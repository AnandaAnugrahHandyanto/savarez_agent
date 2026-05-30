import sys

import pytest

from hermes_cli.toolset_validation import (
    InvalidToolsetError,
    normalize_toolsets,
    validate_explicit_toolsets,
    validate_explicit_toolsets_or_raise,
)


def test_omitted_means_caller_loads_defaults():
    assert validate_explicit_toolsets(None) == (None, None)
    assert validate_explicit_toolsets("") == (None, None)


def test_all_alias_means_caller_loads_defaults():
    assert validate_explicit_toolsets("all") == (None, None)


def test_single_valid_toolset_is_accepted():
    # A real toolset must produce no error, so the CLI guard never trips on it.
    assert validate_explicit_toolsets("web", source="hermes") == (["web"], None)


def test_partial_keeps_valid_subset_and_warns():
    warnings = []
    valid, err = validate_explicit_toolsets("web,definitely_not_a_toolset", source="test", warn=warnings.append)
    assert err is None
    assert valid == ["web"]
    assert any("definitely_not_a_toolset" in w for w in warnings)


def test_all_unknown_is_an_error():
    valid, err = validate_explicit_toolsets("ui", source="hermes")
    assert valid is None
    assert "ui" in err


def test_or_raise_raises_on_all_unknown():
    with pytest.raises(InvalidToolsetError, match="ui"):
        validate_explicit_toolsets_or_raise("ui", source="hermes")


def test_or_raise_returns_subset_on_partial():
    assert validate_explicit_toolsets_or_raise("web,bogus", source="t", warn=lambda _: None) == ["web"]


def test_or_raise_never_exits_the_process(monkeypatch):
    # The hard constraint: SystemExit (BaseException) would escape daemon
    # `except Exception` boundaries and kill a worker task. Shared code raises.
    monkeypatch.setattr(sys, "exit", lambda *a: pytest.fail("sys.exit called"))
    with pytest.raises(InvalidToolsetError):
        validate_explicit_toolsets_or_raise("ui")


def test_all_plus_extras_warns_they_are_ignored():
    warnings = []
    valid, err = validate_explicit_toolsets("all,web", source="t", warn=warnings.append)
    assert (valid, err) == (None, None)
    assert any("web" in w for w in warnings)


def test_enabled_mcp_server_resolves_disabled_one_warns(monkeypatch):
    import hermes_cli.config

    monkeypatch.setattr(
        hermes_cli.config,
        "read_raw_config",
        lambda: {"mcp_servers": {"live_mcp": {"enabled": True}, "off_mcp": {"enabled": False}}},
    )
    warnings = []
    valid, err = validate_explicit_toolsets("web,live_mcp,off_mcp", source="t", warn=warnings.append)
    assert err is None
    assert valid == ["web", "live_mcp"]
    assert any("off_mcp" in w and "enabled: true" in w for w in warnings)


def test_unreadable_config_degrades_to_all_unknown(monkeypatch):
    # A crash reading MCP config must not propagate — names just stay unknown.
    import hermes_cli.config

    def boom():
        raise RuntimeError("config exploded")

    monkeypatch.setattr(hermes_cli.config, "read_raw_config", boom)
    valid, err = validate_explicit_toolsets("not_a_real_mcp", source="t")
    assert valid is None
    assert "not_a_real_mcp" in err


def test_normalize_splits_and_strips():
    assert normalize_toolsets(" web , search ") == ["web", "search"]
    assert normalize_toolsets(["web", "search"]) == ["web", "search"]
    assert normalize_toolsets(None) is None
