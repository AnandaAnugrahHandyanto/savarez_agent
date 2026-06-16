"""SSH remote execution environment using PowerShell on Windows hosts."""

import base64
import hashlib
import logging
import shlex
import subprocess
import tempfile
from pathlib import Path

from tools.environments.base import BaseEnvironment, _popen_bash
from tools.environments.file_sync import (
    FileSyncManager,
    iter_sync_files,
)
from tools.environments.ssh import (
    SSHEnvironment,
    _ensure_ssh_available,
)

logger = logging.getLogger(__name__)


def _decode_ssh_output(data: bytes) -> str:
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return data.decode("gbk")
    except (UnicodeDecodeError, LookupError):
        pass
    return data.decode("latin-1")


class SSHPwshEnvironment(SSHEnvironment):
    """Run commands on a Windows remote over SSH using PowerShell.

    Extends SSHEnvironment — reuses SSH transport (ControlMaster, scp,
    encoding). Overrides shell-related methods to use ``pwsh`` /
    ``powershell`` instead of ``bash``.

    Uses ``-EncodedCommand`` (base64 UTF-16LE) to pass scripts through
    cmd.exe (the typical SSH server default shell on Windows) without
    quoting issues.
    """

    def __init__(self, host: str, user: str, cwd: str = "~",
                 timeout: int = 60, port: int = 22, key_path: str = ""):
        self.host = host
        self.user = user
        self.port = port
        self.key_path = key_path

        self.control_dir = Path(tempfile.gettempdir()) / "hermes-ssh"
        self.control_dir.mkdir(parents=True, exist_ok=True)

        _socket_id = hashlib.sha256(
            f"{user}@{host}:{port}".encode()
        ).hexdigest()[:16]
        self.control_socket = self.control_dir / f"{_socket_id}.sock"

        _ensure_ssh_available()
        self._detect_shell()
        self._remote_home = self._detect_remote_home()
        self._remote_temp = self._detect_remote_temp()

        # Translate Linux-style cwd to Windows path
        if cwd == "~" or cwd == "/root" or cwd.startswith("/home/"):
            cwd = self._remote_home

        BaseEnvironment.__init__(self, cwd=cwd, timeout=timeout)

        self._ensure_remote_dirs()

        self._sync_manager = FileSyncManager(
            get_files_fn=lambda: iter_sync_files(
                f"{self._remote_home}\\.hermes"
            ),
            upload_fn=self._scp_upload,
            delete_fn=self._ssh_delete,
            bulk_upload_fn=self._ssh_bulk_upload,
            bulk_download_fn=self._ssh_bulk_download,
        )
        self._sync_manager.sync(force=True)
        self.init_session()

    def get_temp_dir(self) -> str:
        return getattr(self, "_remote_temp", "/tmp")

    def _detect_shell(self) -> None:
        for shell in ("pwsh", "powershell"):
            cmd = self._build_ssh_command()
            cmd.extend([shell, "-NoProfile", "-Command", "echo ok"])
            try:
                result = subprocess.run(
                    cmd, capture_output=True, timeout=15,
                    stdin=subprocess.DEVNULL,
                )
                if result.returncode == 0:
                    self._pwsh_cmd = shell
                    logger.debug("SSH pwsh: using %s on %s", shell, self.host)
                    return
            except subprocess.TimeoutExpired:
                continue
        raise RuntimeError(
            f"pwsh/PowerShell not found on remote {self.host}. "
            "Install PowerShell 7 (pwsh) or use ssh backend with bash."
        )

    def _detect_remote_home(self) -> str:
        cmd = self._build_ssh_command()
        cmd.extend([self._pwsh_cmd, "-NoProfile", "-Command",
                     "Write-Output $env:USERPROFILE"])
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=10,
                stdin=subprocess.DEVNULL,
            )
            home = _decode_ssh_output(result.stdout).strip().rstrip("\r\n")
            if home and result.returncode == 0:
                logger.debug("SSH pwsh: remote home = %s", home)
                return home
        except Exception:
            pass
        return f"C:\\Users\\{self.user}"

    def _detect_remote_temp(self) -> str:
        cmd = self._build_ssh_command()
        cmd.extend([self._pwsh_cmd, "-NoProfile", "-Command",
                     "Write-Output $env:TEMP"])
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=10,
                stdin=subprocess.DEVNULL,
            )
            temp = _decode_ssh_output(result.stdout).strip().rstrip("\r\n")
            if temp and result.returncode == 0:
                return temp.replace("\\", "/")
        except Exception:
            pass
        return f"C:/Users/{self.user}/AppData/Local/Temp"

    def _ensure_remote_dirs(self) -> None:
        base = f"{self._remote_home}\\.hermes"
        dirs = [base, f"{base}\\skills", f"{base}\\credentials", f"{base}\\cache"]
        dirs_str = ", ".join(f"'{d}'" for d in dirs)
        cmd = self._build_ssh_command()
        cmd.extend([self._pwsh_cmd, "-NoProfile", "-Command",
                     f"foreach ($d in @({dirs_str})) {{ New-Item -ItemType Directory -Force -Path $d | Out-Null }}"])
        subprocess.run(
            cmd, capture_output=True, timeout=10,
            stdin=subprocess.DEVNULL,
        )

    def _ssh_delete(self, remote_paths: list[str]) -> None:
        paths_str = ", ".join(f"'{p}'" for p in remote_paths)
        cmd = self._build_ssh_command()
        cmd.extend([self._pwsh_cmd, "-NoProfile", "-Command",
                     f"Remove-Item -Force -Path @({paths_str}) -ErrorAction SilentlyContinue"])
        result = subprocess.run(
            cmd, capture_output=True, timeout=10,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"remote rm failed: {_decode_ssh_output(result.stderr).strip()}"
            )

    def _ssh_bulk_upload(self, files: list[tuple[str, str]]) -> None:
        for host_path, remote_path in files:
            self._scp_upload(host_path, remote_path)

    def _ssh_bulk_download(self, dest: Path) -> None:
        raise NotImplementedError(
            "Bulk download via tar is not supported on Windows remotes."
        )

    def _run_bash(self, cmd_string: str, *, login: bool = False,
                  timeout: int = 120,
                  stdin_data: str | None = None) -> subprocess.Popen:
        encoded = base64.b64encode(
            cmd_string.encode("utf-16-le")
        ).decode("ascii")
        cmd = self._build_ssh_command()
        cmd.extend([self._pwsh_cmd, "-NoProfile", "-EncodedCommand", encoded])
        return _popen_bash(cmd, stdin_data)

    def _wrap_command(self, command: str, cwd: str) -> str:
        escaped = command.replace("'", "''")
        _quoted_snap = shlex.quote(self._snapshot_path)
        _quoted_cwd_file = shlex.quote(self._cwd_file)

        parts = []

        if self._snapshot_ready:
            parts.append(f". {_quoted_snap} 2>$null")

        parts.append(f"Set-Location -LiteralPath {shlex.quote(cwd)}")
        parts.append("if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { exit 126 }")

        parts.append(f"Invoke-Expression '{escaped}'")
        parts.append("$script:__hermes_ec = $LASTEXITCODE")

        if self._snapshot_ready:
            parts.append(
                "Get-ChildItem Env: | ForEach-Object { "
                "$val = $_.Value -replace \"'\", \"''\"; "
                "\"`$env:$($_.Name) = '$val'\" "
                f"}} | Set-Content -Encoding UTF8 {_quoted_snap}"
            )

        parts.append(
            f"(Get-Location).Path | Set-Content -NoNewline {_quoted_cwd_file}"
        )
        parts.append(
            f'Write-Output "`n{self._cwd_marker}$((Get-Location).Path){self._cwd_marker}"'
        )
        parts.append("exit $script:__hermes_ec")

        return "\n".join(parts)

    def init_session(self):
        _quoted_cwd = shlex.quote(self.cwd)
        _quoted_snap = shlex.quote(self._snapshot_path)
        _quoted_cwd_file = shlex.quote(self._cwd_file)

        bootstrap_parts = [
            f"Get-ChildItem Env: | ForEach-Object {{ $val = $_.Value -replace \"'\", \"''\"; \"`$env:$($_.Name) = '$val'\" }} | Set-Content -Encoding UTF8 {_quoted_snap}",
            f"Set-Location -LiteralPath {_quoted_cwd}",
            f"(Get-Location).Path | Set-Content -NoNewline {_quoted_cwd_file}",
            f'Write-Output "`n{self._cwd_marker}$((Get-Location).Path){self._cwd_marker}"',
        ]
        bootstrap = "\n".join(bootstrap_parts)

        try:
            proc = self._run_bash(bootstrap, login=True,
                                  timeout=self._snapshot_timeout)
            result = self._wait_for_process(proc,
                                            timeout=self._snapshot_timeout)
            self._snapshot_ready = True
            self._update_cwd(result)
            logger.info(
                "SSH pwsh: session snapshot created (session=%s, cwd=%s)",
                self._session_id, self.cwd,
            )
        except Exception as exc:
            logger.warning(
                "SSH pwsh: init_session failed (session=%s): %s — "
                "falling back to direct pwsh per command",
                self._session_id, exc,
            )
            self._snapshot_ready = False
