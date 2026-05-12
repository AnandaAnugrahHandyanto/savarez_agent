"""conftest.py — Fixtures for statusbar-resolved-model tests."""

from pathlib import Path
import pytest


@pytest.fixture(scope="session")
def src() -> dict:
    """Return {'run_agent': source, 'cli': source} for the repo root."""
    # repo root = parent of tests/ directory
    repo_root = Path(__file__).resolve().parent.parent
    return {
        "run_agent": (repo_root / "run_agent.py").read_text(encoding="utf-8"),
        "cli": (repo_root / "cli.py").read_text(encoding="utf-8"),
    }
