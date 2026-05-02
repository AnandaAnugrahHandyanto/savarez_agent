# tests/agent/benchmarks/test_tier1_token_efficiency.py
from agent.model_metadata import estimate_messages_tokens_rough
from tests.agent.benchmarks._report import record
from tests.agent.benchmarks.fixture_builders import make_loop_session


def test_1_1_dedup_friendly_loop_saves_tokens(compressor_pair, stub_summarizer):
    """30 iterations of read+patch on 3 paths = 90 redundant tool results.
    Pass 1.5 should supersede the older reads/patches; net token count
    after compaction should drop materially."""
    baseline, with_flags = compressor_pair
    msgs = make_loop_session(n_iterations=30, chars_per_read=4_000)
    pre_tokens = estimate_messages_tokens_rough(msgs)

    out_b = baseline.compress(msgs.copy(), current_tokens=pre_tokens)
    out_c = with_flags.compress(msgs.copy(), current_tokens=pre_tokens)

    tk_b = estimate_messages_tokens_rough(out_b)
    tk_c = estimate_messages_tokens_rough(out_c)
    record("1.1", "post_compact_tokens", tk_b, tk_c, "tok")
    record("1.1", "op_deduped_count",
           getattr(baseline, "_last_op_deduped", 0),
           getattr(with_flags, "_last_op_deduped", 0), "ops")

    # Acceptance: candidate ≤ 0.85 × baseline (≥ 15% improvement)
    assert tk_c <= 0.85 * tk_b, (
        f"Expected ≥15% token reduction; got {tk_c}/{tk_b} = {tk_c/tk_b:.2%}"
    )
    # And the dedup pass actually fired
    assert with_flags._last_op_deduped > 0


def test_1_2_neutral_session_does_not_lose_information(compressor_pair, stub_summarizer):
    """No resource reuse → dedup should not fire. Token counts within ±5%.
    A larger drop would indicate we deleted information that wasn't redundant."""
    from tests.agent.benchmarks.fixture_builders import make_neutral_session
    baseline, with_flags = compressor_pair
    msgs = make_neutral_session(n_turns=40, chars_per_turn=2_000)
    pre = estimate_messages_tokens_rough(msgs)

    out_b = baseline.compress(msgs.copy(), current_tokens=pre)
    out_c = with_flags.compress(msgs.copy(), current_tokens=pre)
    tk_b = estimate_messages_tokens_rough(out_b)
    tk_c = estimate_messages_tokens_rough(out_c)
    record("1.2", "post_compact_tokens", tk_b, tk_c, "tok")

    # ratio in [0.95, 1.05]
    ratio = tk_c / tk_b if tk_b else 1.0
    assert 0.95 <= ratio <= 1.05, (
        f"Neutral session ratio {ratio:.3f} outside [0.95, 1.05] — "
        f"unexpected info loss or bloat"
    )
