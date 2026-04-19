from people_manager.service import handle_people_message


def test_handle_people_message_creates_and_rejects_duplicate_report(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    created = handle_people_message(
        "New report: Alice Chen - Head of IR - own investor cadence",
        lane_id="telegram:c1",
        workspace="people",
    )
    duplicate = handle_people_message(
        "New report: Alice Chen - Head of IR - own investor cadence",
        lane_id="telegram:c1",
        workspace="people",
    )

    assert "Created report for Alice Chen" in created
    assert "Report already exists" in duplicate


def test_handle_people_message_returns_safe_missing_report_error(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    result = handle_people_message(
        "Prep Alice Chen",
        lane_id="telegram:c1",
        workspace="people",
    )

    assert "No direct report found" in result


def test_handle_people_message_team_question_uses_team_scan(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    handle_people_message(
        "New report: Alice Chen - Head of IR - own investor cadence",
        lane_id="telegram:c1",
        workspace="people",
    )
    handle_people_message(
        "Assessment Alice Chen: solid operator, rising, well matched, confidence medium",
        lane_id="telegram:c1",
        workspace="people",
    )

    result = handle_people_message(
        "Am I under-managing anyone?",
        lane_id="telegram:c1",
        workspace="people",
    )

    assert "Team scan" in result
    assert "Challenge lens" in result
    assert "Alice Chen" in result


def test_handle_people_message_returns_none_outside_people_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    result = handle_people_message(
        "Update Alice Chen: shipped memo",
        lane_id="telegram:c1",
        workspace="speech",
    )

    assert result is None
