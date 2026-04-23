from starlette.testclient import TestClient


def _auth_client(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    from hermes_cli.web_server import app, _SESSION_TOKEN

    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {_SESSION_TOKEN}"
    return client


def _seed_people_state():
    from people_manager.storage import create_report, load_report, save_report
    from people_manager.schedule_store import save_schedule_registry

    report = create_report("Fiona Cao", "Chief of Staff", "Own follow-through")
    report["upcoming_one_on_one"] = {
        "ritual": "weekly operating sync",
        "topics": ["family summer travels", "family SGC application"],
        "relationship_goal": "warm, encouraging",
    }
    report["open_loops"] = {
        "open_todos_for_michael": ["confirm founder follow-through"],
        "current_focus_topics": ["calendar ops"],
    }
    report["management_strategy"] = {"how_michael_should_manage_them": ["watch detail-sensitive items early"]}
    save_report(report)
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
    return load_report("fiona-cao")


def test_people_profiles_and_profile_detail_endpoints(tmp_path, monkeypatch):
    client = _auth_client(tmp_path, monkeypatch)
    _seed_people_state()

    list_resp = client.get("/api/people/profiles")
    detail_resp = client.get("/api/people/profiles/fiona-cao")

    assert list_resp.status_code == 200
    assert detail_resp.status_code == 200
    assert any(item["slug"] == "fiona-cao" for item in list_resp.json()["profiles"])
    assert detail_resp.json()["profile"]["slug"] == "fiona-cao"


def test_people_prep_endpoints_share_modes(tmp_path, monkeypatch):
    client = _auth_client(tmp_path, monkeypatch)
    _seed_people_state()

    adhoc_resp = client.get("/api/people/profiles/fiona-cao/prep?mode=adhoc")
    scheduled_resp = client.get("/api/people/profiles/fiona-cao/prep?mode=scheduled")

    assert adhoc_resp.status_code == 200
    assert scheduled_resp.status_code == 200
    assert adhoc_resp.json()["brief"].splitlines()[0] == "Fiona Cao 1:1"
    assert scheduled_resp.json()["brief"].splitlines()[0] == "Fiona Cao 1:1 in 5m"
    assert adhoc_resp.json()["brief"].splitlines()[1:] == scheduled_resp.json()["brief"].splitlines()[1:]


def test_people_schedule_and_ops_endpoints(tmp_path, monkeypatch):
    client = _auth_client(tmp_path, monkeypatch)
    _seed_people_state()

    schedules_resp = client.get("/api/people/schedules")
    due_now_resp = client.get("/api/people/ops/due-now", params={"now": "2026-04-20T13:10:00+08:00"})
    team_scan_resp = client.get("/api/people/team-scan")

    assert schedules_resp.status_code == 200
    assert due_now_resp.status_code == 200
    assert team_scan_resp.status_code == 200
    assert "fiona-cao" in schedules_resp.json()["schedules"]
    assert team_scan_resp.json()["markdown"].startswith("Team scan")
