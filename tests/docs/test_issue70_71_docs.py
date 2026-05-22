from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def skill_frontmatter(markdown: str) -> dict:
    assert markdown.startswith("---\n")
    end = markdown.index("\n---\n", 4)
    return yaml.safe_load(markdown[4:end])


def test_notion_skill_documents_command_layer_execution_model():
    content = read_text("skills/productivity/notion/SKILL.md")

    assert "## Architecture & Execution Model" in content
    assert "command layer" in content
    assert "curl" in content
    assert "does not rely on a dedicated Python backend tool" in content
    assert "Native tool-level integrations" in content


def test_ai_agent_frameworks_skill_is_bundled_with_selection_guidance():
    content = read_text("skills/mlops/ai-agent-frameworks/SKILL.md")
    metadata = skill_frontmatter(content)

    assert metadata["name"] == "ai-agent-frameworks"
    assert "choosing a Python AI agent framework" in metadata["description"]
    assert "## Quick Decision Matrix" in content
    for framework in ("LangChain", "MetaGPT", "AutoGen", "LlamaIndex", "CrewAI"):
        assert framework in content
    assert "## Decision Flowchart" in content


def test_ai_agent_framework_adventure_log_is_bundled():
    content = read_text("docs/adventures/ai-agent-framework-skill.md")

    assert "# Adventure:" in content
    assert "AI Frameworks" in content
    assert "70+ tool calls" in content
    assert "skills/mlops/ai-agent-frameworks/SKILL.md" in content
