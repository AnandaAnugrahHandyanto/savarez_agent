"""Regression tests for Nix packaging metadata."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_nix_package_uses_python312():
    python_nix = (REPO_ROOT / "nix/python.nix").read_text()

    assert "python312" in python_nix
    assert "python311" not in python_nix


def test_nix_devshell_uses_python312():
    dev_shell_nix = (REPO_ROOT / "nix/devShell.nix").read_text()

    assert "pkgs.python312" in dev_shell_nix
    assert "Python 3.12 venv" in dev_shell_nix
    assert "python311" not in dev_shell_nix
    assert "Python 3.11" not in dev_shell_nix
