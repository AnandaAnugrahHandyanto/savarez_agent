from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "optional-skills"
    / "observability"
    / "langfuse-tracing"
    / "scripts"
    / "setup_langfuse_env.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("langfuse_tracing_skill", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def clear_langfuse_env(monkeypatch):
    for name in (
        "HERMES_LANGFUSE_ENABLED",
        "TRACE_TO_LANGFUSE",
        "CC_LANGFUSE_ENABLED",
        "HERMES_LANGFUSE_PUBLIC_KEY",
        "CC_LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_PUBLIC_KEY",
        "HERMES_LANGFUSE_SECRET_KEY",
        "CC_LANGFUSE_SECRET_KEY",
        "LANGFUSE_SECRET_KEY",
        "HERMES_LANGFUSE_BASE_URL",
        "CC_LANGFUSE_BASE_URL",
        "LANGFUSE_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_ensure_langfuse_env_copies_missing_values_from_shell(tmp_path: Path, monkeypatch):
    clear_langfuse_env(monkeypatch)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-from-shell")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-from-shell")
    mod = load_module()
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://localhost:3000")

    result = mod.ensure_langfuse_env()
    env_text = (tmp_path / ".hermes" / ".env").read_text(encoding="utf-8")

    assert result["success"] is True
    assert "HERMES_LANGFUSE_ENABLED=true" in env_text
    assert "HERMES_LANGFUSE_PUBLIC_KEY=pk-from-shell" in env_text
    assert "HERMES_LANGFUSE_SECRET_KEY=" in env_text
    assert "HERMES_LANGFUSE_BASE_URL=http://localhost:3000" in env_text
    assert result["missing"] == []


def test_ensure_langfuse_env_preserves_existing_alias_values(tmp_path: Path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    mod = load_module()
    hermes_home.mkdir(parents=True, exist_ok=True)
    (hermes_home / ".env").write_text(
        "TRACE_TO_LANGFUSE=true\n"
        "LANGFUSE_PUBLIC_KEY=pk-existing\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-new")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-new")

    result = mod.ensure_langfuse_env()
    env_text = (hermes_home / ".env").read_text(encoding="utf-8")

    assert "TRACE_TO_LANGFUSE=true" in env_text
    assert "LANGFUSE_PUBLIC_KEY=pk-existing" in env_text
    assert "HERMES_LANGFUSE_SECRET_KEY=" in env_text
    assert result["preserved"]["HERMES_LANGFUSE_ENABLED"] == "TRACE_TO_LANGFUSE"
    assert result["preserved"]["HERMES_LANGFUSE_PUBLIC_KEY"] == "LANGFUSE_PUBLIC_KEY"


def test_ensure_langfuse_plugin_fetches_and_installs_files(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    mod = load_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(mod, "_repo_root", lambda: repo_root)

    calls: list[list[str]] = []

    def fake_run(argv, *, cwd=None, capture_output=True):
        calls.append(argv)
        if argv[:3] == ["git", "rev-parse", "--verify"]:
            raise subprocess.CalledProcessError(returncode=1, cmd=argv)
        if argv[:2] == ["git", "fetch"]:
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        if argv[:2] == ["git", "show"]:
            git_path = argv[2].split(":", 1)[1]
            if git_path in {"langfuse_tracing/__init__.py", "langfuse_tracing/plugin.yaml"}:
                filename = git_path.rsplit("/", 1)[1]
                return subprocess.CompletedProcess(argv, 0, stdout=f"contents for {filename}\n", stderr="")
            raise subprocess.CalledProcessError(returncode=1, cmd=argv)
        raise AssertionError(f"Unexpected command: {argv}")

    monkeypatch.setattr(mod, "_run", fake_run)

    result = mod.ensure_langfuse_plugin(
        Namespace(
            feature_repo="https://example.com/repo.git",
            feature_branch="main",
            plugin_ref="langfuse-plugin/main",
        )
    )

    plugin_dir = tmp_path / ".hermes" / "plugins" / "langfuse_tracing"
    assert (plugin_dir / "__init__.py").read_text(encoding="utf-8") == "contents for __init__.py\n"
    assert (plugin_dir / "plugin.yaml").read_text(encoding="utf-8") == "contents for plugin.yaml\n"
    assert result["fetched"] is True
    assert result["plugin_ref"] == "langfuse-plugin/main"
    assert ["git", "fetch", "https://example.com/repo.git", "main:refs/remotes/langfuse-plugin/main"] in calls


def test_ensure_langfuse_setup_reports_combined_success(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    mod = load_module()

    monkeypatch.setattr(mod, "_ensure_langfuse_dependency", lambda: {"installed": True, "changed": False})
    monkeypatch.setattr(mod, "ensure_langfuse_plugin", lambda args=None: {"plugin_dir": str(tmp_path / ".hermes" / "plugins" / "langfuse_tracing")})
    monkeypatch.setattr(
        mod,
        "ensure_langfuse_env",
        lambda args=None: {
            "success": True,
            "env_path": str(tmp_path / ".hermes" / ".env"),
            "added": ["HERMES_LANGFUSE_ENABLED"],
            "preserved": {},
            "missing": [],
        },
    )
    monkeypatch.setattr(mod, "verify_plugin_discovery", lambda: {"success": True, "output": "langfuse_tracing"})
    monkeypatch.setattr(mod, "verify_langfuse_health", lambda base_url: {"success": True, "url": "http://localhost:3000/api/public/health"})

    result = mod.ensure_langfuse_setup(Namespace())

    assert result["success"] is True
    assert result["verification"]["plugin_discovery"]["success"] is True
    assert result["verification"]["langfuse_health"]["success"] is True


def test_main_reports_missing_required_keys(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    mod = load_module()
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("HERMES_LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("HERMES_LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setattr(mod, "_ensure_langfuse_dependency", lambda: {"installed": True, "changed": False})
    monkeypatch.setattr(mod, "ensure_langfuse_plugin", lambda args=None: {"plugin_dir": str(tmp_path / ".hermes" / "plugins" / "langfuse_tracing")})
    monkeypatch.setattr(mod, "verify_plugin_discovery", lambda: {"success": True, "output": "langfuse_tracing"})
    monkeypatch.setattr(mod, "verify_langfuse_health", lambda base_url: {"success": False, "skipped": True, "error": "base_url missing"})

    assert mod.main([]) == 1

    result = json.loads(capsys.readouterr().out)
    assert result["env"]["missing"] == [
        "HERMES_LANGFUSE_PUBLIC_KEY",
        "HERMES_LANGFUSE_SECRET_KEY",
    ]
