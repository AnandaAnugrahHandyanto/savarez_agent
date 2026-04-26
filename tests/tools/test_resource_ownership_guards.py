import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gateway.session_context import clear_session_vars, set_session_vars


OWNER_POLICY_PLATFORMS = {
    "resource_ownership": {
        "owner": {"name": "Roger Gimbel", "platforms": {"telegram": ["1425151324"]}},
        "collaborators": [{"name": "Stuart Seligman", "platforms": {"telegram": ["222"]}}],
    }
}

OWNER_POLICY_USER_IDS = {
    "resource_ownership": {
        "owner": {"name": "Roger Gimbel", "user_ids": {"telegram": ["1425151324"]}},
        "collaborators": [],
    }
}


def _set_gateway_session(user_id: str):
    return set_session_vars(
        platform="telegram",
        chat_id=user_id,
        user_id=user_id,
        user_name="Test User",
        session_key=f"agent:main:telegram:dm:{user_id}",
    )


def test_file_and_terminal_owner_guards_accept_user_ids_config():
    tokens = _set_gateway_session("1425151324")
    try:
        with patch("hermes_cli.config.load_config", return_value=OWNER_POLICY_USER_IDS):
            from tools import file_tools, terminal_tool

            assert file_tools._current_requester_is_owner() is True
            assert terminal_tool._current_requester_is_owner() is True
    finally:
        clear_session_vars(tokens)


def test_file_and_terminal_owner_guards_fail_closed_on_config_error():
    tokens = _set_gateway_session("222")
    try:
        with patch("hermes_cli.config.load_config", side_effect=RuntimeError("config unavailable")):
            from tools import file_tools, terminal_tool

            assert file_tools._current_requester_is_owner() is False
            assert terminal_tool._current_requester_is_owner() is False
    finally:
        clear_session_vars(tokens)


def test_execute_code_blocks_non_owner_local_session_before_running_code():
    tokens = _set_gateway_session("222")
    try:
        with patch("hermes_cli.config.load_config", return_value=OWNER_POLICY_PLATFORMS), \
             patch("tools.terminal_tool._get_env_config", return_value={"env_type": "local"}):
            from tools.code_execution_tool import execute_code

            result = json.loads(execute_code("print('should_not_run')"))
            assert result["status"] == "blocked"
            assert "Roger's M5 is not used by fallback" in result["error"]
    finally:
        clear_session_vars(tokens)


def test_terminal_session_env_injection_replaces_stale_snapshot_identity(tmp_path):
    from tools import terminal_tool

    snapshot = tmp_path / "snapshot.sh"
    snapshot.write_text(
        "export HERMES_SESSION_PLATFORM='telegram'\n"
        "export HERMES_SESSION_USER_ID='1425151324'\n"
        "export KEEP_ME='yes'\n"
    )
    env = SimpleNamespace(env={"HERMES_SESSION_USER_ID": "1425151324"}, _snapshot_path=str(snapshot))

    tokens = _set_gateway_session("222")
    try:
        terminal_tool._inject_session_env(env)
    finally:
        clear_session_vars(tokens)

    assert env.env["HERMES_SESSION_USER_ID"] == "222"
    text = snapshot.read_text()
    assert "KEEP_ME" in text
    assert "1425151324" not in text
    assert "HERMES_SESSION_USER_ID=222" in text


def test_gws_bridge_owner_ids_config_accepts_owner():
    import importlib.util

    path = Path("skills/productivity/google-workspace/scripts/gws_bridge.py")
    spec = importlib.util.spec_from_file_location("gws_bridge_under_test", path)
    gws_bridge = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(gws_bridge)

    assert gws_bridge._entry_platform_ids(
        {"user_ids": {"telegram": ["1425151324"]}},
        "telegram",
    ) == {"1425151324"}
