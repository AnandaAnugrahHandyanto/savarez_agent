from people_manager.renderers import (
    render_challenge,
    render_prep,
    render_review,
    render_team_scan,
)
from people_manager.storage import create_report
from people_manager.merge import apply_assessment, apply_todo, apply_update


def _build_report(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    report = create_report("Alice Chen", "Head of IR", "Own investor rhythm")
    report = apply_update(report, "shipped investor memo", lane_id="telegram:c1")
    report = apply_assessment(report, "solid operator, rising, well matched, confidence medium", lane_id="telegram:c1")
    report = apply_todo(report, "send investor segmentation draft", for_manager=False, lane_id="telegram:c1")
    return report


def test_render_prep_contains_required_sections(tmp_path, monkeypatch):
    report = _build_report(tmp_path, monkeypatch)

    text = render_prep(report)

    for section in [
        "Current read",
        "What changed since last touchpoint",
        "Open loops",
        "Questions to ask",
        "Message to land",
        "Management objective",
    ]:
        assert section in text


def test_render_review_contains_required_sections(tmp_path, monkeypatch):
    report = _build_report(tmp_path, monkeypatch)

    text = render_review(report)

    for section in [
        "Role and mandate",
        "Current performance read",
        "Trajectory",
        "Strongest evidence",
        "Unresolved doubts",
        "Strengths",
        "Weaknesses / failure modes",
        "Managerial recommendation",
        "Suggested next management move",
    ]:
        assert section in text


def test_render_team_scan_summarizes_reports(tmp_path, monkeypatch):
    report = _build_report(tmp_path, monkeypatch)

    text = render_team_scan([report])

    for section in [
        "Overall org read",
        "Strongest people / leverage nodes",
        "Fragile nodes",
        "Under-managed people",
        "People with unclear mandate",
        "People needing stretch",
        "People needing support",
        "Decisions Michael may be postponing",
    ]:
        assert section in text
    assert "Alice Chen" in text


def test_render_challenge_mentions_uncertainty_when_evidence_is_thin(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    report = create_report("Alice Chen", "Head of IR", "Own investor rhythm")

    text = render_challenge(report)

    assert "evidence is still thin" in text.lower()


def test_render_team_scan_does_not_flag_under_managed_without_concern_signal(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    report = create_report("Alice Chen", "Head of IR", "Own investor rhythm")
    report = apply_update(report, "shipped investor memo", lane_id="telegram:c1")
    report = apply_assessment(report, "solid operator, rising, well matched, confidence medium", lane_id="telegram:c1")

    text = render_team_scan([report])

    assert "Under-managed people\n- No clear under-managed pattern from stored data." in text
