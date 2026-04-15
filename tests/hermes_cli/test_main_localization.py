import sys

import pytest

from hermes_cli.commands import get_category_label
from hermes_cli.main import main


def test_get_category_label_localizes_builtin_categories():
    assert get_category_label("Session") == "세션"
    assert get_category_label("Configuration") == "설정"
    assert get_category_label("Tools & Skills") == "도구와 스킬"
    assert get_category_label("Info") == "정보"
    assert get_category_label("Exit") == "종료"


def test_main_help_is_localized_to_korean(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["hermes", "--help"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "도구 호출 기능을 갖춘 AI 어시스턴트" in out
    assert "예시:" in out
    assert "실행할 명령어" in out
    assert "버전을 표시하고 종료" in out
    assert "대화형 채팅 시작" in out
