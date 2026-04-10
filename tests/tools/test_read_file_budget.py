"""Tests that read_file is no longer exempt from result size limits."""

from tools.budget_config import PINNED_THRESHOLDS
from tools.registry import registry


class TestReadFileNotExempt:
    def test_pinned_thresholds_no_infinity(self):
        threshold = PINNED_THRESHOLDS.get("read_file")
        assert threshold is None or threshold != float("inf")

    def test_registry_returns_finite_threshold(self):
        size = registry.get_max_result_size("read_file")
        assert size < float("inf")

    def test_read_file_uses_default_threshold(self):
        from tools.budget_config import DEFAULT_RESULT_SIZE_CHARS
        size = registry.get_max_result_size("read_file")
        assert size == DEFAULT_RESULT_SIZE_CHARS
