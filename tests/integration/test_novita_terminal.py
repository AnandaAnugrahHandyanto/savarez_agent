"""Integration tests for the Novita terminal backend.

Requires NOVITA_API_KEY to be set. Run with:
    TERMINAL_ENV=novita pytest tests/integration/test_novita_terminal.py -v
"""

import json
import os
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

# Skip entire module if no API key
_NOVITA_API_KEY = os.getenv("NOVITA_API_KEY")
if not _NOVITA_API_KEY:
    pytest.skip("NOVITA_API_KEY not set", allow_module_level=True)

from tools.terminal_tool import (
    cleanup_vm,
    clear_task_env_overrides,
    register_task_env_overrides,
    terminal_tool,
)


@pytest.fixture(autouse=True)
def _force_novita(monkeypatch):
    monkeypatch.setenv("NOVITA_API_KEY", _NOVITA_API_KEY)
    monkeypatch.setenv("TERMINAL_ENV", "novita")
    monkeypatch.setenv("TERMINAL_CONTAINER_PERSISTENT", "false")


@pytest.fixture()
def task_id(request):
    """Provide a unique task_id and clean up the sandbox after the test."""
    tid = f"novita_test_{request.node.name}_{uuid.uuid4().hex[:8]}"
    register_task_env_overrides(tid, {})
    yield tid
    os.environ["NOVITA_API_KEY"] = _NOVITA_API_KEY
    os.environ["TERMINAL_CONTAINER_PERSISTENT"] = "false"
    cleanup_vm(tid)
    clear_task_env_overrides(tid)


def _run(command, task_id, **kwargs):
    result = terminal_tool(command, task_id=task_id, **kwargs)
    return json.loads(result)


class TestNovitaBasic:
    def test_echo(self, task_id):
        r = _run("echo 'Hello from Novita!'", task_id)
        assert r["exit_code"] == 0
        assert "Hello from Novita!" in r["output"]

    def test_python_version(self, task_id):
        r = _run("python3 --version", task_id)
        assert r["exit_code"] == 0
        assert "Python" in r["output"]

    def test_nonzero_exit(self, task_id):
        r = _run("exit 42", task_id)
        assert r["exit_code"] == 42

    def test_os_info(self, task_id):
        r = _run("uname -a", task_id)
        assert r["exit_code"] == 0
        assert "Linux" in r["output"]

    def test_default_cwd_is_writable_home(self, task_id):
        """Default cwd should resolve to a writable home, not inaccessible /root."""
        marker = f"cwd_probe_{uuid.uuid4().hex[:8]}"
        r = _run(f"pwd && touch {marker} && test -f {marker}", task_id)
        assert r["exit_code"] == 0
        assert "/home/" in r["output"]


class TestNovitaFilesystem:
    def test_write_and_read_file(self, task_id):
        _run("echo 'test content' > /tmp/novita_test.txt", task_id)
        r = _run("cat /tmp/novita_test.txt", task_id)
        assert r["exit_code"] == 0
        assert "test content" in r["output"]

    def test_persistence_within_session(self, task_id):
        _run("pip install cowsay 2>/dev/null", task_id, timeout=120)
        r = _run('python3 -c "import cowsay; print(cowsay.__file__)"', task_id)
        assert r["exit_code"] == 0
        assert "cowsay" in r["output"]


class TestNovitaPersistence:
    def test_filesystem_survives_pause_and_resume(self):
        """Write a file, pause the sandbox, resume it, assert the file persists."""
        task = f"novita_test_persist_{uuid.uuid4().hex[:8]}"
        register_task_env_overrides(task, {})
        try:
            os.environ["TERMINAL_CONTAINER_PERSISTENT"] = "true"

            # Write a marker file and pause the sandbox
            _run("echo 'survive' > /tmp/persist_test.txt", task)
            cleanup_vm(task)  # pauses (not kills) because persistent=true

            # Resume with the same task_id — file should still exist
            r = _run("cat /tmp/persist_test.txt", task)
            assert r["exit_code"] == 0
            assert "survive" in r["output"]
        finally:
            os.environ["NOVITA_API_KEY"] = _NOVITA_API_KEY
            os.environ["TERMINAL_CONTAINER_PERSISTENT"] = "false"
            cleanup_vm(task)
            clear_task_env_overrides(task)

    def test_sync_back_downloads_remote_hermes_changes(self, monkeypatch):
        """Modify a synced .hermes file remotely, cleanup, assert host file updates."""
        from hermes_constants import get_hermes_home

        task = f"novita_test_sync_back_{uuid.uuid4().hex[:8]}"
        marker = f"sync-back-{uuid.uuid4().hex}"
        skill_file = (
            get_hermes_home()
            / "skills"
            / f"novita-sync-back-{uuid.uuid4().hex[:8]}"
            / "SKILL.md"
        )
        skill_file.parent.mkdir(parents=True)
        skill_file.write_text("initial\n")

        register_task_env_overrides(task, {})
        try:
            monkeypatch.setenv("TERMINAL_CONTAINER_PERSISTENT", "false")

            remote_path = Path("/home/user/.hermes/skills") / skill_file.parent.name / "SKILL.md"
            r = _run(
                f"python3 - <<'PY'\n"
                f"from pathlib import Path\n"
                f"path = Path({str(remote_path)!r})\n"
                f"path.write_text({marker!r} + '\\n')\n"
                f"print(path.read_text().strip())\n"
                f"PY",
                task,
            )
            assert r["exit_code"] == 0
            assert marker in r["output"]

            cleanup_vm(task)

            assert skill_file.read_text().strip() == marker
        finally:
            os.environ["NOVITA_API_KEY"] = _NOVITA_API_KEY
            os.environ["TERMINAL_CONTAINER_PERSISTENT"] = "false"
            cleanup_vm(task)
            clear_task_env_overrides(task)


class TestNovitaLifecycle:
    def test_timeout_clears_cached_sandbox_and_next_command_recreates(self):
        """A timed-out command kills Novita; the next command should recreate cleanly."""
        task = f"novita_test_timeout_{uuid.uuid4().hex[:8]}"
        register_task_env_overrides(task, {})
        try:
            r = _run("sleep 10", task, timeout=1)
            assert r["exit_code"] in (124, 130)

            r = _run("echo after-timeout", task)
            assert r["exit_code"] == 0
            assert "after-timeout" in r["output"]
        finally:
            os.environ["NOVITA_API_KEY"] = _NOVITA_API_KEY
            os.environ["TERMINAL_CONTAINER_PERSISTENT"] = "false"
            cleanup_vm(task)
            clear_task_env_overrides(task)


class TestNovitaIsolation:
    def test_different_tasks_isolated(self):
        suffix = uuid.uuid4().hex[:8]
        task_a = f"novita_test_iso_a_{suffix}"
        task_b = f"novita_test_iso_b_{suffix}"
        marker = f"/tmp/isolated_{suffix}.txt"
        register_task_env_overrides(task_a, {})
        register_task_env_overrides(task_b, {})
        try:
            _run(f"echo 'secret' > {marker}", task_a)
            r = _run(f"cat {marker} 2>&1 || echo NOT_FOUND", task_b)
            assert "secret" not in r["output"] or "NOT_FOUND" in r["output"]
        finally:
            os.environ["NOVITA_API_KEY"] = _NOVITA_API_KEY
            os.environ["TERMINAL_CONTAINER_PERSISTENT"] = "false"
            cleanup_vm(task_a)
            cleanup_vm(task_b)
            clear_task_env_overrides(task_a)
            clear_task_env_overrides(task_b)
