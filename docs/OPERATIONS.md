# Hermes Agent — Tarball 构建与发布操作手册

> 适用于 ADA Desktop App 的轻量 tarball 构建与发布流程
> 
> 最后更新: 2026-05-06

---

## 目录

1. [架构概述](#架构概述)
2. [Tarball 规范](#tarball-规范)
3. [本地构建](#本地构建)
4. [CI 自动构建](#ci-自动构建)
5. [ADA 安装流程](#ada-安装流程)
6. [手动发布操作](#手动发布操作)
7. [故障排查](#故障排查)

---

## 架构概述

### 设计目标

将 Hermes Agent 的安装方式从 `curl | bash` 源码编译改为预构建 tarball 下载：

- **减少用户等待时间**: 从 10+ 分钟编译 → 30 秒下载解压
- **降低依赖风险**: 无需本地 Python/Node/Rust 工具链
- **统一分发渠道**: GitHub Releases 作为唯一下载源

### 组件关系

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub Releases                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  zhang-perry/hermes-agent                           │    │
│  │  ├── hermes-venv-darwin-arm64.tar.gz (27 MB)       │    │
│  │  ├── hermes-venv-darwin-arm64.tar.gz.sha256        │    │
│  │  ├── hermes-venv-darwin-x86_64.tar.gz              │    │
│  │  ├── hermes-venv-linux-x86_64.tar.gz (26 MB)       │    │
│  │  └── hermes-venv-linux-arm64.tar.gz (26 MB)        │    │
│  └─────────────────────────────────────────────────────┘    │
└────────────────────────────┬────────────────────────────────┘
                             │
         download + SHA256   │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     ADA Desktop App                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  install_hermes() in hermes.rs                       │    │
│  │  1. 检测平台 → tarball_filename()                    │    │
│  │  2. 备份旧 runtime/                                   │    │
│  │  3. 下载 tarball + .sha256                           │    │
│  │  4. 校验 SHA256                                      │    │
│  │  5. 解压到 runtime/hermes-agent/                    │    │
│  │  6. 验证 bin/hermes 可执行                           │    │
│  │  7. 更新 app state                                   │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Tarball 规范

### 命名规则

```
hermes-venv-{os}-{arch}.tar.gz
```

| 字段 | 取值 | 说明 |
|------|------|------|
| `os` | `darwin`, `linux` | 操作系统，`macos` 规范化为 `darwin` |
| `arch` | `arm64`, `x86_64` | CPU 架构，`aarch64` 规范化为 `arm64`，`x86_64` 保持原样 |

**示例**: `hermes-venv-darwin-arm64.tar.gz` = macOS Apple Silicon

### 目录结构

解压后顶层目录名固定为 `hermes-agent/`:

```
hermes-agent/
├── bin/
│   └── hermes          # 符号链接 → ../venv/bin/hermes
├── venv/               # Python 虚拟环境（含 [cron,pty,mcp,cli] extras）
│   ├── bin/
│   │   └── hermes      # 实际可执行文件
│   └── lib/
│       └── python3.XX/
│           └── site-packages/
├── src/                # Hermes 源码（用于 editable install）
│   ├── agent/
│   ├── gateway/
│   ├── tools/
│   ├── hermes_cli/
│   ├── pyproject.toml
│   └── ...
└── .build-version.json # 构建元数据
```

### 校验文件

每个 tarball 配套一个 `.sha256` 文件：

```
<sha256-hash>  hermes-venv-darwin-arm64.tar.gz
```

格式兼容 `shasum -c` 和 `sha256sum -c`。

### 大小预期

| 类型 | 大小 |
|------|------|
| Minimal tarball (仅 cron,pty,mcp,cli) | ~26-27 MB |
| 完整 tarball (所有 extras) | ~500 MB+ |

**注意**: 当前构建为 minimal 版本，仅包含 Gateway 必需依赖。

---

## 本地构建

### 前置条件

- Python 3.11+
- Git
- Hermes Agent 源码

### 构建命令

```bash
# 克隆 fork
git clone https://github.com/zhang-perry/hermes-agent.git
cd hermes-agent

# 构建当前平台
bash scripts/build-minimal-tarball.sh

# 构建指定平台
bash scripts/build-minimal-tarball.sh --target darwin-arm64
bash scripts/build-minimal-tarball.sh --target linux-x86_64

# 指定版本
bash scripts/build-minimal-tarball.sh --version 2026.5.6 --target darwin-arm64

# 指定输出目录
bash scripts/build-minimal-tarball.sh --output ./release-assets

# 自定义 extras
bash scripts/build-minimal-tarball.sh --extras "cron,pty,mcp"
```

### 构建参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--version` | 从 `pyproject.toml` 读取 | 覆盖版本号 |
| `--target` | 自动检测 | 目标平台 |
| `--output` | `./dist` | 输出目录 |
| `--extras` | `cron,pty,mcp,cli` | Pip extras |

### 构建产物

成功后在 `--output` 目录生成：

```
dist/
├── hermes-venv-darwin-arm64.tar.gz
└── hermes-venv-darwin-arm64.tar.gz.sha256
```

---

## CI 自动构建

### 触发方式

#### 方式 1: GitHub Release 发布

```bash
# 创建 tag 并发布 release
gh release create v2026.5.6 \
  --title "Hermes Agent v2026.5.6" \
  --notes "Release notes here"
```

CI 会自动为 4 个平台构建 tarball 并上传到 release。

#### 方式 2: 手动触发 (workflow_dispatch)

```bash
gh workflow run build-tarball-release.yml \
  -f version=2026.5.6
```

适用场景: 测试 CI、修复失败构建、无需发版时重新构建。

### 平台矩阵

| Job ID | Runner | Target | 状态 |
|--------|--------|--------|------|
| `build (macos-latest, darwin-arm64)` | `macos-latest` | darwin-arm64 | ✅ ~32s |
| `build (macos-13, darwin-x86_64)` | `macos-13` | darwin-x86_64 | ⚠️ 排队时间长 |
| `build (ubuntu-latest, linux-x86_64)` | `ubuntu-latest` | linux-x86_64 | ✅ ~31s |
| `build (ubuntu-24.04-arm, linux-arm64)` | `ubuntu-24.04-arm` | linux-arm64 | ✅ ~45s |

**注意**: `macos-13` (Intel runner) 在 GitHub Actions 免费版常有较长排队时间。

### CI 流程

1. **Checkout** - 拉取源码
2. **Setup Python 3.11** - 安装 Python
3. **Resolve version** - 确定 version 和 tag
4. **Build minimal tarball** - 执行 `build-minimal-tarball.sh`
5. **Ensure release exists** - (仅 workflow_dispatch) 创建 release
6. **Upload release assets** - 上传 tarball + .sha256

### 查看 CI 状态

```bash
# 列出最近的 workflow runs
gh run list -R zhang-perry/hermes-agent --workflow=build-tarball-release.yml

# 查看特定 run
gh run view <run-id> -R zhang-perry/hermes-agent

# 查看日志
gh run view --log -R zhang-perry/hermes-agent
```

---

## ADA 安装流程

### 路径约定

| 平台 | Runtime 目录 |
|------|--------------|
| macOS | `~/Library/Application Support/com.hermes.agent.desktop/runtime/` |
| Linux | `~/.local/share/com.hermes.agent.desktop/runtime/` |

二进制路径: `<runtime>/hermes-agent/bin/hermes`

### 安装步骤

```rust
// src-tauri/src/hermes.rs: install_hermes()

// Step 1: 检测平台
let tarball_name = tarball_filename();  // "hermes-venv-darwin-arm64.tar.gz"

// Step 2: 备份旧 runtime
backup_runtime_dir(&runtime_dir)  // → /tmp/hermes_runtime_backup_*

// Step 3: 下载 tarball
let tarball_url = format!("{}/{}", TARBALL_BASE_URL, tarball_name);
download_file(&tarball_url, &tarball_path).await;

// Step 4: SHA256 校验
let actual_hash = sha256_file(&tarball_path).await;
let expected_hash = fetch_tarball_sha256(&tarball_name).await;
assert_eq!(actual_hash, expected_hash);

// Step 5: 解压
extract_tarball(&tarball_path, &runtime_dir).await;

// Step 6: 验证
let hermes_binary = runtime_hermes_binary();  // <runtime>/hermes-agent/bin/hermes
assert!(hermes_binary.exists());
hermes_binary --version  // 测试可执行

// Step 7: 更新 app state
state.hermes_path = Some(hermes_binary);
```

### 版本检查

```bash
# ADA 调用 get_hermes_latest_version()
GET https://api.github.com/repos/zhang-perry/hermes-agent/releases/latest

# 返回
{
  "tag_name": "v2026.5.6",
  ...
}
```

### 更新检查

```rust
// src-tauri/src/hermes.rs: check_runtime_update()

let current_version = get_installed_version();
let latest_version = get_hermes_latest_version().await;
let update_available = compare_versions(latest_version, current_version) == Greater;
```

---

## 手动发布操作

### 发布新版本

```bash
# 1. 更新版本号
# 编辑 pyproject.toml: version = "2026.5.7"

# 2. 提交更改
git add pyproject.toml
git commit -m "chore: bump version to 2026.5.7"

# 3. 创建 tag
git tag v2026.5.7

# 4. 推送 tag
git push origin v2026.5.7

# 5. 创建 GitHub Release
gh release create v2026.5.7 \
  --title "Hermes Agent v2026.5.7" \
  --notes "## Changes
- Bug fix: ...
- Feature: ..."

# CI 会自动构建并上传 4 个平台的 tarball
```

### 手动上传 tarball

如果 CI 失败或需要替换资产：

```bash
# 构建
bash scripts/build-minimal-tarball.sh --target darwin-arm64

# 上传到已有 release
gh release upload v2026.5.6 \
  ./dist/hermes-venv-darwin-arm64.tar.gz \
  ./dist/hermes-venv-darwin-arm64.tar.gz.sha256 \
  --clobber
```

### 删除 release 和 tag

```bash
# 删除 release
gh release delete v2026.5.6 --yes

# 删除 tag
git push origin --delete v2026.5.6
git tag -d v2026.5.6
```

---

## 故障排查

### CI 排队时间长

**症状**: `macos-13` (darwin-x86_64) job 卡在 `queued` 状态超过 30 分钟。

**原因**: macOS Intel runner 在 GitHub Actions 免费版资源紧张。

**解决方案**:
1. 等待 (可能需要数小时)
2. 改用 `workflow_dispatch` 重新触发
3. 升级到 GitHub Team/Enterprise plan
4. 使用 self-hosted runner

### SHA256 校验失败

**症状**: ADA 安装时报错 "SHA256 校验失败"。

**可能原因**:
1. 下载不完整
2. Release 资产被覆盖但 .sha256 未更新
3. 网络劫持/中间人攻击

**解决方案**:
```bash
# 手动验证
curl -LO https://github.com/zhang-perry/hermes-agent/releases/latest/download/hermes-venv-darwin-arm64.tar.gz
curl -LO https://github.com/zhang-perry/hermes-agent/releases/latest/download/hermes-venv-darwin-arm64.tar.gz.sha256
shasum -a 256 -c hermes-venv-darwin-arm64.tar.gz.sha256

# 如果校验失败，重新上传
gh release upload v2026.5.6 ./dist/hermes-venv-*.tar.gz --clobber
```

### 安装后 hermes 无法运行

**症状**: `hermes: command not found` 或 `Permission denied`。

**检查步骤**:
```bash
# 检查二进制是否存在
ls -la ~/Library/Application\ Support/com.hermes.agent.desktop/runtime/hermes-agent/bin/hermes

# 检查符号链接
ls -la ~/Library/Application\ Support/com.hermes.agent.desktop/runtime/hermes-agent/bin/
# hermes -> ../venv/bin/hermes

# 检查可执行权限
chmod +x ~/Library/Application\ Support/com.hermes.agent.desktop/runtime/hermes-agent/venv/bin/hermes

# 手动测试
~/Library/Application\ Support/com.hermes.agent.desktop/runtime/hermes-agent/bin/hermes --version
```

### 版本检测失败

**症状**: ADA 显示 "无法获取最新版本"。

**原因**: GitHub API rate limit 或网络问题。

**解决方案**:
```bash
# 测试 API 可达性
curl -I https://api.github.com/repos/zhang-perry/hermes-agent/releases/latest

# 如果 404，检查仓库名称和 release 是否存在
gh release list -R zhang-perry/hermes-agent
```

### 本地构建失败

**症状**: `pip install` 报错。

**检查**:
```bash
# Python 版本
python3 --version  # 需要 3.11+

# 依赖安装
pip install -e ".[cron,pty,mcp,cli]"

# 清理后重试
rm -rf venv/ build/ *.egg-info
bash scripts/build-minimal-tarball.sh
```

---

## 附录

### 相关文件

| 文件 | 用途 |
|------|------|
| `scripts/build-minimal-tarball.sh` | 本地构建脚本 |
| `.github/workflows/build-tarball-release.yml` | CI workflow |
| `ada/src-tauri/src/hermes.rs` | ADA 安装逻辑 |
| `ada/src-tauri/src/paths.rs` | 路径抽象层 |

### 参考链接

- [GitHub Releases API](https://docs.github.com/en/rest/releases)
- [GitHub Actions Matrix Strategy](https://docs.github.com/en/actions/using-jobs/using-a-matrix-for-your-jobs)
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html)
- [Apple File System Programming Guide](https://developer.apple.com/library/archive/documentation/FileManagement/Conceptual/FileSystemProgrammingGuide/)
