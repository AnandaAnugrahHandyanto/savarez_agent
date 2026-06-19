# Development Guide — Savarez Agent

Savarez Agent is a fork of [Hermes Agent](https://github.com/NousResearch/hermes-agent). This guide covers local development setup.

## Architecture Overview

| Component | Technology | Location | Description |
|-----------|------------|----------|-------------|
| Python Runtime | Python 3.11+ | `hermes_cli/`, `agent/`, `tools/` | Core agent loop, tools, CLI |
| Gateway | Python (asyncio) | `gateway/` | Multi-platform messaging (Telegram, Discord, Slack, etc.) |
| Web Dashboard | React + Vite | `web/` | Browser-based UI for configuration and monitoring |
| TUI | Node.js + TypeScript | `ui-tui/` | Terminal user interface with PTY support |
| Tools / MCP | Python | `tools/`, `mcp/` | 40+ built-in tools, MCP server integration |

### Data Flow

```
User Input → CLI/Gateway → Agent Core → Model API → Tool Execution → Response
                                     ↓
                              Memory/Skills (SQLite/FTS5)
```

### Key Directories

```
savarez_agent/
├── hermes_cli/       # CLI entry point, config, gateway launcher
├── agent/            # Agent core: chat loop, tool dispatch, subagents
├── gateway/          # Platform adapters: Telegram, Discord, Slack, etc.
├── tools/            # Built-in tools: terminal, browser, file, web, etc.
├── web/              # React dashboard (Vite build)
├── ui-tui/           # Terminal UI (Node.js)
├── apps/             # Desktop app (Electron)
├── tests/            # Test suite
├── scripts/          # Build, install, test scripts
└── docs/             # Documentation sources
```

---

## Supported Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| Linux (x86_64) | ✅ Fully supported | Primary development platform |
| Linux (ARM) | ⚠️ Partial | Requires manual build tools setup |
| macOS | ✅ Fully supported | Uses uv for Python management |
| Windows (native) | ✅ Fully supported | PowerShell, no WSL required |
| Windows (WSL2) | ✅ Fully supported | Same as Linux |
| Termux (Android) | ⚠️ Partial | Uses venv + pip instead of uv |

---

## Required Tools

### Core Dependencies

| Tool | Version | Purpose | Required |
|------|---------|---------|----------|
| Python | >=3.11,<3.14 | Runtime | Yes |
| uv | Latest | Python dependency management | Yes |
| Node.js | >=20.0.0 | Frontend build, browser tools | Yes |
| npm | Bundled with Node.js | Frontend dependencies | Yes |
| git | 2.0+ | Version control | Yes |

### Optional Dependencies

| Tool | Purpose | Required |
|------|---------|----------|
| ripgrep | Fast search (memory, skills, sessions) | Recommended |
| ffmpeg | Audio/video processing, voice memo transcription | Optional |
| Docker | Container isolation for terminal backend | Optional |

### Python Version Constraint

The project requires Python `>=3.11,<3.14`. The upper bound exists because Rust-backed dependencies (e.g., `pydantic-core`) do not yet ship cp314 wheels. Without the cap, `uv` would attempt a source build that fails. Raise the ceiling once these dependencies ship cp314 wheels.

---

## Build Dependencies

Python packages with native extensions (e.g., `pydantic-core`, `cryptography`) require a C compiler and build tools to install from source.

### Debian / Ubuntu

```bash
sudo apt install build-essential python3-dev libffi-dev
```

### Arch Linux

```bash
pacman -S base-devel
```

This provides: `make`, `gcc`, `g++`, `binutils`, and other core build tools.

### Fedora / RHEL

```bash
sudo dnf groupinstall "Development Tools"
```

### Termux (Android)

```bash
pkg install clang rust make pkg-config libffi openssl ca-certificates curl
```

### Why These Are Needed

| Package | Reason |
|---------|--------|
| `make` | Required by `node-gyp` to compile native Node.js modules (e.g., `node-pty`) |
| `gcc` / `g++` | C/C++ compiler for native extensions |
| `python3-dev` | Python headers for C extensions (e.g., `pydantic-core`) |
| `libffi-dev` | Foreign function interface library (required by `cffi`) |

---

## Python Setup

### Using uv (Recommended)

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment
uv venv .venv --python 3.11

# Activate virtual environment
source .venv/bin/activate

# Install core dependencies
uv pip install -e ".'

# Install all dependencies (including optional extras)
uv pip install -e ".[all,dev]"
```

### Using venv + pip (Fallback)

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install core dependencies
pip install -e ".'

# Install all dependencies
pip install -e ".[all,dev]"
```

---

## Node.js Setup

### Install Dependencies

```bash
# Install all workspace dependencies
npm install

# Or install specific workspace only
npm install --workspace web
npm install --workspace ui-tui
```

### Verify Installation

```bash
node --version   # Should be >= 20.0.0
npm --version
```

---

## Build Commands

### Frontend (Dashboard/Web UI)

```bash
# Build web dashboard
npm run build -w web

# Type check
npm run typecheck -w web

# Run tests
npm run test -w web

# Lint
npm run lint -w web
```

### Full Build (All Workspaces)

```bash
npm install
npm run build --workspaces
```

---

## Testing

### Run Full Test Suite

```bash
# Using the canonical test runner
scripts/run_tests.sh

# With parallelism cap
scripts/run_tests.sh -j 4

# Single file
scripts/run_tests.sh tests/agent/test_example.py

# With pytest args
scripts/run_tests.sh -- -v --tb=long
```

### Run Tests Directly

```bash
# Ensure venv is activated
source .venv/bin/activate

# Run pytest
pytest tests/

# Run specific test file
pytest tests/agent/test_example.py -v
```

---

## Upstream Sync Workflow

Savarez Agent tracks the upstream Hermes Agent repository. When syncing:

```bash
# Fetch latest upstream changes
git fetch upstream

# Merge into current branch
git merge upstream/main

# Resolve any conflicts (if they occur)
# ...

# Verify after merge
hermes --version
python -m py_compile hermes_cli/main.py
scripts/run_tests.sh
```

### Branding Rules

Before making any branding changes, read `REBRANDING_RULES.md` in the repository root. It defines:

- **SAFE TO REBRAND**: User-facing text, documentation, metadata
- **KEEP AS UPSTREAM**: Internal modules, import paths, env vars, HTTP headers
- **REVIEW REQUIRED**: CLI commands, config filenames, package names

Never rebrand internal Python modules, import paths, or runtime identifiers. See `REBRANDING_RULES.md` for the full classification.

---

## Common Problems

### `npm install` Fails — Missing `make`

**Symptom:**
```
gyp ERR! build error
gyp ERR! stack Error: `make` failed
```

**Cause:** `node-gyp` requires `make` to compile native modules like `node-pty`.

**Fix:**
```bash
# Debian/Ubuntu
sudo apt install build-essential

# Arch Linux
pacman -S base-devel

# Fedora
sudo dnf install make gcc gcc-c++
```

### `npm install` Fails — Missing `gcc`

**Symptom:**
```
gyp ERR! stack Error: not found: `gcc`
```

**Fix:** Install build tools (see above).

### Python Package Build Fails — Missing `python3-dev`

**Symptom:**
```
error: command 'gcc' failed
fatal error: Python.h: No such file or directory
```

**Fix:**
```bash
# Debian/Ubuntu
sudo apt install python3-dev

# Arch Linux (usually included)
pacman -S python
```

### `node-pty` Build Fails

**Symptom:**
```
gyp ERR! build error
gyp ERR! stack Error: `make` failed
```

**Cause:** `node-pty` is a native Node.js module that requires `make` and a C compiler.

**Fix:** Install build tools (see "Missing make" above).

### Python Version Too High

**Symptom:**
```
ERROR: No matching distribution found for pydantic-core==...
```

**Cause:** Project requires Python >=3.11,<3.14. Python 3.14+ lacks wheels for some dependencies.

**Fix:**
```bash
# Use uv to install correct Python version
uv venv .venv --python 3.11
```

### Missing Node.js

**Symptom:**
```
sh: line 1: node: command not found
```

**Fix:**
```bash
# Install Node.js (via nvm recommended)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
nvm install 20
nvm use 20
```

---

## Verification Commands

After setup, verify your environment:

```bash
python --version    # Should show 3.11.x (>=3.11,<3.14)
node --version      # Should show >= 20.0.0
npm --version       # Any recent version
git --version       # Any recent version
uv --version        # Any recent version
```

### Verify Python Environment

```bash
source .venv/bin/activate
python -c "import hermes_cli; print('hermes_cli OK')"
python -m py_compile hermes_cli/main.py
```

### Verify Node.js Environment

```bash
node -e "console.log('Node.js OK')"
npm ls --depth=0
```

### Verify Full Stack

```bash
hermes --version
hermes --help
```

---

## IDE Setup

### VS Code

Recommended extensions:
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- ESLint (dbaeumer.vscode-eslint)
- Tailwind CSS IntelliSense (bradlc.vscode-tailwindcss)

### Python Interpreter

Point your IDE to `.venv/bin/python` after creating the virtual environment.
