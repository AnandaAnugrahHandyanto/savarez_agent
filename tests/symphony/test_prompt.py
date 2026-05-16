from pathlib import Path

import pytest

from symphony.errors import SymphonyError
from symphony.prompt import build_runner_prompt, render_prompt


def test_render_prompt_substitutes_issue_dict_and_attempt():
    rendered = render_prompt(
        "{{ issue.identifier }} / {{ attempt }}",
        issue={"identifier": "KATO-1"},
        attempt=2,
    )

    assert rendered == "KATO-1 / 2"


def test_render_prompt_unknown_variable_raises_template_render_error():
    with pytest.raises(SymphonyError) as exc_info:
        render_prompt("{{ missing }}", issue={"identifier": "KATO-1"}, attempt=1)

    assert exc_info.value.code == "template_render_error"


def test_build_runner_prompt_prepends_deterministic_runtime_context_then_body(tmp_path):
    workspace_path = tmp_path / "workspace"
    evidence_dir = tmp_path / "evidence"
    body = "Fix {{ issue.identifier }} on attempt {{ attempt }}."

    prompt = build_runner_prompt(
        body,
        workspace_path=workspace_path,
        evidence_dir=evidence_dir,
        issue={"identifier": "KATO-1", "title": "Broken workflow"},
        attempt=3,
    )

    assert prompt.startswith(
        "# Symphony Runtime Context\n"
        f"Workspace: {workspace_path}\n"
        f"Evidence directory: {evidence_dir}\n"
        "Issue identifier: KATO-1\n"
        "Issue title: Broken workflow\n"
        "Attempt: 3\n"
        "\n"
        "--- Workflow Prompt ---\n"
    )
    assert prompt.endswith("Fix KATO-1 on attempt 3.")


def test_build_runner_prompt_omits_unavailable_issue_fields(tmp_path):
    prompt = build_runner_prompt(
        "Do work.",
        workspace_path=Path("/repo"),
        evidence_dir=Path("/repo/.symphony/evidence"),
        issue={},
        attempt=1,
    )

    assert "Issue identifier:" not in prompt
    assert "Issue title:" not in prompt
    assert "Attempt: 1" in prompt
    assert prompt.endswith("Do work.")
