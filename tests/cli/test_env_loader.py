import logging
from pathlib import Path

import pytest

from hermes_cli.env_loader import warn_on_masked_secrets


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (
            "OPENROUTER_API_KEY=***\nOPENAI_API_KEY=sk-real-value\n",
            ["OPENROUTER_API_KEY"],
        ),
        (
            "FEISHU_APP_SECRET=3VLrMD...1ycT\nNORMAL_VALUE=hello\n",
            ["FEISHU_APP_SECRET"],
        ),
        (
            "OPENAI_API_KEY=sk-real-value\nPASSWORD=hunter2\n",
            [],
        ),
    ],
)
def test_warn_on_masked_secrets_detects_placeholder_values(tmp_path: Path, caplog, content, expected):
    env_path = tmp_path / ".env"
    env_path.write_text(content, encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        flagged = warn_on_masked_secrets(env_path)

    assert flagged == expected
    if expected:
        assert "Masked placeholder secrets detected" in caplog.text
        for key in expected:
            assert key in caplog.text
    else:
        assert "Masked placeholder secrets detected" not in caplog.text
