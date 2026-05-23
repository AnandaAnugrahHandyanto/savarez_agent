"""Guards for using standalone hermes-llm-wiki directly from Hermes.

Hermes should not carry a duplicate `hermes_wiki/` core package. The
standalone `hermes-llm-wiki` package is the DRY source of truth; Hermes keeps
only its native provider adapter under `plugins/memory/llm_wiki`.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from scripts import check_llm_wiki_standalone_import as standalone_import

build_shadow_free_overlay = standalone_import.build_shadow_free_overlay

REPO_ROOT = Path(__file__).resolve().parents[3]
VENDORED_CORE = REPO_ROOT / "hermes_wiki"


def standalone_core_path(raw_path: str | None = None) -> Path:
    configured = raw_path or os.environ.get("LLM_WIKI_STANDALONE_CORE")
    if not configured:
        pytest.skip("LLM_WIKI_STANDALONE_CORE is not set")
    return Path(configured).expanduser().resolve()


def test_hermes_does_not_vendor_llm_wiki_core():
    assert not VENDORED_CORE.exists()


def test_hermes_package_does_not_ship_llm_wiki_core():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"hermes_wiki"' not in pyproject
    assert '"hermes_wiki.*"' not in pyproject
    assert "hermes-wiki-eval =" not in pyproject
    assert "llm-wiki-mcp =" not in pyproject


def test_ci_can_verify_pinned_standalone_tag_when_network_check_enabled():
    script = REPO_ROOT / "scripts" / "check_git_ref.py"
    assert script.exists()
    text = _workflow_text()

    assert "HERMES_LLM_WIKI_CHECK_REMOTE_REF" in text
    assert "python scripts/check_git_ref.py https://github.com/michaelkrauty/hermes-llm-wiki.git v0.1.1" in text


def test_git_ref_guard_validates_release_tag_format_offline():
    script = REPO_ROOT / "scripts" / "check_git_ref.py"
    completed = subprocess.run(
        [standalone_import.sys.executable, str(script), "https://github.com/michaelkrauty/hermes-llm-wiki.git", "v0.1.1"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "ref format ok" in completed.stdout
    assert "remote check skipped" in completed.stdout


def test_ci_installs_standalone_llm_wiki_instead_of_syncing_vendored_core():
    text = _workflow_text()

    assert "repository: michaelkrauty/hermes-llm-wiki" in text
    assert "uv pip install -e .llm-wiki-standalone" in text
    assert "scripts/sync_llm_wiki_core.py" not in text
    assert "Verify vendored LLM Wiki core sync" not in text


def test_shadow_free_overlay_excludes_any_llm_wiki_core_copy(tmp_path):
    repo = tmp_path / "repo"
    (repo / "agent").mkdir(parents=True)
    (repo / "plugins").mkdir()
    (repo / "tools").mkdir()
    (repo / "hermes_wiki").mkdir()
    (repo / "agent" / "memory_provider.py").write_text("", encoding="utf-8")
    (repo / "plugins" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "tools" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "hermes_wiki" / "__init__.py").write_text("", encoding="utf-8")

    overlay = tmp_path / "overlay"

    build_shadow_free_overlay(repo, overlay)

    assert (overlay / "agent").exists()
    assert (overlay / "plugins").exists()
    assert (overlay / "tools").exists()
    assert not (overlay / "hermes_wiki").exists()


def _workflow_text() -> str:
    return (REPO_ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")


def _workflow_shadow_free_tests(text: str) -> set[str]:
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == "LLM_WIKI_TESTS=(")
    except StopIteration:  # pragma: no cover - assertion below gives clearer failure
        return set()
    selected = set()
    for line in lines[start + 1:]:
        stripped = line.strip()
        if stripped == ")":
            break
        if stripped:
            selected.add(stripped)
    return selected


def test_ci_runs_standalone_import_smoke():
    text = _workflow_text()

    assert "python scripts/check_llm_wiki_standalone_import.py --standalone-root .llm-wiki-standalone" in text
    assert "python scripts/check_llm_wiki_standalone_import.py --standalone-root .llm-wiki-standalone --install-standalone" in text
    assert "LLM_WIKI_TESTS=(" in text
    assert "tests/plugins/memory/test_llm_wiki_provider.py" in text
    assert "tests/plugins/memory/test_llm_wiki_caretaker.py" in text
    assert "tests/plugins/memory/test_llm_wiki_maintenance.py" in text
    assert "test_llm_wiki_proposals.py" not in text
    assert "test_llm_wiki_proposal_lifecycle.py" not in text
    assert "test_llm_wiki_caretaker_orchestrator.py" not in text
    assert "${LLM_WIKI_PYTEST_ARGS[@]}" in text
    assert "python scripts/check_llm_wiki_standalone_import.py --standalone-root .llm-wiki-standalone \"${LLM_WIKI_PYTEST_ARGS[@]}\"" in text
    assert "python scripts/check_llm_wiki_standalone_import.py --standalone-root .llm-wiki-standalone --install-standalone \"${LLM_WIKI_PYTEST_ARGS[@]}\"" in text
    assert "assert repo_vendored" not in text
    assert "import hermes_wiki as preloaded" not in text


def test_ci_shadow_free_smoke_covers_core_llm_wiki_test_suites():
    selected = _workflow_shadow_free_tests(_workflow_text())
    all_llm_wiki_tests = {
        str(path.relative_to(REPO_ROOT))
        for path in (REPO_ROOT / "tests" / "plugins" / "memory").glob("test_llm_wiki*.py")
    }
    # These tests validate Hermes-local docs/CI overlay behavior itself rather
    # than the standalone core package boundary, so they are intentionally not
    # part of the shadow-free core smoke.
    excluded = {
        "tests/plugins/memory/test_llm_wiki_public_docs_hygiene.py",
        "tests/plugins/memory/test_llm_wiki_standalone_sync.py",
    }

    assert selected == all_llm_wiki_tests - excluded


def test_cli_can_run_installed_package_import_smoke(monkeypatch, tmp_path, capsys):
    calls = []

    def fake_run_installed_import_smoke(standalone_root, *, repo_root=standalone_import.ROOT, python=standalone_import.sys.executable):
        calls.append((standalone_root, repo_root, python))
        return {"hermes_wiki_file": "/tmp/site-packages/hermes_wiki/__init__.py", "tool_names": ["wiki_search"]}

    monkeypatch.setattr(standalone_import, "run_installed_import_smoke", fake_run_installed_import_smoke)

    result = standalone_import.main([
        "--standalone-root",
        str(tmp_path / "standalone"),
        "--install-standalone",
    ])

    assert result == 0
    assert calls == [(tmp_path / "standalone", standalone_import.ROOT, standalone_import.sys.executable)]
    assert "installed package import smoke passed" in capsys.readouterr().out


def test_shadow_free_overlay_can_include_tests_without_vendored_core(tmp_path):
    repo = tmp_path / "repo"
    (repo / "agent").mkdir(parents=True)
    (repo / "plugins").mkdir()
    (repo / "tools").mkdir()
    (repo / "tests").mkdir()
    (repo / "hermes_wiki").mkdir()
    (repo / "tests" / "test_example.py").write_text("def test_example():\n    assert True\n", encoding="utf-8")
    (repo / "hermes_wiki" / "__init__.py").write_text("", encoding="utf-8")

    overlay = tmp_path / "overlay"

    standalone_import.build_shadow_free_overlay(repo, overlay, include_tests=True)

    assert (overlay / "tests" / "test_example.py").exists()
    assert not (overlay / "hermes_wiki").exists()


def test_run_pytest_smoke_uses_shadow_free_overlay(monkeypatch, tmp_path):
    standalone = tmp_path / "standalone"
    (standalone / "hermes_wiki").mkdir(parents=True)
    (standalone / "hermes_wiki" / "__init__.py").write_text("", encoding="utf-8")
    repo = tmp_path / "repo"
    (repo / "agent").mkdir(parents=True)
    (repo / "plugins").mkdir()
    (repo / "tools").mkdir()
    (repo / "tests").mkdir()
    (repo / "hermes_wiki").mkdir()
    (repo / "tests" / "test_example.py").write_text("def test_example():\n    assert True\n", encoding="utf-8")

    calls = []

    def fake_run(args, *, cwd, env, text, capture_output, check):
        calls.append({"args": args, "cwd": cwd, "env": env, "check": check})
        assert not (Path(cwd) / "hermes_wiki").exists()
        return standalone_import.subprocess.CompletedProcess(args, 0, stdout="passed", stderr="")

    monkeypatch.setattr(standalone_import.subprocess, "run", fake_run)

    payload = standalone_import.run_pytest_smoke(
        standalone,
        repo_root=repo,
        test_paths=["tests/test_example.py"],
        python="python-test",
    )

    assert payload["pytest_stdout"] == "passed"
    assert calls[0]["args"] == ["python-test", "-m", "pytest", "-o", "addopts=", "tests/test_example.py", "-q"]
    assert str(standalone) in calls[0]["env"]["PYTHONPATH"]


def test_cli_can_run_pytest_smoke(monkeypatch, tmp_path, capsys):
    calls = []

    def fake_run_pytest_smoke(standalone_root, *, repo_root=standalone_import.ROOT, test_paths=(), python=standalone_import.sys.executable):
        calls.append((standalone_root, repo_root, tuple(test_paths), python))
        return {"pytest_stdout": "ok"}

    monkeypatch.setattr(standalone_import, "run_pytest_smoke", fake_run_pytest_smoke)

    result = standalone_import.main([
        "--standalone-root",
        str(tmp_path / "standalone"),
        "--pytest",
        "tests/plugins/memory/test_llm_wiki_provider.py",
    ])

    assert result == 0
    assert calls == [(
        tmp_path / "standalone",
        standalone_import.ROOT,
        ("tests/plugins/memory/test_llm_wiki_provider.py",),
        standalone_import.sys.executable,
    )]
    assert "pytest smoke passed" in capsys.readouterr().out


def test_cli_can_run_installed_pytest_smoke(monkeypatch, tmp_path, capsys):
    calls = []

    def fake_run_installed_pytest_smoke(standalone_root, *, repo_root=standalone_import.ROOT, test_paths=(), python=standalone_import.sys.executable):
        calls.append((standalone_root, repo_root, tuple(test_paths), python))
        return {"pytest_stdout": "ok", "installed_wheel": "hermes_llm_wiki-0.1.0-py3-none-any.whl"}

    monkeypatch.setattr(standalone_import, "run_installed_pytest_smoke", fake_run_installed_pytest_smoke)

    result = standalone_import.main([
        "--standalone-root",
        str(tmp_path / "standalone"),
        "--install-standalone",
        "--pytest",
        "tests/plugins/memory/test_llm_wiki_provider.py",
    ])

    assert result == 0
    assert calls == [(
        tmp_path / "standalone",
        standalone_import.ROOT,
        ("tests/plugins/memory/test_llm_wiki_provider.py",),
        standalone_import.sys.executable,
    )]
    assert "installed package pytest smoke passed" in capsys.readouterr().out


def test_provider_module_imports_when_standalone_core_missing():
    code = """
import importlib.abc
import json
import sys

class BlockHermesWiki(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'hermes_wiki' or fullname.startswith('hermes_wiki.'):
            raise ModuleNotFoundError(fullname)
        return None

sys.meta_path.insert(0, BlockHermesWiki())
from plugins.memory.llm_wiki import LLMWikiMemoryProvider
provider = LLMWikiMemoryProvider()
print(json.dumps({'available': provider.is_available()}))
"""
    completed = standalone_import.subprocess.run(
        [standalone_import.sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=True,
    )
    payload = standalone_import.json.loads(completed.stdout)

    assert payload == {"available": True}


def test_provider_imports_installed_standalone_core_from_repo_root():
    code = """
import json
from pathlib import Path
from plugins.memory.llm_wiki import LLMWikiMemoryProvider
import hermes_wiki
provider = LLMWikiMemoryProvider()
print(json.dumps({
    "hermes_wiki_file": str(Path(hermes_wiki.__file__).resolve()),
    "available": provider.is_available(),
}))
"""
    completed = standalone_import.subprocess.run(
        [standalone_import.sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=True,
    )
    payload = standalone_import.json.loads(completed.stdout)

    imported = Path(payload["hermes_wiki_file"]).resolve()
    assert payload["available"] is True
    assert VENDORED_CORE not in imported.parents
    assert "site-packages" in imported.parts or standalone_core_path() in imported.parents


def test_runtime_opt_in_can_use_standalone_checkout_from_repo_root():
    standalone_root = standalone_core_path().parent
    if not (standalone_root / "hermes_wiki" / "__init__.py").exists():
        return

    code = """
import json
from pathlib import Path
from plugins.memory.llm_wiki import LLMWikiMemoryProvider
import hermes_wiki
provider = LLMWikiMemoryProvider()
print(json.dumps({
    "hermes_wiki_file": str(Path(hermes_wiki.__file__).resolve()),
    "available": provider.is_available(),
}))
"""
    env = os.environ.copy()
    env["HERMES_LLM_WIKI_STANDALONE_ROOT"] = str(standalone_root)
    completed = standalone_import.subprocess.run(
        [standalone_import.sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = standalone_import.json.loads(completed.stdout)

    imported = Path(payload["hermes_wiki_file"]).resolve()
    assert payload["available"] is True
    assert standalone_root in imported.parents
    assert VENDORED_CORE not in imported.parents
