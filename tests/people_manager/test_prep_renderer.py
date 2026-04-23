from people_manager.storage import create_report



def test_render_prep_note_prefers_explicit_profile_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from people_manager.prep_renderer import render_prep_note

    report = create_report("Thomas Zhu", "COO", "Own operating cadence")
    report["prep_note_preference"] = ["top 5 priorities sync"]
    report["upcoming_one_on_one"] = {"topics": ["decision backlog", "cross-team unblock"]}
    report["relationship_note"] = "keep trust + 战友情 warm"

    text = render_prep_note(report, minutes_until=5)

    assert text.splitlines()[0] == "Thomas Zhu 1:1 in 5m"
    assert "- top 5 priorities sync" in text
    assert "- decision backlog" in text
    assert "- cross-team unblock" in text
    assert "- tone: keep trust + 战友情 warm" in text



def test_render_prep_note_falls_back_when_profile_is_sparse(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from people_manager.prep_renderer import render_prep_note

    report = create_report("Jeffrey Wang", "Finance", "Own finance rhythm")

    text = render_prep_note(report, minutes_until=5)

    assert text.splitlines()[0] == "Jeffrey Wang 1:1 in 5m"
    assert "- weekly/monthly alignment" in text
    assert "- check current priorities" in text
    assert text.count("\n-") <= 6



def test_render_prep_note_supports_adhoc_header_and_filters_metadataish_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from people_manager.prep_renderer import render_prep_note

    report = create_report("Fiona Cao", "Chief of Staff", "Own follow-through")
    report["prep_note_preference"] = {
        "example_shape": ["bad"],
        "status": "draft",
        "style": "telegram",
    }
    report["upcoming_one_on_one"] = {
        "ritual": "weekly operating sync",
        "topics": ["family summer travels", "family SGC application"],
        "relationship_goal": "warm, encouraging, trust-high",
    }
    report["open_loops"] = {
        "current_focus_topics": ["calendar ops"],
        "open_todos_for_michael": ["any calendar / correspondence escalations for me"],
    }
    report["management_strategy"] = {"how_michael_should_manage_them": ["watch detail-sensitive items early"]}

    text = render_prep_note(report, title_mode="adhoc")
    lines = text.splitlines()

    assert lines[0] == "Fiona Cao 1:1"
    assert 5 <= len(lines) <= 8
    assert "weekly operating sync" in text
    assert "family summer travels" in text
    assert "style" not in text
    assert "status" not in text
    assert "example_shape" not in text


def test_render_prep_note_uses_same_bullets_for_scheduled_and_adhoc_modes(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from people_manager.prep_renderer import render_prep_note

    report = create_report("Thomas Zhu", "COO", "Own operating cadence")
    report["upcoming_one_on_one"] = {
        "ritual": "weekly operating sync",
        "topics": ["decision backlog", "cross-team unblock"],
        "relationship_goal": "direct but supportive",
    }
    report["open_loops"] = {"open_todos_for_michael": ["confirm owner for pricing call"]}
    report["management_strategy"] = {"how_michael_should_manage_them": ["push for cleaner decisions"]}

    scheduled = render_prep_note(report, title_mode="scheduled", minutes_until=5)
    adhoc = render_prep_note(report, title_mode="adhoc")

    assert scheduled.splitlines()[0] == "Thomas Zhu 1:1 in 5m"
    assert adhoc.splitlines()[0] == "Thomas Zhu 1:1"
    assert scheduled.splitlines()[1:] == adhoc.splitlines()[1:]
