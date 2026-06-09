# Hermes Agent 项目使用指南

> 版本：v0.16.0 | 更新日期：2026-06-07
> 本文档面向中文用户，提供从安装到日常使用的完整指引。

---

## 目录

1. [项目概述](#1-项目概述)
2. [环境准备](#2-环境准备)
3. [安装步骤](#3-安装步骤)
4. [使用方法](#4-使用方法)
5. [配置说明](#5-配置说明)
6. [注意事项](#6-注意事项)
7. [故障排除](#7-故障排除)
8. [附录](#8-附录)

---

## 1. 项目概述

### 1.1 什么是 Hermes Agent

**Hermes Agent** 是由 [Nous Research](https://nousresearch.com) 构建的**自进化 AI 代理**。它是目前唯一内置"学习闭环"的智能代理系统——能够从经验中自动创建技能、在使用中持续改进技能、主动持久化知识，并在跨会话中逐步构建对用户的深度理解。

### 1.2 核心功能

| 功能模块 | 说明 |
|---------|------|
| **多模型支持** | 支持 OpenRouter、Nous Portal、Xiaomi MiMo、Kimi、GLM、MiniMax、Hugging Face、OpenAI 等 20+ 提供商，200+ 模型 |
| **真实终端界面** | 完整的 TUI（终端用户界面），支持多行编辑、斜杠命令自动补全、对话历史、中断重定向和流式工具输出 |
| **多平台消息网关** | 同时支持 Telegram、Discord、Slack、WhatsApp、Signal、Email、Google Chat、Microsoft Teams 等 |
| **闭环学习系统** | 代理管理记忆并定期自我提醒；复杂任务后自动创建技能；技能在使用中自我改进 |
| **会话搜索** | 基于 FTS5 的全文搜索 + LLM 摘要，实现跨会话知识回溯 |
| **定时自动化** | 内置 cron 调度器，支持日报、夜间备份、周审计等无人值守任务 |
| **子代理委派** | 生成隔离子代理处理并行工作流，支持批量任务处理 |
| **六种终端后端** | 本地、Docker、SSH、Singularity、Modal、Daytona |
| **代码执行** | 编写 Python 脚本通过 RPC 调用工具，将多步管道压缩为零上下文开销 |
| **语音支持** | 语音备忘录转写（Whisper）、文本转语音（TTS） |

### 1.3 适用场景

- **个人开发助手**：代码审查、Bug 修复、项目重构、技术调研
- **自动化运维**：定时任务、日志分析、系统监控、报告生成
- **多平台智能客服**：接入 Telegram/Discord/Slack 等，提供 7x24 服务
- **知识管理**：跨会话记忆、文档整理、技能库构建
- **研究辅助**：批量数据处理、文献综述、实验设计
- **创意工作**：内容创作、图像生成、视频脚本

### 1.4 设计目标

1. **随处运行**：$5 VPS、GPU 集群、Serverless 环境均可部署
2. **零锁定**：随时切换模型提供商，无需修改代码
3. **自我进化**：越用越聪明，自动积累技能和知识
4. **安全可靠**：命令审批、容器隔离、敏感信息保护
5. **研究就绪**：批量轨迹生成、轨迹压缩，支持模型训练

---

## 2. 环境准备

### 2.1 操作系统支持

| 操作系统 | 支持状态 | 备注 |
|---------|---------|------|
| **Linux** | 完全支持 | 推荐 Ubuntu 22.04+ / Debian 12+ |
| **macOS** | 完全支持 | macOS 13+ (Ventura 及更新版本) |
| **Windows (原生)** | 完全支持 | Windows 10/11，PowerShell 5.1+ |
| **WSL2** | 完全支持 | 推荐 WSL2 + Ubuntu 22.04 |
| **Android (Termux)** | 部分支持 | 需手动安装，语音功能受限 |

### 2.2 软件依赖

#### 必需依赖

| 软件 | 最低版本 | 说明 |
|------|---------|------|
| **Python** | 3.11.x - 3.13.x | 核心运行时（推荐 3.11） |
| **uv** | 0.10.0+ | 极速 Python 包管理器 |
| **Git** | 2.30+ | 版本控制（Windows 会自动安装 MinGit） |

#### 可选依赖（根据功能需求）

| 软件 | 用途 | 安装命令 |
|------|------|---------|
| **Node.js** | 浏览器工具、MCP 服务器 | `hermes postinstall` 自动安装 |
| **ripgrep** | 文件搜索 | `hermes postinstall` 自动安装 |
| **ffmpeg** | 音视频处理 | `hermes postinstall` 自动安装 |
| **Docker** | 容器化终端后端 | [Docker 官网](https://docker.com) 下载 |

#### 本项目的本地环境

本项目已在以下环境中完成部署测试：

```
操作系统：Windows 11
Python：3.13.5（位于 F:\python\python.exe）
uv：0.11.19（位于 F:\uv-x86_64-pc-windows-msvc\uv.exe）
项目路径：F:\AI\xiaoye\hermes-agent
虚拟环境：.venv\（Python 3.13.5）
```

### 2.3 硬件配置建议

| 使用场景 | CPU | 内存 | 磁盘 | 网络 |
|---------|-----|------|------|------|
| **个人轻量使用** | 2 核 | 4 GB | 10 GB | 稳定宽带 |
| **日常开发** | 4 核 | 8 GB | 20 GB | 稳定宽带 |
| **网关 + 多平台** | 4 核 | 16 GB | 50 GB | 低延迟 |
| **批量处理/研究** | 8 核+ | 32 GB+ | 100 GB+ | 高带宽 |

> **注意**：本地 STT（语音转文字）需要额外约 150 MB 模型下载（`faster-whisper`）。

### 2.4 API Key 准备

根据你想使用的模型提供商，提前准备好对应的 API Key：

| 提供商 | 获取地址 | 环境变量名 |
|--------|---------|-----------|
| **Xiaomi MiMo** | https://platform.xiaomimimo.com | `XIAOMI_API_KEY` |
| **OpenRouter** | https://openrouter.ai/keys | `OPENROUTER_API_KEY` |
| **Nous Portal** | https://portal.nousresearch.com | OAuth 登录（无需 Key） |
| **Google Gemini** | https://aistudio.google.com/app/apikey | `GOOGLE_API_KEY` |
| **Kimi/Moonshot** | https://platform.moonshot.ai | `KIMI_API_KEY` |
| **MiniMax** | https://www.minimax.io | `MINIMAX_API_KEY` |
| **Hugging Face** | https://huggingface.co/settings/tokens | `HF_TOKEN` |

---

## 3. 安装步骤

### 3.1 方式一：自动安装（推荐新手）

#### Linux / macOS / WSL2

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
source ~/.bashrc  # 或 source ~/.zshrc
hermes            # 开始对话
```

#### Windows (PowerShell)

```powershell
iex (irm https://hermes-agent.nousresearch.com/install.ps1)
```

> 安装程序会自动处理：uv、Python 3.11、Node.js、ripgrep、ffmpeg，以及便携版 Git Bash（MinGit）。

### 3.2 方式二：手动安装（本项目的部署方式）

如果你已经克隆了源码，或想完全控制安装过程，按以下步骤操作：

#### 步骤 1：确认依赖已安装

```powershell
# 检查 Python 版本（需 3.11 - 3.13）
F:\python\python.exe --version
# 输出：Python 3.13.5

# 检查 uv 版本
F:\uv-x86_64-pc-windows-msvc\uv.exe --version
# 输出：uv 0.11.19
```

#### 步骤 2：进入项目目录

```powershell
cd F:\AI\xiaoye\hermes-agent
```

#### 步骤 3：创建虚拟环境

```powershell
F:\uv-x86_64-pc-windows-msvc\uv.exe venv --python F:\python\python.exe .venv
```

输出示例：
```
Using CPython 3.13.5 interpreter at: F:\python\python.exe
Creating virtual environment at: .venv
Activate with: .venv\Scripts\activate
```

#### 步骤 4：安装项目依赖

```powershell
F:\uv-x86_64-pc-windows-msvc\uv.exe pip install -e . --python .venv\Scripts\python.exe
```

此命令会：
- 读取 `pyproject.toml` 中的依赖定义
- 自动解析并安装 58 个核心依赖包
- 以"可编辑模式"安装 hermes-agent 本身

#### 步骤 5：配置环境变量

从模板创建 `.env` 文件：

```powershell
copy .env.example .env
```

编辑 `.env` 文件，填入你的 API Key。以 **Xiaomi MiMo** 为例：

```env
# =============================================================================
# LLM PROVIDER (Xiaomi MiMo)
# =============================================================================
XIAOMI_API_KEY=你的真实API密钥
XIAOMI_BASE_URL=https://api.xiaomimimo.com/v1
```

> **安全提示**：`.env` 文件包含敏感信息，已自动加入 `.gitignore`，请勿提交到版本控制。

#### 步骤 6：验证安装

```powershell
# 验证模块导入
.venv\Scripts\python.exe -c "import hermes_cli; print('OK')"

# 查看帮助
.venv\Scripts\python.exe -m hermes_cli.main --help
```

### 3.3 安装额外功能（可选）

```powershell
# 安装所有可选依赖（语音、消息平台、浏览器等）
F:\uv-x86_64-pc-windows-msvc\uv.exe pip install -e ".[all]" --python .venv\Scripts\python.exe

# 或按需安装特定功能
F:\uv-x86_64-pc-windows-msvc\uv.exe pip install -e ".[messaging]" --python .venv\Scripts\python.exe  # 消息平台
F:\uv-x86_64-pc-windows-msvc\uv.exe pip install -e ".[voice]" --python .venv\Scripts\python.exe      # 语音功能
F:\uv-x86_64-pc-windows-msvc\uv.exe pip install -e ".[vision]" --python .venv\Scripts\python.exe      # 图像处理
```

### 3.4 安装后初始化

```powershell
# 运行设置向导（推荐首次使用）
.venv\Scripts\hermes.exe setup

# 或使用 Nous Portal 一键配置（无需单独收集 API Key）
.venv\Scripts\hermes.exe setup --portal
```

---

## 4. 使用方法

### 4.1 基本操作流程

#### 启动交互式对话（CLI 模式）

```powershell
# 激活虚拟环境后
.venv\Scripts\hermes.exe

# 或直接指定 provider 和 model
.venv\Scripts\hermes.exe --provider xiaomi --model mimo-v2-pro
```

启动后，你会看到欢迎界面和提示符，直接输入问题即可开始对话。

#### 常用交互模式

```powershell
# 单条命令模式（非交互）
.venv\Scripts\hermes.exe -z "帮我写一个 Python 爬虫"

# 恢复之前的会话
.venv\Scripts\hermes.exe --resume "session-name"

# 启用特定工具集
.venv\Scripts\hermes.exe -t terminal,web,file

# TUI 模式（更现代的终端界面）
.venv\Scripts\hermes.exe --tui
```

### 4.2 斜杠命令完整列表

在对话中输入 `/命令` 可以执行各种操作。以下是所有可用命令：

#### 会话管理（Session）

| 命令 | 别名 | 参数 | 功能说明 |
|------|------|------|---------|
| `/new` | `/reset` | `[name]` | 开始新会话（新的会话 ID + 历史） |
| `/clear` | - | - | 清屏并开始新会话（仅 CLI） |
| `/history` | - | - | 显示对话历史（仅 CLI） |
| `/save` | - | - | 保存当前对话（仅 CLI） |
| `/retry` | - | - | 重试上一条消息 |
| `/undo` | - | `[N]` | 回退 N 轮用户对话（默认 1） |
| `/title` | - | `[name]` | 设置当前会话标题 |
| `/branch` | `/fork` | `[name]` | 分支当前会话（探索不同路径） |
| `/compress` | - | `[here [N] \| focus topic]` | 压缩对话上下文 |
| `/rollback` | - | `[number]` | 列出或恢复文件系统检查点 |
| `/snapshot` | `/snap` | `[create\|restore <id>\|prune]` | 创建/恢复配置快照（仅 CLI） |
| `/stop` | - | - | 终止所有后台进程 |
| `/background` | `/bg`, `/btw` | `<prompt>` | 在后台运行提示 |
| `/agents` | `/tasks` | - | 显示活跃代理和运行中任务 |
| `/queue` | `/q` | `<prompt>` | 将提示加入队列（不中断当前） |
| `/steer` | - | `<prompt>` | 在下次工具调用后注入消息（不中断） |
| `/goal` | - | `[text \| pause \| resume \| clear \| status]` | 设置持续目标 |
| `/subgoal` | - | `[text \| remove N \| clear]` | 添加/管理子目标 |
| `/status` | - | - | 显示会话信息 |
| `/resume` | - | `[name]` | 恢复之前命名的会话 |
| `/sessions` | - | - | 浏览并恢复历史会话 |
| `/handoff` | - | `<platform>` | 将会话移交到消息平台（仅 CLI） |

#### 配置管理（Configuration）

| 命令 | 别名 | 参数 | 功能说明 |
|------|------|------|---------|
| `/config` | - | - | 显示当前配置（仅 CLI） |
| `/model` | - | `[model] [--provider name] [--global] [--refresh]` | 切换模型 |
| `/personality` | - | `[name]` | 设置预定义人格 |
| `/statusbar` | `/sb` | - | 切换上下文/模型状态栏（仅 CLI） |
| `/verbose` | - | - | 循环工具进度显示级别（仅 CLI） |
| `/footer` | - | `[on\|off\|status]` | 切换网关运行时元数据页脚 |
| `/yolo` | - | - | 切换 YOLO 模式（跳过危险命令审批） |
| `/reasoning` | - | `[level\|show\|hide]` | 管理推理努力和显示 |
| `/fast` | - | `[normal\|fast\|status]` | 切换快速模式 |
| `/skin` | - | `[name]` | 显示/更改显示皮肤/主题（仅 CLI） |
| `/indicator` | - | `[kaomoji\|emoji\|unicode\|ascii]` | 选择 TUI 忙碌指示器样式（仅 CLI） |
| `/voice` | - | `[on\|off\|tts\|status]` | 切换语音模式 |
| `/busy` | - | `[queue\|steer\|interrupt\|status]` | 控制 Hermes 工作时 Enter 的行为（仅 CLI） |
| `/codex-runtime` | - | `[auto\|codex_app_server]` | 切换 Codex 运行时 |

#### 工具与技能（Tools & Skills）

| 命令 | 别名 | 参数 | 功能说明 |
|------|------|------|---------|
| `/tools` | - | `[list\|disable\|enable] [name...]` | 管理工具（仅 CLI） |
| `/toolsets` | - | - | 列出可用工具集（仅 CLI） |
| `/skills` | - | `[search\|browse\|inspect\|install\|audit]` | 搜索/安装/管理技能（仅 CLI） |
| `/bundles` | - | - | 列出技能包 |
| `/cron` | - | `[list\|add\|create\|edit\|pause\|resume\|run\|remove]` | 管理定时任务（仅 CLI） |
| `/curator` | - | `[status\|run\|pause\|resume\|pin\|unpin\|restore\|list-archived]` | 后台技能维护 |
| `/kanban` | - | `[子命令]` | 多代理协作看板（详见下方） |
| `/reload` | - | - | 重新加载 .env 变量（仅 CLI） |
| `/reload-mcp` | - | - | 重新加载 MCP 服务器 |
| `/reload-skills` | - | - | 重新扫描技能目录 |
| `/browser` | - | `[connect\|disconnect\|status]` | 连接浏览器工具（仅 CLI） |
| `/plugins` | - | - | 列出已安装插件（仅 CLI） |

**Kanban 子命令**：`init`, `boards`, `create`, `list`, `ls`, `show`, `assign`, `reclaim`, `reassign`, `diagnostics`, `diag`, `link`, `unlink`, `claim`, `comment`, `complete`, `edit`, `block`, `unblock`, `archive`, `tail`, `dispatch`, `stats`, `notify-subscribe`, `notify-list`, `notify-unsubscribe`, `log`, `runs`, `heartbeat`, `assignees`, `context`, `specify`, `gc`

#### 信息查询（Info）

| 命令 | 别名 | 参数 | 功能说明 |
|------|------|------|---------|
| `/commands` | - | `[page]` | 浏览所有命令和技能（仅网关） |
| `/help` | - | - | 显示可用命令 |
| `/usage` | - | - | 显示当前会话的 Token 用量和速率限制 |
| `/insights` | - | `[days]` | 显示使用洞察和分析 |
| `/platforms` | `/gateway` | - | 显示网关/消息平台状态（仅 CLI） |
| `/copy` | - | `[number]` | 复制最后一条助手回复到剪贴板（仅 CLI） |
| `/paste` | - | - | 从剪贴板附加图片（仅 CLI） |
| `/image` | - | `<path>` | 附加本地图片文件（仅 CLI） |
| `/update` | - | - | 更新 Hermes Agent 到最新版本 |
| `/version` | `/v` | - | 显示版本号 |
| `/debug` | - | - | 上传调试报告 |
| `/whoami` | - | - | 显示你的斜杠命令权限 |
| `/profile` | - | - | 显示活跃配置文件名和主目录 |
| `/gquota` | - | - | 显示 Google Gemini Code Assist 配额（仅 CLI） |

#### 退出（Exit）

| 命令 | 别名 | 参数 | 功能说明 |
|------|------|------|---------|
| `/quit` | `/exit` | `[--delete]` | 退出 CLI（`--delete` 同时删除会话历史） |

### 4.3 核心功能模块使用

#### 4.3.1 模型切换

```bash
# 查看可用模型
hermes model --list

# 切换到 Xiaomi MiMo
hermes model --provider xiaomi mimo-v2-pro

# 切换到 OpenRouter 的 Claude
hermes model --provider openrouter anthropic/claude-opus-4.6

# 设置全局默认模型
hermes model --global --provider xiaomi mimo-v2-pro
```

#### 4.3.2 工具管理

```bash
# 交互式工具配置界面
hermes tools

# 列出所有工具集
hermes chat --list-toolsets

# 列出所有工具
hermes chat --list-tools

# 启用/禁用工具集
hermes tools enable web terminal file
hermes tools disable browser image_gen
```

**可用工具集**：

| 工具集 | 包含工具 | 说明 |
|--------|---------|------|
| `web` | web_search, web_extract | 网页搜索和内容提取 |
| `search` | web_search | 仅网页搜索 |
| `terminal` | terminal, process | 命令执行和进程管理 |
| `file` | read_file, write_file, patch, search | 文件操作 |
| `browser` | browser_navigate, browser_click, ... | 浏览器自动化 |
| `vision` | vision_analyze | 图像分析 |
| `image_gen` | image_generate | 图像生成 |
| `skills` | skills_list, skill_view | 技能加载 |
| `todo` | todo | 任务规划 |
| `tts` | text_to_speech | 文本转语音 |
| `cronjob` | cronjob | 定时任务管理 |
| `memory` | 记忆相关 | 持久化记忆 |
| `session_search` | 会话搜索 | 历史会话检索 |

#### 4.3.3 技能系统

```bash
# 搜索技能
hermes skills search 爬虫

# 安装技能
hermes skills install official/web-development/scraping

# 查看已安装技能
hermes skills inspect

# 审计技能安全性
hermes skills audit

# 在对话中使用技能
# 直接输入 /<skill-name> 即可加载
```

#### 4.3.4 定时任务（Cron）

```bash
# 列出所有定时任务
hermes cron list

# 添加定时任务（每 2 小时执行一次）
hermes cron add "每2小时检查网站状态" --schedule "every 2h"

# 添加每日报告
hermes cron add "生成昨日工作总结" --schedule "every day 9am"

# 暂停/恢复任务
hermes cron pause <task-id>
hermes cron resume <task-id>

# 立即运行任务
hermes cron run <task-id>

# 删除任务
hermes cron remove <task-id>
```

#### 4.3.5 消息网关

```bash
# 设置网关（配置 Telegram Bot 等）
hermes gateway setup

# 启动网关
hermes gateway start

# 查看网关状态
hermes gateway status

# 停止网关
hermes gateway stop
```

#### 4.3.6 会话管理

```bash
# 查看所有会话
hermes sessions list

# 恢复特定会话
hermes sessions resume <session-id>

# 删除会话
hermes sessions remove <session-id>

# 搜索历史会话
hermes sessions search "爬虫项目"
```

#### 4.3.7 人格设置

```bash
# 列出可用人格
hermes chat --list-personalities

# 在对话中切换
/personality kawaii
/personality technical
/personality teacher
```

**内置人格**：helpful、concise、technical、creative、teacher、kawaii、catgirl、pirate、shakespeare、surfer、noir、uwu、philosopher、hype

#### 4.3.8 记忆管理

```bash
# 查看当前记忆
hermes memory show

# 手动添加记忆
hermes memory add "用户喜欢 Python 而不是 JavaScript"

# 搜索记忆
hermes memory search "Python"

# 配置记忆设置
hermes config set memory.memory_enabled true
hermes config set memory.memory_char_limit 2200
```

### 4.4 CLI 与消息平台对照

| 操作 | CLI | 消息平台 |
|------|-----|----------|
| 开始对话 | `hermes` | `hermes gateway start` 后给机器人发消息 |
| 新对话 | `/new` 或 `/reset` | `/new` 或 `/reset` |
| 更换模型 | `/model [provider:model]` | `/model [provider:model]` |
| 设置人格 | `/personality [name]` | `/personality [name]` |
| 重试/撤销 | `/retry`, `/undo` | `/retry`, `/undo` |
| 压缩上下文 | `/compress`, `/usage` | `/compress`, `/usage` |
| 浏览技能 | `/skills` 或 `/<skill-name>` | `/<skill-name>` |
| 中断工作 | `Ctrl+C` 或发新消息 | `/stop` 或发新消息 |

---

## 5. 配置说明

### 5.1 配置文件结构

Hermes 使用两个核心配置文件：

| 文件 | 用途 | 位置 |
|------|------|------|
| **`.env`** | API Key、密码等敏感信息 | 项目根目录 或 `~/.hermes/.env` |
| **`config.yaml`** | 功能配置、行为设置 | `~/.hermes/config.yaml` |

### 5.2 `.env` 文件详解

`.env` 文件存储所有敏感凭证。主要配置项：

#### LLM 提供商 API Key

```env
# Xiaomi MiMo（已在本项目中启用）
XIAOMI_API_KEY=你的API密钥
XIAOMI_BASE_URL=https://api.xiaomimimo.com/v1

# OpenRouter
OPENROUTER_API_KEY=sk-or-...

# Google Gemini
GOOGLE_API_KEY=AIza...
GEMINI_API_KEY=AIza...

# Kimi/Moonshot
KIMI_API_KEY=sk-kimi-...

# MiniMax
MINIMAX_API_KEY=...
MINIMAX_CN_API_KEY=...

# Hugging Face
HF_TOKEN=hf_...

# 其他提供商...
```

#### 工具 API Key

```env
# 网页搜索
EXA_API_KEY=...
PARALLEL_API_KEY=...
FIRECRAWL_API_KEY=...

# 图像生成
FAL_KEY=...

# 浏览器自动化
BROWSERBASE_API_KEY=...
BROWSERBASE_PROJECT_ID=...

# 语音
VOICE_TOOLS_OPENAI_KEY=sk-...
GROQ_API_KEY=...

# 跨会话用户建模
HONCHO_API_KEY=...
```

#### 消息平台 Token

```env
# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_ALLOWED_USERS=123456789,987654321

# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...

# WhatsApp
WHATSAPP_ENABLED=false

# Email
EMAIL_ADDRESS=hermes@example.com
EMAIL_PASSWORD=...
```

#### 终端配置

```env
# 终端后端：local, docker, ssh, singularity, modal
TERMINAL_ENV=local

# 命令超时（秒）
TERMINAL_TIMEOUT=60

# 环境生命周期（秒）
TERMINAL_LIFETIME_SECONDS=300
```

### 5.3 `config.yaml` 详解

`config.yaml` 是 YAML 格式的功能配置文件，主要段落：

#### 模型配置（model）

```yaml
model:
  default: "anthropic/claude-opus-4.6"  # 默认模型
  provider: "auto"                      # 提供商：auto/openrouter/xiaomi/...
  base_url: "https://openrouter.ai/api/v1"  # API 基础地址
  # max_tokens: 8192                    # 最大输出 token
  # context_length: 131072              # 上下文窗口（通常自动检测）
```

#### 终端配置（terminal）

```yaml
terminal:
  backend: "local"           # 后端类型
  cwd: "."                   # 工作目录
  timeout: 180               # 超时（秒）
  lifetime_seconds: 300      # 环境生命周期
  container_cpu: 1           # CPU 核心数（容器）
  container_memory: 5120     # 内存（MB）
  container_disk: 51200      # 磁盘（MB）
  container_persistent: true # 持久化文件系统
```

#### 上下文压缩（compression）

```yaml
compression:
  enabled: true        # 启用自动压缩
  threshold: 0.50      # 在 50% 上下文限制时触发
  target_ratio: 0.20   # 保留 20% 的近期消息
  protect_last_n: 20   # 保护最近 20 条消息
  protect_first_n: 3   # 保护前 3 条非系统消息
```

#### 记忆配置（memory）

```yaml
memory:
  memory_enabled: true      # 启用代理记忆
  user_profile_enabled: true # 启用用户画像
  memory_char_limit: 2200    # 记忆字符限制
  user_char_limit: 1375      # 用户画像字符限制
  nudge_interval: 10         # 每 10 轮提醒保存记忆
  flush_min_turns: 6         # 退出时最少轮数才触发记忆保存
```

#### 会话重置策略（session_reset）

```yaml
session_reset:
  mode: both           # both/idle/daily/none
  idle_minutes: 1440   # 空闲 24 小时后重置
  at_hour: 4           # 每天凌晨 4 点重置
```

#### 代理行为（agent）

```yaml
agent:
  max_turns: 60              # 每轮最大工具调用次数
  reasoning_effort: "medium" # 推理努力程度
  verbose: false             # 详细日志
```

#### 显示设置（display）

```yaml
display:
  compact: false             # 紧凑横幅
  tool_progress: all         # 工具进度显示
  streaming: true            # 流式输出
  show_reasoning: false      # 显示推理过程
  skin: "default"            # 皮肤主题
```

#### 工具集配置（platform_toolsets）

```yaml
platform_toolsets:
  cli: [hermes-cli]
  telegram: [hermes-telegram]
  discord: [hermes-discord]
  # ... 其他平台
```

### 5.4 配置优先级

配置值按以下优先级覆盖（高优先级优先）：

1. 命令行参数（如 `--model`, `--provider`）
2. 环境变量（`.env`）
3. `config.yaml` 中的设置
4. 内置默认值

---

## 6. 注意事项

### 6.1 安全建议

1. **保护 API Key**
   - `.env` 文件已加入 `.gitignore`，请勿手动移除
   - 不要将 API Key 硬编码在代码中
   - 定期轮换 API Key

2. **命令审批**
   - 默认开启危险命令审批（删除文件、系统命令等）
   - 使用 `/yolo` 可关闭审批，但需谨慎
   - 生产环境建议保持审批开启

3. **容器隔离**
   - 使用 `terminal.backend: docker` 实现命令隔离
   - Docker 后端默认不挂载当前目录，需显式开启

4. **网关安全**
   - 消息平台网关默认需要 allowlist
   - 不要设置 `GATEWAY_ALLOW_ALL_USERS=true` 除非明确需要开放访问

### 6.2 使用限制

| 限制项 | 默认值 | 说明 |
|--------|--------|------|
| 最大工具调用轮次 | 60 | 防止无限循环 |
| 命令超时 | 60-180 秒 | 取决于后端 |
| 上下文压缩阈值 | 50% | 达到时自动压缩 |
| 子代理并发数 | 3 | 可配置 |
| 会话空闲重置 | 24 小时 | 可配置 |
| Cron 任务硬中断 | 3 分钟 | 防止失控任务 |

### 6.3 最佳实践

1. **定期保存会话**：使用 `/save` 或命名会话 `/new project-name`
2. **使用技能**：复杂任务完成后，让代理创建技能以便复用
3. **管理记忆**：定期审查和清理记忆内容，保持相关性
4. **监控用量**：使用 `/usage` 和 `/insights` 跟踪 Token 消耗
5. **压缩上下文**：长对话使用 `/compress` 减少 Token 消耗
6. **使用检查点**：重要操作前 `/rollback` 创建检查点

### 6.4 常见问题

**Q: 如何切换回之前的会话？**
```bash
/sessions          # 列出所有会话
/resume <name>     # 恢复特定会话
```

**Q: 代理陷入循环怎么办？**
- 按 `Ctrl+C` 中断
- 使用 `/stop` 终止后台进程
- 使用 `/new` 开始新会话

**Q: 如何让代理记住重要信息？**
- 代理会自动保存记忆（如果启用）
- 可以手动提示："请记住我喜欢用 Python"
- 使用 `hermes memory add` 手动添加

**Q: 如何限制代理的工具访问？**
```bash
hermes tools disable terminal browser  # 禁用特定工具
hermes chat --toolsets web,file        # 仅启用指定工具集
```

---

## 7. 故障排除

### 7.1 安装问题

#### 问题：uv 命令找不到

**症状**：`uv : 无法将"uv"项识别为 cmdlet`

**解决方案**：
```powershell
# 使用完整路径调用
F:\uv-x86_64-pc-windows-msvc\uv.exe --version

# 或添加到系统 PATH
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";F:\uv-x86_64-pc-windows-msvc", "User")
```

#### 问题：Python 版本不兼容

**症状**：`requires-python = ">=3.11,<3.14"` 报错

**解决方案**：
```powershell
# 安装 Python 3.11-3.13
# 或使用 uv 安装指定版本
uv python install 3.11
```

#### 问题：依赖安装失败

**症状**：`Failed to build ...` 或编译错误

**解决方案**：
```powershell
# 更新 uv
uv self update

# 清除缓存重试
uv cache clean
uv pip install -e . --no-cache

# 安装编译工具（Windows）
# 安装 Visual C++ Build Tools
```

### 7.2 运行时问题

#### 问题：API Key 无效

**症状**：`401 Unauthorized` 或 `Invalid API key`

**解决方案**：
1. 检查 `.env` 文件中 API Key 是否正确
2. 确认 Key 未过期
3. 验证 `XIAOMI_BASE_URL` 等地址是否正确
4. 重新加载环境变量：`/reload`

#### 问题：模型不可用

**症状**：`Model not found` 或 `Provider error`

**解决方案**：
```bash
# 检查模型名称
hermes model --list

# 切换提供商
hermes model --provider openrouter anthropic/claude-opus-4.6

# 检查提供商配置
hermes config set model.provider openrouter
```

#### 问题：工具调用失败

**症状**：`Tool error` 或 `Permission denied`

**解决方案**：
1. 检查工具是否已启用：`hermes tools`
2. 检查工具所需 API Key 是否配置
3. 检查终端后端权限（特别是 Docker/SSH）
4. 查看详细错误：`hermes config set agent.verbose true`

#### 问题：上下文过长

**症状**：`Context length exceeded` 或响应变慢

**解决方案**：
```bash
# 手动压缩
/compress

# 开始新会话
/new

# 调整压缩阈值
hermes config set compression.threshold 0.40
```

#### 问题：网关无法启动

**症状**：`Gateway failed to start` 或平台连接失败

**解决方案**：
```bash
# 检查配置
hermes gateway status

# 验证平台 Token
hermes doctor

# 查看日志
hermes logs --follow

# 重新设置网关
hermes gateway setup
```

### 7.3 性能问题

#### 问题：响应速度慢

**解决方案**：
1. 使用 `/fast` 开启快速模式
2. 切换到更快的模型（如 gemini-flash）
3. 减少启用的工具集
4. 启用流式输出：`hermes config set display.streaming true`

#### 问题：内存占用高

**解决方案**：
1. 定期 `/compress` 压缩上下文
2. 减少 `memory_char_limit`
3. 关闭不必要的功能（浏览器、图像生成）
4. 重启网关：`hermes gateway restart`

### 7.4 诊断工具

```bash
# 全面诊断
hermes doctor

# 查看日志
hermes logs                    # 查看最新日志
hermes logs --follow           # 实时跟踪
hermes logs --level error      # 仅看错误
hermes logs --session <id>     # 特定会话

# 调试报告
hermes debug                   # 生成并上传调试报告

# 查看配置
hermes config                  # 显示当前配置
hermes config get model.default # 获取特定配置项
```

---

## 8. 附录

### 8.1 相关资源链接

| 资源 | 链接 |
|------|------|
| **官方文档** | https://hermes-agent.nousresearch.com/docs/ |
| **GitHub 仓库** | https://github.com/NousResearch/hermes-agent |
| **Discord 社区** | https://discord.gg/NousResearch |
| **Nous Research** | https://nousresearch.com |
| **Nous Portal** | https://portal.nousresearch.com |
| **OpenRouter** | https://openrouter.ai |
| **Xiaomi MiMo** | https://platform.xiaomimimo.com |
| **Kimi/Moonshot** | https://platform.moonshot.ai |
| **MiniMax** | https://www.minimax.io |
| **Hugging Face** | https://huggingface.co |

### 8.2 术语解释

| 术语 | 解释 |
|------|------|
| **Agent（代理）** | 能够自主执行任务的 AI 系统 |
| **Tool（工具）** | 代理可调用的功能模块（如搜索文件、执行命令） |
| **Toolset（工具集）** | 相关工具的集合，可按平台启用/禁用 |
| **Skill（技能）** | 可复用的任务流程文档，代理可加载执行 |
| **Session（会话）** | 一次完整的对话上下文，包含历史消息 |
| **Context（上下文）** | 当前对话的全部信息，受模型上下文窗口限制 |
| **Compression（压缩）** | 自动总结旧消息以释放上下文空间 |
| **Memory（记忆）** | 跨会话持久化的信息 |
| **Gateway（网关）** | 连接消息平台（Telegram 等）的桥梁 |
| **Provider（提供商）** | LLM API 服务商（如 OpenRouter、Xiaomi） |
| **TUI** | Terminal User Interface，终端用户界面 |
| **MCP** | Model Context Protocol，模型上下文协议 |
| **Cron** | 定时任务调度系统 |
| **Kanban** | 看板系统，用于多代理协作 |
| **YOLO 模式** | 跳过所有危险命令审批的模式 |
| **STT** | Speech-to-Text，语音转文字 |
| **TTS** | Text-to-Speech，文字转语音 |

### 8.3 文件结构速查

```
hermes-agent/
├── .env                    # 环境变量（API Key 等）
├── .env.example            # 环境变量模板
├── pyproject.toml          # Python 项目配置
├── uv.lock                 # 依赖锁定文件
├── cli-config.yaml.example # CLI 配置模板
├── hermes                  # CLI 启动脚本
├── cli.py                  # CLI 入口
├── run_agent.py            # 核心代理逻辑
├── model_tools.py          # 工具编排
├── toolsets.py             # 工具集定义
├── hermes_cli/             # CLI 子命令
│   ├── main.py             # 主入口
│   ├── commands.py         # 斜杠命令定义
│   ├── config.py           # 配置管理
│   └── ...
├── agent/                  # 代理内部模块
│   ├── anthropic_adapter.py
│   ├── bedrock_adapter.py
│   ├── memory_manager.py
│   └── ...
├── tools/                  # 工具实现
│   ├── registry.py         # 工具注册
│   ├── file_tools.py
│   ├── terminal_tool.py
│   └── ...
├── gateway/                # 消息网关
│   ├── run.py              # 网关主程序
│   └── platforms/          # 各平台适配器
├── plugins/                # 插件系统
├── skills/                 # 内置技能
├── tests/                  # 测试套件
└── docs/                   # 文档
```

### 8.4 更新日志

| 日期 | 内容 |
|------|------|
| 2026-06-07 | 创建本使用指南，完成本地部署 |

### 8.5 许可证

本项目采用 **MIT 许可证** 开源。详见 [LICENSE](https://github.com/NousResearch/hermes-agent/blob/main/LICENSE) 文件。

---

> **文档维护**：本指南基于 Hermes Agent v0.16.0 编写。随着项目更新，部分命令和配置可能有所变化，请以官方文档为准。
>
> **反馈建议**：如发现文档错误或遗漏，欢迎通过 GitHub Issues 或 Discord 社区反馈。
