from pathlib import Path

import pytest

from symphony.errors import SymphonyError
from symphony.workflow import load_workflow, resolve_workflow_path


def test_load_workflow_without_front_matter(tmp_path):
    workflow_path = tmp_path / "WORKFLOW.md"
    workflow_path.write_text("Do work.\n", encoding="utf-8")

    workflow = load_workflow(workflow_path)

    assert workflow.config == {}
    assert workflow.prompt_template == "Do work."


def test_load_workflow_with_yaml_front_matter(tmp_path):
    workflow_path = tmp_path / "WORKFLOW.md"
    workflow_path.write_text(
        "---\n"
        "name: build\n"
        "poll_interval: 30\n"
        "labels:\n"
        "  - bug\n"
        "---\n"
        "\n"
        "Do work.\n\n",
        encoding="utf-8",
    )

    workflow = load_workflow(workflow_path)

    assert workflow.config == {
        "name": "build",
        "poll_interval": 30,
        "labels": ["bug"],
    }
    assert workflow.prompt_template == "Do work."


def test_load_workflow_rejects_non_map_front_matter(tmp_path):
    workflow_path = tmp_path / "WORKFLOW.md"
    workflow_path.write_text("---\n- not\n- a\n- map\n---\nDo work.\n", encoding="utf-8")

    with pytest.raises(SymphonyError) as exc_info:
        load_workflow(workflow_path)

    assert exc_info.value.code == "workflow_front_matter_not_a_map"


def test_load_workflow_rejects_invalid_yaml_front_matter_with_stable_error(tmp_path):
    workflow_path = tmp_path / "WORKFLOW.md"
    workflow_path.write_text("---\ntracker: [unterminated\n---\nDo work.\n", encoding="utf-8")

    with pytest.raises(SymphonyError) as exc_info:
        load_workflow(workflow_path)

    assert exc_info.value.code == "workflow_front_matter_invalid_yaml"


def test_resolve_workflow_path_explicit_path_wins(tmp_path):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    default_workflow = cwd / "WORKFLOW.md"
    default_workflow.write_text("Default.\n", encoding="utf-8")
    explicit = tmp_path / "custom.md"
    explicit.write_text("Custom.\n", encoding="utf-8")

    assert resolve_workflow_path(str(explicit), cwd=cwd) == explicit


def test_resolve_workflow_path_defaults_to_cwd_workflow(tmp_path):
    workflow_path = tmp_path / "WORKFLOW.md"
    workflow_path.write_text("Do work.\n", encoding="utf-8")

    assert resolve_workflow_path(None, cwd=tmp_path) == workflow_path


def test_resolve_workflow_path_missing_raises_compatible_error(tmp_path):
    missing = tmp_path / "missing.md"

    with pytest.raises(SymphonyError) as exc_info:
        resolve_workflow_path(str(missing), cwd=tmp_path)

    assert exc_info.value.code == "missing_workflow_file"
    assert str(missing) in exc_info.value.message
