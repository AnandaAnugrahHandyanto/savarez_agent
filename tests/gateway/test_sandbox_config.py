"""Tests for gateway/sandbox_config.py."""

import os
from unittest import mock

import pytest

from gateway.sandbox_config import (
    apply_gateway_backend_to_env,
    get_gateway_sandbox_lifetime,
    get_gateway_terminal_backend,
    should_warn_insecure_gateway,
)


class TestGetGatewayTerminalBackend:

    def test_returns_none_when_not_set(self):
        assert get_gateway_terminal_backend({}) is None

    def test_returns_none_when_gateway_section_empty(self):
        assert get_gateway_terminal_backend({"gateway": {}}) is None

    def test_returns_backend_when_set(self):
        config = {"gateway": {"terminal_backend": "docker"}}
        assert get_gateway_terminal_backend(config) == "docker"

    def test_returns_none_when_explicitly_none(self):
        config = {"gateway": {"terminal_backend": None}}
        assert get_gateway_terminal_backend(config) is None


class TestGetGatewaySandboxLifetime:

    def test_default_3600(self):
        assert get_gateway_sandbox_lifetime({}) == 3600

    def test_custom_value(self):
        config = {"gateway": {"sandbox_lifetime": 7200}}
        assert get_gateway_sandbox_lifetime(config) == 7200


class TestShouldWarnInsecureGateway:

    def test_warns_when_local_and_no_override(self):
        config = {"terminal": {"backend": "local"}}
        assert should_warn_insecure_gateway(config) is True

    def test_warns_when_no_terminal_section(self):
        # Default backend is "local"
        assert should_warn_insecure_gateway({}) is True

    def test_no_warn_when_gateway_override_set(self):
        config = {
            "terminal": {"backend": "local"},
            "gateway": {"terminal_backend": "docker"},
        }
        assert should_warn_insecure_gateway(config) is False

    def test_no_warn_when_terminal_backend_is_docker(self):
        config = {"terminal": {"backend": "docker"}}
        assert should_warn_insecure_gateway(config) is False

    def test_no_warn_when_terminal_backend_is_ssh(self):
        config = {"terminal": {"backend": "ssh"}}
        assert should_warn_insecure_gateway(config) is False


class TestApplyGatewayBackendToEnv:

    def test_sets_terminal_env_when_configured(self):
        config = {"gateway": {"terminal_backend": "docker"}}
        with mock.patch.dict(os.environ, {}, clear=True):
            apply_gateway_backend_to_env(config)
            assert os.environ["TERMINAL_ENV"] == "docker"

    def test_sets_docker_image_from_gateway_config(self):
        config = {
            "gateway": {
                "terminal_backend": "docker",
                "sandbox_image": "custom:latest",
            },
        }
        with mock.patch.dict(os.environ, {}, clear=True):
            apply_gateway_backend_to_env(config)
            assert os.environ["TERMINAL_DOCKER_IMAGE"] == "custom:latest"

    def test_falls_back_to_terminal_docker_image(self):
        config = {
            "terminal": {"docker_image": "nikolaik/python-nodejs:latest"},
            "gateway": {"terminal_backend": "docker"},
        }
        with mock.patch.dict(os.environ, {}, clear=True):
            apply_gateway_backend_to_env(config)
            assert os.environ["TERMINAL_DOCKER_IMAGE"] == "nikolaik/python-nodejs:latest"

    def test_default_image_when_nothing_configured(self):
        config = {"gateway": {"terminal_backend": "docker"}}
        with mock.patch.dict(os.environ, {}, clear=True):
            apply_gateway_backend_to_env(config)
            assert os.environ["TERMINAL_DOCKER_IMAGE"] == "nikolaik/python-nodejs:python3.11-nodejs20"

    def test_does_nothing_when_no_gateway_backend(self):
        config = {}
        with mock.patch.dict(os.environ, {}, clear=True):
            apply_gateway_backend_to_env(config)
            assert "TERMINAL_ENV" not in os.environ

    def test_does_not_override_existing_docker_image(self):
        config = {"gateway": {"terminal_backend": "docker"}}
        with mock.patch.dict(os.environ, {"TERMINAL_DOCKER_IMAGE": "existing:img"}, clear=True):
            apply_gateway_backend_to_env(config)
            # setdefault should preserve existing value
            assert os.environ["TERMINAL_DOCKER_IMAGE"] == "existing:img"

    def test_apply_rejects_invalid_backend(self):
        config = {"gateway": {"terminal_backend": "invalid"}}
        with mock.patch.dict(os.environ, {}, clear=True):
            apply_gateway_backend_to_env(config)
            assert "TERMINAL_ENV" not in os.environ
