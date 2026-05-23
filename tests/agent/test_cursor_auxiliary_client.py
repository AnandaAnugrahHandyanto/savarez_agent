"""Auxiliary routing for the Cursor SDK provider."""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class CursorAuxiliaryClientTests(unittest.TestCase):
    def test_resolve_provider_client_cursor_returns_sdk_shim(self):
        """Cursor must not fall through to OpenAI HTTP with base_url cursor://sdk."""
        from agent.auxiliary_client import resolve_provider_client
        from agent.cursor_auxiliary_client import CursorAuxiliaryClient

        with patch.dict(os.environ, {"CURSOR_API_KEY": "cursor_test_key"}, clear=False):
            client, model = resolve_provider_client("cursor", model="composer-2.5")
        self.assertIsNotNone(client)
        self.assertIsInstance(client, CursorAuxiliaryClient)
        self.assertEqual(model, "composer-2.5")
        self.assertEqual(str(client.base_url), "cursor://sdk")

    def test_resolve_provider_client_cursor_without_key_returns_none(self):
        from agent.auxiliary_client import resolve_provider_client

        with patch(
            "agent.cursor_auxiliary_client.build_cursor_auxiliary_client",
            return_value=(None, None),
        ):
            client, model = resolve_provider_client("cursor", model="composer-2.5")
        self.assertIsNone(client)
        self.assertIsNone(model)

    def test_cursor_completions_adapter_maps_prompt_result(self):
        from agent.cursor_auxiliary_client import CursorAuxiliaryClient

        run_result = SimpleNamespace(
            status="finished", result='{"title": "T", "body": "B"}'
        )
        with patch.dict(os.environ, {"CURSOR_API_KEY": "cursor_test_key"}, clear=False), patch(
            "cursor_sdk.Agent.prompt",
            return_value=run_result,
        ) as prompt_mock, patch(
            "agent.cursor_auxiliary_client.get_cursor_sdk_client",
            return_value=MagicMock(),
        ):
            client = CursorAuxiliaryClient(model="composer-2.5")
            resp = client.chat.completions.create(
                model="composer-2.5",
                messages=[
                    {"role": "system", "content": "sys"},
                    {"role": "user", "content": "user"},
                ],
                timeout=30,
            )

        self.assertEqual(
            resp.choices[0].message.content, '{"title": "T", "body": "B"}'
        )
        prompt_mock.assert_called_once()
        prompt_text = prompt_mock.call_args[0][0]
        self.assertIn("sys", prompt_text)
        self.assertIn("user", prompt_text)

    def test_messages_to_prompt_flattens_roles(self):
        from agent.cursor_auxiliary_client import _messages_to_prompt

        text = _messages_to_prompt(
            [
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "Hello"},
            ]
        )
        self.assertIn("Be concise.", text)
        self.assertIn("Hello", text)


if __name__ == "__main__":
    unittest.main()
