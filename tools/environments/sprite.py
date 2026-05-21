"""Sprite CLI execution environment.

Runs Hermes terminal commands inside a persistent Sprite using the local
``sprite`` CLI.  Sprite creation/authentication are intentionally left to the
operator because they can prompt, open browsers, or spend remote resources.
"""

from __future__ import annotations

import logging
import os
import shlex
import shutil
import signal
import subprocess

from tools.environments.base import BaseEnvironment, _pipe_stdin

logger = logging.getLogger(__name__)


def ensure_sprite_available() -> str:
    """Return the sprite executable path or fail with an actionable error."""
    executable = shutil.which("sprite")
    if not executable:
        raise RuntimeError(
            "Sprite CLI is not installed or not in PATH. Install it with "
            "`curl -fsSL https://sprites.dev/install.sh | sh`, then authenticate "
            "with `sprite org auth` or `sprite auth setup --token ...`."
        )
    return executable


class SpriteEnvironment(BaseEnvironment):
    """Run commands inside a persistent Sprite via ``sprite exec``.

    Spawn-per-call: every execute() ultimately invokes ``sprite exec bash -lc``.
    Session state is preserved through BaseEnvironment's env snapshot and cwd
    marker files stored inside the Sprite filesystem.  The Sprite itself is not
    created or destroyed here; configure an existing Sprite with
    ``terminal.sprite``/``TERMINAL_SPRITE`` or rely on the Sprite CLI's active
    local context.
    """

    def __init__(
        self,
        cwd: str = "/root",
        timeout: int = 60,
        *,
        org: str = "",
        sprite: str = "",
        http_post: bool = False,
        env: dict | None = None,
    ):
        self.sprite_executable = ensure_sprite_available()
        self.org = (org or "").strip()
        self.sprite = (sprite or "").strip()
        self.http_post = bool(http_post)
        super().__init__(cwd=cwd or "/root", timeout=timeout, env=env or {})
        # Pass stdin through the sprite CLI rather than embedding it into the
        # remote shell command.  This preserves binary-ish payloads as well as
        # the existing local backend behavior.
        self._stdin_mode = "pipe"
        self.init_session()

    def _sprite_context_args(self) -> list[str]:
        args: list[str] = []
        if self.org:
            args.extend(["-o", self.org])
        if self.sprite:
            args.extend(["-s", self.sprite])
        return args

    def cleanup(self):
        """No-op: Hermes does not own Sprite lifecycle or destroy remote state."""
        return None

    def _run_bash(
        self,
        cmd_string: str,
        *,
        login: bool = False,
        timeout: int = 120,
        stdin_data: str | None = None,
    ) -> subprocess.Popen:
        # ``sprite exec`` accepts command argv after its flags.  Run a remote
        # bash so BaseEnvironment can pass a multi-line wrapper script and keep
        # cwd/env semantics consistent with Docker/SSH/Modal backends.
        bash_flag = "-lc" if login else "-c"
        args = [self.sprite_executable, "exec"]
        args.extend(self._sprite_context_args())
        args.extend(["--dir", self.cwd])
        if self.http_post:
            args.append("--http-post")
        args.extend(["bash", bash_flag, cmd_string])

        logger.debug(
            "Running command via Sprite: %s", shlex.join(args[:-1] + ["<script>"])
        )
        proc = subprocess.Popen(
            args,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.PIPE if stdin_data is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=(os.name != "nt"),
        )
        if stdin_data is not None:
            _pipe_stdin(proc, stdin_data)
        return proc

    def _kill_process(self, proc):
        """Terminate the local sprite CLI process group when possible."""
        try:
            if os.name != "nt":
                pid = getattr(proc, "pid", None)
                if pid is not None:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                else:
                    proc.kill()
            else:
                proc.kill()
        except (ProcessLookupError, PermissionError, OSError):
            pass
