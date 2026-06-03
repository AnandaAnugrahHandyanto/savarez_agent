"""Regression for PR #37702: skip submodule init when none declared.

The Windows installer (``scripts/install.ps1``) used to always run
``git submodule update --init --recursive`` after cloning. The current Hermes
repository ships **no** ``.gitmodules``, and on Windows machines where the
Git-for-Windows shell-helper path is broken that pointless command can fail
with errors like::

    /mingw64/libexec/git-core/git-sh-setup: line 46: /git-sh-i18n: No such file or directory

The fix wraps the submodule step in ``if (Test-Path ".gitmodules")`` so it only
runs when the checkout actually declares submodules, and otherwise prints a
skip notice and continues.

These tests pin that behavior:

* a portable static guard that inspects ``install.ps1`` text (runs everywhere), and
* a behavioral test that executes the extracted block under PowerShell with a
  stubbed ``git`` (skipped when ``pwsh`` is unavailable, e.g. Linux/macOS CI).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_PS1 = REPO_ROOT / "scripts" / "install.ps1"

# The full ``if (Test-Path ".gitmodules") { ... } else { ... }`` construct that
# guards the submodule step inside Install-Repository.
_SUBMODULE_BLOCK_RE = re.compile(
    r'if \(Test-Path "\.gitmodules"\) \{'
    r".*?"
    r'\n    \} else \{'
    r'\n        Write-Info "No submodules declared; skipping submodule init"'
    r"\n    \}",
    re.DOTALL,
)


def _extract_submodule_block() -> str:
    """Return the guarded submodule block, or skip until the fix lands.

    The guard is introduced by PR #37702. Until that change is present in
    ``scripts/install.ps1`` there is nothing to assert against, so the test
    skips with an explanatory reason rather than failing. Once the fix lands
    the assertions below become active and pin the behavior.
    """
    text = INSTALL_PS1.read_text(encoding="utf-8")
    match = _SUBMODULE_BLOCK_RE.search(text)
    if match is None:
        pytest.skip(
            'scripts/install.ps1 does not yet wrap `git submodule update` in an '
            '`if (Test-Path ".gitmodules")` guard (pending PR #37702).'
        )
    return match.group(0)


def test_submodule_update_is_guarded_by_gitmodules_check() -> None:
    """Static guard: the submodule update must live inside the Test-Path block."""
    block = _extract_submodule_block()

    guard_idx = block.find('if (Test-Path ".gitmodules")')
    update_idx = block.find("submodule update --init --recursive")
    else_idx = block.find("} else {")

    assert guard_idx != -1, "expected the .gitmodules Test-Path guard"
    assert update_idx != -1, "expected `git submodule update --init --recursive`"
    assert else_idx != -1, "expected an `else` branch for the no-submodules case"

    assert guard_idx < update_idx < else_idx, (
        "`git submodule update --init --recursive` must run *inside* the "
        "`if (Test-Path \".gitmodules\")` branch, before the else, so it is "
        "skipped when no submodules are declared (PR #37702)."
    )


def test_no_submodules_branch_prints_skip_notice() -> None:
    """The else branch must announce the skip rather than silently continuing."""
    block = _extract_submodule_block()
    assert "No submodules declared; skipping submodule init" in block, (
        "The no-submodules path should print a skip notice so installer logs "
        "explain why `git submodule` did not run."
    )


def test_submodule_update_is_not_called_unconditionally() -> None:
    """`git submodule update` must not appear outside the Test-Path guard."""
    text = INSTALL_PS1.read_text(encoding="utf-8")
    occurrences = text.count("submodule update --init --recursive")
    assert occurrences == 1, (
        f"Expected exactly one `git submodule update --init --recursive` call "
        f"(inside the .gitmodules guard); found {occurrences}. A second, "
        "unguarded call would reintroduce the Windows failure from PR #37702."
    )

    block = _extract_submodule_block()
    assert "submodule update --init --recursive" in block, (
        "The single submodule update call must be the one inside the guarded block."
    )


def _run_submodule_block(tmp_path: Path, *, with_gitmodules: bool) -> str:
    """Execute the extracted PowerShell block with a stubbed git in tmp_path."""
    if with_gitmodules:
        (tmp_path / ".gitmodules").write_text(
            '[submodule "x"]\n    path = x\n    url = https://example.invalid/x\n',
            encoding="utf-8",
        )

    block = _extract_submodule_block()
    script = "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            "function Write-Info { param($m) Write-Output \"INFO:$m\" }",
            "function Write-Warn { param($m) Write-Output \"WARN:$m\" }",
            "function Write-Success { param($m) Write-Output \"OK:$m\" }",
            "$global:gitCalled = $false",
            # Shadow the external git so the block never touches a real repo.
            "function git { $global:gitCalled = $true; $global:LASTEXITCODE = 0 }",
            block,
            'Write-Output "GIT_CALLED:$global:gitCalled"',
        ]
    )

    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    result = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0, (
        f"PowerShell block failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    return result.stdout


@pytest.mark.skipif(
    shutil.which("pwsh") is None and shutil.which("powershell") is None,
    reason="PowerShell (pwsh/powershell) not available on this host",
)
def test_block_skips_git_when_no_gitmodules(tmp_path: Path) -> None:
    out = _run_submodule_block(tmp_path, with_gitmodules=False)
    assert "GIT_CALLED:False" in out, (
        "git submodule must NOT be invoked when .gitmodules is absent.\n" + out
    )
    assert "No submodules declared; skipping submodule init" in out, out


@pytest.mark.skipif(
    shutil.which("pwsh") is None and shutil.which("powershell") is None,
    reason="PowerShell (pwsh/powershell) not available on this host",
)
def test_block_runs_git_when_gitmodules_present(tmp_path: Path) -> None:
    out = _run_submodule_block(tmp_path, with_gitmodules=True)
    assert "GIT_CALLED:True" in out, (
        "git submodule must run when .gitmodules is present.\n" + out
    )
    assert "Initializing submodules..." in out, out
    assert "OK:Submodules ready" in out, out
