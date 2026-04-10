"""Configuration for MemTensor hermes-agent memory provider."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

DAEMON_PORT = 18992
VIEWER_PORT = 18901
OWNER = "hermes"


def get_plugin_dir() -> Path:
    return Path(__file__).resolve().parent


def get_memos_state_dir() -> Path:
    env = os.environ.get("MEMOS_STATE_DIR")
    if env:
        return Path(env)
    state_dir = get_hermes_home() / "memos-state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def get_daemon_dir() -> Path:
    d = get_memos_state_dir() / "daemon"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_daemon_port() -> int:
    env = os.environ.get("MEMOS_DAEMON_PORT")
    if env:
        return int(env)
    port_file = get_daemon_dir() / "bridge.port"
    if port_file.exists():
        try:
            return int(port_file.read_text().strip())
        except (ValueError, OSError):
            pass
    return DAEMON_PORT


def get_viewer_port() -> int:
    env = os.environ.get("MEMOS_VIEWER_PORT")
    if env:
        return int(env)
    return VIEWER_PORT


def _read_hermes_model_config() -> dict:
    """Read embedding/summarizer config from hermes-scoped memtensor.json."""
    config_path = get_hermes_home() / "memtensor.json"
    try:
        with open(config_path) as f:
            raw = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}

    result: dict = {}
    if raw.get("embedding", {}).get("provider"):
        result["embedding"] = raw["embedding"]
    if raw.get("summarizer", {}).get("provider"):
        result["summarizer"] = raw["summarizer"]
    return result


def get_bridge_config() -> dict:
    """Build configuration dict for the memos-core-bridge process."""
    env_config = os.environ.get("MEMOS_BRIDGE_CONFIG")
    if env_config:
        try:
            return json.loads(env_config)
        except json.JSONDecodeError:
            pass

    state_dir = str(get_memos_state_dir())
    config: dict = {"stateDir": state_dir}
    plugin_config: dict = {}

    embedding_provider = os.environ.get("MEMOS_EMBEDDING_PROVIDER")
    if embedding_provider:
        plugin_config["embedding"] = {"provider": embedding_provider}
        api_key = os.environ.get("MEMOS_EMBEDDING_API_KEY")
        if api_key:
            plugin_config["embedding"]["apiKey"] = api_key
        endpoint = os.environ.get("MEMOS_EMBEDDING_ENDPOINT")
        if endpoint:
            plugin_config["embedding"]["endpoint"] = endpoint

    if "embedding" not in plugin_config:
        hermes_config = _read_hermes_model_config()
        if hermes_config.get("embedding"):
            plugin_config["embedding"] = hermes_config["embedding"]
        if hermes_config.get("summarizer"):
            plugin_config["summarizer"] = hermes_config["summarizer"]

    plugin_config["telemetry"] = {"platform": "hermes"}

    if plugin_config:
        config["config"] = plugin_config

    logo_svg = str(get_plugin_dir() / "logo.svg")
    config["branding"] = {
        "title": "Hermes Memory",
        "titleEn": "Hermes Memory",
        "suffix": "Hermes",
        "favicon": "https://hermes-agent.nousresearch.com/docs/img/favicon.ico",
        "logoSvgPath": logo_svg,
    }

    return config


def _get_plugin_root() -> Path:
    """Return the memos-local-plugin root directory.

    Resolution order:
      1. MEMOS_PLUGIN_ROOT env var (explicit override)
      2. bridge_path.txt recorded by install.sh (derive parent from bridge.cts path)
      3. Fallback: two levels up from this plugin dir (works when symlinked)
    """
    env = os.environ.get("MEMOS_PLUGIN_ROOT")
    if env:
        return Path(env)

    bridge_path_file = get_plugin_dir() / "bridge_path.txt"
    if bridge_path_file.exists():
        recorded = bridge_path_file.read_text().strip()
        if recorded:
            candidate = Path(recorded).parent
            if (candidate / "package.json").exists():
                return candidate

    fallback = get_plugin_dir().parent.parent
    if (fallback / "package.json").exists():
        return fallback

    return get_plugin_dir()


def _resolve_tsx(plugin_root: Path) -> str:
    """Return absolute path to tsx binary, preferring the local node_modules copy."""
    local_tsx = plugin_root / "node_modules" / ".bin" / "tsx"
    if local_tsx.exists():
        return str(local_tsx)
    import shutil
    global_tsx = shutil.which("tsx")
    if global_tsx:
        return global_tsx
    return "npx tsx"


def find_bridge_script() -> list[str]:
    """Locate the bridge.cts entry point and return the command to run it."""
    plugin_dir = get_plugin_dir()
    plugin_root = _get_plugin_root()

    candidates: list[Path] = []

    env_path = os.environ.get("MEMOS_BRIDGE_SCRIPT")
    if env_path:
        candidates.append(Path(env_path))

    bridge_path_file = plugin_dir / "bridge_path.txt"
    if bridge_path_file.exists():
        recorded = bridge_path_file.read_text().strip()
        if recorded:
            candidates.append(Path(recorded))

    candidates.append(plugin_root / "bridge.cts")

    for candidate in candidates:
        if candidate.exists():
            if candidate.suffix == ".js":
                return ["node", str(candidate)]
            tsx = _resolve_tsx(candidate.parent)
            if " " in tsx:
                return tsx.split() + [str(candidate)]
            return [tsx, str(candidate)]

    raise FileNotFoundError(
        "Cannot locate memos bridge script. Looked in:\n"
        + "\n".join(f"  - {c}" for c in candidates)
        + "\n\nRun install.sh first to set up the memos-local-plugin runtime."
    )
