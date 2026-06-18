"""Acceptance tests for WeChat iLink rate-limit behavior changes.

Design contract (red-team verification):
  1. send_typing — rate-limit aware: skips network calls when cooldown is active.
  2. _send_text_chunk — fast-fail on genuine rate limit (ret=-2 + descriptive
     errmsg) by raising RateLimitedError instead of retrying with backoff.
  3. _send_with_retry — recognises rate-limit errors and skips the plain-text
     fallback, returning the failed SendResult directly.
  4. WeixinAdapter._rate_limited_until — new float attribute, initial value 0.0.
  5. RateLimitedError — new exception class inheriting RuntimeError, lives in
     gateway.platforms.weixin.

These tests represent design INTENT.  When a test fails it means the
implementation has not yet satisfied the design contract.
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from gateway.config import PlatformConfig
from gateway.platforms.base import SendResult
from gateway.platforms.weixin import (
    WeixinAdapter,
    RateLimitedError,
    TYPING_START,
)


# ---------------------------------------------------------------------------
# Helpers (mirror style from test_weixin.py)
# ---------------------------------------------------------------------------


def _make_adapter() -> WeixinAdapter:
    """Create a minimal WeixinAdapter with a valid PlatformConfig."""
    return WeixinAdapter(
        PlatformConfig(
            enabled=True,
            token="test-token",
            extra={"account_id": "test-account"},
        )
    )


def _connected_adapter() -> WeixinAdapter:
    """Create a WeixinAdapter that appears connected — session, token, base_url, token_store."""
    adapter = _make_adapter()
    adapter._session = object()
    adapter._send_session = adapter._session
    adapter._token = "test-token"
    adapter._base_url = "https://weixin.example.com"
    adapter._token_store.get = lambda account_id, chat_id: "ctx-token"
    return adapter


# ===================================================================
# Modification 5 — RateLimitedError exception class
# ===================================================================


class TestRateLimitedError:
    """验收 RateLimitedError 异常类定义（修改 5）。"""

    def test_class_exists_and_is_importable(self):
        """RateLimitedError 存在于 gateway.platforms.weixin 模块，可正常导入。"""
        from gateway.platforms import weixin as wx_mod

        assert hasattr(wx_mod, "RateLimitedError")
        assert wx_mod.RateLimitedError is RateLimitedError

    def test_inherits_runtime_error(self):
        """RateLimitedError 继承自 RuntimeError。"""
        assert issubclass(RateLimitedError, RuntimeError)

    def test_can_be_instantiated_with_message(self):
        """RateLimitedError 可接受消息字符串并正确保存。"""
        err = RateLimitedError("[RATE_LIMITED] freq limit hit")
        assert isinstance(err, RuntimeError)
        assert str(err) == "[RATE_LIMITED] freq limit hit"

    def test_can_be_caught_as_runtime_error(self):
        """RateLimitedError 可被 RuntimeError 捕获（向下兼容）。"""
        try:
            raise RateLimitedError("test")
        except RuntimeError as exc:
            assert isinstance(exc, RateLimitedError)
        else:
            raise AssertionError("expected RuntimeError to catch RateLimitedError")


# ===================================================================
# Modification 4 — _rate_limited_until attribute
# ===================================================================


class TestRateLimitedUntilAttribute:
    """验收 _rate_limited_until 属性（修改 4）。"""

    def test_initial_value_is_zero(self):
        """_rate_limited_until 初始值为 0.0，表示当前无限流冷却。"""
        adapter = _make_adapter()
        assert adapter._rate_limited_until == 0.0

    def test_type_is_float(self):
        """_rate_limited_until 类型为 float。"""
        adapter = _make_adapter()
        assert isinstance(adapter._rate_limited_until, float)

    def test_can_be_set_to_future_timestamp(self):
        """_rate_limited_until 可被设置为未来的 Unix 时间戳。"""
        adapter = _make_adapter()
        future = time.time() + 30.0
        adapter._rate_limited_until = future
        assert adapter._rate_limited_until == pytest.approx(future, abs=1.0)

    def test_zero_means_no_cooldown(self):
        """_rate_limited_until == 0 表示无限流冷却。"""
        adapter = _make_adapter()
        adapter._rate_limited_until = 0.0
        assert adapter._rate_limited_until == 0.0
        assert time.time() >= adapter._rate_limited_until


# ===================================================================
# Modification 1 — send_typing rate-limit awareness
# ===================================================================


class TestSendTypingRateLimitAwareness:
    """验收 send_typing 的限流感知行为（修改 1）。

    设计契约：
    - 当 _rate_limited_until > 当前时间时，send_typing() 不发起任何网络请求，直接返回
    - 当 _rate_limited_until 为 0 或已过期时，行为不变（正常发送 typing 指令）
    """

    @patch("gateway.platforms.weixin._send_typing", new_callable=AsyncMock)
    def test_skips_network_call_when_cooldown_active(self, send_typing_mock):
        """冷却期（_rate_limited_until > now）内不调用 _send_typing。"""
        adapter = _connected_adapter()
        adapter._rate_limited_until = time.time() + 30.0
        adapter._typing_cache.get = lambda chat_id: "ticket-abc"

        asyncio.run(adapter.send_typing("wxid_test123"))

        send_typing_mock.assert_not_awaited()

    @patch("gateway.platforms.weixin._send_typing", new_callable=AsyncMock)
    def test_sends_normally_when_no_cooldown(self, send_typing_mock):
        """_rate_limited_until == 0 时正常发送 typing 指令。"""
        adapter = _connected_adapter()
        adapter._rate_limited_until = 0.0
        adapter._typing_cache.get = lambda chat_id: "ticket-abc"

        asyncio.run(adapter.send_typing("wxid_test123"))

        send_typing_mock.assert_awaited_once()
        kwargs = send_typing_mock.await_args.kwargs
        assert kwargs["to_user_id"] == "wxid_test123"
        assert kwargs["typing_ticket"] == "ticket-abc"
        assert kwargs["status"] == TYPING_START

    @patch("gateway.platforms.weixin._send_typing", new_callable=AsyncMock)
    def test_sends_normally_when_cooldown_expired(self, send_typing_mock):
        """冷却期已过期（_rate_limited_until < now）时恢复正常发送。"""
        adapter = _connected_adapter()
        adapter._rate_limited_until = time.time() - 10.0  # 10 秒前过期
        adapter._typing_cache.get = lambda chat_id: "ticket-abc"

        asyncio.run(adapter.send_typing("wxid_test123"))

        send_typing_mock.assert_awaited_once()

    @patch("gateway.platforms.weixin._send_typing", new_callable=AsyncMock)
    def test_skips_when_no_typing_ticket_despite_no_cooldown(self, send_typing_mock):
        """无限流冷却但无 typing_ticket 时静默返回（原有行为，非本次修改）。"""
        adapter = _connected_adapter()
        adapter._rate_limited_until = 0.0
        adapter._typing_cache.get = lambda chat_id: None

        asyncio.run(adapter.send_typing("wxid_test123"))

        send_typing_mock.assert_not_awaited()

    @patch("gateway.platforms.weixin._send_typing", new_callable=AsyncMock)
    def test_skips_when_not_connected_despite_no_cooldown(self, send_typing_mock):
        """无限流冷却但 adapter 未连接时静默返回（原有行为，非本次修改）。"""
        adapter = _make_adapter()
        adapter._rate_limited_until = 0.0

        asyncio.run(adapter.send_typing("wxid_test123"))

        send_typing_mock.assert_not_awaited()


# ===================================================================
# Modification 2 — _send_text_chunk fast-fail on rate limit
# ===================================================================


class TestSendTextChunkRateLimitFastFail:
    """验收 _send_text_chunk 的限流速败行为（修改 2）。

    设计契约：
    - 当 iLink 返回限流（ret=-2 或 errcode=-2 + 描述性 errmsg）时，
      抛出 RateLimitedError 而非重试
    - RateLimitedError 消息以 [RATE_LIMITED] 开头
    - 设置 self._rate_limited_until = time.time() + cooldown_seconds
    - 默认冷却 30s；服务端 retry_after/wait hint 优先
    - stale session（ret=-2 + 空 errmsg）仍按原有逻辑处理（重试免 token）
    """

    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_raises_rate_limited_error_not_retries(self, send_message_mock):
        """限流响应应抛出 RateLimitedError，不进行指数退避重试。"""
        adapter = _connected_adapter()
        adapter._send_chunk_retries = 5  # 即使配置了多次重试
        send_message_mock.return_value = {
            "ret": -2,
            "errcode": -2,
            "errmsg": "freq limit",
        }

        with pytest.raises(RateLimitedError):
            asyncio.run(
                adapter._send_text_chunk(
                    chat_id="wxid_test123",
                    chunk="hello",
                    context_token="ctx-token",
                    client_id="client-1",
                )
            )

        # 只调用一次，无重试
        send_message_mock.assert_awaited_once()

    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_error_message_starts_with_rate_limited_marker(self, send_message_mock):
        """RateLimitedError 消息必须以 [RATE_LIMITED] 开头。"""
        adapter = _connected_adapter()
        adapter._send_chunk_retries = 3
        send_message_mock.return_value = {
            "ret": -2,
            "errcode": -2,
            "errmsg": "too frequently",
        }

        with pytest.raises(RateLimitedError) as exc_info:
            asyncio.run(
                adapter._send_text_chunk(
                    chat_id="wxid_test123",
                    chunk="hello",
                    context_token="ctx-token",
                    client_id="client-1",
                )
            )

        assert str(exc_info.value).startswith("[RATE_LIMITED]")

    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_sets_rate_limited_until_on_rate_limit(self, send_message_mock):
        """_send_text_chunk 在限流时应设置 _rate_limited_until 为未来的时间戳。"""
        adapter = _connected_adapter()
        adapter._send_chunk_retries = 0  # 无重试延迟干扰时间测量
        assert adapter._rate_limited_until == 0.0  # 前置条件
        before = time.time()
        send_message_mock.return_value = {
            "ret": -2,
            "errcode": -2,
            "errmsg": "freq limit",
        }

        try:
            asyncio.run(
                adapter._send_text_chunk(
                    chat_id="wxid_test123",
                    chunk="hello",
                    context_token="ctx-token",
                    client_id="client-1",
                )
            )
        except (RateLimitedError, RuntimeError):
            pass

        after = time.time()
        assert adapter._rate_limited_until >= before
        # 默认 30s 冷却 + cap 上限，不应超过 65s
        assert adapter._rate_limited_until <= after + 65.0

    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_default_cooldown_is_30_seconds(self, send_message_mock):
        """无服务端 hint 时默认冷却 30 秒。

        使用 _send_chunk_retries=0 避免重试延迟干扰时间测量。
        此测试验证冷却值的计算逻辑，不验证重试次数。
        """
        adapter = _connected_adapter()
        adapter._send_chunk_retries = 0  # 只发一次，无重试延迟
        before = time.time()
        send_message_mock.return_value = {
            "ret": -2,
            "errcode": -2,
            "errmsg": "freq limit",
        }

        try:
            asyncio.run(
                adapter._send_text_chunk(
                    chat_id="wxid_test123",
                    chunk="hello",
                    context_token="ctx-token",
                    client_id="client-1",
                )
            )
        except (RateLimitedError, RuntimeError):
            pass

        cooldown = adapter._rate_limited_until - before
        # 默认 30s（允许 ±3s 计时误差）
        assert 27.0 <= cooldown <= 35.0, f"expected ~30s cooldown, got {cooldown:.1f}s"

    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_respects_server_retry_after_hint(self, send_message_mock):
        """服务端返回 retry_after 时，冷却时间取该值（优先于默认 30s）。

        使用 retry_after=12（低于默认 30s 且低于 cap）来验证 hint 确实被使用。
        使用 _send_chunk_retries=0 避免重试延迟干扰时间测量。
        """
        adapter = _connected_adapter()
        adapter._send_chunk_retries = 0
        before = time.time()
        send_message_mock.return_value = {
            "ret": -2,
            "errcode": -2,
            "errmsg": "freq limit",
            "retry_after": 12,
        }

        try:
            asyncio.run(
                adapter._send_text_chunk(
                    chat_id="wxid_test123",
                    chunk="hello",
                    context_token="ctx-token",
                    client_id="client-1",
                )
            )
        except (RateLimitedError, RuntimeError):
            pass

        cooldown = adapter._rate_limited_until - before
        # 应接近 12s 而非默认 30s（允许 ±3s 计时误差）
        assert 9.0 <= cooldown <= 17.0, (
            f"expected ~12s cooldown from retry_after=12 "
            f"(server hint should take precedence over default 30s), got {cooldown:.1f}s"
        )

    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_respects_server_wait_hint(self, send_message_mock):
        """服务端返回 wait 字段（备选字段名）时，冷却时间至少为该值。

        使用 _send_chunk_retries=0 避免重试延迟干扰时间测量。
        """
        adapter = _connected_adapter()
        adapter._send_chunk_retries = 0
        before = time.time()
        send_message_mock.return_value = {
            "ret": -2,
            "errcode": -2,
            "errmsg": "freq limit",
            "wait": 20,
        }

        try:
            asyncio.run(
                adapter._send_text_chunk(
                    chat_id="wxid_test123",
                    chunk="hello",
                    context_token="ctx-token",
                    client_id="client-1",
                )
            )
        except (RateLimitedError, RuntimeError):
            pass

        cooldown = adapter._rate_limited_until - before
        assert cooldown >= 18.0, f"expected >=20s cooldown from wait, got {cooldown:.1f}s"

    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_cooldown_capped_at_backoff_cap(self, send_message_mock):
        """冷却时间不超过 _rate_limit_backoff_cap_seconds 上限。

        使用 _send_chunk_retries=0 避免重试延迟干扰时间测量。
        """
        adapter = _connected_adapter()
        adapter._send_chunk_retries = 0
        adapter._rate_limit_backoff_cap_seconds = 60.0
        before = time.time()
        send_message_mock.return_value = {
            "ret": -2,
            "errcode": -2,
            "errmsg": "freq limit",
            "retry_after": 3600,  # 服务端要求 1 小时，应该被 cap
        }

        try:
            asyncio.run(
                adapter._send_text_chunk(
                    chat_id="wxid_test123",
                    chunk="hello",
                    context_token="ctx-token",
                    client_id="client-1",
                )
            )
        except (RateLimitedError, RuntimeError):
            pass

        cooldown = adapter._rate_limited_until - before
        assert cooldown <= 65.0, f"expected cooldown capped at 60s, got {cooldown:.1f}s"

    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_errcode_minus_2_triggers_rate_limit(self, send_message_mock):
        """errcode=-2（非 ret=-2）也能触发限流速败。"""
        adapter = _connected_adapter()
        adapter._send_chunk_retries = 0
        send_message_mock.return_value = {
            "ret": None,
            "errcode": -2,
            "errmsg": "frequency limit exceeded",
        }

        with pytest.raises((RateLimitedError, RuntimeError)):
            asyncio.run(
                adapter._send_text_chunk(
                    chat_id="wxid_test123",
                    chunk="hello",
                    context_token="ctx-token",
                    client_id="client-1",
                )
            )

    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_stale_session_now_treated_as_rate_limit(self, send_message_mock):
        """改动2：ret=-2 + 空 errmsg 不再误判 stale session，走 rate limit（砍放大器）。

        旧逻辑（_is_stale_session_ret）把空 errmsg 的 ret=-2 当 stale session →
        tokenless retry（放大器，在已限流时多打一次 iLink）。改动2 移除此误判：
        ret=-2（无论 errmsg）统一走 rate limit 分支 → 设 cooldown + raise，不 retry。

        回归防护：真正 token 过期是 errcode=-14（保留 tokenless retry，见 AMP-02）。
        """
        adapter = _connected_adapter()
        adapter._send_chunk_retries = 3
        send_message_mock.return_value = {
            "ret": -2, "errcode": None, "errmsg": None,  # 旧误判源；新：rate limit
        }

        # 改动2：空 errmsg ret=-2 走 rate limit → raise RateLimitedError（不 tokenless retry）
        with pytest.raises(RateLimitedError):
            asyncio.run(
                adapter._send_text_chunk(
                    chat_id="wxid_test123",
                    chunk="hello",
                    context_token="ctx-token",
                    client_id="client-1",
                )
            )
        # 砍放大器：仅 1 次 iLink 调用（不 tokenless retry）
        assert send_message_mock.await_count == 1

    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_rate_limited_error_includes_ret_and_errcode(self, send_message_mock):
        """RateLimitedError 消息应包含 ret 和 errcode 便于排查。"""
        adapter = _connected_adapter()
        adapter._send_chunk_retries = 3
        send_message_mock.return_value = {
            "ret": -2,
            "errcode": -2,
            "errmsg": "freq limit",
        }

        with pytest.raises(RateLimitedError) as exc_info:
            asyncio.run(
                adapter._send_text_chunk(
                    chat_id="wxid_test123",
                    chunk="hello",
                    context_token="ctx-token",
                    client_id="client-1",
                )
            )

        msg = str(exc_info.value)
        assert "ret=-2" in msg or "ret=None" in msg
        assert "errcode=-2" in msg or "errcode=None" in msg


# ===================================================================
# Modification 3 — _send_with_retry rate-limit identification
# ===================================================================


class TestSendWithRetryRateLimitIdentification:
    """验收 _send_with_retry 的限流识别行为（修改 3）。

    设计契约：
    - 当错误消息含 "rate limited" 或 "[RATE_LIMITED]" 时，
      不执行 plain-text fallback，直接返回失败的 SendResult
    - 非限流错误仍执行 plain-text fallback（原有行为不变）
    """

    @patch.object(WeixinAdapter, "send", new_callable=AsyncMock)
    def test_skip_fallback_when_error_has_rate_limited_marker(self, send_mock):
        """错误消息含 [RATE_LIMITED] 时跳过 plain-text fallback。"""
        adapter = _connected_adapter()
        send_mock.return_value = SendResult(
            success=False,
            error="[RATE_LIMITED] iLink sendmessage rate limited: ret=-2 errcode=-2 errmsg=freq limit",
        )

        result = asyncio.run(
            adapter._send_with_retry(chat_id="wxid_test123", content="hello")
        )

        assert result.success is False
        assert "[RATE_LIMITED]" in (result.error or "")
        # 只调用一次 send — 无 fallback
        # 改动3（结论必达有界重试）：限流时 send 重试 HERMES_DELIVERY_MAX_RETRIES 次
        # （默认 3），用尽后 best-effort 投递失败通知 1 次。总调用 1 + 3 + 1 = 5。
        # 仍不执行 plain-text fallback（notice 是失败通知，非 fallback）。
        assert send_mock.await_count == 5

    @patch.object(WeixinAdapter, "send", new_callable=AsyncMock)
    def test_skip_fallback_when_error_contains_rate_limited_text(self, send_mock):
        """错误消息含 'rate limited' 文本（无 [RATE_LIMITED] 前缀）时也跳过 fallback。"""
        adapter = _connected_adapter()
        send_mock.return_value = SendResult(
            success=False,
            error="iLink sendmessage rate limited: ret=-2 errcode=-2 errmsg=freq limit",
        )

        result = asyncio.run(
            adapter._send_with_retry(chat_id="wxid_test123", content="hello")
        )

        assert result.success is False
        # 改动3（结论必达有界重试）：限流时 send 重试 HERMES_DELIVERY_MAX_RETRIES 次
        # （默认 3），用尽后 best-effort 投递失败通知 1 次。总调用 1 + 3 + 1 = 5。
        # 仍不执行 plain-text fallback（notice 是失败通知，非 fallback）。
        assert send_mock.await_count == 5

    @patch.object(WeixinAdapter, "send", new_callable=AsyncMock)
    def test_still_does_fallback_for_ordinary_format_error(self, send_mock):
        """非限流的格式化错误仍执行 plain-text fallback（原有行为不变）。"""
        adapter = _connected_adapter()
        send_mock.side_effect = [
            SendResult(success=False, error="Markdown formatting error"),
            SendResult(success=True, message_id="msg-fb"),
        ]

        asyncio.run(
            adapter._send_with_retry(chat_id="wxid_test123", content="# Title\n\ntext")
        )

        assert send_mock.await_count == 2
        # 第二次调用是 fallback（内容中含 plain text 标识）
        fallback_content = send_mock.await_args_list[1].kwargs["content"]
        assert "plain text" in fallback_content.lower()

    @patch.object(WeixinAdapter, "send", new_callable=AsyncMock)
    def test_rate_limited_marker_case_insensitive(self, send_mock):
        """_send_with_retry 大小写不敏感地匹配 [RATE_LIMITED] 前缀。"""
        adapter = _connected_adapter()
        send_mock.return_value = SendResult(
            success=False,
            error="[rate_limited] iLink sendmessage rate limited",
        )

        result = asyncio.run(
            adapter._send_with_retry(chat_id="wxid_test123", content="hello")
        )

        assert result.success is False
        # 改动3（结论必达有界重试）：限流时 send 重试 HERMES_DELIVERY_MAX_RETRIES 次
        # （默认 3），用尽后 best-effort 投递失败通知 1 次。总调用 1 + 3 + 1 = 5。
        # 仍不执行 plain-text fallback（notice 是失败通知，非 fallback）。
        assert send_mock.await_count == 5

    @patch.object(WeixinAdapter, "send", new_callable=AsyncMock)
    def test_rate_limited_text_case_insensitive(self, send_mock):
        """_send_with_retry 大小写不敏感地匹配 'rate limited' 文本。"""
        adapter = _connected_adapter()
        send_mock.return_value = SendResult(
            success=False,
            error="RATE LIMITED: too many requests",
        )

        result = asyncio.run(
            adapter._send_with_retry(chat_id="wxid_test123", content="hello")
        )

        assert result.success is False
        # 改动3（结论必达有界重试）：限流时 send 重试 HERMES_DELIVERY_MAX_RETRIES 次
        # （默认 3），用尽后 best-effort 投递失败通知 1 次。总调用 1 + 3 + 1 = 5。
        # 仍不执行 plain-text fallback（notice 是失败通知，非 fallback）。
        assert send_mock.await_count == 5

    @patch.object(WeixinAdapter, "send", new_callable=AsyncMock)
    def test_unrelated_errors_not_blocked_by_rate_limit_check(self, send_mock):
        """非限流错误不受 rate-limit 检查影响，正常走 fallback 路径。

        使用明确的非限流、非超时错误来验证 rate-limit 检查不会误匹配。
        """
        adapter = _connected_adapter()
        send_mock.side_effect = [
            SendResult(success=False, error="Message content too long"),
            SendResult(success=True, message_id="msg-fb"),
        ]

        asyncio.run(
            adapter._send_with_retry(chat_id="wxid_test123", content="long" * 1000)
        )

        # 两次调用：第一次失败，第二次 fallback（未被 rate-limit 检查错误拦截）
        assert send_mock.await_count == 2
        fallback_content = send_mock.await_args_list[1].kwargs["content"]
        assert "plain text" in fallback_content.lower()


# ===================================================================
# End-to-end: cooldown chain from send failure to typing suppression
# ===================================================================


class TestEndToEndRateLimitCooldown:
    """端到端验收：限流发生后冷却状态贯穿 send → send_typing。

    完整链条：
    1. send() 调用 _send_text_chunk()
    2. _send_text_chunk() 收到限流 → 抛 RateLimitedError → 设 _rate_limited_until
    3. send() 捕获异常返回失败的 SendResult
    4. 同一 adapter 实例上后续 send_typing() 被冷却阻止
    """

    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    @patch("gateway.platforms.weixin._send_typing", new_callable=AsyncMock)
    def test_send_rate_limit_blocks_subsequent_typing(
        self, send_typing_mock, send_message_mock
    ):
        """send() 触发限流后，同实例上 send_typing() 被冷却阻止。"""
        adapter = _connected_adapter()
        adapter._send_chunk_retries = 3
        adapter._typing_cache.get = lambda chat_id: "ticket-xyz"
        send_message_mock.return_value = {
            "ret": -2,
            "errcode": -2,
            "errmsg": "freq limit",
        }

        # Step 1: send() 触发限流
        result = asyncio.run(adapter.send("wxid_test123", "hello"))
        assert result.success is False
        assert adapter._rate_limited_until > 0.0

        # Step 2: 冷却期内 send_typing 被跳过
        asyncio.run(adapter.send_typing("wxid_test123"))
        send_typing_mock.assert_not_awaited()

        # Step 3: 冷却过期后 send_typing 恢复
        adapter._rate_limited_until = time.time() - 1.0  # 模拟过期
        send_typing_mock.reset_mock()
        asyncio.run(adapter.send_typing("wxid_test123"))
        send_typing_mock.assert_awaited_once()
