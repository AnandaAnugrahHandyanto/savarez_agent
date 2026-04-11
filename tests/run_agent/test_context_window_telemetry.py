"""Tests for context window usage telemetry."""
import pytest


class TestContextWindowTelemetry:
    """Agent should report context window usage to the user."""

    def test_usage_report_format(self):
        """Usage report should show percentage and absolute numbers."""
        from run_agent import ContextUsageReport

        report = ContextUsageReport(
            used_tokens=50000,
            total_tokens=128000,
            message_count=20,
        )

        assert report.percentage == pytest.approx(39.06, abs=0.1)
        assert report.used_tokens == 50000
        assert report.total_tokens == 128000
        assert "39%" in report.summary() or "39.1%" in report.summary()

    def test_usage_report_below_threshold_no_warning(self):
        """Below the warning threshold, is_warning should be False."""
        from run_agent import ContextUsageReport

        report = ContextUsageReport(
            used_tokens=50000,
            total_tokens=128000,
            message_count=20,
        )

        assert report.is_warning(threshold_percent=85) is False

    def test_usage_report_above_threshold_warns(self):
        """Above the warning threshold, is_warning should be True."""
        from run_agent import ContextUsageReport

        report = ContextUsageReport(
            used_tokens=110000,
            total_tokens=128000,
            message_count=40,
        )

        assert report.is_warning(threshold_percent=85) is True

    def test_summary_includes_message_count(self):
        """Summary should include the message count for context."""
        from run_agent import ContextUsageReport

        report = ContextUsageReport(
            used_tokens=50000,
            total_tokens=128000,
            message_count=42,
        )

        summary = report.summary()
        assert "42" in summary
        assert "50,000" in summary or "50000" in summary
