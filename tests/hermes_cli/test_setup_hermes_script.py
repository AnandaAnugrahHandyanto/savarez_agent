from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]
SETUP_SCRIPT = REPO_ROOT / "setup-hermes.sh"


def test_setup_hermes_script_is_valid_shell():
    result = subprocess.run(["bash", "-n", str(SETUP_SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_setup_hermes_script_uses_env_bash_shebang():
    assert SETUP_SCRIPT.read_text(encoding="utf-8").splitlines()[0] == "#!/usr/bin/env bash"


def test_setup_hermes_script_has_termux_path():
    content = SETUP_SCRIPT.read_text(encoding="utf-8")

    assert "is_termux()" in content
    assert ".[termux]" in content
    assert "constraints-termux.txt" in content
    assert "$PREFIX/bin" in content


def test_setup_hermes_script_has_linux_i686_python_gate():
    content = SETUP_SCRIPT.read_text(encoding="utf-8")

    assert "is_linux_i686()" in content
    assert "configure_linux_i686_tempdir()" in content
    assert "configure_linux_i686_uv_python_dirs()" in content
    assert 'export TMPDIR="$SCRIPT_DIR/.tmp"' in content
    assert 'export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-$SCRIPT_DIR/.uv/python}"' in content
    assert 'export UV_PYTHON_BIN_DIR="${UV_PYTHON_BIN_DIR:-$SCRIPT_DIR/.uv/bin}"' in content
    assert "find_compatible_python()" in content
    assert '$UV_CMD python install "$PYTHON_VERSION"' in content
    assert "uv Python install failed on Linux i686; using system Python" in content
    assert "LINUX_I686_SYSTEM_PYTHON=true" in content
    assert '"$PYTHON_PATH" -m venv venv' in content
