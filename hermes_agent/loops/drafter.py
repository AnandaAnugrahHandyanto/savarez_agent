"""Draft outbound responses for the file-based test property loop.

This is the third LLM-call site (after P-01 classify and P-02 triage). It
produces the `drafted_action` body that goes into `outbox/drafts/<id>.json`.

For maintenance with `urgency in {emergency, high, normal, scheduled}` we
also draft a vendor-dispatch summary (the secondary action). The actual
vendor selection in production would query `ucpm.vendors` per P-02; in
the file loop we return a "TBD - no vendor list loaded" placeholder so the
draft is reviewable end-to-end without a vendor table.

For non-maintenance intents we draft only an acknowledgement and let
P-09 (escalation) carry the matter forward — the loop marks
`human_attention_required=true` for those.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from .llm_client import LlmClient
from .schemas import (
    Classification,
    DraftedAction,
    InboundMessage,
    Triage,
    VendorDispatchDraft,
)

logger = logging.getLogger(__name__)


DRAFT_INSTRUCTION = """\
You are the `assistant-property-manager` persona. Draft an outbound email
reply to the tenant for the message below, using the SOP's tone guidance:
direct, scannable, no hedging, plain language. Do NOT cite statutes. Do
NOT promise specific dates or vendors unless given. The reply will be
queued for operator approval before sending — except the maintenance
acknowledgement template (P-02 pre-approved auto-send class), which can
be sent automatically.

Inputs you will receive in the user payload:
  - message: the inbound tenant comm.
  - classification: the P-01 result.
  - triage: the P-02 result if maintenance, else null.

Respond with ONLY a JSON object, no prose:

{
  "subject": "...",
  "body": "...",
  "template_id": "<one of: ack_maintenance, ack_payment_question,
                   ack_complaint_neighbor, ack_admin, ack_lease_change,
                   ack_legal, ack_unclassified>",
  "queued_for_approval": <true|false>,
  "vendor_summary": "<one-line work order summary for vendor dispatch
                     (maintenance only, else empty string)>"
}

Rules for `queued_for_approval`:
  - intent=maintenance → false (ack is in the pre-approved auto-send class).
  - any other intent → true.
"""


def draft_reply(
    message: InboundMessage,
    classification: Classification,
    triage: Optional[Triage],
    *,
    sop_text: str,
    company_context: str,
    llm: LlmClient,
) -> tuple[DraftedAction, Optional[VendorDispatchDraft]]:
    payload = {
        "message": {
            "from": message.from_,
            "subject": message.subject,
            "body": message.body,
        },
        "classification": classification.model_dump(),
        "triage": triage.model_dump() if triage else None,
    }
    user_payload = json.dumps(payload, separators=(",", ":"))

    parsed: dict[str, Any]
    try:
        parsed, _call = llm.call_json(
            cached_context_blocks=[sop_text, company_context],
            instruction=DRAFT_INSTRUCTION,
            user_payload=user_payload,
            max_tokens=1024,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Draft LLM call failed for message %s", message.id)
        return _safe_fallback(message, classification, triage, error=str(exc))

    try:
        action = DraftedAction(
            type="email_reply_to_tenant",
            subject=parsed.get("subject"),
            body=parsed.get("body", ""),
            queued_for_approval=bool(
                parsed.get(
                    "queued_for_approval",
                    classification.intent != "maintenance",
                )
            ),
            template_id=parsed.get("template_id"),
        )
    except Exception as exc:  # noqa: BLE001
        return _safe_fallback(message, classification, triage, error=str(exc))

    secondary: Optional[VendorDispatchDraft] = None
    if classification.intent == "maintenance" and triage is not None:
        vendor_summary = parsed.get("vendor_summary") or _default_vendor_summary(
            message, triage
        )
        secondary = VendorDispatchDraft(
            vendor=f"TBD - no vendor list loaded for {triage.category} yet",
            work_order_summary=vendor_summary,
            queued_for_approval=True,
        )
    return action, secondary


def _safe_fallback(
    message: InboundMessage,
    classification: Classification,
    triage: Optional[Triage],
    *,
    error: str,
) -> tuple[DraftedAction, Optional[VendorDispatchDraft]]:
    """If the drafting call fails, produce a minimal but valid envelope so
    the operator still sees something actionable.
    """
    body = (
        f"[auto-fallback draft — drafting LLM call failed: {error}]\n\n"
        f"Tenant message: {message.subject or '(no subject)'}\n"
        f"Classified as: {classification.intent}\n"
        "Operator: please draft a reply manually."
    )
    action = DraftedAction(
        type="email_reply_to_tenant",
        subject=f"Re: {message.subject}" if message.subject else "Re: your message",
        body=body,
        queued_for_approval=True,  # never auto-send a fallback
        template_id="ack_unclassified",
    )
    secondary: Optional[VendorDispatchDraft] = None
    if classification.intent == "maintenance" and triage is not None:
        secondary = VendorDispatchDraft(
            vendor=f"TBD - no vendor list loaded for {triage.category} yet",
            work_order_summary=_default_vendor_summary(message, triage),
            queued_for_approval=True,
        )
    return action, secondary


def _default_vendor_summary(message: InboundMessage, triage: Triage) -> str:
    return (
        f"{triage.urgency.upper()} {triage.category} issue reported by tenant. "
        f"Subject: {message.subject!r}. "
        f"Operator review pending; full body in source comm."
    )
