from __future__ import annotations

from pathlib import Path

import pytest

from plugins.bmad_symphony import cli as workflow_cli
from plugins.bmad_symphony import core
from plugins.bmad_symphony import register


class DummyCtx:
    def __init__(self) -> None:
        self.tools = []
        self.hooks = []
        self.cli_commands = []
        self.commands = []
        self.skills = []
        self.dispatched = []

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)

    def register_hook(self, name, handler):
        self.hooks.append((name, handler))

    def register_cli_command(self, **kwargs):
        self.cli_commands.append(kwargs)

    def register_command(self, name, handler, **kwargs):
        self.commands.append((name, handler, kwargs))

    def register_skill(self, **kwargs):
        self.skills.append(kwargs)

    def dispatch_tool(self, name, payload):
        self.dispatched.append((name, payload))
        return {"tool": name, "payload": payload}


@pytest.fixture()
def temp_home(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "get_hermes_home", lambda: tmp_path)
    return tmp_path


def test_register_exposes_deep_surfaces(temp_home):
    ctx = DummyCtx()
    register(ctx)

    tool_names = {tool["name"] for tool in ctx.tools}
    assert tool_names == {
        "bmad_intake",
        "bmad_story",
        "symphony_run",
        "bmad_proof",
        "bmad_status",
        "bmad_reset",
    }

    assert [name for name, _ in ctx.hooks] == ["pre_llm_call", "on_session_end"]
    assert {cmd["name"] for cmd in ctx.cli_commands} == {"bmad-symphony"}
    assert {name for name, _, _ in ctx.commands} == {"bmad-symphony", "bmad"}
    assert len(ctx.skills) == 1
    assert ctx.skills[0]["path"].name == "SKILL.md"


def test_plugin_manager_discovers_enabled_bmad_symphony(temp_home, monkeypatch):
    from hermes_cli import plugins as plugin_module

    monkeypatch.setattr(plugin_module, "_get_enabled_plugins", lambda: {"bmad-symphony"})
    manager = plugin_module.PluginManager()
    manager.discover_and_load(force=True)

    record = [item for item in manager.list_plugins() if item["name"] == "bmad-symphony"][0]
    assert record["enabled"] is True
    assert record["tools"] == 6
    assert record["hooks"] == 2
    assert record["commands"] == 2
    assert "bmad-symphony:workflow" in manager._plugin_skills

    from tools.registry import registry
    payload = registry.dispatch("bmad_intake", {"goal": "ship bmad plugin", "context": "test"})
    assert "ship bmad plugin" in payload
    assert "state" in payload


def test_plan_story_run_and_proof_flow_persists_state(temp_home):
    intake = core.build_intake(goal="ship a dashboard export", context="keep it small", constraints=["no new deps"])
    assert "dashboard export" in intake["goal"]
    state = core.update_state(mode="plan", goal=intake["goal"], intake=intake, active=True)
    assert core.state_file().exists()
    assert core.load_state()["current_goal"] == "ship a dashboard export"

    story = core.build_story(goal=intake["goal"], acceptance=["Export is generated", "Tests pass"])
    assert "acceptance_criteria" in story

    run = core.build_run_plan(goal=intake["goal"], parallelism=2)
    assert len(run["tasks"]) == 2
    assert run["recommended_delegate_payload"]["toolsets"]

    proof = core.evaluate_proof(
        goal=intake["goal"],
        evidence=["tests passed", "diff reviewed"],
        tests=["pytest"],
        files_changed=["src/export.py"],
    )
    assert proof["status"] == "pass"

    state = core.update_state(mode="proof", goal=intake["goal"], proof=proof, active=False)
    snapshot = core.summarize_state(state)
    assert snapshot["proof"]["status"] == "pass"


def test_pre_llm_injection_only_when_relevant(temp_home):
    register_ctx = DummyCtx()
    register(register_ctx)
    hook = dict(register_ctx.hooks)["pre_llm_call"]
    assert hook(user_message={"content": "hello"}) is None
    injected = hook(user_message={"content": "We should use BMad for this"})
    assert injected and "BMad/Symphony mode" in injected


def test_cli_and_slash_handlers_can_dispatch(temp_home):
    ctx = DummyCtx()
    register(ctx)

    cli_handler = ctx.cli_commands[0]["handler_fn"]
    args = workflow_cli.build_parser().parse_args(["plan", "--goal", "fix the export pipeline"])
    assert cli_handler(args) == 0

    slash_handler = {name: handler for name, handler, _ in ctx.commands}["bmad"]
    text = slash_handler('plan --goal "fix the export pipeline"')
    assert "BMad intake" in text
    assert "Current goal" in text
    assert not ctx.dispatched


def test_auto_dispatch_uses_delegate_tool(temp_home):
    ctx = DummyCtx()
    register(ctx)
    tool_handler = {tool["name"]: tool["handler"] for tool in ctx.tools}["symphony_run"]
    out = tool_handler({"goal": "fix the export pipeline", "auto_dispatch": True, "parallelism": 2})
    assert "delegate_result" in out
    assert ctx.dispatched[0][0] == "delegate_task"
