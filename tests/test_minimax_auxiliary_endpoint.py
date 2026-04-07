"""Tests for MiniMax auxiliary client URL normalization (issue #5781).

MiniMax exposes two API surfaces on different URL paths:
  - /anthropic  — Anthropic Messages API (used by the main agent loop)
  - /v1         — OpenAI-compatible chat completions (used by auxiliary client)

The auxiliary client builds an OpenAI() instance with the provider's
inference_base_url, which for MiniMax is ``.../anthropic``.  Without
normalization the OpenAI SDK appends ``/chat/completions`` and every
auxiliary request lands on ``.../anthropic/chat/completions`` — a 404.

_to_openai_base_url() strips the ``/anthropic`` suffix and replaces it with
``/v1`` so the auxiliary client always points at the right path.
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.auxiliary_client import _to_openai_base_url


class TestToOpenaiBaseUrl:
    def test_minimax_global_anthropic_suffix_replaced(self):
        assert _to_openai_base_url("https://api.minimax.io/anthropic") == "https://api.minimax.io/v1"

    def test_minimax_cn_anthropic_suffix_replaced(self):
        assert _to_openai_base_url("https://api.minimaxi.com/anthropic") == "https://api.minimaxi.com/v1"

    def test_trailing_slash_stripped_before_replace(self):
        assert _to_openai_base_url("https://api.minimax.io/anthropic/") == "https://api.minimax.io/v1"

    def test_v1_url_unchanged(self):
        assert _to_openai_base_url("https://api.openai.com/v1") == "https://api.openai.com/v1"

    def test_openrouter_url_unchanged(self):
        assert _to_openai_base_url("https://openrouter.ai/api/v1") == "https://openrouter.ai/api/v1"

    def test_url_with_anthropic_in_domain_unchanged(self):
        # ``/anthropic`` must appear as a path suffix, not in the domain
        assert _to_openai_base_url("https://api.anthropic.com") == "https://api.anthropic.com"

    def test_url_with_anthropic_subpath_unchanged(self):
        # Only strip a terminal ``/anthropic``, not a mid-path segment
        assert _to_openai_base_url("https://example.com/anthropic/extra") == "https://example.com/anthropic/extra"

    def test_empty_string(self):
        assert _to_openai_base_url("") == ""

    def test_none_equivalent_empty_string(self):
        # Callers may pass None when a URL is unset
        assert _to_openai_base_url(None) == ""
