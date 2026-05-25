"""Regression tests for out-of-the-box QA + ClawTeam prompting."""

from agent.prompt_builder import build_skills_system_prompt, clear_skills_system_prompt_cache


def test_skills_prompt_calls_out_clawteam_for_issue_pr_shipping_work(monkeypatch, tmp_path):
    """The generic skills prompt should explicitly route issue/PR work through QA/ClawTeam."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    skill_dir = tmp_path / "skills" / "devops" / "clawteam-operations"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: clawteam-operations\n"
        "description: Operate ClawTeam QA gates\n"
        "---\n"
        "# ClawTeam Operations\n",
        encoding="utf-8",
    )
    clear_skills_system_prompt_cache(clear_snapshot=True)

    prompt = build_skills_system_prompt(
        available_tools={"skill_view", "clawteam_inbox_send", "clawteam_inbox_peek"},
        available_toolsets={"skills", "clawteam"},
    )

    assert "GitHub issue, PR, code review, QA verdict, or shipping" in prompt
    assert "clawteam-operations" in prompt
    assert "qa-validation" in prompt


def test_bundled_clawteam_operations_skill_is_available_out_of_box():
    """Hermes should ship the ClawTeam QA workflow skill, not rely on a user's local skill."""
    skill_path = __import__("pathlib").Path("skills/devops/clawteam-operations/SKILL.md")

    content = skill_path.read_text(encoding="utf-8")

    assert "name: clawteam-operations" in content
    assert "qa-validation" in content
    assert "GitHub issue" in content or "issue" in content
