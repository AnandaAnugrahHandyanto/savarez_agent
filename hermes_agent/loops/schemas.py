"""Pydantic schemas for the file-based test property loop.

Shapes match the spec for CHG-0002 (P-01 + P-02). Structures here are
deliberately a subset of the full SOP — we only model what the loop reads
and writes today. Persistent stores (BigQuery `ucpm.*` tables, the draft
queue under `outbox/pending_approval/`, etc.) come later.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Inbound message
# ---------------------------------------------------------------------------


class InboundMessage(BaseModel):
    """Shape of `inbox/<id>.json` files."""

    id: str
    received_at: datetime
    channel: Literal["email", "sms", "voice", "other"] = "email"
    from_: str = Field(alias="from")
    to: str
    subject: str = ""
    body: str
    attachments: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# P-01 classification
# ---------------------------------------------------------------------------


# Intents are exactly the eight defined in SOP P-01 decision criteria.
Intent = Literal[
    "maintenance",
    "payment",
    "lease_change",
    "notice_required",
    "complaint_neighbor",
    "admin",
    "legal",
    "unclassified",
]


class Classification(BaseModel):
    intent: Intent
    tenant_slug: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""


# ---------------------------------------------------------------------------
# P-02 triage
# ---------------------------------------------------------------------------


Urgency = Literal["emergency", "high", "normal", "scheduled"]


class Triage(BaseModel):
    urgency: Urgency
    category: str  # hvac, plumbing, electrical, pest, lock, appliance, ...
    rationale: str
    payer_default: Literal["landlord", "tenant", "ambiguous"] = "landlord"
    estimated_cost_band: Literal["unknown", "<=500", "501-2000", ">2000"] = "unknown"


# ---------------------------------------------------------------------------
# Drafted action(s)
# ---------------------------------------------------------------------------


class DraftedAction(BaseModel):
    type: str  # email_reply_to_tenant, vendor_dispatch_draft, ...
    subject: Optional[str] = None
    body: str
    queued_for_approval: bool = True
    template_id: Optional[str] = None  # references a fixed SOP template, if any


class VendorDispatchDraft(BaseModel):
    type: Literal["vendor_dispatch_draft"] = "vendor_dispatch_draft"
    vendor: str
    work_order_summary: str
    queued_for_approval: bool = True


# ---------------------------------------------------------------------------
# Combined draft envelope
# ---------------------------------------------------------------------------


class DraftEnvelope(BaseModel):
    """Top-level shape written to `outbox/drafts/<id>.json`."""

    source_msg_id: str
    classification: Classification
    triage: Optional[Triage] = None
    drafted_action: DraftedAction
    drafted_action_secondary: Optional[VendorDispatchDraft] = None
    gates_triggered: list[str] = Field(default_factory=list)
    human_attention_required: bool = False


# ---------------------------------------------------------------------------
# Audit log row
# ---------------------------------------------------------------------------


class AuditRow(BaseModel):
    """One JSONL row in `audit-log/<id>.jsonl`.

    Schema mirrors `ucpm.audit_log` defined in SOP global invariants:
        ts, property_id, procedure_id, step, persona, inputs_hash,
        action, output_ref, escalated_bool, operator_review_state.
    """

    ts: datetime
    property_id: str
    procedure_id: str  # P-01, P-02, ...
    step: str
    persona: str  # property-orchestrator, assistant-property-manager, ...
    inputs_hash: str
    action: str  # short verb-phrase: "classified intent", "drafted ack", ...
    output_ref: Optional[str] = None  # path or id pointing at the produced artifact
    escalated_bool: bool = False
    operator_review_state: Literal[
        "n/a", "pending", "approved", "edited", "rejected", "deferred"
    ] = "n/a"
    # Loop-only addenda (not in BQ schema) — useful for debugging the file loop:
    decision_criteria: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""
