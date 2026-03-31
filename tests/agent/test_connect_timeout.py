"""
Tests for HERMES_CONNECT_TIMEOUT injection in _create_openai_client.

Verifies that a connection timeout is applied to the underlying httpx
transport so that unreachable hosts fail fast and trigger the fallback
chain rather than hanging indefinitely.
"""

import os
import unittest
from unittest.mock import MagicMock, patch


class TestConnectTimeoutInjection(unittest.TestCase):
    """_create_openai_client should inject an httpx.Client with a connect timeout."""

    def _make_agent(self):
        """Return a minimal AIAgent-like object with _create_openai_client."""
        from run_agent import AIAgent

        agent = AIAgent.__new__(AIAgent)
        agent.provider = "custom"
        agent._log_prefix = "test"
        # Minimal logger stand-in
        import logging
        agent._logger = logging.getLogger("test")
        return agent

    def test_connect_timeout_injected_by_default(self):
        """http_client with connect timeout is injected when not already present."""
        import httpx

        created_clients = []

        def fake_openai(**kwargs):
            created_clients.append(kwargs)
            m = MagicMock()
            return m

        agent = self._make_agent()
        with patch("run_agent.OpenAI", side_effect=fake_openai):
            with patch.dict(os.environ, {"HERMES_CONNECT_TIMEOUT": "10"}):
                agent._create_openai_client(
                    {"base_url": "http://192.0.2.1:8001/v1", "api_key": "none"},
                    reason="test",
                    shared=False,
                )

        self.assertEqual(len(created_clients), 1)
        kwargs = created_clients[0]
        self.assertIn("http_client", kwargs)
        http_client = kwargs["http_client"]
        self.assertIsInstance(http_client, httpx.Client)
        self.assertEqual(http_client.timeout.connect, 10.0)

    def test_connect_timeout_disabled_when_zero(self):
        """Setting HERMES_CONNECT_TIMEOUT=0 disables injection (old behaviour)."""
        created_clients = []

        def fake_openai(**kwargs):
            created_clients.append(kwargs)
            return MagicMock()

        agent = self._make_agent()
        with patch("run_agent.OpenAI", side_effect=fake_openai):
            with patch.dict(os.environ, {"HERMES_CONNECT_TIMEOUT": "0"}):
                agent._create_openai_client(
                    {"base_url": "http://192.0.2.1:8001/v1", "api_key": "none"},
                    reason="test",
                    shared=False,
                )

        kwargs = created_clients[0]
        self.assertNotIn("http_client", kwargs)

    def test_existing_http_client_not_overridden(self):
        """If caller already passes http_client, it is not replaced."""
        import httpx

        custom_client = httpx.Client(timeout=httpx.Timeout(99.0, connect=99.0))
        created_clients = []

        def fake_openai(**kwargs):
            created_clients.append(kwargs)
            return MagicMock()

        agent = self._make_agent()
        with patch("run_agent.OpenAI", side_effect=fake_openai):
            with patch.dict(os.environ, {"HERMES_CONNECT_TIMEOUT": "10"}):
                agent._create_openai_client(
                    {
                        "base_url": "http://192.0.2.1:8001/v1",
                        "api_key": "none",
                        "http_client": custom_client,
                    },
                    reason="test",
                    shared=False,
                )

        kwargs = created_clients[0]
        self.assertIs(kwargs["http_client"], custom_client)
        self.assertEqual(kwargs["http_client"].timeout.connect, 99.0)


if __name__ == "__main__":
    unittest.main()
