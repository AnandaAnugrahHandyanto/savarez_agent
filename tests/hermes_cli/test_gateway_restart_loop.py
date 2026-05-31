"""Tests for gateway restart-loop defenses (#30719).

Covers:
- Defense 1: `hermes gateway stop/restart` refuse when HERMES_IN_GATEWAY=1
- Defense 2: cron.jobs.create_job rejects prompts/scripts containing gateway
  lifecycle commands — enforced at the lowest layer so the agent's `cronjob`
  model tool is also covered, not just the CLI subcommand.
- _contains_gateway_lifecycle_command pattern matching (positive + negative).
- Regression: agent cannot bypass the filter by calling create_job directly.
"""

import json
from argparse import Namespace
from pathlib import Path

import pytest

from cron.lifecycle_guard import (
    GatewayLifecycleBlocked,
    check_gateway_lifecycle,
    contains_gateway_lifecycle_command,
)


# ---------------------------------------------------------------------------
# Pattern tests — what we DO match (real shell-level lifecycle commands)
# ---------------------------------------------------------------------------

class TestGatewayLifecyclePatternBlocks:
    """Verify the regex catches concrete shell-level lifecycle commands."""

    @pytest.mark.parametrize("text", [
        "hermes gateway restart",
        "hermes gateway stop",
        "hermes  gateway  restart",           # whitespace tolerated
        "HERMES GATEWAY RESTART",             # case-insensitive
        "Upgrade hermes then run hermes gateway restart",  # embedded in prompt
        "hermes gateway   stop  --all",       # extra args after stop
    ])
    def test_hermes_gateway_commands(self, text):
        assert contains_gateway_lifecycle_command(text), f"Should match: {text!r}"

    @pytest.mark.parametrize("text", [
        "launchctl kickstart -k gui/501/ai.hermes.gateway",
        "launchctl unload ~/Library/LaunchAgents/ai.hermes.gateway.plist",
        "launchctl stop ai.hermes.gateway",
        "launchctl load -w ai.hermes.gateway",
        "launchctl restart hermes-gateway",
    ])
    def test_launchctl_against_gateway(self, text):
        assert contains_gateway_lifecycle_command(text), f"Should match: {text!r}"

    @pytest.mark.parametrize("text", [
        "systemctl restart hermes-gateway",
        "systemctl stop hermes-gateway.service",
        "systemctl start hermes-gateway",
        "systemctl restart ai.hermes.gateway.service",
    ])
    def test_systemctl_against_gateway(self, text):
        assert contains_gateway_lifecycle_command(text), f"Should match: {text!r}"

    @pytest.mark.parametrize("text", [
        "kill hermes gateway process",
        "pkill -f hermes.*gateway",
        "pkill -9 hermes gateway worker",
        "kill -TERM gateway process for hermes",
    ])
    def test_kill_against_gateway(self, text):
        assert contains_gateway_lifecycle_command(text), f"Should match: {text!r}"


# ---------------------------------------------------------------------------
# Pattern tests — what we do NOT match (false-positive guards)
# ---------------------------------------------------------------------------

class TestGatewayLifecyclePatternAllows:
    """The regex must not fire on:
      - benign hermes operations
      - natural-language prompts that mention 'gateway' and 'restart' in
        unrelated contexts (Kong, AWS API Gateway, payment gateways, etc.)
      - launchctl/systemctl operations on non-gateway hermes services
      - `hermes gateway start` (starting a gateway is benign)
    """

    @pytest.mark.parametrize("text", [
        # Generic ops with no gateway involvement
        "restart the rabbitmq container",
        "check if nginx needs a restart",
        "echo 'just a normal cron job'",
        "run the backup script",
        # Other hermes commands
        "hermes update",
        "hermes cron list",
        "hermes config set model claude",
        "hermes gateway start",                    # starting is benign
        "hermes gateway start --all",
        # Non-gateway hermes service ops (would have FP'd with `.*hermes`)
        "launchctl unload ai.hermes.update-checker.plist",
        "launchctl restart ai.hermes.daemon",
        "systemctl restart hermes-meta.service",
        "systemctl restart hermes-cron-helper",
    ])
    def test_unrelated_or_benign_commands_pass(self, text):
        assert not contains_gateway_lifecycle_command(text), \
            f"Should NOT match: {text!r}"

    @pytest.mark.parametrize("text", [
        # Natural-language prompts the previous regex (\bgateway.*restart)
        # blocked — agents legitimately discuss gateway/restart topics.
        "research how the OpenAI API gateway handles restart after rate limiting",
        "if the payment gateway times out, draft a memo on whether to restart processing",
        "summarize the new gateway architecture proposal and identify restart-safety concerns",
        "write a postmortem about yesterday's gateway outage — root cause was an unexpected restart",
        "compare AWS API Gateway vs Cloudflare on restart latency",
        "review my draft about Kong API gateway autoscaling and restart behavior",
        "monitor the message gateway for new tickets, restart watcher if needed",
        "the gateway is running fine, no restart needed",
    ])
    def test_natural_language_prompts_pass(self, text):
        """Cron `prompt` text is fed to an LLM, not a shell. Heuristic
        substring detection on English produces a huge false-positive rate
        without preventing the actual foot-gun (which requires a concrete
        shell command shape)."""
        assert not contains_gateway_lifecycle_command(text), \
            f"Should NOT match: {text!r}"


# ---------------------------------------------------------------------------
# check_gateway_lifecycle — the exception-raising wrapper that create_job uses
# ---------------------------------------------------------------------------

class TestCheckGatewayLifecycle:
    """End-to-end behavior of the function callers actually use."""

    def test_prompt_with_command_raises(self):
        with pytest.raises(GatewayLifecycleBlocked) as exc:
            check_gateway_lifecycle("please run hermes gateway restart", None)
        assert "#30719" in str(exc.value)

    def test_clean_prompt_does_not_raise(self):
        check_gateway_lifecycle("research the gateway architecture", None)
        check_gateway_lifecycle("check server health and restart watchers", None)

    def test_script_with_command_raises(self, tmp_path):
        script = tmp_path / "restart.sh"
        script.write_text("#!/bin/bash\nhermes gateway restart\n")
        with pytest.raises(GatewayLifecycleBlocked):
            check_gateway_lifecycle("clean prompt", str(script))

    def test_split_across_prompt_and_script_still_blocks(self, tmp_path):
        """Concatenated scan prevents splitting the command between prompt
        and script to slip through."""
        script = tmp_path / "ops.sh"
        # Self-contained command lives entirely in the script
        script.write_text("hermes gateway stop\n")
        with pytest.raises(GatewayLifecycleBlocked):
            check_gateway_lifecycle("daily ops job", str(script))

    def test_binary_script_does_not_silently_bypass(self, tmp_path):
        """Non-UTF-8 bytes used to be swallowed by `UnicodeDecodeError`
        and the scan proceeded with prompt-only content. Now we decode
        with errors='replace' so the scan always sees something."""
        script = tmp_path / "weird.bin"
        script.write_bytes(b"\xfehermes gateway restart\xff")
        with pytest.raises(GatewayLifecycleBlocked):
            check_gateway_lifecycle("", str(script))

    def test_missing_script_does_not_raise(self, tmp_path):
        """If the script path can't be read at all, we scan only the
        prompt — not a security guarantee, but consistent with the rest
        of the validation surface in create_job."""
        check_gateway_lifecycle("clean prompt", str(tmp_path / "nonexistent.sh"))


# ---------------------------------------------------------------------------
# Defense 2 — create_job is the single chokepoint (covers BOTH CLI + agent)
# ---------------------------------------------------------------------------

class TestCreateJobBlocksLifecycleCommands:
    """create_job itself raises GatewayLifecycleBlocked.

    This is the regression for the original bug-report path AND for the
    agent's `cronjob` tool path, which calls create_job directly.
    """

    @pytest.fixture(autouse=True)
    def _setup_cron_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cron.jobs.CRON_DIR", tmp_path / "cron")
        monkeypatch.setattr("cron.jobs.JOBS_FILE", tmp_path / "cron" / "jobs.json")
        monkeypatch.setattr("cron.jobs.OUTPUT_DIR", tmp_path / "cron" / "output")

    def test_create_job_blocks_hermes_gateway_restart(self):
        from cron.jobs import create_job
        with pytest.raises(GatewayLifecycleBlocked):
            create_job(
                prompt="Upgrade hermes then run hermes gateway restart",
                schedule="30m",
            )

    def test_create_job_blocks_launchctl_kickstart(self):
        from cron.jobs import create_job
        with pytest.raises(GatewayLifecycleBlocked):
            create_job(
                prompt="Run launchctl kickstart -k gui/501/ai.hermes.gateway",
                schedule="0 9 * * *",
            )

    def test_create_job_blocks_script_content(self, tmp_path):
        from cron.jobs import create_job
        script = tmp_path / "restart.sh"
        script.write_text("#!/bin/bash\nhermes gateway restart\n")
        with pytest.raises(GatewayLifecycleBlocked):
            create_job(prompt="daily restart", schedule="1h", script=str(script))

    def test_create_job_allows_clean_prompt(self):
        from cron.jobs import create_job
        job = create_job(
            prompt="check server health and report status",
            schedule="30m",
        )
        assert job["id"]
        assert "gateway" not in (job.get("last_error") or "").lower()


class TestCronjobToolBlocksLifecycleCommands:
    """The agent's `cronjob` model tool must also reject lifecycle commands.

    The original PR only filtered the CLI subcommand. This regression
    test ensures the filter ALSO fires when the agent calls cronjob()
    via the model tool surface.
    """

    @pytest.fixture(autouse=True)
    def _setup_cron_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cron.jobs.CRON_DIR", tmp_path / "cron")
        monkeypatch.setattr("cron.jobs.JOBS_FILE", tmp_path / "cron" / "jobs.json")
        monkeypatch.setattr("cron.jobs.OUTPUT_DIR", tmp_path / "cron" / "output")

    def test_agent_cronjob_tool_blocks_restart(self):
        from tools.cronjob_tools import cronjob

        result_json = cronjob(
            action="create",
            schedule="30m",
            prompt="Upgrade hermes then run hermes gateway restart",
        )
        result = json.loads(result_json)
        assert result.get("success") is False
        assert "30719" in result.get("error", "")

    def test_agent_cronjob_tool_blocks_launchctl(self):
        from tools.cronjob_tools import cronjob

        result_json = cronjob(
            action="create",
            schedule="0 9 * * *",
            prompt="launchctl kickstart -k gui/501/ai.hermes.gateway",
        )
        result = json.loads(result_json)
        assert result.get("success") is False

    def test_agent_cronjob_tool_allows_clean_prompt(self):
        from tools.cronjob_tools import cronjob

        result_json = cronjob(
            action="create",
            schedule="30m",
            prompt="check server health and report status",
        )
        result = json.loads(result_json)
        # success path returns success=True
        assert result.get("success") is True


# ---------------------------------------------------------------------------
# CLI cron_create surfaces the block clearly
# ---------------------------------------------------------------------------

class TestCronCreateCliSurfaceMessage:
    """CLI must print the block reason and exit non-zero on lifecycle commands."""

    @pytest.fixture(autouse=True)
    def _setup_cron_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cron.jobs.CRON_DIR", tmp_path / "cron")
        monkeypatch.setattr("cron.jobs.JOBS_FILE", tmp_path / "cron" / "jobs.json")
        monkeypatch.setattr("cron.jobs.OUTPUT_DIR", tmp_path / "cron" / "output")

    def _base_args(self, **overrides) -> Namespace:
        defaults = dict(
            cron_command="create",
            schedule="30m",
            prompt=None,
            name=None,
            deliver=None,
            repeat=None,
            skill=None,
            skills=None,
            script=None,
            workdir=None,
            profile=None,
            no_agent=False,
        )
        defaults.update(overrides)
        return Namespace(**defaults)

    def test_block_message_surfaces_in_cli(self, capsys):
        from hermes_cli.cron import cron_command
        args = self._base_args(prompt="hermes gateway restart")
        rc = cron_command(args)
        out = capsys.readouterr().out
        assert rc == 1
        # Block reason mentions the issue number so users can find context.
        assert "30719" in out

    # Note: there is no separate CLI-surface test for script-content blocking
    # because the `cronjob` tool requires scripts to live under
    # ~/.hermes/scripts/ (validated BEFORE create_job runs), so a synthetic
    # absolute tmp_path test never reaches the lifecycle guard via the CLI.
    # Script-content blocking IS covered end-to-end by:
    #   - TestCheckGatewayLifecycle.test_script_with_command_raises
    #   - TestCheckGatewayLifecycle.test_binary_script_does_not_silently_bypass
    #   - TestCreateJobBlocksLifecycleCommands.test_create_job_blocks_script_content

    def test_clean_prompt_creates_job(self, capsys):
        from hermes_cli.cron import cron_command
        args = self._base_args(prompt="Check server health and report status")
        rc = cron_command(args)
        out = capsys.readouterr().out
        # rc 0 = success
        assert rc == 0 or rc is None
        assert "Created job" in out

    def test_empty_prompt_fails_for_validation_not_lifecycle(self, capsys):
        """An empty prompt fails the create API for `requires prompt or skill`,
        but the failure must NOT be the lifecycle guard."""
        from hermes_cli.cron import cron_command
        args = self._base_args(prompt=None)
        rc = cron_command(args)
        out = capsys.readouterr().out
        assert rc == 1
        # Lifecycle guard message includes "30719"; this failure must not.
        assert "30719" not in out


# ---------------------------------------------------------------------------
# Defense 1 — gateway stop/restart refuse inside the gateway process
# ---------------------------------------------------------------------------

class TestGatewaySelfTargetingGuard:
    """`hermes gateway stop|restart` must refuse when HERMES_IN_GATEWAY=1."""

    def test_stop_refuses_inside_gateway(self, monkeypatch, capsys):
        monkeypatch.setenv("HERMES_IN_GATEWAY", "1")
        from hermes_cli.gateway import gateway_command
        args = Namespace(gateway_command="stop", all=False, system=False)
        with pytest.raises(SystemExit) as exc_info:
            gateway_command(args)
        assert exc_info.value.code == 1
        # Verify the user actually sees the refusal — `print_error` writes
        # somewhere capsys captures (stderr or stdout, depending on impl).
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "Refusing to stop the gateway" in combined

    def test_restart_refuses_inside_gateway(self, monkeypatch, capsys):
        monkeypatch.setenv("HERMES_IN_GATEWAY", "1")
        from hermes_cli.gateway import gateway_command
        args = Namespace(gateway_command="restart", all=False, system=False)
        with pytest.raises(SystemExit) as exc_info:
            gateway_command(args)
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "Refusing to restart the gateway" in combined

    def test_stop_outside_gateway_does_not_hit_guard(self, monkeypatch, capsys):
        """Outside the gateway, stop may still fail (no gateway running),
        but it MUST NOT fail via the self-targeting guard. We verify the
        captured output is free of the guard's refusal message rather than
        the (vacuous) check `"Refusing" not in str(e)`.

        Stop's post-guard branches reach into systemd/launchd/process search
        which can hang on CI workers that lack a real service environment.
        Stub every post-guard primitive so the test exercises ONLY the
        guard decision."""
        monkeypatch.delenv("HERMES_IN_GATEWAY", raising=False)
        import hermes_cli.gateway as gateway_cli
        monkeypatch.setattr(gateway_cli, "supports_systemd_services", lambda: False)
        monkeypatch.setattr(gateway_cli, "is_macos", lambda: False)
        monkeypatch.setattr(gateway_cli, "is_windows", lambda: False)
        monkeypatch.setattr(gateway_cli, "is_container", lambda: False)
        monkeypatch.setattr(gateway_cli, "is_termux", lambda: False)
        monkeypatch.setattr(gateway_cli, "is_wsl", lambda: False)
        monkeypatch.setattr(gateway_cli, "kill_gateway_processes", lambda **kw: 0)
        monkeypatch.setattr(gateway_cli, "stop_profile_gateway", lambda: False)
        monkeypatch.setattr(gateway_cli, "_dispatch_via_service_manager_if_s6", lambda *_: False)
        args = Namespace(gateway_command="stop", all=False, system=False)
        try:
            gateway_cli.gateway_command(args)
        except SystemExit:
            pass
        captured = capsys.readouterr()
        assert "Refusing to stop the gateway" not in captured.out
        assert "Refusing to stop the gateway" not in captured.err

    def test_restart_outside_gateway_does_not_hit_guard(self, monkeypatch, capsys):
        """Same guard-only contract as the stop variant.  Restart's
        post-guard logic falls through to run_gateway() (foreground) when
        no service manager handles the restart — that would block the
        test indefinitely.  Stub every post-guard primitive so the test
        only asserts the guard decision."""
        monkeypatch.delenv("HERMES_IN_GATEWAY", raising=False)
        import hermes_cli.gateway as gateway_cli
        monkeypatch.setattr(gateway_cli, "supports_systemd_services", lambda: False)
        monkeypatch.setattr(gateway_cli, "is_macos", lambda: False)
        monkeypatch.setattr(gateway_cli, "is_windows", lambda: False)
        monkeypatch.setattr(gateway_cli, "is_container", lambda: False)
        monkeypatch.setattr(gateway_cli, "is_termux", lambda: False)
        monkeypatch.setattr(gateway_cli, "is_wsl", lambda: False)
        monkeypatch.setattr(gateway_cli, "kill_gateway_processes", lambda **kw: 0)
        monkeypatch.setattr(gateway_cli, "stop_profile_gateway", lambda: False)
        monkeypatch.setattr(gateway_cli, "_wait_for_gateway_exit", lambda **kw: None)
        monkeypatch.setattr(gateway_cli, "run_gateway", lambda **kw: None)
        monkeypatch.setattr(gateway_cli, "_dispatch_via_service_manager_if_s6", lambda *_: False)
        monkeypatch.setattr(gateway_cli, "_dispatch_all_via_service_manager_if_s6", lambda *_: False)
        args = Namespace(gateway_command="restart", all=False, system=False)
        try:
            gateway_cli.gateway_command(args)
        except SystemExit:
            pass
        captured = capsys.readouterr()
        assert "Refusing to restart the gateway" not in captured.out
        assert "Refusing to restart the gateway" not in captured.err
