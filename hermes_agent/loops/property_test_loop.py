"""File-based test loop for P-01 + P-02 (CHG-0002).

Reads inbound messages from `inbox/`, runs P-01 classification, conditionally
runs P-02 triage, drafts a response, and writes:
  - `outbox/drafts/<id>.json`  — the drafted action(s) + decisions
  - `audit-log/<id>.jsonl`     — one row per procedure step

This is a local-only loop. No SMTP/IMAP, no Postgres, no external state.
Once it works against synthetic emails the agent stack is verified end-to-end
and the production wiring (SMTP/IMAP, the BigQuery `ucpm.*` ledger, the
Command Center buttons) lands later.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .audit import AuditWriter, compute_inputs_hash
from .classifier import classify
from .drafter import draft_reply
from .llm_client import LlmClient
from .schemas import (
    Classification,
    DraftEnvelope,
    DraftedAction,
    InboundMessage,
    Triage,
    VendorDispatchDraft,
)
from .sop_loader import (
    SopBundle,
    discover_inbox_messages,
    load_message,
    load_sop_bundle,
    render_company_context_block,
)
from .triage import triage as run_triage

logger = logging.getLogger(__name__)


# Intents that the SOP says cannot be auto-acknowledged and must escalate
# (legal-gate / lease-change-gate / novel-situation-gate).
_ESCALATING_INTENTS = {"lease_change", "notice_required", "legal", "unclassified"}


@dataclass
class LoopResult:
    """One processed message's outcome."""

    msg_id: str
    draft_path: Path
    audit_path: Path
    classification: Classification
    triage: Optional[Triage]
    gates_triggered: list[str]
    human_attention_required: bool


@dataclass
class LoopRunSummary:
    """Aggregate result of running the loop over an inbox."""

    processed: list[LoopResult]
    skipped: list[tuple[Path, str]]  # (path, reason)
    llm_calls: int


def run_loop(
    *,
    inbox_dir: Path,
    outbox_dir: Path,
    audit_dir: Path,
    company_dir: Path,
    llm: Optional[LlmClient] = None,
    property_id: Optional[str] = None,
) -> LoopRunSummary:
    """Process every message in `inbox/` and write drafts + audit logs.

    Args:
        inbox_dir: directory containing `*.json` inbound messages.
        outbox_dir: parent dir; drafts go to `<outbox_dir>/drafts/`.
        audit_dir: parent dir for `<msg_id>.jsonl` audit logs.
        company_dir: per-property company directory under `paperclip-UCPM/companies/`.
            If the SOP is not present here, the loader walks up to
            `companies/ucpm-default/SOP.md`.
        llm: optional preconstructed LlmClient (tests inject a fake; real
            invocations let the loop construct a real Anthropic-backed one).
        property_id: stable id used in audit rows. Defaults to
            `<company_dir>.name`.
    """
    inbox_dir = inbox_dir.resolve()
    outbox_dir = outbox_dir.resolve()
    audit_dir = audit_dir.resolve()
    company_dir = company_dir.resolve()

    drafts_dir = outbox_dir / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)

    bundle = load_sop_bundle(company_dir)
    company_ctx = render_company_context_block(bundle)
    pid = property_id or bundle.company_slug

    llm_client = llm or LlmClient()

    processed: list[LoopResult] = []
    skipped: list[tuple[Path, str]] = []

    for msg_path in discover_inbox_messages(inbox_dir):
        try:
            raw = load_message(msg_path)
            message = InboundMessage.model_validate(raw)
        except Exception as exc:  # noqa: BLE001 — bad input shouldn't kill the loop
            logger.exception("Skipping malformed message %s", msg_path.name)
            skipped.append((msg_path, f"malformed: {type(exc).__name__}: {exc!s}"))
            continue

        try:
            result = _process_one(
                message=message,
                bundle=bundle,
                company_ctx=company_ctx,
                drafts_dir=drafts_dir,
                audit_dir=audit_dir,
                llm=llm_client,
                property_id=pid,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Loop crashed on message %s", message.id)
            skipped.append((msg_path, f"runtime: {type(exc).__name__}: {exc!s}"))
            continue
        processed.append(result)

    return LoopRunSummary(
        processed=processed,
        skipped=skipped,
        llm_calls=llm_client.call_count,
    )


def _process_one(
    *,
    message: InboundMessage,
    bundle: SopBundle,
    company_ctx: str,
    drafts_dir: Path,
    audit_dir: Path,
    llm: LlmClient,
    property_id: str,
) -> LoopResult:
    """Drive a single message through P-01 → (maybe P-02) → draft → audit."""
    audit = AuditWriter(audit_dir, message.id, property_id=property_id)

    msg_payload = message.model_dump(by_alias=True, mode="json")
    msg_hash = compute_inputs_hash(msg_payload)

    # ----- Audit: receipt -----
    audit.write(
        procedure_id="P-01",
        step="receive_inbound",
        persona="property-orchestrator",
        inputs_hash=msg_hash,
        action="received inbound comm",
        notes=f"channel={message.channel} from={message.from_}",
    )

    # ----- P-01 classify -----
    classification = classify(
        message,
        sop_text=bundle.sop_text,
        company_context=company_ctx,
        llm=llm,
    )
    audit.write(
        procedure_id="P-01",
        step="classify_intent",
        persona="property-orchestrator",
        inputs_hash=msg_hash,
        action=f"classified intent={classification.intent}",
        decision_criteria={
            "intent": classification.intent,
            "tenant_slug": classification.tenant_slug,
            "confidence": classification.confidence,
            "rationale": classification.rationale,
        },
    )

    # ----- P-02 triage if maintenance -----
    triage: Optional[Triage] = None
    if classification.intent == "maintenance":
        triage = run_triage(
            message,
            sop_text=bundle.sop_text,
            company_context=company_ctx,
            llm=llm,
        )
        audit.write(
            procedure_id="P-02",
            step="triage_maintenance",
            persona="assistant-property-manager",
            inputs_hash=msg_hash,
            action=f"triaged urgency={triage.urgency} category={triage.category}",
            decision_criteria={
                "urgency": triage.urgency,
                "category": triage.category,
                "payer_default": triage.payer_default,
                "estimated_cost_band": triage.estimated_cost_band,
                "rationale": triage.rationale,
            },
        )

    # ----- Determine gates + human-attention before drafting -----
    gates = _gates_triggered(classification, triage)
    human_attention = _needs_human_attention(classification, triage, gates)

    # ----- Draft reply (and optional vendor dispatch summary) -----
    drafted_action, vendor_secondary = draft_reply(
        message,
        classification,
        triage,
        sop_text=bundle.sop_text,
        company_context=company_ctx,
        llm=llm,
    )
    audit.write(
        procedure_id="P-01" if classification.intent != "maintenance" else "P-02",
        step="draft_reply",
        persona="assistant-property-manager",
        inputs_hash=msg_hash,
        action=f"drafted {drafted_action.type} (queued={drafted_action.queued_for_approval})",
        notes=f"template={drafted_action.template_id}",
    )
    if vendor_secondary is not None:
        audit.write(
            procedure_id="P-02",
            step="draft_vendor_dispatch",
            persona="assistant-property-manager",
            inputs_hash=msg_hash,
            action="drafted vendor dispatch (TBD vendor)",
        )

    # ----- Write the draft envelope -----
    envelope = DraftEnvelope(
        source_msg_id=message.id,
        classification=classification,
        triage=triage,
        drafted_action=drafted_action,
        drafted_action_secondary=vendor_secondary,
        gates_triggered=gates,
        human_attention_required=human_attention,
    )
    draft_path = drafts_dir / f"{message.id}.json"
    draft_path.write_text(
        json.dumps(envelope.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    audit.write(
        procedure_id="P-09" if gates else ("P-02" if triage else "P-01"),
        step="emit_envelope",
        persona="property-orchestrator",
        inputs_hash=msg_hash,
        action="wrote draft envelope",
        output_ref=str(draft_path),
        escalated=human_attention,
        operator_review_state="pending" if drafted_action.queued_for_approval else "n/a",
        decision_criteria={"gates_triggered": gates},
    )

    return LoopResult(
        msg_id=message.id,
        draft_path=draft_path,
        audit_path=audit.path,
        classification=classification,
        triage=triage,
        gates_triggered=gates,
        human_attention_required=human_attention,
    )


# ---------------------------------------------------------------------------
# Gate evaluation (rule-based, NOT LLM-driven — these are SOP invariants).
# ---------------------------------------------------------------------------


def _gates_triggered(
    classification: Classification, triage: Optional[Triage]
) -> list[str]:
    """SOP global-invariant gates — applied as pure code, never via the LLM.

    The SOP is explicit: gates (spend, legal, lease-change, novel) are
    enforced by the orchestrator. We evaluate them deterministically here so
    they can never silently regress when prompts change.
    """
    gates: list[str] = []

    # Legal gate.
    if classification.intent == "legal":
        gates.append("legal")

    # Lease-change gate.
    if classification.intent in {"lease_change", "notice_required"}:
        gates.append("lease-change")

    # Novel-situation gate.
    if classification.intent == "unclassified":
        gates.append("novel")

    # Maintenance-specific gates.
    if triage is not None:
        if triage.urgency == "emergency":
            gates.append("emergency-vendor-dispatch")
        # Spend gate: any band > $500 is a hard halt per SOP P-02.
        if triage.estimated_cost_band in {"501-2000", ">2000"}:
            gates.append("spend>500")

    return gates


def _needs_human_attention(
    classification: Classification,
    triage: Optional[Triage],
    gates: list[str],
) -> bool:
    """Should the operator be paged or surfaced at top of digest?

    Human attention is required when:
      - Any gate is tripped (legal/lease-change/novel/spend/emergency).
      - The intent is in the escalating set (lease_change, notice_required,
        legal, unclassified) per SOP P-01 escalation rules.
      - Maintenance triage is `urgency=emergency` (operator notification
        within 15 min per SOP P-02).
    """
    if gates:
        return True
    if classification.intent in _ESCALATING_INTENTS:
        return True
    if triage is not None and triage.urgency == "emergency":
        return True
    return False
