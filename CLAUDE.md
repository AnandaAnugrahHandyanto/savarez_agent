# Hermes Agent - Development Guide

Instructions for AI coding assistants and developers working on the hermes-agent codebase.

## Project Overview

Hermes Agent is a full-featured, self-improving AI agent and gateway framework (Python 3.11+) that runs as an interactive CLI or as a messaging gateway (Telegram, Discord, Slack, WhatsApp, Matrix, etc.). It orchestrates LLM calls, tool invocations, long-running background jobs (cron), skill management, and subagent delegation. The codebase is production-grade, heavily tested, and designed to run on servers, cloud, or local machines.

Primary usages:
- Interactive TUI: hermes (hermes_cli.main)
- Messaging gateway: gateway.run.GatewayRunner and platform adapters
- Programmatic agent runs: run_agent.AIAgent
- Tools and skills: tools/ (self-registering tools) and skills/

Main language: Python 3.11+ (see pyproject.toml). Packaging and developer workflow use uv (astral.sh/uv) and the repository includes helper scripts (e.g., setup-hermes.sh).

## Development Environment

```bash
source venv/bin/activate  # ALWAYS activate before running Python
```

- Python 3.11+ is required.
- Use the repository's setup scripts (e.g., ./setup-hermes.sh) or the documented installer for developer bootstrap.

## Project Structure

```
hermes-agent/
├── run_agent.py          # AIAgent class — core conversation loop
├── model_tools.py        # Tool orchestration, _discover_tools(), handle_function_call()
├── toolsets.py           # Toolset definitions, _HERMES_CORE_TOOLS list
├── cli.py                # HermesCLI class — interactive CLI orchestrator
├── hermes_state.py       # SessionDB — SQLite session store (FTS5 search)
├── agent/                # Agent internals
│   ├── prompt_builder.py     # System prompt assembly
│   ├── context_compressor.py # Auto context compression
│   ├── prompt_caching.py     # Anthropic prompt caching
│   ├── auxiliary_client.py   # Auxiliary LLM client (vision, summarization)
│   ├── model_metadata.py     # Model context lengths, token estimation
│   ├── models_dev.py         # models.dev registry integration (provider-aware context)
│   ├── display.py            # KawaiiSpinner, tool preview formatting
│   ├── skill_commands.py     # Skill slash commands (shared CLI/gateway)
│   └── trajectory.py         # Trajectory saving helpers
├── hermes_cli/           # CLI subcommands and setup
│   ├── main.py           # Entry point — all `hermes` subcommands
│   ├── config.py         # DEFAULT_CONFIG, OPTIONAL_ENV_VARS, migration
│   ├── commands.py       # Slash command definitions + SlashCommandCompleter
│   ├── callbacks.py      # Terminal callbacks (clarify, sudo, approval)
│   ├── setup.py          # Interactive setup wizard
│   ├── skin_engine.py    # Skin/theme engine — CLI visual customization
│   ├── skills_config.py  # `hermes skills` — enable/disable skills per platform
│   ├── tools_config.py   # `hermes tools` — enable/disable tools per platform
│   ├── skills_hub.py     # `/skills` slash command (search, browse, install)
│   ├── models.py         # Model catalog, provider model lists
│   ├── model_switch.py   # Shared /model switch pipeline (CLI + gateway)
│   └── auth.py           # Provider credential resolution
├── tools/                # Tool implementations (one file per tool)
│   ├── registry.py       # Central tool registry (schemas, handlers, dispatch)
│   ├── approval.py       # Dangerous command detection
│   ├── terminal_tool.py  # Terminal orchestration
│   ├── process_registry.py # Background process management
│   ├── file_tools.py     # File read/write/search/patch
│   ├── web_tools.py      # Web search/extract (Parallel + Firecrawl)
│   ├── browser_tool.py   # Browserbase browser automation
│   ├── code_execution_tool.py # execute_code sandbox
│   ├── delegate_tool.py  # Subagent delegation
│   ├── mcp_tool.py       # MCP client (~1050 lines)
│   └── environments/     # Terminal backends (local, docker, ssh, modal, daytona, singularity)
├── gateway/              # Messaging platform gateway
│   ├── run.py            # Main loop, slash commands, message dispatch
│   ├── session.py        # SessionStore — conversation persistence
│   └── platforms/        # Adapters: telegram, discord, slack, whatsapp, homeassistant, signal
├── acp_adapter/          # ACP server (VS Code / Zed / JetBrains integration)
├── cron/                 # Scheduler (jobs.py, scheduler.py)
├── environments/        # RL training environments (Atropos)
├── tests/                # Pytest suite (~3000 tests)
└── batch_runner.py       # Parallel batch processing
```

Additional notable modules and files used across the codebase:
- hermes_constants.py — canonical get_hermes_home(), display_hermes_home(), reasoning effort parsing and provider endpoint constants.
- hermes_logging.py — idempotent logging setup with redaction and rotating file handlers.
- agent/credential_pool.py — credential pool, leasing and selection strategies used for multi-key failover and child-agent credential leasing.
- hermes_cli/runtime_provider.py (and related auth helpers) — runtime provider resolution and credential selection.

**User config:** `~/.hermes/config.yaml` (settings), `~/.hermes/.env` (API keys)

## File Dependency Chain

```
tools/registry.py  (no deps — imported by all tool files)
       ↑
tools/*.py  (each calls registry.register() at import time)
       ↑
model_tools.py  (imports tools/registry + triggers tool discovery)
       ↑
run_agent.py, cli.py, batch_runner.py, environments/
```

---

## AIAgent Class (run_agent.py)

```python
class AIAgent:
    def __init__(self,
        model: str = "anthropic/claude-opus-4.6",
        max_iterations: int = 90,
        enabled_toolsets: list = None,
        disabled_toolsets: list = None,
        quiet_mode: bool = False,
        save_trajectories: bool = False,
        platform: str = None,           # "cli", "telegram", etc.
        session_id: str = None,
        skip_context_files: bool = False,
        skip_memory: bool = False,
        # ... plus provider, api_mode, callbacks, routing params
    ): ...

    def chat(self, message: str) -> str:
        """Simple interface — returns final response string."""

    def run_conversation(self, user_message: str, system_message: str = None,
                         conversation_history: list = None, task_id: str = None) -> dict:
        """Full interface — returns dict with final_response + messages."""
```

- The agent loop is primarily synchronous and uses iteration budgeting and context compression to avoid exceeding model limits.
- Provider calls may be wrapped for gateway/ACP server async compatibility (threadpool bridging helpers exist).

### Agent Loop

The core loop is inside `run_conversation()` — entirely synchronous in the canonical implementation:

```python
while api_call_count < self.max_iterations and self.iteration_budget.remaining > 0:
    response = client.chat.completions.create(model=model, messages=messages, tools=tool_schemas)
    if response.tool_calls:
        for tool_call in response.tool_calls:
            result = handle_function_call(tool_call.name, tool_call.args, task_id)
            messages.append(tool_result_message(result))
        api_call_count += 1
    else:
        return response.content
```

Messages follow OpenAI-style format: `{"role": "system/user/assistant/tool", ...}`. Reasoning content is stored in `assistant_msg["reasoning"]` and the loop accumulates streaming responses when enabled.

- `model_tools.handle_function_call` and helpers in `model_tools.py` manage argument coercion, async/sync bridging (_run_async/_get_tool_loop), and plugin hooks (pre/post tool call). Tool calls are appended as tool-role messages and compressed when necessary.

---

## CLI Architecture (cli.py)

- **Rich** for banner/panels, **prompt_toolkit** for input with autocomplete
- **KawaiiSpinner** (`agent/display.py`) — animated faces during API calls, `┊` activity feed for tool results
- `load_cli_config()` in cli.py merges hardcoded defaults + user config YAML
- **Skin engine** (`hermes_cli/skin_engine.py`) — data-driven CLI theming; initialized from `display.skin` config key at startup; skins customize banner colors, spinner faces/verbs/wings, tool prefix, response box, branding text
- `process_command()` is a method on `HermesCLI` — dispatches on canonical command name resolved via `resolve_command()` from the central registry
- Skill slash commands: `agent/skill_commands.py` scans `~/.hermes/skills/`, injects as **user message** (not system prompt) to preserve prompt caching

### Gateway and Messaging

- The messaging gateway is implemented in `gateway/run.py` (GatewayRunner) and platform adapters live in `gateway/platforms/`. GatewayRunner bridges messaging events into AIAgent runs (GatewayRunner._handle_message_with_agent).
- Gateway adapters must manage lifecycle, SSL cert detection, reconnection logic, and session locks when needed. Gateway platform adapters should call `acquire_scoped_lock()` / `release_scoped_lock()` (gateway.status) when connecting with credentials shared across profiles.
- ACP adapter (acp_adapter/) provides an async server mode — agent provider calls are wrapped (threadpool) to avoid blocking the gateway event loop.

### Slash Command Registry (`hermes_cli/commands.py`)

All slash commands are defined in a central `COMMAND_REGISTRY` list of `CommandDef` objects. Every downstream consumer derives from this registry automatically:

- **CLI** — `process_command()` resolves aliases via `resolve_command()`, dispatches on canonical name
- **Gateway** — `GATEWAY_KNOWN_COMMANDS` frozenset for hook emission, `resolve_command()` for dispatch
- **Gateway help** — `gateway_help_lines()` generates `/help` output
- **Telegram** — `telegram_bot_commands()` generates the BotCommand menu
- **Slack** — `slack_subcommand_map()` generates `/hermes` subcommand routing
- **Autocomplete** — `COMMANDS` flat dict feeds `SlashCommandCompleter`
- **CLI help** — `COMMANDS_BY_CATEGORY` dict feeds `show_help()`

### Adding a Slash Command

1. Add a `CommandDef` entry to `COMMAND_REGISTRY` in `hermes_cli/commands.py`:
```python
CommandDef("mycommand", "Description of what it does", "Session",
           aliases=("mc",), args_hint="[arg]"),
```
2. Add handler in `HermesCLI.process_command()` in `cli.py`:
```python
elif canonical == "mycommand":
    self._handle_mycommand(cmd_original)
```
3. If the command is available in the gateway, add a handler in `gateway/run.py`:
```python
if canonical == "mycommand":
    return await self._handle_mycommand(event)
```
4. For persistent settings, use `save_config_value()` in `cli.py`

**CommandDef fields:**
- `name` — canonical name without slash (e.g. `"background"`)
- `description` — human-readable description
- `category` — one of `"Session"`, `"Configuration"`, `"Tools & Skills"`, `"Info"`, `"Exit"`
- `aliases` — tuple of alternative names (e.g. `("bg",)`) 
- `args_hint` — argument placeholder shown in help (e.g. `"<prompt>"`, `"[name]"`)
- `cli_only` — only available in the interactive CLI
- `gateway_only` — only available in messaging platforms
- `gateway_config_gate` — config dotpath (e.g. `"display.tool_progress_command"`); when set on a `cli_only` command, the command becomes available in the gateway if the config value is truthy. `GATEWAY_KNOWN_COMMANDS` always includes config-gated commands so the gateway can dispatch them; help/menus only show them when the gate is open.

**Adding an alias** requires only adding it to the `aliases` tuple on the existing `CommandDef`. No other file changes needed — dispatch, help text, Telegram menu, Slack mapping, and autocomplete all update automatically.

---

## Adding New Tools

Requires changes in **3 files**:

**1. Create `tools/your_tool.py`:**
```python
import json, os
from tools.registry import registry

def check_requirements() -> bool:
    return bool(os.getenv("EXAMPLE_API_KEY"))

def example_tool(param: str, task_id: str = None) -> str:
    return json.dumps({"success": True, "data": "..."})

registry.register(
    name="example_tool",
    toolset="example",
    schema={"name": "example_tool", "description": "...", "parameters": {...}},
    handler=lambda args, **kw: example_tool(param=args.get("param", ""), task_id=kw.get("task_id")),
    check_fn=check_requirements,
    requires_env=["EXAMPLE_API_KEY"],
)
```

**2. Add import** in `model_tools.py` `_discover_tools()` list.

**3. Add to `toolsets.py`** — either `_HERMES_CORE_TOOLS` (all platforms) or a new toolset.

- The registry handles schema collection, dispatch, availability checking, and error wrapping. All handlers MUST return a JSON string.
- Path references in tool schemas: If the schema description mentions file paths (e.g. default output directories), use `display_hermes_home()` to make them profile-aware. The schema is generated at import time, which is after `_apply_profile_override()` sets `HERMES_HOME`.
- State files: If a tool stores persistent state (caches, logs, checkpoints), use `get_hermes_home()` for the base directory — never `Path.home() / ".hermes"`.
- Agent-level tools (todo, memory): intercepted by `run_agent.py` before `handle_function_call()`. See `todo_tool.py` for the pattern.

- Tool handlers must adhere to the registry contract: return a JSON string and declare any required env vars via `requires_env` and a `check_fn` to gate availability.

---

## Adding Configuration

### config.yaml options:
1. Add to `DEFAULT_CONFIG` in `hermes_cli/config.py`
2. Bump `_config_version` (currently 5) to trigger migration for existing users

### .env variables:
1. Add to `OPTIONAL_ENV_VARS` in `hermes_cli/config.py` with metadata:
```python
"NEW_API_KEY": {
    "description": "What it's for",
    "prompt": "Display name",
    "url": "https://...",
    "password": True,
    "category": "tool",  # provider, tool, messaging, setting
},
```

### Config loaders (two separate systems):

| Loader | Used by | Location |
|--------|---------|----------|
| `load_cli_config()` | CLI mode | `cli.py` |
| `load_config()` | `hermes tools`, `hermes setup` | `hermes_cli/config.py` |
| Direct YAML load | Gateway | `gateway/run.py` |

---

## Skin/Theme System

The skin engine (`hermes_cli/skin_engine.py`) provides data-driven CLI visual customization. Skins are **pure data** — no code changes needed to add a new skin.

### Architecture

```
hermes_cli/skin_engine.py    # SkinConfig dataclass, built-in skins, YAML loader
~/.hermes/skins/*.yaml       # User-installed custom skins (drop-in)
```

- `init_skin_from_config()` — called at CLI startup, reads `display.skin` from config
- `get_active_skin()` — returns cached `SkinConfig` for the current skin
- `set_active_skin(name)` — switches skin at runtime (used by `/skin` command)
- `load_skin(name)` — loads from user skins first, then built-ins, then falls back to default
- Missing skin values inherit from the `default` skin automatically

### What skins customize

| Element | Skin Key | Used By |
|---------|----------|---------|
| Banner panel border | `colors.banner_border` | `banner.py` |
| Banner panel title | `colors.banner_title` | `banner.py` |
| Banner section headers | `colors.banner_accent` | `banner.py` |
| Banner dim text | `colors.banner_dim` | `banner.py` |
| Banner body text | `colors.banner_text` | `banner.py` |
| Response box border | `colors.response_border` | `cli.py` |
| Spinner faces (waiting) | `spinner.waiting_faces` | `display.py` |
| Spinner faces (thinking) | `spinner.thinking_faces` | `display.py` |
| Spinner verbs | `spinner.thinking_verbs` | `display.py` |
| Spinner wings (optional) | `spinner.wings` | `display.py` |
| Tool output prefix | `tool_prefix` | `display.py` |
| Per-tool emojis | `tool_emojis` | `display.py` -> `get_tool_emoji()` |
| Agent name | `branding.agent_name` | `banner.py`, `cli.py` |
| Welcome message | `branding.welcome` | `cli.py` |
| Response box label | `branding.response_label` | `cli.py` |
| Prompt symbol | `branding.prompt_symbol` | `cli.py` |

### Built-in skins

- `default` — Classic Hermes gold/kawaii (the current look)
- `ares` — Crimson/bronze war-god theme with custom spinner wings
- `mono` — Clean grayscale monochrome
- `slate` — Cool blue developer-focused theme

### Adding a built-in skin

Add to `_BUILTIN_SKINS` dict in `hermes_cli/skin_engine.py`:

```python
"mytheme": {
    "name": "mytheme",
    "description": "Short description",
    "colors": { ... },
    "spinner": { ... },
    "branding": { ... },
    "tool_prefix": "┊",
},
```

### User skins (YAML)

Users create `~/.hermes/skins/<name>.yaml`:

```yaml
name: cyberpunk
description: Neon-soaked terminal theme

colors:
  banner_border: "#FF00FF"
  banner_title: "#00FFFF"
  banner_accent: "#FF1493"

spinner:
  thinking_verbs: ["jacking in", "decrypting", "uploading"]
  wings:
    - ["⟨⚡", "⚡⟩"]

branding:
  agent_name: "Cyber Agent"
  response_label: " ⚡ Cyber "

tool_prefix: "▏"
```

Activate with `/skin cyberpunk` or `display.skin: cyberpunk` in config.yaml.

---

## Important Policies
### Prompt Caching Must Not Break

Hermes-Agent ensures caching remains valid throughout a conversation. **Do NOT implement changes that would:**
- Alter past context mid-conversation
- Change toolsets mid-conversation
- Reload memories or rebuild system prompts mid-conversation

Cache-breaking forces dramatically higher costs. The ONLY time we alter context is during context compression.

### Working Directory Behavior
- **CLI**: Uses current directory (`.` → `os.getcwd()`)
- **Messaging**: Uses `MESSAGING_CWD` env var (default: home directory)

### Background Process Notifications (Gateway)

When `terminal(background=true, check_interval=...)` is used, the gateway runs a watcher that
pushes status updates to the user's chat. Control verbosity with `display.background_process_notifications`
in config.yaml (or `HERMES_BACKGROUND_NOTIFICATIONS` env var):

- `all` — running-output updates + final message (default)
- `result` — only the final completion message
- `error` — only the final message when exit code != 0
- `off` — no watcher messages at all

---

## Profiles: Multi-Instance Support

Hermes supports **profiles** — multiple fully isolated instances, each with its own
`HERMES_HOME` directory (config, API keys, memory, sessions, skills, gateway, etc.).

The core mechanism: `_apply_profile_override()` in `hermes_cli/main.py` sets
`HERMES_HOME` before any module imports. All code that uses `get_hermes_home()` automatically scopes to the active profile.

### Rules for profile-safe code

1. **Use `get_hermes_home()` for all HERMES_HOME paths.** Import from `hermes_constants`.
   NEVER hardcode `~/.hermes` or `Path.home() / ".hermes"` in code that reads/writes state.
   ```python
   # GOOD
   from hermes_constants import get_hermes_home
   config_path = get_hermes_home() / "config.yaml"

   # BAD — breaks profiles
   config_path = Path.home() / ".hermes" / "config.yaml"
   ```

2. **Use `display_hermes_home()` for user-facing messages.** Import from `hermes_constants`.
   This returns `~/.hermes` for default or `~/.hermes/profiles/<name>` for profiles.
   ```python
   # GOOD
   from hermes_constants import display_hermes_home
   print(f"Config saved to {display_hermes_home()}/config.yaml")

   # BAD — shows wrong path for profiles
   print("Config saved to ~/.hermes/config.yaml")
   ```

3. **Module-level constants are fine** — they cache `get_hermes_home()` at import time,
   which is AFTER `_apply_profile_override()` sets the env var. Just use `get_hermes_home()`,
   not `Path.home() / ".hermes"`.

4. **Tests that mock `Path.home()` must also set `HERMES_HOME`** — since code now uses
   `get_hermes_home()` (reads env var), not `Path.home() / ".hermes"`:
   ```python
   with patch.object(Path, "home", return_value=tmp_path), \
        patch.dict(os.environ, {"HERMES_HOME": str(tmp_path / ".hermes")}):
       ...
   ```

5. **Gateway platform adapters should use token locks** — if the adapter connects with
   a unique credential (bot token, API key), call `acquire_scoped_lock()` from
   `gateway.status` in the `connect()`/`start()` method and `release_scoped_lock()` in
   `disconnect()`/`stop()`. This prevents two profiles from using the same credential.
   See `gateway/platforms/telegram.py` for the canonical pattern.

6. **Profile operations are HOME-anchored, not HERMES_HOME-anchored** — `_get_profiles_root()`
   returns `Path.home() / ".hermes" / "profiles"`, NOT `get_hermes_home() / "profiles"`.
   This is intentional — it lets `hermes -p coder profile list` see all profiles regardless
   of which one is active.

## Known Pitfalls

### DO NOT hardcode `~/.hermes` paths
Use `get_hermes_home()` from `hermes_constants` for code paths. Use `display_hermes_home()`
for user-facing print/log messages. Hardcoding `~/.hermes` breaks profiles — each profile
has its own `HERMES_HOME` directory. This was the source of 5 bugs fixed in PR #3575.

### DO NOT use `simple_term_menu` for interactive menus
Rendering bugs in tmux/iTerm2 — ghosting on scroll. Use `curses` (stdlib) instead. See `hermes_cli/tools_config.py` for the pattern.

### DO NOT use `\033[K` (ANSI erase-to-EOL) in spinner/display code
Leaks as literal `?[K` text under `prompt_toolkit`'s `patch_stdout`. Use space-padding: `f"\r{line}{' ' * pad}"`.

### `_last_resolved_tool_names` is a process-global in `model_tools.py`
`_run_single_child()` in `delegate_tool.py` saves and restores this global around subagent execution. If you add new code that reads this global, be aware it may be temporarily stale during child agent runs.

### DO NOT hardcode cross-tool references in schema descriptions
Tool schema descriptions must not mention tools from other toolsets by name (e.g., `browser_navigate` saying "prefer web_search"). Those tools may be unavailable (missing API keys, disabled toolset), causing the model to hallucinate calls to non-existent tools. If a cross-reference is needed, add it dynamically in `get_tool_definitions()` in `model_tools.py` — see the `browser_navigate` / `execute_code` post-processing blocks for the pattern.

### Tests must not write to `~/.hermes/`
The `_isolate_hermes_home` autouse fixture in `tests/conftest.py` redirects `HERMES_HOME` to a temp dir. Never hardcode `~/.hermes/` paths in tests.

**Profile tests**: When testing profile features, also mock `Path.home()` so that
`_get_profiles_root()` and `_get_default_hermes_home()` resolve within the temp dir.
Use the pattern from `tests/hermes_cli/test_profiles.py`:
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

## Key Components (expanded)

- run_agent.py:AIAgent — core synchronous agent loop, streaming, tool-calling, context compression, iteration budgeting.
- model_tools.py:get_tool_definitions, handle_function_call — tool discovery, schema generation, and typed dispatch bridging sync/async.
- tools/registry.py — central registry used by all tools to self-register. Tools call registry.register() at import time.
- tools/*.py — concrete tools (terminal_tool, file_tools, browser_tool, delegate_tool, cronjob_tools, mcp_tool, etc.). Each tool returns JSON string results and declares a JSON schema.
- hermes_cli/main.py:_apply_profile_override, main CLI entrypoints — profile handling, early boot, CLI commands and interactive flows.
- hermes_cli/config.py:DEFAULT_CONFIG, ensure_hermes_home — canonical config defaults, HERMES_HOME management and validation helpers.
- hermes_cli/auth.py and agent/credential_pool.py — provider/credential resolution, pool selection, rotation and lease APIs used for multi-key failover and child-agent credential leasing.
- agent/prompt_builder.py — system prompt composition, skills indexing, prompt-injection safety scanning, and caching of skills snapshots.
- agent/context_compressor.py — auto-compression of conversation history when approaching model limits.
- gateway/run.py:GatewayRunner — platform adapters lifecycle, config bridging, SSL cert path detection and adapter reconnection logic.
- cron/scheduler.py — cron runner, secure script containment, delivery helpers and silence marker semantics.
- hermes_constants.py — canonical helpers and constants used early in boot.
- hermes_logging.py — idempotent logging setup used early in startup.

---

## Architecture

High-level dataflow:

    User (CLI / Platform) ---> GatewayRunner (optional) ---> AIAgent
                               |                                  |
                               |                                  └─> tools.registry -> tool handler functions
                               |                                                     └─> external backends (Docker, Modal, Camofox, etc.)
                               └─> SessionStore / SessionDB (persistence)

More detailed:
- CLI or messaging event triggers GatewayRunner._handle_message_with_agent (gateway/run.py) or HermesCLI REPL (cli.py).
- AIAgent is instantiated (run_agent.AIAgent) with runtime provider credentials resolved by hermes_cli/runtime_provider.py and hermes_cli/auth.py.
- AIAgent builds system+user prompts using agent/prompt_builder.py, injects skills, context files, and memory guidance.
- AIAgent calls provider APIs (OpenAI-like) via the chosen client. If the model returns function/tool calls, AIAgent uses model_tools.handle_function_call to dispatch to tools.
- Tools live in tools/* and self-register schemas to tools/registry.py. Tool handlers may call back into agent or gateway (e.g., terminal backend, background processes, MCP servers).
- Tool results are appended to the conversation, compressed when necessary, and persisted by hermes_state.py / SessionDB.

---

## Core Data Structures

- Gateway/session:
  - gateway/session.py:SessionSource, SessionContext, SessionEntry — identify platform, chat, thread, redaction/hashing helpers, and prompt fragment builders.

- Credential pool:
  - agent/credential_pool.py:PooledCredential, CredentialPool — persisted auth.json entries, selection strategies (fill_first, round_robin, random, least_used), exhaustion cooldowns, acquire_lease/release_lease for child agents.

- Tooling:
  - tools/registry.py:registry entries mapping name -> {schema, handler, check_fn, requires_env}
  - model_tools.py:ToolDefinition list returned to LLMs (OpenAI function schema style) and handle_function_call dispatcher.

- Agent:
  - run_agent.py:AIAgent, IterationBudget, _SafeWriter — main control loop, streaming accumulator, tool-call orchestration, surrogate sanitization.

- Prompts & skills:
  - agent/prompt_builder.py:skills snapshot cache (.skills_prompt_snapshot.json) and scanning/truncation helpers for project files.

---

## Control Flow (end-to-end)

1. Startup
   - hermes_cli.main._apply_profile_override sets HERMES_HOME early.
   - hermes_logging.setup_logging invoked early to add rotating logs.
   - CLI or gateway loads config (hermes_cli.config.load_config / load_cli_config) and bridges selected keys into env vars.
2. Receive message
   - GatewayRunner or HermesCLI builds SessionSource and session key (gateway/session.py:build_session_key).
   - Instantiate (or reuse) AIAgent for session with resolved provider runtime via hermes_cli/runtime_provider.resolve_runtime_provider.
3. AIAgent.run_conversation
   - system prompt assembled agent/prompt_builder.build_skills_system_prompt and build_context_files_prompt.
   - pre-flight model metadata checks (agent/model_metadata.py) to ensure fit for context size.
   - call provider API (sync blocking call wrapped in threadpool for ACP server and gateway async contexts).
   - if response contains tool calls: for each tool call model_tools.handle_function_call coerces args, runs tool handler (_run_async), and returns JSON string results appended as tool role messages.
   - loop until final assistant content is produced or iteration budget exhausted.
   - store final messages in SessionDB and optionally save trajectory.

---

## Test-Driven Development & Testing

- The project has extensive unit tests (tests/). CI runs pytest with -m 'not integration' and -n auto (xdist). Use the same commands locally.
- Focus on small, targeted unit tests: tools and agent behaviors are covered by many focused tests. Run relevant test file(s) first.
- When modifying persisted constants (status strings, JSON keys) add migration code and tests because auth.json, cached snapshots and session transcripts are long-lived.

Bash/Test commands:

```bash
source venv/bin/activate
python -m pytest tests/ -q          # Full suite (~3000 tests, ~3 min)
python -m pytest tests/test_model_tools.py -q   # Toolset resolution
python -m pytest tests/test_cli_init.py -q       # CLI config loading
python -m pytest tests/gateway/ -q               # Gateway tests
python -m pytest tests/tools/ -q                 # Tool-level tests

# Fast local subset similar to CI
python -m pytest tests/ -q --ignore=tests/integration --ignore=tests/e2e --tb=short -n auto

# Single test example
python -m pytest tests/tools/test_delegate.py::TestChildCredentialLeasing::test_run_single_child_acquires_and_releases_lease -q
```

Always run the full suite before pushing changes in sensitive areas.

---

## Bash Commands (developer tips)

- Install & dev setup (recommended): see README and setup-hermes.sh
  - Quick: curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
  - Repo dev: ./setup-hermes.sh

- Run CLI:
  - hermes (entry point defined in pyproject.toml)
  - hermes setup
  - hermes gateway start

- Lint and formatting: project prefers PEP8 but no enforced formatter documented. Use standard tools (ruff/black) as desired.

---

## Code Style / Conventions

- PEP8 with pragmatic exceptions. Keep imports lightweight in small modules used at bootstrap (hermes_constants avoids non-stdlib imports).
- Avoid heavy imports at module import time for modules used in prompt building (prompt_builder avoids importing tools.* directly).
- Use get_hermes_home() / display_hermes_home() from hermes_constants.py for all HERMES_HOME path operations to preserve profile semantics.
- Use registry.register() in tools at import time and ensure check_fn is present to gate availability.

---

## Gotchas (expanded)

- HERMES_HOME and profiles: _apply_profile_override must run before other imports that cache HERMES_HOME. Use get_hermes_home() for runtime paths and display_hermes_home() for user-facing messages.
- Do not hardcode ~/.hermes paths. Use hermes_constants.get_hermes_home() and display_hermes_home().
- Do not import heavy modules at top-level in prompt_builder or other early-boot modules — that breaks tests and cold-start performance.
- Event loop lifecycle: model_tools maintains persistent event loops. Changing how loops are created/closed can reintroduce "Event loop is closed" errors. Use _get_tool_loop/_get_worker_loop/_run_async helpers.
- Dangerous command approval: tools/approval.py uses contextvar for session isolation. Gateway must call set_current_session_key()/reset_current_session_key around agent turns.
- Cron jobs: cron/scheduler checks for SILENT_MARKER anywhere in the response (not just startswith). Keep that containment logic for delivery suppression.
- File guards: tools/file_tools blocks specific device paths and prevents reading internal Hermes cache files using get_hermes_home(); altering this risks prompt-injection and profile-escape vulnerabilities.

---

## Pattern Examples

- Adding a tool (good example)
  - tools/example_tool.py: Define schema, check_fn, handler, and call registry.register(...). Keep handler returning JSON string.
  - model_tools._discover_tools: add "tools.example_tool" to the import list.
  - toolsets.py: add a toolset name if intended to be selectable.

- Building a system prompt (good example)
  - agent/prompt_builder.py: build_skills_system_prompt — caches skills snapshot, sanitizes frontmatter, and protects against prompt-injection.

- Credential pool leasing (good example)
  - agent/credential_pool.py: use acquire_lease/release_lease in try/finally when spawning child agents (delegate_tool).

---

## Common Mistakes (symptom → fix)

- Symptom: Tests or runtime error referencing wrong HERMES_HOME path.
  - Fix: Ensure _apply_profile_override ran before imports and code uses get_hermes_home(), not Path.home()/"~/.hermes".
  - Files: hermes_cli/main.py:_apply_profile_override, hermes_constants.get_hermes_home

- Symptom: "Event loop is closed" exceptions in tests or CLI.
  - Fix: Don’t create/destroy global event loops repeatedly. Use model_tools._get_tool_loop/_get_worker_loop and _run_async to bridge sync→async. Avoid closing the loop at module level.
  - Files: model_tools.py (see _get_tool_loop/_run_async)

- Symptom: Model hallucinating a tool that isn’t available.
  - Fix: Ensure model_tools.get_tool_definitions filters unavailable tools and post-processes schemas (execute_code/browser_navigate adjustments). Keep _last_resolved_tool_names semantics intact.
  - Files: model_tools.py, tools/* registration

- Symptom: Credential pool selects exhausted keys repeatedly.
  - Fix: Respect STATUS_EXHAUSTED string constants and cooldown logic; ensure _parse_absolute_timestamp correctly interprets provider reset timestamps.
  - Files: agent/credential_pool.py

---

## Invariants

- All persistent state under HERMES_HOME must be accessed via get_hermes_home() to preserve profile isolation.
- Tool handlers MUST return a JSON string result (tools/registry contract).
- plugin hooks: hermes_cli.plugins.invoke_hook returns a list of non-None results and exceptions must not propagate.
- model_tools.handle_function_call must propagate task_id, tool_call_id, and session_id into plugin hooks (pre_tool_call/post_tool_call).
- Cron job final response detection: scheduler uses SILENT_MARKER contained anywhere (case-insensitive) to suppress delivery.

---

## Anti-patterns

- Importing heavy optional modules at top-level in modules used during CLI/gateway startup (prompt_builder, hermes_constants). Use lazy imports.
- Writing paths with Path.home()/"~/.hermes" hardcoded instead of get_hermes_home().
- Performing blocking network I/O on the gateway event loop: run blocking calls in ThreadPoolExecutor (acp_adapter.server demonstrates pattern).
- Mutating COMMAND_REGISTRY or TOOLSETS at runtime without calling rebuild_lookups()/register_plugin_command.

---

## Additional Notes (Developer workflow tips)

- CI matrix: GitHub Actions runs tests on ubuntu-latest with Python 3.11 installed via uv and dependencies installed from uv.lock (if present). e2e job is separate and has a short timeout.
- Keep the lightweight constants module hermes_constants.py free of non-stdlib imports to avoid circular import or bootstrap problems.
- Many modules include a rich history of fixes and fragile edge-cases (credential pool, model_metadata, gateway SSL cert detection). When editing these areas, run their focused tests (see top of each semantic file analysis in the repository).

If you want, I can also produce quick pointers for making a single change (e.g., how to add a tool, how to update a provider mapping, or how to add a unit test) with exact file and function references.

# Verification Checklist

- Run the full test matrix locally or in CI
- Confirm failing test fails before fix, passes after
- Run linters and formatters

# Test Integrity

- NEVER modify existing tests to make your implementation pass
- If a test fails after your change, fix the implementation, not the test
- Only modify tests when explicitly asked to, or when the test itself is demonstrably incorrect

# Suggestions for Thorough Investigation

When working on a task, consider looking beyond the immediate file:
- Test files can reveal expected behavior and edge cases
- Config or constants files may define values the code depends on
- Files that are frequently changed together (coupled files) often share context

# Must-Follow Rules

1. Work in short cycles. In each cycle: choose the single highest-leverage next action, execute it, verify with the strongest available check (tests, typecheck, run, lint, or a minimal repro), then write a brief log entry of what changed + what you'll do next.
2. Prefer the smallest change that can be verified. Keep edits localized, avoid broad formatting churn, and structure work so every change is easy to revert.
3. If you're missing information (requirements, environment behavior, API contracts), do not assume. Instead: inspect code, read docs in-repo, run a targeted experiment, add temporary instrumentation, or create a minimal reproduction to learn the truth quickly.


# Index Files

I have provided an index file to help navigate this codebase:
- `.claude/docs/general_index.md`

The file is organized by directory (## headers), with each file listed as:
`- `filename` - short description. Key: `construct1`, `construct2` [CATEGORY]`

You can grep for directory names, filenames, construct names, or categories (TEST, CLI, PUBLIC_API, GENERATED, SOURCE_CODE) to quickly find relevant files without reading the entire index.

**MANDATORY RULE — NO EXCEPTIONS:** After you read, reference, or consider editing a file or folder, you MUST run:
`python .claude/docs/get_context.py <path>`

This works for **both files and folders**:
- For a file: `python .claude/docs/get_context.py <file_path>`
- For a folder: `python .claude/docs/get_context.py <folder_path>`

This is a hard requirement for EVERY file and folder you touch. Without this, you'll miss recent important information and your edit will likely fail verification. Do not skip this step. Do not assume you already know enough. Do not batch it "for later." Do not skip files even if you have obtained context about a parent directory. Run it immediately after any other action on that path.

The command returns critical context you cannot infer on your own:

**For files:**
- Edit checklist with tests to run, constants to check, and related files
- Historical insights (past bugs, fixes, lessons learned)
- Key constructs defined in the file
- Tests that exercise this file
- Related files and semantic overview
- Common pitfalls

**For folders:**
- Folder role and responsibility in the codebase
- Key files and why they matter
- Cross-cutting behaviors across the subtree
- Distilled insights from every file in that folder

**Workflow (follow this exact order every time):**
1. Identify the file or folder you need to work with.
2. Run `python .claude/docs/get_context.py <path>` and read the output.
3. Only then proceed to read, edit, or reason about it.

If you need to work with multiple paths, run the command for each one before touching any of them.

**Violations:** If you read or edit a file or folder without first running get_context.py on it, you are violating a project-level rule. Stop, run the command, and re-evaluate your changes with the new context.



---
*This knowledge base was extracted by [Codeset](https://codeset.ai) and is available via `python .claude/docs/get_context.py <file_or_folder>`*
