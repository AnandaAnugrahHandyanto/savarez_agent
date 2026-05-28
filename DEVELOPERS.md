# Hermes Agent — Developer Guide

> Companion to [CONTRIBUTING.md](CONTRIBUTING.md) (contribution workflow) and [AGENTS.md](AGENTS.md) (AI assistant reference).
> This document covers architecture, development patterns, and onboarding for human contributors.

---

## Quick Start

```bash
git clone --recurse-submodules https://github.com/NousResearch/hermes-agent.git
cd hermes-agent

uv venv venv --python 3.11
source venv/bin/activate
uv pip install -e ".[all,dev]"

mkdir -p ~/.hermes/{cron,sessions,logs,memories,skills}
cp cli-config.yaml.example ~/.hermes/config.yaml
touch ~/.hermes/.env
# Add at least one provider key to .env, e.g.:
# OPENROUTER_API_KEY=sk-or-...

hermes doctor   # verify setup
hermes chat     # start chatting
```

---

## Architecture Overview

Hermes is a **tool-using AI agent** with a synchronous core loop, self-registering tools, and a multi-platform gateway for messaging platforms.

### Core Loop

```
┌─────────────────────────────────────────────────┐
│                  AIAgent                         │
│                  (run_agent.py)                   │
├─────────────────────────────────────────────────┤
│                                                  │
│  User Message → Build System Prompt              │
│               → Build API kwargs                 │
│               → Call LLM                         │
│                                                  │
│  ┌──── Tool Calls? ────┐                        │
│  │ Yes                  │ No                     │
│  │ Dispatch via Registry│ Return response        │
│  │ Append results       │                        │
│  │ → Loop back to LLM   │                        │
│  └──────────────────────┘                        │
│                                                  │
│  Context compression if near token limit         │
└─────────────────────────────────────────────────┘
```

### Component Map

| Component | Location | Purpose |
|-----------|----------|---------|
| **AIAgent** | `run_agent.py` | Core conversation loop, tool dispatch |
| **CLI** | `cli.py`, `hermes_cli/` | Interactive TUI, slash commands, skins |
| **Tools** | `tools/*.py` | Self-registering capability modules (~25 tools) |
| **Gateway** | `gateway/` | Async messaging to 11+ platforms |
| **Agent Internals** | `agent/` | Prompt builder, context compressor, display, metadata |
| **Skills** | `skills/`, `optional-skills/` | LLM-readable instruction sets |
| **Plugins** | `plugins/` | Memory providers, future extension points |
| **ACP Adapter** | `acp_adapter/` | VS Code / Zed / JetBrains integration |
| **Cron** | `cron/` | Scheduled task management |
| **Batch Runner** | `batch_runner.py` | Parallel trajectory generation for RL training |

### Key Design Patterns

1. **Self-registering tools** — Each `tools/*.py` calls `registry.register()` at import time. No manual import list.
2. **Toolset grouping** — Tools grouped into logical sets (web, terminal, file, browser, etc.) that can be enabled/disabled per platform.
3. **SQLite + FTS5** — Conversations stored in `hermes_state.py` with full-text search.
4. **Ephemeral injection** — System prompts and prefills are injected at API call time, never persisted.
5. **Provider abstraction** — Works with any OpenAI-compatible API. Provider routing supports throughput/latency/price sorting.
6. **Profile isolation** — Each profile gets its own `HERMES_HOME` directory. No cross-contamination.
7. **Plugin lifecycle** — Plugins have `pre_llm`, `post_llm`, `session_start`, `session_end` hooks.

---

## Adding New Capabilities

### When to Add What

| Capability Type | Use When | Location |
|----------------|----------|----------|
| **Skill** | Wraps CLI/API, no custom Python needed | `skills/<category>/<name>/SKILL.md` |
| **Optional Skill** | Official but niche, not default | `optional-skills/<category>/<name>/SKILL.md` |
| **Tool** | Needs API keys, binary data, real-time events | `tools/<name>_tool.py` |
| **Plugin** | Memory provider or lifecycle hooks | `plugins/<type>/<name>/` |
| **Platform Adapter** | New messaging platform | `gateway/platforms/<name>.py` |

### Adding a Tool

```python
# tools/my_tool.py
import json
from tools.registry import registry

def my_tool(param: str, **kwargs) -> str:
    """Handler. Must return a string (usually JSON)."""
    return json.dumps({"result": "ok"})

MY_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "my_tool",
        "description": "What this tool does and when to use it.",
        "parameters": {
            "type": "object",
            "properties": {
                "param": {"type": "string", "description": "What param is"},
            },
            "required": ["param"],
        },
    },
}

def _check_requirements() -> bool:
    return True  # or check for env vars, binaries, etc.

registry.register(
    name="my_tool",
    toolset="my_toolset",
    schema=MY_TOOL_SCHEMA,
    handler=lambda args, **kw: my_tool(**args, **kw),
    check_fn=_check_requirements,
)
```

Then add `"tools.my_tool"` to the `_modules` list in `model_tools.py`.

**Important:** Tool schemas must not reference other toolsets by name. Cross-references go in `get_tool_definitions()` in `model_tools.py`.

### Adding a Skill

```
skills/
└── research/
    └── my-skill/
        ├── SKILL.md          # Required: instructions for the agent
        ├── scripts/          # Optional: helper scripts
        └── references/       # Optional: reference docs
```

SKILL.md uses YAML frontmatter:

```yaml
---
name: my-skill
description: What it does
version: 1.0.0
author: Your Name
platforms: [linux, macos]          # Optional: restrict by OS
required_environment_variables:    # Optional: secure setup-on-load
  - name: MY_API_KEY
    prompt: API key
    help: Where to get it
metadata:
  hermes:
    tags: [Category, Keywords]
    requires_toolsets: [terminal]  # Only show when terminal is available
    fallback_for_toolsets: [web]   # Only show when web is NOT available
---

# My Skill

Brief intro. The agent reads this at skill-load time.
```

### Adding a Platform Adapter

1. Create `gateway/platforms/<name>.py` implementing the adapter interface
2. Add to `GATEWAY_PLATFORMS` in `gateway/config.py`
3. Add configuration keys to `hermes_cli/config.py` under `DEFAULT_CONFIG`
4. Add env vars to `OPTIONAL_ENV_VARS` in `hermes_cli/config.py`
5. Add tests to `tests/gateway/`
6. If the adapter uses unique credentials, use `acquire_scoped_lock()` from `gateway.status` in `connect()` and `release_scoped_lock()` in `disconnect()`

### Adding a Plugin

Plugins are a newer extension point. Key patterns:
- Plugin context provides `register_command()` for slash commands
- Lifecycle hooks: `pre_llm`, `post_llm`, `session_start`, `session_end`
- Memory providers implement the memory plugin ABC in `plugins/memory/`

---

## Testing

```bash
# Full suite (~3000 tests, ~3 min)
pytest tests/ -v

# Specific modules
pytest tests/test_model_tools.py -v
pytest tests/hermes_cli/ -v
pytest tests/gateway/ -v
pytest tests/tools/ -v
```

**Important:** Tests must not write to `~/.hermes/`. The `_isolate_hermes_home` autouse fixture redirects `HERMES_HOME` to a temp directory.

For profile tests, mock both `HERMES_HOME` and `Path.home()`:
```python
@pytest.fixture
def profile_env(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home
```

---

## Cross-Platform Rules

- **`termios`/`fcntl`** — Unix-only. Always catch `ImportError` and `NotImplementedError`.
- **File encoding** — Windows may save `.env` in `cp1252`. Handle `UnicodeDecodeError`.
- **Process management** — `os.setsid()`/`os.killpg()` differ on Windows. Use platform checks.
- **Path separators** — Always use `pathlib.Path`, never string concatenation with `/`.
- **Shell scripts** — If you change `scripts/install.sh`, check `scripts/install.ps1`.

---

## Known Pitfalls

| Pitfall | Solution |
|---------|----------|
| Don't hardcode `~/.hermes` paths | Use `get_hermes_home()` / `display_hermes_home()` |
| Don't use `simple_term_menu` | Rendering bugs in tmux/iTerm2. Use `curses` instead. |
| Don't use `\033[K` in spinner code | Leaks as literal text in `prompt_toolkit`. Use space-padding. |
| `_last_resolved_tool_names` is process-global | `delegate_tool.py` saves/restores it around child runs. |
| Don't cross-reference toolsets in schemas | Use `get_tool_definitions()` post-processing instead. |
| Tests must not write to `~/.hermes/` | Use `_isolate_hermes_home` autouse fixture. |
| Profile ops are HOME-anchored | `_get_profiles_root()` uses `Path.home()`, not `get_hermes_home()`. |

---

## Project Conventions

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

Types: fix, feat, docs, test, refactor, chore
Scopes: cli, gateway, tools, skills, agent, security, etc.
```

### Code Style

- PEP 8 with practical exceptions (no strict line length)
- Comments only for non-obvious intent
- Specific exception catching with `logger.warning()`/`logger.error()` + `exc_info=True` for unexpected errors

### Config Management

| Location | Purpose |
|----------|---------|
| `hermes_cli/config.py` → `DEFAULT_CONFIG` | Config keys and defaults |
| `hermes_cli/config.py` → `OPTIONAL_ENV_VARS` | API keys and secrets metadata |
| `~/.hermes/config.yaml` | User settings |
| `~/.hermes/.env` | User secrets |

When adding config keys, bump `_config_version` in `config.py` to trigger migration.

---

## Security

See [SECURITY.md](SECURITY.md) for the full policy. Key points for developers:

- Use `shlex.quote()` when interpolating user input into shell commands
- Resolve symlinks with `os.path.realpath()` before path-based access checks
- Never log API keys, tokens, or passwords
- Catch broad exceptions around tool execution to prevent crash cascades
- The code execution sandbox strips API keys from the environment
- Cron prompt injection scanner blocks instruction-override patterns

---

## Community

- **Discord**: [discord.gg/NousResearch](https://discord.gg/NousResearch)
- **GitHub Discussions**: Design proposals and architecture
- **Skills Hub**: Share and discover community skills