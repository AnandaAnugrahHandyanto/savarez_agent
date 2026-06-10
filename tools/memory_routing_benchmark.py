"""History-based benchmark helpers for durable memory routing decisions.

The fixture set is intentionally small and local: it captures representative
USER.md routing decisions from Ryan's prior cleanup/audit issues so schema or
prompt changes can be evaluated without calling an external LLM provider.

Predictions are deliberately generic JSON so different evaluators can produce
outputs with a model, a prompt-only policy, or a deterministic classifier.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import json

ALLOWED_ROUTES = {
    "user",
    "memory",
    "skill",
    "project_doc",
    "kb_page",
    "kb_inventory",
    "issue_comment",
    "nowhere",
}

DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "memory_routing"
    / "fixtures.jsonl"
)


@dataclass(frozen=True)
class RoutingFixture:
    id: str
    source: str
    category: str
    prompt: str
    expected_route: str
    expected_destination: str
    rationale: str


@dataclass(frozen=True)
class RoutingMismatch:
    id: str
    expected_route: str
    predicted_route: str | None
    expected_destination: str
    predicted_destination: str


@dataclass(frozen=True)
class RoutingBenchmarkReport:
    total: int
    exact_matches: int
    exact_accuracy: float
    user_precision: float | None
    user_recall: float | None
    mismatches: list[RoutingMismatch]
    missing_predictions: list[str]
    invalid_routes: dict[str, str]
    domain_specific_user_false_positives: list[str]
    missing_narrower_destinations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "exact_matches": self.exact_matches,
            "exact_accuracy": self.exact_accuracy,
            "user_precision": self.user_precision,
            "user_recall": self.user_recall,
            "mismatches": [mismatch.__dict__ for mismatch in self.mismatches],
            "missing_predictions": self.missing_predictions,
            "invalid_routes": self.invalid_routes,
            "domain_specific_user_false_positives": self.domain_specific_user_false_positives,
            "missing_narrower_destinations": self.missing_narrower_destinations,
        }


def _normalize_route(route: Any) -> str | None:
    if route is None:
        return None
    normalized = str(route).strip().lower().replace("-", "_")
    aliases = {
        "user_md": "user",
        "user_profile": "user",
        "memory_md": "memory",
        "kb_inventory_md": "kb_inventory",
        "inventory": "kb_inventory",
        "issue": "issue_comment",
        "doc": "project_doc",
        "project_docs": "project_doc",
        "skip": "nowhere",
        "none": "nowhere",
    }
    return aliases.get(normalized, normalized)


def load_fixtures(path: str | Path = DEFAULT_FIXTURE_PATH) -> list[RoutingFixture]:
    fixture_path = Path(path)
    fixtures: list[RoutingFixture] = []
    for line_number, line in enumerate(fixture_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        raw = json.loads(line)
        route = _normalize_route(raw.get("expected_route"))
        if route not in ALLOWED_ROUTES:
            raise ValueError(
                f"Invalid expected_route {raw.get('expected_route')!r} "
                f"in {fixture_path}:{line_number}"
            )
        fixtures.append(
            RoutingFixture(
                id=str(raw["id"]),
                source=str(raw["source"]),
                category=str(raw["category"]),
                prompt=str(raw["prompt"]),
                expected_route=route,
                expected_destination=str(raw["expected_destination"]),
                rationale=str(raw["rationale"]),
            )
        )
    return fixtures


def load_predictions(path: str | Path) -> dict[str, dict[str, str]]:
    """Load prediction JSONL.

    Expected per line: {"id": "fixture-id", "route": "user", "destination": "USER.md"}.
    The destination is optional but required for full-credit non-USER routes.
    """
    predictions: dict[str, dict[str, str]] = {}
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        raw = json.loads(line)
        fixture_id = str(raw.get("id", "")).strip()
        if not fixture_id:
            raise ValueError(f"Missing prediction id at line {line_number}")
        route = _normalize_route(raw.get("route"))
        predictions[fixture_id] = {
            "route": "" if route is None else route,
            "destination": str(raw.get("destination", "")).strip(),
        }
    return predictions


def score_predictions(
    fixtures: list[RoutingFixture],
    predictions: Mapping[str, Mapping[str, Any]],
) -> RoutingBenchmarkReport:
    """Score route predictions against fixtures.

    Exact route accuracy is the primary metric. USER.md precision/recall are
    called out because the benchmark's main failure mode is USER.md pollution:
    domain-specific facts incorrectly routed to the always-loaded user profile.
    """
    total = len(fixtures)
    exact_matches = 0
    mismatches: list[RoutingMismatch] = []
    missing_predictions: list[str] = []
    invalid_routes: dict[str, str] = {}
    domain_specific_user_false_positives: list[str] = []
    missing_narrower_destinations: list[str] = []

    expected_user = 0
    predicted_user = 0
    true_positive_user = 0

    for fixture in fixtures:
        prediction = predictions.get(fixture.id)
        if prediction is None:
            missing_predictions.append(fixture.id)
            predicted_route = None
            predicted_destination = ""
        else:
            predicted_route = _normalize_route(prediction.get("route"))
            predicted_destination = str(prediction.get("destination", "")).strip()
            if predicted_route not in ALLOWED_ROUTES:
                invalid_routes[fixture.id] = "" if predicted_route is None else predicted_route

        if fixture.expected_route == "user":
            expected_user += 1
        if predicted_route == "user":
            predicted_user += 1
        if fixture.expected_route == "user" and predicted_route == "user":
            true_positive_user += 1

        if predicted_route == fixture.expected_route:
            exact_matches += 1
        else:
            mismatches.append(
                RoutingMismatch(
                    id=fixture.id,
                    expected_route=fixture.expected_route,
                    predicted_route=predicted_route,
                    expected_destination=fixture.expected_destination,
                    predicted_destination=predicted_destination,
                )
            )

        if fixture.category == "negative_domain_specific" and predicted_route == "user":
            domain_specific_user_false_positives.append(fixture.id)

        if fixture.expected_route != "user" and predicted_route == fixture.expected_route:
            if not predicted_destination or predicted_destination == "USER.md":
                missing_narrower_destinations.append(fixture.id)

    exact_accuracy = exact_matches / total if total else 0.0
    user_precision = true_positive_user / predicted_user if predicted_user else None
    user_recall = true_positive_user / expected_user if expected_user else None

    return RoutingBenchmarkReport(
        total=total,
        exact_matches=exact_matches,
        exact_accuracy=exact_accuracy,
        user_precision=user_precision,
        user_recall=user_recall,
        mismatches=mismatches,
        missing_predictions=missing_predictions,
        invalid_routes=invalid_routes,
        domain_specific_user_false_positives=domain_specific_user_false_positives,
        missing_narrower_destinations=missing_narrower_destinations,
    )
