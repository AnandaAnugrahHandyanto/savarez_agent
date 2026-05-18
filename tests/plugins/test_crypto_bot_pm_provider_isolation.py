from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[2] / "plugins/crypto-bot-pm"
PROJECT_STATUS_MODULE = "scripts.hermes_pm.project_status"


def _fresh_project_status(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_ROOT))
    for name in list(sys.modules):
        if name == "scripts" or name.startswith("scripts.hermes_pm"):
            sys.modules.pop(name, None)
    return importlib.import_module(PROJECT_STATUS_MODULE)


def test_missing_optional_ci_provider_does_not_disable_gitea_snapshot(monkeypatch):
    project_status = _fresh_project_status(monkeypatch)

    assert project_status.capture_gitea_snapshot is not None
    assert project_status.build_work_state is not None
    assert project_status.build_gitea_ci_evidence_summary is None

    snapshot = project_status._optional_gitea_snapshot(
        snapshot_path=None,
        live_gitea_read=True,
    )

    assert snapshot is not None
    assert not any(
        blocker.get("endpoint") == "<local-import>"
        for blocker in snapshot.get("blockers", [])
    )


def test_missing_optional_ci_provider_is_scoped_to_ci_readiness(monkeypatch, tmp_path):
    project_status = _fresh_project_status(monkeypatch)
    snapshot = {
        "schema_version": "hermes.pm.gitea_readonly_snapshot.v1",
        "gitea_base_url": "http://gitea.local",
        "owner": "preston",
        "repo": "crypto_bot",
        "auth_used": False,
        "http_methods_used": ["GET"],
        "issues": {"open_count": 1, "recently_closed_count": 0, "items": []},
        "pull_requests": {
            "open_count": 0,
            "recently_closed_or_merged_count": 0,
            "items": [],
        },
        "checks": {"statuses": [], "combined_status": {}},
        "workflows": {"recent_run_count": 0},
        "blockers": [],
        "warnings": [],
    }

    report = project_status.build_project_status(
        project_id="crypto_bot",
        repo_root=tmp_path,
        gitea_snapshot=snapshot,
    )

    assert report["ci_locality_readiness"] == {
        "available": False,
        "reason": "existing Hermes CI evidence module is unavailable",
    }
    assert report["gitea_pm_snapshot_summary"]["base_url"] == "http://gitea.local"
    assert report["gitea_pm_snapshot_summary"]["open_issue_count"] == 1
    assert report["pm_work_state_summary"]["recommendation_class"] in {
        "approval_required",
        "stale_context",
        "control_plane_regression",
    }
    assert report["recommended_next_pm_action"] != (
        "Review the Gitea snapshot blockers and regenerate the Kanban packet."
    )


def test_pm_status_kanban_semantic_parity_detector_classifies_disagreement(monkeypatch):
    project_status = _fresh_project_status(monkeypatch)
    pm_status = {
        "gitea_pm_snapshot_summary": {
            "open_issue_count": 0,
            "blockers": [
                {"endpoint": "<local-import>", "error": "Gitea snapshot module is unavailable."}
            ],
        },
        "issue_lifecycle_summary": {"exists": False},
    }
    kanban_packet = {
        "daily_summary": {"open_issue_count": 1, "seed_pm_issue_exists": True},
    }

    result = project_status.classify_pm_kanban_semantic_parity(
        pm_status=pm_status,
        kanban_packet=kanban_packet,
    )

    assert result["consistent"] is False
    assert result["recommendation_class"] == "control_plane_regression"
    assert "local-import" in json.dumps(result["blockers"])


def test_pm_status_kanban_semantic_parity_handles_unparseable_counts(monkeypatch):
    project_status = _fresh_project_status(monkeypatch)

    result = project_status.classify_pm_kanban_semantic_parity(
        pm_status={"gitea_pm_snapshot_summary": {"open_issue_count": "unknown"}},
        kanban_packet={"daily_summary": {"open_issue_count": 1}},
    )

    assert result["consistent"] is False
    assert result["recommendation_class"] == "control_plane_regression"
    assert result["blockers"][0]["code"] == "open_issue_count_unparseable"


def test_provider_import_attrs_isolates_plain_import_error(monkeypatch):
    project_status = _fresh_project_status(monkeypatch)

    def fail_import(name: str):
        raise ImportError(f"dependency failed for {name}")

    monkeypatch.setattr(project_status.importlib, "import_module", fail_import)

    attrs, status = project_status._import_provider_attrs(
        "broken_provider",
        ("scripts.hermes_pm.broken_provider",),
        ("capture",),
    )

    assert attrs == {"capture": None}
    assert status.provider == "broken_provider"
    assert status.available is False
    assert status.error_type == "ImportUnavailable"
    assert "ImportError" in status.error
