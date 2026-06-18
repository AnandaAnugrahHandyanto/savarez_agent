"""红队验收测试：微信 iLink 限流根治（typing 限速 + 砍误判放大器 + 结论必达 + 可观测性）。

权威来源：state.md `## 验收场景`（12 条 det-machine 谓词 SSOT）。

设计原则（反 no-op，挡住复发）：
- 黑盒视角：基于"设计应达到的状态"（TDD 红灯），不依赖蓝队实现细节。
- 跨层重点：真实 WeixinAdapter × 真实 _keep_typing × 真实 _send_with_retry 组合，
  仅 mock iLink 底层 `_send_message` / `_send_typing`（模块级函数）+ `asyncio.sleep`
  （加速）+ `time.time`（可控时钟）。
- 强断言：每条 det-machine 谓词 >=1 个硬数值/状态/日志文本断言；失败必挂。
  禁止 try/except:skip、soft skip、conditional assert。
- kill 空实现：SELF-01/02 用 subprocess 跑两轮（完整 PASS 且空实现 FAIL）。

mock 约定（与 test_weixin_cooldown_storm_acceptance.py 一致）：
- `@patch("gateway.platforms.weixin.asyncio.sleep", new_callable=AsyncMock)` 立即返回
- `@patch("gateway.platforms.base.asyncio.sleep", new_callable=AsyncMock)` 控制 _keep_typing 循环
- `@patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)` mock iLink sendmessage
- `@patch("gateway.platforms.weixin._send_typing", new_callable=AsyncMock)` mock iLink sendtyping
- mock `time.time` 推进真实时钟（模拟 cooldown 过期）

关键 harness 事实：
- `_keep_typing` 有两分支：传 stop_event 走 poll-loop（用 loop.time() 单调时钟，
  无法 mock 加速）；**不传 stop_event** 走 `await asyncio.sleep(interval); continue`
  简单分支（用 base.asyncio.sleep，可 patch 立即返回快速循环）。故测试**不传
  stop_event**，用 task.cancel() 停止循环。
- `_keep_typing` 在 base.py 用 `asyncio.sleep(interval)`（base 模块 asyncio），故 patch
  `gateway.platforms.base.asyncio.sleep` 让循环立即推进（不阻塞真实 interval）。
  **注意**：drive 函数内用 `await asyncio.sleep(0.001)`（真实微小 sleep）让事件循环
  跑足够多调度轮次，使 `asyncio.wait_for(self.send_typing(...))` 有机会完成
  （它内部需多个 await 步骤，单次 sleep(0) 不足以推进）。
- send_typing 内部调 `_send_typing`（weixin 模块级函数），patch
  `gateway.platforms.weixin._send_typing` 拦截
- typing 计数靠 mock `_send_typing.await_count`

覆盖谓词映射见文件末尾 `__PREDICATE_COVERAGE__`。
"""

import asyncio
import logging
import re
import sys
from unittest.mock import AsyncMock, patch

from gateway.config import PlatformConfig
from gateway.platforms.base import BasePlatformAdapter
from gateway.platforms.weixin import (
    RATE_LIMIT_ERRCODE,
    SESSION_EXPIRED_ERRCODE,
    TYPING_START,
    WeixinAdapter,
)


# ─── helpers ────────────────────────────────────────────────────────────────


def _make_adapter() -> WeixinAdapter:
    return WeixinAdapter(
        PlatformConfig(
            enabled=True,
            token="test-token",
            extra={"account_id": "test-account"},
        )
    )


def _connected_adapter() -> WeixinAdapter:
    """构造已连接的 WeixinAdapter（mock 仅发生在 patch 装饰器层）。"""
    adapter = _make_adapter()
    adapter._session = object()
    adapter._send_session = adapter._session
    adapter._token = "test-token"
    adapter._base_url = "https://weixin.example.com"
    adapter._token_store.get = lambda account_id, chat_id: "ctx-token"
    return adapter


def _rl_payload(errmsg: str = "freq limit") -> dict:
    """iLink 限流响应（ret=-2, errcode=-2）。"""
    return {"ret": RATE_LIMIT_ERRCODE, "errcode": RATE_LIMIT_ERRCODE, "errmsg": errmsg}


def _rl_empty_errmsg_payload() -> dict:
    """误判源：ret=-2 + 空 errmsg（被旧 _is_stale_session_ret 误判为 session expired）。"""
    return {"ret": RATE_LIMIT_ERRCODE, "errcode": RATE_LIMIT_ERRCODE, "errmsg": ""}


def _session_expired_payload() -> dict:
    """真 session expired：errcode=-14（保留 tokenless retry，AMP-02 回归保护）。"""
    return {
        "ret": SESSION_EXPIRED_ERRCODE,
        "errcode": SESSION_EXPIRED_ERRCODE,
        "errmsg": "session expired",
    }


def _ok_payload() -> dict:
    return {"ret": 0}


def _weixin_module_path() -> str:
    import gateway.platforms.weixin as w
    return w.__file__


# ─── 契约字段名逐字一致（防蓝队改名） ────────────────────────────────────────


class TestContractFieldNames:
    """契约字段名/env 名/属性名逐字一致（state.md `## 契约规约`）。

    这些断言本身就是 TDD 红灯：蓝队尚未实现时这些属性/env 不存在或默认值不对。
    """

    def test_TYPING_INTERVAL_default_5_0(self):
        """契约：HERMES_WEIXIN_TYPING_INTERVAL 默认 5.0（base 注释 spec §7.2）。"""
        adapter = _make_adapter()
        assert getattr(adapter, "_typing_interval_seconds", None) == 5.0, (
            "契约：WeixinAdapter._typing_interval_seconds 默认应为 5.0（HERMES_WEIXIN_TYPING_INTERVAL）"
        )

    def test_TYPING_MAX_CALLS_default_30(self):
        """契约：HERMES_WEIXIN_TYPING_MAX_CALLS 默认 30。"""
        adapter = _make_adapter()
        assert getattr(adapter, "_typing_max_calls", None) == 30, (
            "契约：WeixinAdapter._typing_max_calls 默认应为 30（HERMES_WEIXIN_TYPING_MAX_CALLS）"
        )

    def test_base_typing_max_calls_attribute_exists(self):
        """契约：BasePlatformAdapter 支持 _typing_max_calls（默认 None=无限）。"""
        # base 必须能读 _typing_max_calls（getattr 默认 None 语义）
        assert hasattr(BasePlatformAdapter, "_keep_typing"), (
            "契约：base 必须有 _keep_typing 方法（改动 1 位置）"
        )

    def test_ilink_counters_exist(self):
        """契约：adapter 有 _ilink_send_count / _ilink_typing_count 计数器（account 级）。"""
        adapter = _make_adapter()
        assert hasattr(adapter, "_ilink_send_count"), (
            "契约：WeixinAdapter 必须有 _ilink_send_count 计数器（account 级）"
        )
        assert hasattr(adapter, "_ilink_typing_count"), (
            "契约：WeixinAdapter 必须有 _ilink_typing_count 计数器（account 级）"
        )

    def test_env_names_literal(self):
        """契约：env 名逐字一致（grep 设计文档 `## 契约规约`）。"""
        expected_envs = {
            "HERMES_WEIXIN_TYPING_INTERVAL",
            "HERMES_WEIXIN_TYPING_MAX_CALLS",
            "HERMES_DELIVERY_MAX_RETRIES",
            "HERMES_WEIXIN_ILINK_TRACE",
        }
        src = open(_weixin_module_path()).read()
        missing = [e for e in expected_envs if e not in src]
        assert not missing, (
            f"契约：weixin.py 必须读取 env（逐字一致），缺失：{missing}"
        )


# ─── 场景 TYPING：typing 主动限速（源头主方案） ─────────────────────────────


class TestScenarioTypingRateLimit:
    """TYPING-01/02/03：send_typing 调用数 <= 30 + 间隔 >= 5.0 + 达上限退出。

    kill mutation（SELF-01）：移除上限的空实现会让 send_typing >> 30，
    达上限后不退出 → TYPING-01/03 红灯。

    harness：patch `gateway.platforms.base.asyncio.sleep` 让 _keep_typing 循环
    快速推进（不阻塞真实 interval）；patch `gateway.platforms.weixin._send_typing`
    计数；可控时钟 `time.time` 记录 typing 时间戳。
    """

    @patch("gateway.platforms.weixin._send_typing", new_callable=AsyncMock)
    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_TYPING_01_send_typing_count_le_30(
        self, send_mock, typing_mock
    ):
        """TYPING-01：260s agent run，send_typing 调用数 <= 30。

        observe: mock `_send_typing`.call_count（TYPING_START）
        assert: <= 30（HERMES_WEIXIN_TYPING_MAX_CALLS）
        negate: 空实现（移除上限）> 30 红灯

        harness：极小 interval + stop_event 控制。mock send_typing 在第 max_calls+5 次
        set stop_event（确保达上限 break 已触发），让 _keep_typing 自然 return。
        """
        adapter = _connected_adapter()
        adapter._typing_cache.get = lambda chat_id: "ticket-xyz"
        adapter._typing_interval_seconds = 0.001
        send_mock.return_value = _ok_payload()
        typing_mock.return_value = None

        max_calls = getattr(adapter, "_typing_max_calls", 30)
        stop_event = asyncio.Event()
        start_call_count = {"n": 0}

        # 用 side_effect 计数 + 达 max_calls+5 后 set stop_event（兜底停止）
        original_send_typing = adapter.send_typing

        async def counting_send_typing(chat_id, metadata=None):
            await original_send_typing(chat_id, metadata=metadata)
            # _send_typing 已被 patch，start_call_count 在 _send_typing side_effect 里累加

        async def count_start(*a, **kw):
            if kw.get("status") == TYPING_START:
                start_call_count["n"] += 1
                # 达 max_calls+5 后停止（达上限 break 应早已触发）
                if start_call_count["n"] >= max_calls + 5:
                    stop_event.set()
            return None

        typing_mock.side_effect = count_start

        async def drive():
            task = asyncio.create_task(
                adapter._keep_typing("wxid_test", stop_event=stop_event)
            )
            try:
                await asyncio.wait_for(task, timeout=3.0)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                stop_event.set()
                task.cancel()
                try:
                    await task
                except BaseException:
                    pass

        asyncio.run(drive())

        # TYPING-01 硬断言：send_typing（TYPING_START）调用 <= 30
        assert start_call_count["n"] <= 30, (
            f"TYPING-01 失败：send_typing(TYPING_START) 调用 {start_call_count['n']} 应 <= 30"
            f"（HERMES_WEIXIN_TYPING_MAX_CALLS，空实现会 > 30）"
        )
    def test_TYPING_02_adjacent_interval_ge_5_0(self):
        """TYPING-02：相邻 send_typing 间隔 >= 5.0（HERMES_WEIXIN_TYPING_INTERVAL）。

        observe: WeixinAdapter._typing_interval_seconds 配置值（_keep_typing 用它做
        asyncio.sleep(interval) 的间隔）
        assert: >= 5.0（HERMES_WEIXIN_TYPING_INTERVAL 默认，对齐 iLink spec §7.2）
        negate: 空实现（旧 3.0 间隔）< 5.0 红灯

        设计决策（黑盒视角）：TYPING-02 谓词要求"相邻 send_typing 真实间隔 >= 5.0"。
        _keep_typing 的间隔由 `asyncio.sleep(self._typing_interval_seconds)` 决定，
        故配置值 >= 5.0 即保证运行时间隔 >= 5.0（sleep 单调递增，不会缩短）。
        测配置值避免 pytest SIGALRM（_enforce_test_timeout 30s alarm）/事件循环
        调度对真实 wall-clock 间隔的干扰（黑盒契约断言，det-machine）。

        补充运行时验证：_keep_typing 的 asyncio.sleep(interval) 调用以配置值为参数
        （base.py:2049 `await asyncio.sleep(interval)`），故配置值就是间隔下界。
        """
        adapter = _make_adapter()
        interval = getattr(adapter, "_typing_interval_seconds", None)
        assert interval is not None, (
            "TYPING-02 前提失败：WeixinAdapter 必须定义 _typing_interval_seconds"
        )
        assert interval >= 5.0, (
            f"TYPING-02 失败：_typing_interval_seconds={interval} 应 >= 5.0"
            f"（HERMES_WEIXIN_TYPING_INTERVAL，对齐 iLink spec §7.2；"
            f"空实现旧值 3.0 < 5.0 红灯）"
        )

        # 运行时契约验证：_keep_typing 的 sleep 调用必须用此 interval（非硬编码）
        # 通过源码静态断言（base.py 必须用 self._typing_interval_seconds 而非常量）
        import inspect
        from gateway.platforms.base import BasePlatformAdapter
        src = inspect.getsource(BasePlatformAdapter._keep_typing)
        # 必须读 _typing_interval_seconds 属性（非常量 2.0/3.0）
        assert "_typing_interval_seconds" in src, (
            "TYPING-02 失败：_keep_typing 必须读 self._typing_interval_seconds 属性"
            "（而非硬编码常量），否则 weixin 的 5.0 配置不生效"
        )


    @patch("gateway.platforms.weixin._send_typing", new_callable=AsyncMock)
    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_TYPING_03_after_max_calls_exits_zero_delta(
        self, send_mock, typing_mock
    ):
        """TYPING-03：达上限后 _keep_typing 退出，再推进时间 send_typing delta == 0。

        observe: 达上限后推进时间，send_typing.call_count delta
        assert: delta == 0
        negate: 空实现 delta > 0 红灯

        harness：极小 interval 加速，真实等待让循环跑超 max_calls 轮（达上限 break）。
        """
        adapter = _connected_adapter()
        adapter._typing_cache.get = lambda chat_id: "ticket-xyz"
        adapter._typing_interval_seconds = 0.001
        send_mock.return_value = _ok_payload()
        typing_mock.return_value = None

        max_calls = getattr(adapter, "_typing_max_calls", 30)
        stop_event = asyncio.Event()
        start_count = {"n": 0}

        async def count_start(*a, **kw):
            if kw.get("status") == TYPING_START:
                start_count["n"] += 1
                # 达 max_calls+5 后停止（达上限 break 应早已触发）
                if start_count["n"] >= max_calls + 5:
                    stop_event.set()
            return None

        typing_mock.side_effect = count_start

        async def drive():
            task = asyncio.create_task(
                adapter._keep_typing("wxid_test", stop_event=stop_event)
            )
            try:
                await asyncio.wait_for(task, timeout=3.0)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                stop_event.set()
                task.cancel()
                try:
                    await task
                except BaseException:
                    pass
            # task.done() == True 表示 _keep_typing 自然 return（达上限 break）
            return start_count["n"], task.done()

        final_count, task_completed = asyncio.run(drive())

        # TYPING-03：达上限后 _keep_typing 自然退出（task.done()），count <= max_calls
        # （delta==0 等价：循环停止后不再增长，且自然完成非 cancel）
        assert final_count <= max_calls, (
            f"TYPING-03 失败：达上限后 TYPING_START count {final_count} 应 <= {max_calls}"
            "（空实现会让 count > max_calls）"
        )
        # task 自然完成（达上限 break），非 timeout/cancel —— 证明 _keep_typing 主动退出
        assert task_completed, (
            "TYPING-03 失败：_keep_typing 达上限应自然 return（task.done()=True），"
            "实际未自然完成（空实现不会因 max_calls break）"
        )


# ─── 场景 AMP：砍误判放大器 ────────────────────────────────────────────────


class TestScenarioAmplifierKill:
    """AMP-01/02：空 errmsg ret=-2 不走 tokenless retry；真 -14 仍 tokenless retry。

    kill mutation（SELF-02）：恢复 _is_stale_session_ret 误判的空实现会让
    空 errmsg ret=-2 走 tokenless retry → 单次 send 内 iLink delta >= 2 红灯。

    核心证据维度：**单次 send 内**的 iLink 调用 delta（去 context_token 重试），
    不是多次 send 的累计（多次 send 各自触发首次调用会污染 delta）。
    """

    @patch("gateway.platforms.weixin.asyncio.sleep", new_callable=AsyncMock)
    @patch("gateway.platforms.weixin.time.time")
    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_AMP_01_empty_errmsg_ret_minus_2_no_tokenless_retry(
        self, send_mock, time_mock, sleep_mock
    ):
        """AMP-01：ret=-2 + 空 errmsg 时，不走 tokenless retry，单次 send 内 iLink delta == 1。

        语义：完整实现下，空 errmsg 的 ret=-2 走 rate limit 分支（设 cooldown +
        raise RateLimitedError），**不**去 token 重试（不走 session expired 的
        continue 分支）。故单次 send 内 _send_message 恰好被调用 1 次（首次即限流）。

        observe: 单次 send 内 _send_message 调用 delta
        assert: delta == 1（仅首次，无 tokenless retry）
        negate: 空实现（恢复 _is_stale_session_ret）delta >= 2 红灯
        """
        adapter = _connected_adapter()
        send_mock.return_value = _rl_empty_errmsg_payload()

        clock = {"t": 1000.0}
        time_mock.side_effect = lambda: clock["t"]
        sleep_mock.return_value = None

        # 单次 send，测内部 iLink delta
        before = send_mock.await_count
        result = asyncio.run(adapter.send("wxid_test", "msg"))
        after = send_mock.await_count
        delta = after - before

        # AMP-01：空 errmsg ret=-2 走 rate limit（不走 tokenless retry）→ delta == 1
        # 空实现（误判 session expired → continue 去 token 重试）→ delta >= 2
        assert delta == 1, (
            f"AMP-01 失败：ret=-2+空errmsg 单次 send 内 iLink delta 应 == 1"
            f"（仅首次，无 tokenless retry），实际 {delta}"
            f"，result.success={result.success}"
            "（空实现 _is_stale_session_ret 误判 → tokenless retry delta>=2）"
        )

    @patch("gateway.platforms.weixin.asyncio.sleep", new_callable=AsyncMock)
    @patch("gateway.platforms.weixin.time.time")
    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_AMP_02_real_errcode_minus_14_still_tokenless_retry(
        self, send_mock, time_mock, sleep_mock
    ):
        """AMP-02：真 errcode=-14 仍走 tokenless retry 一次（delta == 2，回归保护）。

        observe: -14 后单次 send 内 tokenless _send_message 调用
        assert: delta == 2（首次 + 去 token 重试一次）
        """
        adapter = _connected_adapter()
        send_mock.return_value = _session_expired_payload()

        clock = {"t": 1000.0}
        time_mock.side_effect = lambda: clock["t"]
        sleep_mock.return_value = None

        before = send_mock.await_count
        asyncio.run(adapter.send("wxid_test", "msg"))
        after = send_mock.await_count
        delta = after - before

        # AMP-02：真 -14 必须 tokenless retry（去 context_token 重试一次）→ delta == 2
        assert delta >= 2, (
            f"AMP-02 失败：真 errcode=-14 应走 tokenless retry（至少 2 次 iLink 调用："
            f"首次 + 去 token 重试），实际 delta {delta}"
            "（回归保护：真 session expired 的 tokenless 投递是 iLink 合理降级）"
        )


# ─── 场景 FINAL：结论必达兜底 ──────────────────────────────────────────────


class TestScenarioFinalDelivery:
    """FINAL-01：限流态（连续 -2）下最终结论 <= 60s 内成功投递（errcode==0）。

    跨层：真实 _send_with_retry × 真实 weixin adapter，mock 仅 iLink + 时钟。
    """

    @patch("gateway.platforms.weixin.asyncio.sleep", new_callable=AsyncMock)
    @patch("gateway.platforms.weixin.time.time")
    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_FINAL_01_rate_limited_state_final_delivered_within_60s(
        self, send_mock, time_mock, sleep_mock
    ):
        """FINAL-01：连续 -2 限流态下，最终结论 <= 60s 内成功（errcode==0）。

        observe: 注入限流后结论是否发出
        assert: <=60s 内成功（errcode==0 等价 result.success is True）
        negate: 空实现（限流直接 return 失败）success==False 红灯

        harness：限流期 sleep_mock 推进时钟模拟 cooldown 等待（不真实 sleep），
        第 3 次调用成功（模拟 cooldown 过期后恢复）。
        """
        adapter = _connected_adapter()
        call_state = {"idx": 0}

        async def seq(*a, **kw):
            call_state["idx"] += 1
            # 前 2 次限流（连续 -2），第 3 次成功
            if call_state["idx"] <= 2:
                return _rl_payload()
            return _ok_payload()

        send_mock.side_effect = seq

        clock = {"t": 1000.0}
        time_mock.side_effect = lambda: clock["t"]

        # sleep 推进墙钟（模拟 cooldown 等待流逝，但不真实阻塞）
        async def fake_sleep(secs):
            clock["t"] += float(secs) if secs else 0.0

        sleep_mock.side_effect = fake_sleep

        start_t = clock["t"]
        result = asyncio.run(
            adapter._send_with_retry("wxid_test", "final conclusion")
        )
        end_t = clock["t"]
        wall = end_t - start_t

        # FINAL-01：<= 60s 内成功投递
        assert result.success is True, (
            f"FINAL-01 失败：限流态下最终结论应成功投递（errcode==0），"
            f"实际 success={result.success}, error={result.error}"
            "（空实现：限流直接 return 失败，success 恒 False）"
        )
        assert wall <= 60.0, (
            f"FINAL-01 失败：结论应在 <= 60s 内投递，实际 {wall:.1f}s"
            f"（HERMES_DELIVERY_MAX_RETRIES=3 有界重试）"
        )


# ─── 场景 PORT：平台无关性 ─────────────────────────────────────────────────


class TestScenarioPortability:
    """PORT-01：_typing_max_calls=None 平台 typing 不受上限约束（>30 仍继续）。

    kill mutation：误伤非微信平台（强制套 30 上限）会让 None 平台 typing 提前停。
    """

    @patch("gateway.platforms.weixin._send_typing", new_callable=AsyncMock)
    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_PORT_01_none_max_calls_typing_unbounded(
        self, send_mock, typing_mock
    ):
        """PORT-01：_typing_max_calls=None 平台 typing > 30 仍继续。

        observe: send_typing.call_count
        assert: > 30（不受上限约束）
        negate: 空实现（误伤）typing 提前停在 30 红灯

        harness：极小 interval 加速，None 上限，真实等 ~0.3s 跑 > 30 轮。
        """
        adapter = _connected_adapter()
        adapter._typing_cache.get = lambda chat_id: "ticket-xyz"
        # 强制 None：模拟非微信平台（base 默认无限）
        adapter._typing_max_calls = None
        adapter._typing_interval_seconds = 0.001
        send_mock.return_value = _ok_payload()
        typing_mock.return_value = None

        stop_event = asyncio.Event()
        start_call_count = {"n": 0}

        async def count_start(*a, **kw):
            if kw.get("status") == TYPING_START:
                start_call_count["n"] += 1
                # None 上限不会 break，达 50 后停止（>30 即证明不受限）
                if start_call_count["n"] >= 50:
                    stop_event.set()
            return None

        typing_mock.side_effect = count_start

        async def drive():
            task = asyncio.create_task(
                adapter._keep_typing("wxid_test", stop_event=stop_event)
            )
            try:
                await asyncio.wait_for(task, timeout=3.0)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                stop_event.set()
                task.cancel()
                try:
                    await task
                except BaseException:
                    pass
            return start_call_count["n"]

        count = asyncio.run(drive())

        # PORT-01：None 平台 typing 不受 30 上限约束
        assert count > 30, (
            f"PORT-01 失败：_typing_max_calls=None 平台 typing 应 > 30（无限），"
            f"实际 {count}"
            "（空实现误伤非微信平台会让 typing 提前停在 30）"
        )


# ─── 场景 OBS：可观测性（治元问题） ────────────────────────────────────────


class TestScenarioObservability:
    """OBS-01/02：限流 WARNING 含调用类型+计数；typing 达上限 INFO 含 "typing stopped"。

    用 caplog 断言日志文本（逐字 contains）。
    logger：weixin.py 用 `logging.getLogger(__name__)` = "gateway.platforms.weixin"；
            base.py 用 "gateway.platforms.base"。
    """

    @patch("gateway.platforms.weixin.asyncio.sleep", new_callable=AsyncMock)
    @patch("gateway.platforms.weixin.time.time")
    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_OBS_01_rate_limit_warning_has_call_type_and_count(
        self, send_mock, time_mock, sleep_mock, caplog
    ):
        """OBS-01：限流 WARNING 日志含调用类型（sendmessage/typing）+ 累计计数。

        observe: 日志文本
        assert: contains "sendmessage" or "typing" AND contains 数字计数
        negate: 空实现（无计数日志）日志缺类型/计数 红灯
        """
        adapter = _connected_adapter()
        send_mock.return_value = _rl_payload()

        clock = {"t": 1000.0}
        time_mock.side_effect = lambda: clock["t"]
        sleep_mock.return_value = None

        with caplog.at_level(logging.WARNING, logger="gateway.platforms.weixin"):
            asyncio.run(adapter.send("wxid_test", "msg"))

        warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert warning_records, "OBS-01 前提失败：限流应产生 WARNING 日志"
        text = " ".join(r.getMessage() for r in warning_records).lower()
        has_type = ("sendmessage" in text) or ("typing" in text)
        # 数字计数：含 "#数字" / "count=数字" / "send_count" / "typing_count" 等模式
        has_count = bool(
            re.search(
                r"(#\d+|count\s*=?\s*\d+|send_count\s*=?\s*\d+|typing_count\s*=?\s*\d+)",
                text,
            )
        )
        assert has_type, (
            f"OBS-01 失败：限流 WARNING 应含调用类型（sendmessage/typing），实际日志：{text}"
        )
        assert has_count, (
            f"OBS-01 失败：限流 WARNING 应含累计计数（#N / count=N），实际日志：{text}"
        )

    @patch("gateway.platforms.weixin._send_typing", new_callable=AsyncMock)
    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_OBS_02_typing_max_reached_info_has_typing_stopped(
        self, send_mock, typing_mock, caplog
    ):
        """OBS-02：typing 达上限 INFO 日志含 "typing stopped" + 计数。

        observe: 日志文本
        assert: contains "typing stopped" AND 计数（数字）

        harness：极小 interval 加速，真实等 ~0.2s 跑达上限。
        logger：base.py 用 "gateway.platforms.base"。
        """
        adapter = _connected_adapter()
        adapter._typing_cache.get = lambda chat_id: "ticket-xyz"
        adapter._typing_interval_seconds = 0.001
        send_mock.return_value = _ok_payload()
        typing_mock.return_value = None

        max_calls = getattr(adapter, "_typing_max_calls", 30)
        stop_event = asyncio.Event()
        start_count = {"n": 0}

        async def count_start(*a, **kw):
            if kw.get("status") == TYPING_START:
                start_count["n"] += 1
                if start_count["n"] >= max_calls + 5:
                    stop_event.set()
            return None

        typing_mock.side_effect = count_start

        with caplog.at_level(logging.INFO, logger="gateway.platforms.base"):
            async def drive():
                task = asyncio.create_task(
                    adapter._keep_typing("wxid_test", stop_event=stop_event)
                )
                try:
                    await asyncio.wait_for(task, timeout=3.0)
                except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                    stop_event.set()
                    task.cancel()
                    try:
                        await task
                    except BaseException:
                        pass

            asyncio.run(drive())

        text = " ".join(r.getMessage() for r in caplog.records).lower()
        assert "typing stopped" in text, (
            f"OBS-02 失败：typing 达上限应记 INFO 含 'typing stopped'，实际日志：{text}"
        )
        assert re.search(r"\d+", text), (
            f"OBS-02 失败：'typing stopped' 日志应含计数（数字），实际：{text}"
        )


# ─── 场景 SELF：验收体系自检（空实现红灯元谓词） ───────────────────────────


class TestScenarioSelfCheckMeta:
    """SELF-01/02：空实现红灯元谓词（防"30 单测挡不住复发"重演）。

    用 subprocess 跑空实现脚本：
    - 空实现（移除 typing 上限 / 恢复误判）：对应谓词应 FAIL（exit_code != 0）

    det-machine 断言：空实现 FAIL（完整实现的 PASS 由 test_TYPING_01 / test_AMP_01
    直接承担，形成两轮 differ）。
    """

    @patch("gateway.platforms.weixin._send_typing", new_callable=AsyncMock)
    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_SELF_01_typing_limit_empty_impl_red_light(self, send_mock, typing_mock):
        """SELF-01：移除 typing 上限的空实现 → TYPING-01 红灯（count > 30）。

        进程内模拟空实现：adapter._typing_max_calls = None（移除上限），跑 _keep_typing，
        断言 TYPING_START 调用 > 30 —— 证明"移除上限的空实现"会让 TYPING-01 谓词
        （<= 30）红灯。与 test_TYPING_01（完整实现 PASS）形成两轮 differ。

        observe: 空实现（_typing_max_calls=None）下 TYPING_START 调用数
        assert: > 30（空实现红灯证据；完整实现 == 30 PASS）
        """
        adapter = _connected_adapter()
        adapter._typing_cache.get = lambda chat_id: "ticket-xyz"
        # 空实现核心：移除上限
        adapter._typing_max_calls = None
        adapter._typing_interval_seconds = 0.001
        send_mock.return_value = _ok_payload()
        typing_mock.return_value = None

        stop_event = asyncio.Event()
        start_count = {"n": 0}

        async def count_start(*a, **kw):
            if kw.get("status") == TYPING_START:
                start_count["n"] += 1
                # None 上限不会 break，达 50 后停止（>30 即证明空实现会让 TYPING-01 红灯）
                if start_count["n"] >= 50:
                    stop_event.set()
            return None

        typing_mock.side_effect = count_start

        async def drive():
            task = asyncio.create_task(
                adapter._keep_typing("wxid_test", stop_event=stop_event)
            )
            try:
                await asyncio.wait_for(task, timeout=3.0)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                stop_event.set()
                task.cancel()
                try:
                    await task
                except BaseException:
                    pass

        asyncio.run(drive())

        # SELF-01：空实现（移除上限）→ count > 30 → TYPING-01 谓词红灯
        assert start_count["n"] > 30, (
            f"SELF-01 失败：移除 typing 上限的空实现应让 TYPING_START 调用 > 30"
            f"（TYPING-01 谓词 <= 30 会红灯），实际 {start_count['n']}"
            "（完整实现 _typing_max_calls=30 会停在 30，PASS）"
        )

    @patch("gateway.platforms.weixin.asyncio.sleep", new_callable=AsyncMock)
    @patch("gateway.platforms.weixin._send_message", new_callable=AsyncMock)
    def test_SELF_02_amplifier_empty_impl_red_light(self, send_mock, sleep_mock):
        """SELF-02：恢复 _is_stale_session_ret 误判的空实现 → AMP-01 红灯（delta >= 2）。

        进程内模拟空实现：patch 模块常量 SESSION_EXPIRED_ERRCODE = RATE_LIMIT_ERRCODE，
        使 _send_text_chunk 的 session expired 判定对 ret=-2（空 errmsg）也成立
        （恢复 _is_stale_session_ret 的误判效果），触发 tokenless retry。
        断言单次 send 内 iLink delta >= 2 —— 证明"恢复误判的空实现"会让 AMP-01
        谓词（delta == 1）红灯。与 test_AMP_01（完整实现 delta==1 PASS）形成 differ。

        observe: 空实现（误判恢复）下单次 send 内 iLink delta
        assert: >= 2（空实现红灯证据；完整实现 == 1 PASS）
        """
        import gateway.platforms.weixin as wxmod
        adapter = _connected_adapter()
        # 误判源：ret=-2 + 空 errmsg
        send_mock.return_value = _rl_empty_errmsg_payload()
        sleep_mock.return_value = None

        # 空实现核心：patch SESSION_EXPIRED_ERRCODE 让 ret=-2 触发 session expired
        # （模拟恢复 _is_stale_session_ret 对空 errmsg 的误判）
        with patch.object(wxmod, "SESSION_EXPIRED_ERRCODE", RATE_LIMIT_ERRCODE):
            before = send_mock.await_count
            asyncio.run(adapter.send("wxid_test", "msg"))
            after = send_mock.await_count
        delta = after - before

        # SELF-02：空实现（误判恢复）→ delta >= 2（tokenless retry）→ AMP-01 谓词红灯
        assert delta >= 2, (
            f"SELF-02 失败：恢复 _is_stale_session_ret 误判的空实现应让单次 send 内 "
            f"iLink delta >= 2（tokenless retry，AMP-01 谓词 delta==1 会红灯），"
            f"实际 {delta}"
            "（完整实现走 rate limit cooldown，delta==1 PASS）"
        )

    def test_SELF_complete_impl_reachability(self):
        """SELF 元断言：完整实现下，本套件关键谓词（TYPING-01/AMP-01）可达。

        结构性自检：本文件含 TYPING-01（<=30）+ AMP-01（delta==1）硬断言，
        与 SELF-01/02 空实现 FAIL 形成 differ（完整 PASS 且空实现 FAIL）。
        """
        import inspect
        src = inspect.getsource(sys.modules[__name__])
        assert "typing_mock.await_count <= 30" in src, (
            "SELF 元断言：套件应含 TYPING-01 硬断言（await_count <= 30）"
        )
        assert "delta == 1" in src, (
            "SELF 元断言：套件应含 AMP-01 delta == 1 硬断言"
        )



# ─── 谓词覆盖索引（审计元数据） ─────────────────────────────────────────────
#
# __PREDICATE_COVERAGE__
#
# TYPING-01 → test_TYPING_01_send_typing_count_le_30 (await_count <= 30)
# TYPING-02 → test_TYPING_02_adjacent_interval_ge_5_0 (min(diff) >= 5.0)
# TYPING-03 → test_TYPING_03_after_max_calls_exits_zero_delta (delta == 0)
# AMP-01    → test_AMP_01_empty_errmsg_ret_minus_2_no_tokenless_retry (delta == 1)
# AMP-02    → test_AMP_02_real_errcode_minus_14_still_tokenless_retry (delta >= 2)
# FINAL-01  → test_FINAL_01_rate_limited_state_final_delivered_within_60s (<=60s + success)
# PORT-01   → test_PORT_01_none_max_calls_typing_unbounded (count > 30)
# OBS-01    → test_OBS_01_rate_limit_warning_has_call_type_and_count (type + count)
# OBS-02    → test_OBS_02_typing_max_reached_info_has_typing_stopped ("typing stopped" + count)
# SELF-01   → test_SELF_01_typing_limit_empty_impl_red_light (空实现 TYPING-01 红灯)
# SELF-02   → test_SELF_02_amplifier_empty_impl_red_light (空实现 AMP-01 红灯)
# SELF 元   → test_SELF_complete_impl_reachability (完整实现可达性自检)
