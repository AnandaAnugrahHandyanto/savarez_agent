"""Regression tests for turn duration display (salvage of #4111).

Verifies:
  - duration string format for sub-minute turns: "3.2s"
  - duration string format for >= 60 s turns: "1m 45s"
  - sub-second turns (< 1.0 s) produce no output (silent)
  - source-inspection: _turn_start captured before def run_agent()
  - source-inspection: _turn_elapsed comparison with 1.0 and 60 present

Uses direct unit tests on the formatting logic (no HermesCLI instantiation).
"""

import inspect


# ---------------------------------------------------------------------------
# Unit tests on the formatting logic (extracted inline)
# ---------------------------------------------------------------------------


def _format_duration(elapsed: float):
    """Mirror of the cli.py turn-duration formatting logic."""
    if elapsed < 1.0:
        return None
    if elapsed >= 60:
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        return f"{mins}m {secs}s"
    return f"{elapsed:.1f}s"


def test_sub_second_turn_is_silent():
    assert _format_duration(0.9) is None
    assert _format_duration(0.0) is None
    assert _format_duration(0.999) is None


def test_exactly_one_second_shows_duration():
    assert _format_duration(1.0) == "1.0s"


def test_sub_minute_format():
    assert _format_duration(3.2) == "3.2s"
    assert _format_duration(59.9) == "59.9s"
    assert _format_duration(10.0) == "10.0s"


def test_minute_boundary():
    assert _format_duration(60.0) == "1m 0s"
    assert _format_duration(60.5) == "1m 0s"   # seconds truncated, not rounded
    assert _format_duration(105.0) == "1m 45s"
    assert _format_duration(3600.0) == "60m 0s"


def test_seconds_truncates_not_rounds():
    # 61.9 → 1m 1s (not 1m 2s)
    assert _format_duration(61.9) == "1m 1s"


# ---------------------------------------------------------------------------
# Source-inspection: wiring present in cli.py
# ---------------------------------------------------------------------------


def test_turn_start_captured_before_run_agent():
    import cli
    src = inspect.getsource(cli)
    ts_idx = src.index("_turn_start = time.time()")
    # search for def run_agent(): starting slightly before ts_idx to allow
    # for the blank line between _turn_start and the def
    ra_idx = src.index("def run_agent():", ts_idx)
    assert ts_idx < ra_idx, "_turn_start must be assigned before def run_agent()"


def test_turn_elapsed_thresholds_present():
    import cli
    src = inspect.getsource(cli)
    assert "_turn_elapsed >= 1.0" in src, "threshold '_turn_elapsed >= 1.0' missing"
    assert "_turn_elapsed >= 60" in src, "minute threshold '_turn_elapsed >= 60' missing"


def test_duration_output_uses_dim_styling():
    import cli
    src = inspect.getsource(cli)
    assert "_dur_str" in src, "_dur_str variable missing"
    # _DIM and _RST must bracket the duration output
    assert "_DIM" in src and "_RST" in src, "_DIM/_RST styling missing from duration output"
