from fastapi.testclient import TestClient

from people_manager.storage import create_report
from people_manager.web_service import create_app


def test_standalone_peopleos_service_serves_health_profiles_and_webui_shell(tmp_path, monkeypatch):
    monkeypatch.setenv("PEOPLEOS_DATA_ROOT", str(tmp_path / "peopleos-data"))
    create_report("Fiona Cao", "COO", "Run operations")
    client = TestClient(create_app())

    health = client.get("/healthz")
    profiles = client.get("/api/profiles")
    webui = client.get("/")

    assert health.status_code == 200
    assert health.json()["service"] == "peopleos"
    assert profiles.status_code == 200
    assert profiles.json()["profiles"][0]["slug"] == "fiona-cao"
    assert webui.status_code == 200
    assert "PeopleOS" in webui.text
    assert "profile-list" in webui.text
    assert "fetch('/api/profiles')" in webui.text
    assert "create-profile-form" in webui.text
    assert "create-profile-panel" in webui.text
    assert "toggleCreatePanel" in webui.text
    for marker in (
        "tab-all",
        "tab-nexus",
        "tab-satellites",
        "tab-external",
        "tab-due",
        "tab-open-loops",
    ):
        assert marker in webui.text
    assert "Nexus" in webui.text
    assert "Satellites" in webui.text
    assert "External" in webui.text
    assert "profile-sort-select" in webui.text
    for marker in ("sort-rank", "sort-updated", "sort-next-followup", "sort-first-name"):
        assert marker in webui.text
    assert "sortProfiles" in webui.text
    assert "numericRank" in webui.text
    for marker in ("detail-tab-summary", "detail-tab-touch", "detail-tab-fields", "detail-tab-loops"):
        assert marker in webui.text
    assert "openProfile(p.slug, 'touch')" in webui.text
    assert "profile-card-next-meeting" in webui.text
    assert "Next meeting:" in webui.text
    assert "setRosterTab" in webui.text
    assert "setDetailTab" in webui.text
    assert "profile_type" in webui.text
    assert "category" in webui.text
    assert "field-category" in webui.text
    assert "Nexus" in webui.text
    assert "Satellites" in webui.text
    assert "External" in webui.text
    assert "field-rank" in webui.text
    assert "Rank (1-101)" in webui.text
    assert "field-roles" in webui.text
    assert "field-mandates" in webui.text
    assert "field-trust" in webui.text
    assert "Rock Solid" in webui.text
    assert "Very High" in webui.text
    assert "field-cadence" in webui.text
    assert "weekly" in webui.text
    assert "biweekly" in webui.text
    assert "monthly" in webui.text
    assert "cadence-details-panel" in webui.text
    assert "field-cadence-week-of-month" in webui.text
    assert "field-cadence-week-parity" in webui.text
    assert "odd week" in webui.text
    assert "even week" in webui.text
    assert "field-cadence-weekday" in webui.text
    assert "field-cadence-hour" in webui.text
    assert "field-cadence-minute" in webui.text
    assert "buildCadenceDetails" in webui.text
    assert "applyCadenceDetails" in webui.text
    assert "1st week" in webui.text
    assert "Monday" in webui.text
    assert "09" in webui.text
    assert "30" in webui.text
    assert "field-last-meeting-date" in webui.text
    assert "Last meeting date (yyyy-mm-dd)" in webui.text
    assert "edit-last-meeting-date" in webui.text
    assert "save-last-meeting-date" in webui.text
    assert "cancel-last-meeting-date" in webui.text
    assert "edit-next-meeting-date" in webui.text
    assert "save-next-meeting-date" in webui.text
    assert "cancel-next-meeting-date" in webui.text
    assert "setMeetingDateEditMode" in webui.text
    assert "next-meeting-calculated-preview" in webui.text
    assert "recalculateNextMeetingDate" in webui.text
    assert "field-last-meeting-notes" in webui.text
    assert "field-next-meeting-date" in webui.text
    assert "Next meeting date (yyyy-mm-dd)" in webui.text
    assert "field-prep-notes" in webui.text
    assert "field-performance-rating" in webui.text
    assert "exceeds expectations" in webui.text
    assert "meets expectations" in webui.text
    assert "below expectations" in webui.text
    assert "field-long-term-notes-todos" in webui.text
    assert "field-strengths" in webui.text
    assert "field-weaknesses" in webui.text
    assert "saveProfileFields" in webui.text
    assert "fetch(`/api/profiles/${encodeURIComponent(slug)}`" in webui.text
    assert "Standalone PeopleOS service is running" not in webui.text


def test_standalone_peopleos_service_can_create_external_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("PEOPLEOS_DATA_ROOT", str(tmp_path / "peopleos-data"))
    client = TestClient(create_app())

    response = client.post(
        "/api/profiles",
        json={
            "name": "External Partner",
            "role_title": "Investor",
            "mandate": "Maintain relationship",
            "profile_type": "external",
            "relationship_kind": "investor",
            "checkup_cadence": "monthly",
        },
    )

    assert response.status_code == 200
    profile = response.json()["profile"]
    assert profile["profile_type"] == "external"
    assert profile["relationship_kind"] == "investor"
    assert profile["checkup_cadence"] == "monthly"
    profiles = client.get("/api/profiles?profile_type=external").json()["profiles"]
    assert [item["slug"] for item in profiles] == ["external-partner"]


def test_standalone_peopleos_service_creates_interactions_without_hermes_dashboard_prefix(tmp_path, monkeypatch):
    monkeypatch.setenv("PEOPLEOS_DATA_ROOT", str(tmp_path / "peopleos-data"))
    create_report("Fiona Cao", "COO", "Run operations")
    client = TestClient(create_app())

    response = client.post(
        "/api/profiles/fiona-cao/interactions",
        json={"kind": "update", "body": "Miya note", "lane_id": "miya-telegram"},
    )

    assert response.status_code == 200
    assert response.json()["interaction"]["source"]["lane"] == "miya-telegram"


def test_standalone_peopleos_service_does_not_mount_hermes_dashboard_people_prefix(tmp_path, monkeypatch):
    monkeypatch.setenv("PEOPLEOS_DATA_ROOT", str(tmp_path / "peopleos-data"))
    client = TestClient(create_app())

    response = client.get("/api/people/profiles")

    assert response.status_code == 404
