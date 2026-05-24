from __future__ import annotations

import json

import pytest

from plugins.janitor import cli as janitor_cli
from plugins.janitor import core
from plugins.janitor import register


class DummyCtx:
    def __init__(self) -> None:
        self.tools = []
        self.hooks = []
        self.cli_commands = []
        self.commands = []
        self.skills = []

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


@pytest.fixture()
def temp_home(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "get_hermes_home", lambda: tmp_path)
    return tmp_path


def test_register_exposes_janitor_surfaces(temp_home):
    ctx = DummyCtx()
    register(ctx)

    assert {tool["name"] for tool in ctx.tools} == {
        "janitor_start",
        "janitor_review",
        "janitor_story",
        "janitor_run",
        "janitor_proof",
        "janitor_status",
        "janitor_reset",
        "janitor_daily_prompt",
    }
    assert [name for name, _ in ctx.hooks] == ["pre_llm_call"]
    assert {cmd["name"] for cmd in ctx.cli_commands} == {"janitor"}
    assert {name for name, _, _ in ctx.commands} == {"janitor"}
    assert ctx.skills[0]["path"].name == "SKILL.md"


def test_janitor_mode_creates_cleanup_rubric_and_handoff(temp_home):
    result = core.janitor(
        goal="Stabilize vibe-coded service",
        codebase_path="/repo",
        symptoms="server falls over every 10 minutes, patches cause regressions",
        constraints="keep public API stable",
    )
    assert result["ok"] is True
    assert result["state"]["track"] == "cleanup"
    assert result["state"]["specialization"] == "senior-engineer-janitor"
    assert any("first principles" in item for item in result["rubric"])
    assert sum(item["weight"] for item in result["scorecard"]) == 100

    story = core.add_story(
        title="Rewrite unstable worker",
        acceptance="characterization tests exist, regression logs are clean",
    )
    run = core.prepare_run()
    handoff = run["handoffs"][0]
    assert "Senior-engineer janitor discipline" in handoff
    assert "Senior Engineer Benchmark scorecard" in handoff
    assert "Do not merely paper over failing edges" in handoff
    assert story["story"]["id"] == "S1"


def test_daily_prompt_targets_charged_repos_and_requires_tdd_prs(temp_home):
    prompt = core.daily_prompt(owner="crisweber2600", lookback_hours=24)

    assert prompt["ok"] is True
    text = prompt["prompt"]
    assert "crisweber2600" in text
    assert "past 24 hours" in text
    assert "charges" in text.lower()
    assert "RED" in text and "GREEN" in text and "REFACTOR" in text
    assert "open a pull request" in text.lower()
    assert "what changed" in text.lower()
    assert "why" in text.lower()
    assert prompt["schedule"] == "0 9 * * *"


def test_tool_handler_registry_shape(temp_home):
    ctx = DummyCtx()
    register(ctx)
    handlers = {tool["name"]: tool["handler"] for tool in ctx.tools}

    out = json.loads(handlers["janitor_start"]({"goal": "clean slop", "symptoms": "brittle patches"}))
    assert out["ok"] is True
    assert out["state"]["track"] == "cleanup"
    review = json.loads(handlers["janitor_review"]({"evidence": "deleted dead abstractions", "notes": "rewrote worker"}))
    assert review["ok"] is True
    assert len(review["review"]["scorecard"]) == 6
    daily = json.loads(handlers["janitor_daily_prompt"]({"owner": "crisweber2600", "lookback_hours": 24}))
    assert daily["schedule"] == "0 9 * * *"


def test_cli_and_slash(temp_home):
    args = janitor_cli.build_parser().parse_args(["start", "--path", "/repo", "Clean", "slop"])
    code, text = janitor_cli.dispatch_namespace(args, emit="text")
    assert code == 0
    assert "Clean slop" in text

    slash = janitor_cli.handle_slash('start --path /repo --symptoms "crashes" "Clean up slop"')
    assert '"track": "cleanup"' in slash

    slash = janitor_cli.handle_slash('daily-prompt --owner crisweber2600 --lookback-hours 24')
    assert "RED" in slash and "GREEN" in slash and "REFACTOR" in slash

    slash = janitor_cli.handle_slash('story --acceptance "works" "Implement thing"')
    assert '"ok": true' in slash


def test_plugin_manager_discovers_enabled_janitor(temp_home, monkeypatch):
    from hermes_cli import plugins as plugin_module

    monkeypatch.setattr(plugin_module, "_get_enabled_plugins", lambda: {"janitor"})
    manager = plugin_module.PluginManager()
    manager.discover_and_load(force=True)

    record = [item for item in manager.list_plugins() if item["name"] == "janitor"][0]
    assert record["enabled"] is True
    assert record["tools"] == 8
    assert record["hooks"] == 1
    assert record["commands"] == 1
    assert "janitor:workflow" in manager._plugin_skills

    from tools.registry import registry

    payload = json.loads(registry.dispatch("janitor_daily_prompt", {"owner": "crisweber2600", "lookback_hours": 24}))
    assert payload["ok"] is True
    assert "open a pull request" in payload["prompt"].lower()


def test_pre_llm_injection_only_when_relevant(temp_home):
    ctx = DummyCtx()
    register(ctx)
    hook = dict(ctx.hooks)["pre_llm_call"]
    assert hook(user_message={"content": "hello"}) is None
    assert "Janitor plugin" in hook(user_message={"content": "run janitor"})
    assert "janitor_start" in hook(user_message={"content": "clean up this slop code like a janitor"})
    assert "janitor_review" in hook(user_message={"content": "rewrite from first principles"})
