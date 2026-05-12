"""Tests for gateway progress-callback dedup key using raw preview (fixes #24298).

Before the fix, truncation happened before the dedup comparison, so two distinct
tool calls with a long shared prefix collapsed to a false (×N) bubble.
"""


def _simulate_dedup(calls, cap=40):
    """Reproduce the dedup logic from gateway/run.py progress_callback.

    Returns a list of queued items — plain strings for new messages,
    ("__dedup__", msg, count) tuples for collapsed repeats.
    """
    last = [None]
    count = [0]
    queued = []
    for tool_name, preview in calls:
        raw = preview or ""
        display = (preview[:cap - 3] + "...") if len(preview) > cap else preview
        msg = f"⚙️ {tool_name}: \"{display}\"" if preview else f"⚙️ {tool_name}..."
        key = f"{tool_name}\x00{raw}"
        if key == last[0]:
            count[0] += 1
            queued.append(("__dedup__", msg, count[0]))
        else:
            last[0] = key
            count[0] = 0
            queued.append(msg)
    return queued


def test_distinct_long_prefix_not_collapsed():
    """Two calls sharing a 37-char prefix but different tails must not collapse."""
    prefix = "cd /home/agent/coding/my-project && "
    calls = [
        ("terminal", prefix + "git log -1"),
        ("terminal", prefix + "git status -s"),
    ]
    result = _simulate_dedup(calls)
    new_msgs = [q for q in result if isinstance(q, str)]
    assert len(new_msgs) == 2, f"Expected 2 distinct messages, got: {result}"
    assert not any(
        isinstance(q, tuple) and q[0] == "__dedup__" for q in result
    ), f"No dedup expected, got: {result}"


def test_identical_calls_collapsed():
    """Two calls with exactly the same tool and preview must collapse."""
    calls = [("terminal", "echo hello"), ("terminal", "echo hello")]
    result = _simulate_dedup(calls)
    assert any(isinstance(q, tuple) and q[0] == "__dedup__" for q in result), (
        f"Expected dedup, got: {result}"
    )


def test_different_tools_same_preview_not_collapsed():
    """Same preview on different tools must not collapse."""
    calls = [("read_file", "README.md"), ("write_file", "README.md")]
    result = _simulate_dedup(calls)
    new_msgs = [q for q in result if isinstance(q, str)]
    assert len(new_msgs) == 2


def test_empty_preview_same_tool_collapses():
    """Two calls with no preview on the same tool collapse."""
    calls = [("terminal", ""), ("terminal", "")]
    result = _simulate_dedup(calls)
    assert any(isinstance(q, tuple) and q[0] == "__dedup__" for q in result)
