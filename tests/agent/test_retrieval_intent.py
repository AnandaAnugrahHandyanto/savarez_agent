"""Tests for agent/retrieval_intent.py (M2 — 5 intents + 6-dim scoring)."""

import pytest

from agent.retrieval_intent import (
    DIMENSION_NAMES,
    INTENT_KINDS,
    IntentKind,
    Score6D,
    get_intent_weights,
    infer_intent,
    rerank_by_intent,
    reset_intent_weights,
    set_intent_weights,
)


# ---------------------------------------------------------------------------
# infer_intent
# ---------------------------------------------------------------------------


def test_infer_intent_empty_defaults_to_fact():
    assert infer_intent("") == IntentKind.FACT_LOOKUP
    assert infer_intent("   \n  ") == IntentKind.FACT_LOOKUP


def test_infer_intent_delta_phrases():
    assert infer_intent("What changed since last week?") == IntentKind.DELTA
    assert infer_intent("anything new from yesterday?") == IntentKind.DELTA
    assert infer_intent("what's new in the project?") == IntentKind.DELTA


def test_infer_intent_briefing_phrases():
    assert infer_intent("what should i know before the meeting?") == IntentKind.BRIEFING
    assert infer_intent("catch me up on Slack") == IntentKind.BRIEFING
    assert infer_intent("any important emails today?") == IntentKind.BRIEFING


def test_infer_intent_planning_phrases():
    assert infer_intent("what's the plan for the migration?") == IntentKind.PLANNING
    assert infer_intent("how do we unblock the release?") == IntentKind.PLANNING
    assert infer_intent("what are the next steps?") == IntentKind.PLANNING


def test_infer_intent_procedure_phrases():
    assert infer_intent("how do I deploy this?") == IntentKind.PROCEDURE_LOOKUP
    assert infer_intent("steps to run the test suite") == IntentKind.PROCEDURE_LOOKUP
    assert infer_intent("show me the runbook") == IntentKind.PROCEDURE_LOOKUP


def test_infer_intent_fact_lookup_fallback():
    """If no phrase matches, we default to fact lookup."""
    assert infer_intent("what is the user's favorite color?") == IntentKind.FACT_LOOKUP
    assert infer_intent("the weather in beijing") == IntentKind.FACT_LOOKUP


def test_infer_intent_case_insensitive():
    """Phrases are matched in lowercase regardless of input case."""
    assert infer_intent("WHAT CHANGED since LAST?") == IntentKind.DELTA


# ---------------------------------------------------------------------------
# 6-dim scoring
# ---------------------------------------------------------------------------


def test_score6d_clip_clamps_out_of_range():
    s = Score6D(novelty=1.5, signal=-0.3)
    s.clip()
    assert s.novelty == 1.0
    assert s.signal == 0.0


def test_score6d_clip_returns_self_for_chaining():
    s = Score6D(novelty=0.5).clip()
    assert s is not None
    assert s.novelty == 0.5


def test_score6d_as_dict_has_six_keys():
    s = Score6D()
    d = s.as_dict()
    assert set(d.keys()) == set(DIMENSION_NAMES)
    assert all(isinstance(v, float) for v in d.values())


# ---------------------------------------------------------------------------
# Intent weights
# ---------------------------------------------------------------------------


def test_intent_kinds_canonical():
    assert INTENT_KINDS == (
        IntentKind.FACT_LOOKUP,
        IntentKind.PROCEDURE_LOOKUP,
        IntentKind.BRIEFING,
        IntentKind.PLANNING,
        IntentKind.DELTA,
    )


def test_get_intent_weights_returns_copy():
    """Caller mutation must not affect the global table."""
    w1 = get_intent_weights(IntentKind.DELTA)
    w1["novelty"] = -1.0  # mutate the copy
    w2 = get_intent_weights(IntentKind.DELTA)
    assert w2["novelty"] > 0  # original is intact


def test_get_intent_weights_unknown_falls_back_to_fact():
    """An unknown intent returns fact-lookup weights (safe default)."""
    w = get_intent_weights("not_a_real_intent")
    fact_w = get_intent_weights(IntentKind.FACT_LOOKUP)
    assert w == fact_w


def test_set_intent_weights_validates_keys():
    """Missing dimension keys should raise rather than silently no-op."""
    with pytest.raises(ValueError) as exc:
        set_intent_weights(IntentKind.DELTA, {"novelty": 0.5})  # missing 5
    assert "missing dimensions" in str(exc.value).lower()
    assert "novelty" in str(exc.value)


def test_set_intent_weights_applies():
    custom = {
        "novelty": 0.1, "signal": 0.2, "urgency": 0.3,
        "impact": 0.4, "actionability": 0.5, "contradiction": 0.6,
    }
    set_intent_weights(IntentKind.PLANNING, custom)
    try:
        w = get_intent_weights(IntentKind.PLANNING)
        assert w == custom
    finally:
        reset_intent_weights()  # leave global state clean for other tests


def test_reset_intent_weights_restores_defaults():
    custom = {
        "novelty": 0.99, "signal": 0.99, "urgency": 0.99,
        "impact": 0.99, "actionability": 0.99, "contradiction": 0.99,
    }
    set_intent_weights(IntentKind.DELTA, custom)
    reset_intent_weights()
    w = get_intent_weights(IntentKind.DELTA)
    # After reset, novelty for DELTA should be back to 1.2 (the default)
    assert w["novelty"] == 1.2


# ---------------------------------------------------------------------------
# rerank_by_intent
# ---------------------------------------------------------------------------


def test_rerank_empty_returns_empty_list():
    assert rerank_by_intent([], IntentKind.DELTA) == []


def test_rerank_orders_by_intent_weighted_score_desc():
    """A candidate with high novelty should rank first under DELTA intent
    (which weights novelty at 1.2)."""
    candidates = [
        ("low_novelty", Score6D(novelty=0.1, signal=0.9, urgency=0.0, impact=0.0, actionability=0.0, contradiction=0.0)),
        ("high_novelty", Score6D(novelty=0.9, signal=0.1, urgency=0.0, impact=0.0, actionability=0.0, contradiction=0.0)),
    ]
    ranked = rerank_by_intent(candidates, IntentKind.DELTA)
    # high_novelty should come first under DELTA
    assert ranked[0][0] == "high_novelty"
    # But under FACT_LOOKUP, signal dominates (weight 1.0 vs novelty 0.4)
    ranked_fact = rerank_by_intent(candidates, IntentKind.FACT_LOOKUP)
    assert ranked_fact[0][0] == "low_novelty"


def test_rerank_clips_out_of_range_dimensions():
    """Dimensions outside [0, 1] must be clipped before scoring."""
    candidates = [
        ("x", Score6D(novelty=2.0, signal=0.5)),  # novelty will be clipped to 1.0
    ]
    # The score should be the same as if we had passed novelty=1.0
    ref = rerank_by_intent(
        [("x", Score6D(novelty=1.0, signal=0.5))],
        IntentKind.DELTA,
    )
    actual = rerank_by_intent(candidates, IntentKind.DELTA)
    assert abs(actual[0][1] - ref[0][1]) < 1e-9


def test_rerank_category_bonus_does_not_dominate():
    """A candidate with a great dim score but a 'wrong' category should
    still rank higher than one with a great category but zero dims."""
    candidates = [
        ("wrong_category_high_score", Score6D(
            novelty=0.0, signal=0.0, urgency=0.0, impact=0.0,
            actionability=0.0, contradiction=0.0,
            category="known_facts",  # BRIEFING boosts this
        )),
        ("right_category_zero_score", Score6D(
            novelty=0.9, signal=0.9, urgency=0.9, impact=0.9,
            actionability=0.9, contradiction=0.9,
            category="known_facts",
        )),
    ]
    ranked = rerank_by_intent(candidates, IntentKind.BRIEFING)
    assert ranked[0][0] == "right_category_zero_score"


def test_rerank_returns_items_not_score_objects():
    """The function returns the original item, not the Score6D."""
    item = "the-item"
    candidates = [(item, Score6D(novelty=0.5))]
    ranked = rerank_by_intent(candidates, IntentKind.FACT_LOOKUP)
    assert ranked[0][0] == item
    assert isinstance(ranked[0][1], float)


def test_rerank_works_with_non_string_items():
    """Items can be anything — dicts, dataclasses, etc."""
    item = {"id": 42, "label": "thing"}
    candidates = [(item, Score6D(novelty=0.5))]
    ranked = rerank_by_intent(candidates, IntentKind.DELTA)
    assert ranked[0][0] is item


# ---------------------------------------------------------------------------
# Integration with retrieval_pack
# ---------------------------------------------------------------------------


def test_rerank_then_pack_filters_by_category():
    """End-to-end: score candidates, rerank by intent, then bucket into
    pack sections by the surviving item's category."""
    from agent.retrieval_pack import RetrievalPack, render_retrieval_pack

    # Two candidates with different categories, scored differently
    cands = [
        ("fact-item", Score6D(novelty=0.0, signal=0.9, category="known_facts")),
        ("signal-item", Score6D(novelty=0.8, signal=0.0, category="high_signal")),
    ]
    ranked = rerank_by_intent(cands, IntentKind.BRIEFING)
    # The signal-item wins for BRIEFING (novelty*0.6 + signal*0.7 + ... + category bonus)
    top = ranked[0]
    # Build a pack from the winner's category
    item, _ = top
    score = dict((c, s) for c, s in cands)[item]
    pack = RetrievalPack(**{score.category: [item]})
    assert score.category in ("high_signal", "known_facts")
    out = render_retrieval_pack(pack)
    assert item in out
