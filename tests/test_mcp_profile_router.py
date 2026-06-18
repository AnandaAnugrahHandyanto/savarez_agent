import argparse
import json
from unittest.mock import MagicMock

import pytest

from mcp_profile_router import (
    COST_CLASS_CALLS_HERMES_AGENT_MODEL,
    COST_CLASS_NO_MODEL,
    ProfileRouterError,
    RouterToolMetadata,
    assert_default_tools_are_no_model,
    get_router_tool_metadata,
    parse_profile_ref,
    profile_get,
    profile_health,
    profiles_list,
)


class _FakeTool:
    def __init__(self, fn):
        self.name = fn.__name__
        self.description = fn.__doc__ or ""
        self.fn = fn


class _FakeToolManager:
    def __init__(self):
        self._tools = {}

    def add_tool(self, fn):
        self._tools[fn.__name__] = _FakeTool(fn)


class _FakeFastMCP:
    def __init__(self, *args, **kwargs):
        self._tool_manager = _FakeToolManager()

    def tool(self):
        def decorator(fn):
            self._tool_manager.add_tool(fn)
            return fn

        return decorator


@pytest.fixture
def hermes_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    profiles_root = tmp_path / "profiles"
    profiles_root.mkdir()
    for name in ("main-bot", "maker"):
        profile_dir = profiles_root / name
        (profile_dir / "skills").mkdir(parents=True)
    return tmp_path


def test_parse_profile_ref_requires_fully_qualified_ref():
    assert parse_profile_ref("local:main-bot").value == "local:main-bot"
    assert parse_profile_ref("LOCAL:Main-Bot").value == "local:main-bot"
    assert parse_profile_ref("mac:maker").value == "mac:maker"

    for bad_ref in ("main-bot", "local:", ":main-bot", "remote:main-bot", "local:hermes"):
        with pytest.raises(ProfileRouterError):
            parse_profile_ref(bad_ref)


def test_router_tool_metadata_is_explicitly_no_model_by_default():
    metadata = get_router_tool_metadata()
    assert set(metadata) == {"profiles_list", "profile_get", "profile_health"}
    for tool in metadata.values():
        assert tool["cost_class"] == COST_CLASS_NO_MODEL
        assert tool["llm_calls"] == 0
        assert tool["enabled_by_default"] is True
        assert tool["mutates_state"] is False

    assert_default_tools_are_no_model()


def test_no_model_guard_fails_closed_for_model_spending_default_tool():
    with pytest.raises(ProfileRouterError, match="Default profile-router tools must be no-model"):
        assert_default_tools_are_no_model(
            {
                "unsafe": RouterToolMetadata(
                    name="unsafe",
                    description="would call an agent loop",
                    cost_class=COST_CLASS_CALLS_HERMES_AGENT_MODEL,
                    llm_calls=1,
                )
            }
        )


def test_profiles_list_returns_local_profile_refs_without_secret_paths(hermes_home):
    result = json.loads(profiles_list())
    assert result["ok"] is True
    assert result["cost_class"] == COST_CLASS_NO_MODEL
    assert result["llm_calls"] == 0

    refs = {profile["profile_ref"] for profile in result["profiles"]}
    assert {"local:default", "local:main-bot", "local:maker"} <= refs
    assert all("path" not in profile for profile in result["profiles"])
    assert all("has_env" not in profile for profile in result["profiles"])
    assert all("model" not in profile for profile in result["profiles"])
    assert all("provider" not in profile for profile in result["profiles"])


def test_profile_get_and_health_are_local_only_no_model_wrappers(hermes_home):
    one = json.loads(profile_get("local:main-bot"))
    assert one["ok"] is True
    assert one["profile"]["profile_ref"] == "local:main-bot"
    assert one["llm_calls"] == 0

    health = json.loads(profile_health("local:main-bot"))
    assert health["ok"] is True
    assert health["profile_ref"] == "local:main-bot"
    assert health["health"]["status"] == "ok"
    assert health["llm_calls"] == 0

    unsupported = json.loads(profile_get("mac:maker"))
    assert unsupported["ok"] is False
    assert unsupported["error"]["code"] == "unsupported_host"
    assert unsupported["llm_calls"] == 0

    missing = json.loads(profile_get("local:missing"))
    assert missing["ok"] is False
    assert missing["error"]["code"] == "profile_not_found"
    assert missing["llm_calls"] == 0


def test_profile_router_mcp_factory_exposes_only_no_model_profile_tools(
    hermes_home,
    monkeypatch,
):
    import mcp_serve

    monkeypatch.setattr(mcp_serve, "_MCP_SERVER_AVAILABLE", True)
    monkeypatch.setattr(mcp_serve, "FastMCP", _FakeFastMCP)

    server = mcp_serve.create_profile_router_mcp_server()
    tools = server._tool_manager._tools

    assert set(tools) == {"profiles_list", "profile_get", "profile_health"}
    assert "messages_send" not in tools
    assert "conversations_list" not in tools

    listed = json.loads(tools["profiles_list"].fn())
    assert listed["ok"] is True
    assert listed["cost_class"] == COST_CLASS_NO_MODEL
    assert listed["llm_calls"] == 0


def test_mcp_serve_profile_router_parser_flag_sets_explicit_surface():
    from hermes_cli.subcommands.mcp import build_mcp_parser

    parser = argparse.ArgumentParser(prog="hermes")
    sub = parser.add_subparsers(dest="command")
    build_mcp_parser(sub, cmd_mcp=lambda args: None)

    args = parser.parse_args(["mcp", "serve", "--profile-router"])
    assert args.mcp_action == "serve"
    assert args.profile_router is True


def test_mcp_command_routes_profile_router_serve(monkeypatch):
    mock_run = MagicMock()
    monkeypatch.setattr("mcp_serve.run_profile_router_mcp_server", mock_run)

    from hermes_cli.mcp_config import mcp_command

    args = argparse.Namespace(mcp_action="serve", verbose=True, profile_router=True)
    mcp_command(args)
    mock_run.assert_called_once_with(verbose=True)
