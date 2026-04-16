"""Regression tests for agent.copilot_acp_client._coerce_timeout_seconds.

Covers #11129: the Copilot ACP shim blew up with
``TypeError: float() argument must be a string or a real number, not
'Timeout'`` whenever Hermes' streaming path passed
``timeout=httpx.Timeout(...)`` through to ``create(...)``.  The ACP shim
has to convert *any* OpenAI-client timeout shape into a single float
number of seconds for its ``copilot --acp --stdio`` subprocess guard.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from agent.copilot_acp_client import (
    _DEFAULT_TIMEOUT_SECONDS,
    CopilotACPClient,
    _coerce_timeout_seconds,
)


class TestCoerceTimeoutSeconds:
    """Every shape Hermes or an OpenAI-client caller might hand us."""

    def test_none_returns_default(self):
        assert _coerce_timeout_seconds(None, 123.0) == 123.0

    def test_int_passes_through(self):
        assert _coerce_timeout_seconds(42, 1.0) == 42.0

    def test_float_passes_through(self):
        assert _coerce_timeout_seconds(12.5, 1.0) == 12.5

    def test_bool_falls_back_to_default(self):
        """``bool`` is an ``int`` subclass but ``True``/``False`` are not
        meaningful timeouts — fall back rather than silently use 1.0s."""
        assert _coerce_timeout_seconds(True, 60.0) == 60.0
        assert _coerce_timeout_seconds(False, 60.0) == 60.0

    def test_httpx_timeout_uses_read(self):
        """#11129 root-cause case. ``httpx.Timeout`` is what Hermes'
        streaming path passes; read is what bounds the response."""
        value = httpx.Timeout(connect=30.0, read=1800.0, write=1800.0, pool=30.0)
        assert _coerce_timeout_seconds(value, 1.0) == 1800.0

    def test_httpx_timeout_bare_number_is_applied_to_all(self):
        """``httpx.Timeout(120)`` applies 120s to every phase including
        read; we must resolve to 120.0, not fall back to default."""
        assert _coerce_timeout_seconds(httpx.Timeout(120), 1.0) == 120.0

    def test_httpx_timeout_none_falls_back_to_default(self):
        """``httpx.Timeout(None)`` means *no* timeout. Keeping the default
        bound is safer than passing ``inf`` to the subprocess guard."""
        assert _coerce_timeout_seconds(httpx.Timeout(None), 600.0) == 600.0

    def test_simplenamespace_with_read_attr(self):
        """Any duck-typed object with ``.read`` as a number is accepted —
        useful for test doubles and other OpenAI-client variants."""
        assert _coerce_timeout_seconds(SimpleNamespace(read=77.0), 1.0) == 77.0

    def test_string_numeric(self):
        assert _coerce_timeout_seconds("30", 1.0) == 30.0

    def test_unparseable_string_falls_back(self):
        assert _coerce_timeout_seconds("thirty", 7.0) == 7.0

    def test_arbitrary_object_falls_back(self):
        class Weird:
            pass

        assert _coerce_timeout_seconds(Weird(), 99.0) == 99.0

    def test_zero_is_preserved(self):
        """A caller passing ``0`` opts into an immediate timeout; don't
        clobber that with the default."""
        assert _coerce_timeout_seconds(0, 99.0) == 0.0


class TestCreateChatCompletionWithHttpxTimeout:
    """End-to-end: the shim's ``.chat.completions.create(...)`` must not
    raise when Hermes' real streaming path hands it an ``httpx.Timeout``.
    """

    def _make_client(self, tmp_path) -> CopilotACPClient:
        return CopilotACPClient(base_url="acp://copilot", acp_cwd=str(tmp_path))

    def test_httpx_timeout_does_not_raise_typeerror(self, tmp_path):
        """Before the fix: TypeError from ``float(httpx.Timeout(...))``
        inside ``_create_chat_completion``.  After: the shim forwards a
        plain float to ``_run_prompt``."""
        client = self._make_client(tmp_path)

        with patch.object(
            CopilotACPClient, "_run_prompt", return_value=("ok", "")
        ) as run_prompt:
            client.chat.completions.create(
                model="claude-sonnet-4.6",
                messages=[{"role": "user", "content": "hi"}],
                timeout=httpx.Timeout(connect=30.0, read=1800.0, write=1800.0, pool=30.0),
            )

        run_prompt.assert_called_once()
        kwargs = run_prompt.call_args.kwargs
        assert "timeout_seconds" in kwargs
        assert kwargs["timeout_seconds"] == 1800.0
        assert isinstance(kwargs["timeout_seconds"], float)

    def test_float_timeout_still_passes_through(self, tmp_path):
        """Non-regression: numeric timeouts still reach ``_run_prompt`` unchanged."""
        client = self._make_client(tmp_path)

        with patch.object(
            CopilotACPClient, "_run_prompt", return_value=("ok", "")
        ) as run_prompt:
            client.chat.completions.create(
                model="claude-sonnet-4.6",
                messages=[{"role": "user", "content": "hi"}],
                timeout=42.0,
            )

        assert run_prompt.call_args.kwargs["timeout_seconds"] == 42.0

    def test_no_timeout_uses_default(self, tmp_path):
        client = self._make_client(tmp_path)

        with patch.object(
            CopilotACPClient, "_run_prompt", return_value=("ok", "")
        ) as run_prompt:
            client.chat.completions.create(
                model="claude-sonnet-4.6",
                messages=[{"role": "user", "content": "hi"}],
            )

        assert run_prompt.call_args.kwargs["timeout_seconds"] == _DEFAULT_TIMEOUT_SECONDS


@pytest.mark.parametrize("bogus", [httpx.Timeout(None), object(), "not-a-number"])
def test_bogus_timeouts_never_raise(bogus):
    """Safety net — if a future caller hands a new shape, we fall back
    to the default rather than aborting the whole request."""
    result = _coerce_timeout_seconds(bogus, 555.5)
    assert isinstance(result, float)
    assert not math.isinf(result)
    assert not math.isnan(result)
