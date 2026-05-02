"""Kaze Claude mode plugin.

Chat-level Telegram "Claude lane" for Hermes/Kaze.

Spec-aligned behavior:
- Hermes remains the Telegram/runtime/session owner (routing, auth, approvals).
- When enabled for a Telegram chat, *plain (non-slash)* messages are routed to a
  Claude Code CLI execution lane (headless `claude -p`), not a hidden model
  provider switch.
- Slash commands remain escape hatches and are never captured as Claude-mode
  plain messages.
"""

from __future__ import annotations

import base64
import json
import os
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from shlex import quote as shell_quote
from shutil import which
from typing import Any

from hermes_constants import display_hermes_home, get_hermes_home

PLUGIN_NAME = "kaze-claude-mode"

MODE_COMMANDS = {"claude-mode", "claude_mode"}
INTERNAL_MODE = "kaze-claude-mode-dispatch"
INTERNAL_RUN = "kaze-claude-mode-run"

MAX_REPLY_CHARS = 3900
_PENDING_TTL_SECS = 120

_CTX = None  # set by register()

_BOUNCE_PREFIX = (
    "Claude mode is enabled for this chat, but the Claude Code CLI backend is not available.\n"
    "Run `/claude-mode status` for setup info."
)


@dataclass(frozen=True)
class _PendingPrompt:
    chat_key: str
    session_key: str
    prompt: str
    created_at: float


_PENDING: dict[str, _PendingPrompt] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _platform_value(source: Any) -> str:
    platform = getattr(source, "platform", "")
    return getattr(platform, "value", str(platform or ""))


def state_key_from_source(source: Any) -> str:
    """Stable per-chat key; includes thread/topic when Hermes exposes it."""
    platform = _platform_value(source) or "unknown"
    chat_id = str(getattr(source, "chat_id", "") or "unknown")
    thread_id = str(getattr(source, "thread_id", "") or "")
    if thread_id:
        return f"{platform}:{chat_id}:{thread_id}"
    return f"{platform}:{chat_id}"


def _state_path() -> Path:
    raw = os.environ.get("KAZE_CLAUDE_MODE_STATE", "").strip()
    if raw:
        return Path(raw)
    return get_hermes_home() / "state" / "kaze_claude_mode.json"


def _load_state(path: Path | None = None) -> dict[str, Any]:
    path = _state_path() if path is None else path
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_name, path)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except OSError:
            pass


def is_enabled(key: str, *, path: Path | None = None) -> bool:
    path = _state_path() if path is None else path
    entry = (_load_state(path).get("chats") or {}).get(key) or {}
    return bool(entry.get("enabled"))


def set_enabled(
    key: str,
    enabled: bool,
    *,
    source: Any = None,
    path: Path | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = _state_path() if path is None else path
    state = _load_state(path)
    chats = state.setdefault("chats", {})
    if not isinstance(chats, dict):
        chats = {}
        state["chats"] = chats
    entry = chats.setdefault(key, {})
    if not isinstance(entry, dict):
        entry = {}
        chats[key] = entry
    entry.update({
        "enabled": bool(enabled),
        "updated_at": _now_iso(),
    })
    if source is not None:
        entry["platform"] = _platform_value(source)
        entry["chat_id"] = str(getattr(source, "chat_id", "") or "")
        thread_id = getattr(source, "thread_id", None)
        if thread_id:
            entry["thread_id"] = str(thread_id)
    if extra:
        entry.update({k: v for k, v in extra.items() if v is not None})
    state["updated_at"] = _now_iso()
    _atomic_write_json(path, state)
    return entry


def _encode_packet(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_packet(raw: str) -> dict[str, Any]:
    try:
        data = base64.urlsafe_b64decode(raw.strip().encode("ascii"))
        parsed = json.loads(data.decode("utf-8"))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _command_name(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped.startswith("/"):
        return ""
    token = stripped.split(maxsplit=1)[0].lstrip("/")
    # Telegram group commands may arrive as /cmd@bot.
    return token.split("@", 1)[0].lower()


def _command_args(text: str) -> str:
    stripped = (text or "").strip()
    parts = stripped.split(maxsplit=1)
    return parts[1] if len(parts) > 1 else ""


def _claude_code_cli_candidates() -> tuple[str, ...]:
    return ("claude", "claude-code")


def _resolve_claude_code_cli_backend() -> tuple[bool, dict[str, Any]]:
    """Return (ok, info) for the Claude Code CLI backend.

    This checks binary presence only; auth is exercised by smoke and live runs.
    """
    for cmd in _claude_code_cli_candidates():
        path = which(cmd)
        if path:
            return True, {"backend": "claude-code-cli", "cmd": cmd, "path": path}
    return False, {
        "backend": "claude-code-cli",
        "cmd": "",
        "path": "",
        "error": "Claude Code CLI not found on PATH",
    }


def _claude_code_allowed_tools() -> str:
    # Safe default: no shell/Bash tool, only read+edit.
    raw = os.environ.get("KAZE_CLAUDE_MODE_ALLOWED_TOOLS", "Read,Edit").strip()
    return raw or "Read,Edit"


def _claude_code_permission_mode() -> str:
    raw = os.environ.get("KAZE_CLAUDE_MODE_PERMISSION_MODE", "acceptEdits").strip()
    allowed = {"acceptEdits", "auto", "default", "dontAsk", "plan"}
    return raw if raw in allowed else "acceptEdits"


def _claude_code_max_turns() -> int:
    raw = os.environ.get("KAZE_CLAUDE_MODE_MAX_TURNS", "10").strip()
    try:
        value = int(raw)
    except Exception:
        value = 10
    return max(1, min(60, value))


def _claude_code_timeout_secs() -> int:
    raw = os.environ.get("KAZE_CLAUDE_MODE_TIMEOUT", "240").strip()
    try:
        value = int(raw)
    except Exception:
        value = 240
    return max(30, min(1800, value))


def _gc_pending(now: float | None = None) -> None:
    now = time.time() if now is None else now
    expired = [k for k, v in _PENDING.items() if (now - v.created_at) > _PENDING_TTL_SECS]
    for k in expired:
        _PENDING.pop(k, None)


def _stash_pending_prompt(*, chat_key: str, session_key: str, prompt: str) -> str:
    _gc_pending()
    token = os.urandom(9).hex()
    _PENDING[token] = _PendingPrompt(
        chat_key=chat_key,
        session_key=session_key,
        prompt=prompt,
        created_at=time.time(),
    )
    return token


def _pop_pending_prompt(token: str) -> _PendingPrompt | None:
    _gc_pending()
    return _PENDING.pop((token or "").strip(), None)


def build_pre_dispatch_decision(event: Any, gateway: Any = None) -> dict[str, Any] | None:
    """Return a pre_gateway_dispatch rewrite/allow decision for an event."""
    text = getattr(event, "text", None) or ""
    source = getattr(event, "source", None)
    if not source or not text.strip():
        return None
    platform = _platform_value(source)
    if platform != "telegram":
        return None

    chat_key = state_key_from_source(source)
    cmd = _command_name(text)

    # /claude-mode itself is rewritten to our internal dispatcher so we can
    # identify the chat + (when possible) the gateway session key.
    if cmd in MODE_COMMANDS:
        session_key = ""
        if gateway is not None:
            try:
                session_key = gateway._session_key_for_source(source)
            except Exception:
                session_key = ""
        packet = {
            "key": chat_key,
            "args": _command_args(text),
            "platform": platform,
            "chat_id": str(getattr(source, "chat_id", "") or ""),
            "thread_id": str(getattr(source, "thread_id", "") or ""),
            "session_key": session_key,
        }
        return {"action": "rewrite", "text": f"/{INTERNAL_MODE} {_encode_packet(packet)}"}

    # Slash commands are escape hatches.
    if cmd:
        return None

    # Plain messages in an enabled chat route to Claude Code.
    if is_enabled(chat_key):
        ok, _info = _resolve_claude_code_cli_backend()
        if not ok:
            # Backend missing: fail closed with a clear message. Avoid embedding
            # user text in the rewritten command to reduce logging leakage.
            return {
                "action": "rewrite",
                "text": f"/{INTERNAL_MODE} {_encode_packet({'key': chat_key, 'args': 'unavailable'})}",
            }
        if gateway is None:
            return {
                "action": "rewrite",
                "text": f"/{INTERNAL_MODE} {_encode_packet({'key': chat_key, 'args': 'unavailable'})}",
            }
        try:
            session_key = gateway._session_key_for_source(source)
        except Exception:
            session_key = ""
        token = _stash_pending_prompt(chat_key=chat_key, session_key=session_key, prompt=text)
        return {"action": "rewrite", "text": f"/{INTERNAL_RUN} {token}"}

    return None


def pre_gateway_dispatch(event: Any = None, gateway: Any = None, session_store: Any = None, **_: Any) -> dict[str, Any] | None:
    return build_pre_dispatch_decision(event, gateway)


def _format_backend_status() -> tuple[str, bool]:
    ok, info = _resolve_claude_code_cli_backend()
    if ok:
        return f"`claude-code-cli` (cmd=`{info.get('cmd')}`, path=`{info.get('path')}`)", True
    return (
        "Claude Code CLI unavailable.\n"
        "Install: `npm install -g @anthropic-ai/claude-code`\n"
        "Auth check: `claude auth status --text`\n"
        "PATH hint: ensure your npm global bin is on PATH for the gateway process.\n"
        f"(Hermes home: {display_hermes_home()})",
        False,
    )


class contextlib_suppress:
    def __init__(self, *exceptions: type[BaseException]) -> None:
        self.exceptions = exceptions or (Exception,)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return exc_type is not None and issubclass(exc_type, self.exceptions)


def _status_message(key: str) -> str:
    state = _load_state()
    entry = ((state.get("chats") or {}).get(key) or {}) if isinstance(state, dict) else {}
    mode = "on" if entry.get("enabled") else "off"
    updated = entry.get("updated_at") or "unknown"
    backend, toolful = _format_backend_status()
    tool_state = "**active**" if (entry.get("enabled") and toolful) else "**inactive**"
    return (
        f"Claude mode: **{mode}**\n"
        f"chat: `{key}`\n"
        f"updated: `{updated}`\n"
        f"backend: {backend}\n"
        f"tool/edit: {tool_state}"
    )


def _truncate_reply(text: str, limit: int = MAX_REPLY_CHARS) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 20)].rstrip() + "\n\n…(truncated)…"


def _extract_terminal_text(payload: dict[str, Any]) -> str:
    stdout = str(payload.get("stdout") or payload.get("output") or payload.get("result") or "")
    stderr = str(payload.get("stderr") or "")
    combined = stdout.strip() or stderr.strip()
    return combined


def _dispatch_tool(tool_name: str, args: dict[str, Any], **kwargs: Any) -> str:
    """Dispatch built-in Hermes tools from plugin command context.

    Plugin discovery can happen before built-in tool modules are imported in
    standalone command/plugin probes, so force idempotent built-in discovery
    before using PluginContext.dispatch_tool.
    """
    from tools.registry import discover_builtin_tools

    discover_builtin_tools()
    return _CTX.dispatch_tool(tool_name, args, **kwargs)


async def _run_claude_code_print(
    *,
    prompt: str,
    session_key: str,
    task_id: str,
    workdir: str | None = None,
) -> tuple[bool, str]:
    """Run Claude Code CLI in headless print mode.

    Critical: do NOT put the raw prompt on the shell command line (it would be
    logged by approval/safety layers). Feed it via a temp file.
    """
    global _CTX
    if _CTX is None:
        return False, "Claude mode failed: plugin context unavailable (tools not wired)."

    ok, info = _resolve_claude_code_cli_backend()
    if not ok:
        backend, _toolful = _format_backend_status()
        return False, backend

    try:
        from tools.approval import reset_current_session_key, set_current_session_key
        token = set_current_session_key(session_key or "")
    except Exception:
        token = None
        reset_current_session_key = None

    tmp_dir = get_hermes_home() / "tmp" / "kaze_claude_mode"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = tmp_dir / f"prompt_{os.urandom(4).hex()}.txt"
    try:
        write_raw = _dispatch_tool(
            "write_file",
            {"path": str(prompt_path), "content": prompt},
            task_id=task_id,
        )
        write_payload = json.loads(write_raw) if isinstance(write_raw, str) else {}
        if write_payload.get("error"):
            return False, "Claude mode failed: could not stage prompt for Claude Code."

        allowed = _claude_code_allowed_tools()
        max_turns = _claude_code_max_turns()

        permission_mode = _claude_code_permission_mode()

        # Use $(cat <file>) so the prompt is NOT present in the command string
        # Hermes logs (inbound previews, approval queues, etc.).
        cmd = (
            f"{shell_quote(str(info.get('cmd') or 'claude'))} -p "
            f"\"$(cat {shell_quote(str(prompt_path))})\" "
            f"--allowedTools {shell_quote(allowed)} "
            f"--permission-mode {shell_quote(permission_mode)} "
            f"--max-turns {max_turns}"
        )
        term_raw = _dispatch_tool(
            "terminal",
            {"command": cmd, "timeout": _claude_code_timeout_secs(), "workdir": workdir},
            task_id=task_id,
        )
        term = json.loads(term_raw) if isinstance(term_raw, str) else {}
        if term.get("status") == "approval_required":
            return False, "Claude mode: waiting for approval to run Claude Code CLI."
        out = _extract_terminal_text(term)
        exit_code = term.get("exit_code")
        if exit_code not in (None, 0, "0"):
            err = out or "Claude Code returned a non-zero exit code."
            return False, _truncate_reply(f"Claude Code error:\n{err}")
        return True, _truncate_reply(out or "(Claude Code returned no output.)")
    finally:
        if token is not None and reset_current_session_key is not None:
            with contextlib_suppress(Exception):
                reset_current_session_key(token)
        with contextlib_suppress(Exception):
            if prompt_path.exists():
                prompt_path.unlink()


async def handle_internal_mode(raw_args: str) -> str:
    packet = _decode_packet(raw_args)
    key = str(packet.get("key") or "").strip()
    args = str(packet.get("args") or "").strip().lower()
    session_key = str(packet.get("session_key") or "").strip()
    if not key:
        return "Claude mode could not identify this chat."

    if args in {"on", "enable", "enabled"}:
        ok, _info = _resolve_claude_code_cli_backend()
        backend, toolful = _format_backend_status()
        if not ok:
            set_enabled(
                key,
                False,
                extra={
                    "backend": "claude-code-cli",
                    "tool_edit_active": False,
                    "last_enable_error": "Claude Code CLI not found",
                },
            )
            return (
                "Claude mode: **off**\n"
                f"backend: {backend}\n\n"
                "Cannot enable Claude Code mode because the CLI backend is unavailable."
            )
        set_enabled(
            key,
            True,
            extra={
                "backend": "claude-code-cli",
                "tool_edit_active": True,
                "last_enable_error": "",
            },
        )
        return (
            "Claude mode: **on**\n"
            f"backend: {backend}\n"
            "Plain (non-slash) messages in this chat now route through Claude Code CLI (headless `claude -p`).\n"
            "Use `/claude-mode off` to return to normal Hermes/Kaze."
        )

    if args in {"off", "disable", "disabled"}:
        set_enabled(key, False, extra={"tool_edit_active": False})
        return "Claude mode: **off**\nPlain messages now use normal Kaze/Hermes again."

    if args in {"status", ""}:
        return _status_message(key) + "\n\nUsage: `/claude-mode on|off|status|smoke`"

    if args == "unavailable":
        backend, _toolful = _format_backend_status()
        return f"{_BOUNCE_PREFIX}\n\nbackend: {backend}\n\nUse `/hermes <message>` to talk to Hermes."

    if args == "smoke":
        backend, toolful = _format_backend_status()
        ok, info = _resolve_claude_code_cli_backend()
        if not ok or not toolful:
            return f"Smoke: **unavailable**\nbackend: {backend}"

        # Prove the real backend: run `claude -p` and verify it can edit a temp file.
        tmp_dir = get_hermes_home() / "tmp" / "kaze_claude_mode_smoke"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = tmp_dir / f"smoke_{os.urandom(3).hex()}.txt"
        marker = "KAZE_CLAUDE_MODE_FILE_OK"
        _dispatch_tool("write_file", {"path": str(tmp_file), "content": "before\n"}, task_id="claude_mode_smoke")

        prompt = (
            "In the current directory, open the file named "
            f"{tmp_file.name} and replace its entire content with exactly this single line:\n"
            f"{marker}\n"
            "Do not add any other text."
        )
        ok_run, out = await _run_claude_code_print(
            prompt=prompt,
            session_key=session_key,
            task_id="claude_mode_smoke",
            workdir=str(tmp_dir),
        )
        if not ok_run:
            with contextlib_suppress(Exception):
                tmp_file.unlink(missing_ok=True)
            return f"Smoke: **FAILED**\n{out}"

        # Verify edit happened (single-line marker) and clean up.
        body = ""
        try:
            raw = _dispatch_tool(
                "terminal",
                {
                    "command": (
                        f"python -c {shell_quote('import pathlib;print(pathlib.Path(' + repr(str(tmp_file)) + ').read_text())')}"
                    ),
                    "timeout": 10,
                },
                task_id="claude_mode_smoke_verify",
            )
            payload = json.loads(raw) if isinstance(raw, str) else {}
            body = _extract_terminal_text(payload)
        except Exception:
            body = ""
        with contextlib_suppress(Exception):
            tmp_file.unlink(missing_ok=True)
        if marker not in body:
            return "Smoke: **FAILED**\nClaude Code ran but did not apply the expected file edit in the temp dir."

        return (
            "Smoke: **OK**\n"
            "- backend: `claude-code-cli`\n"
            f"- allowedTools: `{_claude_code_allowed_tools()}`\n"
            f"- permission-mode: `{_claude_code_permission_mode()}`\n"
            f"- temp edit+cleanup: `{tmp_file.name}`"
        )

    return "Usage: `/claude-mode on|off|status|smoke`"


async def handle_internal_run(raw_args: str) -> str:
    pending = _pop_pending_prompt(raw_args)
    if pending is None:
        return "Claude mode: expired request. Please resend the message."

    ok, _info = _resolve_claude_code_cli_backend()
    if not ok:
        set_enabled(
            pending.chat_key,
            False,
            extra={
                "backend": "claude-code-cli",
                "tool_edit_active": False,
                "last_enable_error": "Claude Code CLI not found",
            },
        )
        backend, _toolful = _format_backend_status()
        return (
            "Claude mode: **off** (auto-disabled)\n"
            f"backend: {backend}\n\n"
            "Claude Code CLI is unavailable. Your message was not routed.\n"
            "Use `/hermes <message>` to talk to Hermes, or re-enable after setup."
        )

    ok_run, out = await _run_claude_code_print(
        prompt=pending.prompt,
        session_key=pending.session_key,
        task_id="claude_mode_run",
    )
    return out


async def handle_public_mode(raw_args: str) -> str:
    return "Use `/claude-mode on|off|status|smoke` from Telegram so the plugin can identify the chat."


def register(ctx: Any) -> None:
    global _CTX
    _CTX = ctx
    ctx.register_hook("pre_gateway_dispatch", pre_gateway_dispatch)
    ctx.register_command(
        "claude-mode",
        handle_public_mode,
        "Toggle chat-level Claude Code CLI mode",
        "on|off|status|smoke",
    )
    ctx.register_command(INTERNAL_MODE, handle_internal_mode, "Internal Kaze Claude mode control", "<packet>")
    ctx.register_command(INTERNAL_RUN, handle_internal_run, "Internal Kaze Claude Code runner", "<token>")
