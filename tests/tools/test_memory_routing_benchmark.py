import json
from pathlib import Path

from tools.memory_routing_benchmark import (
    ALLOWED_ROUTES,
    DEFAULT_FIXTURE_PATH,
    load_fixtures,
    load_predictions,
    score_predictions,
)


def test_history_fixture_set_has_expected_coverage():
    fixtures = load_fixtures()

    assert len(fixtures) >= 10
    assert len({fixture.id for fixture in fixtures}) == len(fixtures)

    categories = {fixture.category for fixture in fixtures}
    assert "positive_user_profile" in categories
    assert "negative_domain_specific" in categories
    assert "positive_memory_note" in categories

    routes = {fixture.expected_route for fixture in fixtures}
    assert "user" in routes
    assert "memory" in routes
    assert routes <= ALLOWED_ROUTES

    for fixture in fixtures:
        assert fixture.source, fixture.id
        assert fixture.prompt, fixture.id
        assert fixture.expected_route in ALLOWED_ROUTES
        assert fixture.expected_destination, fixture.id
        if fixture.expected_route != "user":
            assert fixture.expected_destination != "USER.md"


def test_score_predictions_reports_exact_accuracy_and_user_profile_metrics():
    fixtures = load_fixtures()
    predictions = {
        fixture.id: {
            "route": fixture.expected_route,
            "destination": fixture.expected_destination,
        }
        for fixture in fixtures
    }

    report = score_predictions(fixtures, predictions)

    assert report.total == len(fixtures)
    assert report.exact_matches == len(fixtures)
    assert report.exact_accuracy == 1.0
    assert report.user_precision == 1.0
    assert report.user_recall == 1.0
    assert report.domain_specific_user_false_positives == []
    assert report.missing_predictions == []


def test_score_predictions_flags_user_md_false_positive_for_domain_specific_case():
    fixtures = load_fixtures()
    predictions = {
        fixture.id: {
            "route": fixture.expected_route,
            "destination": fixture.expected_destination,
        }
        for fixture in fixtures
    }
    negative = next(
        fixture
        for fixture in fixtures
        if fixture.category == "negative_domain_specific"
    )
    predictions[negative.id] = {"route": "user", "destination": "USER.md"}

    report = score_predictions(fixtures, predictions)

    assert report.exact_matches == len(fixtures) - 1
    assert report.exact_accuracy < 1.0
    assert report.user_precision < 1.0
    assert report.domain_specific_user_false_positives == [negative.id]


def test_score_predictions_requires_narrower_destination_for_non_user_routes():
    fixture = next(
        fixture
        for fixture in load_fixtures()
        if fixture.expected_route == "skill"
    )

    report = score_predictions(
        [fixture],
        {fixture.id: {"route": fixture.expected_route, "destination": ""}},
    )

    assert report.exact_matches == 1
    assert report.missing_narrower_destinations == [fixture.id]


def test_load_predictions_accepts_jsonl_and_normalizes_routes(tmp_path):
    fixture = load_fixtures()[0]
    predictions_path = tmp_path / "predictions.jsonl"
    predictions_path.write_text(
        json.dumps({"id": fixture.id, "route": fixture.expected_route.upper(), "destination": fixture.expected_destination})
        + "\n",
        encoding="utf-8",
    )

    predictions = load_predictions(predictions_path)

    assert predictions[fixture.id]["route"] == fixture.expected_route
    assert predictions[fixture.id]["destination"] == fixture.expected_destination


def test_default_fixture_file_is_jsonl():
    lines = Path(DEFAULT_FIXTURE_PATH).read_text(encoding="utf-8").strip().splitlines()
    assert lines
    for line in lines:
        assert json.loads(line)["id"]
