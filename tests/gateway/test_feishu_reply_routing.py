import asyncio
import os
from types import SimpleNamespace
from unittest.mock import patch


class TestFeishuReplyRouting:
    @patch.dict(os.environ, {}, clear=True)
    def test_send_with_thread_metadata_only_uses_create_not_reply(self):
        from gateway.config import PlatformConfig
        from gateway.platforms.feishu import FeishuAdapter

        adapter = FeishuAdapter(PlatformConfig())
        captured = {"reply_calls": 0, "create_calls": 0}

        class _MessageAPI:
            def reply(self, request):
                captured["reply_calls"] += 1
                raise AssertionError("reply() should not be used without reply_to")

            def create(self, request):
                captured["create_calls"] += 1
                captured["request"] = request
                return SimpleNamespace(
                    success=lambda: True,
                    data=SimpleNamespace(message_id="om_create"),
                )

        adapter._client = SimpleNamespace(
            im=SimpleNamespace(
                v1=SimpleNamespace(
                    message=_MessageAPI(),
                )
            )
        )

        async def _direct(func, *args, **kwargs):
            return func(*args, **kwargs)

        with patch("gateway.platforms.feishu.asyncio.to_thread", side_effect=_direct):
            result = asyncio.run(
                adapter.send(
                    chat_id="oc_chat",
                    content="hello",
                    metadata={"thread_id": "omt-thread"},
                )
            )

        assert result.success
        assert result.message_id == "om_create"
        assert captured["reply_calls"] == 0
        assert captured["create_calls"] == 1
