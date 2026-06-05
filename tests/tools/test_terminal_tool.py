"""Regression tests for sudo detection and sudo password handling."""

import json

import tools.terminal_tool as terminal_tool


def setup_function():
    terminal_tool._reset_cached_sudo_passwords()


def teardown_function():
    terminal_tool._reset_cached_sudo_passwords()


def test_searching_for_sudo_does_not_trigger_rewrite(monkeypatch):
    monkeypatch.delenv("SUDO_PASSWORD", raising=False)
    monkeypatch.delenv("HERMES_INTERACTIVE", raising=False)

    command = "rg --line-number --no-heading --with-filename 'sudo' . | head -n 20"
    transformed, sudo_stdin = terminal_tool._transform_sudo_command(command)

    assert transformed == command
    assert sudo_stdin is None


def test_printf_literal_sudo_does_not_trigger_rewrite(monkeypatch):
    monkeypatch.delenv("SUDO_PASSWORD", raising=False)
    monkeypatch.delenv("HERMES_INTERACTIVE", raising=False)

    command = "printf '%s\\n' sudo"
    transformed, sudo_stdin = terminal_tool._transform_sudo_command(command)

    assert transformed == command
    assert sudo_stdin is None


def test_non_command_argument_named_sudo_does_not_trigger_rewrite(monkeypatch):
    monkeypatch.delenv("SUDO_PASSWORD", raising=False)
    monkeypatch.delenv("HERMES_INTERACTIVE", raising=False)

    command = "grep -n sudo README.md"
    transformed, sudo_stdin = terminal_tool._transform_sudo_command(command)

    assert transformed == command
    assert sudo_stdin is None


def test_actual_sudo_command_uses_configured_password(monkeypatch):
    monkeypatch.setenv("SUDO_PASSWORD", "testpass")
    monkeypatch.delenv("HERMES_INTERACTIVE", raising=False)

    transformed, sudo_stdin = terminal_tool._transform_sudo_command("sudo apt install -y ripgrep")

    assert transformed == "sudo -S -p '' apt install -y ripgrep"
    assert sudo_stdin == "testpass\n"


def test_actual_sudo_after_leading_env_assignment_is_rewritten(monkeypatch):
    monkeypatch.setenv("SUDO_PASSWORD", "testpass")
    monkeypatch.delenv("HERMES_INTERACTIVE", raising=False)

    transformed, sudo_stdin = terminal_tool._transform_sudo_command("DEBUG=1 sudo whoami")

    assert transformed == "DEBUG=1 sudo -S -p '' whoami"
    assert sudo_stdin == "testpass\n"


def test_explicit_empty_sudo_password_tries_empty_without_prompt(monkeypatch):
    monkeypatch.setenv("SUDO_PASSWORD", "")
    monkeypatch.setenv("HERMES_INTERACTIVE", "1")

    def _fail_prompt(*_args, **_kwargs):
        raise AssertionError("interactive sudo prompt should not run for explicit empty password")

    monkeypatch.setattr(terminal_tool, "_prompt_for_sudo_password", _fail_prompt)

    transformed, sudo_stdin = terminal_tool._transform_sudo_command("sudo true")

    assert transformed == "sudo -S -p '' true"
    assert sudo_stdin == "\n"


def test_cached_sudo_password_is_used_when_env_is_unset(monkeypatch):
    monkeypatch.delenv("SUDO_PASSWORD", raising=False)
    monkeypatch.delenv("HERMES_INTERACTIVE", raising=False)
    terminal_tool._set_cached_sudo_password("cached-pass")

    transformed, sudo_stdin = terminal_tool._transform_sudo_command("echo ok && sudo whoami")

    assert transformed == "echo ok && sudo -S -p '' whoami"
    assert sudo_stdin == "cached-pass\n"


def test_cached_sudo_password_isolated_by_session_key(monkeypatch):
    monkeypatch.delenv("SUDO_PASSWORD", raising=False)
    monkeypatch.delenv("HERMES_INTERACTIVE", raising=False)

    monkeypatch.setenv("HERMES_SESSION_KEY", "session-a")
    terminal_tool._set_cached_sudo_password("alpha-pass")

    monkeypatch.setenv("HERMES_SESSION_KEY", "session-b")
    assert terminal_tool._get_cached_sudo_password() == ""

    monkeypatch.setenv("HERMES_SESSION_KEY", "session-a")
    assert terminal_tool._get_cached_sudo_password() == "alpha-pass"


def test_passwordless_sudo_skips_interactive_prompt_and_rewrite(monkeypatch):
    monkeypatch.delenv("SUDO_PASSWORD", raising=False)
    monkeypatch.delenv("TERMINAL_ENV", raising=False)
    monkeypatch.setenv("HERMES_INTERACTIVE", "1")

    def _fail_prompt(*_args, **_kwargs):
        raise AssertionError(
            "interactive sudo prompt should not run when sudo -n already works"
        )

    monkeypatch.setattr(terminal_tool, "_prompt_for_sudo_password", _fail_prompt)
    monkeypatch.setattr(terminal_tool, "_sudo_nopasswd_works", lambda: True, raising=False)

    transformed, sudo_stdin = terminal_tool._transform_sudo_command("sudo whoami")

    assert transformed == "sudo whoami"
    assert sudo_stdin is None


def test_passwordless_sudo_probe_rechecks_local_terminal(monkeypatch):
    monkeypatch.delenv("TERMINAL_ENV", raising=False)
    calls = []

    class Result:
        def __init__(self, returncode):
            self.returncode = returncode

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return Result(0 if len(calls) == 1 else 1)

    monkeypatch.setattr(terminal_tool.subprocess, "run", fake_run)

    assert terminal_tool._sudo_nopasswd_works() is True
    assert terminal_tool._sudo_nopasswd_works() is False
    assert len(calls) == 2
    assert calls[0][0] == ["sudo", "-n", "true"]
    assert calls[1][0] == ["sudo", "-n", "true"]


def test_passwordless_sudo_probe_is_disabled_for_nonlocal_terminal_env(monkeypatch):
    monkeypatch.setenv("TERMINAL_ENV", "docker")

    def _fail_run(*_args, **_kwargs):
        raise AssertionError("host sudo probe must not run for non-local terminal envs")

    monkeypatch.setattr(terminal_tool.subprocess, "run", _fail_run)

    assert terminal_tool._sudo_nopasswd_works() is False


def test_validate_workdir_allows_windows_drive_paths():
    assert terminal_tool._validate_workdir(r"C:\Users\Alice\project") is None
    assert terminal_tool._validate_workdir("C:/Users/Alice/project") is None


def test_validate_workdir_allows_windows_unc_paths():
    assert terminal_tool._validate_workdir(r"\\server\share\project") is None


def test_validate_workdir_blocks_shell_metacharacters_in_windows_paths():
    assert terminal_tool._validate_workdir(r"C:\Users\Alice\project; rm -rf /")
    assert terminal_tool._validate_workdir(r"C:\Users\Alice\project$(whoami)")
    assert terminal_tool._validate_workdir("C:\\Users\\Alice\\project\nwhoami")


def test_terminal_description_routes_codex_implementation_to_staged_tool():
    description = terminal_tool.TERMINAL_TOOL_DESCRIPTION

    assert "codex_staged_implement" in description
    assert "Do NOT call raw `codex-yuna exec`" in description
    assert "codex_stage_runner.py" in description
    assert "codex_impl_guard.py" in description
    assert "codex_review_guard.py" in description


def test_codex_review_subcommand_guard_accepts_json_schema_and_last_message():
    command = (
        "codex-yuna exec review --uncommitted --json "
        "--output-schema /tmp/codex_review_schema.json "
        "--output-last-message /tmp/codex_review_final.json "
        "'review current changes'"
    )

    assert terminal_tool._codex_review_launch_error(command) is None


def test_codex_read_only_review_prompt_guard_accepts_color_never():
    command = (
        "codex-yuna exec --sandbox read-only --json "
        "--output-schema /tmp/codex_review_schema.json "
        "--output-last-message /tmp/codex_review_final.json "
        "--color never 'review current changes'"
    )

    assert terminal_tool._codex_review_launch_error(command) is None


def test_codex_review_guard_wrapper_is_accepted():
    command = (
        "python scripts/runtime/codex_review_guard.py "
        "--prompt 'review current changes'"
    )

    assert terminal_tool._codex_review_launch_error(command) is None
    assert terminal_tool._foreground_background_guidance(command) is None


def test_codex_controlled_impl_wrappers_do_not_trigger_foreground_guidance():
    commands = (
        "python scripts/runtime/codex_impl_guard.py --prompt 'implement the change'",
        "python scripts/runtime/codex_stage_runner.py --stage 1",
    )

    for command in commands:
        assert terminal_tool._codex_review_launch_error(command) is None
        assert terminal_tool._foreground_background_guidance(command) is None


def test_bare_foreground_codex_exec_gets_background_notify_guidance():
    commands = (
        "codex-yuna exec 'implement the change'",
        "codex exec 'implement the change'",
    )

    for command in commands:
        guidance = terminal_tool._foreground_background_guidance(command)

        assert guidance is not None
        assert "background=true" in guidance
        assert "notify_on_complete=true" in guidance


def test_bare_codex_impl_launch_is_blocked_even_in_background():
    commands = (
        "codex-yuna exec --full-auto 'implement the change'",
        "codex exec 'implement the change'",
        "env FOO=bar codex-yuna exec 'implement the change'",
        "bash -lc 'codex-yuna exec implement the change'",
        "codex-yuna exec --full-auto 'review and implement the change'",
        "codex exec 'review the code then fix it'",
        "codex-yuna exec review and implement the change",
        "codex exec review then fix it",
        "codex-yuna exec review and implement the change --json --output-schema /tmp/schema --output-last-message /tmp/final",
        "codex-yuna exec --full-auto review and implement --json --output-schema /tmp/schema --output-last-message /tmp/final",
        "codex-yuna exec review --sandbox read-only --json --output-schema /tmp/schema --output-last-message /tmp/final 'review then fix it'",
    )

    for command in commands:
        error = terminal_tool._codex_unguarded_impl_launch_error(command)

        assert error is not None
        assert "unguarded Codex implementation" in error
        assert "codex_staged_implement" in error
        assert "allowed_files" in error
        assert "allowed_globs" in error
        assert "codex_stage_runner.py" in error
        assert "codex_impl_guard.py" in error
        assert "codex_review_guard.py" in error


def test_bare_read_only_codex_review_launch_is_not_blocked_as_impl():
    commands = (
        "codex-yuna exec --sandbox read-only --json --output-schema /tmp/schema --output-last-message /tmp/final --color never 'review current changes'",
        "codex-yuna exec --sandbox=read-only --json --output-schema /tmp/schema --output-last-message /tmp/final --color=never 'review current changes'",
        "codex-yuna exec review --sandbox read-only --json --output-schema /tmp/schema --output-last-message /tmp/final 'review current changes'",
    )

    for command in commands:
        assert terminal_tool._codex_unguarded_impl_launch_error(command) is None


def test_codex_impl_guard_wrappers_are_not_blocked_as_unguarded_impl():
    commands = (
        "python scripts/runtime/codex_impl_guard.py --prompt 'implement one slice'",
        "python scripts/runtime/codex_stage_runner.py --plan-file /tmp/stage-plan.json",
        "python scripts/runtime/codex_review_guard.py --prompt 'review current changes'",
        "codex-yuna exec --help",
        "codex --version",
    )

    for command in commands:
        assert terminal_tool._codex_unguarded_impl_launch_error(command) is None


def test_terminal_tool_blocks_background_bare_codex_impl_before_execution():
    result = json.loads(terminal_tool.terminal_tool(
        command="codex-yuna exec --full-auto 'implement the change'",
        background=True,
        pty=True,
        notify_on_complete=True,
    ))

    assert result["status"] == "blocked"
    assert result["code"] == "codex_unguarded_impl_blocked"
    assert result["recommended_action"] == "use_codex_staged_implement"
    assert "已拦截裸 Codex 开发调用" in result["error"]
    assert "codex_staged_implement" in result["error"]
    assert "allowed_files" in result["error"]
    assert "allowed_globs" in result["error"]
    assert "codex_stage_runner.py" in result["error"]
    assert "codex_impl_guard.py" in result["error"]
    assert "codex_review_guard.py --prompt <TEXT>" in result["error"]
    assert "新会话或 runtime 重载" in result["error"]
    assert result["user_message_zh"] == result["error"]
    assert "unguarded Codex implementation" in result["technical_detail"]
    assert "codex_staged_implement" in result["technical_detail"]


def test_bare_codex_after_controlled_wrapper_still_gets_guidance():
    command = (
        "python scripts/runtime/codex_impl_guard.py --prompt 'implement one slice'; "
        "codex-yuna exec 'continue without guard'"
    )

    guidance = terminal_tool._foreground_background_guidance(command)

    assert guidance is not None
    assert "background=true" in guidance
    assert "notify_on_complete=true" in guidance


def test_codex_review_guard_rejects_missing_required_flags():
    command = "codex-yuna exec review --uncommitted 'review current changes'"

    error = terminal_tool._codex_review_launch_error(command)

    assert error is not None
    assert "--json" in error
    assert "--output-schema" in error
    assert "--output-last-message" in error
    assert "Missing required flag(s): --json, --output-schema <FILE>, --output-last-message <FILE>." in error


def test_codex_review_required_flags_must_be_in_same_command_segment():
    commands = (
        "codex-yuna exec review --uncommitted; echo --json --output-schema /tmp/schema --output-last-message /tmp/final",
        "codex-yuna exec review --uncommitted && echo --json --output-schema /tmp/schema --output-last-message /tmp/final",
        "codex-yuna exec review --uncommitted | echo --json --output-schema /tmp/schema --output-last-message /tmp/final",
    )

    for command in commands:
        error = terminal_tool._codex_review_launch_error(command)

        assert error is not None
        assert "--json" in error
        assert "--output-schema" in error
        assert "--output-last-message" in error


def test_codex_review_rejects_short_o_as_last_message_alias():
    command = (
        "codex-yuna exec review --uncommitted --json "
        "--output-schema /tmp/schema.json -o /tmp/final.json 'review current changes'"
    )

    error = terminal_tool._codex_review_launch_error(command)

    assert error is not None
    assert "--output-last-message" in error


def test_codex_review_output_flags_require_file_values():
    commands = (
        "codex-yuna exec review --json --output-schema --output-last-message /tmp/final 'review'",
        "codex-yuna exec review --json --output-schema /tmp/schema --output-last-message --color never 'review'",
        "codex-yuna exec review --json --output-schema=- --output-last-message=/tmp/final 'review'",
    )

    for command in commands:
        error = terminal_tool._codex_review_launch_error(command)

        assert error is not None
        assert "--output-schema" in error or "--output-last-message" in error


def test_shell_wrapped_codex_review_is_inspected():
    command = "bash -lc 'codex-yuna exec review --uncommitted --json --output-schema /tmp/schema review current changes'"

    error = terminal_tool._codex_review_launch_error(command)

    assert error is not None
    assert "--output-last-message" in error


def test_codex_read_only_review_prompt_guard_rejects_missing_required_flags():
    command = "codex-yuna exec --sandbox read-only 'Review current uncommitted changes only'"

    error = terminal_tool._codex_review_launch_error(command)

    assert error is not None
    assert "Codex review" in error
    assert "--color never" in error


def test_env_wrapped_codex_review_is_inspected():
    command = "env -i codex-yuna exec review --uncommitted 'review current changes'"

    error = terminal_tool._codex_review_launch_error(command)

    assert error is not None
    assert "--json" in error
    assert "--output-schema" in error
    assert "--output-last-message" in error


def test_env_wrapped_foreground_codex_exec_gets_background_guidance():
    command = "env --ignore-environment codex-yuna exec 'implement the change'"

    guidance = terminal_tool._foreground_background_guidance(command)

    assert guidance is not None
    assert "background=true" in guidance
    assert "notify_on_complete=true" in guidance


def test_shell_wrapped_foreground_codex_exec_gets_background_guidance():
    command = "bash -lc 'codex-yuna exec implement the change'"

    guidance = terminal_tool._foreground_background_guidance(command)

    assert guidance is not None
    assert "background=true" in guidance
    assert "notify_on_complete=true" in guidance


def test_env_shell_wrapped_codex_review_is_inspected():
    command = "env -i bash -lc 'codex-yuna exec review --uncommitted review current changes'"

    error = terminal_tool._codex_review_launch_error(command)

    assert error is not None
    assert "--json" in error
    assert "--output-schema" in error
    assert "--output-last-message" in error


def test_codex_review_subcommand_after_many_options_is_inspected():
    command = (
        "codex-yuna exec --foo a --bar b --baz c --qux d "
        "review --uncommitted 'review current changes'"
    )

    error = terminal_tool._codex_review_launch_error(command)

    assert error is not None
    assert "--json" in error
    assert "--output-schema" in error
    assert "--output-last-message" in error


def test_absolute_shell_wrapped_codex_review_is_inspected():
    command = "/bin/bash -lc 'codex-yuna exec review --uncommitted review current changes'"

    error = terminal_tool._codex_review_launch_error(command)

    assert error is not None
    assert "--json" in error
    assert "--output-schema" in error
    assert "--output-last-message" in error


def test_absolute_shell_wrapped_foreground_codex_exec_gets_background_guidance():
    command = "/bin/bash -lc 'codex-yuna exec implement the change'"

    guidance = terminal_tool._foreground_background_guidance(command)

    assert guidance is not None
    assert "background=true" in guidance
    assert "notify_on_complete=true" in guidance


def test_env_assignment_shell_wrapped_codex_review_is_inspected():
    command = "env FOO=1 bash -lc 'codex-yuna exec review --uncommitted review current changes'"

    error = terminal_tool._codex_review_launch_error(command)

    assert error is not None
    assert "--json" in error
    assert "--output-schema" in error
    assert "--output-last-message" in error


def test_env_unset_shell_wrapped_foreground_codex_exec_gets_background_guidance():
    command = "env -u FOO bash -lc 'codex-yuna exec implement the change'"

    guidance = terminal_tool._foreground_background_guidance(command)

    assert guidance is not None
    assert "background=true" in guidance
    assert "notify_on_complete=true" in guidance


def test_pure_codex_exec_help_does_not_get_background_guidance():
    assert terminal_tool._foreground_background_guidance("codex-yuna exec --help") is None
    assert terminal_tool._foreground_background_guidance("codex exec --version") is None


def test_mixed_help_command_does_not_bypass_foreground_codex_guidance():
    command = "codex-yuna exec --help; codex-yuna exec 'implement the change'"

    guidance = terminal_tool._foreground_background_guidance(command)

    assert guidance is not None
    assert "background=true" in guidance
    assert "notify_on_complete=true" in guidance


def test_echo_help_command_does_not_bypass_foreground_codex_guidance():
    command = "echo --help && codex-yuna exec 'implement the change'"

    guidance = terminal_tool._foreground_background_guidance(command)

    assert guidance is not None
    assert "background=true" in guidance
    assert "notify_on_complete=true" in guidance


def test_deep_shell_wrapped_codex_review_is_inspected():
    command = "bash -lc \"bash -lc \\\"bash -lc 'codex-yuna exec review --uncommitted review current changes'\\\"\""

    error = terminal_tool._codex_review_launch_error(command)

    assert error is not None
    assert "--json" in error
    assert "--output-schema" in error
    assert "--output-last-message" in error


def test_deep_shell_wrapped_foreground_codex_exec_gets_background_guidance():
    command = "bash -lc \"bash -lc \\\"bash -lc 'codex-yuna exec implement the change'\\\"\""

    guidance = terminal_tool._foreground_background_guidance(command)

    assert guidance is not None
    assert "background=true" in guidance
    assert "notify_on_complete=true" in guidance


def test_codex_global_options_before_exec_review_are_inspected():
    command = "codex-yuna --config foo exec review --uncommitted review current changes"

    error = terminal_tool._codex_review_launch_error(command)

    assert error is not None
    assert "--json" in error
    assert "--output-schema" in error
    assert "--output-last-message" in error


def test_codex_global_options_before_exec_get_foreground_guidance():
    command = "codex-yuna --config foo exec 'implement the change'"

    guidance = terminal_tool._foreground_background_guidance(command)

    assert guidance is not None
    assert "background=true" in guidance
    assert "notify_on_complete=true" in guidance


def test_read_only_review_prompt_still_requires_color_never_when_structured():
    command = (
        "codex-yuna exec --sandbox read-only --json "
        "--output-schema /tmp/schema.json --output-last-message /tmp/final.json "
        "review current changes"
    )

    error = terminal_tool._codex_review_launch_error(command)

    assert error is not None
    assert "--color never" in error


def test_prefixed_codex_review_is_inspected():
    commands = (
        "sudo codex-yuna exec review --uncommitted review current changes",
        "command codex-yuna exec review --uncommitted review current changes",
        "timeout 60 codex-yuna exec review --uncommitted review current changes",
    )

    for command in commands:
        error = terminal_tool._codex_review_launch_error(command)
        assert error is not None
        assert "--json" in error
        assert "--output-schema" in error
        assert "--output-last-message" in error


def test_prefixed_foreground_codex_exec_gets_background_guidance():
    commands = (
        "sudo codex-yuna exec implement the change",
        "command codex-yuna exec implement the change",
        "timeout 60 codex-yuna exec implement the change",
    )

    for command in commands:
        guidance = terminal_tool._foreground_background_guidance(command)
        assert guidance is not None
        assert "background=true" in guidance
        assert "notify_on_complete=true" in guidance


def test_prefixed_shell_wrapped_codex_review_is_inspected():
    commands = (
        "sudo bash -lc 'codex-yuna exec review --uncommitted review current changes'",
        "timeout 60 bash -lc 'codex-yuna exec review --uncommitted review current changes'",
    )

    for command in commands:
        error = terminal_tool._codex_review_launch_error(command)
        assert error is not None
        assert "--json" in error
        assert "--output-schema" in error
        assert "--output-last-message" in error


def test_prefixed_shell_wrapped_foreground_codex_exec_gets_background_guidance():
    commands = (
        "sudo bash -lc 'codex-yuna exec implement the change'",
        "timeout 60 bash -lc 'codex-yuna exec implement the change'",
    )

    for command in commands:
        guidance = terminal_tool._foreground_background_guidance(command)
        assert guidance is not None
        assert "background=true" in guidance
        assert "notify_on_complete=true" in guidance


def test_quoted_codex_review_prompt_is_inspected():
    commands = (
        "codex-yuna exec 'review current changes'",
        'codex-yuna exec "please review the diff"',
    )

    for command in commands:
        error = terminal_tool._codex_review_launch_error(command)
        assert error is not None
        assert "--json" in error
        assert "--output-schema" in error
        assert "--output-last-message" in error
        assert "--color never" in error


def test_option_prefixed_codex_invocations_are_inspected():
    review_commands = (
        "sudo -E codex-yuna exec review --uncommitted review current changes",
        "sudo -n codex-yuna exec review --uncommitted review current changes",
        "timeout --foreground 60 codex-yuna exec review --uncommitted review current changes",
        "timeout -k 5s 60s codex-yuna exec review --uncommitted review current changes",
        "nice -n 10 codex-yuna exec review --uncommitted review current changes",
    )
    for command in review_commands:
        error = terminal_tool._codex_review_launch_error(command)
        assert error is not None
        assert "--json" in error

    foreground_commands = (
        "sudo -E codex-yuna exec implement the change",
        "timeout --foreground 60 codex-yuna exec implement the change",
        "nice -n 10 codex-yuna exec implement the change",
    )
    for command in foreground_commands:
        guidance = terminal_tool._foreground_background_guidance(command)
        assert guidance is not None
        assert "background=true" in guidance


def test_shell_metasyntax_codex_invocations_are_inspected():
    review_commands = (
        "(codex-yuna exec review --uncommitted review current changes)",
        "echo $(codex-yuna exec review --uncommitted review current changes)",
        "echo `codex-yuna exec review --uncommitted review current changes`",
    )
    for command in review_commands:
        error = terminal_tool._codex_review_launch_error(command)
        assert error is not None
        assert "--json" in error

    foreground_commands = (
        "(codex-yuna exec implement the change)",
        "echo $(codex-yuna exec implement the change)",
        "echo `codex-yuna exec implement the change`",
    )
    for command in foreground_commands:
        guidance = terminal_tool._foreground_background_guidance(command)
        assert guidance is not None
        assert "background=true" in guidance


def test_quoted_codex_text_is_not_treated_as_command():
    assert terminal_tool._codex_review_launch_error("echo 'codex-yuna exec review'") is None


def test_codex_review_guard_error_points_to_wrapper_entrypoint():
    command = "codex-yuna exec review --uncommitted 'review current changes'"

    error = terminal_tool._codex_review_launch_error(command)

    assert error is not None
    assert "scripts/runtime/codex_review_guard.py" in error
