"""Tests for the ResponsesApiTransport (Codex)."""

import json
import pytest
from types import SimpleNamespace

from agent.transports import get_transport
from agent.transports.types import NormalizedResponse, ToolCall


@pytest.fixture
def transport():
    import agent.transports.codex  # noqa: F401
    return get_transport("codex_responses")


class TestCodexTransportBasic:

    def test_api_mode(self, transport):
        assert transport.api_mode == "codex_responses"

    def test_registered_on_import(self, transport):
        assert transport is not None

    def test_convert_tools(self, transport):
        tools = [{
            "type": "function",
            "function": {
                "name": "terminal",
                "description": "Run a command",
                "parameters": {"type": "object", "properties": {"command": {"type": "string"}}},
            }
        }]
        result = transport.convert_tools(tools)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["name"] == "terminal"


class TestCodexBuildKwargs:

    def test_basic_kwargs(self, transport):
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        kw = transport.build_kwargs(
            model="gpt-5.4",
            messages=messages,
            tools=[],
        )
        assert kw["model"] == "gpt-5.4"
        assert kw["instructions"] == "You are helpful."
        assert "input" in kw
        assert kw["store"] is False

    def test_system_extracted_from_messages(self, transport):
        messages = [
            {"role": "system", "content": "Custom system prompt"},
            {"role": "user", "content": "Hi"},
        ]
        kw = transport.build_kwargs(model="gpt-5.4", messages=messages, tools=[])
        assert kw["instructions"] == "Custom system prompt"

    def test_no_system_uses_default(self, transport):
        messages = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(model="gpt-5.4", messages=messages, tools=[])
        assert kw["instructions"]  # should be non-empty default

    def test_reasoning_config(self, transport):
        messages = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="gpt-5.4", messages=messages, tools=[],
            reasoning_config={"effort": "high"},
        )
        assert kw.get("reasoning", {}).get("effort") == "high"

    def test_reasoning_disabled(self, transport):
        messages = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="gpt-5.4", messages=messages, tools=[],
            reasoning_config={"enabled": False},
        )
        assert "reasoning" not in kw or kw.get("include") == []

    def test_session_id_sets_cache_key(self, transport):
        messages = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="gpt-5.4", messages=messages, tools=[],
            session_id="test-session-123",
        )
        assert kw.get("prompt_cache_key") == "test-session-123"

    def test_github_responses_no_cache_key(self, transport):
        messages = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="gpt-5.4", messages=messages, tools=[],
            session_id="test-session",
            is_github_responses=True,
        )
        assert "prompt_cache_key" not in kw

    def test_xai_responses_sends_cache_key_via_extra_body(self, transport):
        """xAI's Responses API documents ``prompt_cache_key`` as the
        body-level cache-routing key (the ``x-grok-conv-id`` header is
        Chat-Completions-only). Passing it via ``extra_body`` is robust
        against openai SDK builds whose ``Responses.stream()`` kwarg
        signature ever drops the field — the body field still serializes
        and reaches xAI either way. The ``x-grok-conv-id`` header is kept
        as a belt-and-braces fallback so cache routing survives even
        when the body field would be stripped by an intermediate proxy.
        Ref: https://docs.x.ai/developers/advanced-api-usage/prompt-caching/maximizing-cache-hits
        """
        messages = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="grok-4.3", messages=messages, tools=[],
            session_id="conv-xai-1",
            is_xai_responses=True,
        )
        assert "prompt_cache_key" not in kw
        assert kw.get("extra_body", {}).get("prompt_cache_key") == "conv-xai-1"
        assert kw.get("extra_headers", {}).get("x-grok-conv-id") == "conv-xai-1"

    def test_xai_responses_extra_body_preserves_caller_fields(self, transport):
        """When the caller already supplies ``extra_body`` (e.g. via
        request_overrides), the xAI cache-key injection must merge into
        the existing dict instead of overwriting it. Caller-supplied
        ``prompt_cache_key`` wins (setdefault semantics) so user overrides
        aren't silently clobbered by the transport."""
        messages = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="grok-4.3", messages=messages, tools=[],
            session_id="conv-xai-1",
            is_xai_responses=True,
            request_overrides={"extra_body": {"prompt_cache_key": "caller-override", "other_field": 42}},
        )
        eb = kw.get("extra_body", {})
        assert eb.get("prompt_cache_key") == "caller-override"
        assert eb.get("other_field") == 42

    def test_max_tokens(self, transport):
        messages = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="gpt-5.4", messages=messages, tools=[],
            max_tokens=4096,
        )
        assert kw.get("max_output_tokens") == 4096

    def test_codex_backend_no_max_output_tokens(self, transport):
        messages = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="gpt-5.4", messages=messages, tools=[],
            max_tokens=4096,
            is_codex_backend=True,
        )
        assert "max_output_tokens" not in kw

    def test_xai_headers(self, transport):
        messages = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="grok-3", messages=messages, tools=[],
            session_id="conv-123",
            is_xai_responses=True,
        )
        assert kw.get("extra_headers", {}).get("x-grok-conv-id") == "conv-123"

    def test_xai_headers_preserve_request_override_headers(self, transport):
        messages = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="grok-3", messages=messages, tools=[],
            session_id="conv-123",
            is_xai_responses=True,
            request_overrides={"extra_headers": {"X-Test": "1", "X-Trace": "abc"}},
        )
        assert kw.get("extra_headers") == {
            "X-Test": "1",
            "X-Trace": "abc",
            "x-grok-conv-id": "conv-123",
        }

    def test_minimal_effort_clamped(self, transport):
        messages = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="gpt-5.4", messages=messages, tools=[],
            reasoning_config={"effort": "minimal"},
        )
        # "minimal" should be clamped to "low"
        assert kw.get("reasoning", {}).get("effort") == "low"

    def test_xai_reasoning_effort_passed(self, transport):
        messages = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="grok-4.3", messages=messages, tools=[],
            is_xai_responses=True,
            reasoning_config={"effort": "high"},
        )
        # xAI Responses receives reasoning.effort on the allowlisted models.
        assert kw.get("reasoning") == {"effort": "high"}
        # As of May 2026 we deliberately do NOT request
        # reasoning.encrypted_content back from xAI — the OAuth/SuperGrok
        # surface rejects replayed encrypted reasoning items on turn 2+
        # (the multi-turn "Expected to have received response.created
        # before error" failure).  Grok still reasons natively each turn;
        # we just don't try to thread the prior turn's encrypted blob back
        # in.  See tests/run_agent/test_codex_xai_oauth_recovery.py.
        assert "reasoning.encrypted_content" not in kw.get("include", [])

    def test_xai_reasoning_disabled_no_reasoning_key(self, transport):
        messages = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="grok-4.3", messages=messages, tools=[],
            is_xai_responses=True,
            reasoning_config={"enabled": False},
        )
        # When reasoning is disabled, do not send the reasoning key at all.
        # include is also absent: no reasoning tokens are generated, nothing to suppress.
        assert "reasoning" not in kw
        assert "include" not in kw

    def test_xai_minimal_effort_clamped(self, transport):
        messages = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="grok-4.3", messages=messages, tools=[],
            is_xai_responses=True,
            reasoning_config={"effort": "minimal"},
        )
        # "minimal" should be clamped to "low" for xAI as well
        assert kw.get("reasoning", {}).get("effort") == "low"

    # --- Grok reasoning-effort capability allowlist ---
    # api.x.ai 400s with "Model X does not support parameter reasoningEffort"
    # on grok-4 / grok-4-fast / grok-3 / grok-code-fast / grok-4.20-0309-*.
    # Those models reason natively but don't expose the dial. The transport
    # must omit the `reasoning` key for them.  As of May 2026 we also no
    # longer request ``reasoning.encrypted_content`` back from xAI on ANY
    # model — see test_xai_reasoning_effort_passed for the rationale.

    def test_xai_grok_4_omits_reasoning_effort(self, transport):
        """grok-4 / grok-4-0709 reject reasoning.effort with HTTP 400."""
        messages = [{"role": "user", "content": "Hi"}]
        for model in ("grok-4", "grok-4-0709"):
            kw = transport.build_kwargs(
                model=model, messages=messages, tools=[],
                is_xai_responses=True,
                reasoning_config={"effort": "high"},
            )
            assert "reasoning" not in kw, (
                f"{model} must not receive a reasoning key (xAI rejects it)"
            )
            # We no longer ask xAI for encrypted_content back (see comment
            # above) — verify the include list is empty.
            assert "reasoning.encrypted_content" not in kw.get("include", [])

    def test_xai_grok_4_fast_omits_reasoning_effort(self, transport):
        """grok-4-fast and grok-4-1-fast variants reject reasoning.effort."""
        messages = [{"role": "user", "content": "Hi"}]
        for model in (
            "grok-4-fast-reasoning",
            "grok-4-fast-non-reasoning",
            "grok-4-1-fast-reasoning",
            "grok-4-1-fast-non-reasoning",
        ):
            kw = transport.build_kwargs(
                model=model, messages=messages, tools=[],
                is_xai_responses=True,
                reasoning_config={"effort": "low"},
            )
            assert "reasoning" not in kw, (
                f"{model} must not receive a reasoning key (xAI rejects it)"
            )
            assert kw.get("include") == []

    def test_xai_grok_3_non_mini_omits_reasoning_effort(self, transport):
        """Plain grok-3 rejects reasoning.effort."""
        messages = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="grok-3", messages=messages, tools=[],
            is_xai_responses=True,
            reasoning_config={"effort": "medium"},
        )
        assert "reasoning" not in kw
        assert kw.get("include") == []

    def test_xai_grok_3_mini_keeps_reasoning_effort(self, transport):
        """grok-3-mini and -fast variants no longer accept reasoning.effort per
        official xAI docs (only grok-4.3 and grok-4.20-multi-agent are listed)."""
        messages = [{"role": "user", "content": "Hi"}]
        for model in ("grok-3-mini", "grok-3-mini-fast"):
            kw = transport.build_kwargs(
                model=model, messages=messages, tools=[],
                is_xai_responses=True,
                reasoning_config={"effort": "high"},
            )
            assert "reasoning" not in kw
            assert kw.get("include") == []

    def test_xai_grok_4_20_0309_variants_omit_reasoning_effort(self, transport):
        """grok-4.20-0309-(non-)reasoning reject the effort dial.

        Counterintuitively, only grok-4.20-multi-agent-0309 accepts it.
        """
        messages = [{"role": "user", "content": "Hi"}]
        for model in ("grok-4.20-0309-reasoning", "grok-4.20-0309-non-reasoning"):
            kw = transport.build_kwargs(
                model=model, messages=messages, tools=[],
                is_xai_responses=True,
                reasoning_config={"effort": "high"},
            )
            assert "reasoning" not in kw, f"{model} must not receive reasoning"
            assert kw.get("include") == []

    def test_xai_grok_code_fast_omits_reasoning_effort(self, transport):
        """grok-code-fast-1 rejects reasoning.effort."""
        messages = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="grok-code-fast-1", messages=messages, tools=[],
            is_xai_responses=True,
            reasoning_config={"effort": "high"},
        )
        assert "reasoning" not in kw
        assert kw.get("include") == []


class TestCodexXaiReasoningEffortGating:
    """Regression coverage for issue #23088.

    Background: xAI's Responses API rejects ``reasoning.effort`` with HTTP 400
    on most Grok models (e.g. ``grok-4-1-fast``). Only ``grok-4.3`` and
    ``grok-4.20-multi-agent`` advertise support per xAI's docs. The transport
    must drop both ``reasoning`` and ``reasoning.encrypted_content`` (include)
    from the request when the selected model does not accept the effort dial.
    The ``x-grok-conv-id`` header and other xAI-specific fields are unaffected.

    These tests probe BEHAVIOR through ``build_kwargs`` using representative
    model names. They deliberately avoid importing the internal allowlist
    constant so the suite remains stable as the allowlist grows.
    """

    def _xai_kwargs(self, transport, model, reasoning_config=None, **extra):
        return transport.build_kwargs(
            model=model,
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            is_xai_responses=True,
            reasoning_config=reasoning_config,
            **extra,
        )

    # ── Bug-repro / regression guard ─────────────────────────────────────

    def test_grok_4_1_fast_drops_reasoning_when_effort_configured(self, transport):
        """Issue #23088 literal repro: this MUST fail if the fix is reverted."""
        kw = self._xai_kwargs(
            transport, "grok-4-1-fast", reasoning_config={"effort": "high"},
        )
        assert "reasoning" not in kw

    def test_grok_4_1_fast_drops_reasoning_even_when_explicitly_enabled(self, transport):
        """Capability beats user intent — even an explicit enabled+effort drops."""
        kw = self._xai_kwargs(
            transport,
            "grok-4-1-fast",
            reasoning_config={"enabled": True, "effort": "high"},
        )
        assert "reasoning" not in kw

    def test_grok_4_drops_reasoning(self, transport):
        """grok-4 (base) is documented as rejecting reasoning.effort."""
        kw = self._xai_kwargs(
            transport, "grok-4", reasoning_config={"effort": "medium"},
        )
        assert "reasoning" not in kw

    # ── Allowlist happy paths (both buckets) ─────────────────────────────

    def test_grok_4_3_keeps_reasoning(self, transport):
        kw = self._xai_kwargs(
            transport, "grok-4.3", reasoning_config={"effort": "high"},
        )
        assert kw.get("reasoning") == {"effort": "high"}
        # Bare allowlist token (no suffix) also works at a lower effort level.
        kw_low = self._xai_kwargs(
            transport, "grok-4.3", reasoning_config={"effort": "low"},
        )
        assert kw_low.get("reasoning") == {"effort": "low"}

    def test_grok_4_20_multi_agent_keeps_reasoning(self, transport):
        """Real model id ``grok-4.20-multi-agent-0309`` (substring match)."""
        kw = self._xai_kwargs(
            transport, "grok-4.20-multi-agent-0309",
            reasoning_config={"effort": "medium"},
        )
        assert kw.get("reasoning") == {"effort": "medium"}

    def test_allowlisted_model_minimal_effort_still_clamped(self, transport):
        """Effort clamping must apply on the allowlisted path too."""
        kw = self._xai_kwargs(
            transport, "grok-4.3", reasoning_config={"effort": "minimal"},
        )
        assert kw.get("reasoning") == {"effort": "low"}

    # ── ``include`` field invariants ─────────────────────────────────────

    def test_include_dropped_when_effort_gated_off(self, transport):
        """When the model doesn't accept ``reasoning.effort``, the current fix
        also drops the ``reasoning.encrypted_content`` include — both keys
        move together in/out of the kwargs dict. This test pins that
        coupling so a future change to decouple them is intentional, not
        accidental, and so the suite catches the inverse mistake (sending
        only one of the pair, or sending an empty include list).
        """
        kw = self._xai_kwargs(
            transport, "grok-4-1-fast", reasoning_config={"effort": "high"},
        )
        assert "reasoning" not in kw
        assert kw.get("include") == []

    def test_include_empty_for_allowlisted_model(self, transport):
        kw = self._xai_kwargs(
            transport, "grok-4.3", reasoning_config={"effort": "high"},
        )
        assert kw.get("include") == []

    def test_no_reasoning_or_encrypted_include_when_disabled_on_unsupported(self, transport):
        kw = self._xai_kwargs(
            transport, "grok-4-1-fast", reasoning_config={"enabled": False},
        )
        assert "reasoning" not in kw
        assert "reasoning.encrypted_content" not in kw.get("include", [])

    def test_no_reasoning_or_encrypted_include_when_disabled_on_supported(self, transport):
        kw = self._xai_kwargs(
            transport, "grok-4.3", reasoning_config={"enabled": False},
        )
        assert "reasoning" not in kw
        assert "reasoning.encrypted_content" not in kw.get("include", [])

    # ── Defaults (no reasoning_config supplied) ──────────────────────────

    def test_unsupported_model_default_config_drops_reasoning(self, transport):
        """No reasoning_config == default ``enabled=True, effort=medium``;
        unsupported model should still drop the effort. The current fix also
        drops the ``include`` (coupled in the xAI request shape)."""
        kw = self._xai_kwargs(transport, "grok-4-1-fast")
        assert "reasoning" not in kw
        assert kw.get("include") == []

    def test_supported_model_default_config_keeps_reasoning(self, transport):
        kw = self._xai_kwargs(transport, "grok-4.3")
        assert kw.get("reasoning") == {"effort": "medium"}

    # ── Cross-provider isolation ─────────────────────────────────────────

    def test_gate_does_not_apply_to_openai(self, transport):
        """OpenAI / Codex backend is unaffected by xAI gating."""
        kw = transport.build_kwargs(
            model="gpt-5.4",
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            reasoning_config={"effort": "high"},
        )
        assert kw.get("reasoning", {}).get("effort") == "high"

    def test_grok_model_without_xai_flag_takes_non_xai_branch(self, transport):
        """Sanity: ``is_xai_responses=False`` means the xAI gate is bypassed —
        the non-xAI Responses branch is responsible for whatever it sends."""
        kw = transport.build_kwargs(
            model="grok-4-1-fast",
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            is_xai_responses=False,
            reasoning_config={"effort": "high"},
        )
        # Non-xAI branch sends OpenAI-style reasoning. The point of this test
        # is that the gating logic doesn't leak across the is_xai_responses
        # boundary; assert the xAI gate didn't strip the reasoning here.
        assert kw.get("reasoning") == {"effort": "high", "summary": "auto"}

    # ── Robustness: casing, edge inputs ──────────────────────────────────

    def test_uppercase_model_name_still_gated_correctly(self, transport):
        """Helper lowercases the model name."""
        kw = self._xai_kwargs(
            transport, "GROK-4.3", reasoning_config={"effort": "high"},
        )
        assert kw.get("reasoning") == {"effort": "high"}

    def test_mixed_case_unsupported_model_still_drops(self, transport):
        kw = self._xai_kwargs(
            transport, "Grok-4-1-Fast", reasoning_config={"effort": "high"},
        )
        assert "reasoning" not in kw

    def test_empty_model_drops_reasoning_without_crash(self, transport):
        kw = self._xai_kwargs(
            transport, "", reasoning_config={"effort": "high"},
        )
        assert "reasoning" not in kw

    def test_none_model_drops_reasoning_without_crash(self, transport):
        kw = self._xai_kwargs(
            transport, None, reasoning_config={"effort": "high"},
        )
        assert "reasoning" not in kw

    # ── Boundary semantics: token boundary, not substring ────────────────

    def test_numeric_lookalike_does_not_leak_into_allowlist(self, transport):
        """``grok-4.30-something`` must NOT match the ``grok-4.3`` allowlist
        entry. A naive substring check would misclassify it; the helper uses
        an exact-or-hyphen-prefix boundary specifically to prevent this."""
        kw = self._xai_kwargs(
            transport, "grok-4.30-pro", reasoning_config={"effort": "high"},
        )
        assert "reasoning" not in kw

    def test_openrouter_prefix_stripped_for_allowlisted(self, transport):
        """``x-ai/grok-4.3`` (OpenRouter-style prefix) must still match."""
        kw = self._xai_kwargs(
            transport, "x-ai/grok-4.3", reasoning_config={"effort": "high"},
        )
        assert kw.get("reasoning") == {"effort": "high"}

    def test_openrouter_prefix_stripped_for_unsupported(self, transport):
        """``x-ai/grok-4-1-fast`` (OpenRouter-style prefix) must drop too."""
        kw = self._xai_kwargs(
            transport, "x-ai/grok-4-1-fast", reasoning_config={"effort": "high"},
        )
        assert "reasoning" not in kw

    # ── Scope-creep guard: xAI side-effects untouched by the gate ────────

    def test_xai_conv_id_header_set_even_when_effort_gated_off(self, transport):
        """The fix targets ``reasoning`` only; conv-id plumbing must survive."""
        kw = self._xai_kwargs(
            transport,
            "grok-4-1-fast",
            reasoning_config={"effort": "high"},
            session_id="conv-xyz",
        )
        assert kw.get("extra_headers", {}).get("x-grok-conv-id") == "conv-xyz"
        assert "reasoning" not in kw  # still gated

    def test_other_xai_kwargs_preserved_when_gated(self, transport):
        kw = self._xai_kwargs(
            transport,
            "grok-4-1-fast",
            reasoning_config={"effort": "high"},
            session_id="abc",
            max_tokens=1024,
        )
        assert kw.get("model") == "grok-4-1-fast"
        assert kw.get("store") is False
        assert kw.get("max_output_tokens") == 1024
        assert kw.get("extra_body", {}).get("prompt_cache_key") == "abc"

    # ── Future-proofing ──────────────────────────────────────────────────

    def test_unknown_future_model_fails_closed(self, transport):
        """Models not yet in the allowlist must default to NOT sending effort.
        Failing closed avoids re-introducing #23088 every time xAI ships a model."""
        kw = self._xai_kwargs(
            transport, "grok-99-future-preview",
            reasoning_config={"effort": "high"},
        )
        assert "reasoning" not in kw
        assert kw.get("include") == []


class TestCodexValidateResponse:

    def test_none_response(self, transport):
        assert transport.validate_response(None) is False

    def test_empty_output(self, transport):
        r = SimpleNamespace(output=[], output_text=None)
        assert transport.validate_response(r) is False

    def test_valid_output(self, transport):
        r = SimpleNamespace(output=[{"type": "message", "content": []}])
        assert transport.validate_response(r) is True

    def test_output_text_fallback_not_valid(self, transport):
        """validate_response is strict — output_text doesn't make it valid.
        The caller handles output_text fallback with diagnostic logging."""
        r = SimpleNamespace(output=None, output_text="Some text")
        assert transport.validate_response(r) is False


class TestCodexMapFinishReason:

    def test_completed(self, transport):
        assert transport.map_finish_reason("completed") == "stop"

    def test_incomplete(self, transport):
        assert transport.map_finish_reason("incomplete") == "length"

    def test_failed(self, transport):
        assert transport.map_finish_reason("failed") == "stop"

    def test_unknown(self, transport):
        assert transport.map_finish_reason("unknown_status") == "stop"


class TestCodexNormalizeResponse:

    def test_text_response(self, transport):
        """Normalize a simple text Codex response."""
        r = SimpleNamespace(
            output=[
                SimpleNamespace(
                    type="message",
                    role="assistant",
                    content=[SimpleNamespace(type="output_text", text="Hello world")],
                    status="completed",
                ),
            ],
            status="completed",
            incomplete_details=None,
            usage=SimpleNamespace(input_tokens=10, output_tokens=5,
                                  input_tokens_details=None, output_tokens_details=None),
        )
        nr = transport.normalize_response(r)
        assert isinstance(nr, NormalizedResponse)
        assert nr.content == "Hello world"
        assert nr.finish_reason == "stop"

    def test_message_items_preserved_in_provider_data(self, transport):
        """Codex assistant message item ids/phases must survive transport normalization."""
        r = SimpleNamespace(
            output=[
                SimpleNamespace(
                    type="message",
                    role="assistant",
                    id="msg_abc",
                    phase="final_answer",
                    content=[SimpleNamespace(type="output_text", text="Hello world")],
                    status="completed",
                ),
            ],
            status="completed",
            incomplete_details=None,
            usage=SimpleNamespace(input_tokens=10, output_tokens=5,
                                  input_tokens_details=None, output_tokens_details=None),
        )
        nr = transport.normalize_response(r)
        assert nr.codex_message_items == [
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": "Hello world"}],
                "id": "msg_abc",
                "phase": "final_answer",
            }
        ]

    def test_tool_call_response(self, transport):
        """Normalize a Codex response with tool calls."""
        r = SimpleNamespace(
            output=[
                SimpleNamespace(
                    type="function_call",
                    call_id="call_abc123",
                    name="terminal",
                    arguments=json.dumps({"command": "ls"}),
                    id="fc_abc123",
                    status="completed",
                ),
            ],
            status="completed",
            incomplete_details=None,
            usage=SimpleNamespace(input_tokens=10, output_tokens=20,
                                  input_tokens_details=None, output_tokens_details=None),
        )
        nr = transport.normalize_response(r)
        assert nr.finish_reason == "tool_calls"
        assert len(nr.tool_calls) == 1
        tc = nr.tool_calls[0]
        assert tc.name == "terminal"
        assert '"command"' in tc.arguments
