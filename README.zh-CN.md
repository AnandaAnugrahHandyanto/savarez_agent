# Hermes Agent 中文说明

Hermes Agent 是 Nous Research 开源的通用型 AI Agent 框架。它不是单纯的“聊天壳”或单模型调用器，而是一个围绕长期运行、自主工具调用、跨会话记忆、技能沉淀、消息平台接入和定时自动化构建的完整代理系统。

它的目标不是只在一台笔记本上跑一个临时会话，而是把 Agent 变成一个可以持续工作的“数字执行体”：

- 能在本地终端里直接对话
- 能接入 Telegram、Discord、Slack、WhatsApp、Signal 等消息平台
- 能调用终端、浏览器、Web、文件、MCP 等工具
- 能把经验沉淀成技能和记忆
- 能按计划自动执行任务
- 能在本机、Docker、SSH 远端、Modal、Daytona 等环境中运行

如果你把它理解成“一个可扩展、可持久化、可接入多平台的 Agent 操作系统”，会比把它理解成“另一个命令行聊天程序”更接近这个项目的真实定位。

---

## 1. 项目是做什么的

Hermes Agent 的核心是一个名为 `AIAgent` 的代理执行循环。用户输入一条指令后，它会完成下面这些步骤：

1. 组装系统提示词
2. 读取配置、人格、记忆、技能和上下文文件
3. 选择当前 LLM 提供商和模型
4. 把请求发送给模型
5. 如果模型决定调用工具，就分发到对应工具执行
6. 把工具结果继续送回模型
7. 生成最终回复，并把会话存入本地状态库

这个项目和很多“只会调用 API 再输出结果”的项目不同，重点在于它围绕 Agent 的长期使用做了很多工程化能力：

- 持久化会话和全文检索
- 长期记忆和用户建模
- 技能系统与技能自改进
- 多平台消息网关
- 定时任务
- 子代理并行委派
- 多种终端执行后端
- MCP 集成
- 编辑器 ACP 集成
- 用于研究和 RL 训练的数据/环境支持

简化来说：

- 如果你只想在终端里和 Agent 对话，它可以当 CLI Agent 用
- 如果你想把它部署成长期在线 Bot，它可以当消息网关用
- 如果你想把它接进编辑器，它可以当 ACP Server 用
- 如果你想做轨迹收集、评测和训练，它也提供研究侧能力

---

## 2. 核心特性

### 2.1 自改进与技能沉淀

Hermes Agent 的一个主打点是“闭环学习”：

- 能把复杂任务的经验沉淀为技能
- 能在使用过程中更新技能
- 能保存长期记忆
- 能检索历史会话
- 能跨会话逐步形成对用户的理解

这让它更像一个“会积累经验的 Agent”，而不是每次都从零开始的聊天机器人。

### 2.2 工具调用能力

项目内置了大量工具和工具集，覆盖：

- 终端命令执行
- 文件读写与补丁修改
- Web 搜索与网页提取
- 浏览器自动化
- 代码执行
- 委派给子代理
- MCP 服务
- 图像、音频、记忆等扩展能力

它不是把工具写死在单一运行环境里，而是通过统一注册表和工具分发层来组织这些能力。

### 2.3 多平台入口

Hermes 的入口不止一个：

- CLI 终端界面
- 消息网关
- ACP 编辑器接入
- 批量轨迹生成

因此同一个 Agent 核心可以被不同界面复用，而不是每个平台各写一套逻辑。

### 2.4 定时自动化

Hermes 自带 `cron` 调度能力，能执行“Agent 任务”而不是单纯 Shell 脚本。例如：

- 每天早上汇总新闻
- 每周做代码库巡检
- 每晚备份某些数据
- 定时向 Telegram 或 Discord 推送结果

### 2.5 多运行环境

它不仅能在当前机器本地执行，还支持把终端执行后端切到：

- 本地环境
- Docker
- SSH 远端
- Daytona
- Modal
- Singularity

这使得 Agent 可以在隔离环境、远端机器或近似无服务器环境里工作。

---

## 3. 适合哪些场景

Hermes Agent 比较适合下面几类用途：

- 个人长期助理：持续记住配置、偏好、常用流程
- 编程助手：终端、文件、浏览器、脚本联动
- 远程运维代理：接入 SSH、Docker、消息平台
- 企业内部自动化：定时巡检、日报、告警整理
- 研究和训练：生成轨迹、运行 RL 环境、做评测
- 编辑器集成：作为 ACP Agent 接入 VS Code / Zed / JetBrains

如果你要的是“开箱即用、可持续运行、工具能力很强、可扩展”的 Agent 框架，它是合适的。

如果你只是想跑一个最轻量的单轮对话脚本，这个项目会显得偏重。

---

## 4. 项目架构总览

从代码组织看，这个项目大致可以分成几层：

### 4.1 入口层

- `cli.py`
- `hermes_cli/main.py`
- `gateway/run.py`
- `acp_adapter/`
- `batch_runner.py`

这些入口负责接收不同渠道的输入，但最终都会汇入同一个 Agent 核心。

### 4.2 Agent 核心层

- `run_agent.py`
- `agent/prompt_builder.py`
- `agent/context_compressor.py`
- `agent/prompt_caching.py`
- `agent/auxiliary_client.py`

这层负责：

- 组装系统提示词
- 选择模型和 provider
- 控制会话循环
- 管理上下文压缩
- 处理缓存、辅助模型和显示逻辑

### 4.3 工具系统

- `model_tools.py`
- `toolsets.py`
- `tools/registry.py`
- `tools/*.py`
- `tools/environments/*`

这层负责：

- 工具注册
- 参数 schema 收集
- 工具调用分发
- 后端环境切换
- 安全检查和结果包装

### 4.4 状态与持久化

- `hermes_state.py`
- `gateway/session.py`

这层负责：

- 会话存储
- 全文搜索
- 会话谱系管理
- 平台隔离

### 4.5 网关和平台适配

- `gateway/`
- `gateway/platforms/`

这层负责：

- 平台消息收发
- 用户授权
- 会话路由
- 钩子系统
- 状态跟踪

### 4.6 扩展层

- `plugins/`
- `plugins/memory/`
- `skills/`
- `optional-skills/`
- `cron/`
- `acp_adapter/`
- `environments/`

这层承担插件、技能、调度、研究环境等扩展能力。

---

## 5. 主要目录说明

下面是使用者最常接触的目录：

| 路径 | 作用 |
|------|------|
| `run_agent.py` | 核心代理循环 |
| `cli.py` | 终端交互界面 |
| `hermes_cli/` | `hermes` 命令的大部分实现 |
| `tools/` | 内置工具实现 |
| `gateway/` | 消息平台网关 |
| `cron/` | 定时任务 |
| `acp_adapter/` | ACP 编辑器集成 |
| `plugins/` | 插件系统 |
| `skills/` | 内置技能 |
| `optional-skills/` | 可选官方技能 |
| `website/` | 官方文档站源码 |
| `tests/` | 测试 |
| `Dockerfile` | 官方容器镜像构建文件 |
| `cli-config.yaml.example` | 配置模板 |
| `.env.example` | 环境变量模板 |

---

## 6. 运行方式

Hermes Agent 常见有三种使用方式。

### 6.1 方式一：本机 CLI 交互

直接运行：

```bash
hermes
```

适合：

- 本地开发
- 快速试用
- 终端型工作流

### 6.2 方式二：消息网关常驻

运行网关后，可以从 Telegram、Discord、Slack、WhatsApp、Signal 等平台和它交互：

```bash
hermes gateway run
```

适合：

- 让 Agent 长时间在线
- 远程从手机或聊天工具访问
- 定时任务推送

### 6.3 方式三：Docker 容器部署

Agent 本身运行在容器内，宿主机只保存数据目录。

适合：

- 本地隔离部署
- 小型服务器常驻
- 方便升级和迁移

---

## 7. 依赖与环境要求

根据项目配置和安装文档，推荐环境如下：

- 操作系统：Linux、macOS、WSL2
- 不支持：原生 Windows
- Python：建议 3.11
- Node.js：用于浏览器自动化和 WhatsApp bridge
- Git：必须
- 可选系统工具：`ripgrep`、`ffmpeg`

需要注意两点：

1. `pyproject.toml` 里声明的是 `requires-python = ">=3.11"`，但官方安装流程固定使用 Python 3.11，说明 3.11 是主要测试路径。
2. Node.js 主要用于浏览器自动化和 WhatsApp 相关能力。如果你只需要基础 CLI，对 Node 依赖没那么强，但官方完整安装仍然会把它一起装好。

---

## 8. 从源码安装到本机

这是最适合开发和本地使用的方式，也是你当前已经克隆源码之后最应该走的路径。

### 8.1 初始化子模块

仓库里有一个子模块：

- `tinker-atropos`

它主要用于 RL / Atropos 相关能力，不是普通 CLI 使用的硬依赖，但建议同步初始化，避免后续某些功能缺件：

```bash
git submodule update --init --recursive
```

### 8.2 安装 uv

如果本机还没有 `uv`：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 8.3 创建虚拟环境

建议在项目目录下创建专用虚拟环境，并明确使用 Python 3.11：

```bash
cd hermes-agent
uv venv venv --python 3.11
export VIRTUAL_ENV="$(pwd)/venv"
```

如果你系统里没有 Python 3.11，`uv` 会自动下载。

### 8.4 安装 Python 依赖

完整安装：

```bash
uv pip install -e ".[all]"
```

如果你只想跑最小核心：

```bash
uv pip install -e "."
```

常见可选 extras：

- `messaging`：Telegram / Discord 等消息平台
- `cron`：定时任务
- `cli`：终端菜单界面
- `voice`：语音输入输出
- `mcp`：MCP 支持
- `acp`：编辑器 ACP 支持
- `dev`：测试与开发依赖

例如只装你最可能用到的：

```bash
uv pip install -e ".[cli,messaging,cron,mcp]"
```

### 8.5 安装 Node 依赖

如果你需要浏览器自动化或 WhatsApp bridge：

```bash
npm install
```

如果你后续还要用 Playwright/浏览器工具，通常还需要浏览器运行时：

```bash
npx playwright install --with-deps chromium
```

在 macOS 上，`--with-deps` 的系统依赖部分不会像 Linux 那样完整生效，但安装 Chromium 本体仍然是有用的。

### 8.6 创建 Hermes 数据目录

```bash
mkdir -p ~/.hermes/{cron,sessions,logs,memories,skills,pairing,hooks,image_cache,audio_cache,whatsapp/session}
cp cli-config.yaml.example ~/.hermes/config.yaml
touch ~/.hermes/.env
```

### 8.7 配置 API Key

至少要有一个模型提供商的密钥。最简单是编辑：

```bash
~/.hermes/.env
```

例如：

```bash
OPENROUTER_API_KEY=sk-or-v1-your-key
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=sk-ant-your-key
```

也可以通过命令设置：

```bash
hermes config set OPENROUTER_API_KEY sk-or-v1-your-key
```

### 8.8 把 `hermes` 命令加入 PATH

```bash
mkdir -p ~/.local/bin
ln -sf "$(pwd)/venv/bin/hermes" ~/.local/bin/hermes
```

如果 `~/.local/bin` 还没进 PATH，在 `~/.zshrc` 里加入：

```bash
export PATH="$HOME/.local/bin:$PATH"
```

然后重新加载：

```bash
source ~/.zshrc
```

### 8.9 验证安装

```bash
hermes version
hermes doctor
hermes status
hermes chat -q "Hello"
```

只要 `hermes doctor` 没有关键报错，基本就能正常用了。

---

## 9. 如何“编译”这个项目

这个项目本质上是 Python 应用，不是传统意义上需要复杂编译链的 C/C++ 项目。对大多数用户来说，所谓“编译”其实就是：

1. 创建虚拟环境
2. 安装依赖
3. 用 `-e` 可编辑方式安装项目
4. 准备配置和 API Key
5. 运行 `hermes`

也就是说，日常使用并不需要额外生成二进制文件。

### 9.1 你真正需要的“构建”方式

最常用：

```bash
uv venv venv --python 3.11
export VIRTUAL_ENV="$(pwd)/venv"
uv pip install -e ".[all]"
```

这就是本项目最标准的本地构建/安装流程。

### 9.2 如果你要打包成 wheel / sdist

如果你的需求是分发安装包，而不是自己本机使用，可以额外安装构建工具后打包：

```bash
uv pip install build
python -m build
```

产物通常会出现在：

```bash
dist/
```

但对普通用户来说，这一步不是必须的。

### 9.3 Docker 镜像构建

如果你要构建容器镜像，这也可以视为另一种“编译/构建”：

```bash
docker build -t hermes-agent-local .
```

这个 Dockerfile 会：

- 安装 Python、Node.js、ripgrep、ffmpeg 等系统依赖
- 执行 `pip install -e ".[all]"`
- 执行 `npm install`
- 安装 Playwright 的 Chromium
- 把数据目录挂载到 `/opt/data`

---

## 10. 如何部署到本机

“部署到本机”通常有两种理解：源码部署到当前机器，或者容器部署到当前机器。下面都给出。

### 10.1 方案一：源码方式部署到本机

这是最适合你当前场景的方式。

#### 启动 CLI

```bash
cd /你的/hermes-agent/目录
source venv/bin/activate
hermes
```

或者不激活 venv，直接用：

```bash
./venv/bin/hermes
```

#### 首次配置模型

```bash
hermes model
```

#### 运行完整配置向导

```bash
hermes setup
```

#### 常用命令

```bash
hermes
hermes --continue
hermes model
hermes tools
hermes gateway setup
hermes gateway run
hermes doctor
hermes update
```

### 10.2 方案二：本机 Docker 部署

先准备数据目录：

```bash
mkdir -p ~/.hermes
```

首次交互式初始化：

```bash
docker run -it --rm \
  -v ~/.hermes:/opt/data \
  hermes-agent-local setup
```

配置完成后，后台常驻运行网关：

```bash
docker run -d \
  --name hermes \
  --restart unless-stopped \
  -v ~/.hermes:/opt/data \
  hermes-agent-local gateway run
```

如果只是想临时进入 CLI：

```bash
docker run -it --rm \
  -v ~/.hermes:/opt/data \
  hermes-agent-local
```

### 10.3 方案三：本机作为宿主，Docker 仅作为终端沙箱

这和“把 Hermes 整体跑在 Docker 里”不同。这里是 Agent 跑在宿主机上，但它执行 Shell 命令时用 Docker 隔离。

配置方式大致是：

```bash
hermes config set terminal.backend docker
```

适合：

- 想在本机跑 Hermes
- 但不想让 Agent 直接在宿主机执行命令

---

## 11. 首次使用建议

如果你只是想尽快用起来，建议按下面顺序：

1. 用源码方式安装到本机
2. 配一个最熟悉的 LLM provider
3. 运行 `hermes doctor`
4. 先用 CLI 测试
5. 确认基础功能没问题后再配置消息网关
6. 最后再启用浏览器、MCP、语音、自动化等扩展

不要一开始就把所有平台、所有工具、所有功能都开起来。这个项目功能面很大，先跑通最小闭环更有效率。

---

## 12. 常见配置文件和数据目录

Hermes 的默认数据根目录是：

```bash
~/.hermes
```

常见内容包括：

| 路径 | 说明 |
|------|------|
| `~/.hermes/.env` | API Key 和敏感配置 |
| `~/.hermes/config.yaml` | 主配置文件 |
| `~/.hermes/SOUL.md` | Agent 人格/系统身份 |
| `~/.hermes/sessions/` | 会话记录 |
| `~/.hermes/memories/` | 记忆数据 |
| `~/.hermes/skills/` | 已安装技能 |
| `~/.hermes/cron/` | 定时任务 |
| `~/.hermes/logs/` | 日志 |
| `~/.hermes/hooks/` | Hook |

如果你后续要备份 Hermes，优先备份这个目录。

---

## 13. 常见问题

### 13.1 为什么我已经有 Python 3.13，还建议创建 3.11 虚拟环境

因为项目文档和安装脚本明确把 3.11 作为标准安装版本。虽然 `pyproject.toml` 允许 `>=3.11`，但“能安装”和“官方主路径充分验证”不是一回事。为了减少不必要的问题，优先用 3.11。

### 13.2 为什么需要 Node.js

主要是：

- 浏览器自动化
- WhatsApp bridge
- 一些前端/运行时相关工具

如果你只用基础 CLI，对 Node.js 的依赖感知会弱一些，但完整能力需要它。

### 13.3 这个项目必须用 Docker 吗

不是。Docker 是可选部署方式，也可以作为终端后端。最简单的本机用法仍然是源码安装后直接运行 `hermes`。

### 13.4 子模块一定要装吗

不是强制。`tinker-atropos` 主要和 RL / Atropos 相关，对普通 CLI 使用不是硬阻塞。但为了保持仓库完整，建议初始化。

### 13.5 为什么 `hermes` 能跑，但某些工具不可用

通常是以下几类原因：

- 没装对应 extras
- 没有配置 API Key
- 没装 Node / Playwright
- 没有启用对应工具集
- 当前模型或平台不支持该能力

优先运行：

```bash
hermes doctor
hermes tools
hermes status
```

---

## 14. 推荐的最小可用本机安装流程

如果你只想要一套最务实、最少绕路的本机部署步骤，直接执行下面这些命令：

```bash
git submodule update --init --recursive
uv venv venv --python 3.11
export VIRTUAL_ENV="$(pwd)/venv"
uv pip install -e ".[all]"
npm install
mkdir -p ~/.hermes/{cron,sessions,logs,memories,skills,pairing,hooks,image_cache,audio_cache,whatsapp/session}
cp cli-config.yaml.example ~/.hermes/config.yaml
touch ~/.hermes/.env
mkdir -p ~/.local/bin
ln -sf "$(pwd)/venv/bin/hermes" ~/.local/bin/hermes
```

然后：

1. 在 `~/.hermes/.env` 填入至少一个模型厂商的 API Key
2. 运行 `source ~/.zshrc`
3. 运行 `hermes model`
4. 运行 `hermes doctor`
5. 运行 `hermes`

这条路径是当前仓库最直接、最接近官方文档的本地可用方案。

---

## 15. 总结

Hermes Agent 是一个面向长期运行和工程扩展的 AI Agent 平台，而不是只服务于一次性对话的轻量脚本。它把模型调用、工具系统、持久记忆、消息平台、自动化调度、远端执行和研究环境放进了同一套体系里。

对普通使用者来说，最合理的上手方式不是研究所有模块，而是先把源码安装、本地 CLI、模型配置和基本工具调用跑通。等最小闭环稳定后，再逐步打开消息网关、Docker 隔离、MCP、语音和定时任务。

如果你的目标是“在本机先稳定用起来”，优先走源码安装 + `hermes model` + `hermes doctor` + `hermes` 这条路线，不要一开始就把部署复杂度抬高。
