"""Tests for /deep-research turn-local workflow tool exposure."""

from __future__ import annotations

import queue


def test_deep_research_command_is_registered():
    from hermes_cli.commands import resolve_command

    assert resolve_command("deep-research").name == "deep-research"
    assert resolve_command("deep_research").name == "deep-research"
    assert resolve_command("workflows").name == "workflows"


def test_build_deep_research_prompt_contains_question_and_workflow_tool():
    from cli import build_deep_research_prompt

    prompt = build_deep_research_prompt("What changed in Python packaging?")

    assert "workflow_run" in prompt
    assert "What changed in Python packaging?" in prompt
    assert "cross-check" in prompt


def test_cli_deep_research_queues_workflow_tool_for_one_turn(monkeypatch):
    from cli import HermesCLI

    cli = HermesCLI.__new__(HermesCLI)
    cli._pending_input = queue.Queue()

    messages = []
    monkeypatch.setattr("cli._cprint", messages.append)

    cli._handle_deep_research_command("/deep-research find the source")

    prompt, images, metadata = cli._pending_input.get_nowait()
    assert images == []
    assert metadata == {"ephemeral_toolsets": ["workflow"]}
    assert "find the source" in prompt
    assert "workflow_run" in prompt
    assert any("workflow tool enabled for this turn only" in msg for msg in messages)


def test_workflow_toolset_is_not_in_default_schema():
    from model_tools import get_tool_definitions

    def names(tools):
        return {tool.get("function", {}).get("name") for tool in tools}

    assert "workflow_run" not in names(get_tool_definitions(quiet_mode=True))
    assert "workflow_run" in names(
        get_tool_definitions(enabled_toolsets=["workflow"], quiet_mode=True)
    )


def test_apply_ephemeral_toolsets_restores_agent_tools(monkeypatch):
    from types import SimpleNamespace

    from cli import apply_ephemeral_toolsets

    agent = SimpleNamespace(
        tools=[{"type": "function", "function": {"name": "web_search"}}],
        valid_tool_names={"web_search"},
    )

    monkeypatch.setattr(
        "cli.get_tool_definitions",
        lambda enabled_toolsets, quiet_mode: [
            {"type": "function", "function": {"name": "workflow_run"}}
        ],
    )

    with apply_ephemeral_toolsets(agent, ["workflow"]):
        assert [t["function"]["name"] for t in agent.tools] == ["web_search", "workflow_run"]
        assert agent.valid_tool_names == {"web_search", "workflow_run"}

    assert [t["function"]["name"] for t in agent.tools] == ["web_search"]
    assert agent.valid_tool_names == {"web_search"}
