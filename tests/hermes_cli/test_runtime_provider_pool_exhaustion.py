"""Resolver should raise a structured rate-limit AuthError when a pool's
only credentials are in exhaustion cooldown — instead of falling through
to legacy ``_read_*_tokens`` helpers that emit the misleading "no
credentials stored" message.
"""

from __future__ import annotations

import time

import pytest

from hermes_cli import runtime_provider as rp
from hermes_cli.auth import AuthError


class _StubEntry:
    """Stand-in for PooledCredential with just the fields the helpers read."""

    def __init__(
        self,
        *,
        last_status: str = "exhausted",
        last_error_code: int = 429,
        last_error_reason: str = "usage_limit_reached",
        last_error_message: str = "The usage limit has been reached",
        last_error_reset_at: float | None = None,
        last_status_at: float | None = None,
    ) -> None:
        self.last_status = last_status
        self.last_error_code = last_error_code
        self.last_error_reason = last_error_reason
        self.last_error_message = last_error_message
        self.last_error_reset_at = last_error_reset_at
        self.last_status_at = last_status_at


class _StubPool:
    """Pool stub matching the shape exercised by the resolver."""

    def __init__(self, provider: str, entries: list[_StubEntry]) -> None:
        self.provider = provider
        self._entries = list(entries)

    def has_credentials(self) -> bool:
        return bool(self._entries)

    def has_available(self) -> bool:
        return any(e.last_status != "exhausted" for e in self._entries)

    def select(self):
        for entry in self._entries:
            if entry.last_status != "exhausted":
                return entry
        return None

    def entries(self):
        return list(self._entries)


def test_resolver_raises_rate_limit_authError_when_pool_exhausted(monkeypatch):
    reset_at = time.time() + 4320  # ~1h 12m
    pool = _StubPool(
        "openai-codex",
        [_StubEntry(last_error_reset_at=reset_at)],
    )

    monkeypatch.setattr(rp, "resolve_provider", lambda *a, **k: "openai-codex")
    monkeypatch.setattr(rp, "load_pool", lambda provider: pool)

    # If the resolver fell through to legacy ``_read_codex_tokens``, the
    # test would surface that path's "No Codex credentials stored" error.
    # The new pool-exhaustion check must intercept and raise a structured
    # rate-limit AuthError before that happens.
    with pytest.raises(AuthError) as excinfo:
        rp.resolve_runtime_provider(requested="openai-codex")

    err = excinfo.value
    assert err.kind == "rate_limit"
    assert err.provider == "openai-codex"
    assert err.code == "pool_rate_limit"
    assert err.relogin_required is False
    assert err.reset_at == pytest.approx(reset_at, abs=2)
    message = str(err)
    assert "rate-limited" in message
    assert "openai-codex" in message
    # The duration string from format_remaining; tolerate the 1-second
    # boundary between 1h 11m and 1h 12m.
    assert "1h 11m" in message or "1h 12m" in message
    # The misleading legacy string must NOT appear anywhere.
    assert "No Codex credentials stored" not in message


def test_resolver_raises_auth_failed_authError_when_pool_only_has_auth_failures(monkeypatch):
    pool = _StubPool(
        "openai-codex",
        [
            _StubEntry(
                last_error_code=401,
                last_error_reason="invalid_token",
                last_error_message="Unauthorized",
            )
        ],
    )

    monkeypatch.setattr(rp, "resolve_provider", lambda *a, **k: "openai-codex")
    monkeypatch.setattr(rp, "load_pool", lambda provider: pool)

    with pytest.raises(AuthError) as excinfo:
        rp.resolve_runtime_provider(requested="openai-codex")

    err = excinfo.value
    assert err.kind == "auth_failed"
    assert err.code == "pool_auth_failed"
    assert err.relogin_required is True


def test_resolver_skips_exhaustion_check_for_non_pool_providers(monkeypatch):
    """If the requested provider isn't in the pool-exhaustion set, the
    resolver should fall through unchanged (no new behavior)."""
    pool = _StubPool("openrouter", [_StubEntry()])

    monkeypatch.setattr(rp, "resolve_provider", lambda *a, **k: "openrouter")
    monkeypatch.setattr(rp, "load_pool", lambda provider: pool)
    monkeypatch.setattr(rp, "_get_model_config", lambda: {"provider": "openrouter"})

    # openrouter isn't in _POOL_EXHAUSTION_PROVIDERS, so the new check is
    # a no-op. The resolver should proceed past the exhaustion check (and
    # eventually fail via a different path or return env-var creds — both
    # acceptable; we just assert no AuthError carrying our kind is raised).
    try:
        rp.resolve_runtime_provider(requested="openrouter")
    except AuthError as err:
        assert err.kind not in {"rate_limit", "auth_failed", "exhausted"}, (
            f"openrouter should not trigger pool-exhaustion path; got {err.kind=}"
        )
    except Exception:
        # Other downstream failures (e.g. missing env API key) are fine —
        # we only care that we didn't synthesize a pool-exhaustion error.
        pass


def test_authError_from_pool_exhaustion_message_shape() -> None:
    summary = {
        "kind": "rate_limit",
        "label": "rate-limited",
        "provider": "openai-codex",
        "soonest_reset_at": time.time() + 3600,
        "soonest_remaining_seconds": 3600,
        "last_error_reason": "usage_limit_reached",
        "last_error_code": 429,
        "entry_count": 1,
    }
    err = AuthError.from_pool_exhaustion("openai-codex", summary)
    assert err.kind == "rate_limit"
    assert err.code == "pool_rate_limit"
    assert err.provider == "openai-codex"
    assert err.relogin_required is False
    assert "rate-limited" in str(err)
    assert "resets in 1h 0m" in str(err) or "resets in 59m" in str(err)
