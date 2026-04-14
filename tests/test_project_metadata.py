"""Regression tests for packaging metadata in pyproject.toml."""

from pathlib import Path
import tomllib


def _load_optional_dependencies():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as handle:
        project = tomllib.load(handle)["project"]
    return project["optional-dependencies"]


def _load_uv_lock_text():
    uv_lock_path = Path(__file__).resolve().parents[1] / "uv.lock"
    return uv_lock_path.read_text(encoding="utf-8")


def test_matrix_extra_linux_only_in_all():
    """mautrix[encryption] depends on python-olm which is upstream-broken on
    modern macOS (archived libolm, C++ errors with Clang 21+).  The [matrix]
    extra is included in [all] but gated to Linux via a platform marker so
    that ``hermes update`` doesn't fail on macOS."""
    optional_dependencies = _load_optional_dependencies()

    assert "matrix" in optional_dependencies
    # Must NOT be unconditional — python-olm has no macOS wheels.
    assert "hermes-agent[matrix]" not in optional_dependencies["all"]
    # Must be present with a Linux platform marker.
    linux_gated = [
        dep for dep in optional_dependencies["all"]
        if "matrix" in dep and "linux" in dep
    ]
    assert linux_gated, "expected hermes-agent[matrix] with sys_platform=='linux' marker in [all]"


def test_web_extra_is_exposed_in_uv_lock():
    uv_lock = _load_uv_lock_text()

    assert 'provides-extras = ["' in uv_lock
    provides_extras = next(
        line for line in uv_lock.splitlines()
        if line.startswith("provides-extras = ")
    )
    assert '"web"' in provides_extras
    assert '{ name = "fastapi", marker = "extra == \'rl\' or extra == \'web\'"' in uv_lock
    assert '{ name = "uvicorn", extras = ["standard"], marker = "extra == \'rl\' or extra == \'web\'"' in uv_lock
