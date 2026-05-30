"""Tests for the bundled capability-manifest-verifier plugin."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from typing import Any

import pytest
import yaml


PLUGIN_NAME = "capability-manifest-verifier"
SECRET = "test-secret-value"


@pytest.fixture(autouse=True)
def _isolate_env(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("EVAOS_CAPABILITY_MANIFEST_JWT", raising=False)
    monkeypatch.delenv("EVAOS_CAPABILITY_MANIFEST_SECRET", raising=False)
    for name in list(sys.modules):
        if name.startswith("hermes_plugins.capability_manifest_verifier"):
            sys.modules.pop(name, None)
    yield hermes_home


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _jwt(payload: dict[str, Any], secret: str = SECRET) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = ".".join(
        [
            _b64url(json.dumps(header, separators=(",", ":")).encode()),
            _b64url(json.dumps(payload, separators=(",", ":")).encode()),
        ]
    )
    sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(sig)}"


def _payload(**overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    payload: dict[str, Any] = {
        "iss": "evaos-broker",
        "aud": "evaos-runtime",
        "agent_id": "agent-1",
        "exp": now + 3600,
        "tool_grants": {
            "read_file": {"decision": "allow"},
            "terminal": {"decision": "deny", "reason": "shell unavailable"},
            "write_file": {"decision": "requires_approval"},
            "*": {"decision": "deny", "reason": "default deny"},
        },
    }
    payload.update(overrides)
    return payload


def _write_config(
    hermes_home: Path,
    *,
    enabled: bool = True,
    manifest_path: Path | None = None,
    agent_id: str = "agent-1",
) -> None:
    entry: dict[str, Any] = {"agent_id": agent_id}
    if manifest_path is not None:
        entry["manifest_path"] = str(manifest_path)
    cfg: dict[str, Any] = {
        "plugins": {
            "enabled": [PLUGIN_NAME] if enabled else [],
            "entries": {PLUGIN_NAME: entry},
        }
    }
    (hermes_home / "config.yaml").write_text(yaml.safe_dump(cfg))


def _load_manager():
    from hermes_cli import plugins as pmod

    mgr = pmod.PluginManager()
    mgr.discover_and_load()
    return mgr


def test_bundled_plugin_is_discovered_but_not_loaded_without_opt_in(_isolate_env):
    mgr = _load_manager()

    loaded = mgr._plugins[PLUGIN_NAME]
    assert loaded.manifest.source == "bundled"
    assert loaded.enabled is False
    assert loaded.error and "not enabled" in loaded.error


def test_allow_decision_returns_no_block(_isolate_env, monkeypatch):
    _write_config(_isolate_env)
    monkeypatch.setenv("EVAOS_CAPABILITY_MANIFEST_SECRET", SECRET)
    monkeypatch.setenv("EVAOS_CAPABILITY_MANIFEST_JWT", _jwt(_payload()))
    mgr = _load_manager()

    assert mgr._plugins[PLUGIN_NAME].enabled is True
    assert (
        mgr.invoke_hook(
            "pre_tool_call",
            tool_name="read_file",
            args={"path": "README.md"},
            task_id="task-1",
            session_id="session-1",
        )
        == []
    )


def test_deny_decision_blocks_with_redacted_message(_isolate_env, monkeypatch):
    _write_config(_isolate_env)
    monkeypatch.setenv("EVAOS_CAPABILITY_MANIFEST_SECRET", SECRET)
    monkeypatch.setenv("EVAOS_CAPABILITY_MANIFEST_JWT", _jwt(_payload()))
    mgr = _load_manager()

    result = mgr.invoke_hook(
        "pre_tool_call",
        tool_name="terminal",
        args={"command": "echo secret"},
        task_id="task-1",
        session_id="session-1",
    )

    assert result == [
        {
            "action": "block",
            "message": "capability-manifest-verifier blocked tool 'terminal': shell unavailable",
        }
    ]
    assert SECRET not in result[0]["message"]


def test_pre_tool_call_helper_uses_verifier_block(_isolate_env, monkeypatch):
    _write_config(_isolate_env)
    monkeypatch.setenv("EVAOS_CAPABILITY_MANIFEST_SECRET", SECRET)
    monkeypatch.setenv("EVAOS_CAPABILITY_MANIFEST_JWT", _jwt(_payload()))

    from hermes_cli import plugins as pmod

    monkeypatch.setattr(pmod, "_plugin_manager", _load_manager())

    assert pmod.get_pre_tool_call_block_message(
        "terminal",
        {"command": "echo nope"},
        task_id="task-1",
        session_id="session-1",
    ) == "capability-manifest-verifier blocked tool 'terminal': shell unavailable"


def test_requires_approval_fails_closed_until_approval_lane_exists(
    _isolate_env, monkeypatch
):
    _write_config(_isolate_env)
    monkeypatch.setenv("EVAOS_CAPABILITY_MANIFEST_SECRET", SECRET)
    monkeypatch.setenv("EVAOS_CAPABILITY_MANIFEST_JWT", _jwt(_payload()))
    mgr = _load_manager()

    result = mgr.invoke_hook(
        "pre_tool_call",
        tool_name="write_file",
        args={"path": "out.txt"},
        task_id="task-1",
        session_id="session-1",
    )

    assert result == [
        {
            "action": "block",
            "message": (
                "capability-manifest-verifier blocked tool 'write_file': "
                "approval required by capability manifest"
            ),
        }
    ]


def test_missing_manifest_or_secret_fails_closed(_isolate_env):
    _write_config(_isolate_env)
    mgr = _load_manager()

    result = mgr.invoke_hook(
        "pre_tool_call",
        tool_name="read_file",
        args={},
        task_id="task-1",
        session_id="session-1",
    )

    assert result
    assert result[0]["action"] == "block"
    assert "manifest unavailable" in result[0]["message"]


def test_invalid_signature_fails_closed(_isolate_env, monkeypatch):
    _write_config(_isolate_env)
    monkeypatch.setenv("EVAOS_CAPABILITY_MANIFEST_SECRET", SECRET)
    monkeypatch.setenv(
        "EVAOS_CAPABILITY_MANIFEST_JWT", _jwt(_payload(), secret="wrong-secret")
    )
    mgr = _load_manager()

    result = mgr.invoke_hook(
        "pre_tool_call",
        tool_name="read_file",
        args={},
        task_id="task-1",
        session_id="session-1",
    )

    assert result
    assert "manifest invalid" in result[0]["message"]


def test_expired_manifest_fails_closed(_isolate_env, monkeypatch):
    _write_config(_isolate_env)
    monkeypatch.setenv("EVAOS_CAPABILITY_MANIFEST_SECRET", SECRET)
    monkeypatch.setenv(
        "EVAOS_CAPABILITY_MANIFEST_JWT",
        _jwt(_payload(exp=int(time.time()) - 1)),
    )
    mgr = _load_manager()

    result = mgr.invoke_hook(
        "pre_tool_call",
        tool_name="read_file",
        args={},
        task_id="task-1",
        session_id="session-1",
    )

    assert result
    assert "manifest expired" in result[0]["message"]


def test_agent_mismatch_fails_closed(_isolate_env, monkeypatch):
    _write_config(_isolate_env, agent_id="agent-1")
    monkeypatch.setenv("EVAOS_CAPABILITY_MANIFEST_SECRET", SECRET)
    monkeypatch.setenv(
        "EVAOS_CAPABILITY_MANIFEST_JWT", _jwt(_payload(agent_id="other-agent"))
    )
    mgr = _load_manager()

    result = mgr.invoke_hook(
        "pre_tool_call",
        tool_name="read_file",
        args={},
        task_id="task-1",
        session_id="session-1",
    )

    assert result
    assert "manifest target mismatch" in result[0]["message"]


def test_manifest_path_is_supported_when_env_jwt_is_absent(_isolate_env, monkeypatch):
    manifest_path = _isolate_env / "capability.jwt"
    manifest_path.write_text(_jwt(_payload()))
    _write_config(_isolate_env, manifest_path=manifest_path)
    monkeypatch.setenv("EVAOS_CAPABILITY_MANIFEST_SECRET", SECRET)
    mgr = _load_manager()

    assert (
        mgr.invoke_hook(
            "pre_tool_call",
            tool_name="read_file",
            args={},
            task_id="task-1",
            session_id="session-1",
        )
        == []
    )


def test_env_jwt_takes_precedence_over_manifest_path(_isolate_env, monkeypatch):
    manifest_path = _isolate_env / "capability.jwt"
    manifest_path.write_text(_jwt(_payload(exp=int(time.time()) - 1)))
    _write_config(_isolate_env, manifest_path=manifest_path)
    monkeypatch.setenv("EVAOS_CAPABILITY_MANIFEST_SECRET", SECRET)
    monkeypatch.setenv("EVAOS_CAPABILITY_MANIFEST_JWT", _jwt(_payload()))
    mgr = _load_manager()

    assert (
        mgr.invoke_hook(
            "pre_tool_call",
            tool_name="read_file",
            args={},
            task_id="task-1",
            session_id="session-1",
        )
        == []
    )
