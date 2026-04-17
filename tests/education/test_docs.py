from pathlib import Path


def test_education_question_bank_doc_exists_with_core_sections():
    doc_path = Path("/home/nyx/hermes-agent_edu/.worktrees/education-question-bank/docs/education-question-bank.md")
    assert doc_path.exists()

    content = doc_path.read_text(encoding="utf-8")

    assert "# Education Question Bank" in content
    assert "## Storage layout" in content
    assert "## Supported inputs" in content
    assert "## Tools" in content
    assert "## Formula preservation" in content
    assert "## Citation integrity" in content
