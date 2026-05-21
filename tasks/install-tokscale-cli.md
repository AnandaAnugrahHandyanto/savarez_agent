# 安装 @tokscale/cli — 技术任务包

## 1. 包信息

| 项目 | 值 |
|------|-----|
| **包名** | `@tokscale/cli` |
| **最新版本** | `2.1.3` |
| **许可证** | MIT |
| **GitHub** | https://github.com/junhoyeo/tokscale |
| **描述** | AI 编码助手 token 用量追踪 CLI + 可视化仪表盘，支持多个平台（Claude Code, Cursor, Gemini, Codex, OpenCode 等） |

## 2. 架构分析

**@tokscale/cli 是一个「JS 包装器 + Rust 原生二进制」的混合包：**

- **入口** `bin.js` — 一个简单的 Node.js 脚本（2 行），执行 `await import("./dist/index.js")`
- **核心逻辑** `dist/index.js` — 检测当前平台（macOS arm64 / x64, Linux glibc/musl, Windows），定位并 spawn 原生 Rust 二进制
- **原生二进制** — 通过 `optionalDependencies` 分发平台特定包

**平台特定 optionalDependencies（版本 2.1.3）：**

| 包名 | 对应平台 |
|------|---------|
| `@tokscale/cli-darwin-arm64` | macOS ARM64 (Apple Silicon) |
| `@tokscale/cli-darwin-x64` | macOS x64 (Intel) |
| `@tokscale/cli-linux-x64-gnu` | Linux x64 (glibc) |
| `@tokscale/cli-linux-x64-musl` | Linux x64 (musl) |
| `@tokscale/cli-linux-arm64-gnu` | Linux ARM64 (glibc) |
| `@tokscale/cli-linux-arm64-musl` | Linux ARM64 (musl) |
| `@tokscale/cli-win32-x64-msvc` | Windows x64 |
| `@tokscale/cli-win32-arm64-msvc` | Windows ARM64 |

**依赖情况：**
- **Runtime dependencies**：无（`dependencies: {}`）
- **Native 依赖**：通过 optionalDependencies 分发 Rust 预编译二进制，无需本地 Rust 工具链

## 3. 安装方式

### 3.1 推荐方式：npm global install（已验证可行）

```bash
npm install -g @tokscale/cli
```

或指定 prefix：

```bash
npm install -g @tokscale/cli --prefix ~/.npm-global
```

### 3.2 不需要的操作

- ❌ 不需要安装 Rust/cargo
- ❌ 不需要 Homebrew 包
- ❌ 不需要从源码编译

### 3.3 环境检查前置条件

```bash
# 确认 Node.js 版本（需 >= 18）
node --version   # 当前: v24.14.1 ✅

# 确认 npm 版本
npm --version    # 当前: 11.11.0 ✅

# 确认 npm global prefix 和 PATH
npm config get prefix
# → /Users/gu/.hermes/profiles/maldini/home/.npm-global
#    （这是 .npmrc 中配置的 prefix）

# 确认 global bin 目录在 PATH 中
echo $PATH | tr ':' '\n' | grep npm-global
# → /Users/gu/.npm-global/bin  ✅（在 PATH 中）
```

### 3.4 关于 PATH 的说明

当前环境存在一个**路径不一致**的情况，需要注意：

| 路径 | 说明 |
|------|------|
| `~/.npmrc` 配置的 prefix | `/Users/gu/.hermes/profiles/maldini/home/.npm-global` |
| PATH 中包含的路径 | `/Users/gu/.npm-global/bin` |

这两个是不同的目录。目前所有的 global 工具（repomix, openclaw 等）实际上安装在 `~/.npm-global` 下。

**应对方法：安装时使用 `--prefix ~/.npm-global`**，确保二进制链接到正确的 PATH 目录：

```bash
npm install -g @tokscale/cli --prefix /Users/gu/.npm-global
```

## 4. 安装步骤

```bash
# Step 1: 全局安装
npm install -g @tokscale/cli --prefix /Users/gu/.npm-global

# Step 2: 确认二进制 symlink 已创建
ls -la /Users/gu/.npm-global/bin/ | grep tokscale
# 期望输出: tokscale -> ../lib/node_modules/@tokscale/cli/bin.js

# Step 3: 验证 native 依赖已安装
ls /Users/gu/.npm-global/lib/node_modules/@tokscale/cli/node_modules/@tokscale/cli-darwin-arm64/bin/tokscale
# 期望: 文件存在且为可执行 Mach-O 二进制
```

## 5. 验证步骤

### 5.1 基础验证

```bash
# 版本号
tokscale --version
# 期望输出: tokscale 2.1.3

# 帮助
tokscale --help
# 期望: 显示完整的命令列表和选项
```

### 5.2 功能验证

```bash
# 查看本地客户端扫描位置
tokscale clients

# 快速查看模型使用报告（禁用 spinner 避免超时）
tokscale models --no-spinner --light

# 查看 JSON 格式的月报
tokscale monthly --no-spinner --json

# 查看定价信息
tokscale pricing claude-sonnet-4-20250514
```

### 5.3 深入了解

```bash
# 查看登录状态
tokscale whoami

# 查看图表数据
tokscale graph --json

# 交互式 TUI（需终端支持）
tokscale tui
```

## 6. 可用的子命令

| 命令 | 说明 |
|------|------|
| `models` | 按模型显示用量报告 |
| `monthly` | 按月显示用量报告 |
| `hourly` | 按小时显示用量报告 |
| `pricing` | 查询模型定价 |
| `clients` | 显示本地扫描路径及 session 数量 |
| `login` | 登录 Tokscale（打开浏览器进行 GitHub 认证） |
| `logout` | 登出 |
| `whoami` | 显示当前登录用户 |
| `graph` | 导出贡献图 JSON 数据 |
| `tui` | 启动交互式 TUI |
| `submit` | 向 Tokscale 社交平台提交用量数据 |
| `headless` | 捕获子进程输出的 token 用量 |
| `wrapped` | 生成年度回顾图片 |
| `cursor` | Cursor IDE 集成命令 |
| `antigravity` | Antigravity 集成命令 |
| `delete-submitted-data` | 删除所有已提交的用量数据 |

## 7. 已知问题 / 注意事项

### 7.1 Rust 原生二进制未签名（macOS 安全策略）

该 Rust 二进制**未进行 codesign / notarization**。在某些 macOS 安全配置下（尤其 macOS 26+），直接运行二进制时可能被 Gatekeeper 杀死（"Killed: 9" / SIGKILL）。

**已验证**：在本次测试环境中通过 `npm install -g` 安装后，通过 JS 包装器（`tokscale --help`）可以正常调用，二进制被成功执行。如果遇到 "Killed: 9" 错误，需要手动对二进制进行签名：

```bash
# 如果遇到 killed: 9 错误，手动签名
codesign --force --sign - \
  /Users/gu/.npm-global/lib/node_modules/@tokscale/cli/node_modules/@tokscale/cli-darwin-arm64/bin/tokscale
```

### 7.2 npm prefix 与 PATH 不一致

如 3.4 节所述，`.npmrc` 中的 prefix 指向 Hermes 隔离路径，但 PATH 指向 `~/.npm-global/bin`。后续所有 npm global 安装**必须加上 `--prefix ~/.npm-global`**，否则二进制将无法在 PATH 中找到。

## 8. 验收标准

| # | 验收项 | 期望结果 |
|---|--------|---------|
| 1 | `npm install -g @tokscale/cli` 安装成功 | 无错误，返回 success |
| 2 | `~/.npm-global/bin/tokscale` symlink 存在 | 指向 `../lib/node_modules/@tokscale/cli/bin.js` |
| 3 | `tokscale --version` 正常输出 | `tokscale 2.1.3` |
| 4 | `tokscale --help` 正常输出帮助信息 | 显示所有子命令和选项 |
| 5 | `tokscale clients` 可执行 | 显示本地扫描路径 |
| 6 | `tokscale models --no-spinner --light` 可执行 | 显示模型用量报告（可能较慢） |
| 7 | `tokscale pricing claude-sonnet-4-20250514` 正常 | 返回模型定价信息 |
| 8 | 原生二进制 `tokscale` (Mach-O) 可被 Node 包装器正确调用 | 无 "Killed: 9" 错误 |

## 9. 快速安装脚本

```bash
#!/bin/bash
set -e

echo "==> 安装 @tokscale/cli..."
npm install -g @tokscale/cli --prefix /Users/gu/.npm-global

echo "==> 验证安装..."
which tokscale && tokscale --version

echo "==> 安装完成!"
echo "使用 tokscale --help 查看帮助"
echo "使用 tokscale login 登录（需要 GitHub 认证）"
```
