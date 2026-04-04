from benchmarks.capabilities import BackendCapabilities
from benchmarks.interface import AggregateResult, CategoryResult, RunResult
from benchmarks.statistical import aggregate_results
from benchmarks.tracks import backend_supports_category, missing_capabilities


def test_missing_capabilities_for_temporal_decay():
    caps = BackendCapabilities()
    assert backend_supports_category(caps, "semantic_recall") is True
    assert backend_supports_category(caps, "temporal_decay") is False
    assert missing_capabilities(caps, "temporal_decay") == ["time_simulation"]


def test_structured_backend_supports_structured_categories_only():
    caps = BackendCapabilities(scopes=True, typed_facts=True, supersession=True)
    assert backend_supports_category(caps, "scopes") is True
    assert backend_supports_category(caps, "notation_parsing") is True
    assert backend_supports_category(caps, "supersession") is True
    assert backend_supports_category(caps, "qlearning") is False


def test_aggregate_results_keeps_core_track_and_coverage():
    run1 = RunResult(
        seed=1,
        results_by_category={
            "semantic_recall": CategoryResult("semantic_recall", total=10, correct=9, score=0.9),
            "scopes": CategoryResult("scopes", total=5, correct=5, score=1.0),
        },
        overall_score=14 / 15,
        core_score=0.9,
        track_scores={"core": 0.9, "structured": 1.0},
        executed_categories=["semantic_recall", "scopes"],
        skipped_categories={"temporal_decay": "missing capabilities: time_simulation"},
        capability_coverage={"scopes": True, "time_simulation": False},
    )
    run2 = RunResult(
        seed=2,
        results_by_category={
            "semantic_recall": CategoryResult("semantic_recall", total=10, correct=10, score=1.0),
            "scopes": CategoryResult("scopes", total=5, correct=4, score=0.8),
        },
        overall_score=14 / 15,
        core_score=1.0,
        track_scores={"core": 1.0, "structured": 0.8},
        executed_categories=["semantic_recall", "scopes"],
        skipped_categories={"temporal_decay": "missing capabilities: time_simulation"},
        capability_coverage={"scopes": True, "time_simulation": False},
    )

    agg = aggregate_results([run1, run2])

    assert agg.core_mean_score == 0.95
    assert agg.track_mean["core"] == 0.95
    assert agg.track_mean["structured"] == 0.9
    assert agg.skipped_categories == {"temporal_decay": "missing capabilities: time_simulation"}
    assert agg.capability_coverage == {"scopes": True, "time_simulation": False}
