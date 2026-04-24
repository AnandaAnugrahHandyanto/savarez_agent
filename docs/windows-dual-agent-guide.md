# Windows PowerShell 双 Agent 启动与管理指南

本文档面向在 Windows 原生环境（PowerShell 7+）同时运行两个 Hermes Agent 实例（`default` 和 `turing`）的用户，涵盖 Gateway、Web 仪表盘、Profile 管理以及常见告警处理。

相关前置文档：
- Windows 安装与环境配置：见 `D:\Code\hermes-agent-windows-R\README.md`
- 本仓库：`D:\Code\goldie-fork\hermes-agent`

---

## 目录

- [前置准备](#前置准备)
- [启动 default Agent](#启动-default-agent)
- [启动 turing Agent](#启动-turing-agent)
- [同时运行两个 Agent](#同时运行两个-agent)
- [Web 仪表盘访问](#web-仪表盘访问)
- [Agent / Profile 管理](#agent--profile-管理)
- [常见告警](#常见告警)
- [故障排查](#故障排查)

---

## 前置准备

### 激活虚拟环境

每个新开的 PowerShell 窗口都需要先激活一次：

```powershell
cd D:\Code\goldie-fork\hermes-agent
.\venv\Scripts\Activate.ps1
```

激活成功后提示符前会出现 `(venv)`。

> 若提示脚本执行被禁止：
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 确认前端已构建

Web 仪表盘默认由 Python 服务器托管构建后的静态文件，位于 `hermes_cli/web_dist/`。如果是首次运行或修改了前端，请先构建：

```powershell
cd web
npm install          # 首次安装依赖
npm run build
cd ..
```

此后只要不再改动前端，直接启动 Python 服务器即可，无需 `npm run dev`。

---

## 启动 default Agent

默认 profile 对应 `~/.hermes/`（即 `C:\Users\<用户名>\.hermes\`）。

### 1. 启动 Gateway（消息平台 + 定时任务）

```powershell
hermes gateway run
```

看到如下 banner 即代表成功：

```
┌─────────────────────────────────────────────────────────┐
│           ⚕ Hermes Gateway Starting...                 │
├─────────────────────────────────────────────────────────┤
│  Messaging platforms + cron scheduler                   │
│  Press Ctrl+C to stop                                   │
└─────────────────────────────────────────────────────────┘
```

> 只有在配置了 Telegram / Discord / Slack 等平台时才需要 Gateway。仅用 Web UI 聊天可以不启动。

### 2. 启动 Web 仪表盘

**新开一个 PowerShell 窗口**，激活虚拟环境后：

```powershell
python -m hermes_cli.main dashboard --no-open
```

输出：
```
→ Building web UI...
  ✓ Web UI built
  Hermes Web UI → http://127.0.0.1:9119
```

浏览器打开 `http://127.0.0.1:9119` 即可。

---

## 启动 turing Agent

turing profile 对应 `C:\Users\<用户名>\.hermes\profiles\turing\`。

### 方式一：`-p` 参数（推荐，不改默认 profile）

```powershell
hermes -p turing gateway run
```

### 方式二：通过 `HERMES_HOME` 环境变量

适合 Web 仪表盘场景，因为 `dashboard` 子命令本身不支持 `-p` 参数：

```powershell
$env:HERMES_HOME = "C:\Users\gotmo\.hermes\profiles\turing"
cd D:\Code\goldie-fork\hermes-agent
.\venv\Scripts\Activate.ps1
python -m hermes_cli.main dashboard --no-open --port 9120
```

> **注意端口要改**（例如 9120），避免和默认 9119 冲突。

输出：
```
Hermes Web UI → http://127.0.0.1:9120
```

> ⚠️ `$env:HERMES_HOME` 只在当前 PowerShell 会话有效。关闭窗口后失效。

### 方式三：设为默认 profile

```powershell
hermes profile use turing   # 切换
hermes gateway run          # 此时等同于 -p turing
hermes profile use default  # 用完切回
```

---

## 同时运行两个 Agent

典型场景：一个开 4 个 PowerShell 窗口，每个窗口跑一个进程。

| 窗口 | 任务 | 命令 |
|------|------|------|
| #1 | default Gateway | `hermes gateway run` |
| #2 | default Dashboard（端口 9119）| `python -m hermes_cli.main dashboard --no-open` |
| #3 | turing Gateway | `hermes -p turing gateway run` |
| #4 | turing Dashboard（端口 9120）| 见下方 |

**窗口 #4 的完整命令：**

```powershell
$env:HERMES_HOME = "C:\Users\gotmo\.hermes\profiles\turing"
cd D:\Code\goldie-fork\hermes-agent
.\venv\Scripts\Activate.ps1
python -m hermes_cli.main dashboard --no-open --port 9120
```

运行完成后：
- default Web UI → `http://127.0.0.1:9119`
- turing Web UI → `http://127.0.0.1:9120`

---

## Web 仪表盘访问

构建好前端后，Web UI 的所有功能（Status / Sessions / Chat / Analytics / Logs / Cron / Skills / Config / Keys）直接通过 Python 服务器提供，**不需要 Vite 开发服务器**。

### 何时需要 `npm run dev`

只有在**修改前端源码并希望热更新**时才使用：

```powershell
cd D:\Code\goldie-fork\hermes-agent\web
npm run dev
```

开发服务器会在 `http://localhost:5188` 启动。它需要一个后端实例作为数据源（默认指向 `http://127.0.0.1:9119`）。指向 turing：

```powershell
$env:HERMES_DASHBOARD_URL = "http://127.0.0.1:9120"
npm run dev
```

### Chat 页面

新增的 `/chat` 页面支持：
- 创建新会话 / 恢复旧会话（从 Sessions 页面点"打开"图标跳转 `?resume=<id>`）
- 流式助手输出、工具调用实时显示、中断正在运行的会话
- 斜杠命令：在输入框键入 `/` 会弹出命令列表

---

## Agent / Profile 管理

### 列出所有 Profile

```powershell
hermes profile list
```

输出示例：
```
 Profile      Model              Gateway      Alias
 ───────────    ───────────────    ───────────    ────────
 ◆default     glm-4.7            stopped      —
  turing      MiniMax-M2.7       stopped      turing
```

### 创建 Profile

```powershell
hermes profile create <名字> --clone   # 克隆 default 配置
hermes profile create <名字>           # 从空白开始
```

Profile 目录位于 `C:\Users\<用户名>\.hermes\profiles\<名字>\`，包含独立的 `config.yaml`、`.env`、`SOUL.md`、`state.db` 等。

### 查看 Profile 详情

```powershell
hermes profile show turing
```

### 重命名 / 删除

```powershell
hermes profile rename turing ada
hermes profile delete turing
```

> 删除操作会要求确认。Profile 目录下的所有数据（会话历史、技能、配置）都会被清除。

### 配置模型 / API Key

针对指定 profile 配置：

```powershell
hermes -p turing model        # 切换 LLM 模型
hermes -p turing setup        # 交互式配置 API key
hermes -p turing tools        # 管理工具开关
hermes -p turing doctor       # 诊断环境问题
hermes -p turing config set terminal.cwd "D:\Code\your-project"
```

### 切换默认 Profile

```powershell
hermes profile use turing     # 设为默认
hermes profile use default    # 切回
```

---

## 常见告警

### ⚠ TERMINAL_CWD 在 .env 中已废弃

启动时可能看到：

```
⚠ Deprecated .env settings detected:
  ⚠ TERMINAL_CWD=D:\Code\goldie-fork\hermes-agent found in .env — this is deprecated.
  Move to config.yaml instead:  terminal:
    cwd: /your/project/path
  Then remove the old entries from C:\Users\gotmo\.hermes\profiles\turing/.env
```

**含义：** Hermes 早期版本用 `.env` 里的 `TERMINAL_CWD` 指定 Agent 执行命令的默认工作目录。新版本改为通过 `config.yaml` 的 `terminal.cwd` 字段来配置，更统一、更结构化。

**解决步骤（针对 turing profile）：**

#### 1. 写入 `config.yaml`

最简单的方式：

```powershell
hermes -p turing config set terminal.cwd "D:\Code\goldie-fork\hermes-agent"
```

或手动编辑 `C:\Users\gotmo\.hermes\profiles\turing\config.yaml`，新增：

```yaml
terminal:
  cwd: D:\Code\goldie-fork\hermes-agent
```

> 路径使用 Windows 绝对路径即可。`tools/platform_compat.py` 内部会自动转成 `/d/Code/...` 的 MSYS 形式传给 Git Bash。

#### 2. 从 `.env` 移除旧条目

用编辑器打开 `C:\Users\gotmo\.hermes\profiles\turing\.env`，删除这一行：

```
TERMINAL_CWD=D:\Code\goldie-fork\hermes-agent
```

#### 3. 重启 Agent

关闭正在运行的 dashboard / gateway 后重新启动，告警就会消失。

> 对 default profile 同理，只是路径是 `C:\Users\<用户名>\.hermes\.env` 和 `config.yaml`。

---

## 故障排查

### Q: Chat 页面一直 "Connecting…"？

确认你访问的地址：
- `http://127.0.0.1:9119` 或 `:9120` → Python 服务器，直接可用
- `http://localhost:5188` → Vite 开发服务器，需要同时启动 Python dashboard 作为后端

Vite 开发服务器的 WebSocket 代理已在 `web/vite.config.ts` 中配置，启动前请确保对应的 dashboard 正在运行。

### Q: 端口 9119 已被占用？

```powershell
# 查找占用端口的进程
Get-NetTCPConnection -LocalPort 9119 | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Get-Process -Id $_ }

# 终止
taskkill /PID <pid> /F
```

或直接换端口：`--port 9121`。

### Q: `HERMES_HOME` 设错了怎么办？

```powershell
$env:HERMES_HOME = $null     # 清除当前会话的环境变量
```

或直接关闭 PowerShell 窗口重开。全局设置（非临时）需在"系统属性 → 环境变量"中修改。

### Q: Web UI 显示 "Frontend not built"？

```powershell
cd D:\Code\goldie-fork\hermes-agent\web
npm run build
```

构建产物会输出到 `D:\Code\goldie-fork\hermes-agent\hermes_cli\web_dist\`。

### Q: `hermes` 命令找不到？

虚拟环境未激活。执行：

```powershell
.\venv\Scripts\Activate.ps1
```

提示符出现 `(venv)` 后再试。

### Q: Sessions 页面点"打开"进不了 Chat？

确认 URL 形如 `http://127.0.0.1:9119/chat?resume=<session-id>`。如果历史记录没有展示，检查浏览器 DevTools → Network 中是否有 `/api/sessions/<id>/messages` 的请求被 401 拦截。通常是 session token 过期，刷新页面即可重新注入。

---

## 快速参考：完整启动流程

```powershell
# ── 窗口 1：default Gateway ──
cd D:\Code\goldie-fork\hermes-agent
.\venv\Scripts\Activate.ps1
hermes gateway run

# ── 窗口 2：default Web UI ──
cd D:\Code\goldie-fork\hermes-agent
.\venv\Scripts\Activate.ps1
python -m hermes_cli.main dashboard --no-open
# → http://127.0.0.1:9119

# ── 窗口 3：turing Gateway ──
cd D:\Code\goldie-fork\hermes-agent
.\venv\Scripts\Activate.ps1
hermes -p turing gateway run

# ── 窗口 4：turing Web UI ──
$env:HERMES_HOME = "C:\Users\gotmo\.hermes\profiles\turing"
cd D:\Code\goldie-fork\hermes-agent
.\venv\Scripts\Activate.ps1
python -m hermes_cli.main dashboard --no-open --port 9120
# → http://127.0.0.1:9120
```

---

## 相关文档

- `D:\Code\hermes-agent-windows-R\README.md` — Windows 原生安装指南（uv、虚拟环境、依赖安装）
- `WINDOWS_SUPPORT.md` — Windows 跨平台 helper 技术细节
- `website/docs/user-guide/features/web-dashboard.md` — Web 仪表盘功能说明
