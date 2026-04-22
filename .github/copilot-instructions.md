# Hermes Agent — Copilot Instructions

## Development Environment

```bash
source venv/bin/activate   # Always activate before running Python
```

Install with all extras (messaging, cron, CLI menus, dev tools):
```bash
uv venv venv --python 3.11
export VIRTUAL_ENV="$(pwd)/venv"
uv pip install -e ".[all,dev]"
```

## Build / Test / Lint

```bash
# Run full unit test suite
pytest tests/ -v

# Run tests, skip integration and e2e
python -m pytest tests/ -q --ignore=tests/integration --ignore=tests/e2e --tb=short -n auto

# Run a single test file
pytest tests/test_model_tools.py -v

# Run a single test by name
pytest tests/test_model_tools.py::test_name -v

# Run e2e tests separately
python -m pytest tests/e2e/ -v
```

Tests run in parallel (`-n auto`) by default. Integration tests (marked `@pytest.mark.integration`) require real API keys and are excluded from CI.

All tests redirect `HERMES_HOME` to a temp dir via the `_isolate_hermes_home` autouse fixture — tests never write to `~/.hermes/`.

## Architecture

### Core Loop

```
User message → AIAgent._run_agent_loop()  (run_agent.py)
  ├── Build system prompt  (agent/prompt_builder.py)
  ├── Call LLM via OpenAI-compatible API
  ├── If tool_calls in response:
  │     ├── Dispatch via tools/registry.py
  │     ├── Append tool results to conversation
  │     └── Loop back to LLM
  ├── If text response → persist to SQLite, return
  └── Auto-compress context when approaching token limit  (agent/context_compressor.py)
```

### File Dependency Chain

```
tools/registry.py   (no imports from model_tools or tool files — imported by everything)
       ↑
tools/*.py          (each calls registry.register() at import time)
       ↑
model_tools.py      (imports tools/registry + triggers discovery by importing all tool modules)
       ↑
run_agent.py / cli.py / batch_runner.py / environments/
```

### Key Modules

| File | Role |
|---|---|
| `run_agent.py` | `AIAgent` class — conversation loop, tool dispatch, session persistence |
| `model_tools.py` | Thin orchestration layer; `_discover_tools()`, `handle_function_call()` |
| `toolsets.py` | Tool groupings; `_HERMES_CORE_TOOLS` is the shared list for all platforms |
| `hermes_state.py` | `SessionDB` — SQLite with FTS5 full-text search |
| `agent/prompt_builder.py` | Assembles system prompt: identity, skills, context files, memory |
| `tools/registry.py` | Singleton `ToolRegistry`; schemas + handlers; no circular imports |
| `hermes_cli/main.py` | Entry point for all `hermes` subcommands |
| `hermes_cli/commands.py` | Central slash command registry + `SlashCommandCompleter` |
| `gateway/run.py` | `GatewayRunner` — messaging platform lifecycle, routing, cron |

### User Configuration

All runtime state lives in `~/.hermes/`:
- `config.yaml` — model, toolsets, compression, provider routing settings
- `.env` — API keys (never committed)
- `state.db` — SQLite session store
- `skills/` — active skills (bundled + hub-installed + agent-created)
- `memories/` — persistent memory (`MEMORY.md`, `USER.md`)

## Key Conventions

### Self-Registering Tools

Every tool file calls `registry.register()` at **module import time**. `model_tools.py` triggers discovery by importing all tool modules. To add a new tool:

1. Create `tools/my_tool.py` with the schema, handler, and `registry.register()` call at the bottom.
2. Add `"tools.my_tool"` to the `_modules` list in `model_tools.py`.
3. Add it to the relevant toolset in `toolsets.py`.

```python
from tools.registry import registry

def my_tool(param1: str, **kwargs) -> str:
    ...

MY_TOOL_SCHEMA = { "type": "function", "function": { "name": "my_tool", ... } }

registry.register(
    name="my_tool",
    toolset="my_toolset",
    schema=MY_TOOL_SCHEMA,
    handler=lambda args, **kw: my_tool(**args, **kw),
    check_fn=lambda: True,
)
```

### Skills vs Tools

**Skills** (SKILL.md in `skills/`) are almost always the right choice — they're instructions + shell commands. Only write a **Tool** (Python in `tools/`) when you need binary data handling, custom auth flows, or real-time streaming that can't go through the terminal.

### Skill Structure (`skills/<category>/<name>/SKILL.md`)

```yaml
---
name: skill-name
description: Short description shown in search
version: 1.0.0
platforms: [macos, linux]   # Omit to load on all platforms
metadata:
  hermes:
    tags: [Category, Keywords]
    fallback_for_toolsets: [web]     # Show only when these toolsets are absent
    requires_toolsets: [terminal]    # Show only when these toolsets are present
---
```

Skill filtering happens at prompt build time in `agent/prompt_builder.py::build_skills_system_prompt()`.

### Cross-Platform Rules

- `termios`/`fcntl` are Unix-only — always `except (ImportError, NotImplementedError)`
- Use `pathlib.Path` for all paths, not string `/` concatenation
- Use `shlex.quote()` when interpolating user input into shell commands
- Resolve symlinks with `os.path.realpath()` before path-based access control checks

### Branch Naming

```
fix/description        # Bug fixes
feat/description       # New features
docs/description       # Documentation
test/description       # Tests
refactor/description   # Code restructuring
```

### Contribution Priority Order

Bug fixes → cross-platform compatibility → security hardening → performance → new skills → new tools → docs.
