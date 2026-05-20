"""contextops_ese — standalone, harness-agnostic ContextOps/ESE core.

Public surface only. ContextOps/ESE is cognitive-state middleware; it is not
generic Memory/RAG/summary. This package never imports any harness or product
runtime — harnesses adapt to it, never the reverse.
"""

from .contracts import (
    SCHEMA_VERSION,
    ContextPack,
    EvidenceBundle,
    Finding,
    MessageSummary,
    Observation,
    PreviewConfig,
    Recommendation,
    RuntimeEvent,
    SafetyDecision,
    TaskHandoffAckObservation,
)
from .events import ContextOpsEvent, JsonlEventStore, build_event
from .preview import build_context_pack_preview, safe_ref
from .safety import assert_pack_safe, assert_ref_safe, assert_text_safe, scan_unsafe

__all__ = [
    "SCHEMA_VERSION",
    "ContextOpsEvent",
    "ContextPack",
    "EvidenceBundle",
    "Finding",
    "JsonlEventStore",
    "MessageSummary",
    "Observation",
    "PreviewConfig",
    "Recommendation",
    "RuntimeEvent",
    "SafetyDecision",
    "TaskHandoffAckObservation",
    "assert_pack_safe",
    "assert_ref_safe",
    "assert_text_safe",
    "build_context_pack_preview",
    "build_event",
    "safe_ref",
    "scan_unsafe",
]

__version__ = "0.0.1"
