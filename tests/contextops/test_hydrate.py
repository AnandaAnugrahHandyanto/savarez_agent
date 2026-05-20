from __future__ import annotations

from pathlib import Path

from contextops.hydrate import ChannelWorkingState, build_hydration_preview, hydrate_preview_cli, render_hydration_preview
from contextops.models import ContextPack

SEED_PATH = Path(__file__).parent / "fixtures" / "epistemic_state_engine_seed.yaml"
PRESSURED_THREAD = "thread:discord:contextops:msg-42"
RECENT_THREAD = "thread:cli:contextops:msg-99"
PRESSURE_MESSAGE = "the unresolved coupling anomaly is recurring; restore that contradiction"


def test_preview_selects_pressured_thread_and_builds_context_pack() -> None:
    state = build_hydration_preview("#contextops", PRESSURE_MESSAGE, SEED_PATH)
    assert isinstance(state, ChannelWorkingState)
    assert state.channel == "#contextops"
    assert [thread.id for thread in state.selected_threads] == [PRESSURED_THREAD]
    assert isinstance(state.context_pack, ContextPack)
    assert state.read_only is True


def test_preview_selected_tensions_are_open_only() -> None:
    state = build_hydration_preview("#contextops", PRESSURE_MESSAGE, SEED_PATH)
    ids = [tension.id for tension in state.selected_tensions]
    assert "tension-coupling" in ids
    assert "tension-pricing" not in ids
    assert all(tension.status == "open" for tension in state.selected_tensions)


def test_preview_excludes_recency_only_thread_with_contaminating_reason() -> None:
    state = build_hydration_preview("#contextops", PRESSURE_MESSAGE, SEED_PATH)
    excluded = {candidate.id: candidate for candidate in state.excluded}
    assert RECENT_THREAD in excluded
    candidate = excluded[RECENT_THREAD]
    assert candidate.category == "contaminating"
    assert "recency" in candidate.reason.lower()


def test_preview_marks_thread_with_no_open_tension_as_stale() -> None:
    state = build_hydration_preview("#contextops", "an unresolved pressure is still open", {"events": [{"id": "evt-a", "source": "s", "text": "pressure event", "refs": ["a"]}, {"id": "evt-b", "source": "s", "text": "calm closed event", "refs": ["b"]}], "threads": [{"id": "thread:x:scope:a", "anchor_event_ids": ["evt-a"], "stance": "keep pushing the open question", "heat": 0.9, "metadata": {"heat_components": {"unresolvedness": 0.8, "contradiction_density": 0.8}}}, {"id": "thread:x:scope:b", "anchor_event_ids": ["evt-b"], "stance": "the settled, already-closed thing", "heat": 0.2, "metadata": {"heat_components": {"recency": 0.1}}}], "tensions": [{"id": "tension-open", "thread_id": "thread:x:scope:a", "description": "still open", "evidence_refs": ["evt-a"], "status": "open"}, {"id": "tension-closed", "thread_id": "thread:x:scope:b", "description": "already closed", "evidence_refs": ["evt-b"], "status": "resolved"}]})
    excluded = {candidate.id: candidate for candidate in state.excluded}
    assert excluded["thread:x:scope:b"].category == "stale"


def test_render_shows_selected_and_excluded_with_reasons() -> None:
    state = build_hydration_preview("#contextops", PRESSURE_MESSAGE, SEED_PATH)
    text = render_hydration_preview(state)
    assert "SELECTED THREADS" in text
    assert "EXCLUDED" in text
    assert PRESSURED_THREAD in text
    assert RECENT_THREAD in text
    assert "recency" in text.lower()


def test_hydrate_preview_cli_runs_offline_from_fixture() -> None:
    text = hydrate_preview_cli(["--channel", "#contextops", "--message", PRESSURE_MESSAGE, "--seed", str(SEED_PATH), "--no-dispatch"])
    assert PRESSURED_THREAD in text
    assert RECENT_THREAD in text
