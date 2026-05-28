"""Managed Cloudflare Quick Tunnel helpers for the Photon plugin."""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

DEFAULT_WEBHOOK_PORT = 8788
DEFAULT_WEBHOOK_PATH = "/photon/webhook"
DEFAULT_START_TIMEOUT_SECONDS = 30.0
_TRYCLOUDFLARE_RE = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")


@dataclass
class TunnelStartResult:
    success: bool
    public_url: str = ""
    webhook_url: str = ""
    reused: bool = False
    pid: Optional[int] = None
    error: str = ""
    log_path: Optional[Path] = None
    command: list[str] = field(default_factory=list)


def hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home  # type: ignore
        return Path(get_hermes_home())
    except Exception:
        return Path(os.getenv("HERMES_HOME") or "~/.hermes").expanduser()


def state_dir() -> Path:
    return hermes_home() / "photon"


def state_path() -> Path:
    return state_dir() / "tunnel.json"


def log_path() -> Path:
    return state_dir() / "cloudflared.log"


def _get_env_value(key: str) -> Optional[str]:
    try:
        from hermes_cli.config import get_env_value  # type: ignore
        return get_env_value(key)
    except Exception:
        return os.getenv(key)


def webhook_port() -> int:
    raw = _get_env_value("PHOTON_WEBHOOK_PORT")
    if not raw:
        return DEFAULT_WEBHOOK_PORT
    try:
        port = int(str(raw).strip())
    except ValueError:
        return DEFAULT_WEBHOOK_PORT
    if 1 <= port <= 65535:
        return port
    return DEFAULT_WEBHOOK_PORT


def webhook_path() -> str:
    raw = (_get_env_value("PHOTON_WEBHOOK_PATH") or DEFAULT_WEBHOOK_PATH).strip()
    if not raw:
        return DEFAULT_WEBHOOK_PATH
    if not raw.startswith("/"):
        raw = "/" + raw
    return raw


def local_url() -> str:
    return f"http://127.0.0.1:{webhook_port()}"


def webhook_url_for_base(public_url: str) -> str:
    return public_url.rstrip("/") + webhook_path()


def parse_quick_tunnel_url(text: str) -> str:
    match = _TRYCLOUDFLARE_RE.search(text or "")
    return match.group(0) if match else ""


def is_trycloudflare_url(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    return host == "trycloudflare.com" or host.endswith(".trycloudflare.com")


def load_state() -> dict[str, Any]:
    path = state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(data: dict[str, Any]) -> None:
    directory = state_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = state_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)


def pid_is_running(pid: Any) -> bool:
    try:
        parsed = int(pid)
    except (TypeError, ValueError):
        return False
    if parsed <= 0:
        return False
    try:
        os.kill(parsed, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def _pid_looks_like_cloudflared(pid: Any) -> bool:
    if os.name != "posix":
        return True
    try:
        parsed = int(pid)
    except (TypeError, ValueError):
        return False
    try:
        proc = subprocess.run(  # noqa: S603
            ["ps", "-p", str(parsed), "-o", "comm="],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return True
    name = Path((proc.stdout or "").strip()).name
    return name == "cloudflared"


def status() -> dict[str, Any]:
    state = load_state()
    pid = state.get("pid")
    running = pid_is_running(pid) and _pid_looks_like_cloudflared(pid)
    return {
        "running": running,
        "pid": pid if running else None,
        "public_url": str(state.get("public_url") or ""),
        "webhook_url": str(state.get("webhook_url") or ""),
        "managed": bool(state.get("managed")),
        "started_at": state.get("started_at"),
        "state_path": str(state_path()),
        "log_path": str(log_path()),
    }


def _cloudflared_command(binary: str) -> list[str]:
    return [
        binary,
        "tunnel",
        "--config",
        os.devnull,
        "--url",
        local_url(),
        "--no-autoupdate",
    ]


def start(timeout_seconds: float = DEFAULT_START_TIMEOUT_SECONDS) -> TunnelStartResult:
    current = status()
    if current.get("running") and is_trycloudflare_url(str(current.get("public_url") or "")):
        public_url = str(current.get("public_url") or "")
        webhook_url = str(current.get("webhook_url") or "") or webhook_url_for_base(public_url)
        return TunnelStartResult(
            success=True,
            public_url=public_url,
            webhook_url=webhook_url,
            reused=True,
            pid=int(current["pid"]) if current.get("pid") else None,
            log_path=log_path(),
        )

    binary = shutil.which("cloudflared")
    if not binary:
        return TunnelStartResult(
            success=False,
            error="cloudflared is not installed or not on PATH",
            log_path=log_path(),
        )

    directory = state_dir()
    directory.mkdir(parents=True, exist_ok=True)
    command = _cloudflared_command(binary)
    log_file = log_path()
    with log_file.open("a", encoding="utf-8") as fh:
        fh.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] starting: {' '.join(command)}\n")
        fh.flush()
        proc = subprocess.Popen(  # noqa: S603
            command,
            stdin=subprocess.DEVNULL,
            stdout=fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            text=True,
        )

    deadline = time.monotonic() + timeout_seconds
    public_url = ""
    while time.monotonic() < deadline:
        try:
            text = log_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        public_url = parse_quick_tunnel_url(text)
        if public_url:
            break
        if proc.poll() is not None:
            return TunnelStartResult(
                success=False,
                error=f"cloudflared exited before publishing a tunnel URL (exit {proc.returncode})",
                pid=proc.pid,
                log_path=log_file,
                command=command,
            )
        time.sleep(0.2)

    if not public_url:
        return TunnelStartResult(
            success=False,
            error=f"timed out waiting for a trycloudflare.com URL after {timeout_seconds:.0f}s",
            pid=proc.pid,
            log_path=log_file,
            command=command,
        )

    webhook_url = webhook_url_for_base(public_url)
    save_state({
        "managed": True,
        "pid": proc.pid,
        "public_url": public_url,
        "webhook_url": webhook_url,
        "local_url": local_url(),
        "command": command,
        "started_at": int(time.time()),
        "log_path": str(log_file),
    })
    return TunnelStartResult(
        success=True,
        public_url=public_url,
        webhook_url=webhook_url,
        pid=proc.pid,
        log_path=log_file,
        command=command,
    )


def stop(timeout_seconds: float = 5.0) -> dict[str, Any]:
    current = status()
    pid = current.get("pid")
    if not pid:
        return {"stopped": False, "message": "managed tunnel is not running"}

    parsed = int(pid)
    try:
        if hasattr(os, "killpg"):
            os.killpg(parsed, signal.SIGTERM)
        else:
            os.kill(parsed, signal.SIGTERM)
    except ProcessLookupError:
        return {"stopped": False, "message": "managed tunnel was already stopped"}
    except OSError as e:
        return {"stopped": False, "message": f"could not stop tunnel: {e}"}

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not pid_is_running(parsed):
            return {"stopped": True, "message": f"stopped managed tunnel pid {parsed}"}
        time.sleep(0.1)

    try:
        if hasattr(os, "killpg"):
            os.killpg(parsed, signal.SIGKILL)
        else:
            os.kill(parsed, signal.SIGKILL)
    except OSError:
        pass
    return {"stopped": True, "message": f"stopped managed tunnel pid {parsed}"}


def tail_logs(line_count: int = 80) -> str:
    path = log_path()
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-line_count:])
