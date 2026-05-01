from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from subprocess import TimeoutExpired


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "optional-skills"
    / "email"
    / "agentmail"
    / "scripts"
    / "check_agentmail.py"
)


def test_check_agentmail_reports_missing_npx(monkeypatch):
    spec_name = "check_agentmail_missing_npx"
    import importlib.util

    spec = importlib.util.spec_from_file_location(spec_name, SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    monkeypatch.setattr(module.shutil, "which", lambda cmd: None)
    monkeypatch.setattr(module, "_load_config_text", lambda: "")

    rc = module.main()
    assert rc == 1


def test_check_agentmail_reports_missing_config(monkeypatch, capsys):
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_agentmail_missing_config", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    monkeypatch.setattr(module.shutil, "which", lambda cmd: "/usr/bin/npx")
    monkeypatch.setattr(module, "_load_config_text", lambda: "mcp_servers:\n  other: {}\n")

    rc = module.main()
    payload = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert payload["error"] == "agentmail_not_configured"
    assert payload["npx_found"] is True


def test_check_agentmail_prefers_config_with_agentmail_block(monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_agentmail_prefers_agentmail_block", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    monkeypatch.setattr(module.Path, "home", lambda: Path("/Users/tester"))
    monkeypatch.setattr(module, "_candidate_config_paths", lambda: [
        Path("/Users/tester/.hermes/config.yaml"),
        Path("/tmp/custom-hermes/config.yaml"),
    ])
    monkeypatch.setattr(
        module.Path,
        "exists",
        lambda self: str(self) in {"/Users/tester/.hermes/config.yaml", "/tmp/custom-hermes/config.yaml"},
    )

    def fake_read_text(self, encoding="utf-8"):
        mapping = {
            "/Users/tester/.hermes/config.yaml": "mcp_servers:\n  other: {}\n",
            "/tmp/custom-hermes/config.yaml": "mcp_servers:\n  agentmail:\n    command: npx\n    args: [\"-y\", \"agentmail-mcp\"]\n",
        }
        return mapping[str(self)]

    monkeypatch.setattr(module.Path, "read_text", fake_read_text)

    text = module._load_config_text()
    assert "agentmail-mcp" in text


def test_check_agentmail_success(monkeypatch, capsys):
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_agentmail_success", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    monkeypatch.setattr(module.shutil, "which", lambda cmd: "/usr/bin/npx")
    monkeypatch.setattr(
        module,
        "_load_config_text",
        lambda: "mcp_servers:\n  agentmail:\n    command: npx\n    args: [\"-y\", \"agentmail-mcp\"]\n",
    )

    monkeypatch.setattr(module, "_probe_agentmail_server", lambda path: (True, {
        "agentmail_server_probe_exit_code": None,
        "probe_stdout_preview": "",
        "probe_stderr_preview": "",
        "probe_runtime_seconds": 8.0,
    }))

    rc = module.main()
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["agentmail_configured"] is True
    assert payload["agentmail_server_probe_exit_code"] is None


def test_check_agentmail_timeout(monkeypatch, capsys):
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_agentmail_timeout", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    monkeypatch.setattr(module.shutil, "which", lambda cmd: "/usr/bin/npx")
    monkeypatch.setattr(
        module,
        "_load_config_text",
        lambda: "mcp_servers:\n  agentmail:\n    command: npx\n    args: [\"-y\", \"agentmail-mcp\"]\n",
    )

    def raise_timeout(*args, **kwargs):
        raise TimeoutExpired(cmd=args[0], timeout=20, output="", stderr="")

    monkeypatch.setattr(module, "_probe_agentmail_server", raise_timeout)

    rc = module.main()
    payload = json.loads(capsys.readouterr().out)

    assert rc == 4
    assert payload["error"] == "agentmail_probe_timeout"
    assert payload["agentmail_server_probe_exit_code"] is None


def test_probe_agentmail_server_reports_long_lived_process(monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_agentmail_probe", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    class FakeStream:
        def read(self, size=-1):
            return ""

    class FakeProc:
        def __init__(self):
            self.stdout = None
            self.stderr = None
            self.terminated = False
            self.killed = False
            self.wait_calls = []

        def poll(self):
            return None if not self.terminated else 0

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            self.wait_calls.append(timeout)
            return 0

        def kill(self):
            self.killed = True
            self.terminated = True

    fake_proc = FakeProc()
    monkeypatch.setattr(module.subprocess, "Popen", lambda *a, **k: fake_proc)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    timeline = iter([100.0, 108.0])
    monkeypatch.setattr(module.time, "time", lambda: next(timeline))

    ok, payload = module._probe_agentmail_server("/usr/bin/npx")

    assert ok is True
    assert payload["agentmail_server_probe_exit_code"] is None
    assert payload["probe_runtime_seconds"] == 8.0
    assert fake_proc.terminated is True


def test_check_agentmail_cli_script_executes(monkeypatch, tmp_path: Path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        env={**dict(), "PATH": "/usr/bin:/bin:/opt/homebrew/bin"},
        timeout=20,
    )

    assert result.returncode in {1, 2, 3, 4, 0}
    payload = json.loads(result.stdout)
    assert "npx_found" in payload
    assert "agentmail_configured" in payload
