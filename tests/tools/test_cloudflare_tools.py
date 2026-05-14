"""Tests for the Cloudflare tools module (KV / R2 / D1 / Vectorize / AI Search / Email)."""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _fake_cf_creds(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf-test-token")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct-test")


# ---------------------------------------------------------------------------
# Module registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_tools_register_into_cloudflare_toolset(self):
        import tools.cloudflare_tools  # noqa: F401 (import triggers registration)
        from tools.registry import registry

        names = set(registry.get_tool_names_for_toolset("cloudflare"))
        # Spot-check: every product surface must have at least one tool.
        assert "cloudflare_workers_ai_chat" in names
        assert "cloudflare_workers_ai_embed" in names
        assert "cloudflare_image_generate" in names
        assert "cloudflare_kv_put" in names
        assert "cloudflare_r2_list" in names
        assert "cloudflare_d1_query" in names
        assert "cloudflare_vectorize_query" in names
        assert "cloudflare_ai_search" in names
        assert "cloudflare_browser_screenshot" in names
        assert "cloudflare_email_send" in names


# ---------------------------------------------------------------------------
# Credential gating
# ---------------------------------------------------------------------------


class TestCredentials:
    def test_missing_token_returns_error(self, monkeypatch):
        monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
        from tools.cloudflare_tools import _kv_get

        result = json.loads(_kv_get("ns", "key"))
        assert result["ok"] is False
        assert "CLOUDFLARE_API_TOKEN" in result["error"]

    def test_missing_account_returns_error(self, monkeypatch):
        monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
        from tools.cloudflare_tools import _workers_ai_chat

        result = json.loads(
            _workers_ai_chat(
                "@cf/meta/llama-4-scout-17b-16e-instruct",
                [{"role": "user", "content": "hi"}],
            )
        )
        assert result["ok"] is False
        assert "CLOUDFLARE_ACCOUNT_ID" in result["error"]


# ---------------------------------------------------------------------------
# Workers AI — image
# ---------------------------------------------------------------------------


class TestWorkersAiImage:
    def test_json_image_path(self):
        from tools import cloudflare_tools

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.json.return_value = {"result": {"image": "Zg=="}}

        with patch.object(cloudflare_tools.requests, "post", return_value=mock_resp):
            with patch(
                "agent.image_gen_provider.save_b64_image", return_value="/tmp/img.png"
            ):
                out = json.loads(cloudflare_tools._workers_ai_image("a dog"))

        assert out["ok"] is True
        assert out["data"]["format"] == "file"
        assert out["data"]["image"] == "/tmp/img.png"

    def test_binary_image_path(self):
        from tools import cloudflare_tools

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "image/png"}
        mock_resp.content = b"\x89PNG\r\n\x1a\nbinary"

        with patch.object(cloudflare_tools.requests, "post", return_value=mock_resp):
            with patch(
                "agent.image_gen_provider.save_b64_image", return_value="/tmp/img.png"
            ) as save:
                out = json.loads(cloudflare_tools._workers_ai_image("a dog"))

        assert out["ok"] is True
        # The raw PNG must have been base64-encoded before passing to save_b64_image.
        saved_b64 = save.call_args.args[0]
        assert base64.b64decode(saved_b64) == b"\x89PNG\r\n\x1a\nbinary"

    def test_empty_prompt_rejected(self):
        from tools.cloudflare_tools import _workers_ai_image

        result = json.loads(_workers_ai_image(""))
        assert result["ok"] is False
        assert "prompt" in result["error"]


# ---------------------------------------------------------------------------
# AI Search — new /ai-search/instances/{name}/{chat/completions,search} API
# ---------------------------------------------------------------------------


class TestAiSearch:
    def test_uses_new_endpoint_for_chat(self):
        from tools import cloudflare_tools

        captured: dict = {}

        def fake_request(method, path, **kwargs):
            captured["method"] = method
            captured["path"] = path
            captured["body"] = kwargs.get("json_body")
            return {"ok": True, "result": {"choices": []}}

        with patch.object(cloudflare_tools, "_cf_request", side_effect=fake_request):
            out = json.loads(
                cloudflare_tools._ai_search_query("my-instance", "What is X?")
            )

        assert out["ok"] is True
        assert captured["method"] == "POST"
        assert captured["path"].endswith(
            "/ai-search/instances/my-instance/chat/completions"
        )
        # Body uses OpenAI-style messages array (new API), not the legacy {query}.
        assert captured["body"]["messages"] == [
            {"role": "user", "content": "What is X?"}
        ]
        assert "query" not in captured["body"]

    def test_uses_search_endpoint_when_answer_false(self):
        from tools import cloudflare_tools

        captured: dict = {}

        def fake_request(method, path, **kwargs):
            captured["path"] = path
            return {"ok": True, "result": []}

        with patch.object(cloudflare_tools, "_cf_request", side_effect=fake_request):
            cloudflare_tools._ai_search_query("inst", "q", answer=False)

        assert captured["path"].endswith("/ai-search/instances/inst/search")

    def test_passthrough_messages_for_multi_turn(self):
        from tools import cloudflare_tools

        captured: dict = {}

        def fake_request(method, path, **kwargs):
            captured["body"] = kwargs.get("json_body")
            return {"ok": True, "result": {}}

        with patch.object(cloudflare_tools, "_cf_request", side_effect=fake_request):
            cloudflare_tools._ai_search_query(
                "inst",
                query=None,
                messages=[
                    {"role": "system", "content": "Be helpful."},
                    {"role": "user", "content": "Hi"},
                ],
            )

        assert captured["body"]["messages"][0]["role"] == "system"

    def test_requires_query_or_messages(self):
        from tools.cloudflare_tools import _ai_search_query

        out = json.loads(_ai_search_query("inst", query=None, messages=None))
        assert out["ok"] is False


# ---------------------------------------------------------------------------
# Email — new /email/sending/send endpoint, flat payload
# ---------------------------------------------------------------------------


class TestEmail:
    def test_email_uses_sending_endpoint_and_flat_payload(self, monkeypatch):
        from tools import cloudflare_tools

        monkeypatch.setenv("CLOUDFLARE_EMAIL_FROM", "noreply@example.com")
        captured: dict = {}

        def fake_request(method, path, **kwargs):
            captured["method"] = method
            captured["path"] = path
            captured["body"] = kwargs.get("json_body")
            return {"ok": True, "result": {"delivered": ["a@example.com"]}}

        with patch.object(cloudflare_tools, "_cf_request", side_effect=fake_request):
            out = json.loads(
                cloudflare_tools._email_send(
                    to="a@example.com",
                    subject="hi",
                    text="hello",
                )
            )

        assert out["ok"] is True
        assert captured["method"] == "POST"
        assert captured["path"].endswith("/email/sending/send")
        # Flat shape — Cloudflare Email Sending uses top-level keys, not
        # OpenAI-style content arrays.
        body = captured["body"]
        assert body["from"] == "noreply@example.com"
        assert body["to"] == "a@example.com"
        assert body["subject"] == "hi"
        assert body["text"] == "hello"
        assert "content" not in body

    def test_email_coerces_list_with_single_recipient(self, monkeypatch):
        from tools import cloudflare_tools

        monkeypatch.setenv("CLOUDFLARE_EMAIL_FROM", "noreply@example.com")
        captured: dict = {}

        def fake_request(method, path, **kwargs):
            captured["body"] = kwargs.get("json_body")
            return {"ok": True, "result": {}}

        with patch.object(cloudflare_tools, "_cf_request", side_effect=fake_request):
            cloudflare_tools._email_send(
                to=["one@example.com"],
                subject="hi",
                text="hello",
            )

        assert captured["body"]["to"] == "one@example.com"

    def test_email_requires_sender(self, monkeypatch):
        monkeypatch.delenv("CLOUDFLARE_EMAIL_FROM", raising=False)
        from tools.cloudflare_tools import _email_send

        out = json.loads(_email_send(to="a@example.com", subject="hi", text="hello"))
        assert out["ok"] is False
        assert "from_address" in out["error"]


# ---------------------------------------------------------------------------
# Vectorize — argument validation + text auto-embedding
# ---------------------------------------------------------------------------


class TestVectorize:
    def test_requires_vector_or_text(self):
        from tools.cloudflare_tools import _vectorize_query

        out = json.loads(_vectorize_query("my-index"))
        assert out["ok"] is False

    def test_auto_embeds_text_then_queries(self):
        from tools import cloudflare_tools

        # First call: embed returns a fake vector.
        # Second call: vectorize query against that vector.
        embed_data = json.dumps(
            {"ok": True, "data": {"model": "@cf/baai/bge-m3", "vectors": [[0.1, 0.2]]}}
        )
        captured: list = []

        def fake_request(method, path, **kwargs):
            captured.append((path, kwargs.get("json_body")))
            return {"ok": True, "result": {"matches": []}}

        with patch.object(cloudflare_tools, "_workers_ai_embed", return_value=embed_data):
            with patch.object(cloudflare_tools, "_cf_request", side_effect=fake_request):
                cloudflare_tools._vectorize_query("my-index", text="hello")

        assert captured, "expected vectorize query to be issued after embed"
        path, body = captured[0]
        assert path.endswith("/vectorize/v2/indexes/my-index/query")
        assert body["vector"] == [0.1, 0.2]
        assert body["topK"] == 5


# ---------------------------------------------------------------------------
# Workers AI — chat routes through gateway when configured
# ---------------------------------------------------------------------------


class TestWorkersAiChat:
    def test_gateway_route_when_env_set(self, monkeypatch):
        monkeypatch.setenv("CLOUDFLARE_GATEWAY_ID", "my-gw")
        from tools import cloudflare_tools

        captured: dict = {}

        def fake_post(url, **kwargs):
            captured["url"] = url
            mock = MagicMock()
            mock.ok = True
            mock.status_code = 200
            mock.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
            return mock

        with patch.object(cloudflare_tools.requests, "post", side_effect=fake_post):
            out = json.loads(
                cloudflare_tools._workers_ai_chat(
                    "@cf/meta/llama-4-scout-17b-16e-instruct",
                    [{"role": "user", "content": "hi"}],
                )
            )

        assert out["ok"] is True
        assert "gateway.ai.cloudflare.com" in captured["url"]
        assert "my-gw/workers-ai/v1/chat/completions" in captured["url"]

    def test_direct_route_without_gateway(self, monkeypatch):
        monkeypatch.delenv("CLOUDFLARE_GATEWAY_ID", raising=False)
        from tools import cloudflare_tools

        captured: dict = {}

        def fake_post(url, **kwargs):
            captured["url"] = url
            mock = MagicMock()
            mock.ok = True
            mock.status_code = 200
            mock.json.return_value = {"choices": []}
            return mock

        with patch.object(cloudflare_tools.requests, "post", side_effect=fake_post):
            cloudflare_tools._workers_ai_chat(
                "@cf/meta/llama-4-scout-17b-16e-instruct",
                [{"role": "user", "content": "hi"}],
            )

        assert "gateway.ai.cloudflare.com" not in captured["url"]
        assert "/ai/v1/chat/completions" in captured["url"]


# ---------------------------------------------------------------------------
# KV
# ---------------------------------------------------------------------------


class TestKv:
    def test_kv_get_404_returns_found_false(self):
        from tools import cloudflare_tools

        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch.object(cloudflare_tools.requests, "get", return_value=mock_resp):
            out = json.loads(cloudflare_tools._kv_get("ns", "missing"))

        assert out["ok"] is True
        assert out["data"]["found"] is False
        assert out["data"]["value"] is None

    def test_kv_get_returns_text(self):
        from tools import cloudflare_tools

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.text = "hello"

        with patch.object(cloudflare_tools.requests, "get", return_value=mock_resp):
            out = json.loads(cloudflare_tools._kv_get("ns", "k"))

        assert out["ok"] is True
        assert out["data"]["value"] == "hello"

    def test_kv_namespace_falls_back_to_env(self, monkeypatch):
        monkeypatch.setenv("CLOUDFLARE_KV_NAMESPACE_ID", "ns-from-env")
        from tools import cloudflare_tools

        assert cloudflare_tools._kv_namespace(None) == "ns-from-env"
