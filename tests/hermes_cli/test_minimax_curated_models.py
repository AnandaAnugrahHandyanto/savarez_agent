"""Tests for the minimax / minimax-cn curated model lists.

The offline fallback (used when models.dev is unreachable) is
``hermes_cli.models._PROVIDER_MODELS``.  If a model is available from
the provider but missing from the curated list, users on flaky networks
or behind a corporate proxy that blocks models.dev won't see it in the
``hermes model`` dropdown — even though the model works fine.

Each release should keep these lists in sync with what the upstream
provider actually ships.  See ``references/minimax-model-list.md`` for
the source of truth.
"""

from hermes_cli.models import _PROVIDER_MODELS


def test_minimax_curated_includes_highspeed_variants():
    """The -highspeed variants are shipped by minimax and must be in the
    curated list, otherwise offline users won't see them in the picker."""
    curated = _PROVIDER_MODELS.get("minimax", [])
    assert "MiniMax-M2.7-highspeed" in curated
    assert "MiniMax-M2.5-highspeed" in curated


def test_minimax_cn_curated_includes_highspeed_variants():
    """Same as above, but for the China endpoint."""
    curated = _PROVIDER_MODELS.get("minimax-cn", [])
    assert "MiniMax-M2.7-highspeed" in curated
    assert "MiniMax-M2.5-highspeed" in curated


def test_minimax_curated_dedupes_within_provider():
    """No duplicate model IDs within a single provider list."""
    for prov in ("minimax", "minimax-cn"):
        curated = _PROVIDER_MODELS.get(prov, [])
        assert len(curated) == len(set(curated)), f"{prov} has duplicates: {curated}"


def test_minimax_oauth_curated_unchanged():
    """The OAuth provider ships a smaller set (M3 / M2.7 / M2.7-highspeed).
    Don't accidentally widen this — the OAuth endpoint has its own quota.
    """
    curated = _PROVIDER_MODELS.get("minimax-oauth", [])
    assert curated == ["MiniMax-M3", "MiniMax-M2.7", "MiniMax-M2.7-highspeed"]
