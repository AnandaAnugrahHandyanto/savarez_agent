from pathlib import Path

from hermes_state import SessionDB


def test_campaign_round_trip_persists_across_reopen(tmp_path: Path):
    db_path = tmp_path / "state.db"
    db = SessionDB(db_path)

    campaign_id = db.campaign_start(
        "Ship Spar to production",
        next_step="Implement failure registry",
        metadata={"owner": "dom"},
    )
    assert db.campaign_log(
        campaign_id,
        {"name": "ratchet_done", "details": "snapshot flow landed"},
        status="active",
        next_step="land spar tool",
    )
    assert db.campaign_log(
        campaign_id,
        "spar_done",
        next_step="wire proving matrix",
    )
    db.close()

    reopened = SessionDB(db_path)
    open_campaigns = reopened.campaign_resume()
    assert [item["id"] for item in open_campaigns] == [campaign_id]
    campaign = open_campaigns[0]
    assert campaign["goal"] == "Ship Spar to production"
    assert campaign["status"] == "active"
    assert campaign["next_step"] == "wire proving matrix"
    assert campaign["metadata"]["owner"] == "dom"
    assert [item["name"] for item in campaign["milestones"]] == [
        "created",
        "ratchet_done",
        "spar_done",
    ]


def test_campaign_close_and_prune(tmp_path: Path):
    db = SessionDB(tmp_path / "state.db")
    campaign_id = db.campaign_start("Close the loop")

    assert db.campaign_close(campaign_id, "merged", next_step="observe live usage")
    assert db.campaign_resume() == []

    campaign = db.get_campaign(campaign_id)
    assert campaign["status"] == "completed"
    assert campaign["verdict"] == "merged"

    assert db.prune_closed_campaigns(older_than_days=0) == 1
    assert db.get_campaign(campaign_id) is None
