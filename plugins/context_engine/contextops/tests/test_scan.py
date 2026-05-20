"""Golden-fixture tests for the read-only ``contextops scan`` CLI slice."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contextops_ese import SCHEMA_VERSION
from contextops_ese.safety import scan_unsafe
from plugins.context_engine.contextops.scan import (
    SCAN_SCHEMA_VERSION,
    main,
    render_scan_report,
    run_scan,
    scan_cli,
)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "scan_missing_ack_and_passive_wake.json"


def _all_strings(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from _all_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _all_strings(v)
    elif isinstance(value, str):
        yield value


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


def test_run_scan_emits_versioned_findings_with_opaque_provenance():
    report = run_scan(_load_fixture())
    assert report["schema_version"] == SCAN_SCHEMA_VERSION
    # Anchored to the harness-agnostic contract schema so the report rides the
    # same versioned envelope as core DTOs.
    assert report["contract_schema_version"] == SCHEMA_VERSION
    kinds = {finding["kind"] for finding in report["findings"]}
    assert "missing_origin_ack" in kinds
    assert "passive_delivery_mistaken_for_active_wake" in kinds
    for finding in report["findings"]:
        assert finding["finding_ref"].startswith("ref:")
        assert finding["recommendation"]["routing_category"] == "contextops_backlog"
        assert finding["recommendation"]["policy_mode"] == "suggestion_only"
        assert finding["safety_decision"]["mutation_allowed"] is False
        assert finding["safety_decision"]["dispatch_allowed"] is False
        assert finding["safety_decision"]["read_only"] is True
        evidence_refs = finding["evidence"]["evidence_refs"]
        assert evidence_refs
        assert all(ref.startswith("ref:") for ref in evidence_refs)
    overall = report["safety_decision"]
    assert overall["mutation_allowed"] is False
    assert overall["dispatch_allowed"] is False
    assert overall["read_only"] is True


def test_run_scan_is_deterministic_for_same_snapshot():
    a = run_scan(_load_fixture())
    b = run_scan(_load_fixture())
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_run_scan_report_passes_leak_gate():
    report = run_scan(_load_fixture())
    raw = json.dumps(report)
    for forbidden in (
        "t_snap_ack_missing",
        "msg-raw-snap-1",
        "sess-raw-snap-1",
        "evt-raw-snap-1",
        "#contextops-origin",
        "USER:",
        "/home/",
    ):
        assert forbidden not in raw
    for text in _all_strings(report):
        if text.startswith("ref:"):
            continue
        assert scan_unsafe(text) is None, f"leak gate flagged {text!r}"


def test_scan_cli_json_output_matches_run_scan(tmp_path):
    output = scan_cli(["--snapshot", str(FIXTURE_PATH), "--format", "json"])
    parsed = json.loads(output)
    # ``run_scan`` returns the raw report (tuples in evidence_refs etc.);
    # round-tripping it through JSON normalises those tuples to lists so the
    # comparison is structural, not type-bound.
    expected = json.loads(json.dumps(run_scan(_load_fixture())))
    assert parsed == expected


def test_scan_cli_text_output_is_concise_and_leak_safe():
    text = scan_cli(["--snapshot", str(FIXTURE_PATH)])
    assert "ContextOps scan report" in text
    assert "missing_origin_ack" in text
    assert "passive_delivery_mistaken_for_active_wake" in text
    assert "policy: suggestion_only" in text
    assert "read_only=true" in text.lower()
    for forbidden in (
        "t_snap_ack_missing",
        "msg-raw-snap-1",
        "sess-raw-snap-1",
        "evt-raw-snap-1",
        "#contextops-origin",
        "USER:",
        "/home/",
    ):
        assert forbidden not in text
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("ref:"):
            continue
        # Strip embedded opaque refs from the line before leak-scanning; the ref
        # format is the only allowed `ref:<hex>` token in the rendered text.
        scrubbed = " ".join(
            tok for tok in stripped.split() if not tok.startswith("ref:")
        )
        if not scrubbed:
            continue
        assert scan_unsafe(scrubbed) is None, f"text leak gate flagged {scrubbed!r}"


def test_contextops_scan_entrypoint_accepts_product_subcommand(capsys):
    main(["scan", "--snapshot", str(FIXTURE_PATH)])
    out = capsys.readouterr().out
    assert "ContextOps scan report" in out
    assert "missing_origin_ack" in out
    assert "t_snap_ack_missing" not in out


def test_scan_cli_rejects_unknown_snapshot_path(tmp_path):
    missing = tmp_path / "does-not-exist.json"
    with pytest.raises(FileNotFoundError):
        scan_cli(["--snapshot", str(missing)])


def test_run_scan_rejects_unsupported_runtime_event_type():
    fixture = _load_fixture()
    fixture["runtime_events"][0]["kind"] = "totally_unknown_event"
    with pytest.raises(ValueError, match="unsupported runtime event type"):
        run_scan(fixture)


def test_render_scan_report_omits_internal_keys_and_paths():
    report = run_scan(_load_fixture())
    text = render_scan_report(report)
    # The renderer must not echo any raw filesystem hint, including the
    # fixture's own absolute path passed in via the CLI.
    assert str(FIXTURE_PATH) not in text
    assert "/home/" not in text


def test_golden_scan_report_matches_snapshot():
    """The vertical-slice report must be stable for a fixed input snapshot.

    This pins both the set of finding kinds and the operator-facing
    recommendation text so the demo output is deterministic across runs.
    """

    report = run_scan(_load_fixture())
    kinds_to_rec = {
        f["kind"]: f["recommendation"]["suggested_operator_action"]
        for f in report["findings"]
    }
    assert kinds_to_rec == {
        "missing_origin_ack": "Route a final GO/BLOCK/NEED_MORE report to the origin manually",
        "passive_delivery_mistaken_for_active_wake": "Clarify delivery mode or rerun with an explicit active wake boundary",
    }
    assert report["safety_decision"]["policy_mode"] == "suggestion_only"
    # Counts/aggregates the operator sees should be stable too.
    assert report["finding_count"] == 2
    assert report["observation_counts"] == {
        "runtime_events": 2,
        "messages": 1,
        "tasks": 1,
    }
