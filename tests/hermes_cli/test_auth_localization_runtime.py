from types import SimpleNamespace
import sys
import types

import pytest

from hermes_cli.auth import (
    AuthError,
    _login_openai_codex,
    _prompt_model_selection,
    format_auth_error,
    login_command,
    logout_command,
)


def test_format_auth_error_subscription_and_relogin_are_localized():
    relogin_error = AuthError("토큰이 만료되었어요.", relogin_required=True)
    subscription_error = AuthError("subscription missing", code="subscription_required")

    assert "다시 인증하려면 `hermes model`" in format_auth_error(relogin_error)
    assert "활성화된 유료 구독을 찾지 못했어요" in format_auth_error(subscription_error)


def test_prompt_model_selection_fallback_is_localized(monkeypatch, capsys):
    responses = iter(["abc"])

    def fake_input(_prompt):
        try:
            return next(responses)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)

    selected = _prompt_model_selection(["gpt-4.1", "gpt-4o-mini"], current_model="gpt-4.1")

    out = capsys.readouterr().out
    assert selected is None
    assert "기본 모델 선택:" in out
    assert "gpt-4.1  ← 현재 사용 중" in out
    assert "사용자 지정 모델 이름 입력" in out
    assert "건너뛰기(현재 설정 유지)" in out
    assert "숫자를 입력해 주세요" in out


class _FakeTerminalMenu:
    last_choices = None
    last_title = None

    def __init__(self, choices, **kwargs):
        _FakeTerminalMenu.last_choices = choices
        _FakeTerminalMenu.last_title = kwargs.get("title")
        self._cursor_index = kwargs.get("cursor_index")

    def show(self):
        return self._cursor_index


def test_prompt_model_selection_terminal_menu_is_localized(monkeypatch):
    monkeypatch.setitem(sys.modules, "simple_term_menu", types.SimpleNamespace(TerminalMenu=_FakeTerminalMenu))
    monkeypatch.setattr("hermes_cli.curses_ui.flush_stdin", lambda: None)

    selected = _prompt_model_selection(["gpt-4.1", "gpt-4o-mini"], current_model="gpt-4.1")

    assert selected == "gpt-4.1"
    assert _FakeTerminalMenu.last_title == "기본 모델 선택:"
    assert _FakeTerminalMenu.last_choices[:3] == [
        "  gpt-4.1  ← 현재 사용 중",
        "  gpt-4o-mini",
        "  사용자 지정 모델 이름 입력",
    ]



def test_login_command_deprecation_is_localized(capsys):
    with pytest.raises(SystemExit) as exc:
        login_command(SimpleNamespace())

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "'hermes login' 명령은 제거되었어요." in out
    assert "자격 증명 관리는 'hermes auth'" in out


def test_login_openai_codex_reuse_prompt_is_localized(monkeypatch, capsys):
    monkeypatch.setattr(
        "hermes_cli.auth.resolve_codex_runtime_credentials",
        lambda: {"api_key": "tok", "base_url": "https://example.com/codex"},
    )
    monkeypatch.setattr("hermes_cli.auth._codex_access_token_is_expiring", lambda *_args, **_kwargs: False)
    monkeypatch.setattr("hermes_cli.auth._update_config_for_provider", lambda *_args, **_kwargs: "/tmp/config.yaml")
    monkeypatch.setattr("builtins.input", lambda _prompt: "")

    _login_openai_codex(SimpleNamespace(), None)

    out = capsys.readouterr().out
    assert "Hermes auth store에서 기존 Codex 자격 증명을 찾았어요." in out
    assert "로그인에 성공했어요!" in out
    assert "설정 업데이트: /tmp/config.yaml" in out


def test_logout_command_is_localized(monkeypatch, capsys):
    monkeypatch.setattr("hermes_cli.auth.get_active_provider", lambda: None)
    logout_command(SimpleNamespace(provider=None))
    out = capsys.readouterr().out
    assert "현재 로그인된 provider가 없어요." in out

    with pytest.raises(SystemExit) as exc:
        logout_command(SimpleNamespace(provider="mystery"))
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "알 수 없는 provider예요: mystery" in out

    monkeypatch.setattr("hermes_cli.auth.get_active_provider", lambda: "openai-codex")
    monkeypatch.setattr("hermes_cli.auth.clear_provider_auth", lambda _provider: True)
    monkeypatch.setattr("hermes_cli.auth._reset_config_provider", lambda: None)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    logout_command(SimpleNamespace(provider=None))
    out = capsys.readouterr().out
    assert "OpenAI Codex 에서 로그아웃했어요." in out
    assert "Hermes는 추론에 OpenRouter를 사용할 거예요." in out
