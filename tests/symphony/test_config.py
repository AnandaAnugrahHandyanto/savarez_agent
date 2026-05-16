from pathlib import Path

import pytest

from symphony.errors import SymphonyError
from symphony.config import load_config


def test_load_config_applies_core_defaults(tmp_path):
    config = load_config({}, workflow_dir=tmp_path, env={})

    assert config.polling.interval_ms == 30000
    assert config.agent.max_concurrent_agents == 10
    assert config.agent.max_turns == 20
    assert config.agent.runner == "hermes"
    assert config.hermes.mode == "subprocess"


def test_tracker_api_key_env_reference_resolves_from_explicit_env(tmp_path):
    config = load_config(
        {"tracker": {"api_key": "$LINEAR_API_KEY"}},
        workflow_dir=tmp_path,
        env={"LINEAR_API_KEY": "linear-secret"},
    )

    assert config.tracker.api_key == "linear-secret"
    assert config.tracker.redacted_api_key == "[REDACTED]"
    assert "linear-secret" not in repr(config)


def test_tracker_api_key_missing_env_reference_raises_stable_error(tmp_path):
    with pytest.raises(SymphonyError) as exc_info:
        load_config(
            {"tracker": {"api_key": "$LINEAR_API_KEY"}},
            workflow_dir=tmp_path,
            env={},
        )

    assert exc_info.value.code == "missing_tracker_api_key"


def test_tracker_api_key_literal_is_preserved_without_env_resolution(tmp_path):
    config = load_config(
        {"tracker": {"api_key": "literal-key"}},
        workflow_dir=tmp_path,
        env={"literal-key": "should-not-be-used"},
    )

    assert config.tracker.api_key == "literal-key"
    assert config.tracker.redacted_api_key == "[REDACTED]"
    assert "literal-key" not in repr(config)


def test_tracker_api_key_rejects_non_string_literal(tmp_path):
    with pytest.raises(SymphonyError) as exc_info:
        load_config({"tracker": {"api_key": 123}}, workflow_dir=tmp_path, env={})

    assert exc_info.value.code == "invalid_config_value"


def test_workspace_root_relative_to_workflow_dir(tmp_path):
    workflow_dir = tmp_path / "flows"
    workflow_dir.mkdir()

    config = load_config({"workspace": {"root": "worktrees"}}, workflow_dir=workflow_dir, env={})

    assert config.workspace.root == workflow_dir / "worktrees"


def test_workspace_root_absolute_is_preserved(tmp_path):
    workspace_root = tmp_path / "absolute-worktrees"

    config = load_config({"workspace": {"root": str(workspace_root)}}, workflow_dir=tmp_path / "flows", env={})

    assert config.workspace.root == workspace_root


def test_hermes_runner_does_not_require_codex_command(tmp_path):
    config = load_config({"agent": {"runner": "hermes"}}, workflow_dir=tmp_path, env={})

    assert config.agent.runner == "hermes"
    assert config.codex.command is None


def test_codex_runner_requires_non_empty_codex_command(tmp_path):
    with pytest.raises(SymphonyError) as exc_info:
        load_config({"agent": {"runner": "codex"}}, workflow_dir=tmp_path, env={})

    assert exc_info.value.code == "missing_codex_command"


def test_codex_runner_accepts_non_empty_codex_command(tmp_path):
    config = load_config(
        {"agent": {"runner": "codex"}, "codex": {"command": "codex exec"}},
        workflow_dir=tmp_path,
        env={},
    )

    assert config.agent.runner == "codex"
    assert config.codex.command == "codex exec"


@pytest.mark.parametrize("runner", ["", "claude", "HER MES"])
def test_unsupported_agent_runner_raises_stable_error(tmp_path, runner):
    with pytest.raises(SymphonyError) as exc_info:
        load_config({"agent": {"runner": runner}}, workflow_dir=tmp_path, env={})

    assert exc_info.value.code == "unsupported_agent_runner"


@pytest.mark.parametrize(
    ("raw_config", "expected_code"),
    [
        ({"polling": {"interval_ms": "abc"}}, "invalid_config_value"),
        ({"agent": {"max_turns": "twenty"}}, "invalid_config_value"),
        ({"workspace": {"root": []}}, "invalid_config_value"),
        ({"polling": []}, "invalid_config_section"),
    ],
)
def test_invalid_config_types_raise_stable_errors(tmp_path, raw_config, expected_code):
    with pytest.raises(SymphonyError) as exc_info:
        load_config(raw_config, workflow_dir=tmp_path, env={})

    assert exc_info.value.code == expected_code


@pytest.mark.parametrize(
    ("raw_config", "field_name"),
    [
        ({"polling": {"interval_ms": 0}}, "polling.interval_ms"),
        ({"polling": {"interval_ms": -1}}, "polling.interval_ms"),
        ({"agent": {"max_turns": 0}}, "agent.max_turns"),
        ({"agent": {"max_concurrent_agents": 0}}, "agent.max_concurrent_agents"),
        ({"hermes": {"timeout_seconds": 0}}, "hermes.timeout_seconds"),
        ({"tracker": {"first": 0}}, "tracker.first"),
        ({"agent": {"max_concurrent_agents": 101}}, "agent.max_concurrent_agents"),
        ({"tracker": {"first": 251}}, "tracker.first"),
    ],
)
def test_bounded_integer_config_fields_reject_out_of_range_values(tmp_path, raw_config, field_name):
    with pytest.raises(SymphonyError) as exc_info:
        load_config(raw_config, workflow_dir=tmp_path, env={})

    assert exc_info.value.code == "invalid_config_value"
    assert field_name in exc_info.value.message
