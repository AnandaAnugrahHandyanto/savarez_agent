from starlette.testclient import TestClient


def test_nexusos_dashboard_route_renders_main_sections(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from hermes_cli.web_server import app, _SESSION_TOKEN
    from people_manager.storage import create_report

    create_report("Fiona Cao", "Chief of Staff", "Own follow-through")

    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {_SESSION_TOKEN}"
    resp = client.get("/nexusos")

    assert resp.status_code == 200
    assert "NexusOS" in resp.text
    assert "Team Overview" in resp.text
    assert "Person Profile" in resp.text
    assert "Prep View" in resp.text
    assert "Team Scan / Calibration" in resp.text
    assert "Ops / Schedule View" in resp.text
