import json

from agent.knowledge_lanes import (
    KnowledgeLaneStore,
    validate_knowledge_payload,
)


def test_add_draft_creates_typed_record(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store = KnowledgeLaneStore()

    record = store.add_draft(
        title="Tiger Smart Invest note",
        body="Likely not true instant redemption.",
        source="chat:user",
        provenance={"message_id": "123"},
        tags=["tiger", "finance"],
        confidence="medium",
    )

    assert record["lane"] == "draft"
    assert record["status"] == "draft"
    assert record["source"] == "chat:user"
    assert record["provenance"]["message_id"] == "123"
    assert record["confidence"] == "medium"


def test_promote_draft_moves_record_to_promoted_lane_with_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store = KnowledgeLaneStore()
    draft = store.add_draft(
        title="Context7 is useful",
        body="Use it as a read-only docs sidecar.",
        source="repo:deep-dive",
        provenance={"report": "context7.md"},
    )

    promoted = store.promote_draft(
        draft["id"],
        promotion_reason="validated against pack synthesis",
        evidence=["report:context7", "report:hermes-self-evolution"],
    )

    assert promoted["lane"] == "promoted"
    assert promoted["status"] == "promoted"
    assert promoted["promotion"]["reason"] == "validated against pack synthesis"
    assert promoted["promotion"]["evidence"] == ["report:context7", "report:hermes-self-evolution"]

    state = store.read_state()
    assert len(state["draft_items"]) == 0
    assert len(state["promoted_items"]) == 1


def test_validate_knowledge_payload_reports_invalid_shapes():
    payload = {
        "schema_version": 1,
        "draft_items": [
            {
                "id": "x",
                "lane": "draft",
                "title": "Bad draft",
                "body": "Missing provenance and bad confidence",
                "source": "chat:user",
                "provenance": "oops",
                "confidence": "certain",
                "status": "draft",
                "created_at": "",
                "tags": "bad",
            }
        ],
        "promoted_items": [],
    }

    errors = validate_knowledge_payload(payload)

    assert any("provenance" in err for err in errors)
    assert any("confidence" in err for err in errors)
    assert any("tags" in err for err in errors)
    assert any("created_at" in err for err in errors)


def test_validator_summary_marks_promoted_store_valid(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store = KnowledgeLaneStore()
    draft = store.add_draft(
        title="Provider routing should be validated",
        body="Invalid config should fail closed.",
        source="repo:inspection",
        provenance={"file": "gateway/run.py"},
    )
    store.promote_draft(draft["id"], promotion_reason="implemented", evidence=["tests"])

    report = store.validation_report()

    assert report["valid"] is True
    assert report["counts"]["draft"] == 0
    assert report["counts"]["promoted"] == 1
    assert report["errors"] == []


def test_state_persists_as_json_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store = KnowledgeLaneStore()
    store.add_draft(
        title="Draft persists",
        body="Persist me",
        source="chat:user",
        provenance={"message_id": "1"},
    )

    path = tmp_path / "knowledge" / "knowledge_lanes.json"
    payload = json.loads(path.read_text())
    assert payload["schema_version"] == 1
    assert len(payload["draft_items"]) == 1
