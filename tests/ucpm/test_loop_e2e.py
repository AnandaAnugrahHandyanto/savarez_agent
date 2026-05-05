"""End-to-end test of the file-based property loop on the three example
messages from `examples/test-emails/`.

Exercises:
  - Inbox traversal + JSON parse.
  - P-01 classification (3 messages).
  - P-02 triage (only the 2 maintenance messages).
  - Drafter (3 messages).
  - Audit log JSONL emission (one file per message, multiple rows each).
  - Gate evaluation (legal / lease / spend / emergency / novel).
  - Human-attention bool consistency with gates + emergency triage.

LLM is mocked via the shared `fake_llm` fixture — no API calls.
"""

from __future__ import annotations

import json
from pathlib import Path

from hermes_agent.loops.audit import AuditWriter
from hermes_agent.loops.property_test_loop import run_loop


def test_loop_processes_three_examples_end_to_end(
    inbox_dir, outbox_dir, audit_dir, company_dir, fake_llm
):
    summary = run_loop(
        inbox_dir=inbox_dir,
        outbox_dir=outbox_dir,
        audit_dir=audit_dir,
        company_dir=company_dir,
        llm=fake_llm,
    )

    # All three messages processed, no skipped.
    assert len(summary.processed) == 3
    assert summary.skipped == []

    # 3 classify + 2 triage (only maintenance) + 3 draft = 8 LLM calls.
    assert summary.llm_calls == 8

    by_id = {r.msg_id: r for r in summary.processed}
    assert set(by_id) == {"msg-001", "msg-002", "msg-003"}

    # ----- msg-003: emergency water leak -----
    water = by_id["msg-003"]
    assert water.classification.intent == "maintenance"
    assert water.triage is not None
    assert water.triage.urgency == "emergency"
    assert "emergency-vendor-dispatch" in water.gates_triggered
    assert "spend>500" in water.gates_triggered  # cost band 501-2000
    assert water.human_attention_required is True

    # ----- msg-001: AC down, high but not emergency -----
    hvac = by_id["msg-001"]
    assert hvac.classification.intent == "maintenance"
    assert hvac.triage is not None
    assert hvac.triage.urgency == "high"
    assert hvac.triage.category == "hvac"
    assert hvac.gates_triggered == []
    assert hvac.human_attention_required is False

    # ----- msg-002: rent question -----
    rent = by_id["msg-002"]
    assert rent.classification.intent == "payment"
    assert rent.triage is None
    assert rent.gates_triggered == []
    assert rent.human_attention_required is False


def test_loop_writes_draft_envelope_with_correct_shape(
    inbox_dir, outbox_dir, audit_dir, company_dir, fake_llm
):
    run_loop(
        inbox_dir=inbox_dir,
        outbox_dir=outbox_dir,
        audit_dir=audit_dir,
        company_dir=company_dir,
        llm=fake_llm,
    )

    drafts_dir = outbox_dir / "drafts"
    written = sorted(p.name for p in drafts_dir.glob("*.json"))
    assert written == ["msg-001.json", "msg-002.json", "msg-003.json"]

    water = json.loads((drafts_dir / "msg-003.json").read_text(encoding="utf-8"))
    assert water["source_msg_id"] == "msg-003"
    assert water["classification"]["intent"] == "maintenance"
    assert water["triage"]["urgency"] == "emergency"
    assert "emergency-vendor-dispatch" in water["gates_triggered"]
    assert water["human_attention_required"] is True
    assert water["drafted_action"]["type"] == "email_reply_to_tenant"
    assert water["drafted_action_secondary"]["type"] == "vendor_dispatch_draft"
    # No vendor list loaded yet, so we expect a TBD placeholder.
    assert "TBD" in water["drafted_action_secondary"]["vendor"]

    rent = json.loads((drafts_dir / "msg-002.json").read_text(encoding="utf-8"))
    assert rent["classification"]["intent"] == "payment"
    assert rent["triage"] is None
    assert rent["drafted_action"]["queued_for_approval"] is True
    assert rent["drafted_action_secondary"] is None


def test_loop_writes_audit_log_per_message(
    inbox_dir, outbox_dir, audit_dir, company_dir, fake_llm
):
    run_loop(
        inbox_dir=inbox_dir,
        outbox_dir=outbox_dir,
        audit_dir=audit_dir,
        company_dir=company_dir,
        llm=fake_llm,
    )

    written = sorted(p.name for p in audit_dir.glob("*.jsonl"))
    assert written == ["msg-001.jsonl", "msg-002.jsonl", "msg-003.jsonl"]

    # Maintenance flow: receive, classify(P-01), triage(P-02), draft, vendor, emit.
    hvac_rows = [
        json.loads(line)
        for line in (audit_dir / "msg-001.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    procedures = [r["procedure_id"] for r in hvac_rows]
    steps = [r["step"] for r in hvac_rows]
    assert "P-01" in procedures
    assert "P-02" in procedures
    assert "classify_intent" in steps
    assert "triage_maintenance" in steps
    assert "draft_reply" in steps
    assert "draft_vendor_dispatch" in steps
    assert "emit_envelope" in steps

    # Every row carries the SOP audit-log columns.
    required_columns = {
        "ts",
        "property_id",
        "procedure_id",
        "step",
        "persona",
        "inputs_hash",
        "action",
        "escalated_bool",
        "operator_review_state",
    }
    for row in hvac_rows:
        assert required_columns.issubset(row.keys()), (
            f"missing audit columns: {required_columns - row.keys()}"
        )
    # Property id pulled from company-dir basename.
    assert hvac_rows[0]["property_id"] == "1011-verrado-office"

    # Non-maintenance flow has NO P-02 row.
    rent_rows = [
        json.loads(line)
        for line in (audit_dir / "msg-002.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert all(r["procedure_id"] != "P-02" for r in rent_rows)

    # Emergency flow escalates the final emit row.
    water_rows = [
        json.loads(line)
        for line in (audit_dir / "msg-003.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    emit_row = next(r for r in water_rows if r["step"] == "emit_envelope")
    assert emit_row["escalated_bool"] is True


def test_loop_skips_malformed_inbox_entries(
    inbox_dir, outbox_dir, audit_dir, company_dir, fake_llm
):
    bogus = inbox_dir / "bogus.json"
    bogus.write_text("{not valid json", encoding="utf-8")

    summary = run_loop(
        inbox_dir=inbox_dir,
        outbox_dir=outbox_dir,
        audit_dir=audit_dir,
        company_dir=company_dir,
        llm=fake_llm,
    )

    assert len(summary.processed) == 3
    assert len(summary.skipped) == 1
    skipped_path, reason = summary.skipped[0]
    assert skipped_path.name == "bogus.json"
    assert "malformed" in reason


def test_audit_writer_inputs_hash_is_stable(tmp_path: Path):
    writer = AuditWriter(tmp_path, "msg-x", property_id="prop-1")
    payload = {"a": 1, "b": [1, 2, 3]}
    from hermes_agent.loops.audit import compute_inputs_hash

    h1 = compute_inputs_hash(payload)
    h2 = compute_inputs_hash({"b": [1, 2, 3], "a": 1})  # same content, different key order
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex
