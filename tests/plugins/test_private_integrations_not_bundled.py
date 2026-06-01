"""Guardrails for integrations that must ship outside Hermes core."""

from pathlib import Path


def test_hawser_notifier_is_not_bundled_plugin():
    repo_root = Path(__file__).resolve().parents[2]
    assert not (repo_root / "plugins" / "hawser_notifier").exists()
