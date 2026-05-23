#!/usr/bin/env python3
"""Smoke-test Hermes LLM Wiki against standalone core without vendored shadowing.

Temporary migration helper: until Hermes removes the top-level vendored
`hermes_wiki/` package, this creates a small shadow-free overlay of the Hermes
repo that exposes Hermes-native adapter code (`plugins/`, `agent/`, `tools/`)
without exposing the vendored core. A subprocess then imports the LLM Wiki memory
provider and verifies `hermes_wiki` resolves from the standalone package path.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY_ENTRIES = (
    "agent",
    "plugins",
    "tools",
    "hermes_cli",
)
OVERLAY_FILES = ("pyproject.toml",)
TEST_OVERLAY_ENTRIES = ("tests",)


def _link_or_copy(source: Path, dest: Path) -> None:
    if dest.exists() or dest.is_symlink():
        if dest.is_dir() and not dest.is_symlink():
            shutil.rmtree(dest)
        else:
            dest.unlink()
    try:
        dest.symlink_to(source, target_is_directory=source.is_dir())
    except OSError:
        if source.is_dir():
            shutil.copytree(source, dest)
        else:
            shutil.copy2(source, dest)


def build_shadow_free_overlay(repo_root: Path, overlay_root: Path, *, include_tests: bool = False) -> Path:
    """Expose Hermes adapter code in overlay_root while omitting vendored hermes_wiki."""
    repo_root = repo_root.resolve()
    overlay_root.mkdir(parents=True, exist_ok=True)
    entries = OVERLAY_ENTRIES + (TEST_OVERLAY_ENTRIES if include_tests else ())
    for entry in entries:
        source = repo_root / entry
        if source.exists():
            _link_or_copy(source, overlay_root / entry)
    for entry in OVERLAY_FILES:
        source = repo_root / entry
        if source.exists():
            _link_or_copy(source, overlay_root / entry)
    for source in sorted(repo_root.glob("*.py")):
        if source.name != "__init__.py":
            _link_or_copy(source, overlay_root / source.name)
    vendored = overlay_root / "hermes_wiki"
    if vendored.exists() or vendored.is_symlink():
        if vendored.is_dir() and not vendored.is_symlink():
            shutil.rmtree(vendored)
        else:
            vendored.unlink()
    return overlay_root


def standalone_import_root(path: str | Path) -> Path:
    """Return a sys.path entry for a standalone checkout or hermes_wiki package dir."""
    raw = Path(path).expanduser().resolve()
    if raw.name == "hermes_wiki":
        return raw.parent
    return raw


def run_import_smoke(standalone_root: Path, *, repo_root: Path = ROOT, python: str = sys.executable) -> dict[str, object]:
    standalone_root = standalone_import_root(standalone_root)
    if not (standalone_root / "hermes_wiki" / "__init__.py").exists():
        raise FileNotFoundError(f"standalone hermes_wiki package not found under {standalone_root}")

    with tempfile.TemporaryDirectory(prefix="hermes-llm-wiki-shadow-free-") as tmp:
        overlay = build_shadow_free_overlay(repo_root, Path(tmp) / "overlay")
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = os.pathsep.join(
            part for part in [str(overlay), str(standalone_root), existing_pythonpath] if part
        )
        code = r'''
import json
from pathlib import Path

import hermes_wiki
from plugins.memory.llm_wiki import LLMWikiMemoryProvider

provider = LLMWikiMemoryProvider()
schemas = provider.get_tool_schemas()
print(json.dumps({
    "hermes_wiki_file": str(Path(hermes_wiki.__file__).resolve()),
    "provider_available": provider.is_available(),
    "tool_names": [schema.get("name") for schema in schemas],
}, sort_keys=True))
'''
        completed = subprocess.run(
            [python, "-c", code],
            cwd=overlay,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
    payload = json.loads(completed.stdout)
    imported = Path(str(payload["hermes_wiki_file"])).resolve()
    vendored = (repo_root / "hermes_wiki").resolve()
    if vendored == imported or vendored in imported.parents:
        raise RuntimeError(f"hermes_wiki resolved to vendored Hermes copy: {imported}")
    if standalone_root.resolve() not in imported.parents:
        raise RuntimeError(f"hermes_wiki did not resolve from standalone root {standalone_root}: {imported}")
    required_tools = {"wiki_search", "wiki_query", "wiki_update"}
    missing_tools = sorted(required_tools - set(payload.get("tool_names") or []))
    if missing_tools:
        raise RuntimeError(f"LLM Wiki provider missing expected tools: {', '.join(missing_tools)}")
    return payload


def run_pytest_smoke(
    standalone_root: Path,
    *,
    repo_root: Path = ROOT,
    test_paths: list[str] | tuple[str, ...] = (),
    python: str = sys.executable,
) -> dict[str, object]:
    """Run selected Hermes tests from a shadow-free overlay against standalone core."""
    standalone_root = standalone_import_root(standalone_root)
    if not (standalone_root / "hermes_wiki" / "__init__.py").exists():
        raise FileNotFoundError(f"standalone hermes_wiki package not found under {standalone_root}")
    selected_tests = list(test_paths) or [
        "tests/plugins/memory/test_llm_wiki_provider.py",
        "tests/plugins/memory/test_llm_wiki_agent_agnostic_adapter.py",
    ]

    with tempfile.TemporaryDirectory(prefix="hermes-llm-wiki-pytest-") as tmp:
        overlay = build_shadow_free_overlay(repo_root, Path(tmp) / "overlay", include_tests=True)
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = os.pathsep.join(
            part for part in [str(overlay), str(standalone_root), existing_pythonpath] if part
        )
        completed = subprocess.run(
            [python, "-m", "pytest", "-o", "addopts=", *selected_tests, "-q"],
            cwd=overlay,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        return {
            "standalone_root": str(standalone_root),
            "test_paths": selected_tests,
            "pytest_stdout": completed.stdout,
            "pytest_stderr": completed.stderr,
        }


def _install_standalone_wheel(
    standalone_root: Path,
    target_dir: Path,
    *,
    python: str = sys.executable,
) -> Path:
    """Build standalone wheel and install it into target_dir without dependencies."""
    standalone_root = standalone_import_root(standalone_root)
    if not (standalone_root / "pyproject.toml").exists():
        raise FileNotFoundError(f"standalone pyproject.toml not found under {standalone_root}")
    dist_dir = target_dir.parent / "dist"
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(dist_dir)],
        cwd=standalone_root,
        text=True,
        capture_output=True,
        check=True,
    )
    wheels = sorted(dist_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one standalone wheel, found {len(wheels)}")
    subprocess.run(
        [python, "-m", "pip", "install", "--no-deps", "--target", str(target_dir), str(wheels[0])],
        text=True,
        capture_output=True,
        check=True,
    )
    return wheels[0]


def run_installed_import_smoke(
    standalone_root: Path,
    *,
    repo_root: Path = ROOT,
    python: str = sys.executable,
) -> dict[str, object]:
    """Build/install standalone into a temp target, then run the shadow-free smoke."""
    standalone_root = standalone_import_root(standalone_root)
    with tempfile.TemporaryDirectory(prefix="hermes-llm-wiki-installed-") as tmp:
        target_dir = Path(tmp) / "site"
        wheel = _install_standalone_wheel(standalone_root, target_dir, python=python)
        payload = run_import_smoke(target_dir, repo_root=repo_root, python=python)
        payload["installed_wheel"] = wheel.name
        return payload


def run_installed_pytest_smoke(
    standalone_root: Path,
    *,
    repo_root: Path = ROOT,
    test_paths: list[str] | tuple[str, ...] = (),
    python: str = sys.executable,
) -> dict[str, object]:
    """Build/install standalone, then run selected Hermes tests without vendored core."""
    standalone_root = standalone_import_root(standalone_root)
    with tempfile.TemporaryDirectory(prefix="hermes-llm-wiki-installed-pytest-") as tmp:
        target_dir = Path(tmp) / "site"
        wheel = _install_standalone_wheel(standalone_root, target_dir, python=python)
        payload = run_pytest_smoke(target_dir, repo_root=repo_root, test_paths=test_paths, python=python)
        payload["installed_wheel"] = wheel.name
        return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Hermes LLM Wiki can import standalone core without vendored shadowing")
    parser.add_argument("--standalone-root", required=True, help="Path to standalone hermes-llm-wiki repo or its hermes_wiki package")
    parser.add_argument("--repo-root", default=str(ROOT), help="Path to Hermes Agent repository root")
    parser.add_argument(
        "--install-standalone",
        action="store_true",
        help="Build and install standalone wheel into a temp target before running the import smoke",
    )
    parser.add_argument(
        "--pytest",
        action="append",
        default=[],
        metavar="TEST_PATH",
        help="Run a selected Hermes pytest path from a shadow-free overlay against standalone core",
    )
    args = parser.parse_args(argv)

    if args.pytest and args.install_standalone:
        payload = run_installed_pytest_smoke(
            Path(args.standalone_root),
            repo_root=Path(args.repo_root),
            test_paths=args.pytest,
        )
        print("LLM Wiki installed package pytest smoke passed")
    elif args.pytest:
        payload = run_pytest_smoke(Path(args.standalone_root), repo_root=Path(args.repo_root), test_paths=args.pytest)
        print("LLM Wiki standalone pytest smoke passed")
    elif args.install_standalone:
        payload = run_installed_import_smoke(Path(args.standalone_root), repo_root=Path(args.repo_root))
        print("LLM Wiki installed package import smoke passed")
    else:
        payload = run_import_smoke(Path(args.standalone_root), repo_root=Path(args.repo_root))
        print("LLM Wiki standalone import smoke passed")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
