"""P-01 — Inbound tenant comm intake.

Classifies an inbound message into exactly one of the eight intents
defined in SOP P-01. The SOP is a deterministic first-match-wins rule
list; we delegate the matching to the model with the SOP itself in cache,
because keyword matching alone fails on polite/indirect tenant phrasing.

The model returns a JSON object matching `Classification`. We validate
shape; if validation fails we fall back to `intent=unclassified` so the
loop continues and P-09 picks up the escalation downstream.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .llm_client import LlmClient
from .schemas import Classification, InboundMessage

logger = logging.getLogger(__name__)


P01_INSTRUCTION = """\
You are the `property-orchestrator` persona. Apply procedure **P-01 —
Inbound tenant comm intake** from the SOP above.

Task: classify the incoming tenant message into exactly ONE intent using
the SOP's first-match-wins decision rules:

    1. maintenance       — habitability/repair issues
    2. payment           — rent, balance, autopay, receipts
    3. lease_change      — renew, extend, terminate, move-out, sublease, alter
    4. notice_required   — formal notice (e.g. intent to vacate)
    5. complaint_neighbor — noise, parking, smoke (cannabis context), neighbors
    6. admin             — COI, keys, parking permits, contact updates
    7. legal             — attorney, court, ADA, fair housing, statute citations
    8. unclassified      — none of the above

Also: identify the tenant if possible. The company state and tenant
records are in the system context above. Use the sender email or body
content to match a tenant; produce a short slug (e.g. "beautiful-minds-a-101")
if confident, else null.

Respond with ONLY a JSON object, no prose, no code fences:

{
  "intent": "<one of the eight>",
  "tenant_slug": "<slug or null>",
  "confidence": <float 0.0-1.0>,
  "rationale": "<one short sentence>"
}
"""


def classify(
    message: InboundMessage,
    *,
    sop_text: str,
    company_context: str,
    llm: LlmClient,
) -> Classification:
    """Run P-01 classification on a single inbound message.

    Args:
        message: parsed inbox message.
        sop_text: full SOP markdown — cached system block.
        company_context: rendered per-property context — cached system block.
        llm: shared LLM client (one instance reused across the inbox so
            prompt cache hits across messages).

    Returns:
        Classification. On validation failure, falls back to
        `intent=unclassified` and surfaces the parse error in the rationale.
    """
    user_payload = json.dumps(_message_payload(message), separators=(",", ":"))

    parsed: dict[str, Any]
    try:
        parsed, _call = llm.call_json(
            cached_context_blocks=[sop_text, company_context],
            instruction=P01_INSTRUCTION,
            user_payload=user_payload,
            max_tokens=512,
        )
    except Exception as exc:  # noqa: BLE001 — never let a bad LLM call break the loop
        logger.exception("P-01 LLM call failed for message %s", message.id)
        return Classification(
            intent="unclassified",
            tenant_slug=None,
            confidence=0.0,
            rationale=f"classifier-error: {type(exc).__name__}: {exc!s}"[:240],
        )

    try:
        return Classification(**parsed)
    except Exception as exc:  # noqa: BLE001 — schema mismatch
        logger.warning(
            "P-01 returned unparseable JSON for %s: %r — defaulting to unclassified",
            message.id,
            parsed,
        )
        return Classification(
            intent="unclassified",
            tenant_slug=None,
            confidence=0.0,
            rationale=f"schema-error: {type(exc).__name__}: {exc!s}"[:240],
        )


def _message_payload(message: InboundMessage) -> dict[str, Any]:
    """Trim attachments to references — never feed raw blobs to the model."""
    return {
        "id": message.id,
        "received_at": message.received_at.isoformat(),
        "channel": message.channel,
        "from": message.from_,
        "to": message.to,
        "subject": message.subject,
        "body": message.body,
        "attachment_count": len(message.attachments),
    }
