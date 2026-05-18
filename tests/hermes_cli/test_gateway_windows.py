"""Tests for Windows gateway service wrapper generation."""

import hermes_cli.gateway_windows as gateway_windows


class TestWindowsGatewayTerminalEnv:
    def test_gateway_cmd_forces_configured_local_backend_and_clears_docker_env(self):
        content = gateway_windows._build_gateway_cmd_script(
            r"C:\Hermes\venv\Scripts\pythonw.exe",
            r"C:\Hermes\hermes-agent",
            r"C:\Users\Vineel\AppData\Local\hermes",
            "",
            terminal_env_overlay={
                "TERMINAL_ENV": "local",
                "TERMINAL_DOCKER_IMAGE": "",
                "TERMINAL_DOCKER_MOUNT_CWD_TO_WORKSPACE": "",
                "TERMINAL_DOCKER_VOLUMES": "",
                "TERMINAL_DOCKER_ENV": "",
            },
        )

        assert 'set "TERMINAL_ENV=local"' in content
        assert 'set "TERMINAL_DOCKER_IMAGE="' in content
        assert 'set "TERMINAL_DOCKER_MOUNT_CWD_TO_WORKSPACE="' in content
        assert 'set "TERMINAL_DOCKER_VOLUMES="' in content
        assert 'set "TERMINAL_DOCKER_ENV="' in content
        assert content.index('set "TERMINAL_ENV=local"') < content.index("pythonw.exe")

    def test_terminal_env_overlay_clears_docker_settings_when_backend_is_not_docker(self):
        overlay = gateway_windows._gateway_terminal_env_overlay(
            {
                "terminal": {
                    "backend": "local",
                    "docker_image": "nikolaik/python-nodejs:python3.11-nodejs20",
                    "docker_mount_cwd_to_workspace": False,
                    "docker_volumes": [],
                    "docker_env": {},
                }
            }
        )

        assert overlay["TERMINAL_ENV"] == "local"
        assert overlay["TERMINAL_DOCKER_IMAGE"] == ""
        assert overlay["TERMINAL_DOCKER_MOUNT_CWD_TO_WORKSPACE"] == ""
        assert overlay["TERMINAL_DOCKER_VOLUMES"] == ""
        assert overlay["TERMINAL_DOCKER_ENV"] == ""
