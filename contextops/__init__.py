"""ContextOps Epistemic State Engine prototype substrate."""

from contextops.context_pack import build_context_pack
from contextops.extractor import StateDeltaProposal, extract_state_deltas
from contextops.hydrate import (
    ChannelWorkingState,
    ExcludedCandidate,
    build_hydration_preview,
    hydrate_preview_cli,
    render_hydration_preview,
)
from contextops.models import ContextPack, Event, StateDelta, Tension, Thread
from contextops.router import RouteProposal, route_context_event
from contextops.store import ContextOpsStore, default_store_root

try:
    from contextops.eval import (
        CONTEXT_VARIANTS,
        RUBRIC_FIELDS,
        EvalReport,
        load_eval_fixture,
        render_eval_report,
        run_context_pack_eval,
    )
except ModuleNotFoundError:  # optional Wave2 eval file may be absent in this shared dir
    CONTEXT_VARIANTS = ()
    RUBRIC_FIELDS = ()
    EvalReport = None  # type: ignore[assignment]
    load_eval_fixture = None  # type: ignore[assignment]
    render_eval_report = None  # type: ignore[assignment]
    run_context_pack_eval = None  # type: ignore[assignment]

__all__ = [
    "CONTEXT_VARIANTS",
    "ChannelWorkingState",
    "ContextOpsStore",
    "ContextPack",
    "Event",
    "EvalReport",
    "ExcludedCandidate",
    "RUBRIC_FIELDS",
    "RouteProposal",
    "StateDelta",
    "StateDeltaProposal",
    "Tension",
    "Thread",
    "build_context_pack",
    "build_hydration_preview",
    "default_store_root",
    "extract_state_deltas",
    "hydrate_preview_cli",
    "load_eval_fixture",
    "render_eval_report",
    "render_hydration_preview",
    "route_context_event",
    "run_context_pack_eval",
]
