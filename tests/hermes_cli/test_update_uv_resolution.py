from pathlib import Path


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")
    path.chmod(0o755)
    return path


def test_resolve_uv_binary_prefers_venv_uv_over_path(tmp_path, monkeypatch):
    from hermes_cli import main as main_mod

    project_root = tmp_path / "repo"
    venv_uv = _touch(project_root / "venv" / "bin" / "uv")
    path_uv = _touch(tmp_path / "anaconda3" / "bin" / "uv")

    monkeypatch.setattr(main_mod, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(main_mod.sys, "prefix", str(tmp_path / "python"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setattr(main_mod.shutil, "which", lambda name: str(path_uv))

    assert main_mod._resolve_uv_binary() == str(venv_uv)


def test_resolve_uv_binary_prefers_astral_user_uv_over_path(tmp_path, monkeypatch):
    from hermes_cli import main as main_mod

    project_root = tmp_path / "repo"
    managed_uv = _touch(tmp_path / "home" / ".local" / "bin" / "uv")
    path_uv = _touch(tmp_path / "anaconda3" / "bin" / "uv")

    monkeypatch.setattr(main_mod, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(main_mod.sys, "prefix", str(tmp_path / "python"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setattr(main_mod.shutil, "which", lambda name: str(path_uv))

    assert main_mod._resolve_uv_binary() == str(managed_uv)


def test_python_update_validation_checks_known_compiled_imports_and_wheel_tags():
    from hermes_cli import main as main_mod

    code = main_mod._python_update_validation_code()

    assert "from frozenlist import FrozenList" in code
    assert "from multidict import CIMultiDict, MultiDict" in code
    assert 'hasattr(aiohttp, "ClientSession")' in code
    assert "uvicorn.protocols.websockets.websockets_impl" in code
    assert "*.dist-info/WHEEL" in code
    assert "binary wheel tag mismatch" in code
