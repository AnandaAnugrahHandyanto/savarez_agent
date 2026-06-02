"""Tests for MiniMax auxiliary client URL normalization.

MiniMax and MiniMax-CN set inference_base_url to the /anthropic path.
For M-series models the /v1 endpoint returns 404 on /v1/chat/completions,
so the auxiliary client must preserve the /anthropic URL and let the
downstream ``_maybe_wrap_anthropic`` chokepoint route through the
Anthropic SDK via ``_endpoint_speaks_anthropic_messages``.  See #17387.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agent.auxiliary_client import _to_openai_base_url


class TestToOpenaiBaseUrl:
    def test_minimax_global_anthropic_suffix_preserved(self):
        # MiniMax /anthropic must NOT be rewritten to /v1 — the downstream
        # _maybe_wrap_anthropic chokepoint needs the original URL to detect
        # the Anthropic Messages surface and route through the Anthropic SDK.
        # M-series models on api.minimax.io return 404 on /v1/chat/completions.
        assert _to_openai_base_url("https://api.minimax.io/anthropic") == "https://api.minimax.io/anthropic"

    def test_minimax_cn_anthropic_suffix_preserved(self):
        # MiniMax-CN /anthropic must NOT be rewritten to /v1 — same reason
        # as the global endpoint, only the host differs.
        assert _to_openai_base_url("https://api.minimaxi.com/anthropic") == "https://api.minimaxi.com/anthropic"

    def test_trailing_slash_minimax_preserved(self):
        # Trailing slashes are stripped, but the /anthropic suffix stays.
        assert _to_openai_base_url("https://api.minimax.io/anthropic/") == "https://api.minimax.io/anthropic"

    def test_trailing_slash_minimax_cn_preserved(self):
        assert _to_openai_base_url("https://api.minimaxi.com/anthropic/") == "https://api.minimaxi.com/anthropic"

    def test_v1_url_unchanged(self):
        assert _to_openai_base_url("https://api.openai.com/v1") == "https://api.openai.com/v1"

    def test_openrouter_url_unchanged(self):
        assert _to_openai_base_url("https://openrouter.ai/api/v1") == "https://openrouter.ai/api/v1"

    def test_empty_url_returns_empty(self):
        # Defensive: empty / None-ish input should not raise.
        assert _to_openai_base_url("") == ""

    def test_zai_anthropic_rewritten_to_paas_v4(self):
        # ZAI's /anthropic must still be rewritten to /api/paas/v4 — it is
        # the only Anthropic-style provider that has a working OpenAI-wire
        # sibling.  Regression guard: ensure the new MiniMax exception
        # doesn't accidentally swallow the ZAI branch.
        assert _to_openai_base_url("https://open.bigmodel.cn/api/anthropic") == "https://open.bigmodel.cn/api/paas/v4"

    def test_generic_anthropic_url_rewritten_to_v1(self):
        # Other /anthropic endpoints (LiteLLM proxies, Zhipu GLM on non-`bigmodel`
        # hosts, etc.) still get rewritten to /v1 — only MiniMax hosts are exempted.
        assert _to_openai_base_url("https://example.com/anthropic") == "https://example.com/v1"


class TestEndToEndAnthropicRouting:
    """Verify that preserved /anthropic URLs are detected by the downstream
    Anthropic-transport detection function, so the call ends up on the
    Anthropic SDK wire rather than the OpenAI wire."""

    def test_preserved_minimax_cn_url_detected_as_anthropic(self):
        from agent.auxiliary_client import _endpoint_speaks_anthropic_messages
        # After _to_openai_base_url preserves the /anthropic suffix, the
        # detection helper must still recognise it as Anthropic-Messages.
        preserved = _to_openai_base_url("https://api.minimaxi.com/anthropic")
        assert _endpoint_speaks_anthropic_messages(preserved) is True

    def test_preserved_minimax_global_url_detected_as_anthropic(self):
        from agent.auxiliary_client import _endpoint_speaks_anthropic_messages
        preserved = _to_openai_base_url("https://api.minimax.io/anthropic")
        assert _endpoint_speaks_anthropic_messages(preserved) is True
