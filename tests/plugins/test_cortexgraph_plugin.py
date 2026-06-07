"""Tests for the bundled CortexGraph connector plugin."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _isolate_env(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("HERMES_CORTEXGRAPH_ALWAYS", raising=False)
    monkeypatch.delenv("HERMES_CORTEXGRAPH_DISABLE", raising=False)
    return hermes_home


def _load_plugin():
    plugin_dir = _repo_root() / "plugins" / "cortexgraph"
    if "hermes_plugins" not in sys.modules:
        ns = types.ModuleType("hermes_plugins")
        ns.__path__ = []
        sys.modules["hermes_plugins"] = ns
    spec = importlib.util.spec_from_file_location(
        "hermes_plugins.cortexgraph",
        plugin_dir / "__init__.py",
        submodule_search_locations=[str(plugin_dir)],
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "hermes_plugins.cortexgraph"
    mod.__path__ = [str(plugin_dir)]
    sys.modules["hermes_plugins.cortexgraph"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_relevant_message_injects_runtime_contract():
    mod = _load_plugin()

    result = mod._on_pre_llm_call(
        user_message="Use CortexGraph to coordinate this with the other agents",
        platform="telegram",
        session_id="s1",
    )

    assert isinstance(result, dict)
    context = result["context"]
    assert "CortexGraph runtime contract" in context
    assert "agent.heartbeat" in context
    assert "thread.checkpoint" in context
    assert "question.answer" in context
    assert "delivery != completion" in context


def test_unrelated_message_does_not_inject_by_default():
    mod = _load_plugin()

    assert mod._on_pre_llm_call(user_message="what is 2+2", platform="telegram") is None


def test_always_mode_injects_for_every_turn(monkeypatch):
    monkeypatch.setenv("HERMES_CORTEXGRAPH_ALWAYS", "1")
    mod = _load_plugin()

    result = mod._on_pre_llm_call(user_message="ordinary work", platform="telegram")

    assert isinstance(result, dict)
    assert "CortexGraph runtime contract" in result["context"]


def test_webhook_event_payload_injects_runtime_contract():
    mod = _load_plugin()
    payload = json.dumps(
        {
            "source": "cortexgraph",
            "event": "question.asked",
            "questionId": "q_123",
            "threadId": "thread_123",
        }
    )

    result = mod._on_pre_llm_call(user_message=payload, platform="webhook")

    assert isinstance(result, dict)
    assert "q_123" in result["context"]
    assert "thread_123" in result["context"]
    assert "Resolve the active question/thread" in result["context"]


def test_config_status_redacts_auth_headers(tmp_path, monkeypatch):
    mod = _load_plugin()
    config = tmp_path / "config.yaml"
    config.write_text(
        "mcp_servers:\n"
        "  cortexgraph:\n"
        "    url: https://www.cortexgraph.ai/api/mcp\n"
        "    headers:\n"
        "      Authorization: token_abc123\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_config_path", lambda: config)

    result = json.loads(mod._tool_config_status({}))

    assert result["configured"] is True
    assert result["mcp_server"]["headers"]["Authorization"] == "[REDACTED]"
    assert "abc123" not in json.dumps(result)

def test_transform_delivery_result_warns_that_delivery_is_not_completion():
    mod = _load_plugin()
    tool_result = json.dumps(
        {
            "deliveries": [
                {"id": "del_1", "status": "delivered", "eventName": "question.asked"}
            ]
        }
    )

    transformed = mod._on_transform_tool_result(
        tool_name="mcp_cortexgraph_webhook_delivery_list",
        args={},
        result=tool_result,
    )

    assert isinstance(transformed, str)
    assert transformed.startswith(tool_result)
    assert "delivery != completion" in transformed
    assert "question.answer" in transformed
    assert "thread.checkpoint" in transformed


def test_loads_via_plugin_manager(_isolate_env):
    import yaml

    config = {"plugins": {"enabled": ["cortexgraph"]}}
    (_isolate_env / "config.yaml").write_text(yaml.safe_dump(config))

    for key in list(sys.modules):
        if key.startswith(("hermes_plugins", "hermes_cli.plugins")):
            del sys.modules[key]

    from hermes_cli.plugins import _ensure_plugins_discovered

    mgr = _ensure_plugins_discovered(force=True)
    loaded = set(mgr._plugins.keys()) if hasattr(mgr, "_plugins") else set()
    assert "cortexgraph" in loaded
    assert "cortexgraph:cortexgraph-connector" in mgr._plugin_skills


def test_plugin_registers_tools_hooks_and_skill(tmp_path):
    mod = _load_plugin()
    calls = {"tools": [], "hooks": [], "skills": []}

    class Ctx:
        manifest = types.SimpleNamespace(name="cortexgraph")

        def register_tool(self, **kwargs):
            calls["tools"].append(kwargs)

        def register_hook(self, hook_name, callback):
            calls["hooks"].append((hook_name, callback))

        def register_skill(self, name, path, description=""):
            calls["skills"].append((name, Path(path), description))

    mod.register(Ctx())

    assert {tool["name"] for tool in calls["tools"]} == {
        "cortexgraph_config_status",
        "cortexgraph_runtime_contract",
    }
    assert {name for name, _ in calls["hooks"]} == {"pre_llm_call", "transform_tool_result"}
    assert calls["skills"][0][0] == "cortexgraph-connector"
    assert calls["skills"][0][1].name == "SKILL.md"
