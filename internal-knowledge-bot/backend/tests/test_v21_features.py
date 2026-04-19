from app.ingest import chunk_text
from app.policy import evaluate_handoff_decision


def test_chunk_text_returns_offsets_and_section_labels():
    text = "# Intro\nHello world\n\n## Details\nMore details here"
    chunks = list(chunk_text(text, size=20, overlap=5))
    assert len(chunks) >= 2
    first = chunks[0]
    assert isinstance(first[0], str)
    assert isinstance(first[1], int)
    assert isinstance(first[2], int)
    assert isinstance(first[3], str)
    assert first[2] > first[1]


def test_policy_rule_can_force_handoff():
    decision = evaluate_handoff_decision(
        question="normal request",
        confidence=0.99,
        min_confidence=0.2,
        force_keywords=[],
        rules=[
            {
                "name": "confidential-approval",
                "field": "classification",
                "op": "equals",
                "value": "confidential",
                "action": "handoff",
                "reason": "Confidential requires approval",
                "enabled": True,
            }
        ],
        classification="confidential",
        role="employee",
    )
    assert decision.handoff_recommended is True
    assert "confidential-approval" in decision.matched_rules
    assert decision.final_action == "handoff"
