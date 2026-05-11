"""
session_mode_state.py — Hermes 人格模式状态机
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
职责:
  持有 WORK / LIFE 当前状态、切换历史、最近路由分类（auto-sense 上下文）
  持久化到 MEMORY.md [mode_state] 条目
  线程安全 — gateway 并发请求同一 session 时不竞态

依赖: 仅标准库，无 Hermes 内部循环依赖
上游调用方: ModeDetector (mode_detection.py)
            ephemeral_prompt builder
            Brain pipeline (route_message → record_route)
"""

from __future__ import annotations

import datetime
import logging
import re
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 枚举
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AgentMode(str, Enum):
    WORK = "WORK"
    LIFE = "LIFE"

    def opposite(self) -> "AgentMode":
        return AgentMode.LIFE if self == AgentMode.WORK else AgentMode.WORK


class TriggerType(str, Enum):
    COMMAND          = "command"          # 用户明确指令切换
    AUTO_SENSE       = "auto_sense"       # 信号积累自动感知
    AUTOMATION_LOCK  = "automation_lock"  # 自动化场景强制锁定
    SESSION_INIT     = "session_init"     # session 初始化/恢复
    NONE             = "none"             # 无切换


class RouteClass(str, Enum):
    """Brain 路由分类，记录到 auto-sense 上下文窗口。"""
    SIMPLE  = "simple"
    CODING  = "coding"
    COMPLEX = "complex"
    VISION  = "vision"
    PERSONA = "persona"   # 人格/模式切换消息

    @property
    def is_technical(self) -> bool:
        return self in (RouteClass.CODING, RouteClass.COMPLEX)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MEMORY.md 持久化格式
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_MEMORY_PREFIX = "[mode_state]"

# 写入格式
def _format_memory_entry(
    mode: AgentMode,
    ts: datetime.datetime,
    trigger: TriggerType,
    reason: str,
) -> str:
    return (
        f"{_MEMORY_PREFIX} 最后模式: {mode.value} | "
        f"切换时间: {ts.strftime('%Y-%m-%dT%H:%M:%S')} | "
        f"触发: {trigger.value} | "
        f"原因: {reason}"
    )

# 读取正则
_MEMORY_RE = re.compile(
    r"\[mode_state\]\s+最后模式:\s*(?P<mode>WORK|LIFE)"
    r"\s*\|\s*切换时间:\s*(?P<ts>[^\|]+)"
    r"\s*\|\s*触发:\s*(?P<trigger>[^\|]+)"
    r"\s*\|\s*原因:\s*(?P<reason>.+)$",
    re.IGNORECASE,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SwitchRecord
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass(frozen=True)
class SwitchRecord:
    """单次模式切换的不可变记录。"""
    from_mode : AgentMode
    to_mode   : AgentMode
    trigger   : TriggerType
    reason    : str
    ts        : datetime.datetime = field(default_factory=datetime.datetime.now)

    def __str__(self) -> str:
        return (
            f"[{self.ts.strftime('%H:%M:%S')}] "
            f"{self.from_mode.value} → {self.to_mode.value} "
            f"via {self.trigger.value}: {self.reason}"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SessionModeState
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SessionModeState:
    """
    Hermes session 人格模式状态机。

    ── 线程安全 ──────────────────────────────────
    所有公开方法通过 self._lock (RLock) 保护。
    RLock 允许同一线程重入（switch_mode → _persist 路径安全）。

    ── auto-sense 上下文窗口 ─────────────────────
    _recent_routes: 最近 CONTEXT_WINDOW 轮的 RouteClass
    Brain pipeline 每次路由决策后调用 record_route() 更新。
    ModeDetector 读取 has_recent_technical_context() 判断 Signal C。

    ── 持久化 ────────────────────────────────────
    persist_callback: (entry_str: str) -> None
    每次 switch_mode 后调用，写入 MEMORY.md [mode_state] 行。
    None 时只在内存中维护，适合测试场景。
    """

    # 可调整常量
    CONTEXT_WINDOW     = 4   # 保留最近 N 轮路由分类
    SWITCH_HISTORY_MAX = 20  # 最多保留 N 条切换记录

    # ── 初始化 ────────────────────────────────────────────────────────────────

    def __init__(
        self,
        initial_mode     : AgentMode = AgentMode.WORK,
        trigger          : TriggerType = TriggerType.SESSION_INIT,
        reason           : str = "default",
        persist_callback : Optional[Callable[[str], None]] = None,
    ) -> None:
        self._lock              = threading.RLock()
        self._mode              = initial_mode
        self._persist_callback  = persist_callback
        self._automation_locked = False
        self._last_switch_ts    = datetime.datetime.now()
        self._last_trigger      = trigger
        self._last_reason       = reason

        self._recent_routes : deque[RouteClass]   = deque(maxlen=self.CONTEXT_WINDOW)
        self._switch_history: deque[SwitchRecord] = deque(maxlen=self.SWITCH_HISTORY_MAX)

        logger.debug("SessionModeState init | mode=%s trigger=%s", initial_mode.value, trigger.value)

    # ── 只读属性 ──────────────────────────────────────────────────────────────

    @property
    def current_mode(self) -> AgentMode:
        with self._lock:
            return self._mode

    @property
    def is_work(self) -> bool:
        return self.current_mode == AgentMode.WORK

    @property
    def is_life(self) -> bool:
        return self.current_mode == AgentMode.LIFE

    @property
    def automation_locked(self) -> bool:
        with self._lock:
            return self._automation_locked

    @property
    def last_switch_ts(self) -> datetime.datetime:
        with self._lock:
            return self._last_switch_ts

    @property
    def last_trigger(self) -> TriggerType:
        with self._lock:
            return self._last_trigger

    @property
    def last_reason(self) -> str:
        with self._lock:
            return self._last_reason

    @property
    def switch_history(self) -> List[SwitchRecord]:
        with self._lock:
            return list(self._switch_history)

    @property
    def recent_routes(self) -> List[RouteClass]:
        with self._lock:
            return list(self._recent_routes)

    @property
    def last_record(self) -> Optional[SwitchRecord]:
        with self._lock:
            return self._switch_history[-1] if self._switch_history else None

    def seconds_since_last_switch(self) -> float:
        with self._lock:
            return (datetime.datetime.now() - self._last_switch_ts).total_seconds()

    # ── 核心写操作 ────────────────────────────────────────────────────────────

    def switch_mode(
        self,
        target_mode : AgentMode,
        trigger     : TriggerType,
        reason      : str,
    ) -> bool:
        """
        切换到目标模式。

        幂等: 已在目标模式时静默返回 False，不重复记录。
        自动化锁: 锁定后只允许切换到 WORK，其他目标被拒绝。

        Returns:
            True  — 切换发生并已持久化
            False — 无切换（已是目标模式 or 被锁阻止）
        """
        with self._lock:
            if self._automation_locked and target_mode != AgentMode.WORK:
                logger.warning(
                    "switch_mode blocked by automation lock | target=%s trigger=%s",
                    target_mode.value, trigger.value,
                )
                return False

            if self._mode == target_mode:
                logger.debug("switch_mode: already in %s, skip", target_mode.value)
                return False

            record = SwitchRecord(
                from_mode=self._mode,
                to_mode=target_mode,
                trigger=trigger,
                reason=reason,
            )
            self._switch_history.append(record)
            self._mode           = target_mode
            self._last_switch_ts = record.ts
            self._last_trigger   = trigger
            self._last_reason    = reason

            logger.info("Mode switched | %s", record)
            self._persist()
            return True

    def apply_automation_lock(self) -> bool:
        """
        激活自动化强制锁。
        - 强制切换到 WORK（如当前是 LIFE）
        - 此后拒绝所有非 WORK 切换请求
        - 锁一旦设置，session 生命周期内不解除

        Returns:
            True  — 锁定成功
            False — 已经锁定
        """
        with self._lock:
            if self._automation_locked:
                return False
            self._automation_locked = True
            logger.info("Automation lock applied")
            # 内部调用 switch_mode；因为 _automation_locked 已置 True，
            # 且目标是 WORK，不会被锁拦截
            self.switch_mode(
                AgentMode.WORK,
                TriggerType.AUTOMATION_LOCK,
                "automated context detected",
            )
            return True

    def record_route(self, route: RouteClass) -> None:
        """
        Brain 路由决策完成后调用，更新 auto-sense 上下文窗口。
        调用方: Brain Execution layer，每轮必须调用一次。
        """
        with self._lock:
            self._recent_routes.append(route)

    # ── auto-sense 上下文查询 ─────────────────────────────────────────────────

    def has_recent_technical_context(self) -> bool:
        """
        最近 CONTEXT_WINDOW 轮是否含技术性路由（coding / complex）。
        ModeDetector 用于 WORK→LIFE auto-sense Signal C 判断。
        """
        with self._lock:
            return any(r.is_technical for r in self._recent_routes)

    def recent_technical_ratio(self) -> float:
        """
        最近 N 轮中技术性路由的比例（0.0 ~ 1.0）。
        可选用于更精细的 auto-sense 权重计算。
        """
        with self._lock:
            if not self._recent_routes:
                return 0.0
            tech = sum(1 for r in self._recent_routes if r.is_technical)
            return tech / len(self._recent_routes)

    # ── MEMORY.md 持久化 ──────────────────────────────────────────────────────

    def _persist(self) -> None:
        """写入 MEMORY.md。由 switch_mode 在锁内调用，异常静默降级。"""
        if self._persist_callback is None:
            return
        entry = _format_memory_entry(
            mode=self._mode,
            ts=self._last_switch_ts,
            trigger=self._last_trigger,
            reason=self._last_reason,
        )
        try:
            self._persist_callback(entry)
        except Exception as exc:
            logger.warning("Mode state persist failed (non-fatal): %s", exc)

    def to_memory_entry(self) -> str:
        """导出 MEMORY.md 格式字符串（不触发 callback，只读）。"""
        with self._lock:
            return _format_memory_entry(
                mode=self._mode,
                ts=self._last_switch_ts,
                trigger=self._last_trigger,
                reason=self._last_reason,
            )

    # ── 工厂方法 ──────────────────────────────────────────────────────────────

    @classmethod
    def from_memory_entry(
        cls,
        entry: str,
        persist_callback: Optional[Callable[[str], None]] = None,
    ) -> "SessionModeState":
        """
        从 MEMORY.md [mode_state] 条目恢复状态。
        解析失败时静默返回默认 WORK 实例（不抛异常，防止 session 启动阻塞）。
        """
        m = _MEMORY_RE.search(entry)
        if not m:
            logger.warning("Cannot parse mode_state entry, defaulting to WORK | entry=%r", entry[:120])
            return cls.default(persist_callback=persist_callback)

        try:
            mode    = AgentMode(m.group("mode").strip().upper())
            trigger = TriggerType(m.group("trigger").strip().lower())
            reason  = m.group("reason").strip()
            ts      = datetime.datetime.fromisoformat(m.group("ts").strip())
        except (ValueError, KeyError) as exc:
            logger.warning("Mode state parse error: %s — defaulting to WORK", exc)
            return cls.default(persist_callback=persist_callback)

        state = cls(
            initial_mode     = mode,
            trigger          = TriggerType.SESSION_INIT,
            reason           = f"restored (original: {trigger.value} — {reason})",
            persist_callback = persist_callback,
        )
        # 覆盖初始化时写入的 now() 时间戳，还原为持久化时间
        state._last_switch_ts = ts
        state._last_trigger   = trigger
        state._last_reason    = reason

        logger.info("SessionModeState restored | mode=%s ts=%s", mode.value, ts.isoformat())
        return state

    @classmethod
    def default(
        cls,
        persist_callback: Optional[Callable[[str], None]] = None,
    ) -> "SessionModeState":
        """创建默认 WORK 模式实例（新 session）。"""
        return cls(
            initial_mode     = AgentMode.WORK,
            trigger          = TriggerType.SESSION_INIT,
            reason           = "new session default",
            persist_callback = persist_callback,
        )

    # ── 调试 / 序列化 ─────────────────────────────────────────────────────────

    def summary(self) -> dict:
        """可序列化的状态摘要，用于日志、healthcheck、调试。"""
        with self._lock:
            return {
                "current_mode"         : self._mode.value,
                "automation_locked"    : self._automation_locked,
                "last_trigger"         : self._last_trigger.value,
                "last_reason"          : self._last_reason,
                "last_switch_ts"       : self._last_switch_ts.isoformat(),
                "seconds_since_switch" : round(self.seconds_since_last_switch(), 1),
                "recent_routes"        : [r.value for r in self._recent_routes],
                "has_technical_context": self.has_recent_technical_context(),
                "technical_ratio"      : round(self.recent_technical_ratio(), 2),
                "switch_count"         : len(self._switch_history),
            }

    def __repr__(self) -> str:
        with self._lock:
            lock_flag = " [LOCKED]" if self._automation_locked else ""
            return (
                f"<SessionModeState "
                f"mode={self._mode.value}{lock_flag} "
                f"trigger={self._last_trigger.value}>"
            )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# persist_callback 工厂 — MEMORY.md 写入
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def make_mode_persist_callback(memories_dir: str) -> Callable[[str], None]:
    """
    构建 persist_callback：将 [mode_state] 条目写入 MEMORY.md。

    策略：读 MEMORY.md → 正则匹配 [mode_state] 行 → 替换 / 追加 → 原子写回。
    MEMORY.md 不存在时创建。并发写入冲突静默降级。

    Args:
        memories_dir: MEMORY.md 所在目录（通常 HERMES_HOME/memories）

    Returns:
        Callable[[str], None] — 传给 SessionModeState(persist_callback=...)
    """
    import os as _os
    import tempfile as _tempfile

    _memory_path = _os.path.join(memories_dir, "MEMORY.md")

    def _persist(entry: str) -> None:
        # 读取现有内容
        try:
            with open(_memory_path, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            content = ""

        # 替换或追加 [mode_state] 行
        if _MEMORY_RE.search(content):
            new_content = _MEMORY_RE.sub(entry.strip(), content)
        else:
            # 追加到末尾（前面加 § 分隔）
            if content and not content.endswith("\n"):
                content += "\n"
            new_content = content + "\n§\n" + entry.strip() + "\n"

        # 原子写入（写临时文件 + rename）
        try:
            _os.makedirs(_os.path.dirname(_memory_path), exist_ok=True)
            fd, tmp = _tempfile.mkstemp(
                dir=_os.path.dirname(_memory_path),
                prefix=".memory_tmp_",
                suffix=".md",
            )
            with _os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(new_content)
            _os.replace(tmp, _memory_path)
        except Exception as exc:
            logger.warning("Mode state persist write failed (non-fatal): %s", exc)
            try:
                _os.unlink(tmp)
            except Exception:
                pass

    return _persist
