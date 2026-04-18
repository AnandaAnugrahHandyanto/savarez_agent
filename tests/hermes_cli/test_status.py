from types import SimpleNamespace

import hermes_cli.gateway as gateway_cli
from hermes_cli.status import show_status


def test_show_status_includes_tavily_key(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-1...cdef")

    show_status(SimpleNamespace(all=False, deep=False))

    output = capsys.readouterr().out
    assert "Tavily" in output
    assert "tvly...cdef" in output


def test_show_status_surfaces_gateway_repair_hints_for_drifted_outdated_unit(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    unit_path = tmp_path / "hermes-gateway-17b8e69b.service"
    unit_path.write_text("[Unit]\n", encoding="utf-8")

    monkeypatch.setattr(
        gateway_cli,
        "get_gateway_systemd_report",
        lambda: {
            "installed": True,
            "active": True,
            "state": "running",
            "scope": "system",
            "system": True,
            "unit_name": "hermes-gateway-17b8e69b",
            "unit_path": str(unit_path),
            "drifted": True,
        },
    )
    monkeypatch.setattr(gateway_cli, "systemd_unit_path_is_current", lambda path, system=False: False)

    show_status(SimpleNamespace(all=False, deep=False))

    output = capsys.readouterr().out
    assert "Unit:         hermes-gateway-17b8e69b (legacy/non-canonical)" in output
    assert "Drift:        yes" in output
    assert "Preview:      hermes gateway repair --system" in output
    assert "Apply:        sudo hermes gateway repair --system --apply --cleanup-legacy" in output
    assert "Definition:   outdated" in output
    assert "Refresh:      sudo hermes gateway restart --system" in output


def test_show_status_skips_gateway_repair_hints_when_unit_is_canonical_and_current(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    unit_path = tmp_path / "hermes-gateway.service"
    unit_path.write_text("[Unit]\n", encoding="utf-8")

    monkeypatch.setattr(
        gateway_cli,
        "get_gateway_systemd_report",
        lambda: {
            "installed": True,
            "active": True,
            "state": "running",
            "scope": "system",
            "system": True,
            "unit_name": "hermes-gateway",
            "unit_path": str(unit_path),
            "drifted": False,
        },
    )
    monkeypatch.setattr(gateway_cli, "systemd_unit_path_is_current", lambda path, system=False: True)

    show_status(SimpleNamespace(all=False, deep=False))

    output = capsys.readouterr().out
    assert "Unit:         hermes-gateway" in output
    assert "Preview:" not in output
    assert "Apply:" not in output
    assert "Definition:" not in output
    assert "Refresh:" not in output
