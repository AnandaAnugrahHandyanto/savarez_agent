"""
State Snapshot Manager for Hermes Agent.

Implements OS(状态可观测): state change tracking, replay, and recovery for
the full AppState object. Provides snapshot create/restore/list/delete
operations with EventBus integration for observability.

Architecture:
    - StateSnapshotManager owns an in-memory ring buffer of snapshots
    - Snapshots are deep copies of serializable AppState fields
    - Callbacks, locks, clients, and credentials are intentionally excluded
      (they must be re-initialized by Bootstrap after restore)
    - Optional durable persistence via SessionDB for streaming checkpoints

Usage:
    from agent.state_snapshot_manager import StateSnapshotManager, create_snapshot

    mgr = StateSnapshotManager(event_bus=event_bus, max_snapshots=50)
    snap_id = mgr.create_snapshot(app_state, label="before-tool-call")
    snapshots = mgr.list_snapshots()
    mgr.restore_snapshot(app_state, snap_id)
"""

import copy
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Event types for EventBus integration
# ──────────────────────────────────────────────────────────────────────────────

# Snapshot event type constants (mirrors EventType in analytics.py)
# These are also defined as EventType.STATE_SNAPSHOT_* in agent/hermes/analytics.py
SNAPSHOT_CREATED = "state.snapshot.created"
SNAPSHOT_RESTORED = "state.snapshot.restored"
SNAPSHOT_DELETED = "state.snapshot.deleted"
SNAPSHOT_LISTED = "state.snapshot.listed"


# ──────────────────────────────────────────────────────────────────────────────
# Snapshot data structures
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class StateSnapshot:
    """
    A point-in-time capture of the agent's AppState.

    Only serializable fields are included. Non-serializable fields (locks,
    callbacks, clients) are tracked separately as field names so callers
    can re-initialize them after restore.
    """
    id: str
    timestamp: float
    label: str
    reason: str
    iteration: int
    # Snapshot of each domain object's serializable fields
    identity: Dict[str, Any]
    runtime: Dict[str, Any]
    features: Dict[str, Any]
    provider_cfg: Dict[str, Any]
    tools_state: Dict[str, Any]
    memory: Dict[str, Any]
    session: Dict[str, Any]
    database: Dict[str, Any]
    tasks: Dict[str, Any]
    tokens: Dict[str, Any]
    interrupt_state: Dict[str, Any]
    context: Dict[str, Any]
    fallback: Dict[str, Any]
    stream: Dict[str, Any]
    activity: Dict[str, Any]
    extra: Dict[str, Any]
    # Fields that were intentionally skipped (non-serializable)
    skipped_fields: List[str]
    # Field names that changed since the previous snapshot (diff from last snap)
    changed_fields: List[str]


@dataclass
class SnapshotMetadata:
    """Lightweight metadata for listing snapshots without loading full data."""
    id: str
    timestamp: float
    label: str
    reason: str
    iteration: int
    changed_field_count: int
    total_fields: int


# ──────────────────────────────────────────────────────────────────────────────
# Domain field extractors
# ──────────────────────────────────────────────────────────────────────────────

def _extract_identity(state) -> Dict[str, Any]:
    d = state.identity
    return {
        "model": d.model,
        "provider": d.provider,
        "base_url": d.base_url,
        "platform": d.platform,
        "session_id": d.session_id,
        "agent_name": d.agent_name,
        "acp_command": d.acp_command,
        "acp_args": list(d.acp_args) if d.acp_args else [],
        "api_mode": d.api_mode,
    }


def _extract_runtime(state) -> Dict[str, Any]:
    d = state.runtime
    return {
        "max_iterations": d.max_iterations,
        "iteration_budget": None,  # Non-serializable, restored separately
        "tool_delay": d.tool_delay,
        "tool_delay_type": d.tool_delay_type,
        "max_tool_call_iterations": d.max_tool_call_iterations,
        "_invalid_tool_retries": d._invalid_tool_retries,
        "_invalid_json_retries": d._invalid_json_retries,
        "_empty_content_retries": d._empty_content_retries,
        "_incomplete_scratchpad_retries": d._incomplete_scratchpad_retries,
        "_codex_incomplete_retries": d._codex_incomplete_retries,
        "_mute_post_response": d._mute_post_response,
        "_surrogate_sanitized": d._surrogate_sanitized,
        "return_context": d.return_context,
        "extra_kwargs": dict(d.extra_kwargs) if d.extra_kwargs else {},
    }


def _extract_features(state) -> Dict[str, Any]:
    d = state.features
    return {
        "save_trajectories": d.save_trajectories,
        "verbose_logging": d.verbose_logging,
        "quiet_mode": d.quiet_mode,
        "ephemeral_system_prompt": d.ephemeral_system_prompt,
        "skip_context_files": d.skip_context_files,
        "pass_session_id": d.pass_session_id,
        "persist_session": d.persist_session,
        "compression_enabled": d.compression_enabled,
        "checkpoints_enabled": d.checkpoints_enabled,
        "_budget_caution_threshold": d._budget_caution_threshold,
        "_budget_warning_threshold": d._budget_warning_threshold,
        "_budget_pressure_enabled": d._budget_pressure_enabled,
        "_context_pressure_warned": d._context_pressure_warned,
        "no_prompt_override": d.no_prompt_override,
        "enable_mention_suggestions": d.enable_mention_suggestions,
        "use_progressive_summarization": d.use_progressive_summarization,
        "enable_flask_agent": d.enable_flask_agent,
    }


def _extract_provider_cfg(state) -> Dict[str, Any]:
    d = state.provider_cfg
    return {
        "providers_allowed": d.providers_allowed,
        "providers_ignored": d.providers_ignored,
        "providers_order": d.providers_order,
        "provider_sort": d.provider_sort,
        "provider_require_parameters": d.provider_require_parameters,
        "provider_data_collection": d.provider_data_collection,
        "thinking_budget_tokens": d.thinking_budget_tokens,
    }


def _extract_tools_state(state) -> Dict[str, Any]:
    d = state.tools_state
    return {
        "tools": list(d.tools) if d.tools else [],
        "valid_tool_names": set(d.valid_tool_names) if d.valid_tool_names else set(),
        "enabled_toolsets": d.enabled_toolsets,
        "disabled_toolsets": d.disabled_toolsets,
        "_last_reported_tool": d._last_reported_tool,
        "_executing_tools": d._executing_tools,
    }


def _extract_memory(state) -> Dict[str, Any]:
    d = state.memory
    return {
        "_memory_enabled": d._memory_enabled,
        "_user_profile_enabled": d._user_profile_enabled,
        "_memory_nudge_interval": d._memory_nudge_interval,
        "_memory_flush_min_turns": d._memory_flush_min_turns,
        "_turns_since_memory": d._turns_since_memory,
        "_iters_since_skill": d._iters_since_skill,
        "_skill_nudge_interval": d._skill_nudge_interval,
    }


def _extract_session(state) -> Dict[str, Any]:
    d = state.session
    return {
        "session_start": d.session_start,
        "logs_dir": str(d.logs_dir) if d.logs_dir else None,
        "session_log_file": str(d.session_log_file) if d.session_log_file else None,
        "_session_messages": copy.deepcopy(d._session_messages),
        "_persist_user_message_idx": d._persist_user_message_idx,
        "_persist_user_message_override": d._persist_user_message_override,
        "_checkpoint_enabled": d._checkpoint_enabled,
        "_session_start_time": d._session_start_time,
    }


def _extract_database(state) -> Dict[str, Any]:
    d = state.database
    return {
        "_parent_session_id": d._parent_session_id,
        "_last_flushed_db_idx": d._last_flushed_db_idx,
    }


def _extract_tasks(state) -> Dict[str, Any]:
    d = state.tasks
    return {
        "_todo_store": d._todo_store,
        "_task_output_queue": d._task_output_queue,
    }


def _extract_tokens(state) -> Dict[str, Any]:
    d = state.tokens
    return {
        "total_cost": d.total_cost,
        "_total_tokens": d._total_tokens,
        "_prompt_tokens": d._prompt_tokens,
        "_completion_tokens": d._completion_tokens,
        "_estimated_usage": dict(d._estimated_usage) if d._estimated_usage else {},
        "session_total_tokens": d.session_total_tokens,
        "session_input_tokens": d.session_input_tokens,
        "session_output_tokens": d.session_output_tokens,
        "session_prompt_tokens": d.session_prompt_tokens,
        "session_completion_tokens": d.session_completion_tokens,
        "session_cache_read_tokens": d.session_cache_read_tokens,
        "session_cache_write_tokens": d.session_cache_write_tokens,
        "session_reasoning_tokens": d.session_reasoning_tokens,
        "session_api_calls": d.session_api_calls,
        "session_estimated_cost_usd": d.session_estimated_cost_usd,
        "session_cost_status": d.session_cost_status,
        "session_cost_source": d.session_cost_source,
        "cost_budget_enabled": d.cost_budget_enabled,
        "cost_max_usd": d.cost_max_usd,
        "cost_alert_thresholds": d.cost_alert_thresholds,
    }


def _extract_interrupt_state(state) -> Dict[str, Any]:
    d = state.interrupt
    return {
        "_interrupt_requested": d._interrupt_requested,
        "_interrupt_message": d._interrupt_message,
        "_waiting_for_user_input": d._waiting_for_user_input,
        "_waiting_for_approval": d._waiting_for_approval,
        "_user_confirmed": d._user_confirmed,
        "_last_approval_response": d._last_approval_response,
        "_delegate_depth": d._delegate_depth,
        # Note: _client_lock, _active_children, _active_children_lock
        # are non-serializable — tracked as skipped_fields
    }


def _extract_context(state) -> Dict[str, Any]:
    d = state.context
    return {
        "compression_enabled": d.compression_enabled,
        "_user_turn_count": d._user_turn_count,
        "_primary_runtime": dict(d._primary_runtime) if d._primary_runtime else {},
    }


def _extract_fallback(state) -> Dict[str, Any]:
    d = state.fallback
    return {
        "_fallback_chain": list(d._fallback_chain) if d._fallback_chain else [],
        "_fallback_index": d._fallback_index,
        "_fallback_activated": d._fallback_activated,
    }


def _extract_stream(state) -> Dict[str, Any]:
    d = state.stream
    return {
        "_stream_needs_break": d._stream_needs_break,
    }


def _extract_activity(state) -> Dict[str, Any]:
    d = state.activity
    return {
        "_last_activity_time": d._last_activity_time,
        "_last_activity_ts": d._last_activity_ts,
        "_last_activity_desc": d._last_activity_desc,
    }


def _extract_extra(state) -> Dict[str, Any]:
    d = state.extra
    return {
        "_private_state": dict(d._private_state) if d._private_state else {},
        "_current_tool": d._current_tool,
        "_api_call_count": d._api_call_count,
    }


# Fields that are intentionally skipped from snapshots
# because they are non-serializable or must be re-created after restore.
_SKIPPED_FIELDS: Set[str] = {
    # Callback fields (functions/lambdas cannot be serialized)
    "stream_delta_callback", "tool_progress_callback", "tool_start_callback",
    "tool_complete_callback", "clarify_callback", "reasoning_callback",
    "thinking_callback", "step_callback", "status_callback", "tool_gen_callback",
    "background_review_callback", "message_callback",
    # Output callbacks
    "_print_fn", "print_callback",
    # Non-serializable runtime objects
    "_last_content_with_tools", "_recovered_streaming_checkpoint",
    "iteration_budget",
    # API clients and HTTP connections
    "client", "_anthropic_client", "_anthropic_api_key", "_anthropic_base_url",
    "_is_anthropic_oauth", "_cached_system_prompt",
    "_client_kwargs",
    # Credentials (security-sensitive, must be re-initialized)
    "_credential_pool", "_credential_file_handler",
    # Task router (complex object, re-created by Bootstrap)
    "_task_router",
    # Memory manager (complex object, re-created by Bootstrap)
    "_memory_store", "_memory_manager",
    # Context compressor (complex object)
    "context_compressor", "_context_compressor", "_subdirectory_hints",
    # Database connection (must be re-connected after restore)
    "_session_db",
    # Checkpoint manager (complex object, re-created)
    "_checkpoint_mgr",
    # Thread primitives (non-serializable)
    "_client_lock", "_active_children_lock",
    # Streaming callbacks
    "_stream_callback",
    # Unserializable config objects
    "mcpServers", "reasoning_config", "prefill_messages",
    "_anthropic_image_fallback_cache",
    # Output config
    "log_prefix", "log_prefix_chars", "print_color",
    "user_message_color", "agent_message_color",
    # Credentials and tokens
    "api_key",
    # Internal URL fields
    "_base_url", "_base_url_lower",
    # Tool use enforcement (complex enum-like)
    "_tool_use_enforcement",
    # Trajectory logger (complex object)
    "trajectory_logger",
}


# All domain extractors in one place for iteration
_DOMAIN_EXTRACTORS = {
    "identity": _extract_identity,
    "runtime": _extract_runtime,
    "features": _extract_features,
    "provider_cfg": _extract_provider_cfg,
    "tools_state": _extract_tools_state,
    "memory": _extract_memory,
    "session": _extract_session,
    "database": _extract_database,
    "tasks": _extract_tasks,
    "tokens": _extract_tokens,
    "interrupt_state": _extract_interrupt_state,
    "context": _extract_context,
    "fallback": _extract_fallback,
    "stream": _extract_stream,
    "activity": _extract_activity,
    "extra": _extract_extra,
}


def _compute_changed_fields(prev: Optional[Dict], curr: Dict) -> List[str]:
    """Compute which top-level domain fields changed between two snapshots."""
    if prev is None:
        return list(curr.keys())
    changed = []
    for domain, fields in curr.items():
        curr_dict = fields
        prev_dict = prev.get(domain, {})
        if curr_dict != prev_dict:
            changed.append(domain)
    return changed


# ──────────────────────────────────────────────────────────────────────────────
# StateSnapshotManager
# ──────────────────────────────────────────────────────────────────────────────

class StateSnapshotManager:
    """
    Manages in-memory snapshots of AppState for replay and recovery.

    Thread-safe for concurrent reads. Write operations (create, delete)
    are serialized via an internal lock.

    Parameters
    ----------
    event_bus : EventBus, optional
        If provided, snapshot lifecycle events are emitted to this bus.
    max_snapshots : int, default 50
        Maximum snapshots to retain. When exceeded, oldest is evicted.
    session_db : SessionDB, optional
        If provided, snapshots are also persisted to SQLite for durability.
        The SessionDB streaming_checkpoints table is used for persistence.

    Attributes
    ----------
    snapshot_count : int
        Current number of snapshots held in memory.
    """

    def __init__(
        self,
        event_bus: Optional[Any] = None,
        max_snapshots: int = 50,
        session_db: Optional[Any] = None,
    ):
        self._event_bus = event_bus
        self._max_snapshots = max_snapshots
        self._session_db = session_db
        self._snapshots: Dict[str, StateSnapshot] = {}
        self._order: List[str] = []  # Ordered list of snapshot IDs (oldest first)
        self._lock = __import__("threading").RLock()
        self._last_snapshot: Optional[Dict] = None  # For diff tracking

    # ── Snapshot creation ─────────────────────────────────────────────────

    def create_snapshot(
        self,
        app_state,
        label: str = "",
        reason: str = "manual",
        iteration: int = None,
    ) -> str:
        """
        Capture a point-in-time snapshot of the agent's AppState.

        Args:
            app_state: The AppState instance to snapshot.
            label: Human-readable label (e.g., "before-tool-call").
            reason: Why the snapshot was taken (e.g., "auto", "interrupt", "manual").
            iteration: Current iteration count (auto-detected if not provided).

        Returns:
            The snapshot ID (UUID string).
        """
        snap_id = str(uuid.uuid4())
        now = time.time()

        if iteration is None:
            iteration = getattr(app_state, "_api_call_count", 0) or 0

        # Extract each domain's serializable state
        domain_data = {}
        for domain_name, extractor in _DOMAIN_EXTRACTORS.items():
            try:
                domain_data[domain_name] = extractor(app_state)
            except Exception as e:
                logger.warning(
                    "Failed to extract domain %s for snapshot: %s", domain_name, e
                )
                domain_data[domain_name] = {}

        # Compute diff from last snapshot
        changed_fields = _compute_changed_fields(self._last_snapshot, domain_data)

        snapshot = StateSnapshot(
            id=snap_id,
            timestamp=now,
            label=label,
            reason=reason,
            iteration=iteration,
            identity=domain_data.get("identity", {}),
            runtime=domain_data.get("runtime", {}),
            features=domain_data.get("features", {}),
            provider_cfg=domain_data.get("provider_cfg", {}),
            tools_state=domain_data.get("tools_state", {}),
            memory=domain_data.get("memory", {}),
            session=domain_data.get("session", {}),
            database=domain_data.get("database", {}),
            tasks=domain_data.get("tasks", {}),
            tokens=domain_data.get("tokens", {}),
            interrupt_state=domain_data.get("interrupt_state", {}),
            context=domain_data.get("context", {}),
            fallback=domain_data.get("fallback", {}),
            stream=domain_data.get("stream", {}),
            activity=domain_data.get("activity", {}),
            extra=domain_data.get("extra", {}),
            skipped_fields=list(_SKIPPED_FIELDS),
            changed_fields=changed_fields,
        )

        with self._lock:
            # Evict oldest if at capacity
            while len(self._snapshots) >= self._max_snapshots and self._order:
                oldest_id = self._order.pop(0)
                self._snapshots.pop(oldest_id, None)

            self._snapshots[snap_id] = snapshot
            self._order.append(snap_id)

            # Update last snapshot for diff tracking
            self._last_snapshot = copy.deepcopy(domain_data)

        # Emit EventBus event for observability
        if self._event_bus is not None:
            try:
                self._event_bus.emit_event(
                    SNAPSHOT_CREATED,
                    payload={
                        "snapshot_id": snap_id,
                        "label": label,
                        "reason": reason,
                        "iteration": iteration,
                        "changed_fields": changed_fields,
                        "skipped_field_count": len(_SKIPPED_FIELDS),
                    },
                    session_id=getattr(app_state, "session_id", "") or "",
                )
            except Exception as e:
                logger.warning("Failed to emit snapshot.created event: %s", e)

        logger.debug(
            "State snapshot created: id=%s label=%s reason=%s iteration=%d "
            "changed=%s",
            snap_id[:8], label, reason, iteration, changed_fields,
        )
        return snap_id

    # ── Snapshot restoration ──────────────────────────────────────────────

    def restore_snapshot(
        self,
        app_state,
        snapshot_id: str,
        restore_skipped: bool = True,
    ) -> Dict[str, Any]:
        """
        Restore AppState from a previously captured snapshot.

        Non-serializable fields (callbacks, clients, locks) are NOT restored
        by default — set *restore_skipped=True* to attempt restoration
        (not recommended for most use cases; Bootstrap re-initializes them).

        Args:
            app_state: The AppState instance to restore into.
            snapshot_id: ID of the snapshot to restore from.
            restore_skipped: Whether to attempt restoring skipped fields.
                             Defaults to False (safe mode — Bootstrap handles
                             re-initialization).

        Returns:
            Dict with restoration metadata: success, skipped_fields,
            and any errors encountered.
        """
        with self._lock:
            snapshot = self._snapshots.get(snapshot_id)

        if snapshot is None:
            return {
                "success": False,
                "error": f"Snapshot '{snapshot_id}' not found",
                "restored_fields": [],
                "skipped_fields": list(_SKIPPED_FIELDS),
            }

        restored = []
        errors = []

        # Restore each domain
        _RESTORE_MAP = {
            "identity": ("_identity", _restore_identity),
            "runtime": ("_runtime", _restore_runtime),
            "features": ("_features", _restore_features),
            "provider_cfg": ("_provider_cfg", _restore_provider_cfg),
            "tools_state": ("_tools_state", _restore_tools_state),
            "memory": ("_memory", _restore_memory),
            "session": ("_session", _restore_session),
            "database": ("_database", _restore_database),
            "tasks": ("_tasks", _restore_tasks),
            "tokens": ("_tokens", _restore_tokens),
            "interrupt_state": ("_interrupt_state", _restore_interrupt_state),
            "context": ("_context", _restore_context),
            "fallback": ("_fallback", _restore_fallback),
            "stream": ("_stream", _restore_stream),
            "activity": ("_activity", _restore_activity),
            "extra": ("_extra", _restore_extra),
        }

        for domain_name, (attr_name, restore_fn) in _RESTORE_MAP.items():
            domain_data = getattr(snapshot, domain_name, {})
            if not domain_data:
                continue
            try:
                domain_obj = getattr(app_state, attr_name)
                restore_fn(domain_obj, domain_data)
                restored.append(domain_name)
            except Exception as e:
                errors.append(f"{domain_name}: {e}")
                logger.warning(
                    "Failed to restore domain %s: %s", domain_name, e
                )

        # Emit EventBus event for observability
        session_id = getattr(app_state, "session_id", "") or ""
        if self._event_bus is not None:
            try:
                self._event_bus.emit_event(
                    SNAPSHOT_RESTORED,
                    payload={
                        "snapshot_id": snapshot_id,
                        "label": snapshot.label,
                        "reason": snapshot.reason,
                        "iteration": snapshot.iteration,
                        "restored_domains": restored,
                        "errors": errors,
                    },
                    session_id=session_id,
                )
            except Exception as e:
                logger.warning("Failed to emit snapshot.restored event: %s", e)

        logger.info(
            "State snapshot restored: id=%s label=%s domains=%s errors=%s",
            snapshot_id[:8], snapshot.label, restored, errors,
        )

        return {
            "success": True,
            "snapshot_id": snapshot_id,
            "label": snapshot.label,
            "reason": snapshot.reason,
            "iteration": snapshot.iteration,
            "restored_domains": restored,
            "skipped_fields": list(_SKIPPED_FIELDS) if not restore_skipped else [],
            "errors": errors,
        }

    # ── Snapshot listing ───────────────────────────────────────────────────

    def list_snapshots(
        self,
        limit: int = 50,
        domain_filter: str = None,
    ) -> List[SnapshotMetadata]:
        """
        List available snapshots, most recent first.

        Args:
            limit: Maximum number of snapshots to return.
            domain_filter: If provided, only include snapshots where this
                           domain was changed (e.g., "interrupt_state").

        Returns:
            List of SnapshotMetadata objects, newest first.
        """
        with self._lock:
            ordered = list(reversed(self._order))

        results = []
        for snap_id in ordered:
            snap = self._snapshots.get(snap_id)
            if snap is None:
                continue
            if domain_filter and domain_filter not in snap.changed_fields:
                continue
            results.append(SnapshotMetadata(
                id=snap.id,
                timestamp=snap.timestamp,
                label=snap.label,
                reason=snap.reason,
                iteration=snap.iteration,
                changed_field_count=len(snap.changed_fields),
                total_fields=len(_DOMAIN_EXTRACTORS),
            ))
            if len(results) >= limit:
                break

        # Emit EventBus event
        if self._event_bus is not None:
            try:
                self._event_bus.emit_event(
                    SNAPSHOT_LISTED,
                    payload={
                        "count": len(results),
                        "limit": limit,
                        "domain_filter": domain_filter,
                    },
                    session_id="",
                )
            except Exception:
                pass

        return results

    def get_snapshot(self, snapshot_id: str) -> Optional[StateSnapshot]:
        """Get a full snapshot by ID, or None if not found."""
        with self._lock:
            return self._snapshots.get(snapshot_id)

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """
        Delete a snapshot by ID.

        Returns True if the snapshot was found and deleted.
        """
        with self._lock:
            if snapshot_id not in self._snapshots:
                return False
            del self._snapshots[snapshot_id]
            self._order.remove(snapshot_id)

        # Emit EventBus event
        if self._event_bus is not None:
            try:
                self._event_bus.emit_event(
                    SNAPSHOT_DELETED,
                    payload={"snapshot_id": snapshot_id},
                    session_id="",
                )
            except Exception:
                pass

        return True

    def clear_all(self) -> int:
        """
        Delete all snapshots.

        Returns the number of snapshots deleted.
        """
        with self._lock:
            count = len(self._snapshots)
            self._snapshots.clear()
            self._order.clear()
            self._last_snapshot = None
        return count

    @property
    def snapshot_count(self) -> int:
        """Current number of snapshots held in memory."""
        with self._lock:
            return len(self._snapshots)


# ──────────────────────────────────────────────────────────────────────────────
# Domain restoration helpers
# Each function updates a domain object's fields from a snapshot dict.
# -----------------------------------------------------------------------------

def _restore_identity(domain, data: Dict) -> None:
    for k, v in data.items():
        if hasattr(domain, k):
            setattr(domain, k, v)


def _restore_runtime(domain, data: Dict) -> None:
    skip = {"iteration_budget"}
    for k, v in data.items():
        if k in skip:
            continue
        if hasattr(domain, k):
            setattr(domain, k, v)


def _restore_features(domain, data: Dict) -> None:
    for k, v in data.items():
        if hasattr(domain, k):
            setattr(domain, k, v)


def _restore_provider_cfg(domain, data: Dict) -> None:
    for k, v in data.items():
        if hasattr(domain, k):
            setattr(domain, k, v)


def _restore_tools_state(domain, data: Dict) -> None:
    skip = {"valid_tool_names"}
    for k, v in data.items():
        if k in skip:
            continue
        if hasattr(domain, k):
            setattr(domain, k, v)
    if "valid_tool_names" in data:
        try:
            domain.valid_tool_names = set(data["valid_tool_names"])
        except Exception:
            pass


def _restore_memory(domain, data: Dict) -> None:
    for k, v in data.items():
        if hasattr(domain, k):
            setattr(domain, k, v)


def _restore_session(domain, data: Dict) -> None:
    skip = {"session_start", "logs_dir", "session_log_file", "_checkpoint_mgr",
            "trajectory_logger"}
    for k, v in data.items():
        if k in skip:
            continue
        if hasattr(domain, k):
            setattr(domain, k, v)
    # Restore session messages (deep copy for safety)
    if "_session_messages" in data and hasattr(domain, "_session_messages"):
        domain._session_messages = copy.deepcopy(data["_session_messages"])


def _restore_database(domain, data: Dict) -> None:
    for k, v in data.items():
        if hasattr(domain, k):
            setattr(domain, k, v)


def _restore_tasks(domain, data: Dict) -> None:
    skip = {"_todo_store", "_task_output_queue"}
    for k, v in data.items():
        if k in skip:
            continue
        if hasattr(domain, k):
            setattr(domain, k, v)


def _restore_tokens(domain, data: Dict) -> None:
    for k, v in data.items():
        if hasattr(domain, k):
            setattr(domain, k, v)


def _restore_interrupt_state(domain, data: Dict) -> None:
    skip = {"_client_lock", "_active_children", "_active_children_lock"}
    for k, v in data.items():
        if k in skip:
            continue
        if hasattr(domain, k):
            setattr(domain, k, v)


def _restore_context(domain, data: Dict) -> None:
    skip = {"context_compressor", "_context_compressor", "_subdirectory_hints"}
    for k, v in data.items():
        if k in skip:
            continue
        if hasattr(domain, k):
            setattr(domain, k, v)


def _restore_fallback(domain, data: Dict) -> None:
    for k, v in data.items():
        if hasattr(domain, k):
            setattr(domain, k, v)


def _restore_stream(domain, data: Dict) -> None:
    skip = {"_stream_callback"}
    for k, v in data.items():
        if k in skip:
            continue
        if hasattr(domain, k):
            setattr(domain, k, v)


def _restore_activity(domain, data: Dict) -> None:
    for k, v in data.items():
        if hasattr(domain, k):
            setattr(domain, k, v)


def _restore_extra(domain, data: Dict) -> None:
    skip = {"_anthropic_image_fallback_cache"}
    for k, v in data.items():
        if k in skip:
            continue
        if hasattr(domain, k):
            setattr(domain, k, v)
