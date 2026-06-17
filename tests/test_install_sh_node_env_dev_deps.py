"""Regression: installer npm builds must not inherit production NODE_ENV.

The desktop updater can be launched from a Hermes runtime whose environment has
``NODE_ENV=production``. npm treats that as omit=dev, so TypeScript/Vite are not
installed and later builds fail with ``sh: tsc: command not found``.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"
INSTALL_PS1 = REPO_ROOT / "scripts" / "install.ps1"


def _extract_function_body(name: str) -> str:
    text = INSTALL_SH.read_text(encoding="utf-8")
    match = re.search(
        rf"^{re.escape(name)}\(\)\s*\{{\s*\n(?P<body>.*?)^\}}",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"{name}() not found in scripts/install.sh"
    return match["body"]


def test_install_desktop_forces_development_env_for_npm_install_and_pack() -> None:
    body = _extract_function_body("install_desktop")

    assert "NODE_ENV=development NPM_CONFIG_OMIT= npm ci" in body
    assert "NODE_ENV=development NPM_CONFIG_OMIT= npm install" in body
    desktop_pack_body = _extract_function_body("_desktop_pack")
    assert "NPM_CONFIG_OMIT=" in desktop_pack_body
    assert "NODE_ENV=development" not in desktop_pack_body


def test_install_desktop_user_guidance_does_not_reproduce_production_omit_dev() -> None:
    body = _extract_function_body("install_desktop")

    assert "NODE_ENV=development NPM_CONFIG_OMIT= npm ci" in body
    assert "NODE_ENV=development NPM_CONFIG_OMIT= npm run pack" in body


def test_install_ps1_uses_workspace_local_electron_dist() -> None:
    text = INSTALL_PS1.read_text(encoding="utf-8")

    assert "function Get-ElectronDir" in text
    assert "apps\\desktop\\node_modules\\electron" in text
    assert "Get-ElectronDir -InstallDir $InstallDir" in text


def test_install_ps1_forces_dev_dependencies_for_desktop_install() -> None:
    text = INSTALL_PS1.read_text(encoding="utf-8")

    assert '$env:NODE_ENV = "development"' in text
    assert '$env:NPM_CONFIG_OMIT = ""' in text
