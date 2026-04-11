import asyncio
from xml.etree import ElementTree as ET

import pytest

from gateway.config import PlatformConfig
from gateway.platforms.wecom_callback import WecomCallbackAdapter
from gateway.platforms.wecom_crypto import WXBizMsgCrypt


def _app(name="test-app", corp_id="ww1234567890", agent_id="1000002"):
    return {
        "name": name,
        "corp_id": corp_id,
        "corp_secret": "secret",
        "agent_id": agent_id,
        "token": "***",
        "encoding_aes_key": "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG",
    }


def _config(apps=None):
    return PlatformConfig(
        enabled=True,
        extra={"mode": "callback", "host": "127.0.0.1", "port": 0, "apps": apps or [_app()]},
    )


def test_crypto_roundtrip_encrypt_decrypt():
    app = _app()
    crypt = WXBizMsgCrypt(app["token"], app["encoding_aes_key"], app["corp_id"])
    encrypted_xml = crypt.encrypt("<xml><Content>hello</Content></xml>", nonce="nonce123", timestamp="123456")
    root = ET.fromstring(encrypted_xml)
    decrypted = crypt.decrypt(
        root.findtext("MsgSignature", default=""),
        root.findtext("TimeStamp", default=""),
        root.findtext("Nonce", default=""),
        root.findtext("Encrypt", default=""),
    )
    assert b"<Content>hello</Content>" in decrypted


@pytest.mark.asyncio
async def test_send_resolves_pending_reply_future():
    adapter = WecomCallbackAdapter(_config())
    fut = asyncio.get_running_loop().create_future()
    adapter._pending_replies["m1"] = fut
    result = await adapter.send("user1", "hi", reply_to="m1")
    assert result.success is True
    assert result.message_id == "m1"
    assert await fut == "hi"


def test_build_event_uses_source_field_and_message_id():
    adapter = WecomCallbackAdapter(_config())
    xml_text = """
    <xml>
      <ToUserName>ww1234567890</ToUserName>
      <FromUserName>zhangsan</FromUserName>
      <CreateTime>1710000000</CreateTime>
      <MsgType>text</MsgType>
      <Content>你好</Content>
      <MsgId>123456789</MsgId>
    </xml>
    """
    event = adapter._build_event(_app(), xml_text)
    assert event is not None
    assert event.source is not None
    assert event.source.user_id == "zhangsan"
    assert event.source.chat_id == "ww1234567890:zhangsan"
    assert event.message_id == "123456789"
    assert event.text == "你好"


def test_user_app_key_scopes_same_user_across_corps():
    adapter = WecomCallbackAdapter(_config())
    assert adapter._user_app_key("corpA", "alice") == "corpA:alice"
    assert adapter._user_app_key("corpB", "alice") == "corpB:alice"
    assert adapter._user_app_key("corpA", "alice") != adapter._user_app_key("corpB", "alice")


@pytest.mark.asyncio
async def test_send_uses_scoped_chat_id_to_select_correct_app():
    apps = [
        _app(name="corp-a", corp_id="corpA", agent_id="1001"),
        _app(name="corp-b", corp_id="corpB", agent_id="2002"),
    ]
    adapter = WecomCallbackAdapter(_config(apps=apps))
    adapter._user_app_map["corpB:alice"] = "corp-b"
    adapter._access_tokens["corp-b"] = {"token": "tok-b", "expires_at": 9999999999}

    calls = {}

    class FakeResponse:
        def json(self):
            return {"errcode": 0, "msgid": "ok1"}

    class FakeClient:
        async def post(self, url, json):
            calls["url"] = url
            calls["json"] = json
            return FakeResponse()

    adapter._http_client = FakeClient()
    result = await adapter.send("corpB:alice", "hello")

    assert result.success is True
    assert calls["json"]["touser"] == "alice"
    assert calls["json"]["agentid"] == 2002
    assert "tok-b" in calls["url"]


@pytest.mark.asyncio
async def test_send_falls_back_from_bare_user_id_when_unique():
    apps = [
        _app(name="corp-a", corp_id="corpA", agent_id="1001"),
    ]
    adapter = WecomCallbackAdapter(_config(apps=apps))
    adapter._user_app_map["corpA:alice"] = "corp-a"
    adapter._access_tokens["corp-a"] = {"token": "tok-a", "expires_at": 9999999999}

    calls = {}

    class FakeResponse:
        def json(self):
            return {"errcode": 0, "msgid": "ok2"}

    class FakeClient:
        async def post(self, url, json):
            calls["url"] = url
            calls["json"] = json
            return FakeResponse()

    adapter._http_client = FakeClient()
    result = await adapter.send("alice", "hello")

    assert result.success is True
    assert calls["json"]["agentid"] == 1001


@pytest.mark.asyncio
async def test_poll_loop_dispatches_handle_message(monkeypatch):
    adapter = WecomCallbackAdapter(_config())
    calls = []

    async def fake_handle_message(event):
        calls.append(event.text)

    monkeypatch.setattr(adapter, "handle_message", fake_handle_message)
    event = adapter._build_event(
        _app(),
        """
        <xml>
          <ToUserName>ww1234567890</ToUserName>
          <FromUserName>lisi</FromUserName>
          <CreateTime>1710000000</CreateTime>
          <MsgType>text</MsgType>
          <Content>test</Content>
          <MsgId>m2</MsgId>
        </xml>
        """,
    )
    task = asyncio.create_task(adapter._poll_loop())
    await adapter._message_queue.put(event)
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls == ["test"]
