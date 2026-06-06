"""Regression tests for Linux i686 installer guards.

Linux i686 installs often run on small systems where ``/tmp`` or ``$HOME`` may
be tmpfs-backed. The installer should keep uv-managed Python downloads under
Hermes' data directory, keep uv as the primary Python provider, and fall back
to an already-installed Python only when uv cannot provide one.
"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"
PYPROJECT_TOML = REPO_ROOT / "pyproject.toml"


def _function_body(name: str) -> str:
    text = INSTALL_SH.read_text(encoding="utf-8")
    _, _, rest = text.partition(f"{name}() {{\n")
    assert rest, f"Could not find {name}() in scripts/install.sh"
    body, _, _ = rest.partition("\n}\n")
    assert body, f"Could not find {name}() body"
    return body


def test_linux_i686_detection_is_narrow() -> None:
    text = INSTALL_SH.read_text(encoding="utf-8")

    assert "is_linux_i686()" in text
    assert 'i386|i486|i586|i686)' in text
    assert 'getconf LONG_BIT' in text
    assert '[ "${OS:-}" = "linux" ]' in text


def test_install_script_uses_env_bash_shebang() -> None:
    assert INSTALL_SH.read_text(encoding="utf-8").splitlines()[0] == "#!/usr/bin/env bash"


def test_linux_i686_tempdir_defaults_under_hermes_home() -> None:
    body = _function_body("configure_linux_i686_tempdir")

    assert 'if ! is_linux_i686 || [ -n "${TMPDIR:-}" ]; then' in body
    assert 'export TMPDIR="$HERMES_HOME/tmp"' in body
    assert 'mkdir -p "$TMPDIR"' in body


def test_linux_i686_uv_python_dirs_default_under_hermes_home() -> None:
    body = _function_body("configure_linux_i686_uv_python_dirs")

    assert 'if ! is_linux_i686 || [ "$ROOT_FHS_LAYOUT" = true ]; then' in body
    assert 'export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-$HERMES_HOME/uv/python}"' in body
    assert 'export UV_PYTHON_BIN_DIR="${UV_PYTHON_BIN_DIR:-$HERMES_HOME/uv/bin}"' in body
    assert 'mkdir -p "$UV_PYTHON_INSTALL_DIR" "$UV_PYTHON_BIN_DIR"' in body


def test_linux_i686_check_python_prefers_uv_with_system_fallback() -> None:
    body = _function_body("check_python")

    uv_install_idx = body.find('"$UV_CMD" python install "$PYTHON_VERSION"')
    assert uv_install_idx != -1, "test expected the regular uv python install path"
    assert "elif is_linux_i686 && PYTHON_PATH=\"$(find_compatible_python)\"; then" in body
    assert "LINUX_I686_SYSTEM_PYTHON=true" in body
    assert "uv Python install failed on Linux i686; using system Python" in body
    assert "HERMES_PYTHON=/path/to/python" in body
    assert "uv-managed CPython does not publish Linux i686 builds" not in body


def test_linux_i686_venv_uses_system_python_only_after_fallback() -> None:
    body = _function_body("setup_venv")

    fallback_idx = body.find('if [ "$LINUX_I686_SYSTEM_PYTHON" = true ]; then')
    uv_venv_idx = body.find('$UV_CMD venv venv --python "$PYTHON_VERSION"')
    assert fallback_idx != -1, "setup_venv must have a Linux i686 system-Python fallback"
    assert uv_venv_idx != -1, "test expected the regular uv venv path"
    assert fallback_idx < uv_venv_idx, "system-Python fallback must be checked before uv venv"
    assert '"$PYTHON_PATH" -m venv venv' in body
    assert 'export UV_PYTHON="$INSTALL_DIR/venv/bin/python"' in body


def test_linux_i686_uses_plain_uvicorn_to_avoid_source_only_uvloop() -> None:
    text = PYPROJECT_TOML.read_text(encoding="utf-8")

    assert 'uvicorn[standard]>=0.24.0,<1; sys_platform != \'linux\'' in text
    assert "platform_machine != 'i686'" in text
    assert 'uvicorn>=0.24.0,<1; sys_platform == \'linux\'' in text
    assert "platform_machine == 'i686'" in text
    assert 'uvicorn[standard]==0.41.0; sys_platform != \'linux\'' in text
    assert 'uvicorn==0.41.0; sys_platform == \'linux\'' in text


def test_linux_i686_uses_plain_pyjwt_to_avoid_source_only_cryptography() -> None:
    text = PYPROJECT_TOML.read_text(encoding="utf-8")

    assert 'PyJWT[crypto]==2.12.1; sys_platform != \'linux\'' in text
    assert "platform_machine != 'i686'" in text
    assert 'PyJWT==2.12.1; sys_platform == \'linux\'' in text
    assert "platform_machine == 'i686'" in text
    assert 'hermes-agent[mcp]; sys_platform != \'linux\'' in text
    assert 'hermes-agent[google]; sys_platform != \'linux\'' in text
