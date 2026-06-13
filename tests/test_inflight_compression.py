"""Unit tests for the mid-turn in-flight compression safety valve.

``_maybe_inflight_compress`` complements the once-per-turn preflight
compression: it re-checks context size *inside* the tool-calling loop, but
only once the request nears the model's real context window (an emergency
fraction, not the 50% preflight threshold), so normal turns keep their
prompt-cache prefix and only a turn that would otherwise overflow pays the
mid-turn cache bust.
"""

from agent.conversation_loop import _maybe_inflight_compress


class FakeCompressor:
    def __init__(self, context_length, last_prompt_tokens, *, block=False):
        self.context_length = context_length
        self.last_prompt_tokens = last_prompt_tokens
        self.threshold_tokens = int(context_length * 0.5)  # preflight threshold
        self.protect_first_n = 1
        self.protect_last_n = 1
        self._block = block

    def should_compress(self, tokens):
        # Mirrors the real anti-thrash gate: above threshold unless backed off.
        return tokens >= self.threshold_tokens and not self._block


class FakeAgent:
    def __init__(self, compressor, *, enabled=True):
        self.compression_enabled = enabled
        self.context_compressor = compressor
        self.tools = None
        self.compress_calls = 0
        # Pre-set to non-zero so we can assert the helper resets them.
        self._empty_content_retries = 7
        self._thinking_prefill_retries = 7
        self._last_content_with_tools = "stale"
        self._last_content_tools_all_housekeeping = True
        self._mute_post_response = True

    def _emit_status(self, *_a, **_k):
        pass

    def _compress_context(self, messages, system_message, *, approx_tokens=None, task_id="default"):
        self.compress_calls += 1
        # Shrink hard: keep the first message and the last two.
        return [messages[0]] + messages[-2:], "compressed-sys"


def _msgs(n=12):
    return [{"role": "user" if i % 2 else "assistant", "content": f"message {i}"} for i in range(n)]


def test_fires_when_request_nears_context_limit():
    comp = FakeCompressor(context_length=40000, last_prompt_tokens=36000)  # > 0.85*40000
    agent = FakeAgent(comp)
    msgs, asp, fired = _maybe_inflight_compress(
        agent, _msgs(), "sys", "orig-sys", "default", api_call_count=3,
    )
    assert fired is True
    assert agent.compress_calls == 1
    assert len(msgs) < 12
    assert asp == "compressed-sys"
    # post-compression resets mirror preflight
    assert agent._empty_content_retries == 0
    assert agent._thinking_prefill_retries == 0
    assert agent._last_content_with_tools is None


def test_skips_on_first_iteration():
    comp = FakeCompressor(context_length=40000, last_prompt_tokens=39000)
    agent = FakeAgent(comp)
    msgs, asp, fired = _maybe_inflight_compress(
        agent, _msgs(), "sys", "orig-sys", "default", api_call_count=1,
    )
    assert fired is False
    assert agent.compress_calls == 0
    assert asp == "orig-sys"


def test_skips_below_emergency_even_if_above_preflight_threshold():
    # 24000 is above the 20000 preflight threshold but below the 34000 (85%)
    # emergency line — preflight handles this between turns, not the valve.
    comp = FakeCompressor(context_length=40000, last_prompt_tokens=24000)
    agent = FakeAgent(comp)
    _msgs_out, _asp, fired = _maybe_inflight_compress(
        agent, _msgs(), "sys", "orig-sys", "default", api_call_count=5,
    )
    assert fired is False
    assert agent.compress_calls == 0


def test_skips_when_compression_disabled():
    comp = FakeCompressor(context_length=40000, last_prompt_tokens=39000)
    agent = FakeAgent(comp, enabled=False)
    _m, _a, fired = _maybe_inflight_compress(
        agent, _msgs(), "sys", "orig-sys", "default", api_call_count=3,
    )
    assert fired is False
    assert agent.compress_calls == 0


def test_anti_thrash_blocks_repeat_compaction():
    comp = FakeCompressor(context_length=40000, last_prompt_tokens=39000, block=True)
    agent = FakeAgent(comp)
    _m, _a, fired = _maybe_inflight_compress(
        agent, _msgs(), "sys", "orig-sys", "default", api_call_count=4,
    )
    assert fired is False
    assert agent.compress_calls == 0


def test_emergency_fraction_env_override(monkeypatch):
    # Lower the emergency line to 50% — now 24000 (60% of 40000) trips it.
    monkeypatch.setenv("HERMES_INFLIGHT_COMPRESS_FRACTION", "0.5")
    comp = FakeCompressor(context_length=40000, last_prompt_tokens=24000)
    agent = FakeAgent(comp)
    _m, _a, fired = _maybe_inflight_compress(
        agent, _msgs(), "sys", "orig-sys", "default", api_call_count=3,
    )
    assert fired is True
    assert agent.compress_calls == 1
