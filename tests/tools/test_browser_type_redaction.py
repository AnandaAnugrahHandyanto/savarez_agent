"""Regression tests for browser_type display redaction."""

import json
from unittest.mock import patch

from tools.browser_tool import browser_type


def test_browser_type_never_echoes_raw_typed_text(monkeypatch):
    monkeypatch.delenv("CAMOFOX_URL", raising=False)
    monkeypatch.delenv("BROWSER_CDP_URL", raising=False)
    secret = "my_secret_password_123"

    with patch(
        "tools.browser_tool._run_browser_command",
        return_value={"success": True},
    ) as mock_run:
        result = json.loads(browser_type("@password", secret, task_id="redaction-test"))

    assert result["success"] is True
    assert result["typed"] == "[redacted typed text]"
    assert secret not in json.dumps(result)
    mock_run.assert_called_once()
    assert mock_run.call_args.args[2] == ["@password", secret]
