from datetime import datetime, timezone

import pytest

from hermes_cli import calendar_db


def test_parse_dt_requires_timezone():
    with pytest.raises(ValueError, match="timezone"):
        calendar_db._parse_dt("2026-05-27T10:00:00", field="scheduled_at")


def test_parse_dt_accepts_zulu():
    dt = calendar_db._parse_dt("2026-05-27T10:00:00Z", field="scheduled_at")

    assert dt == datetime(2026, 5, 27, 10, 0, tzinfo=timezone.utc)


def test_normalize_recurrence_accepts_simple_values():
    assert calendar_db._normalize_recurrence("daily") == "daily"
    assert calendar_db._normalize_recurrence(" WEEKLY ") == "weekly"
    assert calendar_db._normalize_recurrence(None) is None


def test_normalize_recurrence_rejects_rrule_for_v1():
    with pytest.raises(ValueError, match="daily, weekly, monthly"):
        calendar_db._normalize_recurrence("FREQ=DAILY")


def test_advance_monthly_clamps_end_of_month():
    dt = datetime(2026, 1, 31, 8, 0, tzinfo=timezone.utc)

    assert calendar_db._advance(dt, "monthly") == datetime(2026, 2, 28, 8, 0, tzinfo=timezone.utc)

