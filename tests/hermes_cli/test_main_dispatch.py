from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from hermes_cli import main as main_module


def test_dispatch_parsed_command_exits_with_integer_return(monkeypatch):
    exits = []
    parser = Mock()
    args = SimpleNamespace(func=lambda _args: 7)
    monkeypatch.setattr(main_module.sys, "exit", lambda code: exits.append(code))

    main_module._dispatch_parsed_command(args, parser)

    assert exits == [7]
    parser.print_help.assert_not_called()


def test_dispatch_parsed_command_allows_none_return(monkeypatch):
    exits = []
    parser = Mock()
    args = SimpleNamespace(func=lambda _args: None)
    monkeypatch.setattr(main_module.sys, "exit", lambda code: exits.append(code))

    main_module._dispatch_parsed_command(args, parser)

    assert exits == []
    parser.print_help.assert_not_called()


def test_dispatch_parsed_command_prints_help_without_func(monkeypatch):
    exits = []
    parser = Mock()
    args = SimpleNamespace()
    monkeypatch.setattr(main_module.sys, "exit", lambda code: exits.append(code))

    main_module._dispatch_parsed_command(args, parser)

    assert exits == []
    parser.print_help.assert_called_once_with()
