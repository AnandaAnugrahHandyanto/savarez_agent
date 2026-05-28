from hermes_cli.commands import resolve_command


def test_reload_permissions_command_is_gateway_only():
    command = resolve_command("reload-permissions")

    assert command is not None
    assert command.name == "reload-permissions"
    assert command.gateway_only is True
    assert command.cli_only is False


def test_reload_permissions_underscore_alias_resolves():
    command = resolve_command("reload_permissions")

    assert command is not None
    assert command.name == "reload-permissions"
