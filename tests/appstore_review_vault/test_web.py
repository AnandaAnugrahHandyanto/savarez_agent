from pathlib import Path

from fastapi.testclient import TestClient

from appstore_review_vault.main import create_app


def make_client(tmp_path):
    app = create_app(tmp_path / "reviews.sqlite", tmp_path / "apps.yaml")
    return TestClient(app)


def test_web_pages_render(tmp_path):
    client = make_client(tmp_path)

    for path in ["/", "/apps", "/reviews", "/runs", "/errors"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "App Store Review Vault" in response.text


def test_add_archive_restore_app_flow(tmp_path):
    client = make_client(tmp_path)

    response = client.post("/apps", data={"app_id": "1477376905", "name": "GitHub"}, follow_redirects=False)
    assert response.status_code == 303

    response = client.get("/apps")
    assert "1477376905" in response.text
    assert "GitHub" in response.text

    response = client.post("/apps/1477376905/archive", follow_redirects=False)
    assert response.status_code == 303
    active_html = client.get("/apps").text
    assert "GitHub" not in active_html
    assert "archived" in client.get("/apps?include_archived=true").text

    response = client.post("/apps/1477376905/restore", follow_redirects=False)
    assert response.status_code == 303
    assert "1477376905" in client.get("/apps").text
