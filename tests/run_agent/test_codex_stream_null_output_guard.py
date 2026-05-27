"""Regression: openai SDK parse_response must not crash when a streaming
snapshot's ``response.output`` is ``None``.

chatgpt.com's backend-api/codex emits early streaming snapshots where
``output`` is ``null``. openai 2.24.0 iterates that field without a
None-guard at ``openai/lib/_parsing/_responses.py:61`` (called from
``openai/lib/streaming/responses/_responses.py:360`` inside
``accumulate_event``), which raises ``TypeError: 'NoneType' object is
not iterable`` mid-``for event in stream`` and aborts every codex turn.

We can't bump the pin (other openai releases segfault pydantic-core), so
``agent._openai_sdk_compat.install_codex_responses_output_guard`` wraps
``parse_response`` in both bound namespaces and coerces
``response.output`` to ``[]`` before delegating. These tests pin that
contract.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest


# Importing codex_runtime triggers install_codex_responses_output_guard()
# at module import time — exactly how it ships in production.
import agent.codex_runtime  # noqa: F401  (import for side effect)
import openai.lib._parsing._responses as _origin_mod
import openai.lib.streaming.responses._responses as _streaming_mod
from agent._openai_sdk_compat import (
    _PATCH_MARKER,
    install_codex_responses_output_guard,
)


def _is_patched(fn) -> bool:
    return bool(getattr(fn, _PATCH_MARKER, False))


def test_parse_response_is_patched_in_both_namespaces() -> None:
    """Both bindings of ``parse_response`` must carry the guard marker."""
    assert _is_patched(_origin_mod.parse_response), (
        "openai.lib._parsing._responses.parse_response is not wrapped"
    )
    assert _is_patched(_streaming_mod.parse_response), (
        "openai.lib.streaming.responses._responses.parse_response is not wrapped"
    )


def test_install_is_idempotent() -> None:
    """Calling the installer twice must not stack wrappers."""
    before_origin = _origin_mod.parse_response
    before_streaming = _streaming_mod.parse_response
    install_codex_responses_output_guard()
    install_codex_responses_output_guard()
    assert _origin_mod.parse_response is before_origin
    assert _streaming_mod.parse_response is before_streaming


def test_null_output_no_longer_raises_typeerror() -> None:
    """Snapshot with ``output=None`` must reach the wrapped body and not crash.

    We don't need a fully valid Response — only that the wrapper coerces
    ``output`` to ``[]`` before delegating. We stub the original so we
    don't depend on the rest of ``parse_response``'s real machinery.
    """
    captured = {}

    def _fake_original(*, text_format, input_tools, response):
        # If the guard fired, output is now [] and iteration works.
        captured["output"] = response.output
        # Mimic what the real fn returns: a ParsedResponse-ish stub.
        return SimpleNamespace(output=list(response.output))

    # Temporarily swap the underlying original behind both wrappers.
    # Each wrapped fn closes over its own ``original``; the cleanest way
    # to inject is to install the guard around _fake_original directly,
    # which is what production does at import time.
    from agent._openai_sdk_compat import _wrap_parse_response

    guarded = _wrap_parse_response(_fake_original)

    snapshot = SimpleNamespace(output=None)
    # Should NOT raise TypeError.
    result = guarded(text_format=None, input_tools=None, response=snapshot)

    assert captured["output"] == []
    assert result.output == []


def test_non_null_output_is_passed_through_unchanged() -> None:
    """Sanity: when ``output`` is already a list the guard must not touch it."""
    from agent._openai_sdk_compat import _wrap_parse_response

    seen = {}

    def _fake_original(*, text_format, input_tools, response):
        seen["output"] = response.output
        return SimpleNamespace(output=response.output)

    guarded = _wrap_parse_response(_fake_original)
    sentinel = [SimpleNamespace(type="message", content=[])]
    snapshot = SimpleNamespace(output=sentinel)

    guarded(text_format=None, input_tools=None, response=snapshot)
    # Same object — no replacement, no copy.
    assert seen["output"] is sentinel


def test_guard_survives_pydantic_assignment_rejection(caplog) -> None:
    """If a future SDK rejects direct ``response.output = []`` assignment,
    the guard must swallow the error and still delegate to the original
    (which will then raise its own, clearer error). The point of the
    swallow is: the guard never makes things *worse* than upstream.
    """
    from agent._openai_sdk_compat import _wrap_parse_response

    class FrozenResponse:
        # __slots__-less but with a property that rejects assignment.
        @property
        def output(self):
            return None

        @output.setter
        def output(self, _value):
            raise AttributeError("frozen")

    delegated = {"called": False}

    def _fake_original(*, text_format, input_tools, response):
        delegated["called"] = True
        # Mimic upstream behaviour: try to iterate, blow up with the
        # SAME error the user would see without the guard.
        for _ in response.output:  # noqa: B007
            pass

    guarded = _wrap_parse_response(_fake_original)

    with pytest.raises(TypeError):
        guarded(text_format=None, input_tools=None, response=FrozenResponse())

    # The guard must still have delegated rather than masking the call.
    assert delegated["called"] is True


def test_guard_tolerates_positional_response_arg() -> None:
    """Defensive path: even if a future SDK changes ``parse_response`` to
    accept ``response`` positionally, the guard must still find it."""
    from agent._openai_sdk_compat import _wrap_parse_response

    captured = {}

    def _fake_original(text_format, input_tools, response):
        captured["output"] = response.output
        return None

    guarded = _wrap_parse_response(_fake_original)
    snapshot = SimpleNamespace(output=None)
    guarded(None, None, snapshot)
    assert captured["output"] == []
