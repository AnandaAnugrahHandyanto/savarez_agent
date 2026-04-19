from people_manager.merge import (
    apply_assessment,
    apply_one_on_one,
    apply_todo,
    apply_update,
)
from people_manager.storage import create_report


def test_apply_update_appends_interaction_log(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    report = create_report("Alice Chen", "Head of IR", "Own investor rhythm")

    updated = apply_update(report, "shipped investor memo", lane_id="telegram:c1")

    entry = updated["interaction_log"][-1]
    assert entry["type"] == "update"
    assert entry["source"]["message_text"] == "Update Alice Chen: shipped investor memo"
    assert updated["updated_at"]


def test_apply_one_on_one_appends_interaction_log(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    report = create_report("Alice Chen", "Head of IR", "Own investor rhythm")

    updated = apply_one_on_one(report, "seems stretched but committed", lane_id="telegram:c1")

    assert updated["interaction_log"][-1]["type"] == "one_on_one"


def test_apply_todo_for_report_goes_to_report_bucket(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    report = create_report("Alice Chen", "Head of IR", "Own investor rhythm")

    updated = apply_todo(report, "send investor segmentation draft", for_manager=False, lane_id="telegram:c1")

    assert "send investor segmentation draft" in updated["open_loops"]["open_todos_for_them"]
    assert updated["interaction_log"][-1]["type"] == "todo_report"


def test_apply_todo_for_manager_goes_to_manager_bucket(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    report = create_report("Alice Chen", "Head of IR", "Own investor rhythm")

    updated = apply_todo(report, "define clearer mandate", for_manager=True, lane_id="telegram:c1")

    assert "define clearer mandate" in updated["open_loops"]["open_todos_for_michael"]
    assert updated["interaction_log"][-1]["type"] == "todo_manager"


def test_apply_assessment_refreshes_performance_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    report = create_report("Alice Chen", "Head of IR", "Own investor rhythm")

    updated = apply_assessment(
        report,
        "solid operator, rising, well matched, confidence medium",
        lane_id="telegram:c1",
    )

    assert updated["performance"]["current_performance_read"] == "solid operator"
    assert updated["performance"]["trajectory"] == "rising"
    assert updated["performance"]["scope_fit"] == "well-matched"
    assert updated["performance"]["confidence_level_in_read"] == "medium"
