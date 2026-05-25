"""
Minimal Railway admin wrapper for Hermes.

- Serves a small admin UI at /
- Health check at /health
- Manages `hermes gateway` as a subprocess
- Stores config in /data/.hermes/.env
- Writes a minimal config.yaml so Hermes picks up the selected model
"""

import asyncio
import base64
import os
import re
import secrets
import signal
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict

from starlette.applications import Starlette
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    SimpleUser,
)
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse
from starlette.routing import Route

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")

HERMES_HOME = os.environ.get("HERMES_HOME", "/data/.hermes")
ENV_FILE = Path(HERMES_HOME) / ".env"
CONFIG_FILE = Path(HERMES_HOME) / "config.yaml"

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
if not ADMIN_PASSWORD:
    ADMIN_PASSWORD = secrets.token_urlsafe(16)
    print(
        f"[server] Admin credentials generated - username: {ADMIN_USERNAME} password: {ADMIN_PASSWORD}",
        flush=True,
    )
else:
    print(f"[server] Admin username: {ADMIN_USERNAME}", flush=True)

ENV_VARS = [
    ("LLM_MODEL", "Model", "model", False),
    ("OPENROUTER_API_KEY", "OpenRouter", "provider", True),
    ("DEEPSEEK_API_KEY", "DeepSeek", "provider", True),
    ("DASHSCOPE_API_KEY", "DashScope", "provider", True),
    ("GLM_API_KEY", "GLM / Z.AI", "provider", True),
    ("KIMI_API_KEY", "Kimi", "provider", True),
    ("MINIMAX_API_KEY", "MiniMax", "provider", True),
    ("HF_TOKEN", "Hugging Face", "provider", True),
    ("TELEGRAM_BOT_TOKEN", "Telegram Bot Token", "channel", True),
    ("DISCORD_BOT_TOKEN", "Discord Bot Token", "channel", True),
    ("SLACK_BOT_TOKEN", "Slack Bot Token", "channel", True),
    ("SLACK_APP_TOKEN", "Slack App Token", "channel", True),
    ("GITHUB_TOKEN", "GitHub Token", "tool", True),
    ("PARALLEL_API_KEY", "Parallel API Key", "tool", True),
    ("FIRECRAWL_API_KEY", "Firecrawl API Key", "tool", True),
    ("TAVILY_API_KEY", "Tavily API Key", "tool", True),
    ("FAL_KEY", "FAL Key", "tool", True),
    ("BROWSERBASE_API_KEY", "Browserbase API Key", "tool", True),
    ("BROWSERBASE_PROJECT_ID", "Browserbase Project ID", "tool", False),
    ("VOICE_TOOLS_OPENAI_KEY", "OpenAI Voice/TTS Key", "tool", True),
    ("HONCHO_API_KEY", "Honcho API Key", "tool", True),
    ("GATEWAY_ALLOW_ALL_USERS", "Allow all users", "gateway", False),
    ("ADMIN_USERNAME", "Admin username", "admin", False),
    ("ADMIN_PASSWORD", "Admin password", "admin", True),
]

SECRET_KEYS = {k for k, _, _, s in ENV_VARS if s}
PROVIDER_KEYS = [k for k, _, category, _ in ENV_VARS if category == "provider"]


def ensure_dirs() -> None:
    for rel in [
        "",
        "cron",
        "sessions",
        "logs",
        "memories",
        "skills",
        "pairing",
        "hooks",
        "image_cache",
        "audio_cache",
        "workspace",
    ]:
        (Path(HERMES_HOME) / rel).mkdir(parents=True, exist_ok=True)


def read_env(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    out: Dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        out[k.strip()] = v
    return out


def write_env(path: Path, data: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for key in sorted(data.keys()):
        value = data[key]
        if value is None:
            continue
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""))


def write_config_yaml(data: Dict[str, str]) -> None:
    model = data.get("LLM_MODEL", "").strip() or "openrouter/auto"
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        f"""model:
  default: "{model}"
  provider: "auto"

terminal:
  backend: "local"
  timeout: 60
  cwd: "/tmp"

agent:
  max_iterations: 50
  data_dir: "{HERMES_HOME}"
"""
    )


def mask(data: Dict[str, str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in data.items():
        if k in SECRET_KEYS and v:
            out[k] = (v[:8] + "***") if len(v) > 8 else "***"
        else:
            out[k] = v
    return out


def unmask(new: Dict[str, str], existing: Dict[str, str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in new.items():
        if k in SECRET_KEYS and isinstance(v, str) and v.endswith("***"):
            out[k] = existing.get(k, "")
        else:
            out[k] = v
    return out


class BasicAuth(AuthenticationBackend):
    async def authenticate(self, conn):
        header = conn.headers.get("Authorization")
        if not header:
