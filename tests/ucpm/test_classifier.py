"""P-01 classifier unit tests."""

from __future__ import annotations

from datetime import datetime, timezone

from hermes_agent.loops.classifier import classify
from hermes_agent.loops.schemas import InboundMessage

from tests.ucpm.conftest import make_fake_llm


def _msg(**overrides) -> InboundMessage:
    base = {
        "id": "msg-test",
        "received_at": datetime(2026, 5, 5, 15, 30, tzinfo=timezone.utc),
        "channel": "email",
        "from": "tenant@example.com",
        "to": "manager@example.com",
        "subject": "Test",
        "body": "Test",
        "attachments": [],
    }
    base.update(overrides)
    return InboundMessage.model_validate(base)


def test_maintenance_classification(tiny_sop_text):
    llm = make_fake_llm(
        {
            "classify": [
                {
                    "intent": "maintenance",
                    "tenant_slug": "beautiful-minds-a-101",
                    "confidence": 0.95,
                    "rationale": "AC failure keyword.",
                }
            ]
        }
    )
    result = classify(
        _msg(subject="AC not cooling", body="AC blowing warm air"),
        sop_text=tiny_sop_text,
        company_context="company: test\n",
        llm=llm,
    )
    assert result.intent == "maintenance"
    assert result.tenant_slug == "beautiful-minds-a-101"
    assert result.confidence == 0.95


def test_payment_classification(tiny_sop_text):
    llm = make_fake_llm(
        {
            "classify": [
                {
                    "intent": "payment",
                    "tenant_slug": None,
                    "confidence": 0.9,
                    "rationale": "Asks about balance.",
                }
            ]
        }
    )
    result = classify(
        _msg(subject="balance question", body="What's my May balance?"),
        sop_text=tiny_sop_text,
        company_context="company: test\n",
        llm=llm,
    )
    assert result.intent == "payment"
    assert result.tenant_slug is None


def test_legal_classification(tiny_sop_text):
    llm = make_fake_llm(
        {
            "classify": [
                {
                    "intent": "legal",
                    "tenant_slug": None,
                    "confidence": 0.99,
                    "rationale": "Tenant cited an attorney.",
                }
            ]
        }
    )
    result = classify(
        _msg(body="My attorney will be in touch about ADA compliance."),
        sop_text=tiny_sop_text,
        company_context="company: test\n",
        llm=llm,
    )
    assert result.intent == "legal"


def test_classifier_falls_back_to_unclassified_on_bad_json(tiny_sop_text):
    """If the LLM returns malformed JSON the classifier must NOT crash —
    it must return `unclassified` so the loop's P-09 path picks it up."""

    class _BadAnthropic:
        class _Messages:
            def create(self, **kwargs):
                # Return raw text that isn't JSON.
                class _Block:
                    text = "I'm not JSON, sorry."

                class _Resp:
                    content = [_Block()]
                    usage = {}

                return _Resp()

        messages = _Messages()

    from hermes_agent.loops.llm_client import LlmClient

    llm = LlmClient(client=_BadAnthropic(), model="fake")
    result = classify(
        _msg(),
        sop_text=tiny_sop_text,
        company_context="company: test\n",
        llm=llm,
    )
    assert result.intent == "unclassified"
    assert result.confidence == 0.0
    assert "classifier-error" in result.rationale or "schema-error" in result.rationale


def test_classifier_falls_back_on_invalid_intent(tiny_sop_text):
    """Schema mismatch (intent not in the allowed set) must not crash."""
    llm = make_fake_llm(
        {
            "classify": [
                {
                    "intent": "spaghetti",  # not in Intent literal
                    "tenant_slug": None,
                    "confidence": 0.5,
                    "rationale": "weird",
                }
            ]
        }
    )
    result = classify(
        _msg(),
        sop_text=tiny_sop_text,
        company_context="company: test\n",
        llm=llm,
    )
    assert result.intent == "unclassified"
