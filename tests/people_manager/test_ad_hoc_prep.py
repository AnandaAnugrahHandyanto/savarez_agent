from people_manager.storage import create_report, save_report



def _install_reports(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    from people_manager.schedule_store import save_schedule_registry

    fiona = create_report("Fiona Cao", "Chief of Staff", "Own follow-through")
    fiona["upcoming_one_on_one"] = {
        "topics": ["family summer travels", "family SGC application"],
        "ritual": "weekly operating sync",
        "relationship_goal": "warm, encouraging, trust-high",
    }
    fiona["open_loops"] = {
        "open_todos_for_michael": ["any calendar / correspondence escalations for me"],
        "current_focus_topics": ["calendar ops"],
    }
    fiona["management_strategy"] = {"how_michael_should_manage_them": ["watch detail-sensitive items early"]}
    save_report(fiona)

    thomas = create_report("Tom Zhu", "COO", "Own operating cadence")
    thomas["upcoming_one_on_one"] = {"topics": ["decision backlog"]}
    save_report(thomas)

    tom = create_report("Tom Lee", "Ops", "Own special projects")
    tom["upcoming_one_on_one"] = {"topics": ["vendor cleanup"]}
    save_report(tom)

    save_schedule_registry(
        {
            "version": 1,
            "timezone": "Asia/Singapore",
            "profiles": {
                "fiona-cao": {
                    "name": "Fiona Cao",
                    "enabled": True,
                    "delivery_target": "origin",
                    "meeting": {"type": "weekly", "weekday": 1, "time": "13:15"},
                    "prep_offset_minutes": 5,
                    "template_style": "ultra_short_telegram",
                }
            },
        }
    )



def test_resolve_prep_report_allows_unique_first_name(tmp_path, monkeypatch):
    _install_reports(tmp_path, monkeypatch)
    from people_manager.ad_hoc_prep import resolve_prep_report

    meta, error = resolve_prep_report("Fiona")

    assert error is None
    assert meta is not None
    assert meta["slug"] == "fiona-cao"



def test_resolve_prep_report_rejects_ambiguous_first_name(tmp_path, monkeypatch):
    _install_reports(tmp_path, monkeypatch)
    from people_manager.ad_hoc_prep import resolve_prep_report

    meta, error = resolve_prep_report("Tom")

    assert meta is None
    assert "Multiple direct reports match `Tom`" in error
    assert "Tom Zhu" in error
    assert "Tom Lee" in error


def test_resolve_prep_report_rejects_partial_prefix_guess(tmp_path, monkeypatch):
    _install_reports(tmp_path, monkeypatch)
    from people_manager.ad_hoc_prep import resolve_prep_report

    meta, error = resolve_prep_report("Fi")

    assert meta is None
    assert "No direct report found" in error



def test_render_ad_hoc_prep_note_returns_short_tg_ready_output(tmp_path, monkeypatch):
    _install_reports(tmp_path, monkeypatch)
    from people_manager.ad_hoc_prep import build_ad_hoc_prep_note

    text = build_ad_hoc_prep_note("Fiona")
    lines = text.splitlines()

    assert lines[0] == "Fiona Cao 1:1"
    assert 5 <= len(lines) <= 8
    assert "weekly operating sync" in text
    assert "family summer travels" in text
    assert "family SGC application" in text
    assert "watch detail-sensitive items early" in text
    assert "tone: warm, encouraging, trust-high" in text
