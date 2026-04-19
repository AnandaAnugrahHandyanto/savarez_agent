from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = REPO_ROOT / "docker" / "entrypoint.sh"


def _active_venv_root() -> Path:
    repo_venv = REPO_ROOT / "venv"
    if repo_venv.exists():
        return repo_venv
    return Path(sys.executable).resolve().parent.parent


def test_entrypoint_bootstraps_without_bundled_soul_md(tmp_path: Path):
    install_dir = tmp_path / "install"
    home_dir = tmp_path / "home"
    install_dir.mkdir()
    home_dir.mkdir()

    entrypoint_copy = install_dir / "docker" / "entrypoint.sh"
    entrypoint_copy.parent.mkdir(parents=True)
    entrypoint_copy.write_text(
        ENTRYPOINT.read_text(encoding="utf-8").replace(
            'INSTALL_DIR="/opt/hermes"', f'INSTALL_DIR="{install_dir}"'
        ),
        encoding="utf-8",
    )
    entrypoint_copy.chmod(0o755)

    (install_dir / ".env.example").write_text("", encoding="utf-8")
    (install_dir / "cli-config.yaml.example").write_text("display: {}\n", encoding="utf-8")
    (install_dir / "skills").mkdir()
    (install_dir / "tools").mkdir()
    (install_dir / "tools" / "skills_sync.py").write_text(
        "from pathlib import Path\n"
        "from hermes_constants import get_hermes_home\n"
        "skills_dir = get_hermes_home() / 'skills'\n"
        "skills_dir.mkdir(parents=True, exist_ok=True)\n"
        "(skills_dir / '.bundled_manifest').write_text('', encoding='utf-8')\n",
        encoding="utf-8",
    )

    os.symlink(_active_venv_root(), install_dir / ".venv")

    env = os.environ.copy()
    env["HERMES_HOME"] = str(home_dir)
    proc = subprocess.run(
        [str(entrypoint_copy), "--help"],
        cwd=str(install_dir),
        env=env,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    soul_text = (home_dir / "SOUL.md").read_text(encoding="utf-8")
    assert "Hermes Agent Persona" in soul_text
    assert (home_dir / "skills" / ".bundled_manifest").exists()
    assert "For more help on a command:" in proc.stdout
