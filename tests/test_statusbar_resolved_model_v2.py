"""
test_statusbar_resolved_model_v2.py — Validation of the statusbar-resolved-model
feature in the isolated worktree (no overlay dependency).

Tests are static/structural: they verify the code contains the expected
patterns without making real API calls.

Usage:
  python3 tests/test_statusbar_resolved_model_v2.py <repo-root>
  pytest tests/test_statusbar_resolved_model_v2.py <repo-root> -x
"""

import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(repo_path: str) -> dict[str, str]:
    """Return {'run_agent': source, 'cli': source} for the repo under *repo_path*."""
    base = Path(repo_path)
    return {
        "run_agent": (base / "run_agent.py").read_text(encoding="utf-8"),
        "cli": (base / "cli.py").read_text(encoding="utf-8"),
    }


def _assert(desc: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(f"FAIL: {desc}")
    print(f"  PASS  {desc}")


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_resolved_model_set_from_response(src: dict[str, str]):
    """run_agent.py: _resolved_model is assigned from response.model when
    the response is valid and the resolved model differs from self.model."""
    run = src["run_agent"]
    _assert("_resolved_model = _resp_model present",
            "self._resolved_model = _resp_model" in run)
    _assert("response.model is read",
            "hasattr(response, \"model\")" in run or "response.model" in run)
    _assert("resolved differs from self.model guard",
            "_resp_model != self.model" in run or "_resp_model and _resp_model != self.model" in run)


def test_resolved_context_length_set(src: dict[str, str]):
    """run_agent.py: _resolved_context_length and _resolved_context_model are
    populated via get_model_context_length()."""
    run = src["run_agent"]
    _assert("_resolved_context_length assigned",
            "self._resolved_context_length = _real_ctx" in run)
    _assert("_resolved_context_model assigned",
            "self._resolved_context_model = _resp_model" in run)
    _assert("get_model_context_length called",
            "get_model_context_length(" in run)


def test_compressor_update_called(src: dict[str, str]):
    """run_agent.py: context_compressor.update_model() is called with the
    resolved model so the compressor uses the correct context window."""
    run = src["run_agent"]
    _assert("context_compressor.update_model() called",
            "_compressor.update_model(" in run)
    _assert("update_model receives _resp_model",
            "model=_resp_model" in run)


def test_self_model_not_overwritten(src: dict[str, str]):
    """run_agent.py: self.model is NOT overwritten by response.model.
    The user-configured model must remain intact for fallback/retry logic."""
    run = src["run_agent"]
    lines = run.splitlines()
    bad_lines = [
        (i + 1, l.strip())
        for i, l in enumerate(lines)
        if l.strip().startswith("self.model =") and "response.model" in l
    ]
    _assert("self.model never assigned from response.model", len(bad_lines) == 0)


def test_status_bar_prefers_resolved_model(src: dict[str, str]):
    """cli.py: _get_status_bar_snapshot() prefers agent._resolved_model over
    agent.model in the fallback chain."""
    cli = src["cli"]
    _assert("_resolved_model consulted in status bar",
            'getattr(agent, "_resolved_model", None)' in cli)
    # _resolved_model must appear BEFORE agent.model in the chain
    resolved_pos = cli.index('getattr(agent, "_resolved_model"')
    agent_model_pos = cli.index('getattr(agent, "model"')
    _assert("_resolved_model precedes agent.model in fallback chain",
            resolved_pos < agent_model_pos)


def test_status_bar_prefers_resolved_context_length(src: dict[str, str]):
    """cli.py: _get_status_bar_snapshot() prefers agent._resolved_context_length
    over compressor.context_length."""
    cli = src["cli"]
    _assert("_resolved_context_length consulted",
            '"_resolved_context_length"' in cli)
    resolved_ctx_pos = cli.index('"_resolved_context_length"')
    # Find "context_length" that appears AFTER the resolved one
    compressor_ctx_pos = cli.index('"context_length"', resolved_ctx_pos)
    _assert("_resolved_context_length precedes compressor.context_length",
            resolved_ctx_pos < compressor_ctx_pos)


def test_no_overlay_dependency(src: dict[str, str]):
    """Neither file references HUP/overlay machinery."""
    for name, source in src.items():
        _assert(f"{name}: no 'apply-overlays' reference",
                "apply-overlays" not in source)
        _assert(f"{name}: no 'hup-auto' reference",
                "hup-auto" not in source)
        _assert(f"{name}: no 'mastertrend-overlays' path reference",
                "mastertrend-overlays" not in source)


def test_resolved_model_error_handling(src: dict[str, str]):
    """run_agent.py: context-resolution errors are caught gracefully
    (try/except with pass so existing context is preserved on failure)."""
    run = src["run_agent"]
    # The except clause should exist and swallow errors silently
    _assert("try/except around context resolution",
            "except Exception:" in run and "pass  # keep current context" in run)


def test_status_bar_unknown_fallback(src: dict[str, str]):
    """cli.py: status bar still shows 'unknown' when no model info is available."""
    cli = src["cli"]
    _assert('"unknown" fallback in model_name chain',
            '"unknown"' in cli)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

TESTS = [
    ("resolved_model_set_from_response", test_resolved_model_set_from_response),
    ("resolved_context_length_set", test_resolved_context_length_set),
    ("compressor_update_called", test_compressor_update_called),
    ("self_model_not_overwritten", test_self_model_not_overwritten),
    ("status_bar_prefers_resolved_model", test_status_bar_prefers_resolved_model),
    ("status_bar_prefers_resolved_context_length", test_status_bar_prefers_resolved_context_length),
    ("no_overlay_dependency", test_no_overlay_dependency),
    ("resolved_model_error_handling", test_resolved_model_error_handling),
    ("status_bar_unknown_fallback", test_status_bar_unknown_fallback),
]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <repo-path>")
        sys.exit(1)

    repo = sys.argv[1]
    sources = _load(repo)

    passed = 0
    failed = 0
    for name, fn in TESTS:
        try:
            fn(sources)
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {name}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)