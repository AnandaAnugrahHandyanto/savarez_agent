"""Regression: install.sh must detect a non-Python venv/bin/hermes.

Issue hermes-agent#21802: when the venv entry point is itself a bash
wrapper (left over from a botched install, a clobbered venv, or an
older installer), the launcher written to ``~/.local/bin/hermes``
execs back into ``venv/bin/hermes`` which execs back into itself —
``hermes`` hangs silently with no output.

The fix adds a defensive check inside ``setup_path()`` that inspects
the shebang of ``$HERMES_BIN``, and regenerates the entry point via
``pip install --force-reinstall --no-deps -e .`` when the shebang is
not a Python interpreter.  These tests assert the guard is present in
``scripts/install.sh`` so it cannot be silently dropped during future
refactors.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"


@pytest.fixture(scope="module")
def install_sh_text() -> str:
    return INSTALL_SH.read_text()


def test_install_sh_inspects_hermes_bin_shebang(install_sh_text: str) -> None:
    # The guard reads the first line of $HERMES_BIN to look at its shebang.
    assert 'head -n 1 "$HERMES_BIN"' in install_sh_text


def test_install_sh_accepts_python_shebang_only(install_sh_text: str) -> None:
    # The case branch must require a python interpreter in the shebang;
    # any other shape (bash, sh, missing) triggers the regeneration path.
    assert "'#!'*python*" in install_sh_text


def test_install_sh_regenerates_via_force_reinstall(install_sh_text: str) -> None:
    # Regeneration must use --force-reinstall so a clobbered console
    # script is overwritten, and --no-deps so we don't rebuild the
    # whole dependency tree just to fix the entry point.
    assert "--force-reinstall" in install_sh_text
    assert "--no-deps" in install_sh_text


def test_install_sh_references_issue_in_guard_comment(install_sh_text: str) -> None:
    # Future maintainers must be able to trace the guard back to the
    # original bug report so they don't remove it as "unused" code.
    assert "#21802" in install_sh_text


def test_install_sh_falls_back_to_manual_instruction_on_failure(
    install_sh_text: str,
) -> None:
    # When automatic regeneration fails the user must see the exact
    # command to run by hand — not a silent skip.
    assert "Manual fix: cd $INSTALL_DIR && uv pip install -e '.[all]'" in install_sh_text


def test_install_sh_guard_runs_before_launcher_is_written(install_sh_text: str) -> None:
    # The guard would be useless if the launcher (which would exec into
    # the broken wrapper) were written first.  Order must be: detect →
    # regenerate → write launcher.
    guard_marker = "Defensive guard against the recursive-wrapper hang"
    launcher_marker = 'cat > "$command_link_dir/hermes" <<EOF'
    guard_pos = install_sh_text.find(guard_marker)
    launcher_pos = install_sh_text.find(launcher_marker)
    assert guard_pos != -1, "guard marker missing"
    assert launcher_pos != -1, "launcher marker missing"
    assert guard_pos < launcher_pos, "guard must run before launcher write"


def test_install_sh_guard_skipped_when_not_using_venv(install_sh_text: str) -> None:
    # Non-venv paths (system install) don't have a $INSTALL_DIR/venv at
    # all, so the regeneration command would be nonsensical.  The guard
    # must be conditional on USE_VENV.
    guard_idx = install_sh_text.find("Defensive guard against the recursive-wrapper hang")
    assert guard_idx != -1
    window = install_sh_text[guard_idx : guard_idx + 1500]
    assert '[ "$USE_VENV" = true ]' in window
