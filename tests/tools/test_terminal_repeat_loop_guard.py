"""Regression tests for terminal repeated-command loop guard."""

import json
from unittest.mock import MagicMock, patch


def _make_env_config(**overrides):
    config = {
        "env_type": "local",
        "timeout": 180,
        "cwd": "/tmp",
        "host_cwd": None,
        "modal_mode": "auto",
        "docker_image": "",
        "singularity_image": "",
        "modal_image": "",
        "daytona_image": "",
    }
    config.update(overrides)
    return config


def test_identical_successful_foreground_command_gets_blocked_after_repeats():
    """Fourth identical successful foreground command should be blocked."""
    from tools.terminal_tool import terminal_tool

    mock_env = MagicMock()
    mock_env.execute.return_value = {"output": "", "returncode": 0}
    command = "sed -i '' 's/a/a/' data/wiki/article.md"

    with patch("tools.terminal_tool._get_env_config", return_value=_make_env_config()), \
         patch("tools.terminal_tool._start_cleanup_thread"), \
         patch("tools.terminal_tool._active_environments", {"loop-task": mock_env}), \
         patch("tools.terminal_tool._last_activity", {"loop-task": 0}), \
         patch("tools.terminal_tool._check_all_guards", return_value={"approved": True}):

        for _ in range(3):
            result = json.loads(terminal_tool(command=command, task_id="loop-task"))
            assert result.get("error") is None

        blocked = json.loads(terminal_tool(command=command, task_id="loop-task"))

    assert blocked["status"] == "blocked"
    assert "BLOCKED" in blocked["error"]
    assert "same foreground command" in blocked["error"]

