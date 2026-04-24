from __future__ import annotations

import json
from pathlib import Path

from plugins.memory.skill_factory import SkillFactoryMemoryProvider


def _write_config(home: Path, **overrides):
    config = {
        "enabled": True,
        "auto_write": True,
        "min_hits": 2,
        "max_examples": 3,
        "draft_dir": "skill_factory/drafts",
        "state_dir": "skill_factory",
    }
    config.update(overrides)
    (home / "skill_factory.json").write_text(json.dumps(config), encoding="utf-8")


def test_skill_factory_writes_draft_after_repeated_successful_delegations(tmp_path):
    _write_config(tmp_path)

    provider = SkillFactoryMemoryProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli", agent_context="primary")

    task = "Build a repeatable browser extraction workflow for docs pages"
    result = "Implemented successfully and passed verification."

    provider.on_delegation(task, result, child_session_id="child-1")
    provider.on_delegation(task, result, child_session_id="child-2")
    provider.on_session_end([])

    draft_files = list((tmp_path / "skill_factory" / "drafts").rglob("SKILL.md"))
    assert draft_files, "expected a draft skill file to be generated"

    draft = draft_files[0].read_text(encoding="utf-8")
    assert draft.startswith("---\n")
    assert "name:" in draft
    assert "# Build a repeatable browser extraction workflow for docs pages" in draft
    assert "## When to use" in draft
    assert "## Procedure" in draft
    assert "draft-only" in draft

    state = json.loads((tmp_path / "skill_factory" / "state.json").read_text(encoding="utf-8"))
    assert state["records"]
    record = next(iter(state["records"].values()))
    assert record["count"] == 2
    assert record["draft_path"]


def test_skill_factory_ignores_non_primary_context(tmp_path):
    _write_config(tmp_path)

    provider = SkillFactoryMemoryProvider()
    provider.initialize("session-2", hermes_home=str(tmp_path), platform="cli", agent_context="subagent")

    provider.on_delegation(
        "Build a reusable bash cleanup workflow",
        "Implemented successfully and passed verification.",
        child_session_id="child-1",
    )
    provider.on_session_end([])

    assert not list((tmp_path / "skill_factory" / "drafts").rglob("*.skill.md"))
    state = json.loads((tmp_path / "skill_factory" / "state.json").read_text(encoding="utf-8"))
    assert state["records"] == {}


def test_skill_factory_config_schema_exposes_local_settings():
    provider = SkillFactoryMemoryProvider()
    schema = provider.get_config_schema()
    keys = {item["key"] for item in schema}

    assert {"enabled", "auto_write", "min_hits", "max_examples", "draft_dir", "state_dir"} <= keys
