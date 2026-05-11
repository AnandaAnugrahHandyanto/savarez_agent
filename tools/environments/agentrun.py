"""Alibaba Cloud AgentRun execution environment.

Uses the ``agentrun-sdk`` Python package
(`pip install agentrun-sdk`, ``import agentrun``) to run shell commands in
managed Code Interpreter sandboxes on Alibaba Cloud Function Compute v3 /
AgentRun. Supports persistent sandboxes across sessions: when enabled, the
sandbox id is stored locally and the sandbox is reconnected on the next
construction with the same ``task_id`` (vendor-side session affinity:
sandboxes survive idle periods up to ``sandbox_idle_timeout_seconds``,
and once their idle timeout fires the AgentRun control plane reaps them).

Compared to ``modal.py``:

* AgentRun does not expose a snapshot API. Filesystem persistence is
  provided by reconnecting to the same long-lived sandbox via
  ``Sandbox.connect(sandbox_id)``; the sandbox stays alive across calls
  as long as it is reused within ``sandbox_idle_timeout_seconds``.
* Templates are first-class server-side resources. We materialise a
  template named ``hermes-{task_id}`` once via ``Sandbox.create_template``;
  re-creates of the same template name are tolerated (idempotent on the
  client side: we catch the conflict and re-use the existing one).
* AgentRun caps single-command execution at ~30s server-side. The SDK's
  ``sandbox.process.cmd(command, cwd, timeout=...)`` is invoked once per
  ``_run_bash()`` call. We forward the caller's timeout but clamp to the
  vendor maximum to avoid silent truncation surprises.
"""

from __future__ import annotations

import io
import logging
import os
import shlex
import tarfile
import threading
from pathlib import Path
from typing import Any, Optional

from hermes_constants import get_hermes_home
from tools.environments.base import (
    BaseEnvironment,
    _ThreadedProcessHandle,
    _load_json_store,
    _save_json_store,
)
from tools.environments.file_sync import (
    FileSyncManager,
    iter_sync_files,
    quoted_mkdir_command,
    quoted_rm_command,
    unique_parent_dirs,
)

logger = logging.getLogger(__name__)

# Hard upper bound on a single command's timeout as enforced by the AgentRun
# Code Interpreter sandbox HTTP API (per the published Sandbox docs). Callers
# may request more; the SDK will silently truncate. We clamp explicitly so
# users see a warning rather than a surprise timeout.
_AGENTRUN_CMD_MAX_TIMEOUT = 30

# Default idle ttl for the sandbox itself: 5 minutes of inactivity before the
# control plane reaps it. Long enough to cover a normal multi-tool-call
# conversation; short enough to keep the dormant-instance bill negligible.
_DEFAULT_IDLE_TIMEOUT = 300

# Remote home/working directory inside the Code Interpreter sandbox.
_REMOTE_HOME = "/root"

# Local store mapping ``task_id -> sandbox_id`` so we can resume across
# process restarts (parallel to modal_snapshots.json).
_SANDBOX_STORE = get_hermes_home() / "agentrun_sandboxes.json"


def _load_sandbox_map() -> dict:
    return _load_json_store(_SANDBOX_STORE)


def _save_sandbox_map(data: dict) -> None:
    _save_json_store(_SANDBOX_STORE, data)


def _get_stored_sandbox_id(task_id: str) -> str | None:
    value = _load_sandbox_map().get(task_id)
    return value if isinstance(value, str) and value else None


def _store_sandbox_id(task_id: str, sandbox_id: str) -> None:
    data = _load_sandbox_map()
    data[task_id] = sandbox_id
    _save_sandbox_map(data)


def _delete_stored_sandbox(task_id: str, sandbox_id: str | None = None) -> None:
    data = _load_sandbox_map()
    current = data.get(task_id)
    if current is None:
        return
    if sandbox_id is None or current == sandbox_id:
        data.pop(task_id, None)
        _save_sandbox_map(data)


def _ensure_template(template_name: str) -> None:
    """Create the named template if it does not already exist.

    AgentRun templates are durable server-side resources. The first time
    a backend instance is materialised for a given task_id we create the
    template; subsequent instances re-use it. We swallow
    ``already exists``-shaped errors because the SDK does not expose a
    typed ``AlreadyExists`` exception (it raises ``ServerError`` /
    ``APIError`` with the upstream HTTP message).
    """
    from agentrun.sandbox import Sandbox, TemplateInput, TemplateType

    try:
        Sandbox.get_template(template_name)
        return  # already exists
    except Exception as exc:
        # Treat any "get" failure as "not found" — the create call below
        # will raise distinctly if something else is wrong.
        logger.debug(
            "AgentRun: get_template(%s) failed (treating as not-found): %s",
            template_name, exc,
        )

    try:
        Sandbox.create_template(
            input=TemplateInput(
                template_name=template_name,
                template_type=TemplateType.CODE_INTERPRETER,
            )
        )
        logger.info("AgentRun: created template %s", template_name)
    except Exception as exc:
        # Tolerate race with concurrent creators (e.g. parallel callers
        # with the same task_id). If get_template now succeeds, we are
        # fine. Otherwise re-raise.
        try:
            Sandbox.get_template(template_name)
            logger.info(
                "AgentRun: template %s already existed (raced create)",
                template_name,
            )
        except Exception:
            raise exc


class AgentRunEnvironment(BaseEnvironment):
    """Alibaba Cloud AgentRun Code Interpreter sandbox execution backend.

    Spawn-per-call via ``_ThreadedProcessHandle`` wrapping blocking SDK
    calls. ``cancel_fn`` is wired to ``sandbox.stop()`` so an interrupt
    tears the sandbox down cleanly. Persistence is by reconnecting to a
    stored ``sandbox_id`` keyed on ``task_id``.
    """

    _stdin_mode = "heredoc"
    _snapshot_timeout = 60

    def __init__(
        self,
        cwd: str = _REMOTE_HOME,
        timeout: int = 60,
        task_id: str = "default",
        template_name: Optional[str] = None,
        idle_timeout_seconds: int = _DEFAULT_IDLE_TIMEOUT,
        persistent_filesystem: bool = True,
    ):
        super().__init__(cwd=cwd, timeout=timeout)

        self._persistent = persistent_filesystem
        self._task_id = task_id
        self._template_name = template_name or f"hermes-{task_id}"
        self._idle_timeout = idle_timeout_seconds
        self._sandbox = None
        self._lock = threading.Lock()

        # Late import: SDK is only required when this backend is selected.
        from agentrun.sandbox import Sandbox, TemplateType

        self._TemplateType = TemplateType

        _ensure_template(self._template_name)

        # Persistence path: try to resume an existing sandbox first. We
        # only attempt resume when persistent_filesystem=True; otherwise
        # we always create a fresh sandbox to enforce isolation between
        # ephemeral runs.
        stored_sandbox_id = (
            _get_stored_sandbox_id(self._task_id) if self._persistent else None
        )

        if stored_sandbox_id:
            try:
                self._sandbox = Sandbox.connect(
                    stored_sandbox_id,
                    template_type=TemplateType.CODE_INTERPRETER,
                )
                logger.info(
                    "AgentRun: resumed sandbox %s for task %s",
                    stored_sandbox_id, self._task_id,
                )
            except Exception as exc:
                logger.warning(
                    "AgentRun: failed to resume sandbox %s for task %s "
                    "(%s); creating a fresh one",
                    stored_sandbox_id, self._task_id, exc,
                )
                _delete_stored_sandbox(self._task_id, stored_sandbox_id)
                self._sandbox = None

        if self._sandbox is None:
            self._sandbox = Sandbox.create(
                template_type=TemplateType.CODE_INTERPRETER,
                template_name=self._template_name,
                sandbox_idle_timeout_seconds=self._idle_timeout,
            )
            logger.info(
                "AgentRun: created sandbox %s for task %s "
                "(template=%s, idle_ttl=%ds)",
                self._sandbox.sandbox_id, self._task_id,
                self._template_name, self._idle_timeout,
            )

        # Wait until the sandbox is actually ready to serve requests.
        # ``check_health`` polls the data-plane endpoint inside the
        # sandbox; ``Sandbox.create`` returns as soon as the control
        # plane accepts the request, which is *before* the workload is
        # actually accepting commands.
        self._wait_for_health()

        if self._persistent and self._sandbox.sandbox_id:
            _store_sandbox_id(self._task_id, self._sandbox.sandbox_id)

        self._sync_manager = FileSyncManager(
            get_files_fn=lambda: iter_sync_files(f"{_REMOTE_HOME}/.hermes"),
            upload_fn=self._agentrun_upload,
            delete_fn=self._agentrun_delete,
            bulk_upload_fn=self._agentrun_bulk_upload,
            bulk_download_fn=self._agentrun_bulk_download,
        )
        self._sync_manager.sync(force=True)
        self.init_session()

    # ------------------------------------------------------------------
    # Sandbox lifecycle helpers
    # ------------------------------------------------------------------

    def _wait_for_health(self, retries: int = 60) -> None:
        """Poll ``check_health`` until the sandbox is ready or we give up.

        The SDK's built-in context-manager (``with sandbox as sb:``) does
        the same poll, but we are not using the context manager so we
        replicate the wait explicitly.
        """
        import time

        for attempt in range(1, retries + 1):
            try:
                health = self._sandbox.check_health()
                if isinstance(health, dict) and health.get("status") == "ok":
                    logger.debug(
                        "AgentRun: sandbox %s ready after %ds",
                        self._sandbox.sandbox_id, attempt,
                    )
                    return
            except Exception as exc:
                logger.debug(
                    "AgentRun: health check %d/%d failed: %s",
                    attempt, retries, exc,
                )
            time.sleep(1)

        raise RuntimeError(
            f"AgentRun: sandbox {self._sandbox.sandbox_id} did not become "
            f"healthy within {retries}s"
        )

    # ------------------------------------------------------------------
    # File sync callbacks
    # ------------------------------------------------------------------

    def _agentrun_upload(self, host_path: str, remote_path: str) -> None:
        """Upload a single file via the SDK's multipart endpoint."""
        parent = str(Path(remote_path).parent)
        try:
            self._sandbox.file_system.mkdir(path=parent, parents=True)
        except Exception as exc:
            # mkdir is idempotent in practice; log and proceed so the
            # upload itself surfaces the real failure if any.
            logger.debug(
                "AgentRun: mkdir %s failed (continuing): %s", parent, exc,
            )
        self._sandbox.file_system.upload(
            local_file_path=host_path,
            target_file_path=remote_path,
        )

    def _agentrun_bulk_upload(self, files: list[tuple[str, str]]) -> None:
        """Upload a batch of files.

        The SDK does not expose a multi-file multipart endpoint, so we
        ship each file individually via ``file_system.upload``. We still
        batch-create parent directories with a single shell command to
        keep the round-trip count down. For larger payloads (~hundreds of
        files) callers should prefer this to ``upload_fn`` so the parent
        ``mkdir -p`` only fires once.
        """
        if not files:
            return

        parents = unique_parent_dirs(files)
        if parents:
            try:
                self._sandbox.process.cmd(
                    command=quoted_mkdir_command(parents),
                    cwd="/",
                    timeout=_AGENTRUN_CMD_MAX_TIMEOUT,
                )
            except Exception as exc:
                logger.debug(
                    "AgentRun: bulk mkdir failed (continuing): %s", exc,
                )

        for host_path, remote_path in files:
            self._sandbox.file_system.upload(
                local_file_path=host_path,
                target_file_path=remote_path,
            )

    def _agentrun_bulk_download(self, dest: Path) -> None:
        """Download remote ``.hermes/`` as a tar archive to *dest*.

        We tar inside the sandbox, then pull the tar with
        ``file_system.download``. The remote tar path is suffixed with
        the host PID to avoid collisions when multiple processes share
        the same sandbox by accident.
        """
        rel_base = f"{_REMOTE_HOME}/.hermes".lstrip("/")
        remote_tar = f"/tmp/.hermes_sync.{os.getpid()}.tar"

        self._sandbox.process.cmd(
            command=f"tar cf {shlex.quote(remote_tar)} -C / {shlex.quote(rel_base)}",
            cwd="/",
            timeout=_AGENTRUN_CMD_MAX_TIMEOUT,
        )
        self._sandbox.file_system.download(
            path=remote_tar,
            save_path=str(dest),
        )
        try:
            self._sandbox.process.cmd(
                command=f"rm -f {shlex.quote(remote_tar)}",
                cwd="/",
                timeout=_AGENTRUN_CMD_MAX_TIMEOUT,
            )
        except Exception as exc:
            # Best-effort cleanup; not fatal.
            logger.debug("AgentRun: remote tar cleanup failed: %s", exc)

    def _agentrun_delete(self, remote_paths: list[str]) -> None:
        """Batch-delete remote files via a single shell ``rm -f``."""
        if not remote_paths:
            return
        self._sandbox.process.cmd(
            command=quoted_rm_command(remote_paths),
            cwd="/",
            timeout=_AGENTRUN_CMD_MAX_TIMEOUT,
        )

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------

    def _before_execute(self) -> None:
        """Sync files to sandbox via FileSyncManager (rate-limited internally)."""
        self._sync_manager.sync()

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _run_bash(
        self,
        cmd_string: str,
        *,
        login: bool = False,
        timeout: int = 120,
        stdin_data: str | None = None,
    ):
        """Run a bash command in the AgentRun sandbox.

        Returns a ``_ThreadedProcessHandle`` whose worker performs a
        single blocking ``sandbox.process.cmd`` call. ``cancel_fn`` is
        wired to ``sandbox.stop`` so a ``kill`` from the base class
        tears the instance down (subsequent commands will resume into a
        fresh sandbox under the same task_id).
        """
        sandbox = self._sandbox
        lock = self._lock

        # Clamp timeout to the vendor limit, log once if we had to.
        effective_timeout = timeout
        if timeout > _AGENTRUN_CMD_MAX_TIMEOUT:
            logger.warning(
                "AgentRun: requested cmd timeout %ds exceeds vendor "
                "maximum %ds; clamping",
                timeout, _AGENTRUN_CMD_MAX_TIMEOUT,
            )
            effective_timeout = _AGENTRUN_CMD_MAX_TIMEOUT

        if login:
            shell_cmd = f"bash -l -c {shlex.quote(cmd_string)}"
        else:
            shell_cmd = f"bash -c {shlex.quote(cmd_string)}"

        def cancel():
            with lock:
                try:
                    sandbox.stop()
                except Exception as exc:
                    logger.debug("AgentRun: sandbox.stop on cancel failed: %s", exc)

        def exec_fn() -> tuple[str, int]:
            response = sandbox.process.cmd(
                command=shell_cmd,
                cwd=self.cwd,
                timeout=effective_timeout,
            )
            # SDK returns a raw HTTP body dict. Code Interpreter shapes
            # it as ``{"stdout": ..., "stderr": ..., "exit_code": ...,
            # "result": ...}``; older versions used ``output`` for the
            # combined stream. Accept all variants and fall back to the
            # full payload as a string.
            output, exit_code = _normalise_cmd_response(response)
            return output, exit_code

        return _ThreadedProcessHandle(exec_fn, cancel_fn=cancel)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self):
        """Sync changes back to the host, then stop or delete the sandbox.

        When ``persistent_filesystem=True`` we call ``sandbox.stop()`` so
        the filesystem is preserved server-side and the next constructor
        call with the same ``task_id`` will reconnect. Otherwise we
        ``delete()`` the sandbox outright.
        """
        with self._lock:
            if self._sandbox is None:
                return

            if self._sync_manager:
                logger.info("AgentRun: syncing files from sandbox...")
                try:
                    self._sync_manager.sync_back()
                except Exception as exc:
                    logger.warning("AgentRun: sync_back failed: %s", exc)

            sandbox_id = self._sandbox.sandbox_id
            try:
                if self._persistent:
                    self._sandbox.stop()
                    logger.info(
                        "AgentRun: stopped sandbox %s "
                        "(filesystem preserved for resume)",
                        sandbox_id,
                    )
                else:
                    self._sandbox.delete()
                    _delete_stored_sandbox(self._task_id, sandbox_id)
                    logger.info("AgentRun: deleted sandbox %s", sandbox_id)
            except Exception as exc:
                logger.warning(
                    "AgentRun: cleanup of sandbox %s failed: %s",
                    sandbox_id, exc,
                )
            self._sandbox = None


def _normalise_cmd_response(response: Any) -> tuple[str, int]:
    """Coerce the SDK's cmd-response payload into ``(output, exit_code)``.

    The SDK forwards the data-plane HTTP body unchanged. Across versions
    we have seen these shapes:

    * ``{"stdout": "...", "stderr": "...", "exit_code": 0}``
    * ``{"output": "...", "exit_code": 0}``
    * ``{"data": {"stdout": ..., "exit_code": ...}}``

    We normalise to ``(combined_output, exit_code)``. Unknown shapes are
    repr()d so the caller still sees *something* instead of an empty
    string.
    """
    if response is None:
        return "", 1
    body = response
    if isinstance(body, dict) and "data" in body and isinstance(body["data"], dict):
        body = body["data"]

    if isinstance(body, dict):
        stdout = body.get("stdout") or body.get("output") or ""
        stderr = body.get("stderr") or ""
        exit_code = body.get("exit_code")
        if exit_code is None:
            exit_code = body.get("exitCode")
        if exit_code is None:
            exit_code = body.get("returncode", 0)
        try:
            exit_code = int(exit_code)
        except (TypeError, ValueError):
            exit_code = 0

        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")

        if stderr and stdout:
            return f"{stdout}\n{stderr}", exit_code
        return stdout or stderr or "", exit_code

    return str(body), 0
