"""Tests for `hermes update --yes / --force` — skip interactive prompts.

Covers:
  1. --yes and --force auto-apply config migration without prompting
  2. --yes and --force auto-restore stashed changes without prompting
  3. --force acts as a stronger alias for --yes
  4. Without --yes/--force, existing interactive behavior is preserved
  5. Dummy argparsestubs for test isolation (argparse is tested via cmd_update)
"""

import subprocess
from types import SimpleNamespace
from unittest.mock import patch

from hermes_cli.main import cmd_update


def _make_run_side_effect(
    branch="main", verify_ok=True, commit_count="1", dirty=False
):
    """Minimal subprocess.run side_effect for the update flow."""

    def side_effect(cmd, **kwargs):
        joined = " ".join(str(c) for c in cmd)

        if "rev-parse" in joined and "--abbrev-ref" in joined:
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{branch}\n", stderr="")
        if "rev-parse" in joined and "--verify" in joined:
            return subprocess.CompletedProcess(
                cmd, 0 if verify_ok else 128, stdout="", stderr=""
            )
        if "rev-list" in joined:
            return subprocess.CompletedProcess(
                cmd, 0, stdout=f"{commit_count}\n", stderr=""
            )
        if "status" in joined and "--porcelain" in joined:
            out = " M hermes_cli/main.py\n" if dirty else ""
            return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")
        if "stash" in joined and "list" in joined:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return side_effect


class TestUpdateYesConfigMigration:
    """--yes auto-answers the config-migration prompt and skips API-key prompts."""

    @patch("hermes_cli.config.migrate_config")
    @patch("hermes_cli.config.check_config_version", return_value=(1, 2))
    @patch("hermes_cli.config.get_missing_config_fields", return_value=[])
    @patch("hermes_cli.config.get_missing_env_vars", return_value=["NEW_KEY"])
    @patch("shutil.which", return_value=None)
    @patch("subprocess.run")
    def test_yes_auto_migrates_without_input(
        self,
        mock_run,
        _mock_which,
        _mock_missing_env,
        _mock_missing_cfg,
        _mock_version,
        mock_migrate,
        capsys,
    ):
        mock_run.side_effect = _make_run_side_effect(
            branch="main", verify_ok=True, commit_count="1"
        )
        mock_migrate.return_value = {"env_added": [], "config_added": []}

        args = SimpleNamespace(yes=True)

        with patch("builtins.input") as mock_input:
            cmd_update(args)
            mock_input.assert_not_called()

        assert mock_migrate.call_count == 1
        _, kwargs = mock_migrate.call_args
        assert kwargs.get("interactive") is False

        out = capsys.readouterr().out
        assert "--yes: auto-applying config migration" in out
        assert "Would you like to configure them now?" not in out

    @patch("hermes_cli.config.migrate_config")
    @patch("hermes_cli.config.check_config_version", return_value=(1, 2))
    @patch("hermes_cli.config.get_missing_config_fields", return_value=[])
    @patch("hermes_cli.config.get_missing_env_vars", return_value=["NEW_KEY"])
    @patch("shutil.which", return_value=None)
    @patch("subprocess.run")
    def test_no_yes_flag_still_prompts_in_tty(
        self,
        mock_run,
        _mock_which,
        _mock_missing_env,
        _mock_missing_cfg,
        _mock_version,
        mock_migrate,
        capsys,
    ):
        """Regression guard: without --yes, the TTY prompt path still fires."""
        mock_run.side_effect = _make_run_side_effect(
            branch="main", verify_ok=True, commit_count="1"
        )
        mock_migrate.return_value = {"env_added": [], "config_added": []}

        args = SimpleNamespace(yes=False)

        import sys as _sys

        with patch("builtins.input", return_value="n") as mock_input, patch.object(
            _sys.stdin, "isatty", return_value=True
        ), patch.object(_sys.stdout, "isatty", return_value=True):
            cmd_update(args)
            assert mock_input.called
            prompts = [c.args[0] if c.args else "" for c in mock_input.call_args_list]
            assert any("configure them now" in p for p in prompts)


class TestUpdateForceConfigMigration:
    """--force auto-answers the config-migration prompt (same as --yes)."""

    @patch("hermes_cli.config.migrate_config")
    @patch("hermes_cli.config.check_config_version", return_value=(1, 2))
    @patch("hermes_cli.config.get_missing_config_fields", return_value=[])
    @patch("hermes_cli.config.get_missing_env_vars", return_value=["NEW_KEY"])
    @patch("shutil.which", return_value=None)
    @patch("subprocess.run")
    def test_force_auto_migrates_without_input(
        self,
        mock_run,
        _mock_which,
        _mock_missing_env,
        _mock_missing_cfg,
        _mock_version,
        mock_migrate,
        capsys,
    ):
        """--force auto-applies config migration without prompting."""
        mock_run.side_effect = _make_run_side_effect(
            branch="main", verify_ok=True, commit_count="1"
        )
        mock_migrate.return_value = {"env_added": [], "config_added": []}

        args = SimpleNamespace(yes=False, force=True)

        with patch("builtins.input") as mock_input:
            cmd_update(args)
            mock_input.assert_not_called()

        assert mock_migrate.call_count == 1
        _, kwargs = mock_migrate.call_args
        assert kwargs.get("interactive") is False

        out = capsys.readouterr().out
        assert "--force: auto-applying config migration" in out
        assert "Would you like to configure them now?" not in out


class TestUpdateYesStashRestore:
    """--yes auto-restores the pre-update autostash without prompting."""

    @patch("hermes_cli.main._restore_stashed_changes")
    @patch("hermes_cli.main._stash_local_changes_if_needed")
    @patch("hermes_cli.config.migrate_config", return_value={"env_added": [], "config_added": []})
    @patch("hermes_cli.config.check_config_version", return_value=(1, 2))
    @patch("hermes_cli.config.get_missing_config_fields", return_value=[])
    @patch("hermes_cli.config.get_missing_env_vars", return_value=[])
    @patch("shutil.which", return_value=None)
    @patch("subprocess.run")
    def test_yes_auto_restores_stash(
        self,
        mock_run,
        _mock_which,
        _mock_missing_env,
        _mock_missing_cfg,
        _mock_version,
        _mock_migrate,
        mock_stash_needed,
        mock_restore,
    ):
        """--yes should call _restore_stashed_changes with prompt_user=False."""
        mock_run.side_effect = _make_run_side_effect(
            branch="main", verify_ok=True, commit_count="1", dirty=True
        )
        mock_stash_needed.return_value = "stash@{0}"

        args = SimpleNamespace(yes=True)

        with patch("builtins.input") as mock_input:
            cmd_update(args)
            mock_input.assert_not_called()

        assert mock_restore.call_count >= 1
        _, kwargs = mock_restore.call_args
        assert kwargs.get("prompt_user") is False


class TestUpdateForceStashRestore:
    """--force auto-restores the pre-update autostash without prompting."""

    @patch("hermes_cli.main._restore_stashed_changes")
    @patch("hermes_cli.main._stash_local_changes_if_needed")
    @patch("hermes_cli.config.migrate_config", return_value={"env_added": [], "config_added": []})
    @patch("hermes_cli.config.check_config_version", return_value=(1, 2))
    @patch("hermes_cli.config.get_missing_config_fields", return_value=[])
    @patch("hermes_cli.config.get_missing_env_vars", return_value=[])
    @patch("shutil.which", return_value=None)
    @patch("subprocess.run")
    def test_force_auto_restores_stash(
        self,
        mock_run,
        _mock_which,
        _mock_missing_env,
        _mock_missing_cfg,
        _mock_version,
        _mock_migrate,
        mock_stash_needed,
        mock_restore,
    ):
        """--force should call _restore_stashed_changes with prompt_user=False."""
        mock_run.side_effect = _make_run_side_effect(
            branch="main", verify_ok=True, commit_count="1", dirty=True
        )
        mock_stash_needed.return_value = "stash@{0}"

        args = SimpleNamespace(yes=False, force=True)

        with patch("builtins.input") as mock_input:
            cmd_update(args)
            mock_input.assert_not_called()

        assert mock_restore.call_count >= 1
        _, kwargs = mock_restore.call_args
        assert kwargs.get("prompt_user") is False
