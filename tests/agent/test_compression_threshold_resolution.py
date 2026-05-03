"""Tests for issue #18733 — per-model / per-provider compression overrides.

Covers the pure-function ``resolve_compression_threshold()`` resolver in
``agent/context_compressor.py`` plus the wire-up at the ``ContextCompressor``
instantiation site in ``run_agent.py``.

Note: ``ContextCompressor.update_model()`` re-resolution on model switch is
intentionally NOT exercised here — that's owned by the ``threshold_percent=``
parameter introduced by PR #18638. Once that lands, callers compose the two:
``update_model(threshold_percent=resolve_compression_threshold(...))``.
"""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.context_compressor import (
    ContextCompressor,
    _LOGGED_INVALID_OVERRIDE,
    _THRESHOLD_DEFAULT,
    _THRESHOLD_MAX,
    _THRESHOLD_MIN,
    resolve_compression_threshold,
)


@pytest.fixture(autouse=True)
def _clear_dedup():
    """Reset the module-level dedup set so warnings re-fire each test."""
    _LOGGED_INVALID_OVERRIDE.clear()
    yield
    _LOGGED_INVALID_OVERRIDE.clear()


class TestResolutionPrecedence:
    """Per-model > per-provider > global > built-in default."""

    def test_default_when_config_empty(self):
        assert resolve_compression_threshold("any-model", "any-provider", {}) == _THRESHOLD_DEFAULT

    def test_default_when_config_none_typed(self):
        # Defensive: callers pass dicts in practice, but a stray None shouldn't crash.
        assert resolve_compression_threshold("m", "p", None) == _THRESHOLD_DEFAULT  # type: ignore[arg-type]

    def test_global_threshold_used_when_no_overrides(self):
        cfg = {"threshold": 0.40}
        assert resolve_compression_threshold("m", "p", cfg) == 0.40

    def test_provider_override_beats_global(self):
        cfg = {"threshold": 0.50, "provider_thresholds": {"anthropic": 0.65}}
        assert resolve_compression_threshold("any-model", "anthropic", cfg) == 0.65

    def test_model_override_beats_provider(self):
        cfg = {
            "threshold": 0.50,
            "provider_thresholds": {"anthropic": 0.65},
            "model_thresholds": {"claude-sonnet-4": 0.30},
        }
        assert resolve_compression_threshold("claude-sonnet-4", "anthropic", cfg) == 0.30

    def test_model_override_beats_global_when_no_provider_match(self):
        cfg = {
            "threshold": 0.50,
            "model_thresholds": {"claude-sonnet-4": 0.30},
        }
        assert resolve_compression_threshold("claude-sonnet-4", "unknown-provider", cfg) == 0.30

    def test_unknown_model_falls_to_provider(self):
        cfg = {"provider_thresholds": {"anthropic": 0.65}}
        assert resolve_compression_threshold("unknown", "anthropic", cfg) == 0.65

    def test_unknown_provider_falls_to_global(self):
        cfg = {"threshold": 0.40, "provider_thresholds": {"anthropic": 0.65}}
        assert resolve_compression_threshold("unknown", "openrouter", cfg) == 0.40

    def test_no_provider_no_model_falls_to_global(self):
        cfg = {"threshold": 0.40, "provider_thresholds": {"anthropic": 0.65}}
        assert resolve_compression_threshold("", "", cfg) == 0.40

    def test_empty_override_dicts_silent_fall_through(self):
        cfg = {"threshold": 0.40, "provider_thresholds": {}, "model_thresholds": {}}
        assert resolve_compression_threshold("m", "p", cfg) == 0.40

    def test_aliased_provider_key_falls_through(self):
        # Per the resolver docstring: aliases like "google" / "moonshot" are
        # auxiliary-routing-only and won't match the main agent's canonical
        # PROVIDER_REGISTRY id. They should silently fall through.
        cfg = {"threshold": 0.40, "provider_thresholds": {"google": 0.30}}
        # self.provider would be "gemini", not "google"
        assert resolve_compression_threshold("any", "gemini", cfg) == 0.40


class TestValidation:
    """Out-of-range / non-numeric overrides log once and fall through."""

    def test_non_numeric_override_falls_through(self, caplog):
        cfg = {"threshold": 0.40, "provider_thresholds": {"anthropic": "high"}}
        with caplog.at_level(logging.WARNING, logger="agent.context_compressor"):
            result = resolve_compression_threshold("m", "anthropic", cfg)
        assert result == 0.40
        assert any("Invalid" in rec.message and "high" in rec.message for rec in caplog.records)

    def test_below_min_falls_through(self, caplog):
        cfg = {"threshold": 0.40, "model_thresholds": {"m": 0.05}}
        with caplog.at_level(logging.WARNING, logger="agent.context_compressor"):
            result = resolve_compression_threshold("m", "p", cfg)
        assert result == 0.40
        assert any("Invalid" in rec.message for rec in caplog.records)

    def test_above_max_falls_through(self, caplog):
        cfg = {"threshold": 0.40, "model_thresholds": {"m": 1.5}}
        with caplog.at_level(logging.WARNING, logger="agent.context_compressor"):
            result = resolve_compression_threshold("m", "p", cfg)
        assert result == 0.40

    def test_at_min_boundary_accepted(self):
        cfg = {"model_thresholds": {"m": _THRESHOLD_MIN}}
        assert resolve_compression_threshold("m", "p", cfg) == _THRESHOLD_MIN

    def test_at_max_boundary_accepted(self):
        cfg = {"model_thresholds": {"m": _THRESHOLD_MAX}}
        assert resolve_compression_threshold("m", "p", cfg) == _THRESHOLD_MAX

    def test_dedup_warning_per_key(self, caplog):
        cfg = {"model_thresholds": {"m": "bad"}}
        with caplog.at_level(logging.WARNING, logger="agent.context_compressor"):
            for _ in range(3):
                resolve_compression_threshold("m", "p", cfg)
        invalid_records = [r for r in caplog.records if "Invalid" in r.message]
        assert len(invalid_records) == 1, (
            "Module-level dedup should suppress repeated warnings for the same key"
        )

    def test_dedup_distinct_keys_each_warn_once(self, caplog):
        cfg = {"model_thresholds": {"a": "bad", "b": 99}}
        with caplog.at_level(logging.WARNING, logger="agent.context_compressor"):
            resolve_compression_threshold("a", "p", cfg)
            resolve_compression_threshold("a", "p", cfg)  # dedup
            resolve_compression_threshold("b", "p", cfg)
            resolve_compression_threshold("b", "p", cfg)  # dedup
        invalid_records = [r for r in caplog.records if "Invalid" in r.message]
        assert len(invalid_records) == 2

    def test_invalid_global_falls_to_built_in_default(self, caplog):
        cfg = {"threshold": "not-a-float"}
        with caplog.at_level(logging.WARNING, logger="agent.context_compressor"):
            result = resolve_compression_threshold("m", "p", cfg)
        assert result == _THRESHOLD_DEFAULT


class TestWireUpComposition:
    """The resolver composes correctly with ContextCompressor at the call site."""

    def test_resolved_value_flows_into_compressor(self):
        cfg = {
            "threshold": 0.50,
            "model_thresholds": {"test-model": 0.30},
        }
        resolved = resolve_compression_threshold("test-model", "anthropic", cfg)
        with patch("agent.context_compressor.get_model_context_length", return_value=200_000):
            compressor = ContextCompressor(
                model="test-model",
                threshold_percent=resolved,
                quiet_mode=True,
            )
        assert compressor.threshold_percent == 0.30
        # 200_000 * 0.30 = 60_000, but MINIMUM_CONTEXT_LENGTH (64_000) floor applies
        from agent.model_metadata import MINIMUM_CONTEXT_LENGTH
        assert compressor.threshold_tokens == max(60_000, MINIMUM_CONTEXT_LENGTH)

    def test_provider_override_flows_into_compressor(self):
        cfg = {
            "threshold": 0.50,
            "provider_thresholds": {"anthropic": 0.65},
        }
        resolved = resolve_compression_threshold("any-model", "anthropic", cfg)
        with patch("agent.context_compressor.get_model_context_length", return_value=200_000):
            compressor = ContextCompressor(
                model="any-model",
                threshold_percent=resolved,
                quiet_mode=True,
            )
        assert compressor.threshold_percent == 0.65
        # 200_000 * 0.65 = 130_000
        assert compressor.threshold_tokens == 130_000


class TestWireUpSourcePresence:
    """Source-level checks that the resolver is wired in at run_agent.py:2013."""

    @pytest.fixture(scope="class")
    def run_agent_src(self) -> str:
        path = Path(__file__).resolve().parents[2] / "run_agent.py"
        return path.read_text(encoding="utf-8")

    def test_resolver_imported_at_instantiation_site(self, run_agent_src):
        assert "from agent.context_compressor import resolve_compression_threshold" in run_agent_src, (
            "Wire-up missing: resolver must be imported in run_agent.py"
        )

    def test_resolver_called_with_self_model_and_provider(self, run_agent_src):
        # Locate the ContextCompressor instantiation block and assert the
        # resolver call appears in the same window. Window size of 30 lines
        # is generous; the actual gap is ~5 lines.
        idx = run_agent_src.find("self.context_compressor = ContextCompressor(")
        assert idx >= 0, "ContextCompressor instantiation site not found"
        window = run_agent_src[max(0, idx - 1500):idx]
        assert "resolve_compression_threshold(" in window, (
            "Resolver call missing immediately before ContextCompressor() instantiation"
        )
        assert "model=self.model" in window
        assert "provider=self.provider" in window

    def test_compression_schema_keys_added(self):
        path = Path(__file__).resolve().parents[2] / "hermes_cli" / "config.py"
        src = path.read_text(encoding="utf-8")
        assert '"provider_thresholds": {}' in src, "Schema add missing: provider_thresholds"
        assert '"model_thresholds": {}' in src, "Schema add missing: model_thresholds"

    def test_yaml_example_documents_canonical_provider_keys(self):
        path = Path(__file__).resolve().parents[2] / "cli-config.yaml.example"
        src = path.read_text(encoding="utf-8")
        # Either the literal canonical keys or a docstring-style note. Accept
        # either form so reviewers can polish wording without breaking tests.
        assert "provider_thresholds" in src
        assert "model_thresholds" in src
        assert "PROVIDER_REGISTRY" in src, (
            "Example yaml should reference the canonical-id source so users "
            "don't write aliases like 'google'/'moonshot'"
        )
