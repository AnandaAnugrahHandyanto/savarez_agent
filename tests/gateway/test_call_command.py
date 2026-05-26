from hermes_cli.commands import GATEWAY_KNOWN_COMMANDS, SUBCOMMANDS, gateway_help_lines, resolve_command


def test_call_command_is_gateway_visible():
    cmd = resolve_command("call")

    assert cmd is not None
    assert cmd.name == "call"
    assert "call" in GATEWAY_KNOWN_COMMANDS
    assert "/call" in "\n".join(gateway_help_lines())


def test_call_command_has_expected_subcommands():
    assert SUBCOMMANDS["/call"] == ["browser", "native", "status", "end"]
