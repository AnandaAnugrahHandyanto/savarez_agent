import pytest
import os
import sys

# Ensure cron is importable
agent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, agent_dir)

from cron.ingest_platform import parse_platform_state

def test_parse_platform_state_basic():
    """Verify that parse_platform_state executes without exception and returns a formatted manifest string."""
    manifest = parse_platform_state()
    
    # Check that it returns a non-empty string
    assert isinstance(manifest, str)
    assert len(manifest) > 0
    
    # Check for expected markdown headers
    assert "## Cron Jobs" in manifest or "## Core Configuration" in manifest or "## Skills" in manifest
    assert "# Hermes Context Graph - System Manifest" in manifest
