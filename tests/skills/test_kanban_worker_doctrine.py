from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "skills" / "devops" / "kanban-worker" / "SKILL.md"


def test_review_task_doctrine_documents_materialized_review_outcome_schema():
    doctrine = SKILL_PATH.read_text(encoding="utf-8")

    assert '"schema": "cato_review_outcome.v1"' in doctrine
    assert '"outcome": "CHANGES_REQUIRED"' in doctrine
    assert '"owner": "vitruvius"' in doctrine
    assert '"detail": "Use parameterized queries"' in doctrine
    assert '"schema_version": "cato_review_outcome.v1"' not in doctrine
    assert '"status": "CHANGES_REQUIRED"' not in doctrine
