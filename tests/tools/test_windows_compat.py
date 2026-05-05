"""Tests for Windows compatibility of process management code.

Verifies that os.setsid and os.killpg are never called unconditionally,
and that each module uses a platform guard before invoking POSIX-only functions.
"""

import ast
import pytest
from pathlib import Path

# Files that must have Windows-safe process management
GUARDED_FILES = [
    "tools/environments/local.py",
    "tools/process_registry.py",
    "tools/code_execution_tool.py",
    "gateway/platforms/whatsapp.py",
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _get_preexec_fn_values(filepath: Path) -> list:
    """Find all preexec_fn= keyword arguments in Popen calls."""
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(filepath))
    values = []
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "preexec_fn":
            values.append(ast.dump(node.value))
    return values


def _get_popen_keyword_names(filepath: Path) -> list[str]:
    """Find keyword names used on subprocess.Popen calls."""
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(filepath))
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "Popen"
            and isinstance(func.value, ast.Name)
            and func.value.id == "subprocess"
        ):
            names.extend(kw.arg for kw in node.keywords if kw.arg)
    return names


class TestNoUnconditionalSetsid:
    """preexec_fn must never be a bare os.setsid reference."""

    @pytest.mark.parametrize("relpath", GUARDED_FILES)
    def test_preexec_fn_is_guarded(self, relpath):
        filepath = PROJECT_ROOT / relpath
        if not filepath.exists():
            pytest.skip(f"{relpath} not found")
        values = _get_preexec_fn_values(filepath)
        for val in values:
            # A bare os.setsid would be: Attribute(value=Name(id='os'), attr='setsid')
            assert "attr='setsid'" not in val or "IfExp" in val or "None" in val, (
                f"{relpath} has unconditional preexec_fn=os.setsid"
            )

    @pytest.mark.parametrize("relpath", GUARDED_FILES)
    def test_hot_paths_do_not_use_preexec_fn(self, relpath):
        filepath = PROJECT_ROOT / relpath
        if not filepath.exists():
            pytest.skip(f"{relpath} not found")
        values = _get_preexec_fn_values(filepath)
        assert values == [], (
            f"{relpath} uses preexec_fn in a gateway/process hot path. "
            "Use start_new_session=True for POSIX process groups instead."
        )

    @pytest.mark.parametrize("relpath", GUARDED_FILES)
    def test_posix_process_groups_use_start_new_session(self, relpath):
        filepath = PROJECT_ROOT / relpath
        if not filepath.exists():
            pytest.skip(f"{relpath} not found")
        keywords = _get_popen_keyword_names(filepath)
        assert "start_new_session" in keywords, (
            f"{relpath} must use start_new_session for POSIX process groups"
        )


class TestIsWindowsConstant:
    """Each guarded file must define _IS_WINDOWS."""

    @pytest.mark.parametrize("relpath", GUARDED_FILES)
    def test_has_is_windows(self, relpath):
        filepath = PROJECT_ROOT / relpath
        if not filepath.exists():
            pytest.skip(f"{relpath} not found")
        source = filepath.read_text(encoding="utf-8")
        assert "_IS_WINDOWS" in source, (
            f"{relpath} missing _IS_WINDOWS platform guard"
        )


class TestKillpgGuarded:
    """os.killpg must always be behind a platform check."""

    @pytest.mark.parametrize("relpath", GUARDED_FILES)
    def test_no_unguarded_killpg(self, relpath):
        filepath = PROJECT_ROOT / relpath
        if not filepath.exists():
            pytest.skip(f"{relpath} not found")
        source = filepath.read_text(encoding="utf-8")
        lines = source.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if "os.killpg" in stripped or "os.getpgid" in stripped:
                # Check that there's an _IS_WINDOWS guard in the surrounding context
                context = "\n".join(lines[max(0, i - 15):i + 1])
                assert "_IS_WINDOWS" in context or "else:" in context, (
                    f"{relpath}:{i + 1} has unguarded os.killpg/os.getpgid call"
                )
