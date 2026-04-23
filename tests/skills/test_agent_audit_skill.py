from pathlib import Path
import json

from agent.skill_utils import parse_frontmatter


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "software-development" / "agent-audit"


def test_agent_audit_skill_frontmatter_and_references_are_parseable():
    skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(skill_text)

    assert frontmatter["name"] == "agent-audit"
    assert "Evidence-first audit workflow" in frontmatter["description"]
    assert "agent_check_scope.json" in body
    assert "evidence_pack.json" in body
    assert "failure_map.json" in body
    assert "agent_check_report.json" in body
    assert "references/report-schema.json" in body


def test_agent_audit_report_schema_and_example_include_contamination_paths():
    schema = json.loads((SKILL_DIR / "references" / "report-schema.json").read_text())
    example = json.loads((SKILL_DIR / "references" / "example-report.json").read_text())

    assert schema["schema_version"] == "agent-audit.report.v1"
    assert example["schema_version"] == "agent-audit.report.v1"
    assert "contamination_paths" in schema
    assert "contamination_paths" in example
    assert example["ordered_fix_plan"][0]["order"] == 1
