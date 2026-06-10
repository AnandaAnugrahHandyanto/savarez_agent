from pathlib import Path

from gateway.orchestrator_modes import (
    MODE_CLARA_LEAD,
    MODE_HUGO_LEAD,
    handle_lead_slash,
    handle_mode_text,
    mode_system_note,
    parse_mode_request,
    read_mode,
)


def test_natural_korean_mode_commands(tmp_path: Path):
    reply = handle_mode_text("2번 모드", hermes_home=tmp_path, source="test")
    assert reply is not None
    assert "clara-lead" in reply
    assert read_mode(tmp_path)["mode"] == MODE_CLARA_LEAD

    reply = handle_mode_text("현재 모드", hermes_home=tmp_path, source="test")
    assert reply is not None
    assert "clara-lead" in reply

    reply = handle_mode_text("기본 모드로", hermes_home=tmp_path, source="test")
    assert reply is not None
    assert "hugo-lead" in reply
    assert read_mode(tmp_path)["mode"] == MODE_HUGO_LEAD


def test_parse_is_conservative_for_normal_sentences():
    assert parse_mode_request("2번 모드가 좋은 것 같아") is None
    assert parse_mode_request("클라라가 코딩하고 휴고가 리뷰하자") is None


def test_lead_slash_commands_and_system_note(tmp_path: Path):
    assert "hugo-lead" in handle_lead_slash("hugo-lead", hermes_home=tmp_path)
    assert "clara-lead" in handle_lead_slash("clara-lead", hermes_home=tmp_path)
    assert "2번 clara-lead" in mode_system_note(tmp_path)


def test_lead_slash_does_not_accept_legacy_multiplexer(tmp_path: Path):
    reply = handle_lead_slash("orchestrator-mode 2", hermes_home=tmp_path)
    assert "사용법: /hugo-lead 또는 /clara-lead" in reply
