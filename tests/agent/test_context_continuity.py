"""Tests for Context Continuity Manager handoff packet generation."""

from agent.context_continuity import (
    ContextContinuityStatus,
    build_handoff_packet,
    recommend_continuity_action,
)
from hermes_cli.commands import resolve_command


def test_handoff_packet_is_structured_for_new_session_resume():
    messages = [
        {"role": "user", "content": "Build Context Continuity Manager for long sessions."},
        {"role": "assistant", "content": "Plan: add a handoff packet first."},
        {"role": "tool", "name": "read_file", "content": "read cli.py"},
        {"role": "assistant", "content": "Implemented tests for the handoff generator."},
    ]

    packet = build_handoff_packet(
        messages,
        session_id="sess-123",
        context_tokens=75000,
        context_length=100000,
        current_step="Add CLI /handoff command",
    )

    assert packet.startswith("[새 세션 이어가기 안내]")
    for heading in [
        "## 목표",
        "## 현재 상태",
        "## 완료한 일",
        "## 남은 일",
        "## 확인할 것",
        "## 중요한 판단",
        "## 주의",
        "## 다음 세션 시작 방법",
        "## 완료 기준",
    ]:
        assert heading in packet
    assert "sess-123" in packet
    assert "75%" in packet
    assert "Build Context Continuity Manager" in packet
    assert "Add CLI /handoff command" in packet
    assert "최신 사용자 요청부터 이어가세요" in packet


def test_recommend_continuity_action_prefers_handoff_before_compression():
    status = recommend_continuity_action(
        ContextContinuityStatus(
            context_tokens=85000,
            context_length=100000,
            remaining_todos=3,
            compression_count=0,
            high_risk_task=True,
        )
    )

    assert status.level == "strong_handoff"
    assert status.recommended_action == "handoff"
    assert "새 세션" in status.reason


def test_handoff_command_registered():
    cmd = resolve_command("handoff")
    assert cmd is not None
    assert cmd.name == "handoff"
    assert "이어가기 안내" in cmd.description
