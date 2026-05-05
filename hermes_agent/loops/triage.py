"""P-02 — Maintenance request triage.

Classifies maintenance urgency (emergency / high / normal / scheduled),
identifies category and probable payer, and returns a structured Triage.

Spend-gate detection and explicit gate-tripping is computed by the loop
itself once we have triage output (see `test_property_loop.py`). This
module is concerned only with what the SOP P-02 decision rules say about
the message.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .llm_client import LlmClient
from .schemas import InboundMessage, Triage

logger = logging.getLogger(__name__)


P02_INSTRUCTION = """\
You are the `assistant-property-manager` persona. Apply procedure **P-02 —
Maintenance request triage** from the SOP above for the given inbound
maintenance message.

Decide:

  urgency: one of
    - emergency  (life-safety: gas, smoke, fire, active flood, sewage, no
                  heat<40F, no AC>90F+medical, sparking, broken exterior
                  lock, ceiling collapse, CO)
    - high       (habitability: no hot water, HVAC down, fridge dead, sole
                  toilet inop, slow leak, broken interior lock, infestation
                  observed)
    - normal     (cosmetic / non-habitability)
    - scheduled  (routine, not broken)

  category: short kebab-case tag (hvac, plumbing, electrical, pest, lock,
            appliance, roof, structural, other).

  payer_default: "landlord", "tenant", or "ambiguous".
    - default to landlord unless the body strongly indicates tenant-caused
      damage. v1 leans landlord for ambiguity.

  estimated_cost_band: "<=500", "501-2000", ">2000", or "unknown".

  rationale: one short sentence explaining the urgency call, anchored in
             the specific SOP rule that matched.

Respond with ONLY a JSON object, no prose:

{
  "urgency": "...",
  "category": "...",
  "rationale": "...",
  "payer_default": "...",
  "estimated_cost_band": "..."
}
"""


def triage(
    message: InboundMessage,
    *,
    sop_text: str,
    company_context: str,
    llm: LlmClient,
) -> Triage:
    """Run P-02 triage. On error, default to `urgency=high` (safer than normal)
    and flag in rationale so the loop escalates correctly.
    """
    user_payload = json.dumps(_message_payload(message), separators=(",", ":"))

    parsed: dict[str, Any]
    try:
        parsed, _call = llm.call_json(
            cached_context_blocks=[sop_text, company_context],
            instruction=P02_INSTRUCTION,
            user_payload=user_payload,
            max_tokens=512,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("P-02 LLM call failed for message %s", message.id)
        return Triage(
            urgency="high",
            category="other",
            rationale=f"triage-error fallback: {type(exc).__name__}: {exc!s}"[:240],
            payer_default="ambiguous",
            estimated_cost_band="unknown",
        )

    try:
        return Triage(**parsed)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "P-02 returned unparseable JSON for %s: %r — defaulting to high/other",
            message.id,
            parsed,
        )
        return Triage(
            urgency="high",
            category="other",
            rationale=f"schema-error fallback: {type(exc).__name__}: {exc!s}"[:240],
            payer_default="ambiguous",
            estimated_cost_band="unknown",
        )


def _message_payload(message: InboundMessage) -> dict[str, Any]:
    return {
        "id": message.id,
        "from": message.from_,
        "subject": message.subject,
        "body": message.body,
    }
