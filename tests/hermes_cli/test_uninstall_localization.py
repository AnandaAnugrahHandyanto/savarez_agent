from pathlib import Path
from types import SimpleNamespace

import pytest

from hermes_cli.uninstall import run_uninstall


def _stub_common(monkeypatch, tmp_path):
    monkeypatch.setattr("hermes_cli.uninstall.get_project_root", lambda: tmp_path / "repo")
    monkeypatch.setattr("hermes_cli.uninstall.get_hermes_home", lambda: tmp_path / ".hermes")
    monkeypatch.setattr("hermes_cli.uninstall.uninstall_gateway_service", lambda: False)
    monkeypatch.setattr("hermes_cli.uninstall.remove_path_from_shell_configs", lambda: [])
    monkeypatch.setattr("hermes_cli.uninstall.remove_wrapper_script", lambda: [])
    monkeypatch.setattr("shutil.rmtree", lambda *_args, **_kwargs: None)


def test_uninstall_keyboard_interrupt_is_localized(monkeypatch, tmp_path, capsys):
    _stub_common(monkeypatch, tmp_path)

    def raise_eof(_prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)

    run_uninstall(SimpleNamespace())

    out = capsys.readouterr().out
    assert "취소했어요." in out


def test_uninstall_cancel_choice_is_localized(monkeypatch, tmp_path, capsys):
    _stub_common(monkeypatch, tmp_path)
    monkeypatch.setattr("builtins.input", lambda _prompt: "3")

    run_uninstall(SimpleNamespace())

    out = capsys.readouterr().out
    assert "제거를 취소했어요." in out


def test_uninstall_keep_data_summary_is_localized(monkeypatch, tmp_path, capsys):
    _stub_common(monkeypatch, tmp_path)
    responses = iter(["1", "yes"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))

    run_uninstall(SimpleNamespace())

    out = capsys.readouterr().out
    assert "Hermes 코드는 제거하지만 설정과 데이터는 유지해요." in out
    assert "게이트웨이 서비스를 찾지 못했어요" in out
    assert "제거할 PATH 항목이 없어요" in out
    assert "래퍼 스크립트를 찾지 못했어요" in out
    assert "설정과 데이터는 그대로 보존했어요:" in out
    assert "나중에 기존 설정으로 다시 설치하려면:" in out
    assert "Hermes Agent를 사용해 주셔서 고마워요!" in out
