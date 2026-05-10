from __future__ import annotations

import json
from pathlib import Path

import pytest

from artifact_checks import (
    ArtifactCheckItem,
    ArtifactCheckResult,
    ArtifactPathPolicy,
    artifact_path_from_spec,
    check_required_artifacts,
    required_artifact_paths,
    resolve_artifact_path,
)


def test_artifact_path_from_spec_accepts_string_and_dict() -> None:
    assert artifact_path_from_spec("reports/out.md") == "reports/out.md"
    assert artifact_path_from_spec({"path": "artifacts/result.json", "description": "ignored"}) == "artifacts/result.json"


@pytest.mark.parametrize(
    "spec",
    [
        {},
        {"path": ""},
        {"path": 123},
        123,
        None,
    ],
)
def test_artifact_path_from_spec_ignores_malformed_specs(spec: object) -> None:
    assert artifact_path_from_spec(spec) is None  # type: ignore[arg-type]


def test_required_artifact_paths_handles_empty_and_mixed_specs() -> None:
    assert required_artifact_paths({}) == []
    assert required_artifact_paths({"required_artifacts": []}) == []
    assert required_artifact_paths(
        {
            "required_artifacts": [
                "one.md",
                {"path": "two.json", "description": "ignored"},
                {"description": "missing path"},
                17,
            ],
        }
    ) == ["one.md", "two.json"]


def test_required_artifact_paths_supports_custom_field() -> None:
    assert required_artifact_paths({"outputs": ["summary.md"]}, field="outputs") == ["summary.md"]


def test_resolve_artifact_path_handles_base_workspace_and_absolute_paths(tmp_path: Path) -> None:
    base_dir = tmp_path / "tasks" / "task-1"
    workspace_root = tmp_path / "workspace"
    base_dir.mkdir(parents=True)
    workspace_root.mkdir()
    policy = ArtifactPathPolicy(
        base_dir=base_dir,
        workspace_root=workspace_root,
        workspace_relative_prefixes=("tasks/",),
    )

    assert resolve_artifact_path("local.md", policy) == base_dir / "local.md"
    assert resolve_artifact_path("tasks/task-1/artifacts/out.md", policy) == workspace_root / "tasks/task-1/artifacts/out.md"
    absolute = tmp_path / "absolute.md"
    assert resolve_artifact_path(str(absolute), policy) == absolute


def test_resolve_artifact_path_rejects_absolute_paths_when_disallowed(tmp_path: Path) -> None:
    policy = ArtifactPathPolicy(base_dir=tmp_path, allow_absolute=False)

    with pytest.raises(ValueError, match="Absolute artifact paths are not allowed"):
        resolve_artifact_path(str(tmp_path / "absolute.md"), policy)


def test_artifact_path_policy_requires_path_base_dir() -> None:
    with pytest.raises(TypeError):
        ArtifactPathPolicy(base_dir="not-a-path")  # type: ignore[arg-type]


@pytest.mark.parametrize("missing", ["missing-a.md", "missing-b.json"])
def test_check_required_artifacts_reports_all_missing(tmp_path: Path, missing: str) -> None:
    result = check_required_artifacts(
        {"required_artifacts": [missing]},
        policy=ArtifactPathPolicy(base_dir=tmp_path),
    )

    assert result.ok is False
    assert result.expected_count == 1
    assert result.present == []
    assert result.missing == [missing]
    assert result.checked[0].exists is False
    assert result.checked[0].is_file is None


def test_check_required_artifacts_reports_all_present(tmp_path: Path) -> None:
    (tmp_path / "report.md").write_text("done", encoding="utf-8")
    (tmp_path / "result.json").write_text("{}", encoding="utf-8")

    result = check_required_artifacts(
        {"required_artifacts": ["report.md", {"path": "result.json"}]},
        policy=ArtifactPathPolicy(base_dir=tmp_path),
    )

    assert result.ok is True
    assert result.expected_count == 2
    assert result.present == ["report.md", "result.json"]
    assert result.missing == []
    assert [item.exists for item in result.checked] == [True, True]
    assert [item.is_file for item in result.checked] == [True, True]


def test_check_required_artifacts_reports_mixed_present_missing_and_extra_paths(tmp_path: Path) -> None:
    (tmp_path / "present.md").write_text("done", encoding="utf-8")
    (tmp_path / "extra.md").write_text("extra", encoding="utf-8")

    result = check_required_artifacts(
        {"required_artifacts": ["present.md", "missing.md"]},
        policy=ArtifactPathPolicy(base_dir=tmp_path),
        extra_paths=["extra.md", {"path": "extra-missing.md"}],
    )

    assert result.ok is False
    assert result.expected_count == 4
    assert result.present == ["present.md", "extra.md"]
    assert result.missing == ["missing.md", "extra-missing.md"]


def test_check_required_artifacts_treats_directories_as_missing_by_default(tmp_path: Path) -> None:
    (tmp_path / "artifact-dir").mkdir()

    result = check_required_artifacts(
        {"required_artifacts": ["artifact-dir"]},
        policy=ArtifactPathPolicy(base_dir=tmp_path),
    )

    assert result.ok is False
    assert result.present == []
    assert result.missing == ["artifact-dir"]
    assert result.checked[0].exists is True
    assert result.checked[0].is_file is False


def test_check_required_artifacts_can_accept_directories_when_configured(tmp_path: Path) -> None:
    (tmp_path / "artifact-dir").mkdir()

    result = check_required_artifacts(
        {"required_artifacts": ["artifact-dir"]},
        policy=ArtifactPathPolicy(base_dir=tmp_path, require_file=False),
    )

    assert result.ok is True
    assert result.present == ["artifact-dir"]
    assert result.missing == []
    assert result.checked[0].exists is True
    assert result.checked[0].is_file is False


def test_check_result_to_dict_is_json_serializable() -> None:
    result = ArtifactCheckResult(
        ok=False,
        expected_count=1,
        present=[],
        missing=["missing.md"],
        checked=[ArtifactCheckItem(path="missing.md", exists=False, is_file=None, resolved="/tmp/missing.md")],
    )

    payload = result.to_dict()

    assert payload == {
        "ok": False,
        "expected_count": 1,
        "present": [],
        "missing": ["missing.md"],
        "checked": [
            {
                "path": "missing.md",
                "exists": False,
                "is_file": None,
                "resolved": "/tmp/missing.md",
            }
        ],
    }
    json.dumps(payload)
