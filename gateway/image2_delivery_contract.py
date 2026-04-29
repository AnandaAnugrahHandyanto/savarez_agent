"""Hermes-owned Feishu Image2 delivery contract.

This module builds a native Feishu image-delivery plan only after the deterministic
candidate gate and visual/reviewer gate pass. It deliberately does not send the
image or call Feishu; the live sender/read-back implementation is a later slice.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _accepted_candidate(candidate_gate: Mapping[str, Any]) -> dict[str, Any]:
    accepted = candidate_gate.get("accepted")
    return dict(accepted) if isinstance(accepted, Mapping) else {}


def _thread_target(message: Mapping[str, Any]) -> str:
    for key in ("thread_id", "root_id", "parent_id", "upper_message_id", "feishu_message_id"):
        value = str(message.get(key) or "").strip()
        if value:
            return value
    return ""


def evaluate_delivery_contract(
    *,
    job_dir: Path,
    message: Mapping[str, Any] | None,
    candidate_gate: Mapping[str, Any],
    review_gate: Mapping[str, Any],
    write_result: bool = True,
) -> dict[str, Any]:
    """Build a fail-closed plan for future native Feishu image delivery.

    A ``ready_to_send`` result is not a send result. It means only that the next
    slice may call the Feishu adapter/OpenAPI with this exact chat/thread target
    and image path, then perform exact message read-back.
    """
    root = Path(job_dir)
    msg = dict(message or {})
    accepted = _accepted_candidate(candidate_gate)
    candidate_path = Path(str(accepted.get("path") or "")).expanduser() if accepted.get("path") else None
    chat_id = str(msg.get("chat_id") or "").strip()
    reply_to = _thread_target(msg)
    reasons: list[str] = []

    if candidate_gate.get("status") != "pass" or not accepted:
        reasons.append("candidate_gate_not_pass")
    if not candidate_path or not candidate_path.is_file():
        reasons.append("candidate_file_missing")
    if review_gate.get("status") != "pass":
        reasons.append("review_gate_not_pass")
    if not chat_id:
        reasons.append("missing_chat_id")
    if not reply_to:
        reasons.append("missing_thread_or_root_id")

    ordered_reasons = list(dict.fromkeys(reasons))
    result = {
        "status": "ready_to_send" if not ordered_reasons else "rejected",
        "reasons": ordered_reasons,
        "sent": False,
        "send_method": "feishu_native_image_thread_reply",
        "chat_id": chat_id,
        "reply_to": reply_to,
        "image_path": str(candidate_path) if candidate_path else "",
        "image_sha256": str(accepted.get("sha256") or ""),
        "requires_exact_readback": True,
        "note": "delivery-contract-only; no Feishu API/adapter send was run",
    }
    if write_result:
        root.mkdir(parents=True, exist_ok=True)
        (root / "delivery_plan.json").write_text(_safe_json(result), encoding="utf-8")
    return result
