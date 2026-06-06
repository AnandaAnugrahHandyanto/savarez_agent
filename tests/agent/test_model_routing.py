from __future__ import annotations

import os
import sys
import unittest
from contextlib import contextmanager
from types import ModuleType
from unittest.mock import Mock, patch

from agent.model_routing import resolve_model_route


PRIMARY_RUNTIME = {
    "api_key": "primary-key",
    "base_url": "https://primary.example/v1",
    "provider": "primary",
    "api_mode": "chat_completions",
    "command": None,
    "args": [],
    "credential_pool": None,
    "max_tokens": 1200,
}


@contextmanager
def fake_hermes_modules(
    *,
    has_hook: bool = False,
    hook_results: list | None = None,
    discover_side_effect: Exception | None = None,
    runtime_result: dict | None = None,
):
    plugins = ModuleType("hermes_cli.plugins")
    plugins.discover_plugins = Mock(side_effect=discover_side_effect)
    plugins.has_hook = Mock(return_value=has_hook)
    plugins.invoke_hook = Mock(return_value=hook_results or [])

    runtime_provider = ModuleType("hermes_cli.runtime_provider")
    runtime_provider.resolve_runtime_provider = Mock(return_value=runtime_result or {})

    with patch.dict(
        sys.modules,
        {
            "hermes_cli.plugins": plugins,
            "hermes_cli.runtime_provider": runtime_provider,
        },
    ):
        yield plugins, runtime_provider


class ModelRoutingTests(unittest.TestCase):
    def test_no_hook_returns_primary_route(self):
        with fake_hermes_modules(has_hook=False):
            route = resolve_model_route(
                user_message="hello",
                config={},
                primary_model="primary/model",
                primary_runtime=PRIMARY_RUNTIME,
                platform="cli",
            )

        self.assertEqual(route["model"], "primary/model")
        self.assertEqual(route["runtime"], PRIMARY_RUNTIME)
        self.assertIsNot(route["runtime"], PRIMARY_RUNTIME)
        self.assertEqual(route["signature"][0], "primary/model")
        self.assertEqual(route["signature"][6], 1200)
        self.assertNotIn("reasoning_config", route)

    def test_hook_result_resolves_provider_runtime_and_reasoning(self):
        resolved_runtime = {
            "api_key": "routed-key",
            "base_url": "https://router.example/v1",
            "provider": "openrouter",
            "api_mode": "chat_completions",
            "command": None,
            "args": [],
            "credential_pool": None,
            "max_output_tokens": 6000,
        }
        hook_result = {
            "model": "anthropic/claude-sonnet-4.6",
            "provider": "openrouter",
            "base_url": "https://router.example/v1",
            "api_key_env": "ROUTED_API_KEY",
            "reasoning_config": {"enabled": True, "effort": "high"},
            "max_tokens": 8000,
            "metadata": {"reason": "hard task"},
        }

        with (
            patch.dict(os.environ, {"ROUTED_API_KEY": "routed-key"}),
            fake_hermes_modules(
                has_hook=True,
                hook_results=[hook_result],
                runtime_result=resolved_runtime,
            ) as (_, runtime_provider),
        ):
            route = resolve_model_route(
                user_message="debug this flaky distributed test",
                config={"plugins": {"enabled": ["router"]}},
                primary_model="primary/model",
                primary_runtime=PRIMARY_RUNTIME,
                platform="gateway",
                session_id="session-1",
                reasoning_config={"enabled": True, "effort": "low"},
            )

        runtime_provider.resolve_runtime_provider.assert_called_once_with(
            requested="openrouter",
            explicit_api_key="routed-key",
            explicit_base_url="https://router.example/v1",
            target_model="anthropic/claude-sonnet-4.6",
        )
        self.assertEqual(route["model"], "anthropic/claude-sonnet-4.6")
        self.assertEqual(route["runtime"]["provider"], "openrouter")
        self.assertEqual(route["runtime"]["max_tokens"], 8000)
        self.assertEqual(
            route["reasoning_config"],
            {"enabled": True, "effort": "high"},
        )
        self.assertEqual(route["model_route"], {"reason": "hard task"})
        self.assertEqual(route["signature"][6], 8000)

    def test_invalid_hook_results_are_skipped(self):
        with fake_hermes_modules(
            has_hook=True,
            hook_results=[
                "not a route",
                {"model": ""},
                {
                    "model": "routed/model",
                    "runtime": {
                        "provider": "custom",
                        "base_url": "https://custom.example/v1",
                        "api_mode": "chat_completions",
                        "args": ["--fast"],
                        "max_tokens": 4096,
                    },
                },
            ],
        ):
            route = resolve_model_route(
                user_message="write tests",
                config={},
                primary_model="primary/model",
                primary_runtime=PRIMARY_RUNTIME,
                platform="tui",
            )

        self.assertEqual(route["model"], "routed/model")
        self.assertEqual(route["runtime"]["provider"], "custom")
        self.assertEqual(route["runtime"]["args"], ["--fast"])
        self.assertEqual(route["signature"][5], ("--fast",))
        self.assertEqual(route["signature"][6], 4096)

    def test_runtime_provider_max_output_tokens_maps_to_max_tokens(self):
        with fake_hermes_modules(
            has_hook=True,
            hook_results=[
                {
                    "model": "custom/model",
                    "provider": "custom:local",
                },
            ],
            runtime_result={
                "provider": "custom",
                "base_url": "http://localhost:1234/v1",
                "api_mode": "chat_completions",
                "api_key": "no-key-required",
                "max_output_tokens": 2048,
            },
        ):
            route = resolve_model_route(
                user_message="summarize",
                config={},
                primary_model="primary/model",
                primary_runtime={**PRIMARY_RUNTIME, "max_tokens": None},
                platform="cli",
            )

        self.assertEqual(route["runtime"]["max_tokens"], 2048)
        self.assertEqual(route["signature"][6], 2048)

    def test_hook_failure_falls_back_to_primary_route(self):
        with (
            fake_hermes_modules(
                discover_side_effect=RuntimeError("plugin registry unavailable"),
            ),
            patch("agent.model_routing.logger.warning"),
        ):
            route = resolve_model_route(
                user_message="hello",
                config={},
                primary_model="primary/model",
                primary_runtime=PRIMARY_RUNTIME,
                platform="cli",
                reasoning_config={"enabled": False},
            )

        self.assertEqual(route["model"], "primary/model")
        self.assertEqual(route["runtime"]["provider"], "primary")
        self.assertEqual(route["reasoning_config"], {"enabled": False})


if __name__ == "__main__":
    unittest.main()
