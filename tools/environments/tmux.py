"""tmux-backed local execution environment.

This backend keeps commands on the local host like ``LocalEnvironment`` but
routes execution through a profile-scoped tmux session and an agent/task-scoped
window. Hermes still receives deterministic stdout/exit-code results through a
small driver protocol while humans can attach to the tmux session to watch the
live terminal context.
"""

from __future__ import annotations

import logging
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

from tools.environments.base import BaseEnvironment, _ThreadedProcessHandle
from tools.environments.local import (
    _find_bash,
    _make_run_env,
    _prepend_shell_init,
    _resolve_safe_cwd,
    _resolve_shell_init_files,
)

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r"[^A-Za-z0-9_-]+")
_DONE_RE_TEMPLATE = r"\n{marker}(-?\d+){marker}\n"


def _slug(value: object, *, default: str, max_len: int = 64) -> str:
    """Return a tmux-safe session/window name component."""
    text = str(value or "").strip()
    text = _NAME_RE.sub("-", text).strip("-_")
    if not text:
        text = default
    if len(text) > max_len:
        digest = uuid.uuid5(uuid.NAMESPACE_URL, text).hex[:8]
        text = f"{text[: max_len - 9]}-{digest}"
    return text


def _active_profile_name() -> str:
    try:
        from hermes_cli.profiles import get_active_profile_name

        return get_active_profile_name() or "default"
    except Exception:
        return "default"


def _session_env(name: str) -> str:
    try:
        from gateway.session_context import get_session_env

        return get_session_env(name, "") or ""
    except Exception:
        return os.getenv(name, "") or ""


def _format_template(template: str, values: dict[str, str], fallback: str) -> str:
    template = template or fallback
    try:
        rendered = template.format(**values)
    except Exception:
        logger.warning("Invalid tmux name template %r; falling back to %r", template, fallback)
        rendered = fallback.format(**values)
    return rendered


class TmuxEnvironment(BaseEnvironment):
    """Execute commands through a local tmux session/window.

    Session naming defaults to one tmux session per Hermes profile and one
    window per Hermes task/agent inside that session:

    * session: ``hermes-{profile}``
    * window: ``{agent}``

    ``preserve_session=True`` leaves the tmux session/window alive when Hermes
    reaps the Python environment object, which is the point of this backend for
    Desktop/app survivability. Tests can pass ``preserve_session=False`` to clean
    their windows up deterministically.
    """

    _snapshot_timeout = 30

    def __init__(
        self,
        cwd: str = "",
        timeout: int = 60,
        env: dict | None = None,
        *,
        task_id: str = "default",
        session_template: str = "hermes-{profile}",
        window_template: str = "{agent}",
        shell: str = "",
        preserve_session: bool = True,
        history_limit: int = 200_000,
    ):
        if os.name == "nt":
            raise RuntimeError("tmux terminal backend is only supported on POSIX hosts")
        if cwd:
            cwd = os.path.expanduser(cwd)
        super().__init__(cwd=cwd or os.getcwd(), timeout=timeout, env=env or {})

        self.task_id = str(task_id or "default")
        self.profile = _slug(_active_profile_name(), default="default")
        self.session_id = _slug(_session_env("HERMES_SESSION_ID"), default="session")
        self.session_key = _slug(_session_env("HERMES_SESSION_KEY"), default="session")
        self.agent = _slug(self.task_id, default="default")
        self.shell = shell or _find_bash()
        self.preserve_session = bool(preserve_session)
        self.history_limit = int(history_limit or 0)
        self._tmux_bin = shutil.which("tmux")
        self._pane_lock = threading.Lock()
        self._target_ready = False
        self._pane_target = ""
        self._temp_paths: set[Path] = set()

        values = {
            "profile": self.profile,
            "task_id": self.agent,
            "agent": self.agent,
            "session_id": self.session_id,
            "session_key": self.session_key,
        }
        self.session_name = _slug(
            _format_template(session_template, values, "hermes-{profile}"),
            default=f"hermes-{self.profile}",
        )
        self.window_name = _slug(
            _format_template(window_template, values, "{agent}"),
            default=self.agent,
        )

        self.init_session()

    # ------------------------------------------------------------------
    # tmux control helpers
    # ------------------------------------------------------------------

    def _tmux_env(self) -> dict[str, str]:
        env = _make_run_env(self.env)
        # If Hermes itself is running inside tmux, control commands should talk
        # to the server by socket/defaults instead of trying to nest clients.
        env.pop("TMUX", None)
        return env

    def _tmux(self, args: list[str], *, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
        if not self._tmux_bin:
            raise RuntimeError("tmux executable not found; install tmux or set terminal.backend back to local")
        result = subprocess.run(
            [self._tmux_bin, *args],
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._tmux_env(),
            check=False,
        )
        if check and result.returncode != 0:
            raise RuntimeError(
                f"tmux {' '.join(args)} failed with rc={result.returncode}: {result.stderr.strip()}"
            )
        return result

    def _target(self) -> str:
        return f"{self.session_name}:{self.window_name}"

    def _ensure_target(self) -> None:
        safe_cwd = _resolve_safe_cwd(self.cwd)
        if safe_cwd != self.cwd:
            logger.warning(
                "TmuxEnvironment cwd %r is missing on disk; falling back to %r.",
                self.cwd,
                safe_cwd,
            )
            self.cwd = safe_cwd

        has_session = self._tmux(["has-session", "-t", self.session_name], check=False)
        if has_session.returncode != 0:
            args = [
                "new-session",
                "-d",
                "-s",
                self.session_name,
                "-n",
                self.window_name,
                "-c",
                self.cwd,
            ]
            if self.shell:
                args.append(self.shell)
            self._tmux(args)
        else:
            windows = self._tmux(
                ["list-windows", "-t", self.session_name, "-F", "#{window_name}"],
            ).stdout.splitlines()
            if self.window_name not in windows:
                args = [
                    "new-window",
                    "-d",
                    "-t",
                    self.session_name,
                    "-n",
                    self.window_name,
                    "-c",
                    self.cwd,
                ]
                if self.shell:
                    args.append(self.shell)
                self._tmux(args)

        if self.history_limit > 0:
            self._tmux(
                ["set-option", "-t", self.session_name, "-g", "history-limit", str(self.history_limit)],
                check=False,
            )

        pane = self._tmux(["display-message", "-p", "-t", self._target(), "#{pane_id}"]).stdout.strip()
        self._pane_target = pane or self._target()
        self._target_ready = True

    def _tmp_path(self, suffix: str) -> Path:
        root = Path(tempfile.gettempdir()) / "hermes-tmux"
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{self.session_name}-{self.window_name}-{uuid.uuid4().hex[:12]}{suffix}"
        self._temp_paths.add(path)
        return path

    def _close_pipe(self) -> None:
        if self._pane_target:
            self._tmux(["pipe-pane", "-t", self._pane_target], check=False)

    def _send_ctrl_c(self) -> None:
        if self._pane_target:
            self._tmux(["send-keys", "-t", self._pane_target, "C-c"], check=False)

    # ------------------------------------------------------------------
    # BaseEnvironment hooks
    # ------------------------------------------------------------------

    def _run_bash(
        self,
        cmd_string: str,
        *,
        login: bool = False,
        timeout: int = 120,
        stdin_data: str | None = None,
    ):
        if login:
            init_files = _resolve_shell_init_files()
            if init_files:
                cmd_string = _prepend_shell_init(cmd_string, init_files)

        if stdin_data:
            cmd_string = self._embed_stdin_heredoc(cmd_string, stdin_data)

        cancel_event = threading.Event()

        def _cancel() -> None:
            cancel_event.set()
            self._send_ctrl_c()

        return _ThreadedProcessHandle(
            lambda: self._execute_script_in_tmux(cmd_string, login=login, timeout=timeout, cancel_event=cancel_event),
            cancel_fn=_cancel,
        )

    def _execute_script_in_tmux(
        self,
        cmd_string: str,
        *,
        login: bool,
        timeout: int,
        cancel_event: threading.Event,
    ) -> tuple[str, int]:
        with self._pane_lock:
            self._ensure_target()
            run_id = uuid.uuid4().hex
            start_marker = f"__HERMES_TMUX_START_{run_id}__"
            done_marker = f"__HERMES_TMUX_DONE_{run_id}__"
            script_path = self._tmp_path(".sh")
            output_path = self._tmp_path(".out")
            script_path.write_text(cmd_string, encoding="utf-8")
            try:
                os.chmod(script_path, 0o600)
            except OSError:
                pass

            # Reset any stale pipe on this pane, then capture only this run to a
            # fresh file. The command line sent to tmux references only the script
            # path, so the user's command body is not echoed into the model output.
            self._close_pipe()
            pipe_cmd = f"cat > {shlex.quote(str(output_path))}"
            self._tmux(["pipe-pane", "-t", self._pane_target, pipe_cmd])

            bash = shlex.quote(self.shell or _find_bash())
            login_flag = " -l" if login else ""
            command_line = (
                f"printf '\\n{start_marker}\\n'; "
                f"{bash}{login_flag} {shlex.quote(str(script_path))}; "
                f"__hermes_tmux_ec=$?; "
                f"printf '\\n{done_marker}%s{done_marker}\\n' \"$__hermes_tmux_ec\""
            )
            self._tmux(["send-keys", "-t", self._pane_target, "-l", command_line])
            self._tmux(["send-keys", "-t", self._pane_target, "Enter"])

            deadline = time.monotonic() + max(1, int(timeout or self.timeout))
            last_raw = ""
            try:
                while time.monotonic() < deadline:
                    if cancel_event.is_set():
                        self._send_ctrl_c()
                        return self._parse_output(last_raw, start_marker, done_marker, fallback_code=130)
                    if output_path.exists():
                        last_raw = output_path.read_text(encoding="utf-8", errors="replace")
                        parsed = self._try_parse_output(last_raw, start_marker, done_marker)
                        if parsed is not None:
                            return parsed
                    time.sleep(0.05)

                self._send_ctrl_c()
                output, _ = self._parse_output(last_raw, start_marker, done_marker, fallback_code=124)
                suffix = f"\n[Command timed out after {timeout}s]"
                return (output + suffix if output else suffix.lstrip(), 124)
            finally:
                self._close_pipe()
                for path in (script_path, output_path):
                    try:
                        path.unlink()
                        self._temp_paths.discard(path)
                    except OSError:
                        pass

    def _normalise_pane_output(self, raw: str) -> str:
        return raw.replace("\r\n", "\n").replace("\r", "\n")

    def _try_parse_output(self, raw: str, start_marker: str, done_marker: str) -> tuple[str, int] | None:
        text = self._normalise_pane_output(raw)
        start_token = f"\n{start_marker}\n"
        start_idx = text.find(start_token)
        if start_idx == -1:
            return None
        body_start = start_idx + len(start_token)
        done_re = re.compile(_DONE_RE_TEMPLATE.format(marker=re.escape(done_marker)))
        match = done_re.search(text, body_start)
        if not match:
            return None
        output = text[body_start : match.start()]
        try:
            code = int(match.group(1))
        except (TypeError, ValueError):
            code = 1
        return output, code

    def _parse_output(
        self,
        raw: str,
        start_marker: str,
        done_marker: str,
        *,
        fallback_code: int,
    ) -> tuple[str, int]:
        parsed = self._try_parse_output(raw, start_marker, done_marker)
        if parsed is not None:
            return parsed
        text = self._normalise_pane_output(raw)
        start_token = f"\n{start_marker}\n"
        start_idx = text.find(start_token)
        if start_idx != -1:
            return text[start_idx + len(start_token) :], fallback_code
        return text, fallback_code

    def cleanup(self):
        for path in list(self._temp_paths):
            try:
                path.unlink()
            except OSError:
                pass
            self._temp_paths.discard(path)

        if self.preserve_session or not self._target_ready:
            return
        try:
            self._tmux(["kill-window", "-t", self._target()], check=False)
        except Exception:
            pass
