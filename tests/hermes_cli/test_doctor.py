"""Tests for hermes_cli.doctor."""

import os
import sys
import types
import json
from argparse import Namespace
from types import SimpleNamespace

import pytest

import hermes_cli.doctor as doctor
import hermes_cli.gateway as gateway_cli
from hermes_cli import doctor as doctor_mod
from hermes_cli.doctor import _has_provider_env_config


class TestProviderEnvDetection:
    def test_detects_openai_api_key(self):
        content = "OPENAI_BASE_URL=http://localhost:1234/v1\nOPENAI_API_KEY=***"
        assert _has_provider_env_config(content)

    def test_detects_custom_endpoint_without_openrouter_key(self):
        content = "OPENAI_BASE_URL=http://localhost:8080/v1\n"
        assert _has_provider_env_config(content)

    def test_returns_false_when_no_provider_settings(self):
        content = "TERMINAL_ENV=local\n"
        assert not _has_provider_env_config(content)


class TestDoctorToolAvailabilityOverrides:
    def test_marks_honcho_available_when_configured(self, monkeypatch):
        monkeypatch.setattr(doctor, "_honcho_is_configured_for_doctor", lambda: True)

        available, unavailable = doctor._apply_doctor_tool_availability_overrides(
            [],
            [{"name": "honcho", "env_vars": [], "tools": ["query_user_context"]}],
        )

        assert available == ["honcho"]
        assert unavailable == []

    def test_leaves_honcho_unavailable_when_not_configured(self, monkeypatch):
        monkeypatch.setattr(doctor, "_honcho_is_configured_for_doctor", lambda: False)

        honcho_entry = {"name": "honcho", "env_vars": [], "tools": ["query_user_context"]}
        available, unavailable = doctor._apply_doctor_tool_availability_overrides(
            [],
            [honcho_entry],
        )

        assert available == []
        assert unavailable == [honcho_entry]


class TestHonchoDoctorConfigDetection:
    def test_reports_configured_when_enabled_with_api_key(self, monkeypatch):
        fake_config = SimpleNamespace(enabled=True, api_key="***")

        monkeypatch.setattr(
            "honcho_integration.client.HonchoClientConfig.from_global_config",
            lambda: fake_config,
        )

        assert doctor._honcho_is_configured_for_doctor()

    def test_reports_not_configured_without_api_key(self, monkeypatch):
        fake_config = SimpleNamespace(enabled=True, api_key="")

        monkeypatch.setattr(
            "honcho_integration.client.HonchoClientConfig.from_global_config",
            lambda: fake_config,
        )

        assert not doctor._honcho_is_configured_for_doctor()


def test_run_doctor_sets_interactive_env_for_tool_checks(monkeypatch, tmp_path):
    """Doctor should present CLI-gated tools as available in CLI context."""
    project_root = tmp_path / "project"
    hermes_home = tmp_path / ".hermes"
    project_root.mkdir()
    hermes_home.mkdir()

    monkeypatch.setattr(doctor_mod, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(doctor_mod, "HERMES_HOME", hermes_home)
    monkeypatch.delenv("HERMES_INTERACTIVE", raising=False)

    seen = {}

    def fake_check_tool_availability(*args, **kwargs):
        seen["interactive"] = os.getenv("HERMES_INTERACTIVE")
        raise SystemExit(0)

    fake_model_tools = types.SimpleNamespace(
        check_tool_availability=fake_check_tool_availability,
        TOOLSET_REQUIREMENTS={},
    )
    monkeypatch.setitem(sys.modules, "model_tools", fake_model_tools)

    with pytest.raises(SystemExit):
        doctor_mod.run_doctor(Namespace(fix=False))

    assert seen["interactive"] == "1"


def test_check_gateway_service_linger_warns_when_disabled(monkeypatch, tmp_path, capsys):
    unit_path = tmp_path / "hermes-gateway.service"
    unit_path.write_text("[Unit]\n")

    monkeypatch.setattr(gateway_cli, "is_linux", lambda: True)
    monkeypatch.setattr(gateway_cli, "get_systemd_unit_path", lambda: unit_path)
    monkeypatch.setattr(gateway_cli, "get_systemd_linger_status", lambda: (False, ""))

    issues = []
    doctor._check_gateway_service_linger(issues)

    out = capsys.readouterr().out
    assert "Gateway Service" in out
    assert "Systemd linger disabled" in out
    assert "loginctl enable-linger" in out
    assert issues == [
        "Enable linger for the gateway user service: sudo loginctl enable-linger $USER"
    ]


def test_check_gateway_service_linger_skips_when_service_not_installed(monkeypatch, tmp_path, capsys):
    unit_path = tmp_path / "missing.service"

    monkeypatch.setattr(gateway_cli, "is_linux", lambda: True)
    monkeypatch.setattr(gateway_cli, "get_systemd_unit_path", lambda: unit_path)

    issues = []
    doctor._check_gateway_service_linger(issues)

    out = capsys.readouterr().out
    assert out == ""
    assert issues == []


def test_run_doctor_json_emits_machine_readable_payload(monkeypatch, tmp_path, capsys):
    project_root = tmp_path / "project"
    hermes_home = tmp_path / ".hermes"
    project_root.mkdir()
    hermes_home.mkdir()
    (hermes_home / ".env").write_text("OPENAI_API_KEY=sk-test-1234567890\n")
    (hermes_home / "config.yaml").write_text("model: openai/gpt-5\n")

    monkeypatch.setattr(doctor_mod, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(doctor_mod, "HERMES_HOME", hermes_home)
    monkeypatch.setattr(doctor_mod, "_DHH", "~/.hermes")
    monkeypatch.setattr(doctor_mod.shutil, "which", lambda cmd: None)
    monkeypatch.setattr(
        doctor_mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr=""),
    )

    fake_model_tools = types.SimpleNamespace(
        check_tool_availability=lambda: ([], []),
        TOOLSET_REQUIREMENTS={},
    )
    monkeypatch.setitem(sys.modules, "model_tools", fake_model_tools)

    doctor_mod.run_doctor(Namespace(fix=False, json=True))

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == 1
    assert "sections" in payload
    assert "bootstrap" in payload
    assert payload["bootstrap"]["issue_count"] == payload["summary"]["remaining_issues_count"]


def test_run_doctor_reports_missing_test_dependencies(monkeypatch, tmp_path, capsys):
    project_root = tmp_path / "project"
    hermes_home = tmp_path / ".hermes"
    project_root.mkdir()
    hermes_home.mkdir()
    (hermes_home / ".env").write_text("OPENAI_API_KEY=sk-test-1234567890\n")
    (hermes_home / "config.yaml").write_text("model: openai/gpt-5\n")

    monkeypatch.setattr(doctor_mod, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(doctor_mod, "HERMES_HOME", hermes_home)
    monkeypatch.setattr(doctor_mod, "_DHH", "~/.hermes")
    monkeypatch.setattr(
        doctor_mod,
        "find_missing_test_modules",
        lambda: {
            "prompt_toolkit": "required by CLI command/help imports used in tests",
            "pytest_asyncio": "required for @pytest.mark.asyncio gateway tests",
        },
    )
    monkeypatch.setattr(doctor_mod.shutil, "which", lambda cmd: None)
    monkeypatch.setattr(
        doctor_mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr=""),
    )

    fake_model_tools = types.SimpleNamespace(
        check_tool_availability=lambda: ([], []),
        TOOLSET_REQUIREMENTS={},
    )
    monkeypatch.setitem(sys.modules, "model_tools", fake_model_tools)

    doctor_mod.run_doctor(Namespace(fix=False))

    output = capsys.readouterr().out
    assert "Test Environment" in output
    assert "prompt_toolkit" in output
    assert "pytest_asyncio" in output
    assert 'Install the dev environment: uv pip install -e ".[all,dev]"' in output


def test_run_doctor_json_includes_test_environment_section(monkeypatch, tmp_path, capsys):
    project_root = tmp_path / "project"
    hermes_home = tmp_path / ".hermes"
    project_root.mkdir()
    hermes_home.mkdir()
    (hermes_home / ".env").write_text("OPENAI_API_KEY=sk-test-1234567890\n")
    (hermes_home / "config.yaml").write_text("model: openai/gpt-5\n")

    monkeypatch.setattr(doctor_mod, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(doctor_mod, "HERMES_HOME", hermes_home)
    monkeypatch.setattr(doctor_mod, "_DHH", "~/.hermes")
    monkeypatch.setattr(
        doctor_mod,
        "find_missing_test_modules",
        lambda: {"xdist": "required because pytest defaults to '-n auto' in pyproject.toml"},
    )
    monkeypatch.setattr(doctor_mod.shutil, "which", lambda cmd: None)
    monkeypatch.setattr(
        doctor_mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr=""),
    )

    fake_model_tools = types.SimpleNamespace(
        check_tool_availability=lambda: ([], []),
        TOOLSET_REQUIREMENTS={},
    )
    monkeypatch.setitem(sys.modules, "model_tools", fake_model_tools)

    doctor_mod.run_doctor(Namespace(fix=False, json=True))

    payload = json.loads(capsys.readouterr().out)
    test_section = next(section for section in payload["sections"] if section["name"] == "Test Environment")
    assert any(check["text"] == "xdist" and check["level"] == "warn" for check in test_section["checks"])
    assert any(
        check["text"] == 'Install the dev environment: uv pip install -e ".[all,dev]"'
        and check["level"] == "info"
        for check in test_section["checks"]
    )
    assert 'Install test dependencies: uv pip install -e ".[all,dev]"' in payload["issues"]
