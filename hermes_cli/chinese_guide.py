"""Offline Chinese quickstart and command guide for Hermes Agent."""

from __future__ import annotations

from hermes_constants import display_hermes_home

TOPIC_ALIASES = {
    "quick": "quickstart",
    "quickstart": "quickstart",
    "install": "quickstart",
    "intro": "quickstart",
    "setup": "setup",
    "config": "config",
    "commands": "commands",
    "command": "commands",
    "cmd": "commands",
    "gateway": "gateway",
    "profile": "profiles",
    "profiles": "profiles",
    "topics": "topics",
    "topic": "topics",
    "list": "topics",
}

TOPIC_TITLES = {
    "quickstart": "Hermes 中文快速上手",
    "setup": "Hermes 中文配置流程",
    "config": "Hermes 中文配置文件说明",
    "commands": "Hermes 常用命令中文说明",
    "gateway": "Hermes 消息网关中文说明",
    "profiles": "Hermes Profiles 中文说明",
    "topics": "Hermes 中文向导主题列表",
}


def available_topics() -> list[str]:
    """Return user-facing topic names in display order."""
    return ["quickstart", "setup", "config", "commands", "gateway", "profiles"]


def normalize_topic(topic: str | None) -> str:
    """Normalize a topic or fallback to the default quickstart guide."""
    raw = (topic or "").strip().lower()
    if not raw:
        return "quickstart"
    return TOPIC_ALIASES.get(raw, "")


def render_topic(topic: str | None = None, *, markdown: bool = False) -> str:
    """Render a Chinese guide topic for CLI or gateway output."""
    normalized = normalize_topic(topic)
    if not normalized:
        topics = ", ".join(available_topics())
        return (
            "未找到这个主题。可用主题："
            f"{topics}\n"
            "你也可以使用 `hermes zh topics` 或 `/zh topics` 查看列表。"
        )
    if normalized == "topics":
        return _render_topics(markdown=markdown)
    if normalized == "quickstart":
        return _render_quickstart(markdown=markdown)
    if normalized == "setup":
        return _render_setup(markdown=markdown)
    if normalized == "config":
        return _render_config(markdown=markdown)
    if normalized == "commands":
        return _render_commands(markdown=markdown)
    if normalized == "gateway":
        return _render_gateway(markdown=markdown)
    if normalized == "profiles":
        return _render_profiles(markdown=markdown)
    return _render_topics(markdown=markdown)


def _render_topics(*, markdown: bool) -> str:
    body = [
        "可用主题：",
        "- `quickstart`：安装后 2 分钟快速上手",
        "- `setup`：第一次配置 Hermes 的推荐流程",
        "- `config`：`config.yaml`、`.env`、常见配置项说明",
        "- `commands`：CLI / slash 常用命令中文解释",
        "- `gateway`：Telegram / Discord / Slack 等网关接入思路",
        "- `profiles`：多实例隔离配置的使用方式",
        "",
        "示例：`hermes zh commands` 或在会话里输入 `/zh config`。",
    ]
    return _render_document(TOPIC_TITLES["topics"], body, markdown=markdown)


def _render_quickstart(*, markdown: bool) -> str:
    body = [
        "1. 安装 Hermes",
        "- `curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash`",
        "- 安装完成后重新加载 shell：`source ~/.bashrc` 或 `source ~/.zshrc`。",
        "",
        "2. 启动并进入交互界面",
        "- 直接运行 `hermes` 就会进入交互式 CLI。",
        "- 第一次使用建议先执行 `hermes setup`，它会带你完成模型和环境配置。",
        "",
        "3. 选择模型 / Provider",
        "- `hermes model`：交互式选择模型。",
        "- 如果你已经知道要用哪个模型，也可以直接在配置里设置：`hermes config set model.default openai/gpt-5`。",
        "",
        "4. 遇到不会配的地方",
        "- `hermes zh setup`：看中文配置流程。",
        "- `hermes zh commands`：看中文命令速查。",
        "- `hermes doctor`：检查环境、依赖和常见错误。",
        "",
        "5. 会话里也能随时查中文帮助",
        "- 输入 `/zh` 查看快速上手。",
        "- 输入 `/zh config`、`/zh gateway`、`/zh profiles` 查看专题说明。",
    ]
    return _render_document(TOPIC_TITLES["quickstart"], body, markdown=markdown)


def _render_setup(*, markdown: bool) -> str:
    hermes_home = display_hermes_home()
    body = [
        "推荐给新用户的配置顺序：",
        "1. 运行 `hermes setup`。",
        "2. 先确定你要用的 Provider，例如 OpenAI、Anthropic、OpenRouter 或自建兼容接口。",
        "3. 把 API Key 写进 `.env`，或者用 `hermes config set OPENAI_API_KEY <你的key>` 这类命令写入。",
        "4. 再运行 `hermes model` 选择默认模型。",
        "5. 如果你要让 Hermes 接入 Telegram / Discord / Slack，再运行 `hermes gateway setup`。",
        "6. 最后执行 `hermes doctor`，确认依赖、配置和网络都正常。",
        "",
        "配置文件位置：",
        f"- 主配置：`{hermes_home}/config.yaml`",
        f"- 密钥环境变量：`{hermes_home}/.env`",
        "",
        "常见建议：",
        "- 只想先在终端里用：完成 `setup`、`model` 就够了，网关可以以后再配。",
        "- 想在手机聊天软件里用：除了 CLI 配置外，再补 `gateway setup` 和对应平台 token。",
        "- 想多人或多场景隔离使用：从一开始就考虑 `hermes profile create <name>`。",
    ]
    return _render_document(TOPIC_TITLES["setup"], body, markdown=markdown)


def _render_config(*, markdown: bool) -> str:
    hermes_home = display_hermes_home()
    body = [
        "Hermes 的配置主要分两类：",
        f"- `config.yaml`：普通配置，位置在 `{hermes_home}/config.yaml`",
        f"- `.env`：API Key、token 等敏感信息，位置在 `{hermes_home}/.env`",
        "",
        "常用命令：",
        "- `hermes config show`：查看当前配置。",
        "- `hermes config path`：打印 `config.yaml` 路径。",
        "- `hermes config env-path`：打印 `.env` 路径。",
        "- `hermes config set model.default anthropic/claude-opus-4.6`：设置默认模型。",
        "- `hermes config set OPENROUTER_API_KEY <key>`：写入 API Key；这类敏感项会自动进入 `.env`。",
        "",
        "你可以这样理解：",
        "- 跟行为、显示、模型默认值有关的设置，通常放 `config.yaml`。",
        "- 以 `_API_KEY`、`_TOKEN` 结尾，或类似平台密钥的设置，通常放 `.env`。",
        "",
        "排查建议：",
        "- 改完配置后，如果行为不符合预期，先执行 `hermes config show` 看最终生效值。",
        "- 如果是模型或 Provider 问题，结合 `hermes model`、`hermes doctor` 一起检查。",
    ]
    return _render_document(TOPIC_TITLES["config"], body, markdown=markdown)


def _render_commands(*, markdown: bool) -> str:
    body = [
        "CLI 常用命令：",
        "- `hermes`：进入交互式聊天界面。",
        "- `hermes setup`：第一次安装后最推荐的配置入口。",
        "- `hermes model`：切换默认模型或 Provider。",
        "- `hermes tools`：查看或启用/禁用工具。",
        "- `hermes gateway`：启动消息平台网关。",
        "- `hermes doctor`：诊断环境和配置问题。",
        "- `hermes zh <topic>`：查看内置中文指南。",
        "",
        "会话里的 slash 命令：",
        "- `/help`：查看可用命令。",
        "- `/new` 或 `/reset`：开启全新会话。",
        "- `/model [provider:model]`：当前会话切模型。",
        "- `/retry`：重试上一条消息。",
        "- `/undo`：撤销上一轮用户/助手对话。",
        "- `/compress`：手动压缩上下文，适合长会话。",
        "- `/usage`：查看 token 使用情况。",
        "- `/skills`：浏览或安装技能。",
        "- `/lang [en|zh|status]`：切换或查看 TUI 界面语言。",
        "- `/zh [topic]`：在会话里查看中文说明。",
        "",
        "推荐记住的两个排障命令：",
        "- `hermes doctor`：偏向安装、依赖、配置检查。",
        "- `/status`：偏向当前会话状态、模型、token 等信息。",
    ]
    return _render_document(TOPIC_TITLES["commands"], body, markdown=markdown)


def _render_gateway(*, markdown: bool) -> str:
    body = [
        "Hermes Gateway 的作用：",
        "- 让 Hermes 不只在本地终端里工作，还能接入 Telegram、Discord、Slack、WhatsApp、Signal 等平台。",
        "",
        "推荐流程：",
        "1. 先把 CLI 用顺手，确认模型和 API Key 没问题。",
        "2. 运行 `hermes gateway setup` 配置平台 token。",
        "3. 用 `hermes gateway run` 前台启动，先验证是否正常。",
        "4. 稳定后再按需要使用 `hermes gateway install` / `start` 作为后台服务。",
        "",
        "常用命令：",
        "- `hermes gateway setup`：配置平台接入信息。",
        "- `hermes gateway run`：前台运行，最适合调试。",
        "- `hermes gateway status`：查看服务状态。",
        "- `hermes gateway restart`：重启网关服务。",
        "",
        "使用建议：",
        "- 调试阶段优先用 `run`，因为报错更直观。",
        "- 生产环境再考虑后台服务和自动启动。",
        "- 如果消息平台收不到回复，先检查对应平台 token、授权用户和日志。",
    ]
    return _render_document(TOPIC_TITLES["gateway"], body, markdown=markdown)


def _render_profiles(*, markdown: bool) -> str:
    hermes_home = display_hermes_home()
    body = [
        "Profiles 是 Hermes 的多实例隔离能力。",
        "- 适合把“工作 / 个人 / 实验 / 不同客户项目”完全分开。",
        "- 每个 profile 都有自己的配置、密钥、记忆、session、skills。",
        "",
        "常用命令：",
        "- `hermes profile list`：查看所有 profile。",
        "- `hermes profile create coder`：创建一个新 profile。",
        "- `hermes -p coder`：直接以指定 profile 启动。",
        "- `hermes profile use coder`：把某个 profile 设为默认。",
        "- `hermes profile show coder`：看某个 profile 的详情。",
        "",
        "理解方式：",
        f"- 默认实例通常在 `{hermes_home}`。",
        "- 其他 profile 会使用独立目录，不共享 session 和配置。",
        "",
        "什么时候该用它：",
        "- 你想把不同工作流彻底隔离。",
        "- 你想给不同项目配不同模型、技能、API Key。",
        "- 你需要演示环境和开发环境互不影响。",
    ]
    return _render_document(TOPIC_TITLES["profiles"], body, markdown=markdown)


def _render_document(title: str, body: list[str], *, markdown: bool) -> str:
    if markdown:
        return "\n".join([f"## {title}", "", *body]).strip()
    underline = "=" * len(title)
    return "\n".join([title, underline, "", *body]).strip()
