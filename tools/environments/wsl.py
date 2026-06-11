"""WSL2 execution environment - terminal inside WSL, file tools on Windows.

Mirrors Docker's philosophy: no path translation. The agent is told
(via prompt) to use Linux paths for terminal commands and Windows paths
for file tools.

.. note::
    ``self.cwd`` stores a **Linux** path (e.g. ``/home/agents``), not a
    Windows path.  This is correct because ``cd`` commands dispatch
    through WSL's bash.  It differs from ``LocalEnvironment`` where
    ``self.cwd`` is a Windows native path.
"""

import logging
import os
import shutil
import subprocess

from tools.environments.base import BaseEnvironment, _pipe_stdin
from hermes_cli._subprocess_compat import windows_hide_flags


logger = logging.getLogger(__name__)


def _find_wsl() -> str:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    system32_wsl = os.path.join(system_root, "System32", "wsl.exe")
    if os.path.isfile(system32_wsl):
        return system32_wsl
    found = shutil.which("wsl")
    if found:
        return found
    raise RuntimeError(
        "wsl.exe not found. Install WSL2: "
        "https://learn.microsoft.com/en-us/windows/wsl/install"
    )


def _probe_wsl_home(wsl_exe: str, distro: str = "") -> str:
    try:
        args = [wsl_exe]
        if distro:
            args.extend(["-d", distro])
        args.extend(["-e", "bash", "-c", "echo $HOME"])
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=5,
            creationflags=windows_hide_flags(),
        )
        home = result.stdout.strip()
        if home and home.startswith("/"):
            return home
    except Exception:
        pass
    return "/root"


class WslEnvironment(BaseEnvironment):
    """Run terminal commands inside WSL2 via ``wsl -e bash``.

    No path translation - same as Docker. The agent receives prompt hints
    telling it to use Linux paths for ``terminal`` and Windows paths for
    ``read_file``/``write_file``/``patch``/``search_files``.

    Optional env vars:
      TERMINAL_WSL_DISTRO  - WSL distribution name (e.g. "Debian")
    """

    _snapshot_timeout: int = 30

    def __init__(self, cwd: str = "", timeout: int = 60, env: dict = None):
        self._wsl = _find_wsl()
        self._distro = os.getenv("TERMINAL_WSL_DISTRO", "")
        if not cwd:
            cwd = _probe_wsl_home(self._wsl, self._distro)
        super().__init__(cwd=cwd, timeout=timeout, env=env)
        self.init_session()

    def get_temp_dir(self) -> str:
        return "/tmp"

    def _run_bash(
        self,
        cmd_string: str,
        *,
        login: bool = False,
        timeout: int = 120,   # enforced by BaseEnvironment._wait_for_process
        stdin_data: str | None = None,
    ) -> subprocess.Popen:
        wsl_args = [self._wsl]
        if self._distro:
            wsl_args.extend(["-d", self._distro])
        if login:
            wsl_args.extend(["-e", "bash", "-l", "-c", cmd_string])
        else:
            wsl_args.extend(["-e", "bash", "-c", cmd_string])

        proc = subprocess.Popen(
            wsl_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE if stdin_data is not None else subprocess.DEVNULL,
            text=True,
            creationflags=windows_hide_flags(),
        )

        if stdin_data is not None:
            _pipe_stdin(proc, stdin_data)

        return proc

    def _update_cwd(self, result: dict):
        self._extract_cwd_from_output(result)

    def cleanup(self):
        for f in (self._snapshot_path, self._cwd_file):
            try:
                os.unlink(f)
            except OSError:
                pass

    def _kill_process(self, proc):
        try:
            proc.terminate()
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
