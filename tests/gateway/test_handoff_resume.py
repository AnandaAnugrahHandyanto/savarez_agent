"""Tests for handoff resume trigger helpers."""

from types import SimpleNamespace

from gateway.config import Platform
from gateway.handoff_pack import (
    build_handoff_pack,
    build_handoff_reference,
    find_latest_handoff,
    should_resume_from_handoff,
    write_handoff_pack,
)
from gateway.session import SessionSource


def _source():
    return SessionSource(
        platform=Platform.SLACK,
        chat_id="C123",
        thread_id="177.1",
        user_id="U123",
        user_name="tester",
        chat_type="thread",
    )


def test_resume_request_can_load_latest_handoff_reference(tmp_path):
    source = _source()
    pack = build_handoff_pack(
        session_entry=SimpleNamespace(session_id="20260525_120000_deadbeef"),
        source=source,
        messages=[{"role": "user", "content": "현재 작업은 handoff 구현"}],
        created_at="2026-05-25T12:00:00+00:00",
    )
    paths = write_handoff_pack(pack, base_dir=tmp_path)

    assert should_resume_from_handoff("handoff 읽고 이어가")
    assert find_latest_handoff(source, base_dir=tmp_path) == paths.latest_summary_path
    reference = build_handoff_reference(paths.latest_summary_path)
    assert "REFERENCE ONLY" in reference
    assert "현재 작업은 handoff 구현" in reference
