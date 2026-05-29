"""UI-side contract tests for the Kanban dashboard Spearhead facets.

The card chips, the drawer's Spearhead summary panel, and the toolbar's
attention filter all derive their behaviour from one pure, framework-free
block in ``plugins/kanban/dashboard/dist/index.js`` delimited by
``// <facet-logic>`` / ``// </facet-logic>`` markers.

Rather than duplicate that JS logic in Python (which would drift), we
extract the block verbatim, evaluate it under Node, and assert the derived
attention bucket / chip ordering for representative cards that mirror the
parser fixture categories from the parent parser task (planning,
review-required, monitor, recovery, scheduled, malformed/no-frontmatter)
plus the worker-fixable diagnostic case.

Skips cleanly when Node is unavailable so the broader pytest run is not
blocked on a JS runtime.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

INDEX_JS = (
    Path(__file__).resolve().parents[2]
    / "plugins" / "kanban" / "dashboard" / "dist" / "index.js"
)

_MARKER_RE = re.compile(
    r"//\s*<facet-logic>(?P<body>.*?)//\s*</facet-logic>",
    re.DOTALL,
)


def _extract_facet_logic() -> str:
    text = INDEX_JS.read_text(encoding="utf-8")
    m = _MARKER_RE.search(text)
    assert m, "facet-logic sentinel block not found in dist/index.js"
    return m.group("body")


def _run_node(fixtures: list[dict]) -> list[dict]:
    node = shutil.which("node")
    if node is None:  # pragma: no cover - environment dependent
        pytest.skip("node runtime not available")
    block = _extract_facet_logic()
    driver = (
        block
        + "\n"
        + "const fixtures = JSON.parse(process.env.HERMES_FACET_FIXTURES);\n"
        + "const out = fixtures.map(function (fx) {\n"
        + "  return {\n"
        + "    name: fx.name,\n"
        + "    bucket: facetBucket(fx.task),\n"
        + "    hasAny: hasAnyFacet(fx.task),\n"
        + "    chips: facetChipSpecs(fx.task).map(function (s) {\n"
        + "      return { kind: s.kind, value: s.value, tone: s.tone };\n"
        + "    }),\n"
        + "    origin: facetOriginSummary(fx.task),\n"
        + "    bucketKeys: FACET_BUCKETS.map(function (b) { return b.key; }),\n"
        + "  };\n"
        + "});\n"
        + "process.stdout.write(JSON.stringify(out));\n"
    )
    import os

    env = dict(os.environ, HERMES_FACET_FIXTURES=json.dumps(fixtures))
    proc = subprocess.run(
        [node, "-e", driver],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert proc.returncode == 0, f"node failed: {proc.stderr}"
    return json.loads(proc.stdout)


def _task(facets=None, warnings=None) -> dict:
    return {"facets": facets or {}, "warnings": warnings}


FIXTURES = [
    {
        "name": "planning",
        "task": _task({"work_mode": "planning"}),
    },
    {
        "name": "review-required",
        "task": _task(
            {"handoff_state": "review-required", "review_gate": "human-review"}
        ),
    },
    {
        "name": "monitor",
        "task": _task({"monitor_state": "monitoring", "handoff_state": "waiting"}),
    },
    {
        "name": "scheduled",
        "task": _task({"monitor_state": "scheduled", "handoff_state": "waiting"}),
    },
    {
        "name": "recovery",
        "task": _task({"work_mode": "recovery", "handoff_state": "needs-recovery"}),
    },
    {
        "name": "worker-fixable",
        "task": _task({}, warnings={"count": 2, "highest_severity": "error"}),
    },
    {
        "name": "no-facets",
        "task": _task({}),
    },
    {
        "name": "needs-human-beats-recovery",
        "task": _task({"review_gate": "human-review", "work_mode": "recovery"}),
    },
    {
        "name": "with-origin",
        "task": _task(
            {
                "work_mode": "planning",
                "origin_kind": "notion",
                "origin_key": "abc",
                "origin_fingerprint": "deadbeef",
            }
        ),
    },
]


@pytest.fixture(scope="module")
def results() -> dict[str, dict]:
    out = _run_node(FIXTURES)
    return {r["name"]: r for r in out}


def test_markers_present_and_extractable():
    block = _extract_facet_logic()
    for fn in ("facetBucket", "facetChipSpecs", "facetOriginSummary", "hasAnyFacet"):
        assert fn in block, f"{fn} missing from facet-logic block"
    # The pure block must not reference React/SDK globals. Strip `//` line
    # comments first so the block's own explanatory prose (which names React,
    # SDK, h(), etc. to warn future editors) doesn't trip the check.
    code_only = "\n".join(
        line.split("//", 1)[0] for line in block.splitlines()
    )
    for forbidden in ("React", "SDK", "createElement", "useState", "useMemo"):
        assert forbidden not in code_only, (
            f"facet-logic block leaks UI dependency: {forbidden!r}"
        )


def test_bucket_assignment(results):
    assert results["planning"]["bucket"] is None
    assert results["review-required"]["bucket"] == "needs-human"
    assert results["monitor"]["bucket"] == "waiting"
    assert results["scheduled"]["bucket"] == "waiting"
    assert results["recovery"]["bucket"] == "recovery"
    assert results["worker-fixable"]["bucket"] == "worker-fixable"
    assert results["no-facets"]["bucket"] is None


def test_bucket_precedence_human_beats_recovery(results):
    # A human review gate must win over a recovery work mode.
    assert results["needs-human-beats-recovery"]["bucket"] == "needs-human"


def test_filter_buckets_cover_required_four(results):
    keys = set(results["planning"]["bucketKeys"])
    assert keys == {"needs-human", "waiting", "recovery", "worker-fixable"}


def test_chip_order_mode_then_handoff(results):
    chips = results["recovery"]["chips"]
    assert [c["kind"] for c in chips] == ["mode", "handoff"]
    assert chips[0]["value"] == "recovery"
    assert chips[0]["tone"] == "recovery"
    assert chips[1]["value"] == "needs-recovery"


def test_review_gate_not_duplicated_when_handoff_review_required(results):
    # review_gate chip is suppressed when handoff already says review-required.
    chips = results["review-required"]["chips"]
    kinds = [c["kind"] for c in chips]
    assert kinds == ["handoff"]
    assert chips[0]["tone"] == "human"


def test_monitor_chip_tone(results):
    chips = results["monitor"]["chips"]
    kinds = [c["kind"] for c in chips]
    assert kinds == ["handoff", "monitor"]
    assert chips[-1]["tone"] == "waiting"


def test_has_any_facet_and_origin(results):
    assert results["no-facets"]["hasAny"] is False
    assert results["planning"]["hasAny"] is True
    origin = results["with-origin"]["origin"]
    assert origin == {"kind": "notion", "key": "abc", "fingerprint": "deadbeef"}
    assert results["planning"]["origin"] is None
