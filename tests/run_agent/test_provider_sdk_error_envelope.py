"""Provider/SDK streaming bug envelope on the user-facing error boundary.

When ``openai`` 2.24.0's ``accumulate_event`` iterates a streaming
snapshot whose ``response.output`` is ``null`` (the canonical case is
chatgpt.com's backend-api/codex prelude), it raises bare
``TypeError("'NoneType' object is not iterable")`` mid-``for event in
stream``.  The SDK-level guard installed by
``agent._openai_sdk_compat.install_codex_responses_output_guard``
prevents the crash, but the conversation retry loop also has to
withstand other future provider SDK leaks of the same shape.

The defense in depth: ``AIAgent._summarize_api_error`` recognises bare
Python ``TypeError``/``AttributeError`` whose ``str(error)`` matches
Python's stock ``"'<TypeName>' object …"`` shape (a signature that real
provider HTTP bodies never emit) and rewrites them as a compact
``Provider SDK streaming bug`` envelope.  The final retry-loop reply
then reads cleanly on Telegram/CLI/Slack/web instead of leaking raw
Python interpreter text into the chat bubble.
"""
from __future__ import annotations


def test_summarize_typeerror_nonetype_iterable_is_wrapped() -> None:
    """The canonical codex streaming bug must be rewrapped, not leaked."""
    from run_agent import AIAgent

    summary = AIAgent._summarize_api_error(
        TypeError("'NoneType' object is not iterable")
    )
    assert "Provider SDK streaming bug" in summary
    # The original signature should be quoted inside the envelope so
    # logs still carry the technical detail, but the prefix lets the
    # gateway shape regex classify the reply as infrastructure-level.
    assert "NoneType" in summary
    # Envelope must be short — this becomes part of a Telegram bubble.
    assert len(summary) < 400


def test_summarize_attributeerror_object_no_attribute_is_wrapped() -> None:
    """Similar SDK-internal shapes (AttributeError on Response objects)
    must follow the same envelope path so future provider SDK churn does
    not surface raw Python text either."""
    from run_agent import AIAgent

    summary = AIAgent._summarize_api_error(
        AttributeError("'Response' object has no attribute 'output_text'")
    )
    assert "Provider SDK streaming bug" in summary


def test_summarize_typeerror_not_subscriptable_is_wrapped() -> None:
    from run_agent import AIAgent

    summary = AIAgent._summarize_api_error(
        TypeError("'NoneType' object is not subscriptable")
    )
    assert "Provider SDK streaming bug" in summary


def test_summarize_typeerror_with_status_code_is_not_rewrapped() -> None:
    """If a TypeError carries provider HTTP context, treat it as a normal
    provider error — the SDK-leak envelope only fires on bare exceptions
    that lack any provider response context."""
    from run_agent import AIAgent

    class _ProviderTypeError(TypeError):
        status_code = 400

    summary = AIAgent._summarize_api_error(
        _ProviderTypeError("'NoneType' object is not iterable")
    )
    # Should fall through to the HTTP-prefixed fallback, not the SDK-bug
    # envelope, because the provider attached a real status code.
    assert "Provider SDK streaming bug" not in summary
    assert "HTTP 400" in summary


def test_summarize_typeerror_with_random_message_falls_through() -> None:
    """Non-stock TypeError messages (anything that isn't Python's
    ``'<TypeName>' object …`` shape) are not SDK-internal leaks — leave
    them alone so they keep flowing through the legacy fallback."""
    from run_agent import AIAgent

    summary = AIAgent._summarize_api_error(
        TypeError("custom validation rejected your payload at field foo")
    )
    assert "Provider SDK streaming bug" not in summary
    assert "custom validation rejected" in summary


def test_summarize_provider_json_body_message_is_not_rewrapped() -> None:
    """Errors that carry a structured provider body keep their existing
    extraction path — the envelope must not steal them."""
    from run_agent import AIAgent

    class _ProviderErr(Exception):
        status_code = 403
        body = {"error": {"message": "Forbidden: missing scope"}}

    summary = AIAgent._summarize_api_error(_ProviderErr("403 forbidden"))
    assert "Provider SDK streaming bug" not in summary
    assert "Forbidden: missing scope" in summary
    assert "HTTP 403" in summary


def test_final_retry_response_keeps_gateway_shape_prefix() -> None:
    """The retry loop wraps the summary in ``"API call failed after N
    retries: <summary>"``.  Even with the new envelope content, the
    composed string must still trigger the Telegram shape regex so the
    gateway's ``_gateway_provider_error_reply`` swaps it for a chat-safe
    reply rather than dumping technical text to the user."""
    from run_agent import AIAgent
    from gateway.run import _looks_like_gateway_provider_error

    summary = AIAgent._summarize_api_error(
        TypeError("'NoneType' object is not iterable")
    )
    composed = f"API call failed after 5 retries: {summary}"
    assert _looks_like_gateway_provider_error(composed)


def test_telegram_sanitizer_uses_sdk_bug_specific_reply() -> None:
    """Telegram replies for the SDK-streaming-bug envelope must be the
    targeted reply (so users know it is upstream-malformed-response, not
    auth / rate-limit / policy)."""
    from gateway.config import Platform
    from gateway.run import _sanitize_gateway_final_response

    raw = (
        "API call failed after 5 retries: Provider SDK streaming bug — "
        "upstream returned a snapshot the SDK could not parse "
        "('NoneType' object is not iterable). Raw diagnostics in gateway logs."
    )
    sanitized = _sanitize_gateway_final_response(Platform.TELEGRAM, raw)

    # User-facing reply must not leak the Python-internal phrase.
    assert "NoneType" not in sanitized
    assert "object is not iterable" not in sanitized
    # And it should specifically call out malformed streaming, not the
    # generic provider-failed-after-retries fallback.
    assert "malformed" in sanitized.lower()


def test_non_telegram_final_response_gets_clean_envelope() -> None:
    """Other gateway platforms (CLI / Slack / WhatsApp / Discord / web)
    skip Telegram-only sanitization, so the in-string envelope is the
    only defence.  Verify the user sees the classified envelope rather
    than raw Python text on those platforms."""
    from run_agent import AIAgent
    from gateway.run import _sanitize_gateway_final_response

    summary = AIAgent._summarize_api_error(
        TypeError("'NoneType' object is not iterable")
    )
    composed = f"API call failed after 5 retries: {summary}"

    # Discord is one of the non-Telegram platforms that passes through.
    passthrough = _sanitize_gateway_final_response("discord", composed)
    assert passthrough == composed
    assert "Provider SDK streaming bug" in passthrough
