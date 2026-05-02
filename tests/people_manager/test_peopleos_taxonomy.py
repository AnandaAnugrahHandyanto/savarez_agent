import pytest

from people_manager.constants import (
    CADENCE_VALUES,
    CATEGORY_VALUES,
    EXTERNAL_RELATIONSHIP_KINDS,
    INTERNAL_RANK_VALUES,
    PERFORMANCE_VALUES,
    PROFILE_TYPES,
    TRUST_VALUES,
)
from people_manager.storage import create_report, normalize_report


def test_peopleos_taxonomy_constants_are_explicit():
    assert PROFILE_TYPES == ("internal", "external")
    assert EXTERNAL_RELATIONSHIP_KINDS == (
        "investor",
        "advisor",
        "board",
        "strategic_partner",
        "customer",
        "friend",
        "family",
        "other",
    )
    assert "N-" in INTERNAL_RANK_VALUES
    assert "S-" in INTERNAL_RANK_VALUES


def test_external_profiles_preserve_relationship_kind_and_do_not_get_internal_rank(tmp_path, monkeypatch):
    monkeypatch.setenv("PEOPLEOS_DATA_ROOT", str(tmp_path / "peopleos-data"))

    report = create_report(
        "Roland Investor",
        "Investor",
        "Maintain investor relationship",
        profile_type="external",
        relationship_kind="investor",
    )

    assert report["profile_type"] == "external"
    assert report["relationship_kind"] == "investor"
    assert report["internal_rank"] is None
    assert report["performance"]["current_performance_read"] is None


def test_invalid_external_relationship_kind_normalizes_to_other():
    report = normalize_report({"name": "Partner", "profile_type": "external", "relationship_kind": "direct_report"})

    assert report["profile_type"] == "external"
    assert report["relationship_kind"] == "other"


def test_internal_rank_preserves_exact_n_and_s_labels():
    report = normalize_report({"name": "Amber Person", "profile_type": "internal", "internal_rank": "N-"})
    assert report["internal_rank"] == "N-"

    report = normalize_report({"name": "Amber Person", "profile_type": "internal", "internal_rank": "S-"})
    assert report["internal_rank"] == "S-"


def test_external_profiles_cannot_carry_internal_rank():
    report = normalize_report({"name": "Su Investor", "profile_type": "external", "relationship_kind": "investor", "internal_rank": "S-"})

    assert report["profile_type"] == "external"
    assert report["relationship_kind"] == "investor"
    assert report["internal_rank"] is None


def test_peopleos_clean_profile_schema_constants_are_explicit():
    assert CATEGORY_VALUES == ("Nexus", "Satellites", "External")
    assert TRUST_VALUES == ("Rock Solid", "Very High", "Positive", "Normal", "Low")
    assert CADENCE_VALUES == ("weekly", "biweekly", "monthly")
    assert PERFORMANCE_VALUES == ("exceeds expectations", "meets expectations", "below expectations")


def test_clean_profile_fields_normalize_and_drive_legacy_compatibility():
    report = normalize_report(
        {
            "name": "Yi Bao",
            "category": "Nexus",
            "rank": 1,
            "roles": "CPO\nCOO candidate",
            "mandates": "Product\nOperations",
            "trust": "Very High",
            "cadence": "biweekly",
            "cadence_details": {"week_of_month": 2, "weekday": "Tuesday", "hour": 9, "minute": 30},
            "last_meeting_date": "2026-05-01",
            "last_meeting_notes": "Discussed COO path",
            "next_meeting_date": "2026-05-15",
            "next_meeting_date_overridden": True,
            "prep_notes": "Ask about product org",
            "performance_rating": "exceeds expectations",
            "long_term_notes_todos": "Keep expanding scope",
            "strengths": "Product taste",
            "weaknesses": "Needs operating cadence",
        }
    )

    assert report["category"] == "Nexus"
    assert report["profile_type"] == "internal"
    assert report["rank"] == 1
    assert report["internal_rank"] is None
    assert report["role_title"] == "CPO; COO candidate"
    assert report["role_charter"]["mandate"] == "Product\nOperations"
    assert report["trust"] == "Very High"
    assert report["cadence"] == "biweekly"
    assert report["checkup_cadence"] == "biweekly"
    assert report["next_checkup_at"] == "2026-05-15"
    assert report["performance_rating"] == "exceeds expectations"
    assert report["performance"]["current_performance_read"] == "exceeds expectations"


def test_clean_profile_fields_coerce_invalid_values_to_safe_defaults():
    report = normalize_report({"name": "Unknown Person", "category": "Bad", "rank": 900, "trust": "bad", "cadence": "daily", "performance_rating": "wow"})

    assert report["category"] == "Nexus"
    assert report["rank"] == 101
    assert report["trust"] == "Normal"
    assert report["cadence"] == "monthly"
    assert report["performance_rating"] == "meets expectations"
