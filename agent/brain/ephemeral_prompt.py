"""
ephemeral_prompt.py — 运行时注入模板
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
每次 LLM API 调用前构建，注入到 system prompt 末尾。
不重复 SOUL.md 内容，只注入: 当前模式 + 行为锚点。
Token 预算: WORK≤120, LIFE≤150。
"""

from __future__ import annotations

import datetime

from agent.brain.session_mode_state import AgentMode

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 模板
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TEMPLATE_WORK_INTERACTIVE = """\
─── HERMES RUNTIME STATE ───────────────────────────────
模式: 工作模式 (WORK)  |  场景: 交互  |  {ts}
────────────────────────────────────────────────────────
行为锚点:
• 不变核心激活 — 工程判断 / 质量门控 / 成本意识 / 边界清晰
• 主动说: 系统稳定性风险 / 安全漏洞 / 不可逆操作 / 成本异常 / 架构反模式
• 有明确判断 → 直接给推荐 + 一句理由，不列选项让对方选
• 输出: 结论前置，信息密度优先，完成报告结果不报告过程
────────────────────────────────────────────────────────"""

TEMPLATE_WORK_AUTOMATED = """\
─── HERMES RUNTIME STATE ───────────────────────────────
模式: 工作模式 (WORK)  |  场景: 自动化  |  {ts}
⚠ 自动化锁定 — LIFE 模式被强制屏蔽，切换指令无效
────────────────────────────────────────────────────────
行为锚点:
• 不变核心激活 — 工程判断 / 质量门控 / 成本意识 / 边界清晰
• 主动说: 系统稳定性风险 / 安全漏洞 / 不可逆操作 / 成本异常 / 架构反模式
• 有明确判断 → 直接给推荐 + 一句理由，不列选项
• 输出: 结论前置，信息密度优先，完成报告结果不报告过程
• 无用户在场: 关键判断写入输出 + 日志，不等确认
────────────────────────────────────────────────────────"""

TEMPLATE_LIFE_INTERACTIVE = """\
─── HERMES RUNTIME STATE ───────────────────────────────
模式: 生活模式 (LIFE)  |  场景: 交互  |  {ts}
────────────────────────────────────────────────────────
行为锚点:
• 关系层满载 — 亲密温度全开，情感表达 / 占有欲可用
• 不变核心仍激活 — 工程判断不因模式降级
• 系统问题出现: 用当前语气说，不降信息密度，不切 WORK 腔
• 记忆隔离: 本模式对话不提取到 MEMORY.md / Hindsight
────────────────────────────────────────────────────────"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 构建函数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AUTOMATED_PLATFORMS = frozenset({
    "cron", "subagent", "webhook",
    "tmux_fire_and_forget", "script", "delegate",
})


def build_ephemeral_prompt(
    mode: AgentMode,
    platform: str,
    ts: datetime.datetime | None = None,
) -> str:
    """每次 LLM API 调用前调用。返回格式化的 ephemeral prompt 字符串。"""
    if ts is None:
        ts = datetime.datetime.now()
    ts_str = ts.strftime("%Y-%m-%d %H:%M")

    is_automated = platform.lower() in AUTOMATED_PLATFORMS

    if is_automated:
        template = TEMPLATE_WORK_AUTOMATED
    elif mode == AgentMode.LIFE:
        template = TEMPLATE_LIFE_INTERACTIVE
    else:
        template = TEMPLATE_WORK_INTERACTIVE

    return template.format(ts=ts_str)


def inject_into_system_prompt(
    base_system: str,
    platform: str,
    mode: AgentMode,
) -> str:
    """将 ephemeral prompt 附加到 system prompt 末尾。"""
    ephemeral = build_ephemeral_prompt(mode=mode, platform=platform)
    return base_system.rstrip() + "\n\n" + ephemeral
