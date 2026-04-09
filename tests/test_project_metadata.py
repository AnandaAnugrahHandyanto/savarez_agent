"""Regression tests for packaging metadata in pyproject.toml."""

from pathlib import Path
import tomllib


def _load_project_metadata():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as handle:
        return tomllib.load(handle)["project"]


def test_matrix_extra_exists_but_excluded_from_all():
    """matrix-nio[e2e] depends on python-olm which is upstream-broken on modern
    macOS (archived libolm, C++ errors with Clang 21+).  The [matrix] extra is
    kept for opt-in install but deliberately excluded from [all] so one broken
    upstream dep doesn't nuke every other extra during ``hermes update``."""
    optional_dependencies = _load_project_metadata()["optional-dependencies"]

    assert "matrix" in optional_dependencies
    assert "hermes-agent[matrix]" not in optional_dependencies["all"]


def test_httpx_base_dependency_enables_socks_support():
    dependencies = _load_project_metadata()["dependencies"]
    httpx_dependencies = [dependency for dependency in dependencies if dependency.startswith("httpx")]

    assert len(httpx_dependencies) == 1
    assert httpx_dependencies[0].startswith("httpx[socks]>=")
    assert "[socks]" in httpx_dependencies[0]
