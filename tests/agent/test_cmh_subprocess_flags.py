from agent.cmh_subprocess.flags import (
    CLAUDE_REQUIRED_FLAGS,
    validate_flags,
    extract_long_flags,
)

CLAUDE_HELP = """
Usage: claude [options] [prompt]
  -p, --print                                       Print response and exit
  --max-budget-usd <amount>                         Maximum dollar amount to spend on API calls
  --output-format <format>                          Output format
  --no-session-persistence                          Disable session persistence
  --plugin-dir <path>                               Load a plugin
  --model <model>                                   Model for the current session
  --permission-mode <mode>                          Permission mode
  --tools <tools...>                                Specify the list of available tools
  --bare                                            Minimal mode
"""


def test_extract_long_flags_finds_claude_print_flags():
    flags = extract_long_flags(CLAUDE_HELP)

    assert "--print" in flags
    assert "--max-budget-usd" in flags
    assert "--output-format" in flags
    assert "--no-session-persistence" in flags


def test_validate_flags_accepts_current_claude_required_flags():
    result = validate_flags("claude", CLAUDE_HELP, required_flags=CLAUDE_REQUIRED_FLAGS)

    assert result.ok is True
    assert result.missing_required_flags == []
    assert result.available_flags["--max-budget-usd"] is True


def test_validate_flags_rejects_draft_max_cost_flag_when_help_lacks_it():
    result = validate_flags("claude", CLAUDE_HELP, required_flags=("--max-cost-usd",))

    assert result.ok is False
    assert result.missing_required_flags == ["--max-cost-usd"]
    assert result.available_flags["--max-cost-usd"] is False
