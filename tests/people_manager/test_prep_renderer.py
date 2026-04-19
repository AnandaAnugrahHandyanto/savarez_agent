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
