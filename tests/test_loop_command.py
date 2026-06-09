"""Tests for /loop slash command — parsing, creation, and loop evaluation."""

import hashlib
import json
import pytest
from unittest.mock import patch, MagicMock
from subprocess import CompletedProcess, TimeoutExpired

from hermes_cli.loop_command import handle_loop_command, _parse_create_args
from cron.scheduler import _evaluate_loop_tick, _run_loop_verify


# =========================================================================
# _parse_create_args
# =========================================================================

class TestParseCreateArgs:
    def test_basic_interval_and_prompt(self):
        r = _parse_create_args("5m check the deployment")
        assert r["schedule"] == "5m"
        assert r["prompt"] == "check the deployment"
        assert r["skills"] is None
        assert r["verify"] is None
        assert r["error"] is None

    def test_every_prefix(self):
        r = _parse_create_args("every 2h monitor disk usage")
        assert r["schedule"] == "every 2h"
        assert r["prompt"] == "monitor disk usage"

    def test_skills_flag(self):
        r = _parse_create_args("30m check logs --skills devops,networking")
        assert r["schedule"] == "30m"
        assert r["skills"] == ["devops", "networking"]
        assert r["prompt"] == "check logs"

    def test_verify_flag_bare(self):
        r = _parse_create_args("5m fix tests --verify pytest")
        assert r["schedule"] == "5m"
        assert r["verify"] == "pytest"
        assert r["prompt"] == "fix tests"

    def test_verify_flag_quoted(self):
        r = _parse_create_args('5m fix tests --verify "npm test -- -u"')
        assert r["verify"] == "npm test -- -u"

    def test_verify_flag_single_quotes(self):
        r = _parse_create_args("5m fix tests --verify 'pytest -x -v'")
        assert r["verify"] == "pytest -x -v"

    def test_skills_and_verify_combined(self):
        r = _parse_create_args("1h review PRs --skills github-code-review --verify 'gh pr checks'")
        assert r["schedule"] == "1h"
        assert r["prompt"] == "review PRs"
        assert r["skills"] == ["github-code-review"]
        assert r["verify"] == "gh pr checks"

    def test_verify_before_skills_ordering(self):
        """--verify without quotes should NOT eat --skills when --skills is parsed first."""
        r = _parse_create_args("30m check status --verify pytest --skills devops")
        assert r["schedule"] == "30m"
        assert r["prompt"] == "check status"
        assert r["skills"] == ["devops"]
        assert r["verify"] == "pytest"

    def test_name_flag(self):
        r = _parse_create_args("30m check logs --name log-watcher")
        assert r["schedule"] == "30m"
        assert r["prompt"] == "check logs"
        assert r["name"] == "log-watcher"

    def test_name_with_skills_and_verify(self):
        r = _parse_create_args("1h review PRs --name pr-check --skills github-code-review --verify 'gh pr checks'")
        assert r["schedule"] == "1h"
        assert r["prompt"] == "review PRs"
        assert r["name"] == "pr-check"
        assert r["skills"] == ["github-code-review"]
        assert r["verify"] == "gh pr checks"

    def test_missing_prompt(self):
        r = _parse_create_args("5m")
        assert r["error"] == "Missing prompt text"

    def test_missing_every_prompt(self):
        r = _parse_create_args("every 30m")
        assert r["error"] == "Missing prompt text"

    def test_empty_string(self):
        r = _parse_create_args("")
        assert r["error"] == "Missing interval and prompt"


# =========================================================================
# handle_loop_command
# =========================================================================

class TestHandleLoopCommand:
    def test_empty_returns_usage(self):
        result = json.loads(handle_loop_command(""))
        assert result["success"] is True
        assert "Usage" in result["message"]

    def test_status_returns_success(self):
        result = json.loads(handle_loop_command("status"))
        assert result["success"] is True

    def test_pause_missing_id(self):
        result = json.loads(handle_loop_command("pause"))
        assert result["success"] is False
        assert "Usage" in result["error"]

    def test_resume_missing_id(self):
        result = json.loads(handle_loop_command("resume"))
        assert result["success"] is False
        assert "Usage" in result["error"]

    def test_stop_missing_id(self):
        result = json.loads(handle_loop_command("stop"))
        assert result["success"] is False
        assert "Usage" in result["error"]

    def test_remove_missing_id(self):
        result = json.loads(handle_loop_command("remove"))
        assert result["success"] is False
        assert "Usage" in result["error"]

    def test_list_alias(self):
        result = json.loads(handle_loop_command("list"))
        assert result["success"] is True

    def test_help_alias(self):
        result = json.loads(handle_loop_command("help"))
        assert result["success"] is True
        assert "Usage" in result["message"]


# =========================================================================
# Loop evaluation logic (hash-based no-progress detection)
# =========================================================================

class TestLoopEvaluation:
    def test_hash_consistency(self):
        """Same input always produces the same hash."""
        text = "deployment is healthy, all pods running"
        h1 = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        h2 = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        assert h1 == h2

    def test_hash_differs_on_different_input(self):
        h1 = hashlib.sha256("output A".encode("utf-8")).hexdigest()[:16]
        h2 = hashlib.sha256("output B".encode("utf-8")).hexdigest()[:16]
        assert h1 != h2

    def test_no_progress_count_increments_on_same_hash(self):
        """When output hash matches previous, counter should increment."""
        response_hash = hashlib.sha256("same output".encode("utf-8")).hexdigest()[:16]
        last_hash = response_hash
        no_progress_count = 0
        threshold = 3

        if response_hash == last_hash:
            no_progress_count += 1

        assert no_progress_count == 1

    def test_no_progress_count_resets_on_different_hash(self):
        """When output hash changes, counter should reset to 0."""
        hash_a = hashlib.sha256("output A".encode("utf-8")).hexdigest()[:16]
        hash_b = hashlib.sha256("output B".encode("utf-8")).hexdigest()[:16]
        no_progress_count = 2

        if hash_b != hash_a:
            no_progress_count = 0

        assert no_progress_count == 0

    def test_threshold_triggers_pause(self):
        """When no_progress_count hits threshold, should trigger pause."""
        threshold = 3
        no_progress_count = 3
        should_pause = no_progress_count >= threshold
        assert should_pause is True

    def test_below_threshold_no_pause(self):
        threshold = 3
        no_progress_count = 2
        should_pause = no_progress_count >= threshold
        assert should_pause is False

    def test_delivery_gating_same_hash(self):
        """Skip delivery when output hash matches last delivered hash."""
        response_hash = "abc123"
        last_delivered_hash = "abc123"
        skip = last_delivered_hash is not None and response_hash == last_delivered_hash
        assert skip is True

    def test_delivery_gating_different_hash(self):
        """Deliver when output hash differs from last delivered."""
        response_hash = "abc123"
        last_delivered_hash = "def456"
        skip = last_delivered_hash is not None and response_hash == last_delivered_hash
        assert skip is False

    def test_delivery_gating_first_run(self):
        """Deliver on first run (no previous hash)."""
        response_hash = "abc123"
        last_delivered_hash = None
        skip = last_delivered_hash is not None and response_hash == last_delivered_hash
        assert skip is False


# =========================================================================
# _run_loop_verify (mocked subprocess)
# =========================================================================

class TestRunLoopVerify:
    def test_no_verify_command(self):
        """No verify command configured -> returns None."""
        job = {"loop_verify": None}
        assert _run_loop_verify(job) is None

    def test_no_verify_key(self):
        """Job without loop_verify key -> returns None."""
        job = {}
        assert _run_loop_verify(job) is None

    @patch("cron.scheduler.subprocess.run")
    def test_verify_success(self, mock_run):
        """Verify command exits 0 -> returns None."""
        mock_run.return_value = CompletedProcess([], 0, stdout="", stderr="")
        job = {"loop_verify": "echo ok"}
        assert _run_loop_verify(job) is None
        mock_run.assert_called_once_with(
            "echo ok", shell=True, capture_output=True, text=True, timeout=60,
        )

    @patch("cron.scheduler.subprocess.run")
    def test_verify_failure_with_stderr(self, mock_run):
        """Verify command exits non-zero with stderr -> returns error string."""
        mock_run.return_value = CompletedProcess(
            [], 1, stdout="output here", stderr="something broke",
        )
        job = {"loop_verify": "pytest"}
        result = _run_loop_verify(job)
        assert result is not None
        assert "exit 1" in result
        assert "something broke" in result
        assert "output here" in result

    @patch("cron.scheduler.subprocess.run")
    def test_verify_failure_stdout_only(self, mock_run):
        """Verify fails with stdout but no stderr."""
        mock_run.return_value = CompletedProcess(
            [], 2, stdout="FAIL: 3 tests", stderr="",
        )
        job = {"loop_verify": "pytest"}
        result = _run_loop_verify(job)
        assert result is not None
        assert "exit 2" in result
        assert "FAIL: 3 tests" in result
        assert "stderr" not in result

    @patch("cron.scheduler.subprocess.run")
    def test_verify_timeout(self, mock_run):
        """Verify command times out -> returns timeout message."""
        mock_run.side_effect = TimeoutExpired("pytest", 60)
        job = {"loop_verify": "pytest --slow"}
        result = _run_loop_verify(job)
        assert result is not None
        assert "timed out" in result
        assert "60s" in result

    @patch("cron.scheduler.subprocess.run")
    def test_verify_generic_exception(self, mock_run):
        """Verify command raises unexpected error -> returns error string."""
        mock_run.side_effect = OSError("no such file")
        job = {"loop_verify": "/nonexistent/cmd"}
        result = _run_loop_verify(job)
        assert result is not None
        assert "no such file" in result


# =========================================================================
# _evaluate_loop_tick (integration — full state machine)
# =========================================================================

def _make_loop_job(**overrides):
    """Create a minimal loop job dict for testing."""
    job = {
        "id": "test123",
        "name": "test-loop",
        "prompt": "check deployment status",
        "loop": True,
        "loop_verify": None,
        "loop_no_progress_threshold": 3,
        "loop_no_progress_count": 0,
        "loop_last_output_hash": None,
        "loop_last_response": None,
        "loop_last_delivered_hash": None,
        "loop_last_verify_error": None,
    }
    job.update(overrides)
    return job


class TestEvaluateLoopTickIntegration:
    @patch("cron.jobs.update_job")
    @patch("cron.jobs.pause_job")
    def test_first_run_delivers(self, mock_pause, mock_update):
        """First run with no previous hash -> delivers, no pause."""
        job = _make_loop_job()
        alert, skip = _evaluate_loop_tick(job, "some output")
        assert alert is None
        assert skip is False  # no previous delivered hash -> deliver
        mock_update.assert_called_once()
        mock_pause.assert_not_called()
        # Verify the update includes the hash
        updates = mock_update.call_args[0][1]
        assert updates["loop_last_output_hash"] is not None
        assert updates["loop_no_progress_count"] == 0

    @patch("cron.jobs.update_job")
    @patch("cron.jobs.pause_job")
    def test_same_output_increments_count(self, mock_pause, mock_update):
        """Same output twice -> count increments, no pause."""
        response_hash = hashlib.sha256(b"same output").hexdigest()[:16]
        job = _make_loop_job(loop_last_output_hash=response_hash)

        alert, skip = _evaluate_loop_tick(job, "same output")
        assert alert is None
        assert skip is False  # first delivery of this hash
        updates = mock_update.call_args[0][1]
        assert updates["loop_no_progress_count"] == 1
        mock_pause.assert_not_called()

    @patch("cron.jobs.update_job")
    @patch("cron.jobs.pause_job")
    def test_same_output_threshold_triggers_pause(self, mock_pause, mock_update):
        """Same output reaching threshold -> auto-pause."""
        response_hash = hashlib.sha256(b"stuck output").hexdigest()[:16]
        job = _make_loop_job(
            loop_last_output_hash=response_hash,
            loop_no_progress_count=2,  # one away from threshold
        )

        alert, skip = _evaluate_loop_tick(job, "stuck output")
        assert alert is not None
        assert "auto-paused" in alert
        assert skip is True
        mock_pause.assert_called_once_with("test123", reason="no progress detected")

    @patch("cron.jobs.update_job")
    @patch("cron.jobs.pause_job")
    def test_different_output_resets_count(self, mock_pause, mock_update):
        """Different output -> count resets to 0."""
        old_hash = hashlib.sha256(b"old output").hexdigest()[:16]
        job = _make_loop_job(
            loop_last_output_hash=old_hash,
            loop_no_progress_count=2,
        )

        alert, skip = _evaluate_loop_tick(job, "new output")
        assert alert is None
        updates = mock_update.call_args[0][1]
        assert updates["loop_no_progress_count"] == 0
        mock_pause.assert_not_called()

    @patch("hermes_cli.goals.judge_goal", return_value=("done", "goal achieved", False))
    @patch("cron.jobs.update_job")
    @patch("cron.jobs.pause_job")
    def test_judge_done_increments_count(self, mock_pause, mock_update, mock_judge):
        """Judge returns 'done' -> count increments (no progress in loop context)."""
        job = _make_loop_job()

        alert, skip = _evaluate_loop_tick(job, "all tests passing")
        # count goes from 0 -> 1, threshold is 3, no pause yet
        assert alert is None
        updates = mock_update.call_args[0][1]
        assert updates["loop_no_progress_count"] == 1
        mock_pause.assert_not_called()

    @patch("hermes_cli.goals.judge_goal", return_value=("done", "goal achieved", False))
    @patch("cron.jobs.update_job")
    @patch("cron.jobs.pause_job")
    def test_judge_done_threshold_triggers_pause(self, mock_pause, mock_update, mock_judge):
        """Judge 'done' pushes count to threshold -> auto-pause."""
        response_hash = hashlib.sha256(b"everything done").hexdigest()[:16]
        job = _make_loop_job(
            loop_last_output_hash=response_hash,  # same hash so count doesn't reset
            loop_no_progress_count=1,  # hash match -> 2, judge done -> 3 = threshold
        )

        alert, skip = _evaluate_loop_tick(job, "everything done")
        assert alert is not None
        assert "auto-paused" in alert
        mock_pause.assert_called_once()

    @patch("hermes_cli.goals.judge_goal", side_effect=Exception("model unavailable"))
    @patch("cron.jobs.update_job")
    @patch("cron.jobs.pause_job")
    def test_judge_failure_fail_open(self, mock_pause, mock_update, mock_judge):
        """Judge throws exception -> fail-open, continues without pausing."""
        job = _make_loop_job()

        alert, skip = _evaluate_loop_tick(job, "some output")
        assert alert is None
        # count stays at 0 because judge didn't return 'done'
        updates = mock_update.call_args[0][1]
        assert updates["loop_no_progress_count"] == 0
        mock_pause.assert_not_called()

    @patch("cron.scheduler._run_loop_verify", return_value="verify failed: exit 1")
    @patch("cron.jobs.update_job")
    @patch("cron.jobs.pause_job")
    def test_verify_error_stored_on_job(self, mock_pause, mock_update, mock_verify):
        """Verify error -> stored in loop_last_verify_error field."""
        job = _make_loop_job(loop_verify="pytest")

        alert, skip = _evaluate_loop_tick(job, "some output")
        assert alert is None
        updates = mock_update.call_args[0][1]
        assert updates["loop_last_verify_error"] == "verify failed: exit 1"

    @patch("cron.scheduler._run_loop_verify", return_value=None)
    @patch("cron.jobs.update_job")
    @patch("cron.jobs.pause_job")
    def test_verify_success_clears_error(self, mock_pause, mock_update, mock_verify):
        """Verify passes -> loop_last_verify_error set to None."""
        job = _make_loop_job(loop_verify="pytest", loop_last_verify_error="old error")

        alert, skip = _evaluate_loop_tick(job, "some output")
        assert alert is None
        updates = mock_update.call_args[0][1]
        assert updates["loop_last_verify_error"] is None

    @patch("cron.jobs.update_job")
    @patch("cron.jobs.pause_job")
    def test_delivery_gating_same_as_last_delivered(self, mock_pause, mock_update):
        """Same hash as last delivered -> skip delivery."""
        response_hash = hashlib.sha256(b"same output").hexdigest()[:16]
        job = _make_loop_job(
            loop_last_output_hash="different_hash",  # so count resets
            loop_last_delivered_hash=response_hash,  # same as current
        )

        alert, skip = _evaluate_loop_tick(job, "same output")
        assert alert is None
        assert skip is True  # delivery skipped

    @patch("cron.jobs.update_job")
    @patch("cron.jobs.pause_job")
    def test_delivery_gating_different_from_last(self, mock_pause, mock_update):
        """Different hash from last delivered -> deliver."""
        job = _make_loop_job(
            loop_last_output_hash="old_hash",
            loop_last_delivered_hash="old_hash",
        )

        alert, skip = _evaluate_loop_tick(job, "new output")
        assert alert is None
        assert skip is False  # deliver

    @patch("cron.jobs.update_job")
    @patch("cron.jobs.pause_job")
    def test_empty_response_hashes_consistently(self, mock_pause, mock_update):
        """Empty response should hash consistently and not crash."""
        job = _make_loop_job()

        alert, skip = _evaluate_loop_tick(job, "")
        assert alert is None
        updates = mock_update.call_args[0][1]
        assert updates["loop_last_output_hash"] is not None
        # Empty response shouldn't set delivered hash
        assert "loop_last_delivered_hash" not in updates

    @patch("cron.jobs.update_job")
    @patch("cron.jobs.pause_job")
    def test_none_response_hashes_consistently(self, mock_pause, mock_update):
        """None response should hash as empty string."""
        job = _make_loop_job()

        alert, skip = _evaluate_loop_tick(job, None)
        assert alert is None
        updates = mock_update.call_args[0][1]
        # Should hash the same as empty string
        expected_hash = hashlib.sha256(b"").hexdigest()[:16]
        assert updates["loop_last_output_hash"] == expected_hash
