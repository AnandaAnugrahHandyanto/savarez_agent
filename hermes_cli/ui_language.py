"""Helpers for switching Hermes CLI/TUI user-facing text between English and Chinese."""

from __future__ import annotations

from typing import Mapping


SUPPORTED_DISPLAY_LANGUAGES = {
    "en": "en",
    "en-us": "en",
    "en_us": "en",
    "english": "en",
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh_cn": "zh-CN",
    "zh-hans": "zh-CN",
    "cn": "zh-CN",
    "chinese": "zh-CN",
    "中文": "zh-CN",
}


_CATEGORY_ZH = {
    "Session": "会话",
    "Configuration": "配置",
    "Tools & Skills": "工具与技能",
    "Info": "信息",
    "Exit": "退出",
}


_COMMAND_DESC_ZH = {
    "new": "开始一个新会话（新的会话 ID 和历史）",
    "clear": "清屏并开始一个新会话",
    "history": "查看对话历史",
    "save": "保存当前对话",
    "retry": "重试上一条消息（重新发送给代理）",
    "undo": "删除上一轮用户/助手对话",
    "title": "为当前会话设置标题",
    "branch": "为当前会话创建分支（探索不同路径）",
    "compress": "手动压缩对话上下文",
    "rollback": "列出或恢复文件系统检查点",
    "stop": "停止所有后台进程",
    "approve": "批准待处理的危险命令",
    "deny": "拒绝待处理的危险命令",
    "background": "在后台运行一个提示词",
    "btw": "基于当前会话上下文的临时侧问（无工具、不持久化）",
    "queue": "把提示排到下一轮（不打断当前运行）",
    "status": "查看当前会话状态",
    "profile": "查看当前激活的 profile 名称和 home 目录",
    "sethome": "把当前聊天设置为 home 频道",
    "resume": "恢复之前命名过的会话",
    "config": "查看当前配置",
    "model": "切换当前会话模型",
    "provider": "查看可用 provider 和当前 provider",
    "personality": "设置预定义人格",
    "statusbar": "切换上下文/模型状态栏显示",
    "verbose": "循环切换工具进度显示：off -> new -> all -> verbose",
    "yolo": "切换 YOLO 模式（跳过所有危险命令审批）",
    "reasoning": "管理 reasoning 强度和显示",
    "fast": "切换快速模式（普通 / 快速）",
    "skin": "查看或切换显示皮肤/主题",
    "voice": "切换语音模式",
    "lang": "切换 TUI 界面语言（英文 / 中文）",
    "tools": "管理工具：/tools [list|disable|enable] [name...]",
    "toolsets": "列出可用 toolset",
    "skills": "搜索、安装、查看或管理技能",
    "cron": "管理定时任务",
    "reload-mcp": "从配置重新加载 MCP 服务器",
    "browser": "通过 CDP 把浏览器工具连接到你的 Chrome",
    "plugins": "列出已安装插件及其状态",
    "commands": "分页浏览所有命令和技能",
    "help": "显示可用命令",
    "zh": "显示内置中文快速上手和命令向导",
    "restart": "优雅重启网关，等待当前任务排空后执行",
    "usage": "查看当前会话的 token 使用和速率限制",
    "insights": "查看使用洞察和分析",
    "platforms": "查看网关/消息平台状态",
    "paste": "检查剪贴板里的图片并附加到下一条消息",
    "image": "为下一条提示附加本地图片",
    "update": "把 Hermes Agent 更新到最新版本",
    "quit": "退出 CLI",
}


_TEXT = {
    "help_header": {"en": "(^_^)? Available Commands", "zh-CN": "(^_^)? 可用命令"},
    "skill_commands": {"en": "Skill Commands", "zh-CN": "技能命令"},
    "installed_count": {"en": "{count} installed", "zh-CN": "已安装 {count} 个"},
    "help_tip_chat": {
        "en": "Tip: Just type your message to chat with Hermes!",
        "zh-CN": "提示：直接输入消息就可以和 Hermes 对话！",
    },
    "help_tip_multiline": {
        "en": "Multi-line: Alt+Enter for a new line",
        "zh-CN": "多行输入：按 Alt+Enter 换行",
    },
    "help_tip_attach_image": {
        "en": "Attach image: /image {path} or start your prompt with a local image path",
        "zh-CN": "附加图片：/image {path}，或在提示词开头直接写本地图片路径",
    },
    "help_tip_paste_image": {
        "en": "Paste image: Alt+V (or /paste)",
        "zh-CN": "粘贴图片：Alt+V（或 /paste）",
    },
    "usage_label": {"en": "usage", "zh-CN": "用法"},
    "status_title": {"en": "Hermes CLI Status", "zh-CN": "Hermes CLI 状态"},
    "status_session_id": {"en": "Session ID", "zh-CN": "会话 ID"},
    "status_path": {"en": "Path", "zh-CN": "路径"},
    "status_title_field": {"en": "Title", "zh-CN": "标题"},
    "status_model": {"en": "Model", "zh-CN": "模型"},
    "status_created": {"en": "Created", "zh-CN": "创建时间"},
    "status_last_activity": {"en": "Last Activity", "zh-CN": "最后活动"},
    "status_tokens": {"en": "Tokens", "zh-CN": "Tokens"},
    "status_agent_running": {"en": "Agent Running", "zh-CN": "代理运行中"},
    "yes": {"en": "Yes", "zh-CN": "是"},
    "no": {"en": "No", "zh-CN": "否"},
    "no_tools_available": {"en": "(;_;) No tools available", "zh-CN": "(;_;) 当前没有可用工具"},
    "available_tools_title": {"en": "(^_^)/ Available Tools", "zh-CN": "(^_^)/ 可用工具"},
    "tools_total": {"en": "Total: {count} tools  ヽ(^o^)ノ", "zh-CN": "总计：{count} 个工具  ヽ(^o^)ノ"},
    "available_toolsets_title": {"en": "(^_^)b Available Toolsets", "zh-CN": "(^_^)b 可用 Toolset"},
    "toolsets_currently_enabled": {"en": "(*) = currently enabled", "zh-CN": "(*) = 当前已启用"},
    "toolsets_tip_enable_all": {"en": "Tip: Use 'all' or '*' to enable all toolsets", "zh-CN": "提示：使用 'all' 或 '*' 启用全部 toolset"},
    "toolsets_example": {"en": "Example: python cli.py --toolsets web,terminal", "zh-CN": "示例：python cli.py --toolsets web,terminal"},
    "gateway_status_title": {"en": "(✿◠‿◠) Gateway Status", "zh-CN": "(✿◠‿◠) 网关状态"},
    "gateway_platform_config": {"en": "Messaging Platform Configuration:", "zh-CN": "消息平台配置："},
    "gateway_enabled": {"en": "Enabled", "zh-CN": "已启用"},
    "gateway_not_configured": {"en": "Not configured", "zh-CN": "未配置"},
    "gateway_reset_policy": {"en": "Session Reset Policy:", "zh-CN": "会话重置策略："},
    "gateway_mode": {"en": "Mode", "zh-CN": "模式"},
    "gateway_daily_reset": {"en": "Daily reset at", "zh-CN": "每日重置时间"},
    "gateway_idle_timeout": {"en": "Idle timeout", "zh-CN": "空闲超时"},
    "gateway_minutes": {"en": "minutes", "zh-CN": "分钟"},
    "gateway_start_label": {"en": "To start the gateway:", "zh-CN": "启动网关："},
    "gateway_config_file": {"en": "Configuration file", "zh-CN": "配置文件"},
    "gateway_configure_label": {"en": "To configure the gateway:", "zh-CN": "配置网关："},
    "gateway_set_env": {"en": "Set environment variables:", "zh-CN": "设置环境变量："},
    "gateway_or_config": {"en": "Or configure settings in", "zh-CN": "或直接在这里配置："},
    "fresh_start": {
        "en": "  ✨ (◕‿◕)✨ Fresh start! Screen cleared and conversation reset.\n",
        "zh-CN": "  ✨ (◕‿◕)✨ 全新开始！界面已清空，会话已重置。\n",
    },
    "statusbar_visible": {"en": "  Status bar visible", "zh-CN": "  状态栏已显示"},
    "statusbar_hidden": {"en": "  Status bar hidden", "zh-CN": "  状态栏已隐藏"},
    "welcome": {
        "en": "Welcome to {agent_name}! Type your message or /help for commands.",
        "zh-CN": "欢迎来到 {agent_name}！直接输入消息开始聊天，或输入 /help 查看命令。",
    },
    "activated_skills": {"en": "Activated skills:", "zh-CN": "已激活技能："},
    "tool_progress_off": {"en": "Tool progress: OFF — silent mode, just the final response.", "zh-CN": "工具进度：关闭 — 静默模式，只显示最终回复。"},
    "tool_progress_new": {"en": "Tool progress: NEW — show each new tool (skip repeats).", "zh-CN": "工具进度：NEW — 显示每个新工具调用（跳过重复项）。"},
    "tool_progress_all": {"en": "Tool progress: ALL — show every tool call.", "zh-CN": "工具进度：ALL — 显示每一次工具调用。"},
    "tool_progress_verbose": {"en": "Tool progress: VERBOSE — full args, results, think blocks, and debug logs.", "zh-CN": "工具进度：VERBOSE — 显示完整参数、结果、思考片段和调试日志。"},
    "yolo_off": {"en": "  ⚠ YOLO mode OFF — dangerous commands will require approval.", "zh-CN": "  ⚠ YOLO 模式已关闭 — 危险命令仍需要审批。"},
    "yolo_on": {"en": "  ⚡ YOLO mode ON — all commands auto-approved. Use with caution.", "zh-CN": "  ⚡ YOLO 模式已开启 — 所有命令自动批准，请谨慎使用。"},
    "reasoning_effort": {"en": "  Reasoning effort:  {level}", "zh-CN": "  推理强度：{level}"},
    "reasoning_display": {"en": "  Reasoning display: {state}", "zh-CN": "  推理显示：{state}"},
    "reasoning_usage": {"en": "Usage: /reasoning <none|minimal|low|medium|high|xhigh|show|hide>", "zh-CN": "用法：/reasoning <none|minimal|low|medium|high|xhigh|show|hide>"},
    "reasoning_display_on": {"en": "  ✓ Reasoning display: ON (saved)", "zh-CN": "  ✓ 推理显示：开启（已保存）"},
    "reasoning_display_on_detail": {"en": "  Model thinking will be shown during and after each response.", "zh-CN": "  每次回复期间和结束后都会显示模型思考。"},
    "reasoning_display_off": {"en": "  ✓ Reasoning display: OFF (saved)", "zh-CN": "  ✓ 推理显示：关闭（已保存）"},
    "reasoning_unknown_arg": {"en": "(._.) Unknown argument: {arg}", "zh-CN": "(._.) 未知参数：{arg}"},
    "reasoning_valid_levels": {"en": "Valid levels: none, minimal, low, medium, high, xhigh", "zh-CN": "可用级别：none、minimal、low、medium、high、xhigh"},
    "reasoning_display_values": {"en": "Display:      show, hide", "zh-CN": "显示控制：show、hide"},
    "reasoning_set_saved": {"en": "  ✓ Reasoning effort set to '{arg}' (saved to config)", "zh-CN": "  ✓ 推理强度已设置为 '{arg}'（已保存到配置）"},
    "reasoning_set_session": {"en": "  ✓ Reasoning effort set to '{arg}' (session only)", "zh-CN": "  ✓ 推理强度已设置为 '{arg}'（仅当前会话）"},
    "lang_status": {"en": "Current TUI language: {label}", "zh-CN": "当前 TUI 语言：{label}"},
    "lang_usage": {"en": "Usage: /lang [en|zh|status]", "zh-CN": "用法：/lang [en|zh|status]"},
    "lang_changed_saved": {"en": "TUI language set to {label} (saved to config).", "zh-CN": "TUI 语言已切换为 {label}（已保存到配置）。"},
    "lang_changed_session": {"en": "TUI language set to {label} (session only).", "zh-CN": "TUI 语言已切换为 {label}（仅当前会话）。"},
    "lang_unknown": {"en": "Unsupported language: {value}. Use en or zh.", "zh-CN": "不支持的语言：{value}。请使用 en 或 zh。"},
    "banner_available_tools": {"en": "Available Tools", "zh-CN": "可用工具"},
    "banner_more_toolsets": {"en": "(and {count} more toolsets...)", "zh-CN": "（以及另外 {count} 个 toolset...）"},
    "banner_mcp_servers": {"en": "MCP Servers", "zh-CN": "MCP 服务器"},
    "banner_tool_count": {"en": "{count} tool(s)", "zh-CN": "{count} 个工具"},
    "banner_failed": {"en": "failed", "zh-CN": "连接失败"},
    "banner_available_skills": {"en": "Available Skills", "zh-CN": "可用技能"},
    "banner_more_skills": {"en": "+{count} more", "zh-CN": "+另外 {count} 个"},
    "banner_no_skills": {"en": "No skills installed", "zh-CN": "当前没有安装技能"},
    "banner_profile": {"en": "Profile:", "zh-CN": "Profile："},
    "banner_summary_tools": {"en": "{count} tools", "zh-CN": "{count} 个工具"},
    "banner_summary_skills": {"en": "{count} skills", "zh-CN": "{count} 个技能"},
    "banner_summary_mcp": {"en": "{count} MCP servers", "zh-CN": "{count} 个 MCP 服务器"},
    "banner_summary_help": {"en": "/help for commands", "zh-CN": "输入 /help 查看命令"},
    "banner_update": {"en": "⚠ {count} {word} behind — run {command} to update", "zh-CN": "⚠ 落后 {count} 个{word} — 运行 {command} 更新"},
    "banner_commit_word_singular": {"en": "commit", "zh-CN": "提交"},
    "banner_commit_word_plural": {"en": "commits", "zh-CN": "提交"},
    "tools_disabled_missing_keys": {"en": "⚠️  Some tools disabled (missing API keys):", "zh-CN": "⚠️  有些工具已禁用（缺少 API Key）："},
    "run_setup_to_configure": {"en": "Run 'hermes setup' to configure", "zh-CN": "运行 'hermes setup' 完成配置"},
    "context_warning": {
        "en": "⚠️  Context length is only {count} tokens — this is likely too low for agent use with tools.",
        "zh-CN": "⚠️  当前上下文长度只有 {count} tokens，这通常不足以支撑带工具的 agent 使用。",
    },
    "context_warning_detail": {
        "en": "Hermes needs 16k–32k minimum. Tool schemas + system prompt alone use ~4k–8k.",
        "zh-CN": "Hermes 至少需要 16k–32k。仅工具 schema 和 system prompt 就会占用约 4k–8k。",
    },
    "context_warning_ollama": {
        "en": "Ollama fix: OLLAMA_CONTEXT_LENGTH=32768 ollama serve",
        "zh-CN": "Ollama 修复方式：OLLAMA_CONTEXT_LENGTH=32768 ollama serve",
    },
    "context_warning_lmstudio": {
        "en": "LM Studio fix: Set context length in model settings → reload model",
        "zh-CN": "LM Studio 修复方式：在模型设置里提高上下文长度，然后重新加载模型",
    },
    "context_warning_generic": {
        "en": "Fix: Set model.context_length in config.yaml, or increase your server's context setting",
        "zh-CN": "修复方式：在 config.yaml 里设置 model.context_length，或提高你的服务端上下文长度设置",
    },
    "hermes_model_warning": {
        "en": "⚠  Nous Research Hermes 3 & 4 models are NOT agentic and are not designed for use with Hermes Agent.",
        "zh-CN": "⚠  Nous Research Hermes 3 和 4 模型不是 agentic 模型，不适合搭配 Hermes Agent 使用。",
    },
    "hermes_model_warning_detail": {
        "en": "They lack tool-calling capabilities required for agent workflows. Consider using an agentic model (Claude, GPT, Gemini, DeepSeek, etc.).",
        "zh-CN": "它们缺少 agent 工作流所需的工具调用能力。建议改用 Claude、GPT、Gemini、DeepSeek 等 agentic 模型。",
    },
    "voice_rec_compact": {"en": " ● REC ", "zh-CN": " ● 录音 "},
    "voice_rec_full": {"en": " ● REC  Ctrl+B to stop ", "zh-CN": " ● 录音中  Ctrl+B 停止 "},
    "voice_stt_compact": {"en": " ◉ STT ", "zh-CN": " ◉ 转写 "},
    "voice_stt_full": {"en": " ◉ Transcribing... ", "zh-CN": " ◉ 转写中... "},
    "voice_ready_compact": {"en": " 🎤 Ctrl+B ", "zh-CN": " 🎤 Ctrl+B "},
    "voice_ready_full": {"en": " 🎤 Voice mode{tts}{cont}  —  Ctrl+B to record ", "zh-CN": " 🎤 语音模式{tts}{cont}  —  Ctrl+B 开始录音 "},
    "voice_tts_on": {"en": " | TTS on", "zh-CN": " | TTS 开启"},
    "voice_continuous": {"en": " | Continuous", "zh-CN": " | 连续模式"},
}


def normalize_display_language(value: str | None, *, default: str = "en") -> str:
    """Normalize a display language value into a supported locale tag."""
    raw = (value or "").strip()
    if not raw:
        return default
    lowered = raw.lower()
    if lowered in SUPPORTED_DISPLAY_LANGUAGES:
        return SUPPORTED_DISPLAY_LANGUAGES[lowered]
    if lowered.startswith("zh"):
        return "zh-CN"
    if lowered.startswith("en"):
        return "en"
    return default


def parse_display_language(value: str | None) -> str | None:
    """Parse a user-entered display language; return None when unsupported."""
    raw = (value or "").strip()
    if not raw:
        return None
    lowered = raw.lower()
    if lowered in SUPPORTED_DISPLAY_LANGUAGES:
        return SUPPORTED_DISPLAY_LANGUAGES[lowered]
    if lowered.startswith("zh"):
        return "zh-CN"
    if lowered.startswith("en"):
        return "en"
    return None


def is_chinese_display(language: str | None) -> bool:
    """Return True when the language should show Chinese UI text."""
    return normalize_display_language(language) == "zh-CN"


def display_language_name(language: str | None) -> str:
    """Return a human-readable language label."""
    return "中文" if is_chinese_display(language) else "English"


def ui_text(key: str, language: str | None = None, /, **kwargs) -> str:
    """Return a localized UI string."""
    lang = normalize_display_language(language)
    entry = _TEXT[key]
    template = entry["zh-CN"] if lang == "zh-CN" else entry["en"]
    return template.format(**kwargs)


def category_label(category: str, language: str | None = None) -> str:
    """Return a localized CLI help category label."""
    if is_chinese_display(language):
        return _CATEGORY_ZH.get(category, category)
    return category


def command_description(command_name: str, fallback: str, language: str | None = None) -> str:
    """Return a localized slash-command description for CLI help."""
    if is_chinese_display(language):
        return _COMMAND_DESC_ZH.get(command_name, fallback)
    return fallback


def command_help_description(
    command_name: str,
    fallback: str,
    args_hint: str = "",
    language: str | None = None,
) -> str:
    """Return a localized command description including usage when available."""
    desc = command_description(command_name, fallback, language)
    if not args_hint:
        return desc
    usage_label = ui_text("usage_label", language)
    return f"{desc} ({usage_label}: /{command_name} {args_hint})"


def alias_description(desc: str, canonical_name: str, language: str | None = None) -> str:
    """Format an alias description in the current UI language."""
    if is_chinese_display(language):
        return f"{desc}（`/{canonical_name}` 的别名）"
    return f"{desc} (alias for /{canonical_name})"


def format_tool_progress(mode: str, language: str | None = None) -> str:
    """Return a localized tool-progress label."""
    key = {
        "off": "tool_progress_off",
        "new": "tool_progress_new",
        "all": "tool_progress_all",
        "verbose": "tool_progress_verbose",
    }.get(mode, "tool_progress_all")
    return ui_text(key, language)


def localized_welcome(agent_name: str, language: str | None = None) -> str:
    """Return the localized welcome line shown under the banner."""
    return ui_text("welcome", language, agent_name=agent_name)


def map_ui_text(keys: Mapping[str, str], language: str | None = None) -> dict[str, str]:
    """Translate a fixed mapping of logical labels to localized strings."""
    return {name: ui_text(key, language) for name, key in keys.items()}
