---
sidebar_position: 2
title: "Installation"
description: "Install Hermes Agent on Linux, macOS, WSL2, native Windows (early beta), or Android via Termux"
---

# Installation

Get Hermes Agent up and running in under two minutes with the one-line installer.

## Quick Install

### Linux / macOS / WSL2

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

### Windows (native, PowerShell) — Early Beta

:::warning Early BETA
Native Windows support is **early beta**. It installs and works for the common paths, but hasn't been road-tested as broadly as our POSIX installers. Please [file issues](https://github.com/NousResearch/hermes-agent/issues) when you hit rough edges. For the most battle-tested setup on Windows today, use the Linux/macOS one-liner above inside **WSL2** instead.
:::

Open PowerShell and run:

```powershell
irm https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.ps1 | iex
```

The installer handles **everything**: `uv`, Python 3.11, Node.js 22, `ripgrep`, `ffmpeg`, **and a portable Git Bash** (MinGit — a slim, self-contained Git for Windows distribution that Hermes uses for shell commands).  It clones the repo under `%LOCALAPPDATA%\hermes\hermes-agent`, creates a virtualenv, and adds `hermes` to your **User PATH**.  Restart your terminal (or open a new PowerShell window) after the install so PATH picks up.

**How Git is handled:**
1. If `git` is already on your PATH, the installer uses your existing install.
2. Otherwise it downloads portable **MinGit** (~45MB, from the official `git-for-windows` GitHub release) and unpacks it to `%LOCALAPPDATA%\hermes\git`.  No admin rights required.  Completely isolated — it won't interfere with any system Git install, broken or otherwise.

**Why not use winget?**  Earlier designs auto-installed Git via `winget install Git.Git`, but winget fails badly when a system Git install is in a partial or broken state (exactly when users need the installer to just work).  The portable MinGit approach sidesteps winget, the Windows installer registry, and any existing system Git entirely.  If the Hermes Git install itself ever breaks, `Remove-Item %LOCALAPPDATA%\hermes\git` and re-run the installer — no system impact, no uninstall drama.

The installer also sets `HERMES_GIT_BASH_PATH` to the located `bash.exe` so Hermes resolves it deterministically in fresh shells.

If you prefer WSL2, the Linux installer above works inside it; both native and WSL installs can coexist without conflict (native data lives under `%LOCALAPPDATA%\hermes`, WSL data lives under `~/.hermes`).

### Android / Termux

Hermes now ships a Termux-aware installer path too:

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

The installer detects Termux automatically and switches to a tested Android flow:
- uses Termux `pkg` for hard requirements (`git`, `python`, certificates/curl, build tools as needed)
- creates the virtualenv with `python -m venv`
- exports `ANDROID_API_LEVEL` automatically for Android wheel builds
- installs `.[termux-all]` for the default install option, or `.[termux-minimal]` for `--install-option minimal` / `--install-option minimalTUI`
- skips optional Node/browser, WhatsApp, TUI/npm, voice/TTS, dashboard, and `ffmpeg` work unless the selected install option or `--with ...` requests them

If you want the fully explicit path, follow the dedicated [Termux guide](./termux.md).

:::note Windows Feature Parity (Early Beta)

Native Windows is in **early beta**. Everything except the browser-based dashboard chat terminal runs natively on Windows:
- **CLI (`hermes chat`, `hermes setup`, `hermes gateway`, …)** — native, uses your default terminal
- **Gateway (Telegram, Discord, Slack, …)** — native, runs as a background PowerShell process
- **Cron scheduler** — native
- **Browser tool** — native (Chromium via Node.js)
- **MCP servers** — native (stdio and HTTP transports both supported)
- **Dashboard `/chat` terminal pane** — **WSL2 only** (uses a POSIX PTY; native Windows has no equivalent).  The rest of the dashboard (sessions, jobs, metrics) works natively — only the embedded PTY terminal tab is gated.

Set `HERMES_DISABLE_WINDOWS_UTF8=1` in your environment if you hit an encoding-related bug and want to fall back to the legacy cp1252 stdio path (useful for bisecting).
:::

The default installer uses the **default** install option: the full desktop/server feature set Hermes traditionally installed.

For a compact install, choose `minimal` or `minimalTUI` explicitly:

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash -s -- --install-option minimal
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash -s -- --install-option minimalTUI
```

`minimal` installs the core Python CLI plus lightweight agent tools: skills, file editing, terminal/process, todo, memory, session search, clarify, and web search/extraction. `minimalTUI` adds the TUI dependencies. To opt into specific features during install, use `--with`:

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash -s -- --with terminal,file,web-search
```

### What the Installer Does

The installer handles the repo clone, virtual environment, global `hermes` command setup, and LLM provider configuration. The default install option installs the full Hermes feature set. Compact install options keep dependencies smaller: `minimal` sticks to the core Python CLI and lightweight agent tools, while `minimalTUI` adds TUI dependencies without pulling in every optional integration. Selected features add their own extras: for example `--with dashboard` installs local web UI/API dependencies, `--with browser` enables Node/browser setup, and `--with tts`/`--with voice` checks `ffmpeg`. By the end, you're ready to chat; install extra features only when you need them.

#### Install Layout

Where the installer puts things depends on whether you're installing as a normal user or as root:

| Installer | Code lives at | `hermes` binary | Data directory |
|---|---|---|---|
| Per-user (normal) | `~/.hermes/hermes-agent/` | `~/.local/bin/hermes` (symlink) | `~/.hermes/` |
| Root-mode (`sudo curl … \| sudo bash`) | `/usr/local/lib/hermes-agent/` | `/usr/local/bin/hermes` | `/root/.hermes/` (or `$HERMES_HOME`) |

The root-mode **FHS layout** (`/usr/local/lib/…`, `/usr/local/bin/hermes`) matches where other system-wide developer tools land on Linux. It's useful for shared-machine deployments where one system install should serve every user. Per-user config (auth, skills, sessions) still lives under each user's `~/.hermes/` or explicit `HERMES_HOME`.

### After Installation

Reload your shell and start chatting:

```bash
source ~/.bashrc   # or: source ~/.zshrc
hermes             # Start chatting!
```

To reconfigure individual settings later, use the dedicated commands:

```bash
hermes model          # Choose your LLM provider and model
hermes tools          # Configure which tools are enabled
hermes gateway setup  # Set up messaging platforms
hermes config set     # Set individual config values
hermes setup          # Or run the full setup wizard to configure everything at once
```

---

## Prerequisites

The hard prerequisites depend on the install option:

- **Default** install: Git, Python/uv, Node.js for frontend/browser/TUI features, and `ffmpeg` for media features are checked or installed as needed.
- **Minimal** install: Git is the only hard prerequisite; uv/Python are bootstrapped or managed on desktop platforms.
- **minimalTUI**: minimal plus the TUI dependency path.

Notes:
- **uv** (fast Python package manager) is bootstrapped if missing
- **Python 3.11** is managed via uv on desktop platforms
- **Node.js v22** is checked/installed for the default install option, browser/TUI features (`--with browser`, `--with tui`), or compact `minimalTUI`
- **ripgrep** is optional in minimal; file search falls back when it is absent
- **ffmpeg** is checked/installed for the default install option, TTS, or voice (`--with tts`, `--with voice`)

:::info
You do **not** need to install Python, Node.js, ripgrep, or ffmpeg manually for the minimal smoke path. Make sure `git` is available (`git --version`), run the installer with `--install-option minimal`, reload your shell, then start with `hermes`.
:::

:::tip Nix users
If you use Nix (on NixOS, macOS, or Linux), there's a dedicated setup path with a Nix flake, declarative NixOS module, and optional container mode. See the **[Nix & NixOS Setup](./nix-setup.md)** guide.
:::

---

## Manual / Developer Installation

If you want to clone the repo and install from source — for contributing, running from a specific branch, or having full control over the virtual environment — see the [Development Setup](../developer-guide/contributing.md#development-setup) section in the Contributing guide.

When you run `scripts/install.sh` from a local checkout, the installer uses that checkout's current tracked remote and branch by default. This keeps fork/feature-branch testing from silently updating `~/.hermes/hermes-agent` back to `NousResearch/main`. Override explicitly with `--repo URL --branch NAME` if needed.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `hermes: command not found` | Reload your shell (`source ~/.bashrc`) or check PATH |
| `API key not set` | Run `hermes model` to configure your provider, or `hermes config set OPENROUTER_API_KEY your_key` |
| Missing config after update | Run `hermes config check` then `hermes config migrate` |

For more diagnostics, run `hermes doctor` — it will tell you exactly what's missing and how to fix it.
