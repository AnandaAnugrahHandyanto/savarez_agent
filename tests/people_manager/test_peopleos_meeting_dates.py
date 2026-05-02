from people_manager.storage import normalize_report


def test_next_meeting_date_weekly_uses_cadence_pattern_not_last_meeting_date():
    report = normalize_report(
        {
            "name": "Weekly Person",
            "last_meeting_date": "2026-05-04",
            "cadence": "weekly",
            "cadence_details": {"weekday": "Monday", "hour": 9, "minute": 30},
            "calculation_reference_date": "2026-05-06",
        }
    )

    assert report["last_meeting_date"] == "2026-05-04"
    assert report["next_meeting_date"] == "2026-05-11"
    assert report["next_meeting_date_source"] == "calculated"
    assert report["next_checkup_at"] == "2026-05-11"


def test_next_meeting_date_ignores_rescheduled_last_meeting_date():
    report = normalize_report(
        {
            "name": "Rescheduled Weekly Person",
            "last_meeting_date": "2026-05-08",
            "last_meeting_date_overridden": True,
            "cadence": "weekly",
            "cadence_details": {"weekday": "Monday"},
            "calculation_reference_date": "2026-05-06",
        }
    )

    assert report["last_meeting_date"] == "2026-05-08"
    assert report["next_meeting_date"] == "2026-05-11"


def test_next_meeting_date_biweekly_uses_even_week_pattern():
    report = normalize_report(
        {
            "name": "Biweekly Even Person",
            "last_meeting_date": "2026-05-04",
            "cadence": "biweekly",
            "cadence_details": {"weekday": "Monday", "week_parity": "even"},
            "calculation_reference_date": "2026-05-06",
        }
    )

    assert report["next_meeting_date"] == "2026-05-11"


def test_next_meeting_date_biweekly_uses_odd_week_pattern():
    report = normalize_report(
        {
            "name": "Biweekly Odd Person",
            "last_meeting_date": "2026-05-04",
            "cadence": "biweekly",
            "cadence_details": {"weekday": "Monday", "week_parity": "odd"},
            "calculation_reference_date": "2026-05-06",
        }
    )

    assert report["next_meeting_date"] == "2026-05-18"


def test_next_meeting_date_monthly_clamps_end_of_month_edge_case_from_reference_date():
    report = normalize_report(
        {
            "name": "Monthly Person",
            "last_meeting_date": "2026-01-12",
            "cadence": "monthly",
            "cadence_details": {},
            "calculation_reference_date": "2026-01-31",
        }
    )

    assert report["next_meeting_date"] == "2026-02-28"


def test_next_meeting_date_monthly_uses_weekday_and_week_of_month_from_reference_date():
    report = normalize_report(
        {
            "name": "Monthly Tuesday Person",
            "last_meeting_date": "2026-05-20",
            "cadence": "monthly",
            "cadence_details": {"week_of_month": "2", "weekday": "Tuesday"},
            "calculation_reference_date": "2026-05-20",
        }
    )

    assert report["next_meeting_date"] == "2026-06-09"


def test_next_meeting_date_manual_override_is_preserved_until_flag_cleared():
    report = normalize_report(
        {
            "name": "Override Person",
            "last_meeting_date": "2026-05-04",
            "cadence": "weekly",
            "next_meeting_date": "2026-06-01",
            "next_meeting_date_overridden": True,
            "calculation_reference_date": "2026-05-06",
        }
    )

    assert report["next_meeting_date"] == "2026-06-01"
    assert report["next_meeting_date_source"] == "manual"


def test_last_meeting_date_database_source_is_preserved_without_manual_override():
    report = normalize_report(
        {
            "name": "Database Date Person",
            "last_touch_at": "2026-05-04",
            "last_meeting_date": "2026-05-01",
            "last_meeting_date_overridden": False,
            "cadence": "weekly",
            "cadence_details": {"weekday": "Monday"},
            "calculation_reference_date": "2026-05-06",
        }
    )

    assert report["last_meeting_date"] == "2026-05-04"
    assert report["last_meeting_date_source"] == "database"
    assert report["next_meeting_date"] == "2026-05-11"


def test_last_meeting_date_manual_override_does_not_drive_next_meeting_date():
    report = normalize_report(
        {
            "name": "Manual Last Person",
            "last_touch_at": "2026-05-04",
            "last_meeting_date": "2026-05-01",
            "last_meeting_date_overridden": True,
            "cadence": "weekly",
            "cadence_details": {"weekday": "Monday"},
            "calculation_reference_date": "2026-05-06",
        }
    )

    assert report["last_meeting_date"] == "2026-05-01"
    assert report["last_meeting_date_source"] == "manual"
    assert report["next_meeting_date"] == "2026-05-11"
