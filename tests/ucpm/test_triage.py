"""P-02 triage unit tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hermes_agent.loops.schemas import InboundMessage
from hermes_agent.loops.triage import triage as run_triage

from tests.ucpm.conftest import make_fake_llm


def _msg(body: str, subject: str = "") -> InboundMessage:
    return InboundMessage.model_validate(
        {
            "id": "msg-test",
            "received_at": datetime(2026, 5, 5, 8, 0, tzinfo=timezone.utc),
            "channel": "email",
            "from": "tenant@example.com",
            "to": "manager@example.com",
            "subject": subject,
            "body": body,
            "attachments": [],
        }
    )


@pytest.mark.parametrize(
    "scripted, expected_urgency",
    [
        (
            {
                "urgency": "emergency",
                "category": "plumbing",
                "rationale": "active flood",
                "payer_default": "landlord",
                "estimated_cost_band": "501-2000",
            },
            "emergency",
        ),
        (
            {
                "urgency": "high",
                "category": "hvac",
                "rationale": "AC down, business hours",
                "payer_default": "landlord",
                "estimated_cost_band": "<=500",
            },
            "high",
        ),
        (
            {
                "urgency": "normal",
                "category": "plumbing",
                "rationale": "slow drain",
                "payer_default": "landlord",
                "estimated_cost_band": "<=500",
            },
            "normal",
        ),
        (
            {
                "urgency": "scheduled",
                "category": "hvac",
                "rationale": "filter change request",
                "payer_default": "landlord",
                "estimated_cost_band": "<=500",
            },
            "scheduled",
        ),
    ],
)
def test_triage_urgency_levels(tiny_sop_text, scripted, expected_urgency):
    llm = make_fake_llm({"triage": [scripted]})
    result = run_triage(
        _msg("anything"),
        sop_text=tiny_sop_text,
        company_context="company: test\n",
        llm=llm,
    )
    assert result.urgency == expected_urgency
    assert result.category == scripted["category"]


def test_triage_falls_back_on_invalid_urgency(tiny_sop_text):
    """A bad urgency value must not crash the loop — must default to high
    so the operator surfaces it (safer than dropping to normal silently)."""
    llm = make_fake_llm(
        {
            "triage": [
                {
                    "urgency": "kinda-bad",  # invalid
                    "category": "hvac",
                    "rationale": "x",
                    "payer_default": "landlord",
                    "estimated_cost_band": "<=500",
                }
            ]
        }
    )
    result = run_triage(
        _msg("AC down"),
        sop_text=tiny_sop_text,
        company_context="company: test\n",
        llm=llm,
    )
    assert result.urgency == "high"
    assert "schema-error" in result.rationale


def test_triage_falls_back_on_llm_exception(tiny_sop_text):
    class _BoomAnthropic:
        class _Messages:
            def create(self, **kwargs):
                raise RuntimeError("API exploded")

        messages = _Messages()

    from hermes_agent.loops.llm_client import LlmClient

    llm = LlmClient(client=_BoomAnthropic(), model="fake")
    result = run_triage(
        _msg("AC down"),
        sop_text=tiny_sop_text,
        company_context="company: test\n",
        llm=llm,
    )
    assert result.urgency == "high"
    assert "triage-error" in result.rationale
