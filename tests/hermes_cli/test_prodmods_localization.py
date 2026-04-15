from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from hermes_cli.backup import run_backup, run_import
from hermes_cli.config import config_command, edit_config
from hermes_cli.debug import run_debug


def test_edit_config_no_editor_is_localized(monkeypatch, tmp_path, capsys):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("hermes_cli.config.get_config_path", lambda: cfg)
    monkeypatch.setattr("shutil.which", lambda _cmd: None)

    edit_config()

    out = capsys.readouterr().out
    assert "에디터를 찾지 못했어요. config 파일 위치:" in out
    assert str(cfg) in out


def test_run_debug_help_is_localized(capsys):
    run_debug(Namespace(debug_command=None))

    out = capsys.readouterr().out
    assert "사용법: hermes debug share" in out
    assert "명령어:" in out
    assert "옵션:" in out
    assert "디버그 리포트를 paste 서비스에 업로드하고 URL 출력" in out


def test_run_backup_empty_is_localized(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("hermes_cli.backup.get_default_hermes_root", lambda: tmp_path)
    monkeypatch.setattr("hermes_cli.backup.display_hermes_home", lambda: str(tmp_path))

    run_backup(Namespace(output=None))

    out = capsys.readouterr().out
    assert "스캔하는 중" in out
    assert "백업할 파일이 없어요." in out


def test_run_import_existing_target_prompt_is_localized(monkeypatch, tmp_path, capsys):
    archive = tmp_path / "backup.zip"
    hermes_root = tmp_path / "target"
    hermes_root.mkdir()
    (hermes_root / "config.yaml").write_text("existing: true\n", encoding="utf-8")

    import zipfile

    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("config.yaml", "model: test\n")

    monkeypatch.setattr("hermes_cli.backup.get_default_hermes_root", lambda: hermes_root)
    monkeypatch.setattr("hermes_cli.backup.display_hermes_home", lambda: str(hermes_root))
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    run_import(Namespace(zipfile=str(archive), force=False))

    out = capsys.readouterr().out
    assert "경고: 대상 디렉터리에 이미 Hermes 설정이 있어요." in out
    assert "가져오기를 진행하면 기존 파일을 백업 내용으로 덮어써요." in out
    assert "중단했어요." in out


def test_run_import_missing_file_is_localized(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        run_import(Namespace(zipfile=str(tmp_path / "missing.zip"), force=False))

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "오류: 파일을 찾지 못했어요:" in out
