"""Regression tests for packaging metadata in pyproject.toml."""

from pathlib import Path
import tomllib


def _load_optional_dependencies():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as handle:
        project = tomllib.load(handle)["project"]
    return project["optional-dependencies"]


def test_broken_matrix_extra_not_advertised():
    """Do not publish a Matrix extra until its dependency stack is compatible.

    Current matrix-nio wheels still require h11~=0.14, which conflicts with the
    httpcore==1.x stack pulled in by Hermes core dependencies. Advertising a
    ``hermes-agent[matrix]`` install path would therefore publish a broken
    dependency set in packaging metadata.
    """
    optional_dependencies = _load_optional_dependencies()

    assert "matrix" not in optional_dependencies


def test_all_extra_does_not_pull_matrix_dependencies():
    """The catch-all extra must stay installable even while Matrix is guarded."""
    optional_dependencies = _load_optional_dependencies()

    assert all("matrix" not in dep for dep in optional_dependencies["all"])
