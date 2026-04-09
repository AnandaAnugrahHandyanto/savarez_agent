"""Tests for Browser Use session settings resolution."""

import os
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _enable_managed_nous_tools(monkeypatch):
    monkeypatch.setenv("HERMES_ENABLE_NOUS_MANAGED_TOOLS", "1")


class _OkResponse:
    """Fake HTTP 200 response for requests.post."""
    status_code = 200
    ok = True
    text = ""

    def __init__(self, data, headers=None):
        self._data = data
        self.headers = headers or {}

    def json(self):
        return self._data


def _make_env(tmp_path, api_key="test-key", extras=None):
    """Build an environment dict with HERMES_HOME and optional overrides."""
    env = os.environ.copy()
    env["HERMES_HOME"] = str(tmp_path)
    if api_key:
        env["BROWSER_USE_API_KEY"] = api_key
    else:
        env.pop("BROWSER_USE_API_KEY", None)
    if extras:
        env.update(extras)
    return env


def _resolve_settings(fake_tools_package, tmp_path, config_yaml=None, env_extras=None):
    """Write config, load provider, and return resolved session settings."""
    if config_yaml is not None:
        (tmp_path / "config.yaml").write_text(config_yaml, encoding="utf-8")
    env = _make_env(tmp_path, extras=env_extras)
    with patch.dict(os.environ, env, clear=True):
        mod = fake_tools_package(
            "tools.browser_providers.browser_use",
            "browser_providers/browser_use.py",
        )
        return mod.BrowserUseProvider()._resolve_session_settings()


class TestResolveSessionSettings:
    """_resolve_session_settings reads from config.yaml and env vars."""

    def test_from_config_yaml(self, fake_tools_package, tmp_path):
        """Settings in config.yaml browser.browser_use are returned."""
        settings = _resolve_settings(fake_tools_package, tmp_path, config_yaml=(
            "browser:\n"
            "  cloud_provider: browser-use\n"
            "  browser_use:\n"
            '    profile_id: "550e8400-e29b-41d4-a716-446655440000"\n'
            "    proxy_country_code: de\n"
            "    timeout: 10\n"
            "    screen_width: 1920\n"
            "    screen_height: 1080\n"
            "    allow_resizing: true\n"
            "    enable_recording: true\n"
        ))
        assert settings["profileId"] == "550e8400-e29b-41d4-a716-446655440000"
        assert settings["proxyCountryCode"] == "de"
        assert settings["timeout"] == 10
        assert settings["browserScreenWidth"] == 1920
        assert settings["browserScreenHeight"] == 1080
        assert settings["allowResizing"] is True
        assert settings["enableRecording"] is True

    def test_empty_config(self, fake_tools_package, tmp_path):
        """When browser_use section is absent, returns empty dict."""
        settings = _resolve_settings(
            fake_tools_package, tmp_path,
            config_yaml="browser:\n  cloud_provider: browser-use\n",
        )
        assert settings == {}

    def test_no_config_file(self, fake_tools_package, tmp_path):
        """When config.yaml doesn't exist, returns empty dict."""
        settings = _resolve_settings(fake_tools_package, tmp_path)
        assert settings == {}

    def test_no_browser_use_key_in_config(self, fake_tools_package, tmp_path):
        """Works when config.yaml has a browser section but no browser_use key."""
        settings = _resolve_settings(fake_tools_package, tmp_path, config_yaml=(
            "browser:\n"
            "  command_timeout: 30\n"
            "  record_sessions: false\n"
        ))
        assert settings == {}

    def test_from_env_vars(self, fake_tools_package, tmp_path):
        """Environment variables populate session settings."""
        settings = _resolve_settings(
            fake_tools_package, tmp_path,
            config_yaml="browser:\n  cloud_provider: browser-use\n",
            env_extras={
                "BROWSER_USE_PROFILE_ID": "env-profile-uuid",
                "BROWSER_USE_PROXY_COUNTRY_CODE": "gb",
                "BROWSER_USE_TIMEOUT": "15",
                "BROWSER_USE_SCREEN_WIDTH": "1280",
                "BROWSER_USE_SCREEN_HEIGHT": "720",
                "BROWSER_USE_ALLOW_RESIZING": "true",
                "BROWSER_USE_ENABLE_RECORDING": "1",
            },
        )
        assert settings["profileId"] == "env-profile-uuid"
        assert settings["proxyCountryCode"] == "gb"
        assert settings["timeout"] == 15
        assert settings["browserScreenWidth"] == 1280
        assert settings["browserScreenHeight"] == 720
        assert settings["allowResizing"] is True
        assert settings["enableRecording"] is True

    def test_env_overrides_config(self, fake_tools_package, tmp_path):
        """Environment variables take precedence over config.yaml values."""
        settings = _resolve_settings(
            fake_tools_package, tmp_path,
            config_yaml=(
                "browser:\n"
                "  browser_use:\n"
                "    proxy_country_code: de\n"
                "    timeout: 10\n"
            ),
            env_extras={"BROWSER_USE_PROXY_COUNTRY_CODE": "fr"},
        )
        assert settings["proxyCountryCode"] == "fr"
        assert settings["timeout"] == 10

    def test_boolean_false_values(self, fake_tools_package, tmp_path):
        """Falsy string values ('false', '0') are parsed to False and retained."""
        settings = _resolve_settings(
            fake_tools_package, tmp_path,
            config_yaml="",
            env_extras={
                "BROWSER_USE_ALLOW_RESIZING": "false",
                "BROWSER_USE_ENABLE_RECORDING": "0",
            },
        )
        assert settings["allowResizing"] is False
        assert settings["enableRecording"] is False


class TestCreateSessionPayload:
    """Session settings flow through to create_session POST payload."""

    def test_direct_mode_sends_user_settings(self, fake_tools_package, tmp_path):
        """In direct mode, user session settings are sent in the POST payload."""
        (tmp_path / "config.yaml").write_text(
            "browser:\n"
            "  browser_use:\n"
            '    profile_id: "direct-profile-uuid"\n'
            "    proxy_country_code: jp\n"
            "    timeout: 30\n",
            encoding="utf-8",
        )
        env = _make_env(tmp_path, api_key="direct-api-key")
        response = _OkResponse({"id": "session-direct-1", "cdpUrl": "wss://cdp.example/session"})

        with patch.dict(os.environ, env, clear=True):
            mod = fake_tools_package(
                "tools.browser_providers.browser_use",
                "browser_providers/browser_use.py",
            )
            with patch.object(mod.requests, "post", return_value=response) as post:
                mod.BrowserUseProvider().create_session("task-direct-settings")

        payload = post.call_args.kwargs["json"]
        assert payload["profileId"] == "direct-profile-uuid"
        assert payload["proxyCountryCode"] == "jp"
        assert payload["timeout"] == 30

    def test_managed_mode_user_settings_override_defaults(self, fake_tools_package, tmp_path):
        """In managed mode, user settings override the managed defaults."""
        (tmp_path / "config.yaml").write_text(
            "browser:\n"
            "  browser_use:\n"
            "    proxy_country_code: de\n"
            "    timeout: 8\n",
            encoding="utf-8",
        )
        env = _make_env(tmp_path, api_key=None, extras={
            "TOOL_GATEWAY_USER_TOKEN": "nous-token",
            "BROWSER_USE_GATEWAY_URL": "http://127.0.0.1:3009",
        })
        response = _OkResponse(
            {"id": "session-managed-1", "connectUrl": "wss://connect.example/session"},
            headers={"x-external-call-id": "call-managed-1"},
        )

        with patch.dict(os.environ, env, clear=True):
            mod = fake_tools_package(
                "tools.browser_providers.browser_use",
                "browser_providers/browser_use.py",
            )
            with patch.object(mod.requests, "post", return_value=response) as post:
                mod.BrowserUseProvider().create_session("task-managed-override")

        payload = post.call_args.kwargs["json"]
        assert payload["proxyCountryCode"] == "de"
        assert payload["timeout"] == 8

    def test_managed_mode_preserves_defaults_when_no_user_settings(self, fake_tools_package, tmp_path):
        """In managed mode without user settings, managed defaults are preserved."""
        (tmp_path / "config.yaml").write_text(
            "browser:\n  cloud_provider: browser-use\n",
            encoding="utf-8",
        )
        env = _make_env(tmp_path, api_key=None, extras={
            "TOOL_GATEWAY_USER_TOKEN": "nous-token",
            "BROWSER_USE_GATEWAY_URL": "http://127.0.0.1:3009",
        })
        response = _OkResponse(
            {"id": "session-managed-2", "connectUrl": "wss://connect.example/session"},
            headers={"x-external-call-id": "call-managed-2"},
        )

        with patch.dict(os.environ, env, clear=True):
            mod = fake_tools_package(
                "tools.browser_providers.browser_use",
                "browser_providers/browser_use.py",
            )
            with patch.object(mod.requests, "post", return_value=response) as post:
                mod.BrowserUseProvider().create_session("task-managed-defaults")

        payload = post.call_args.kwargs["json"]
        assert payload["timeout"] == 5
        assert payload["proxyCountryCode"] == "us"
