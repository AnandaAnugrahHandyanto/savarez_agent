"""Safe synchronous primitives for autonomous Hermes production-order execution."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Callable

from .production_order_dispatch import ProfileTaskEnvelope, validate_profile_result_packet


Runner = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class ProfileInvocationResult:
    production_order_id: str
    target_profile: str
    source_state: str
    dispatch_attempt: int
    idempotency_key: str
    timeout_seconds: int | None
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int | None
    log_ref: str
    result_channel: Any = None
    runner_metadata: dict[str, Any] = field(default_factory=dict)


def invoke_profile_task(
    envelope: ProfileTaskEnvelope,
    runner: Runner | None = None,
    timeout_seconds: int | None = None,
) -> ProfileInvocationResult:
    """Invoke exactly one profile task through an injected synchronous runner."""
    if not isinstance(envelope, ProfileTaskEnvelope):
        raise TypeError("invoke_profile_task requires exactly one ProfileTaskEnvelope")
    if runner is None:
        raise ValueError("invoke_profile_task requires an injected synchronous runner")

    payload = envelope.to_dict()
    if timeout_seconds is not None:
        payload["timeout_seconds"] = timeout_seconds

    raw = runner(payload)
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("profile runner must return a dict-like result")

    log_ref = str(
        raw.get("log_ref")
        or raw.get("log_refs")
        or f"profile-invocation:{envelope.idempotency_key}"
    )
    reserved = {
        "stdout",
        "stderr",
        "exit_code",
        "duration_ms",
        "log_ref",
        "log_refs",
        "result_channel",
    }
    metadata = {key: value for key, value in raw.items() if key not in reserved}
    return ProfileInvocationResult(
        production_order_id=envelope.production_order_id,
        target_profile=envelope.target_profile,
        source_state=envelope.source_state,
        dispatch_attempt=envelope.dispatch_attempt,
        idempotency_key=envelope.idempotency_key,
        timeout_seconds=timeout_seconds,
        stdout=str(raw.get("stdout", "") or ""),
        stderr=str(raw.get("stderr", "") or ""),
        exit_code=int(raw.get("exit_code", 0) or 0),
        duration_ms=_maybe_int(raw.get("duration_ms")),
        log_ref=log_ref,
        result_channel=raw.get("result_channel"),
        runner_metadata=metadata,
    )


def collect_profile_result_packet(
    invocation_result: ProfileInvocationResult,
    envelope: ProfileTaskEnvelope,
) -> dict[str, Any]:
    """Extract and validate exactly one structured result packet from one invocation."""
    if not isinstance(invocation_result, ProfileInvocationResult):
        raise TypeError("collect_profile_result_packet requires a ProfileInvocationResult")
    if not isinstance(envelope, ProfileTaskEnvelope):
        raise TypeError("collect_profile_result_packet requires a ProfileTaskEnvelope")
    if invocation_result.production_order_id != envelope.production_order_id:
        raise ValueError("invocation result production_order_id does not match the provided envelope")
    if invocation_result.target_profile != envelope.target_profile:
        raise ValueError("invocation result target_profile does not match the provided envelope")
    if invocation_result.source_state != envelope.source_state:
        raise ValueError("invocation result source_state does not match the provided envelope")
    if invocation_result.exit_code != 0:
        raise ValueError(
            f"profile invocation failed with exit_code={invocation_result.exit_code}"
        )

    packet = _extract_single_packet(invocation_result)
    return validate_profile_result_packet(envelope, packet)


def _extract_single_packet(invocation_result: ProfileInvocationResult) -> dict[str, Any]:
    candidate = invocation_result.result_channel
    if candidate is None:
        text = invocation_result.stdout.strip()
        if not text:
            raise ValueError("profile invocation returned no structured result packet")
        candidate = _parse_packet_text(text)

    if isinstance(candidate, str):
        candidate = _parse_packet_text(candidate.strip())

    if isinstance(candidate, list):
        if len(candidate) != 1:
            raise ValueError("profile invocation returned multiple competing packets")
        candidate = candidate[0]

    if not isinstance(candidate, dict):
        raise ValueError("profile invocation result packet must be a JSON object")
    return dict(candidate)


def _parse_packet_text(text: str) -> Any:
    if not text:
        raise ValueError("profile invocation returned no structured result packet")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        if any(ch in text for ch in "{}[]"):
            raise ValueError("profile invocation returned malformed JSON") from exc
        raise ValueError("profile invocation returned free-text-only output") from exc


def _maybe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)
