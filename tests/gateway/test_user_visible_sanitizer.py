import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, SendResult


class _StubAdapter(BasePlatformAdapter):
    def __init__(self):
        super().__init__(PlatformConfig(enabled=True, token="t"), Platform.TELEGRAM)
        self.sent = []

    async def connect(self):
        return True

    async def disconnect(self):
        return None

    async def send(self, chat_id, content, reply_to=None, metadata=None, **kwargs):
        self.sent.append({"chat_id": chat_id, "content": content, "metadata": metadata})
        return SendResult(success=True, message_id="m1")

    async def get_chat_info(self, chat_id):
        return {}


def test_sanitizer_strips_leading_context_compaction_block():
    leaked = """[CONTEXT COMPACTION — REFERENCE ONLY] Earlier turns were compacted into the summary below.
## Active Task
Do not show this.
--- END OF CONTEXT SUMMARY ---

실제 답변입니다."""

    assert _StubAdapter.sanitize_user_visible_content(leaked) == "실제 답변입니다."


def test_sanitizer_uses_safe_fallback_for_unclosed_context_compaction_summary():
    leaked = """[CONTEXT COMPACTION — REFERENCE ONLY] Earlier turns were compacted into the summary below.
## Active Task
None.

## Goal
Do not show this.

## Critical Context
Internal summary body without an END marker."""

    cleaned = _StubAdapter.sanitize_user_visible_content(leaked)

    assert "내부 압축 메모" in cleaned
    assert "Active Task" not in cleaned
    assert "Critical Context" not in cleaned
    assert "Internal summary" not in cleaned


def test_sanitizer_keeps_non_summary_text_after_marker_only_line():
    leaked = """[CONTEXT COMPACTION — REFERENCE ONLY]
사용자에게 보여도 되는 답변"""

    assert _StubAdapter.sanitize_user_visible_content(leaked) == "사용자에게 보여도 되는 답변"


def test_sanitizer_strips_todo_injection_marker_and_bullets():
    leaked = """답변 시작
[Your active task list was preserved across context compression]
- [>] t1. 내부 할일 (in_progress)
- [ ] t2. 다음 내부 할일 (pending)

답변 끝"""

    cleaned = _StubAdapter.sanitize_user_visible_content(leaked)

    assert "Your active task list" not in cleaned
    assert "내부 할일" not in cleaned
    assert cleaned == "답변 시작\n\n답변 끝"


@pytest.mark.asyncio
async def test_send_with_retry_sanitizes_before_send():
    adapter = _StubAdapter()
    await adapter._send_with_retry(
        "chat",
        "[CONTEXT COMPACTION - REFERENCE ONLY]\n--- END OF CONTEXT SUMMARY ---\n\n사용자 답변",
    )

    assert adapter.sent[0]["content"] == "사용자 답변"


def test_sanitizer_returns_safe_fallback_when_only_internal_artifact():
    cleaned = _StubAdapter.sanitize_user_visible_content(
        "[CONTEXT COMPACTION — REFERENCE ONLY]\n--- END OF CONTEXT SUMMARY ---"
    )

    assert "내부 압축 메모" in cleaned
