"""Tests for DingTalk delivery in tools/send_message_tool.py.

Covers the OrgGroupSend OpenAPI path (proactive send to any group by
openConversationId) and the static custom-robot webhook fallback. Kept in a
separate module from test_send_message_tool.py so it does not inherit that
file's `pytest.importorskip("telegram")` skip — none of these tests need
python-telegram-bot.
"""

import asyncio
import json
from types import SimpleNamespace

from tools.send_message_tool import (
    _is_dingtalk_group_conversation,
    _parse_target_ref,
    _send_dingtalk,
)


# ---------------------------------------------------------------------------
# _parse_target_ref / _is_dingtalk_group_conversation
# ---------------------------------------------------------------------------


class TestParseTargetRefDingtalk:
    """A DingTalk openConversationId is recognized as an explicit target."""

    def test_group_conversation_id_is_explicit(self):
        chat_id, thread_id, is_explicit = _parse_target_ref(
            "dingtalk", "cidM1xck538oLOh0Qod1YUVlA=="
        )
        assert chat_id == "cidM1xck538oLOh0Qod1YUVlA=="
        assert thread_id is None
        assert is_explicit is True

    def test_conversation_id_with_plus_and_single_pad(self):
        chat_id, _thread_id, is_explicit = _parse_target_ref(
            "dingtalk", "cidFk62nfRicihGYoueJdbv+nmUCsZhYgc6MURB1F4gIeg="
        )
        assert chat_id == "cidFk62nfRicihGYoueJdbv+nmUCsZhYgc6MURB1F4gIeg="
        assert is_explicit is True

    def test_whitespace_is_stripped(self):
        chat_id, _thread_id, is_explicit = _parse_target_ref(
            "dingtalk", "  cidunHQNUauVrulszxrY5naeA==  "
        )
        assert chat_id == "cidunHQNUauVrulszxrY5naeA=="
        assert is_explicit is True

    def test_non_conversation_name_is_not_explicit(self):
        # A human-friendly name must still flow through directory resolution.
        chat_id, _thread_id, is_explicit = _parse_target_ref("dingtalk", "SEO group")
        assert is_explicit is False
        assert chat_id is None

    def test_webhook_url_is_not_a_conversation_id(self):
        assert not _is_dingtalk_group_conversation(
            "https://oapi.dingtalk.com/robot/send?access_token=abc"
        )

    def test_is_group_conversation_helper(self):
        assert _is_dingtalk_group_conversation("cidM1xck538oLOh0Qod1YUVlA==")
        assert not _is_dingtalk_group_conversation("")
        assert not _is_dingtalk_group_conversation(None)
        assert not _is_dingtalk_group_conversation("12345")


# ---------------------------------------------------------------------------
# httpx stand-in
# ---------------------------------------------------------------------------


class _FakeHttp:
    """Async-context-manager stand-in for httpx.AsyncClient.

    Returns a response per `post` call, matched by URL substring against
    `responses` (a dict of {url_substring: payload}). Captures every call's
    url / payload / headers for assertions.
    """

    def __init__(self, responses, status_code=200):
        self.responses = responses
        self.status_code = status_code
        self.calls = []

    def __call__(self, *_a, **_kw):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False

    async def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "payload": json, "headers": headers})
        payload = None
        for key, value in self.responses.items():
            if key in url:
                payload = value
                break
        if payload is None:
            raise AssertionError(f"Unexpected POST to {url}")
        body = json_dumps(payload)
        return SimpleNamespace(
            status_code=self.status_code,
            content=body.encode("utf-8"),
            text=body,
            raise_for_status=lambda: None,
            json=lambda data=payload: data,
        )


def json_dumps(obj):
    return json.dumps(obj)


def _install_http(monkeypatch, fake):
    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", fake)


# ---------------------------------------------------------------------------
# _send_dingtalk — OpenAPI group send
# ---------------------------------------------------------------------------


class TestSendDingtalkOpenAPI:
    def test_group_cid_with_credentials_uses_openapi(self, monkeypatch):
        fake = _FakeHttp(
            {
                "oauth2/accessToken": {"accessToken": "tok-123"},
                "robot/groupMessages/send": {"processQueryKey": "pqk-456"},
            }
        )
        _install_http(monkeypatch, fake)

        extra = {"client_id": "appkey", "client_secret": "appsecret"}
        result = asyncio.run(
            _send_dingtalk(extra, "cidM1xck538oLOh0Qod1YUVlA==", "hello group")
        )

        assert result["success"] is True
        assert result["chat_id"] == "cidM1xck538oLOh0Qod1YUVlA=="
        assert result["message_id"] == "pqk-456"

        # Two calls: token fetch, then group send.
        assert len(fake.calls) == 2
        token_call, send_call = fake.calls
        assert "oauth2/accessToken" in token_call["url"]
        assert token_call["payload"] == {"appKey": "appkey", "appSecret": "appsecret"}

        assert "robot/groupMessages/send" in send_call["url"]
        assert send_call["headers"]["x-acs-dingtalk-access-token"] == "tok-123"
        body = send_call["payload"]
        assert body["robotCode"] == "appkey"  # defaults to client_id
        assert body["openConversationId"] == "cidM1xck538oLOh0Qod1YUVlA=="
        assert body["msgKey"] == "sampleText"
        assert json.loads(body["msgParam"]) == {"content": "hello group"}

    def test_explicit_robot_code_is_used(self, monkeypatch):
        fake = _FakeHttp(
            {
                "oauth2/accessToken": {"accessToken": "tok"},
                "robot/groupMessages/send": {"processQueryKey": "k"},
            }
        )
        _install_http(monkeypatch, fake)

        extra = {
            "client_id": "appkey",
            "client_secret": "appsecret",
            "robot_code": "custom-robot",
        }
        asyncio.run(_send_dingtalk(extra, "cidAAAA==", "hi"))
        assert fake.calls[1]["payload"]["robotCode"] == "custom-robot"

    def test_openapi_http_error_is_surfaced(self, monkeypatch):
        fake = _FakeHttp(
            {
                "oauth2/accessToken": {"accessToken": "tok"},
                "robot/groupMessages/send": {"code": "Forbidden", "message": "no perm"},
            },
            status_code=403,
        )
        _install_http(monkeypatch, fake)

        extra = {"client_id": "appkey", "client_secret": "appsecret"}
        result = asyncio.run(_send_dingtalk(extra, "cidAAAA==", "hi"))
        assert "error" in result
        assert "403" in result["error"]
        assert "no perm" in result["error"]

    def test_missing_token_is_reported(self, monkeypatch):
        fake = _FakeHttp({"oauth2/accessToken": {}})  # no accessToken in body
        _install_http(monkeypatch, fake)

        extra = {"client_id": "appkey", "client_secret": "appsecret"}
        result = asyncio.run(_send_dingtalk(extra, "cidAAAA==", "hi"))
        assert "error" in result
        assert "access token" in result["error"].lower()
        # Never attempted the group send.
        assert len(fake.calls) == 1


# ---------------------------------------------------------------------------
# _send_dingtalk — static webhook fallback
# ---------------------------------------------------------------------------


class TestSendDingtalkWebhookFallback:
    def test_no_credentials_falls_back_to_webhook(self, monkeypatch):
        monkeypatch.delenv("DINGTALK_CLIENT_ID", raising=False)
        monkeypatch.delenv("DINGTALK_CLIENT_SECRET", raising=False)
        fake = _FakeHttp({"oapi.dingtalk.com/robot/send": {"errcode": 0}})
        _install_http(monkeypatch, fake)

        extra = {"webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=x"}
        result = asyncio.run(
            _send_dingtalk(extra, "cidM1xck538oLOh0Qod1YUVlA==", "hi")
        )
        assert result["success"] is True
        assert len(fake.calls) == 1
        assert "oapi.dingtalk.com/robot/send" in fake.calls[0]["url"]
        assert fake.calls[0]["payload"] == {
            "msgtype": "text",
            "text": {"content": "hi"},
        }

    def test_non_conversation_target_falls_back_even_with_credentials(self, monkeypatch):
        # A non-cid chat_id with creds present must NOT hit the OpenAPI path.
        fake = _FakeHttp({"oapi.dingtalk.com/robot/send": {"errcode": 0}})
        _install_http(monkeypatch, fake)

        extra = {
            "client_id": "appkey",
            "client_secret": "appsecret",
            "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=x",
        }
        result = asyncio.run(_send_dingtalk(extra, "not-a-cid", "hi"))
        assert result["success"] is True
        assert "oapi.dingtalk.com/robot/send" in fake.calls[0]["url"]

    def test_no_webhook_and_no_credentials_returns_error(self, monkeypatch):
        monkeypatch.delenv("DINGTALK_CLIENT_ID", raising=False)
        monkeypatch.delenv("DINGTALK_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("DINGTALK_WEBHOOK_URL", raising=False)
        result = asyncio.run(_send_dingtalk({}, "cidAAAA==", "hi"))
        assert "error" in result
        assert "DingTalk not configured" in result["error"]
