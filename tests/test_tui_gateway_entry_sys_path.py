import os
import subprocess
import sys
from pathlib import Path


def test_tui_gateway_entry_ignores_cwd_package_shadowing(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    shadow_cwd = tmp_path / "shadow-cwd"
    shadow_cwd.mkdir()
    shadow_utils = shadow_cwd / "utils"
    shadow_utils.mkdir()
    (shadow_utils / "__init__.py").write_text(
        "raise RuntimeError('shadow utils package imported from cwd')\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["HERMES_HOME"] = str(tmp_path / "hermes-home")
    env["HERMES_PYTHON_SRC_ROOT"] = str(repo_root)
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(repo_root) if not existing_pythonpath else f"{repo_root}{os.pathsep}{existing_pythonpath}"
    )

    proc = subprocess.run(
        [sys.executable, "-m", "tui_gateway.entry"],
        cwd=shadow_cwd,
        env=env,
        input="",
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert proc.returncode == 0, proc.stderr
    assert "gateway.ready" in proc.stdout
    assert "shadow utils package imported" not in proc.stderr
