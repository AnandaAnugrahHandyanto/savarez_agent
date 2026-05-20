"""Read-only ChannelWorkingState hydration preview for ContextOps."""

from __future__ import annotations

import argparse
from typing import Any, Literal

from contextops.context_pack import _load_seed, _pressure_heat, build_context_pack
from contextops.models import ContextOpsModel, ContextPack, Tension, Thread

HYDRATION_AUTHORITY = "dry-run/read-only: no gateway restart, no memory write, no message dispatch"
_RECENCY_CONTAMINATION_FLOOR = 0.5
ExclusionCategory = Literal["stale", "contaminating", "low_score"]


class ExcludedCandidate(ContextOpsModel):
    """A thread the preview deliberately did *not* restore, with a reason."""

    kind: Literal["thread"] = "thread"
    id: str
    category: ExclusionCategory
    reason: str
    score: float


class ChannelWorkingState(ContextOpsModel):
    """Hydration preview contract: what a channel turn would restore."""

    channel: str
    message: str
    selected_threads: list[Thread]
    selected_tensions: list[Tension]
    context_pack: ContextPack
    excluded: list[ExcludedCandidate]
    read_only: bool = True


def _exclusion_reason(thread: Thread, open_tensions: list[Tension], score: float) -> tuple[ExclusionCategory, str]:
    """Classify why ``thread`` was not selected for hydration."""

    components = thread.metadata.get("heat_components", {})
    recency = float(components.get("recency", 0.0) or 0.0) if isinstance(components, dict) else 0.0
    pressure_heat = _pressure_heat(thread)
    if recency >= _RECENCY_CONTAMINATION_FLOOR and recency > pressure_heat:
        return ("contaminating", f"ranked on recency ({recency:.2f}) not cognitive pressure ({pressure_heat:.2f}); restoring it would contaminate the phase.")
    if not open_tensions:
        return ("stale", "no open tension anchors this thread; it carries no live pressure worth restoring.")
    return ("low_score", f"score {score:.3f} fell below the context pack selection threshold.")


def build_hydration_preview(channel: str, message: str, seed: dict[str, Any] | str, *, pack_id: str = "pack-contextops") -> ChannelWorkingState:
    """Build a read-only hydration preview for one channel turn."""

    data = _load_seed(seed)
    context_pack = build_context_pack(data, message, pack_id=pack_id)
    selected_thread_ids = set(context_pack.thread_ids)
    selected_tension_ids = set(context_pack.tension_ids)
    threads = [Thread.model_validate(row) for row in data.get("threads", [])]
    tensions = [Tension.model_validate(row) for row in data.get("tensions", [])]
    open_by_thread: dict[str, list[Tension]] = {}
    for tension in tensions:
        if tension.status == "open":
            open_by_thread.setdefault(tension.thread_id, []).append(tension)
    selected_threads = [thread for thread in threads if thread.id in selected_thread_ids]
    selected_threads.sort(key=lambda thread: context_pack.thread_ids.index(thread.id))
    selected_tensions = [tension for tension in tensions if tension.id in selected_tension_ids]
    selected_tensions.sort(key=lambda tension: tension.id)
    scores = context_pack.metadata.get("scores", {})
    excluded: list[ExcludedCandidate] = []
    for thread in threads:
        if thread.id in selected_thread_ids:
            continue
        score = float(scores.get(thread.id, 0.0) or 0.0) if isinstance(scores, dict) else 0.0
        category, reason = _exclusion_reason(thread, open_by_thread.get(thread.id, []), score)
        excluded.append(ExcludedCandidate(id=thread.id, category=category, reason=reason, score=score))
    excluded.sort(key=lambda candidate: candidate.id)
    return ChannelWorkingState(channel=channel, message=message, selected_threads=selected_threads, selected_tensions=selected_tensions, context_pack=context_pack, excluded=excluded, read_only=True)


def render_hydration_preview(state: ChannelWorkingState) -> str:
    """Render a hydration preview as inspectable plain text."""

    lines = [f"ContextOps hydration preview — channel {state.channel}", f"message: {state.message}", f"mode: {HYDRATION_AUTHORITY}", "", f"SELECTED THREADS ({len(state.selected_threads)}):"]
    for thread in state.selected_threads:
        lines.append(f"  - {thread.id} [heat={thread.heat:.2f}, {thread.status}] stance: {thread.stance}")
    lines.extend(["", f"SELECTED TENSIONS ({len(state.selected_tensions)}):"])
    for tension in state.selected_tensions:
        lines.append(f"  - {tension.id} [{tension.thread_id}]: {tension.description}")
    lines.extend(["", f"CONTEXT PACK {state.context_pack.id}:", "  restore:"])
    for item in state.context_pack.restore:
        lines.append(f"    - {item}")
    lines.append("  avoid:")
    for item in state.context_pack.avoid:
        lines.append(f"    - {item}")
    lines.extend(["", f"EXCLUDED CANDIDATES ({len(state.excluded)}):"])
    for candidate in state.excluded:
        lines.append(f"  - {candidate.id} [{candidate.category}, score={candidate.score:.3f}]: {candidate.reason}")
    return "\n".join(lines)


def hydrate_preview_cli(argv: list[str] | None = None) -> str:
    """``contextops hydrate-preview`` command: render an offline preview."""

    parser = argparse.ArgumentParser(prog="contextops hydrate-preview", description="Dry-run ContextOps hydration preview for a channel turn.")
    parser.add_argument("--channel", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--seed", required=True, help="path to a ContextOps seed YAML file")
    parser.add_argument("--pack-id", default="pack-contextops")
    parser.add_argument("--no-dispatch", action="store_true", default=True, help="always on; the preview never dispatches (kept for CLI parity)")
    args = parser.parse_args(argv)
    return render_hydration_preview(build_hydration_preview(args.channel, args.message, args.seed, pack_id=args.pack_id))
