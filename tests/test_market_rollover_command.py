from pathlib import Path

from hermes_cli.commands import resolve_command


def test_market_rollover_slash_command_registered_with_alias():
    cmd = resolve_command("market-rollover")
    alias = resolve_command("market_rollover")

    assert cmd is not None
    assert cmd.name == "market-rollover"
    assert alias is not None
    assert alias.name == "market-rollover"
    assert "handoff" in cmd.description.lower()


def test_market_rollover_dispatch_and_handler_are_wired_in_cli_source():
    source = Path("cli.py").read_text(encoding="utf-8")

    assert 'elif canonical == "market-rollover":' in source
    assert 'self._manual_market_rollover(cmd_original)' in source
    assert 'def _manual_market_rollover(self, cmd_original: str = ""):' in source
    assert 'force_market_rollover=True' in source
