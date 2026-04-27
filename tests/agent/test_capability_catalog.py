import json
import os
from pathlib import Path
from unittest.mock import patch

from tools.registry import ToolRegistry


def _dummy_handler(args, **kwargs):
    return json.dumps({"ok": True})


def _make_schema(name="test_tool"):
    return {
        "name": name,
        "description": f"A {name}",
        "parameters": {"type": "object", "properties": {}},
    }


def _write_skill(skill_root: Path, name: str, description: str, extra_frontmatter: str = "") -> None:
    skill_dir = skill_root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"{extra_frontmatter}"
        "---\n\n"
        f"# {name}\n\n"
        "Skill body.\n",
        encoding="utf-8",
    )


class TestCapabilityCatalog:
    def test_builds_tool_and_skill_records(self, tmp_path):
        reg = ToolRegistry()
        reg.register(
            name="alpha",
            toolset="core",
            schema=_make_schema("alpha"),
            handler=_dummy_handler,
            requires_env=["ALPHA_KEY"],
            runtime_dependencies=["filesystem"],
            execution_tags=["side_effect"],
        )

        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "demo-skill", "Demo skill for catalog")

        with patch("tools.skills_tool.SKILLS_DIR", skills_dir):
            from agent.capability_catalog import build_capability_catalog, get_capability

            catalog = build_capability_catalog(tool_registry=reg, skills_dir=skills_dir)

        assert catalog["counts"]["tool"] == 1
        assert catalog["counts"]["skill"] == 1

        tool_record = get_capability("tool:alpha", catalog=catalog)
        assert tool_record is not None
        assert tool_record["canonical_name"] == "alpha"
        assert tool_record["group"] == "core"
        assert tool_record["required_env"] == ["ALPHA_KEY"]
        assert tool_record["runtime_dependencies"] == ["filesystem"]
        assert tool_record["execution_tags"] == ["side_effect"]
        assert tool_record["readiness"]["status"] == "ready"

        skill_record = get_capability("skill:demo-skill", catalog=catalog)
        assert skill_record is not None
        assert skill_record["canonical_name"] == "demo-skill"
        assert skill_record["group"] == "skill"
        assert skill_record["readiness"]["status"] == "ready"
        assert skill_record["source"]["type"] == "skill_frontmatter"

    def test_summarizes_repo_context_capabilities(self, tmp_path):
        reg = ToolRegistry()
        reg.register(
            name="mcp_claude_context_index_codebase",
            toolset="mcp-claude-context",
            schema=_make_schema("mcp_claude_context_index_codebase"),
            handler=_dummy_handler,
            runtime_dependencies=["filesystem", "mcp_server", "vector_store"],
            execution_tags=["filesystem", "network", "side_effect", "indexing_workflow"],
        )

        skills_dir = tmp_path / "skills"
        with patch("tools.skills_tool.SKILLS_DIR", skills_dir):
            from agent.capability_catalog import build_capability_catalog, summarize_repo_context_capabilities

            catalog = build_capability_catalog(tool_registry=reg, skills_dir=skills_dir)
            summary = summarize_repo_context_capabilities(catalog)

        assert summary == [
            {
                "name": "mcp_claude_context_index_codebase",
                "group": "mcp-claude-context",
                "readiness_status": "ready",
                "identity_scope": "absolute_path",
                "workflow": "index/status/search/clear",
                "result_mode": "partial_or_complete",
            }
        ]

    def test_summarizes_repo_context_capabilities_from_configured_mcp_profiles(self, tmp_path):
        reg = ToolRegistry()
        skills_dir = tmp_path / "skills"
        with patch("tools.skills_tool.SKILLS_DIR", skills_dir), patch(
            "tools.mcp_tool._load_mcp_config",
            return_value={"claude-context": {"command": "npx"}},
        ):
            from agent.capability_catalog import build_capability_catalog, summarize_repo_context_capabilities

            catalog = build_capability_catalog(tool_registry=reg, skills_dir=skills_dir)
            summary = summarize_repo_context_capabilities(catalog)

        assert any(item["group"] == "mcp-claude-context" for item in summary)
        assert any(item["identity_scope"] == "absolute_path" for item in summary)
        assert any(item["workflow"] == "index/status/search/clear" for item in summary)

    def test_tracks_skill_setup_needed_and_health_summary(self, tmp_path):
        reg = ToolRegistry()
        reg.register(
            name="beta",
            toolset="core",
            schema=_make_schema("beta"),
            handler=_dummy_handler,
        )

        skills_dir = tmp_path / "skills"
        _write_skill(
            skills_dir,
            "needs-secret",
            "Skill that requires setup",
            extra_frontmatter="required_environment_variables:\n  - SECRET_TOKEN\n",
        )

        with (
            patch.dict(os.environ, {"SECRET_TOKEN": ""}, clear=False),
        ):
            from agent.capability_catalog import build_capability_catalog, summarize_capability_health

            catalog = build_capability_catalog(tool_registry=reg, skills_dir=skills_dir)
            summary = summarize_capability_health(catalog)

        skill_record = next(r for r in catalog["records"] if r["id"] == "skill:needs-secret")
        assert skill_record["readiness"]["status"] == "setup_needed"
        assert skill_record["required_env"] == ["SECRET_TOKEN"]
        assert skill_record["readiness"]["checks"][0]["name"] == "required_environment_variables"
        assert summary == {
            "total": 2,
            "by_kind": {"skill": 1, "tool": 1},
            "by_status": {"ready": 1, "setup_needed": 1},
        }

    def test_includes_unsupported_skills_and_command_prerequisites(self, tmp_path):
        reg = ToolRegistry()
        reg.register(
            name="gamma",
            toolset="core",
            schema=_make_schema("gamma"),
            handler=_dummy_handler,
        )

        skills_dir = tmp_path / "skills"
        _write_skill(
            skills_dir,
            "linux-only",
            "Linux only skill",
            extra_frontmatter="platforms:\n  - linux\nprerequisites:\n  commands:\n    - jq\n",
        )

        from agent.capability_catalog import build_capability_catalog

        catalog = build_capability_catalog(tool_registry=reg, skills_dir=skills_dir)
        skill_record = next(r for r in catalog["records"] if r["id"] == "skill:linux-only")

        assert skill_record["platform_scope"] == ["linux"]
        assert skill_record["required_commands"] == ["jq"]
        assert skill_record["readiness"]["status"] == "unsupported"
        assert any(check["name"] == "required_commands" for check in skill_record["readiness"]["checks"])
