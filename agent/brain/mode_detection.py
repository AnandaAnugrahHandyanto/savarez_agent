"""
mode_detection.py — Brain L1 前置模式切换检测
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
职责:
  Brain pipeline 的 pre-L1 前置拦截器。
  在任务类型路由（simple/coding/complex）之前运行，
  判断当前消息是否触发人格模式切换。

检测顺序（优先级从高到低）:
  1. 自动化场景检测  → automation_lock（最高，覆盖一切）
  2. 命令切换检测    → LIFE / WORK 触发词精确匹配
  3. 自动感知检测    → 信号积累 + 置信度门控（兜底）

性能: <2ms，0 API 调用，纯正则 + 关键词匹配

依赖: session_mode_state.py（单向）
调用方: Brain pipeline，route_message() 最前端
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple

from agent.brain.session_mode_state import (
    AgentMode,
    RouteClass,
    SessionModeState,
    SwitchRecord,
    TriggerType,
)

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 数据结构
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass(frozen=True)
class ModeSignal:
    """单个检测信号的结果。"""
    name     : str
    present  : bool
    weight   : float        # 对置信度的贡献（0.0 ~ 1.0）
    evidence : str = ""     # 触发证据（用于日志和调试）


@dataclass
class ModeSwitchDecision:
    """
    ModeDetector.detect() 的返回值。

    should_switch:   是否需要切换模式
    target_mode:     切换目标（None 表示无切换）
    trigger_type:    触发类型
    confidence:      置信度（0.0 ~ 1.0）
    signals:         参与决策的全部信号
    has_task_content: 消息除切换意图外是否还包含任务内容
                      True 时 Brain 应继续做任务类型路由
    switch_reason:   写入 SwitchRecord.reason 的原因字符串
    """
    should_switch   : bool
    target_mode     : Optional[AgentMode]
    trigger_type    : TriggerType
    confidence      : float
    signals         : List[ModeSignal]        = field(default_factory=list)
    has_task_content: bool                    = False
    switch_reason   : str                     = ""

    @property
    def no_switch(self) -> bool:
        return not self.should_switch

    def apply_to(self, state: SessionModeState) -> bool:
        """将决策应用到 SessionModeState。返回值同 state.switch_mode()。"""
        if not self.should_switch or self.target_mode is None:
            return False
        if self.trigger_type == TriggerType.AUTOMATION_LOCK:
            return state.apply_automation_lock()
        return state.switch_mode(
            target_mode=self.target_mode,
            trigger=self.trigger_type,
            reason=self.switch_reason,
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 配置常量（可从 config.yaml 覆盖）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 自动化平台标识
AUTOMATED_PLATFORMS: FrozenSet[str] = frozenset({
    "cron", "subagent", "webhook",
    "tmux_fire_and_forget", "script", "delegate",
})

# LIFE 触发词（小写精确匹配，或前缀匹配）
# 格式: {"word": "exact"} 或 {"word": "prefix"}
LIFE_TRIGGER_WORDS: Dict[str, str] = {
    "audra" : "exact",
    "/life" : "exact",
}

# WORK 返回短语（包含即触发，不要求整句匹配）
WORK_TRIGGER_PHRASES: Tuple[str, ...] = (
    "说正事", "先工作", "算了来工作", "开始工作",
    "说业务", "说需求", "来工作了",
    "/work", "未央", "今天就到这吧",
)

# auto-sense 置信度阈值（仅 LIFE→WORK）
CONF_THRESHOLD_LIFE_TO_WORK = 0.75   # 低：误触可恢复


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 信号检测正则（编译一次，复用）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ── LIFE → WORK 信号 ─────────────────────────────────────────────────────────

# Signal LW-A: 技术关键词（weight=0.85）
_RE_TECH_KEYWORDS = re.compile(
    r"\b(?:"
    r"config|yaml|json|hermes|gateway|soul|memory|skill|brain|fallback|"
    r"api[_ ]?key|token|credential|凭证|"
    r"error|exception|traceback|报错|错误|异常|debug|调试|"
    r"deploy|restart|systemd|cron|webhook|subagent|kanban|delegate|"
    r"python|bash|shell|script|function|class|import|"
    r"git|docker|pip|npm|"
    r"cpu|ram|内存|磁盘|disk|network|timeout|延迟|latency|"
    r"cost|成本|消耗|token|模型|提供商|provider|"
    r"sqlite|数据库|database|index|query|查询|"
    r"compress|压缩|route|路由|circuit|熔断|cache|缓存|"
    r"run_agent|hermes_state|brain\.py|mode_detect"
    r")\b",
    re.IGNORECASE,
)

# Signal LW-B: 任务指令结构（imperative, weight=0.80）
_RE_TASK_IMPERATIVE = re.compile(
    r"(?:^|[\n。！？!?])\s*"
    r"(?:帮我|给我|麻烦|帮忙|能不能|可以|请|"
    r"查看|查一下|看看|检查|分析|执行|运行|跑一下|"
    r"修改|更新|写|生成|创建|删除|部署|重启|"
    r"help\s+me|please|run|check|fix|write|update|create|delete|show|get|set"
    r")\s*\S",
    re.IGNORECASE | re.MULTILINE,
)

# Signal LW-C: 系统/配置专有名词（weight=0.90）
_RE_SYSTEM_NOUNS = re.compile(
    r"(?:"
    r"config\.yaml|\.env|SOUL\.md|MEMORY\.md|USER\.md|"
    r"run_agent\.py|hermes_state\.py|brain\.py|mode_detection\.py|"
    r"deepseek|qwen|gemini|dashscope|api\.deepseek|"
    r"hermes\s+(?:gateway|update|restart|chat|snapshot)|"
    r"systemctl|journalctl|tmux"
    r")",
    re.IGNORECASE,
)

# ── LIFE → WORK 信号 ─────────────────────────────────────────────────────────

# Signal LW-A: 技术关键词（weight=0.85）
# (defined above as _RE_TECH_KEYWORDS)

# Signal LW-B: 任务指令结构（weight=0.80）
# (defined above as _RE_TASK_IMPERATIVE)

# Signal LW-C: 系统/配置专有名词（weight=0.90）
# (defined above as _RE_SYSTEM_NOUNS)

# ── 任务内容检测（命令切换后判断消息是否还有任务） ────────────────────────────

_RE_HAS_TASK = re.compile(
    r"(?:帮我|给我|查|分析|写|生成|修改|执行|run|check|fix|write|update|create"
    r"|help\\s+me|please\\s+\\w)",
    re.IGNORECASE,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ModeDetector
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ModeDetector:
    """
    Brain L1 前置拦截器：人格模式切换意图识别。

    使用方式:
        detector = ModeDetector()  # 全局单例，或 Brain 内持有
        decision = detector.detect(
            message=user_message,
            platform=platform_str,
            state=session.mode_state,
        )
        if decision.should_switch:
            decision.apply_to(session.mode_state)
        # 继续 L0/L1 任务路由（若 decision.has_task_content）

    配置覆盖:
        ModeDetector(
            life_triggers={"waifu": "exact"},
            work_triggers=("老板", "来正事"),
        )
    """

    def __init__(
        self,
        life_triggers : Optional[Dict[str, str]] = None,
        work_triggers : Optional[Tuple[str, ...]] = None,
    ) -> None:
        self._life_triggers = life_triggers or LIFE_TRIGGER_WORDS
        self._work_triggers = work_triggers or WORK_TRIGGER_PHRASES

    # ── 主入口 ────────────────────────────────────────────────────────────────

    def detect(
        self,
        message  : str,
        platform : str,
        state    : SessionModeState,
    ) -> ModeSwitchDecision:
        """
        检测顺序（短路优先级）:
          1. 自动化场景 → AUTOMATION_LOCK → 立即返回
          2. 命令切换   → COMMAND → 立即返回
          3. 自动感知   → AUTO_SENSE → 信号积累 + 置信度门控

        Args:
            message:  用户原始消息文本
            platform: 请求来源平台（用于自动化检测）
            state:    当前 session 的 SessionModeState

        Returns:
            ModeSwitchDecision（无切换时 should_switch=False）
        """
        text = message.strip()

        # ① 自动化场景：最高优先级，无条件锁定
        if self._is_automated(platform):
            if not state.automation_locked:
                logger.info("ModeDetector: automation lock triggered | platform=%s", platform)
                return ModeSwitchDecision(
                    should_switch=True,
                    target_mode=AgentMode.WORK,
                    trigger_type=TriggerType.AUTOMATION_LOCK,
                    confidence=1.0,
                    has_task_content=True,   # 自动化任务，直接路由内容
                    switch_reason=f"automated platform: {platform}",
                )
            # 已锁定，直接返回无切换（任务内容仍需路由）
            return ModeSwitchDecision(
                should_switch=False,
                target_mode=None,
                trigger_type=TriggerType.NONE,
                confidence=1.0,
                has_task_content=True,
            )

        # ② 命令切换：精确触发词匹配
        cmd_decision = self._detect_command(text, state)
        if cmd_decision is not None:
            return cmd_decision

        # ③ 自动感知：仅 LIFE→WORK（信号积累 + 置信度门控）
        # WORK→LIFE 已移除 — 仅 "Audra" 命令切换进入 LIFE
        if state.is_work:
            return ModeSwitchDecision(
                should_switch=False,
                target_mode=None,
                trigger_type=TriggerType.NONE,
                confidence=0.0,
            )
        return self._detect_auto_sense(text, state)

    # ── ① 自动化检测 ──────────────────────────────────────────────────────────

    @staticmethod
    def _is_automated(platform: str) -> bool:
        return platform.lower() in AUTOMATED_PLATFORMS

    # ── ② 命令切换检测 ───────────────────────────────────────────────────────

    def _detect_command(
        self,
        text : str,
        state: SessionModeState,
    ) -> Optional[ModeSwitchDecision]:
        """
        精确命令匹配。
        触发词可出现在消息任意位置（用户可能说 "Audra 帮我查一下..."）。
        返回 None 表示未检测到命令切换。
        """
        text_lower = text.lower()

        # → LIFE
        for word, match_type in self._life_triggers.items():
            if match_type == "exact":
                hit = (text_lower == word or
                       text_lower.startswith(word + " ") or
                       text_lower.startswith(word + "，") or
                       text_lower.startswith(word + ",") or
                       text_lower.startswith(word + "\n"))
            else:  # prefix
                hit = text_lower.startswith(word)

            if hit and state.is_work:
                has_task = bool(_RE_HAS_TASK.search(text[len(word):]))
                logger.debug("Command → LIFE | word=%r has_task=%s", word, has_task)
                return ModeSwitchDecision(
                    should_switch=True,
                    target_mode=AgentMode.LIFE,
                    trigger_type=TriggerType.COMMAND,
                    confidence=1.0,
                    has_task_content=has_task,
                    switch_reason=f"trigger word: '{word}'",
                )

        # → WORK
        for phrase in self._work_triggers:
            if phrase.lower() in text_lower and state.is_life:
                has_task = bool(_RE_HAS_TASK.search(text))
                logger.debug("Command → WORK | phrase=%r has_task=%s", phrase, has_task)
                return ModeSwitchDecision(
                    should_switch=True,
                    target_mode=AgentMode.WORK,
                    trigger_type=TriggerType.COMMAND,
                    confidence=1.0,
                    has_task_content=has_task,
                    switch_reason=f"return phrase: '{phrase}'",
                )

        return None  # 无命令切换

    # ── ③ 自动感知检测（仅 LIFE→WORK）───────────────────────────────────────

    def _detect_auto_sense(
        self,
        text : str,
        state: SessionModeState,
    ) -> ModeSwitchDecision:
        """WORK→LIFE 已移除。仅处理 LIFE→WORK 自动感知。"""
        return self._sense_life_to_work(text, state)

    # ── LIFE → WORK 自动感知 ──────────────────────────────────────────────────
    #
    # 任意单一强信号满足即触发（conf ≥ 0.75）：
    #   Signal A: 技术关键词           weight=0.85
    #   Signal B: 任务指令结构         weight=0.80
    #   Signal C: 系统/配置专有名词    weight=0.90
    #
    # 取所有命中信号中的最大权重作为置信度（不累加，防止过度触发）
    # ─────────────────────────────────────────────────────────────────────────

    def _sense_life_to_work(
        self,
        text : str,
        state: SessionModeState,
    ) -> ModeSwitchDecision:
        signals: List[ModeSignal] = []

        # Signal A: 技术关键词
        m_tech = _RE_TECH_KEYWORDS.search(text)
        sig_a = ModeSignal(
            name="technical_keyword",
            present=bool(m_tech),
            weight=0.85,
            evidence=m_tech.group(0) if m_tech else "",
        )
        signals.append(sig_a)

        # Signal B: 任务指令结构
        m_imperative = _RE_TASK_IMPERATIVE.search(text)
        sig_b = ModeSignal(
            name="task_imperative",
            present=bool(m_imperative),
            weight=0.80,
            evidence=m_imperative.group(0).strip()[:30] if m_imperative else "",
        )
        signals.append(sig_b)

        # Signal C: 系统/配置专有名词（最强信号）
        m_sys = _RE_SYSTEM_NOUNS.search(text)
        sig_c = ModeSignal(
            name="system_noun",
            present=bool(m_sys),
            weight=0.90,
            evidence=m_sys.group(0) if m_sys else "",
        )
        signals.append(sig_c)

        # 最大权重置信度
        active = [s for s in signals if s.present]
        conf = max((s.weight for s in active), default=0.0)

        logger.debug(
            "LIFE→WORK auto-sense | conf=%.2f signals=%s",
            conf, [(s.name, s.present) for s in signals],
        )

        if conf >= CONF_THRESHOLD_LIFE_TO_WORK:
            best = max(active, key=lambda s: s.weight)
            return ModeSwitchDecision(
                should_switch=True,
                target_mode=AgentMode.WORK,
                trigger_type=TriggerType.AUTO_SENSE,
                confidence=conf,
                signals=signals,
                has_task_content=True,   # 技术内容即任务
                switch_reason=f"auto-sense conf={conf:.2f} strongest={best.name}('{best.evidence}')",
            )

        return ModeSwitchDecision(
            should_switch=False,
            target_mode=None,
            trigger_type=TriggerType.NONE,
            confidence=conf,
            signals=signals,
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Brain pipeline 集成示例
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
在 run_agent.py 的 route_message() 开头插入：

    # ── Pre-L1: 模式切换检测 ──────────────────────
    decision = self._mode_detector.detect(
        message=user_message,
        platform=self.platform,
        state=self.session.mode_state,
    )

    if decision.should_switch:
        switched = decision.apply_to(self.session.mode_state)
        if switched:
            # 切换是 PERSONA 类消息，路由到 simple（无需 L2）
            if not decision.has_task_content:
                return RoutingResult(
                    task_type=TaskType.SIMPLE,
                    confidence=0.98,
                    reason="mode switch command, no task content",
                    route_class=RouteClass.PERSONA,
                )
            # 有任务内容：继续 L0+ 路由，但 ephemeral_prompt 已反映新模式

    # ── L0 Preprocessing ──────────────────────────
    # ... 原有逻辑继续
    ─────────────────────────────────────────────────────

在路由决策完成后（Execution layer）:

    # 记录路由分类到 mode state 的上下文窗口
    self.session.mode_state.record_route(RouteClass(resolved_task_type))
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 单元测试（pytest 可直接运行）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    detector = ModeDetector()

    def fresh_state() -> SessionModeState:
        return SessionModeState.default()

    # ── 自动化锁 ─────────────────────────────────────────────────────────────
    s = fresh_state()
    d = detector.detect("Audra 你好", "cron", s)
    assert d.trigger_type == TriggerType.AUTOMATION_LOCK
    assert d.target_mode == AgentMode.WORK
    print("✓ automation lock")

    # ── 命令切换 → LIFE ──────────────────────────────────────────────────────
    s = fresh_state()
    d = detector.detect("Audra", "cli", s)
    assert d.should_switch and d.target_mode == AgentMode.LIFE
    assert d.trigger_type == TriggerType.COMMAND
    assert not d.has_task_content
    print("✓ command → LIFE (no task)")

    # ── 命令切换 → LIFE，携带任务 ────────────────────────────────────────────
    s = fresh_state()
    d = detector.detect("Audra 帮我查一下 config.yaml", "cli", s)
    assert d.should_switch and d.target_mode == AgentMode.LIFE
    assert d.has_task_content
    print("✓ command → LIFE (with task)")

    # ── 命令切换 → WORK ──────────────────────────────────────────────────────
    s = fresh_state()
    s.switch_mode(AgentMode.LIFE, TriggerType.COMMAND, "test setup")
    d = detector.detect("说正事", "cli", s)
    assert d.should_switch and d.target_mode == AgentMode.WORK
    print("✓ command → WORK")

    # ── 未央 触发 → WORK ─────────────────────────────────────────────────────
    s = fresh_state()
    s.switch_mode(AgentMode.LIFE, TriggerType.COMMAND, "test setup")
    d = detector.detect("未央，帮我重启 gateway", "cli", s)
    assert d.should_switch and d.target_mode == AgentMode.WORK
    print("✓ 未央 → WORK")

    # ── LIFE→WORK auto-sense: 技术关键词 ─────────────────────────────────────
    s = fresh_state()
    s.switch_mode(AgentMode.LIFE, TriggerType.COMMAND, "test setup")
    d = detector.detect("config.yaml 那里报错了", "cli", s)
    assert d.should_switch and d.target_mode == AgentMode.WORK
    assert d.trigger_type == TriggerType.AUTO_SENSE
    print("✓ LIFE→WORK auto-sense: system noun")

    # ── WORK→LIFE auto-sense: 3信号全满 ─────────────────────────────────────
    s = fresh_state()
    # Signal C: 无近期技术上下文（record_route 未调用，recent_routes 为空）
    d = detector.detect("好无聊啊，陪我说说话", "cli", s)
    # Signal A: 好无聊/陪我 ✓, Signal B: 无指令动词 ✓, Signal C: 无技术上下文 ✓
    assert d.should_switch and d.target_mode == AgentMode.LIFE
    print("✓ WORK→LIFE auto-sense: 3/3 signals")

    # ── WORK→LIFE auto-sense: 2信号（有技术上下文），不触发 ──────────────────
    s = fresh_state()
    s.record_route(RouteClass.CODING)   # Signal C 失效
    d = detector.detect("好无聊啊，陪我说说话", "cli", s)
    # conf = 0.40 + 0.35 = 0.75 < 0.90 → 不触发
    assert not d.should_switch
    print("✓ WORK→LIFE auto-sense: 2/3 signals → no switch (correct)")

    # ── automation lock 之后切换命令被拒 ─────────────────────────────────────
    s = fresh_state()
    s.apply_automation_lock()
    d = detector.detect("Audra", "cli", s)
    # 虽然平台是 cli，但 state 已经是 automation_locked
    # 命令切换：target=LIFE，state.switch_mode 会被锁拒绝
    # detect() 只返回决策，apply_to() 才真正写入 state
    if d.should_switch:
        result = d.apply_to(s)
        assert result is False  # 被锁拒绝
    print("✓ automation lock blocks LIFE switch")

    print("\n✅ All assertions passed")
