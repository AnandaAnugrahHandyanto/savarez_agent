import os

from symphony.reload import WorkflowReloader
from symphony.errors import SymphonyError


def _write_workflow(path, *, interval_ms=30000, prompt="Do work.", extra_config=""):
    path.write_text(
        "---\n"
        "polling:\n"
        f"  interval_ms: {interval_ms}\n"
        f"{extra_config}"
        "---\n"
        f"{prompt}\n",
        encoding="utf-8",
    )


def _bump_mtime(path):
    current = path.stat().st_mtime_ns
    os.utime(path, ns=(current + 1_000_000, current + 1_000_000))


def test_reload_if_changed_returns_false_when_mtime_unchanged(tmp_path):
    workflow_path = tmp_path / "WORKFLOW.md"
    _write_workflow(workflow_path, interval_ms=30000, prompt="Original prompt.")
    reloader = WorkflowReloader(workflow_path, env={})

    assert reloader.reload_if_changed() is False
    assert reloader.config.polling.interval_ms == 30000
    assert reloader.workflow.prompt_template == "Original prompt."
    assert reloader.last_error is None


def test_reload_if_changed_updates_future_config_and_prompt_on_valid_change(tmp_path):
    workflow_path = tmp_path / "WORKFLOW.md"
    _write_workflow(workflow_path, interval_ms=30000, prompt="Original prompt.")
    reloader = WorkflowReloader(workflow_path, env={})

    _write_workflow(workflow_path, interval_ms=5000, prompt="Updated prompt.")
    _bump_mtime(workflow_path)

    assert reloader.reload_if_changed() is True
    assert reloader.config.polling.interval_ms == 5000
    assert reloader.workflow.prompt_template == "Updated prompt."
    assert reloader.last_error is None


def test_invalid_reload_keeps_last_good_config_and_exposes_safe_error(tmp_path):
    workflow_path = tmp_path / "WORKFLOW.md"
    _write_workflow(workflow_path, interval_ms=30000, prompt="Good prompt.")
    reloader = WorkflowReloader(workflow_path, env={"LINEAR_API_KEY": "super-secret-token"})

    workflow_path.write_text(
        "---\n"
        "polling:\n"
        "  interval_ms: invalid\n"
        "tracker:\n"
        "  api_key: $LINEAR_API_KEY\n"
        "---\n"
        "Bad prompt.\n",
        encoding="utf-8",
    )
    _bump_mtime(workflow_path)

    assert reloader.reload_if_changed() is False
    assert reloader.config.polling.interval_ms == 30000
    assert reloader.workflow.prompt_template == "Good prompt."
    assert isinstance(reloader.last_error, SymphonyError)
    assert reloader.last_error.code == "invalid_config_value"
    assert "super-secret-token" not in str(reloader.last_error)
