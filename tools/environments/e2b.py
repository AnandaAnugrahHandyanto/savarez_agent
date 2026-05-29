"""E2B cloud execution environment.

Uses the E2B Python SDK to run commands in cloud sandboxes. Persistent mode
pauses sandboxes on cleanup and reconnects by sandbox id on the next creation.
"""

import logging
import os
import shlex
import threading
from pathlib import Path

from tools.environments.base import (
    BaseEnvironment,
    _ThreadedProcessHandle,
    _load_json_store,
    _save_json_store,
    get_sandbox_dir,
)
from tools.environments.file_sync import (
    FileSyncManager,
    iter_sync_files,
    quoted_mkdir_command,
    quoted_rm_command,
    unique_parent_dirs,
)

logger = logging.getLogger(__name__)


class E2BEnvironment(BaseEnvironment):
    """E2B cloud sandbox execution backend."""

    _stdin_mode = "heredoc"

    def __init__(
        self,
        template: str = "base",
        cwd: str = "~",
        timeout: int = 60,
        lifetime_seconds: int = 300,
        persistent_filesystem: bool = True,
        task_id: str = "default",
    ):
        requested_cwd = cwd
        super().__init__(cwd=cwd, timeout=timeout)

        try:
            from tools.lazy_deps import ensure as _lazy_ensure

            _lazy_ensure("terminal.e2b", prompt=False)
        except ImportError:
            pass
        except Exception as e:
            raise ImportError(str(e))

        from e2b import Sandbox
        from e2b.exceptions import SandboxException, SandboxNotFoundException

        self._Sandbox = Sandbox
        self._SandboxException = SandboxException
        self._SandboxNotFoundException = SandboxNotFoundException
        self._persistent = persistent_filesystem
        self._task_id = task_id
        self._lifetime_seconds = lifetime_seconds
        self._sandbox = None
        self._lock = threading.Lock()
        self._store_path = get_sandbox_dir() / "e2b" / "sandboxes.json"

        sandbox_id = self._load_sandbox_id()
        if self._persistent and sandbox_id:
            try:
                self._sandbox = Sandbox.connect(sandbox_id, timeout=lifetime_seconds)
                logger.info("E2B: reconnected sandbox %s for task %s", sandbox_id, task_id)
            except SandboxNotFoundException:
                logger.info("E2B: stored sandbox %s no longer exists", sandbox_id)
                self._forget_sandbox_id()
            except Exception as e:
                logger.warning("E2B: failed to reconnect sandbox %s: %s", sandbox_id, e)
                self._sandbox = None

        if self._sandbox is None:
            metadata = {"hermes_task_id": task_id}
            self._sandbox = Sandbox.create(
                template=template or None,
                timeout=lifetime_seconds,
                metadata=metadata,
                lifecycle={"on_timeout": "pause", "auto_resume": True}
                if persistent_filesystem
                else None,
            )
            logger.info("E2B: created sandbox %s for task %s", self._sandbox.sandbox_id, task_id)
            if self._persistent:
                self._save_sandbox_id(self._sandbox.sandbox_id)

        self._remote_home = "/home/user"
        try:
            home = self._sandbox.commands.run("echo $HOME", timeout=timeout).stdout.strip()
            if home:
                self._remote_home = home
                if requested_cwd in {"~", "/home/user", "/root"}:
                    self.cwd = home
        except Exception:
            pass
        logger.info("E2B: resolved home to %s, cwd to %s", self._remote_home, self.cwd)

        self._sync_manager = FileSyncManager(
            get_files_fn=lambda: iter_sync_files(f"{self._remote_home}/.hermes"),
            upload_fn=self._e2b_upload,
            delete_fn=self._e2b_delete,
            bulk_upload_fn=self._e2b_bulk_upload,
            bulk_download_fn=self._e2b_bulk_download,
        )
        self._sync_manager.sync(force=True)
        self.init_session()

    def _load_sandbox_id(self) -> str | None:
        data = _load_json_store(self._store_path)
        value = data.get(self._task_id)
        return str(value) if value else None

    def _save_sandbox_id(self, sandbox_id: str) -> None:
        data = _load_json_store(self._store_path)
        data[self._task_id] = sandbox_id
        _save_json_store(self._store_path, data)

    def _forget_sandbox_id(self) -> None:
        data = _load_json_store(self._store_path)
        if self._task_id in data:
            data.pop(self._task_id, None)
            _save_json_store(self._store_path, data)

    def _e2b_upload(self, host_path: str, remote_path: str) -> None:
        with open(host_path, "rb") as handle:
            self._sandbox.files.write(remote_path, handle)

    def _e2b_bulk_upload(self, files: list[tuple[str, str]]) -> None:
        if not files:
            return

        parents = unique_parent_dirs(files)
        if parents:
            self._sandbox.commands.run(quoted_mkdir_command(parents), timeout=self.timeout)

        for host_path, remote_path in files:
            self._e2b_upload(host_path, remote_path)

    def _e2b_bulk_download(self, dest: Path) -> None:
        rel_base = f"{self._remote_home}/.hermes".lstrip("/")
        remote_tar = f"/tmp/.hermes_sync.{os.getpid()}.tar"
        self._sandbox.commands.run(
            f"tar cf {shlex.quote(remote_tar)} -C / {shlex.quote(rel_base)}",
            timeout=self.timeout,
        )
        data = self._sandbox.files.read(remote_tar, format="bytes")
        dest.write_bytes(bytes(data))
        try:
            self._sandbox.files.remove(remote_tar)
        except Exception:
            pass

    def _e2b_delete(self, remote_paths: list[str]) -> None:
        self._sandbox.commands.run(quoted_rm_command(remote_paths), timeout=self.timeout)

    def _ensure_sandbox_ready(self) -> None:
        if self._sandbox is None:
            raise RuntimeError("E2B sandbox is not initialized")
        try:
            if not self._sandbox.is_running():
                self._sandbox = self._sandbox.connect(timeout=self._lifetime_seconds)
        except Exception:
            sandbox_id = getattr(self._sandbox, "sandbox_id", None)
            if sandbox_id:
                self._sandbox = self._Sandbox.connect(sandbox_id, timeout=self._lifetime_seconds)
            else:
                raise

    def _before_execute(self) -> None:
        with self._lock:
            self._ensure_sandbox_ready()
        self._sync_manager.sync()

    def _run_bash(
        self,
        cmd_string: str,
        *,
        login: bool = False,
        timeout: int = 120,
        stdin_data: str | None = None,
    ):
        sandbox = self._sandbox
        state = {"handle": None}

        def cancel():
            handle = state.get("handle")
            if handle is not None:
                try:
                    handle.kill()
                except Exception:
                    pass

        def exec_fn() -> tuple[str, int]:
            from e2b.sandbox.commands.command_handle import CommandExitException

            parts: list[str] = []
            try:
                handle = sandbox.commands.run(
                    cmd_string,
                    background=True,
                    timeout=timeout,
                    stdin=stdin_data is not None,
                )
                state["handle"] = handle
                if stdin_data is not None:
                    sandbox.commands.send_stdin(handle.pid, stdin_data)
                result = handle.wait(
                    on_stdout=parts.append,
                    on_stderr=parts.append,
                )
                if not parts:
                    parts.extend([result.stdout or "", result.stderr or ""])
                return ("".join(parts), result.exit_code)
            except CommandExitException as exc:
                if not parts:
                    parts.extend([exc.stdout or "", exc.stderr or ""])
                return ("".join(parts), exc.exit_code)
            except Exception as exc:
                if parts:
                    return ("".join(parts) + f"\n[E2B command failed: {exc}]", 1)
                return (f"E2B command failed: {exc}", 1)

        return _ThreadedProcessHandle(exec_fn, cancel_fn=cancel)

    def cleanup(self):
        with self._lock:
            if self._sandbox is None:
                return

            if self._sync_manager:
                logger.info("E2B: syncing files from sandbox...")
                try:
                    self._sync_manager.sync_back()
                except Exception as e:
                    logger.warning("E2B: sync_back failed: %s", e)

            try:
                if self._persistent:
                    self._sandbox.pause()
                    self._save_sandbox_id(self._sandbox.sandbox_id)
                    logger.info("E2B: paused sandbox %s", self._sandbox.sandbox_id)
                else:
                    sandbox_id = self._sandbox.sandbox_id
                    self._sandbox.kill()
                    self._forget_sandbox_id()
                    logger.info("E2B: killed sandbox %s", sandbox_id)
            except Exception as e:
                logger.warning("E2B: cleanup failed: %s", e)
            self._sandbox = None
