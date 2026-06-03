"""Tests for OpenRouter usage-rankings picker ordering.

Covers:
  * permaslug → canonical routing-id normalization
  * latest-day rank extraction from the dataset payload
  * the pure reorder (pinned-first, usage-ranked, manifest tiebreak)
  * graceful fallback when ranking data is empty
"""

from __future__ import annotations

import hermes_cli.openrouter_rankings as orr
from hermes_cli.openrouter_rankings import (
    _parse_latest_day_ranks,
    normalize_permaslug,
    reorder_by_usage,
)


# ---------------------------------------------------------------------------
# normalize_permaslug
# ---------------------------------------------------------------------------


class TestNormalizePermaslug:
    def test_strips_date_suffix(self):
        assert normalize_permaslug("xiaomi/mimo-v2.5-20260422") == "xiaomi/mimo-v2.5"
        assert (
            normalize_permaslug("deepseek/deepseek-v4-flash-20260423")
            == "deepseek/deepseek-v4-flash"
        )

    def test_preserves_free_tag(self):
        assert (
            normalize_permaslug("nvidia/nemotron-3-super-120b-a12b-20230311:free")
            == "nvidia/nemotron-3-super-120b-a12b:free"
        )

    def test_anthropic_component_reorder(self):
        # rankings list claude-<gen>-<tier>; routing id is claude-<tier>-<gen>
        assert (
            normalize_permaslug("anthropic/claude-4.7-opus-20260416")
            == "anthropic/claude-opus-4.7"
        )
        assert (
            normalize_permaslug("anthropic/claude-4.6-sonnet-20260217")
            == "anthropic/claude-sonnet-4.6"
        )
        assert (
            normalize_permaslug("anthropic/claude-4.8-opus-20260528")
            == "anthropic/claude-opus-4.8"
        )

    def test_no_date_passes_through(self):
        assert normalize_permaslug("openrouter/owl-alpha") == "openrouter/owl-alpha"

    def test_other_and_garbage_return_none(self):
        assert normalize_permaslug("other") is None
        assert normalize_permaslug("") is None
        assert normalize_permaslug("no-slug-here") is None
        assert normalize_permaslug(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _parse_latest_day_ranks
# ---------------------------------------------------------------------------


class TestParseLatestDayRanks:
    def _payload(self):
        return {
            "data": [
                # older day — must be ignored
                {"date": "2026-05-30", "model_permaslug": "x/old", "total_tokens": "999"},
                # latest day
                {"date": "2026-05-31", "model_permaslug": "deepseek/deepseek-v4-flash-20260423", "total_tokens": "389441645148"},
                {"date": "2026-05-31", "model_permaslug": "tencent/hy3-preview-20260421", "total_tokens": "362650457872"},
                {"date": "2026-05-31", "model_permaslug": "anthropic/claude-4.7-opus-20260416", "total_tokens": "217765264111"},
                {"date": "2026-05-31", "model_permaslug": "other", "total_tokens": "100"},
            ],
            "meta": {"end_date": "2026-05-31"},
        }

    def test_uses_latest_day_only_and_ranks_by_tokens(self):
        ranks = _parse_latest_day_ranks(self._payload())
        assert ranks["deepseek/deepseek-v4-flash"] == 0
        assert ranks["tencent/hy3-preview"] == 1
        assert ranks["anthropic/claude-opus-4.7"] == 2
        # older-day model and `other` excluded
        assert "x/old" not in ranks
        assert "other" not in ranks

    def test_empty_payload(self):
        assert _parse_latest_day_ranks({}) == {}
        assert _parse_latest_day_ranks({"data": []}) == {}
        assert _parse_latest_day_ranks(None) == {}

    def test_dedup_keeps_higher_usage(self):
        payload = {
            "data": [
                {"date": "2026-05-31", "model_permaslug": "z/m-20260101", "total_tokens": "50"},
                {"date": "2026-05-31", "model_permaslug": "z/m-20260202", "total_tokens": "500"},
            ]
        }
        ranks = _parse_latest_day_ranks(payload)
        # both normalize to z/m; the 500-token one (rank 0) wins
        assert ranks == {"z/m": 0}


# ---------------------------------------------------------------------------
# reorder_by_usage
# ---------------------------------------------------------------------------


class TestReorderByUsage:
    CURATED = [
        ("anthropic/claude-opus-4.8", ""),
        ("openai/gpt-5.5", ""),
        ("moonshotai/kimi-k2.6", "recommended"),
        ("deepseek/deepseek-v4-flash", ""),
        ("tencent/hy3-preview", "free"),
        ("some/unranked-model", ""),
    ]

    def test_pinned_first_then_usage_then_tiebreak(self):
        ranks = {
            "tencent/hy3-preview": 0,       # most used
            "deepseek/deepseek-v4-flash": 1,
            "moonshotai/kimi-k2.6": 5,
            # opus-4.8 / gpt-5.5 also ranked high but are PINNED so order is forced
            "anthropic/claude-opus-4.8": 0,
            "openai/gpt-5.5": 0,
            # some/unranked-model intentionally absent
        }
        pinned = ["anthropic/claude-opus-4.8", "openai/gpt-5.5"]
        out = [mid for mid, _ in reorder_by_usage(self.CURATED, ranks, pinned)]
        assert out[0] == "anthropic/claude-opus-4.8"
        assert out[1] == "openai/gpt-5.5"
        # then ranked tail by usage
        assert out[2] == "tencent/hy3-preview"
        assert out[3] == "deepseek/deepseek-v4-flash"
        assert out[4] == "moonshotai/kimi-k2.6"
        # unranked model last, preserving manifest order
        assert out[5] == "some/unranked-model"

    def test_descriptions_preserved(self):
        ranks = {"tencent/hy3-preview": 0}
        out = dict(reorder_by_usage(self.CURATED, ranks, []))
        assert out["tencent/hy3-preview"] == "free"
        assert out["moonshotai/kimi-k2.6"] == "recommended"

    def test_no_ranks_keeps_manifest_order_with_pins(self):
        # empty ranking map (fallback path) — only pins move, rest unchanged
        out = [mid for mid, _ in reorder_by_usage(self.CURATED, {}, ["openai/gpt-5.5"])]
        assert out[0] == "openai/gpt-5.5"
        # remaining keep original relative order
        assert out[1:] == [
            "anthropic/claude-opus-4.8",
            "moonshotai/kimi-k2.6",
            "deepseek/deepseek-v4-flash",
            "tencent/hy3-preview",
            "some/unranked-model",
        ]

    def test_empty_curated(self):
        assert reorder_by_usage([], {"x/y": 0}, ["a/b"]) == []

    def test_pin_not_in_curated_is_skipped(self):
        out = [mid for mid, _ in reorder_by_usage(self.CURATED, {}, ["not/present"])]
        assert out == [mid for mid, _ in self.CURATED]

    def test_no_entries_dropped_or_added(self):
        ranks = {"tencent/hy3-preview": 0, "moonshotai/kimi-k2.6": 1}
        out = reorder_by_usage(self.CURATED, ranks, ["openai/gpt-5.5"])
        assert sorted(m for m, _ in out) == sorted(m for m, _ in self.CURATED)
        assert len(out) == len(self.CURATED)


# ---------------------------------------------------------------------------
# fetch_openrouter_rankings — fallback behavior (no network)
# ---------------------------------------------------------------------------


class TestFetchFallback:
    def test_no_key_no_disk_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr(orr, "_rankings_cache", None)
        monkeypatch.setattr(orr, "_rankings_cache_at", 0.0)
        monkeypatch.setattr(orr, "_cache_path", lambda: tmp_path / "nope.json")
        monkeypatch.setattr(orr, "_resolve_openrouter_api_key", lambda: "")
        assert orr.fetch_openrouter_rankings(force_refresh=True) == {}
