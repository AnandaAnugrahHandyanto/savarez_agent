"""Tests that launchctl constant is properly resolved.

When UV's bundled Python has a minimal PATH that doesn't include /bin,
subprocess calls to launchctl would fail with FileNotFoundError.
This test verifies that the _LAUNCHCTL constant falls back to the
absolute path /bin/launchctl.
"""

import os
import shutil
from unittest.mock import patch


def test_launchctl_fallback_to_absolute_path():
    """When shutil.which() returns None, should fall back to /bin/launchctl."""
    with patch.object(shutil, "which", return_value=None):
        # Re-import to recalculate the constant
        import importlib
        import hermes_cli.gateway as gateway_module
        importlib.reload(gateway_module)
        
        assert gateway_module._LAUNCHCTL == "/bin/launchctl"


def test_launchctl_uses_which_result_when_available():
    """When shutil.which() finds launchctl, should use that path."""
    with patch.object(shutil, "which", return_value="/usr/bin/launchctl"):
        import importlib
        import hermes_cli.gateway as gateway_module
        importlib.reload(gateway_module)
        
        assert gateway_module._LAUNCHCTL == "/usr/bin/launchctl"


def test_launchctl_constant_is_string():
    """_LAUNCHCTL should always be a non-empty string."""
    from hermes_cli import gateway
    
    assert isinstance(gateway._LAUNCHCTL, str)
    assert len(gateway._LAUNCHCTL) > 0
