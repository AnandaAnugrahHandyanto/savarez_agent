from app.policy import evaluate_handoff_decision, matched_keywords, redact_pii


def test_matched_keywords_detects_force_terms():
    hits = matched_keywords("We have a legal incident and possible breach", ["legal", "breach", "refund"])
    assert hits == ["legal", "breach"]


def test_evaluate_handoff_triggers_on_low_confidence():
    decision = evaluate_handoff_decision(
        question="simple question",
        confidence=0.10,
        min_confidence=0.30,
        force_keywords=["legal"],
    )
    assert decision.handoff_recommended is True
    assert decision.matched_keywords == []
    assert decision.final_action in {"allow", "handoff"}


def test_redact_pii_masks_email_and_phone():
    txt = "Contact alice@company.com or +358 40 123 4567"
    redacted = redact_pii(txt)
    assert "alice@company.com" not in redacted
    assert "+358 40 123 4567" not in redacted
    assert "[REDACTED_EMAIL]" in redacted
    assert "[REDACTED_PHONE]" in redacted
