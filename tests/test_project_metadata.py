"""Regression tests for packaging metadata in pyproject.toml."""

from pathlib import Path
import tomllib


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_optional_dependencies():
    pyproject_path = REPO_ROOT / "pyproject.toml"
    with pyproject_path.open("rb") as handle:
        project = tomllib.load(handle)["project"]
    return project["optional-dependencies"]


def _load_pytest_ini_options():
    pyproject_path = REPO_ROOT / "pyproject.toml"
    with pyproject_path.open("rb") as handle:
        return tomllib.load(handle)["tool"]["pytest"]["ini_options"]


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


def test_messaging_extra_includes_qrcode_for_weixin_setup():
    optional_dependencies = _load_optional_dependencies()

    messaging_extra = optional_dependencies["messaging"]
    assert any(dep.startswith("qrcode") for dep in messaging_extra)


def test_pytest_default_addopts_do_not_force_xdist_auto():
    """Default `pytest` runs should stay below low macOS file-descriptor limits.

    The canonical parallel entrypoint is scripts/run_tests.sh, which pins an
    explicit worker count. Keeping `-n auto` out of pyproject addopts avoids
    EMFILE crashes on low-FD hosts while preserving marker filtering.
    """
    addopts = _load_pytest_ini_options()["addopts"]

    assert "-m 'not integration'" in addopts
    assert "-n auto" not in addopts
