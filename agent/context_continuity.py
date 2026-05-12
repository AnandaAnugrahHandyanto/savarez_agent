"""Context continuity helpers for quality-preserving session handoff.

This module is intentionally separate from ``context_compressor``.  Compression
keeps an oversized session alive; continuity handoff creates an explicit packet
that a fresh session can use to resume work without inheriting all historical
noise.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class ContextContinuityStatus:
    """Inputs used to recommend the next context-continuity action."""

    context_tokens: int = 0
    context_length: int = 0
    remaining_todos: int = 0
    compression_count: int = 0
    high_risk_task: bool = False
    tool_call_count: int = 0
    failed_attempts: int = 0


@dataclass(frozen=True)
class ContextContinuityRecommendation:
    """Recommendation returned by ``recommend_continuity_action``."""

    level: str
    recommended_action: str
    usage_percent: int
    reason: str


def _usage_percent(context_tokens: int, context_length: int) -> int:
    if context_length <= 0:
        return 0
    return max(0, min(100, round((max(0, context_tokens) / context_length) * 100)))


def recommend_continuity_action(
    status: ContextContinuityStatus,
) -> ContextContinuityRecommendation:
    """Recommend continue/checkpoint/handoff/stop based on context risk.

    Policy: handoff is preferred before lossy compression for quality risk;
    compression remains a safety fallback elsewhere.
    """

    pct = _usage_percent(status.context_tokens, status.context_length)
    risk = pct

    if status.high_risk_task:
        risk += 10
    risk += min(10, status.remaining_todos * 2)
    risk += min(8, status.compression_count * 4)
    risk += min(6, status.failed_attempts * 2)
    if status.tool_call_count >= 20:
        risk += 5

    if pct >= 90:
        return ContextContinuityRecommendation(
            level="hard_stop",
            recommended_action="handoff_required",
            usage_percent=pct,
            reason="대화가 한계에 가까워졌습니다. 더 진행하기 전에 새 세션용 이어가기 안내를 만드세요.",
        )
    if pct >= 85 or risk >= 85:
        return ContextContinuityRecommendation(
            level="strong_handoff",
            recommended_action="handoff",
            usage_percent=pct,
            reason="다음 단계는 자동 압축보다 새 세션으로 넘기는 편이 안전합니다.",
        )
    if pct >= 75 or risk >= 75:
        return ContextContinuityRecommendation(
            level="handoff_recommended",
            recommended_action="handoff",
            usage_percent=pct,
            reason="대화가 길어져 품질이 떨어질 수 있습니다. 이어가기 안내를 준비하세요.",
        )
    if pct >= 65 or risk >= 65:
        return ContextContinuityRecommendation(
            level="checkpoint",
            recommended_action="checkpoint",
            usage_percent=pct,
            reason="작업이 길어지고 있습니다. 다음 큰 단계 전에 체크포인트를 남기는 편이 좋습니다.",
        )
    return ContextContinuityRecommendation(
        level="continue",
        recommended_action="continue",
        usage_percent=pct,
        reason="아직 현재 세션에서 계속 진행해도 됩니다.",
    )


def _message_text(message: Mapping[str, Any]) -> str:
    content = message.get("content")
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, Mapping) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(p for p in parts if p).strip()
    return str(content).strip()


def _first_text(messages: Iterable[Mapping[str, Any]], role: str) -> str:
    for msg in messages:
        if msg.get("role") == role:
            text = _message_text(msg)
            if text:
                return text
    return ""


def _last_text(messages: Iterable[Mapping[str, Any]], role: str) -> str:
    last = ""
    for msg in messages:
        if msg.get("role") == role:
            text = _message_text(msg)
            if text:
                last = text
    return last


def _truncate(text: str, limit: int = 700) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def build_handoff_packet(
    messages: list[Mapping[str, Any]],
    *,
    session_id: str | None = None,
    context_tokens: int | None = None,
    context_length: int | None = None,
    current_step: str | None = None,
    title: str | None = None,
) -> str:
    """Build a copy/paste packet for resuming the task in a new session.

    The packet is deterministic and conservative.  It does not pretend to be a
    perfect semantic summary; it tells the next session what to verify and where
    to restart, while preserving the latest user/assistant anchors.
    """

    messages = list(messages or [])
    goal = _first_text(messages, "user") or "Not captured; ask the user to restate the goal."
    latest_user = _last_text(messages, "user") or "No latest user message captured."
    latest_assistant = _last_text(messages, "assistant") or "No assistant progress captured."

    tool_count = sum(1 for m in messages if m.get("role") == "tool")
    user_count = sum(1 for m in messages if m.get("role") == "user")
    assistant_count = sum(1 for m in messages if m.get("role") == "assistant")
    pct = _usage_percent(context_tokens or 0, context_length or 0)
    usage = "unknown"
    if context_tokens is not None and context_length:
        usage = f"{pct}% 사용 중 ({context_tokens:,}/{context_length:,} 토큰)"

    next_step = current_step or "Read this packet, inspect the current files/state, then continue from the latest user request."
    session_line = f"- Source session: {session_id}" if session_id else "- Source session: unknown"
    title_line = f"- Title: {title}" if title else "- Title: unknown"

    return "\n".join(
        [
            "[새 세션 이어가기 안내]",
            "",
            "## 목표",
            f"- {_truncate(goal)}",
            "",
            "## 현재 상태",
            session_line.replace("Source session", "원본 세션"),
            title_line.replace("Title", "제목"),
            f"- 대화 용량: {usage}",
            f"- 포함된 메시지: 사용자 {user_count}개 / Hermes {assistant_count}개 / 도구 {tool_count}개",
            f"- 마지막 사용자 요청: {_truncate(latest_user)}",
            "",
            "## 완료한 일",
            f"- 마지막 진행 요약: {_truncate(latest_assistant)}",
            "- 이 안내는 기준점일 뿐 증명이 아닙니다. 편집 전 관련 파일과 현재 상태를 다시 확인하세요.",
            "",
            "## 남은 일",
            f"- 다음으로 할 일: {_truncate(next_step)}",
            "- 이 안내 뒤의 최신 사용자 요청부터 이어가세요. 이전 완료 작업을 다시 반복하지 마세요.",
            "",
            "## 확인할 것",
            "- 완료라고 말하기 전에 가장 작은 관련 테스트/검사를 다시 실행하세요.",
            "- 이전 도구 출력이 중요하면 요약을 믿지 말고 원본 파일을 읽거나 명령을 다시 실행하세요.",
            "",
            "## 중요한 판단",
            "- 품질이나 장기 작업 연속성이 중요할 때는 손실 압축보다 새 세션 이어가기를 우선합니다.",
            "- 압축은 세션 생존용 안전장치이며, 품질 보존의 기본 경로가 아닙니다.",
            "",
            "## 주의",
            "- 이 안내를 과거 작업을 다시 하라는 요청으로 해석하지 마세요.",
            "- 생성된 요약은 무손실이 아닙니다. 파일, 테스트, 외부 상태를 직접 확인하세요.",
            "",
            "## 다음 세션 시작 방법",
            "1. 이 안내를 먼저 읽습니다.",
            "2. 이 안내 뒤에 있는 최신 사용자 요청을 확인합니다.",
            "3. 그 요청에 필요한 실제 파일/상태를 다시 확인합니다.",
            "4. 가장 작은 안전한 다음 단계부터 진행하고 검증합니다.",
            "",
            "## 완료 기준",
            "- 다음 세션이 숨은 이전 문맥에 의존하지 않고, 무엇을 바꿨고 무엇을 검증했으며 무엇이 남았는지 말할 수 있어야 합니다.",
        ]
    )
