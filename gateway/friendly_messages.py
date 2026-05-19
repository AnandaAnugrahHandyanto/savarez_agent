"""Friendly user-facing message contracts for gateway system notices.

This module is intentionally small and dependency-light: gateway/runtime code can
call it from hot paths without pulling platform SDKs into the import graph.  It
keeps Hermes-owned system notices in one message contract instead of scattering
raw strings across adapters.
"""

from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Mapping, Sequence


ApprovalDecision = Literal["once", "session", "always", "deny"]

PLAIN_TABLE_DIVIDER = "────────────────────────────────────────"


RAW_ERROR_MARKERS = (
    "traceback",
    "runtimeerror",
    "httperror",
    "http 5",
    "http 429",
    "ret=-2",
    "errcode=-2",
    "last_status=",
    "same_tool_fail",
)

INTERNAL_ACTIVITY_MARKERS = (
    "receiving stream response",
    "iteration",
    "api_call_count",
    "max_iterations",
    "current_tool",
)


@dataclass(frozen=True)
class FriendlyPersona:
    """External identity used in user-facing friendly messages."""

    display_name: str = "Hermes"
    product_name: str = "Hermes"
    role_name: str = "随身执行伙伴"
    greeting: str = "我是「{display_name}」，你的随身执行伙伴 😊～"
    signature: str = "{display_name}"
    powered_by: str = "Hermes"
    show_powered_by: bool = False
    tone: str = "warm_friendly"

    def format(self, template: str) -> str:
        values = {
            "display_name": self.display_name,
            "product_name": self.product_name,
            "role_name": self.role_name,
            "signature": self.signature.format(display_name=self.display_name, product_name=self.product_name),
            "powered_by": self.powered_by,
        }
        try:
            return str(template).format(**values)
        except Exception:
            return str(template)

    def greeting_text(self) -> str:
        return self.format(self.greeting)


def get_persona(config: Mapping[str, Any] | None = None) -> FriendlyPersona:
    cfg = _load_friendly_config() if config is None else config
    persona_cfg = _persona_config(cfg)
    env_name = os.getenv("HERMES_FRIENDLY_DISPLAY_NAME") or os.getenv("HERMES_DISPLAY_NAME")
    display_name = _first_text(
        env_name,
        persona_cfg.get("display_name"),
        persona_cfg.get("name"),
        _mapping_get(cfg, "display_name"),
        "Hermes",
    )
    product_name = _first_text(persona_cfg.get("product_name"), "Hermes")
    role_name = _first_text(persona_cfg.get("role_name"), "随身执行伙伴")
    greeting = _first_text(
        persona_cfg.get("greeting"),
        "我是「{display_name}」，你的随身执行伙伴 😊～",
    )
    signature = _first_text(persona_cfg.get("signature"), "{display_name}")
    powered_by = _first_text(persona_cfg.get("powered_by"), product_name)
    tone = _first_text(persona_cfg.get("tone"), "warm_friendly")
    return FriendlyPersona(
        display_name=display_name,
        product_name=product_name,
        role_name=role_name,
        greeting=greeting,
        signature=signature,
        powered_by=powered_by,
        show_powered_by=_coerce_bool(persona_cfg.get("show_powered_by"), False),
        tone=tone,
    )


def render_welcome(config: Mapping[str, Any] | None = None) -> str:
    persona = get_persona(config)
    lines = [
        persona.greeting_text(),
        "",
        "你可以让我查资料、改代码、管文件、跑定时任务，也可以把微信、飞书、网页和本地工作串起来 ✨",
        "",
        "有什么要处理的，直接告诉我就行～",
    ]
    if persona.show_powered_by:
        lines.extend(["", f"由 {persona.powered_by} 驱动"])
    return "\n".join(lines)


def render_greeting(config: Mapping[str, Any] | None = None) -> str:
    persona = get_persona(config)
    return "\n".join(
        [
            f"我在，{persona.display_name}在线 😊～",
            "",
            "有什么要处理的，直接告诉我就行 ✨",
        ]
    )


def render_ack(config: Mapping[str, Any] | None = None) -> str:
    persona = get_persona(config)
    return f"收到，{persona.display_name}来处理 😊"


def render_starting(action: str = "先看一下当前状态", config: Mapping[str, Any] | None = None) -> str:
    get_persona(config)
    return f"我来处理，{_sanitize_user_visible(action)} 🔎"


def render_simple_done(next_step: str | None = None) -> str:
    lines = ["处理好了 🌿"]
    if next_step:
        lines.extend(["", _sanitize_user_visible(next_step)])
    else:
        lines.extend(["", "你可以继续说下一步要做什么 ✨"])
    return "\n".join(lines)


def render_simple_failure(reason: str | None = None) -> str:
    lines = ["这轮没跑完 ⚠️", "", "我已经把细节留在本地记录里，不会在微信里堆报错。"]
    if reason:
        lines.extend(["", f"原因｜{_sanitize_user_visible(reason)}"])
    lines.extend(["", "你可以让我重试，或调整目标后再跑一次 ✨"])
    return "\n".join(lines)


def render_capabilities(config: Mapping[str, Any] | None = None) -> str:
    persona = get_persona(config)
    lines = [
        f"我是「{persona.display_name}」，我可以帮你做这些 😊～",
        "",
        "• 🔎 查天气、搜资料、整理信息",
        "• 💻 写代码、排查问题、修改项目",
        "• 📁 读文件、写文档、整理资料",
        "• 🌐 浏览网页、提取重点",
        "• ⏰ 设置提醒、执行定时任务",
        "• 💬 处理微信、飞书等消息通知",
        "• 🧠 记住你的偏好，跨场景接着做事",
        "",
        "你可以直接说目标，不用按固定格式提问 ✨",
    ]
    if persona.show_powered_by:
        lines.extend(["", f"由 {persona.powered_by} 驱动"])
    return "\n".join(lines)


def render_persona_reply(text: str, config: Mapping[str, Any] | None = None) -> str | None:
    normalized = _normalize_persona_query(text)
    persona = get_persona(config)
    greeting_queries = {
        "你好",
        "您好",
        "hi",
        "hello",
        "hey",
        "哈喽",
        "哈啰",
        "在吗",
        "在不在",
        "你在吗",
        "有人吗",
        "我来了",
        persona.display_name.lower(),
    }
    identity_queries = {
        "你是谁",
        "你是谁呀",
        "你是谁啊",
        "你叫什么",
        "你叫啥",
        "介绍一下自己",
        "自我介绍",
        "你是什么",
    }
    capability_queries = {
        "你能干嘛",
        "你能干什么",
        "你能做什么",
        "你会什么",
        "你有什么能力",
        "你有什么功能",
        "能干嘛",
        "能做什么",
    }
    if normalized in greeting_queries:
        return render_greeting(config)
    if normalized in identity_queries:
        return render_welcome(config)
    if normalized in capability_queries:
        return render_capabilities(config)
    return None


def render_digest_report(
    title: str,
    *,
    headline: str | None = None,
    sections: Sequence[Mapping[str, Any]] | None = None,
    next_step: str | None = None,
) -> str:
    lines = [_sanitize_user_visible(title).strip()]
    if headline:
        lines.extend(["", _sanitize_user_visible(headline).strip()])
    for section in sections or ():
        rendered = _render_digest_section(section)
        if rendered:
            lines.extend(["", rendered])
    if next_step:
        lines.extend(["", "🧭 下一步", _sanitize_user_visible(next_step).strip()])
    return "\n".join(line.rstrip() for line in lines if line is not None).strip()


def render_plain_table(
    headers: Sequence[Any],
    rows: Sequence[Sequence[Any]],
    *,
    divider: str = PLAIN_TABLE_DIVIDER,
) -> str:
    columns = [str(header or "") for header in headers]
    table_rows = [[str(cell or "") for cell in row] for row in rows]
    widths: list[int] = []
    for index, header in enumerate(columns):
        values = [header]
        values.extend(row[index] if index < len(row) else "" for row in table_rows)
        widths.append(max(_display_width(value) for value in values))
    rendered = [_format_table_row(columns, widths), divider]
    rendered.extend(_format_table_row(row, widths) for row in table_rows)
    rendered.append(divider)
    return "\n".join(rendered)


def render_pairing_code(platform_name: str, code: str) -> str:
    return friendly_card(
        "🧭 需要完成配对｜我还不认识这个账号",
        action="已生成一次性配对码",
        result=f"配对码｜{code}",
        impact="通过前不会处理这个账号发来的指令",
        boundary=f"只用于 {platform_name or '当前平台'} 当前账号的授权绑定",
        next_step=f"请让管理员运行：hermes pairing approve {platform_name} {code}",
    )


def render_pairing_rate_limited() -> str:
    return friendly_card(
        "⚠️ 配对请求过于频繁｜请稍后再试",
        action="已暂时停止生成新的配对码",
        result="本次请求没有创建新授权",
        impact="避免陌生账号反复触发提醒",
        boundary="只影响当前配对入口，已授权用户不受影响",
        next_step="请稍等一会儿再发送消息。",
    )


def render_unknown_command(command: str) -> str:
    command = str(command or "").strip().lstrip("/") or "unknown"
    return friendly_card(
        f"🧭 没找到这个命令｜/{command}",
        action="已拦截未知斜杠命令",
        result="没有把它当作普通聊天交给模型处理",
        impact="避免误触发不存在的工具或流程",
        boundary="只检查当前网关已注册的命令和技能",
        next_step="发送 /commands 查看可用命令；如果想当普通消息发送，请去掉开头的 /。",
    )


def render_telegram_topic_root_lobby() -> str:
    return friendly_card(
        "🧭 这里是 Telegram 主入口｜当前只处理系统命令",
        action="已保留主入口用于管理命令",
        result="没有在这里开启新的对话会话",
        impact="避免多个并行会话混在同一个主聊天里",
        boundary="每个话题会作为独立 Hermes 会话运行",
        next_step="请打开顶部的 All Messages 话题并发送任意消息，Telegram 会为你创建新的独立话题。",
    )


def render_telegram_topic_root_new() -> str:
    return friendly_card(
        "🧭 请从 All Messages 开启并行会话",
        action="没有在主入口直接创建并行会话",
        result="当前主入口仍只保留系统命令能力",
        impact="避免误替换或混淆已有话题会话",
        boundary="/new 在已有话题内只会重置当前话题",
        next_step="请打开顶部的 All Messages 话题并发送任意消息来创建新的并行会话。",
    )


def render_telegram_topic_new_header() -> str:
    return (
        "🌿 已在当前话题开启新会话\n\n"
        "提示｜如果要并行处理另一件事，请打开 All Messages 并发送新消息；每个话题都是独立会话。"
    )


@dataclass(frozen=True)
class FriendlyCard:
    """Canonical text-card contract used by gateway system notices."""

    title: str
    action: str
    result: str
    impact: str
    boundary: str
    next_step: str
    extra_status: tuple[str, ...] = field(default_factory=tuple)
    next_heading: str = "【下一步】"

    def render(self) -> str:
        lines = [
            _sanitize_user_visible(self.title),
            "",
            "【状态】",
            f"动作｜{_sanitize_user_visible(self.action)}",
            f"结果｜{_sanitize_user_visible(self.result)}",
            f"影响｜{_sanitize_user_visible(self.impact)}",
            f"边界｜{_sanitize_user_visible(self.boundary)}",
        ]
        lines.extend(_sanitize_user_visible(line) for line in self.extra_status if line)
        lines.extend(["", self.next_heading, _sanitize_user_visible(self.next_step)])
        return "\n".join(lines)


def friendly_card(
    title: str,
    *,
    action: str,
    result: str,
    impact: str,
    boundary: str,
    next_step: str,
    extra_status: Iterable[str] | None = None,
    next_heading: str = "【下一步】",
) -> str:
    return FriendlyCard(
        title=title,
        action=action,
        result=result,
        impact=impact,
        boundary=boundary,
        next_step=next_step,
        extra_status=tuple(extra_status or ()),
        next_heading=next_heading,
    ).render()


def render_cron_result(job_name: str, content: str) -> str:
    return friendly_card(
        f"🌿 定时任务已完成｜{job_name}",
        action="已完成本轮自动执行并发送结果",
        result=_compact_message_preview(content),
        impact="这是定时任务结果，不会附带内部任务编号或英文管理说明",
        boundary="完整输出已保存在本地任务记录；聊天里只保留可读摘要",
        next_step="如果需要调整、暂停或删除任务，直接告诉我你的操作意图就行～ ✨",
    )


def render_cron_failure(job_name: str, error: str | None) -> str:
    error_text = str(error or "任务未返回可展示结果")
    safe_result = "任务没有完成，已停止继续重试。"
    if "blocked" in error_text.lower() or "injection" in error_text.lower():
        safe_result = "任务触发安全保护，已停止执行。"
    elif "timeout" in error_text.lower() or "timed out" in error_text.lower():
        safe_result = "任务执行超时，已保留现场。"
    return friendly_card(
        f"⚠️ 这轮任务没跑完｜{job_name}",
        action="已记录失败并停止本轮自动补发",
        result=safe_result,
        impact="不会把原始异常直接发到聊天里，也不会因为告警刷屏延长限流",
        boundary="详细堆栈、HTTP 状态和命令输出只保存在本地输出文件",
        next_step="我会在下一次调度周期重新执行；如果连续失败，你可以让我查看最近一次输出。",
    )


def render_background_result(prompt: str, content: str | None) -> str:
    return friendly_card(
        "🌿 后台任务已完成",
        action="已完成这次后台执行",
        result=_compact_message_preview(content or "没有返回可展示内容。"),
        impact="不会打断当前会话，也不会重复发送内部执行细节",
        boundary="完整过程保存在本地记录；聊天里只保留可读结果",
        next_step="如果要继续处理这个结果，直接接着说你的下一步要求就行～ ✨",
        extra_status=(f"任务｜{command_preview(prompt, 120)}",) if str(prompt or "").strip() else (),
    )


def render_background_failure(task_id: str, error: str | None) -> str:
    return friendly_card(
        f"⚠️ 后台任务没跑完｜{task_id or '未命名任务'}",
        action="已停止这次后台执行",
        result=_sanitize_user_visible(error or "任务暂时没有完成"),
        impact="不会继续刷屏，也不会把原始堆栈反复发到聊天里",
        boundary="详细错误只保存在本地日志和任务记录",
        next_step="你可以让我重试，或调整任务目标后重新发起 ✨",
    )


def render_update_result(success: bool, output: str | None = None, exit_code: int | None = None) -> str:
    if success:
        return friendly_card(
            "🌿 Hermes 更新已完成",
            action="已完成更新流程",
            result=_compact_message_preview(output or "更新成功，当前服务会继续恢复运行。"),
            impact="后续消息会使用更新后的运行时处理",
            boundary="完整更新输出保存在本地日志；聊天里只保留摘要",
            next_step="你可以继续发消息，我会按新的运行时接着处理 ✨",
        )
    code_text = f"退出码 {exit_code}" if exit_code is not None else "更新流程返回失败"
    return friendly_card(
        "⚠️ Hermes 更新没完成",
        action="已停止本轮更新流程",
        result=_sanitize_user_visible(output or code_text),
        impact="当前服务会继续使用更新前的可用状态",
        boundary="详细输出已保存在本地日志，不会把原始堆栈直接发到聊天里",
        next_step="可以稍后重试，或运行 hermes update 查看本地详情。",
    )


def _compact_message_preview(content: str, limit: int = 1200) -> str:
    rendered = str(content or "").strip()
    if not rendered:
        return "任务已完成，但没有返回可展示内容。"
    if len(rendered) <= limit:
        return rendered
    return rendered[: max(0, limit - 3)].rstrip() + "..."


def _load_friendly_config() -> Mapping[str, Any]:
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        return cfg if isinstance(cfg, Mapping) else {}
    except Exception:
        return {}


def _persona_config(config: Mapping[str, Any]) -> Mapping[str, Any]:
    friendly = _mapping_get(config, "friendly")
    if isinstance(friendly, Mapping):
        persona = _mapping_get(friendly, "persona")
        if isinstance(persona, Mapping):
            return persona
    persona = _mapping_get(config, "persona")
    if isinstance(persona, Mapping):
        return persona
    return {}


def _mapping_get(config: Mapping[str, Any] | None, key: str) -> Any:
    if isinstance(config, Mapping):
        return config.get(key)
    return None


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def _normalize_persona_query(text: str) -> str:
    normalized = str(text or "").strip().lower()
    normalized = re.sub(r"^[`'\"“”‘’\s]+|[`'\"“”‘’\s]+$", "", normalized)
    normalized = re.sub(r"[？?。.!！～~\s]+$", "", normalized)
    normalized = re.sub(r"\s+", "", normalized)
    return normalized


def _render_digest_section(section: Mapping[str, Any]) -> str:
    title = _first_text(section.get("title"))
    lines = [title] if title else []
    headers = section.get("headers")
    rows = section.get("rows")
    if isinstance(headers, Sequence) and not isinstance(headers, (str, bytes)):
        if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes)):
            row_values = [row for row in rows if isinstance(row, Sequence) and not isinstance(row, (str, bytes))]
            if row_values:
                lines.extend(["", render_plain_table(headers, row_values)] if lines else [render_plain_table(headers, row_values)])
    bullets = section.get("bullets")
    if isinstance(bullets, Sequence) and not isinstance(bullets, (str, bytes)):
        rendered_bullets = [f"• {_sanitize_user_visible(item)}" for item in bullets if str(item or "").strip()]
        if rendered_bullets:
            if lines:
                lines.append("")
            lines.extend(rendered_bullets)
    body = _first_text(section.get("body"))
    if body:
        if lines:
            lines.append("")
        lines.append(_sanitize_user_visible(body))
    return "\n".join(lines).strip()


def _display_width(value: Any) -> int:
    width = 0
    for char in str(value or ""):
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
    return width


def _pad_display(value: Any, width: int) -> str:
    text = str(value or "")
    return text + " " * max(0, width - _display_width(text))


def _format_table_row(row: Sequence[Any], widths: Sequence[int]) -> str:
    cells = []
    for index, width in enumerate(widths):
        cell = row[index] if index < len(row) else ""
        cells.append(_pad_display(cell, width))
    return "    ".join(cells).rstrip()


def _sanitize_user_visible(text: Any) -> str:
    rendered = str(text or "")
    lowered = rendered.lower()
    if any(marker in lowered for marker in RAW_ERROR_MARKERS):
        return "内部技术细节已转入本地诊断记录，这里只保留可操作信息。"
    for marker in INTERNAL_ACTIVITY_MARKERS:
        if marker in lowered:
            return _public_activity_label({"last_activity_desc": rendered})
    return rendered


def command_preview(command: str, limit: int = 1800) -> str:
    command = str(command or "").strip()
    if len(command) <= limit:
        return command
    return command[: max(0, limit - 3)].rstrip() + "..."


def approval_id(session_key: str, command: str) -> str:
    digest = hashlib.sha1(f"{session_key}\n{command}".encode("utf-8", "replace")).hexdigest()
    return f"gw-{digest[:12]}"


def approval_summary(command: str, session_key: str, description: str) -> dict[str, str]:
    return {
        "title": "🧯 命令需要审批",
        "risk_pill": "高风险",
        "risk": describe_approval_risk(description, command),
        "scope": infer_approval_scope(command, description),
        "command": command_preview(command),
        "approval_id": approval_id(session_key, command),
    }


def render_approval_request(command: str, session_key: str, description: str = "dangerous command") -> str:
    summary = approval_summary(command, session_key, description)
    return "\n".join(
        [
            f"{summary['title']}｜{summary['risk_pill']}",
            "",
            "我已暂停执行。确认前，这条命令不会运行。",
            "",
            "【判断信息】",
            f"风险｜{summary['risk']}",
            f"范围｜{summary['scope']}",
            "命令｜",
            "```",
            summary["command"],
            "```",
            f"审批 ID｜{summary['approval_id']}",
            "",
            "【可选操作】",
            "01｜批准本次",
            "02｜本会话允许",
            "03｜永久允许",
            "04｜拒绝",
            "",
            "【下一步】",
            "直接回复序号或文字：批准本次 / 本会话允许 / 永久允许 / 拒绝。",
        ]
    )


def render_approval_resolved(choice: ApprovalDecision, count: int = 1) -> str:
    if choice == "deny":
        return render_approval_denied(count)
    mode = {
        "once": "本次允许",
        "session": "本会话允许",
        "always": "永久允许",
    }.get(choice, "本次允许")
    return friendly_card(
        f"🌿 命令已批准｜{mode}",
        action="已放行等待中的命令",
        result="代理正在恢复执行",
        impact="只继续这次已确认的操作，不会额外启动新任务",
        boundary=(
            f"本次共处理 {count} 条待审批命令"
            if count > 1 else "仅处理当前这条待审批命令"
        ),
        next_step="请继续等待后续执行结果。",
    )


def render_approval_denied(count: int = 1) -> str:
    return friendly_card(
        "🧯 命令已拒绝｜不会执行",
        action="已取消等待中的危险命令",
        result="代理会收到拒绝结果并继续收口当前任务",
        impact="不会运行你刚刚拒绝的命令",
        boundary=(
            f"本次共拒绝 {count} 条待审批命令"
            if count > 1 else "仅拒绝当前这条待审批命令"
        ),
        next_step="你可以调整需求后重试，或发送 /reset 取消当前会话。",
    )


def render_no_pending_approval(action: str = "approve") -> str:
    verb = "批准" if action == "approve" else "拒绝"
    return friendly_card(
        f"ℹ️ 当前没有待{verb}的命令",
        action="没有发现正在等待的审批请求",
        result="无需处理，当前会话状态保持不变",
        impact="不会执行或取消任何命令",
        boundary="只检查当前聊天对应的会话",
        next_step="如果刚才的审批已过期，请让代理重新尝试该操作。",
    )


def describe_approval_risk(description: str, command: str = "") -> str:
    desc = (description or "").strip().lower()
    command_l = (command or "").lower()
    mappings = [
        (("recursive delete", "find -delete", "find -exec"), "删除文件或目录，可能造成不可恢复的数据丢失"),
        (("delete in root path",), "删除根路径内容，风险极高"),
        (("script execution via -e/-c flag", "script execution via heredoc"), "执行临时代码片段，需要你确认风险"),
        (("shell command via -c/-lc flag",), "通过 shell 执行拼接命令，需要你确认风险"),
        (("pipe remote content to shell", "execute remote script",), "下载并执行远程内容，存在供应链风险"),
        (("sudo", "privilege",), "涉及提权或敏感权限，需要人工确认"),
        (("git reset --hard", "git clean", "git branch force delete"), "可能删除或覆盖未提交改动"),
        (("git force push",), "会改写远端历史，可能影响协作者"),
        (("system service", "hermes gateway", "hermes update"), "会影响正在运行的系统或网关服务"),
        (("sql drop", "sql delete", "sql truncate"), "会修改或删除数据库数据"),
        (("format filesystem", "disk copy", "block device"), "会影响磁盘或文件系统"),
        (("chmod", "chown", "permissions"), "会修改权限或所有者，可能扩大访问范围"),
    ]
    for needles, label in mappings:
        if any(needle in desc for needle in needles):
            return label
    if re.search(r"\brm\b", command_l):
        return "删除操作，需要确认影响范围"
    if re.search(r"\b(python|python3|node|ruby|perl)\b", command_l):
        return "执行脚本代码，需要确认风险"
    return "命令可能影响本机环境，需要人工确认"


def infer_approval_scope(command: str, description: str = "") -> str:
    command = str(command or "")
    desc = str(description or "").lower()
    if any(token in desc for token in ("system", "root path", "filesystem", "block device")):
        return "系统或磁盘级资源"
    if re.search(r"(^|\s)([A-Za-z]:\\|/)(?!tmp\b|var/tmp\b)", command):
        return "本机绝对路径"
    if re.search(r"(^|\s)(\./|\.\\|\.\.|\*|\?)", command):
        return "当前工作区相对路径"
    if any(token in desc for token in ("git", "project", "env/config")):
        return "当前项目或版本库"
    if "sql" in desc:
        return "数据库数据"
    return "当前执行环境"


_CHOICE_ALIASES: dict[str, ApprovalDecision] = {
    "1": "once",
    "01": "once",
    "批准本次": "once",
    "本次批准": "once",
    "允许本次": "once",
    "仅此一次": "once",
    "approve once": "once",
    "allow once": "once",
    "once": "once",
    "2": "session",
    "02": "session",
    "本会话允许": "session",
    "会话允许": "session",
    "本次会话允许": "session",
    "approve session": "session",
    "allow session": "session",
    "session": "session",
    "3": "always",
    "03": "always",
    "永久允许": "always",
    "一直允许": "always",
    "总是允许": "always",
    "approve always": "always",
    "always approve": "always",
    "always allow": "always",
    "always": "always",
    "4": "deny",
    "04": "deny",
    "拒绝": "deny",
    "不允许": "deny",
    "取消": "deny",
    "deny": "deny",
    "cancel": "deny",
}


def parse_approval_reply(text: str) -> ApprovalDecision | None:
    """Parse explicit friendly approval replies.

    Deliberately does *not* accept bare yes/ok to avoid accidental execution.
    """

    raw = str(text or "").strip()
    if not raw or raw.startswith("/"):
        return None
    normalized = raw.lower()
    normalized = normalized.replace("｜", " ").replace("|", " ")
    normalized = re.sub(r"^[`'\"\s]+|[`'\"\s]+$", "", normalized)
    normalized = re.sub(r"^[（(\[]?\s*(0?[1-4])\s*[）)\].、.．:：\-—_\s]*", r"\1 ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" 。.!！")
    if normalized in _CHOICE_ALIASES:
        return _CHOICE_ALIASES[normalized]
    first = normalized.split(" ", 1)[0]
    return _CHOICE_ALIASES.get(first)


def _public_activity_label(summary: dict[str, Any]) -> str:
    current_tool = str(summary.get("current_tool") or "").strip().lower()
    last_desc = str(summary.get("last_activity_desc") or "").strip().lower()
    text = f"{current_tool} {last_desc}"
    if "receiving stream" in text or "stream response" in text:
        return "正在等待模型输出"
    if any(token in current_tool for token in ("search", "grep", "rg", "find")):
        return "正在检索资料"
    if any(token in current_tool for token in ("terminal", "shell", "command", "execute")):
        return "正在执行命令"
    if current_tool:
        return "正在执行工具步骤"
    if "starting" in text:
        return "正在启动任务"
    if "tool" in text:
        return "正在等待工具返回"
    return "仍在处理当前任务"


def public_activity_extra_status(
    summary: dict[str, Any] | None,
    *,
    elapsed_mins: int | None = None,
    label: str = "进展",
) -> tuple[str, ...]:
    parts: list[str] = []
    if elapsed_mins is not None and elapsed_mins > 0:
        parts.append(f"已运行约 {elapsed_mins} 分钟")
    if summary:
        parts.append(_public_activity_label(summary))
    if not parts:
        return ()
    return (f"{label}｜{'；'.join(parts)}",)


def render_task_progress(elapsed_mins: int, activity_summary: dict[str, Any] | None = None) -> str:
    return friendly_card(
        f"⏳ 任务仍在处理中｜已运行约 {elapsed_mins} 分钟",
        action="继续等待后台任务",
        result="尚未完成，但仍有活动迹象",
        impact="不会重复刷屏，只保留这一次进度提示",
        boundary="如果后续无活动，会进入超时保护",
        next_step="你可以继续等待，或发送 /reset 取消当前会话。",
        extra_status=public_activity_extra_status(activity_summary),
    )


def render_inactivity_warning(elapsed_mins: int, remaining_mins: int) -> str:
    return friendly_card(
        f"⚠️ 会话活动变慢｜约 {elapsed_mins} 分钟没有新进展",
        action="已启动超时保护观察",
        result=f"如果仍无活动，约 {remaining_mins} 分钟后会自动停止",
        impact="避免后台任务无限占用会话",
        boundary="不会重复发送原始错误或内部堆栈",
        next_step="你可以继续等待，或发送 /reset 立即重置。",
    )


def render_inactivity_timeout(timeout_mins: int, activity_summary: dict[str, Any] | None = None) -> str:
    return friendly_card(
        f"⏱️ 任务已自动暂停｜超过 {timeout_mins} 分钟无新活动",
        action="已停止当前后台执行",
        result="本次任务未完成，当前会话已回到可操作状态",
        impact="避免任务无限占用会话；不会展示内部堆栈或原始错误",
        boundary="详细诊断只保存在本地日志，聊天里只保留可操作信息",
        next_step="你可以重试刚才的请求，或发送 /reset 开始新的会话。",
        extra_status=public_activity_extra_status(activity_summary),
    )


def render_busy_ack(
    mode: Literal["steer", "queue", "interrupt"],
    activity_summary: dict[str, Any] | None = None,
    *,
    elapsed_mins: int | None = None,
) -> str:
    extra = public_activity_extra_status(activity_summary, elapsed_mins=elapsed_mins)
    if mode == "steer":
        return friendly_card(
            "⏩ 已接入当前任务｜消息会在下一次工具调用后生效",
            action="已尝试追加到当前运行",
            result="当前任务继续执行",
            impact="不会开启第二个并发任务",
            boundary="如果工具调用长期无返回，仍会进入超时保护",
            next_step="请等待当前任务继续输出。",
            extra_status=extra,
        )
    if mode == "queue":
        return friendly_card(
            "⏳ 已排到下一轮｜当前任务完成后处理",
            action="已保存你的后续消息",
            result="当前任务完成后会自动继续",
            impact="不会打断正在执行的任务",
            boundary="短时间多条消息会合并，避免刷屏",
            next_step="请等待当前任务结束，我会继续处理。",
            extra_status=extra,
        )
    return friendly_card(
        "⚡ 正在切换到你的新消息｜当前任务会被中断",
        action="已请求中断当前任务",
        result="会尽快处理你的新消息",
        impact="当前任务可能不会继续输出",
        boundary="只发送一次中断确认",
        next_step="请稍等，我会回复新的请求。",
        extra_status=extra,
    )
