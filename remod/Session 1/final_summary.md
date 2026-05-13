# Hermes Agent → Jade: Final Codebase Analysis

## Overview
This document consolidates findings from reading the Hermes Agent codebase across 7 analysis steps, providing actionable intelligence for forking/customizing it into "Jade" (Oracule Zero executive orchestrator). Each section documents architecture, key files, branding surfaces, and customization guidance.

---

## 1. CORE DEVELOPMENT RULES

### Rule #1: NEVER modify these files
Per AGENTS.md (Rule section, Teknium May 2026):
```
run_agent.py          # AIAgent class — core conversation loop (~12k LOC)
cli.py                # HermesCLI class — interactive CLI orchestrator (~11k LOC)
gateway/run.py        # Gateway runner — main event loop (16.6k LOC)
hermes_cli/main.py    # CLI entry point — argparse, setup, subcommands
```

These files are explicitly forbidden from modification. Instead, use:
- **Plugin system** for adding tools and hooks
- **Skin engine** for visual customization
- **Config system** for behavioral tuning
- **Skills system** for specialized workflows

### Rule #2: Plugin-Only Extensions
Plugins MUST NOT modify core files. If a plugin needs a capability the framework doesn't expose, expand the generic plugin surface (new hook, new ctx method) — never hardcode plugin-specific logic into core.

### Rule #3: Profile-Aware Paths
All state paths must use `get_hermes_home()` from `hermes_constants`, never `Path.home() / ".hermes"`. User-facing messages use `display_hermes_home()`.

### File Dependency Chain
```
tools/registry.py        (no deps — imported by all tool files)
  ↑
tools/*.py               (each calls registry.register() at import time)
  ↑
model_tools.py           (imports tools/registry + triggers tool discovery)
  ↑
run_agent.py, cli.py, batch_runner.py, environments/
```

---

## 2. PLUGIN SYSTEM

### Architecture
- `PluginManager` discovers plugins from: `~/.hermes/plugins/`, `./.hermes/plugins/`, and pip entry points
- Each plugin exposes a `register(ctx)` function
- Discovery happens as side effect of importing `model_tools.py`

### Plugin Registration Pattern (hooks-based)
```python
# plugins/disk-cleanup/__init__.py
def register(ctx):
    ctx.register_hook("post_tool_call", cleanup_after_tool)
    ctx.register_hook("on_session_end", cleanup_on_exit)
```

### Plugin Registration Pattern (tools-based)
```python
# plugins/spotify/__init__.py
from tools.registry import registry

def register(ctx):
    ctx.register_tool(
        name="spotify_search",
        description="Search Spotify for music",
        parameters={...},
        handler=spotify_search_handler,
        requires_env=["SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET"],
    )
```

### Plugin Manifest Format (plugin.yaml)
```yaml
name: "plugin-name"
version: "1.0.0"
description: "What it does"
# Optional: kind: "backend"  # backend plugins provide tools
# Optional: provides_tools: true
requires_env: ["ENV_VAR_1", "ENV_VAR_2"]
hooks: ["post_tool_call", "on_session_end"]  # lifecycle hooks
```

### Available Plugin Hooks
- `pre_tool_call`, `post_tool_call` — before/after tool execution
- `pre_llm_call`, `post_llm_call` — before/after LLM API calls
- `on_session_start`, `on_session_end` — session lifecycle
- CLI subcommands via `ctx.register_cli_command(...)`

### Memory Provider Plugins
Separate discovery for memory backends (plugins/memory/<name>/):
- Implement `MemoryProvider` ABC (agent/memory_provider.py)
- Orchestrated by `agent/memory_manager.py`
- Lifecycle hooks: `sync_turn()`, `prefetch()`, `shutdown()`, `post_setup()`
- Built-in: honcho, mem0, supermemory, byterover, hindsight, holographic, openviking, retaindb

### Model Provider Plugins
Separate lazy discovery via `_discover_providers()`:
- Scan order: bundled → user → legacy
- Each plugin calls `providers.register_provider(ProviderProfile(...))`
- User plugins override bundled ones (last-writer-wins)

---

## 3. SKILL SYSTEM

### Directory Structure
```
skills/                        # Built-in skills (loaded by default)
  apple/macos-computer-use/
    SKILL.md
  autonomous-ai-agents/hermes-agent/SKILL.md
  blockchain/
  communication/
  creative/
  devops/
  email/
  health/
  migration/
  mlops/
  productivity/
  research/
  security/
  web-development/

optional-skills/               # Niche skills (explicit install required)
  autonomous-ai-agents/
  blockchain/
  communication/
  creative/
  devops/
  email/
  health/
  mcp/
  migration/
  mlops/
  productivity/
  research/
  security/
  web-development/
```

### SKILL.md Frontmatter Format
```markdown
---
name: "skill-name"
description: "What this skill does"
version: "1.0.0"
author: "Author Name"
license: "MIT"
platforms: [linux, macos, windows]  # OS gating
tags: [tag1, tag2]                   # discovery tags (mirrors metadata.hermes.tags)
category: "category-name"            # (mirrors metadata.hermes.category)
metadata:
  hermes:
    tags: [tag1, tag2]
    category: "category-name"
    related_skills: [other-skill]     # related skill references
    config:                           # config.yaml keys needed
      some_key: "description"
---
```

### Key Skill Configuration (config.yaml)
```yaml
skills:
  external_dirs: []              # Additional skill directories to scan
  template_vars: true            # Substitute ${HERMES_SKILL_DIR} in SKILL.md
  inline_shell: false            # Execute !`cmd` snippets in skills
  guard_agent_created: false     # Scan agent-created skills for dangerous patterns

curator:
  enabled: true                  # Background skill maintenance
  interval_hours: 168            # 7 days between runs
  stale_after_days: 30           # Mark skill stale after 30d no use
  archive_after_days: 90         # Archive after 90d no use
```

---

## 4. CONFIG SYSTEM

### Config Loading Chain (three paths):
| Loader | Used by | Location |
|--------|---------|----------|
| `load_cli_config()` | CLI mode | cli.py — merges CLI-specific defaults + user YAML |
| `load_config()` | `hermes tools`, `hermes setup`, most subcommands | hermes_cli/config.py — merges DEFAULT_CONFIG + user YAML |
| Direct YAML load | Gateway runtime | gateway/run.py + gateway/config.py — reads user YAML raw |

### File Locations
- **Config**: `~/.hermes/config.yaml` (via `get_config_path()`)
- **Secrets**: `~/.hermes/.env` (via `get_env_path()`)
- **Logs**: `~/.hermes/logs/agent.log`, `~/.hermes/logs/errors.log`
- **Sessions**: `~/.hermes/state.db` (SQLite with FTS5)
- **Skills**: `~/.hermes/skills/`
- **Plugins**: `~/.hermes/plugins/`
- **Skins**: `~/.hermes/skins/`
- **Checkpoints**: `~/.hermes/checkpoints/`
- **Memories**: `~/.hermes/memories/`

### DEFAULT_CONFIG Sections (hermes_cli/config.py lines 437-1557)
Each section is configurable in config.yaml:

| Section | Key | Default | Purpose |
|---------|-----|---------|---------|
| model | `model` | `""` | Model name/id |
| model | `providers` | `{}` | Provider configurations |
| model | `fallback_providers` | `[]` | Fallback provider chain |
| agent | `max_turns` | `90` | Max tool-calling iterations |
| agent | `gateway_timeout` | `1800` | Gateway inactivity timeout (s) |
| agent | `tool_use_enforcement` | `"auto"` | Tool-use guidance injection |
| agent | `image_input_mode` | `"auto"` | How user images are presented |
| terminal | `backend` | `"local"` | Execution environment |
| terminal | `cwd` | `"."` | Working directory |
| terminal | `persistent_shell` | `True` | Keep shell across commands |
| display | `skin` | `"default"` | Visual skin/theme name |
| display | `personality` | `"kawaii"` | CLI personality |
| display | `streaming` | `False` | Streaming output |
| display | `show_reasoning` | `False` | Show model reasoning |
| display | `compact` | `False` | Compact display mode |
| display | `language` | `"en"` | UI language |
| display | `ephemeral_system_ttl` | `0` | Auto-delete system notices (s) |
| display | `runtime_footer.enabled` | `False` | Show model metadata footer |
| compression | `enabled` | `True` | Context compression |
| compression | `threshold` | `0.50` | Compress at 50% context usage |
| compression | `target_ratio` | `0.20` | Compress to 20% of threshold |
| memory | `memory_enabled` | `True` | Persistent memory |
| memory | `memory_char_limit` | `2200` | Memory char limit |
| memory | `provider` | `""` | External memory provider |
| skills | `external_dirs` | `[]` | Skill directories |
| skills | `template_vars` | `True` | SKILL.md variable substitution |
| curator | `enabled` | `True` | Skill maintenance |
| curator | `interval_hours` | `168` | Run interval |
| approvals | `mode` | `"manual"` | Approval mode |
| approvals | `cron_mode` | `"deny"` | Cron approval mode |
| audio/voice | `tts.provider` | `"edge"` | TTS provider |
| audio/voice | `stt.provider` | `"local"` | STT provider |
| privacy | `redact_pii` | `False` | PII redaction |
| checkpoints | `enabled` | `False` | File snapshots |
| tool_loop_guardrails | `warnings_enabled` | `True` | Tool loop warnings |
| delegation | `max_concurrent_children` | `3` | Parallel child agents |
| delegation | `child_timeout_seconds` | `600` | Child agent timeout |
| code_execution | `mode` | `"project"` | Code execution mode |
| network | `force_ipv4` | `False` | IPv4-only |
| sessions | `auto_prune` | `False` | Session auto-cleanup |
| logging | `level` | `"INFO"` | Log level |

### Environment Variables (OPTIONAL_ENV_VARS in config.py)
Categorized by purpose:
- **provider** (40+ vars): API keys and base URLs for model providers
- **tool** (20+ vars): Keys for web search, browser, image gen, etc.
- **messaging** (60+ vars): Bot tokens, allowed users, webhook configs
- **skill** (5 vars): Notion, Linear, Airtable, Tenor API keys
- **setting** (5 vars): SUDO_PASSWORD, HERMES_MAX_ITERATIONS, etc.

---

## 5. TUI SYSTEM

### Architecture
```
hermes --tui
  └─ Node (Ink/React)  ──stdio JSON-RPC──  Python (tui_gateway)
       │                                  └─ AIAgent + tools + sessions
       └─ renders transcript, composer, prompts, activity
```

### Key TUI Files
| File | Purpose |
|------|---------|
| `ui-tui/src/entry.tsx` | Entry point — GatewayClient, graceful exit, memory monitoring |
| `ui-tui/src/app.tsx` | Main App — orchestrates useMainApp hook, renders AppLayout |
| `ui-tui/src/theme.ts` | Theme interface + DARK_THEME/LIGHT_THEME + fromSkin() bridge |
| `ui-tui/src/banner.ts` | ASCII art — LOGO_ART ("HERMES AGENT"), CADUCEUS_ART |
| `ui-tui/src/components/branding.tsx` | Banner, session panel, skills/toolsets display |
| `ui-tui/src/components/appLayout.tsx` | Layout orchestrator |
| `ui-tui/src/components/appChrome.tsx` | Status bar, title bar, thinking indicator |
| `ui-tui/src/components/thinking.tsx` | Thinking/animation states |
| `ui-tui/src/components/messageLine.tsx` | Message rendering |
| `ui-tui/src/components/streamingAssistant.tsx` | Streaming response display |
| `ui-tui/src/components/sessionPicker.tsx` | Session resume UI |
| `ui-tui/src/components/modelPicker.tsx` | Model switching UI |
| `ui-tui/src/components/prompts.tsx` | Approval dialogs |
| `ui-tui/src/components/maskedPrompt.tsx` | Password input |
| `ui-tui/src/components/textInput.tsx` | Text input |
| `ui-tui/src/components/markdown.tsx` | Markdown rendering |
| `ui-tui/src/components/helpHint.tsx` | Help hints |
| `ui-tui/src/components/agentsOverlay.tsx` | Sub-agent overlay |
| `ui-tui/src/components/todoPanel.tsx` | Todo list panel |
| `ui-tui/src/components/queuedMessages.tsx` | Message queue |
| `ui-tui/src/components/skillsHub.tsx` | Skills hub panel |
| `ui-tui/src/components/themed.tsx` | Themed text wrapper |
| `ui-tui/src/components/overlayControls.tsx` | Overlay controls |
| `ui-tui/src/components/fpsOverlay.tsx` | Performance overlay |
| `tui_gateway/server.py` | Python backend — JSON-RPC method/event catalog |

### Theme System (theme.ts)
```typescript
interface ThemeColors {
  primary, accent, border, text, muted: string       // Core colors
  completionBg, completionCurrentBg, completionMetaBg, completionMetaCurrentBg: string  // Menu colors
  label, ok, error, warn: string                      // Semantic colors
  prompt, sessionLabel, sessionBorder: string         // UI colors
  statusBg, statusFg, statusGood, statusWarn, statusBad, statusCritical, selectionBg: string  // Status colors
  diffAdded, diffRemoved, diffAddedWord, diffRemovedWord: string  // Diff colors
  shellDollar: string                                 // Shell prompt
}

interface ThemeBrand {
  name: string           // Agent display name
  icon: string           // Brand icon (caduceus: ⚕)
  prompt: string         // Input prompt symbol
  welcome: string        // Welcome message
  goodbye: string        // Goodbye message
  tool: string           // Tool output prefix
  helpHeader: string     // Help header text
}
```

### TUI Branding BRAND constant (theme.ts L239-247):
```typescript
const BRAND = {
  name: 'Hermes Agent',
  icon: '⚕',
  prompt: '❯',
  welcome: 'Type your message or /help for commands.',
  goodbye: 'Goodbye! ⚕',
  tool: '┊',
  helpHeader: '(^_^)? Commands'
};
```

### Banner (banner.ts):
- **LOGO_ART**: "HERMES AGENT" in 6-line ASCII block letters (98 chars wide, gold gradient)
- **CADUCEUS_ART**: Caduceus symbol in 15-line Braille/Unicode art
- Gradient: 4-step (primary → accent → border → muted) mapped per line

---

## 6. BRANDING STRINGS INVENTORY

### TUI Branding Strings to Replace for "Jade"
| Location | String | File:Line |
|----------|--------|-----------|
| theme.ts | `name: 'Hermes Agent'` | theme.ts:240 |
| theme.ts | `icon: '⚕'` | theme.ts:241 |
| theme.ts | `welcome: 'Type your message or /help for commands.'` | theme.ts:243 |
| theme.ts | `goodbye: 'Goodbye! ⚕'` | theme.ts:244 |
| theme.ts | `helpHeader: '(^_^)? Commands'` | theme.ts:246 |
| branding.tsx | `{t.brand.icon} NOUS HERMES` | branding.tsx:52 |
| branding.tsx | `{t.brand.icon} Nous Research · Messenger of the Digital Gods` | branding.tsx:56 |
| branding.tsx | `· Nous Research` | branding.tsx:227 |
| appLayout.tsx | `⚕ {ui.status}` | appLayout.tsx:318 |
| appChrome.tsx | `EMOJI_FRAMES = ['⚕ ', ...]` | appChrome.tsx:30 |
| banner.ts | LOGO_ART ("HERMES AGENT") | banner.ts:46-53 |
| banner.ts | CADUCEUS_ART (caduceus art) | banner.ts:55-71 |

### Python CLI Skin Engine Branding (skin_engine.py)
Each built-in skin has branding strings:

| Skin | agent_name | welcome | response_label | goodbye | prompt_symbol |
|------|-----------|---------|---------------|---------|--------------|
| default | "Hermes Agent" | "Welcome to Hermes Agent!" | " ⚕ Hermes " | "Goodbye! ⚕" | "❯" |
| ares | "Ares Agent" | "Welcome to Ares Agent!" | " ⚔ Ares " | "Farewell, warrior! ⚔" | "⚔" |
| mono | "Hermes Agent" | "Welcome to Hermes Agent!" | " ⚕ Hermes " | "Goodbye! ⚕" | "❯" |
| slate | "Hermes Agent" | "Welcome to Hermes Agent!" | " ⚕ Hermes " | "Goodbye! ⚕" | "❯" |
| daylight | "Hermes Agent" | "Welcome to Hermes Agent!" | " ⚕ Hermes " | "Goodbye! ⚕" | "❯" |
| warm-lightmode | "Hermes Agent" | "Welcome to Hermes Agent!" | " ⚕ Hermes " | "Goodbye! ⚕" | "❯" |

### Python CLI String References to Replace
| File | Line | String |
|------|------|--------|
| default_soul.py | 4 | "You are Hermes Agent, an intelligent AI assistant created by Nous Research." |
| banner.py | 472 | "Nous Research" |
| banner.py | 130 | "https://github.com/NousResearch/hermes-agent.git" |
| banner.py | 287 | "https://github.com/NousResearch/hermes-agent/releases/tag" |
| status.py | 97 | "⚕ Hermes Agent Status" |
| setup.py | 180 | "⚕ Hermes Setup" |
| setup.py | 2087 | `bot_name="Hermes"` |
| setup.py | 3097/3133 | "⚕ Hermes Agent Setup Wizard" |
| tools_config.py | 2377/2393 | "⚕ Hermes Tool Configuration" |
| uninstall.py | 455/679 | "⚕ Hermes Agent Uninstaller" / "Thank you for using Hermes Agent! ⚕" |
| gateway.py | 3171 | "⚕ Hermes Gateway Starting..." |
| gateway.py | 4776 | "⚕ Gateway Setup" |
| config.py | 4707 | "⚕ Hermes Configuration" |
| config.py | 1260 | comment: "⚕ *Hermes Agent*" header |
| main.py | 7340 | "⚕ Updating Hermes Agent..." |
| main.py | 9629 | `help='Bot display name (default: "Hermes")'` |
| main.py | 1647/1654 | "Agent responses are prefixed with '⚕ Hermes Agent'" |
| slack_cli.py | 112/117 | `--name NAME Override bot display name (default: "Hermes")` |
| claw.py | 351/577 | "⚕ Hermes — OpenClaw Migration/Cleanup" |
| skills_hub.py | 356/574 | "Nous Research" attribution |
| tip.py | 335 | "Skills from trusted repos (NousResearch)" |
| models.py | 906 | "Nous Portal (Nous Research subscription)" |
| model_switch.py | 54-66 | Nous Research Hermes model detection logic |
| _parser.py | 90 | `prog="hermes"` |
| auth.py | 3249 | "hermes" substring check in model names |
| config.py | 278 | `exec_user = "hermes"` default |
| commands.py | 982 | `("hermes", "Talk to Hermes or run a subcommand")` |

### Environment Variable Names Affected
| Env Var | Change Needed | Location |
|---------|--------------|----------|
| `HERMES_MANAGED` | Rename | config.py |
| `HERMES_CONTAINER` | Rename | config.py |
| `HERMES_SKIP_CHMOD` | Rename | config.py |
| `HERMES_HOME_MODE` | Rename | config.py |
| `HERMES_TOOL_PROGRESS` | Rename | config.py |
| `HERMES_PREFILL_MESSAGES_FILE` | Rename | config.py |
| `HERMES_EPHEMERAL_SYSTEM_PROMPT` | Rename | config.py |
| `HERMES_MAX_ITERATIONS` | Rename | config.py |
| `HERMES_DEV_PERF` | Rename | TUI perf lib |
| `HERMES_TUI_THEME` | Rename | theme.ts |
| `HERMES_TUI_LIGHT` | Rename | theme.ts |
| `HERMES_TUI_BACKGROUND` | Rename | theme.ts |
| `HERMES_TUI_NO_CONFIRM` | Rename | config reference |
| `HERMES_TUI_RESUME` | Rename | config reference |
| `HERMES_ACCEPT_HOOKS` | Rename | config.py |
| `HERMES_HEAPDUMP_ON_START` | Rename | TUI entry.tsx |
| `HERMES_KANBAN_BOARD` | Rename | kanban |
| `HERMES_BACKGROUND_NOTIFICATIONS` | Rename | config reference |

### GitHub/URL References to Replace
| URL | Location |
|-----|----------|
| `github.com/NousResearch/hermes-agent` | banner.py:130, main.py:5950/6277-6282/6416/6430/6438/7358 |
| `hermes-agent.nousresearch.com` | config.py:1434 |
| `raw.githubusercontent.com/NousResearch/hermes-agent/` | uninstall.py:667 |
| `https://nousresearch.com` or similar branding | banner.py |

### Python Module/Class Names to Consider
| Name | Type | Files |
|------|------|-------|
| `hermes_bootstrap` | Module | gateway/run.py |
| `hermes_cli` | Package | All CLI files |
| `hermes_constants` | Module | Throughout |
| `hermes_state` | Module | Session DB |
| `hermes_logging` | Module | Logging |
| `HermesCLI` | Class | cli.py |
| `get_hermes_home()` | Function | hermes_constants.py |
| `display_hermes_home()` | Function | hermes_constants.py |

---

## 7. GATEWAY SYSTEM

### Platform Adapter Inventory (34 platforms)
| Platform | File | Dependencies | Key Features |
|----------|------|-------------|--------------|
| Telegram | telegram.py | python-telegram-bot | Draft streaming, reactions, voice, topics |
| Discord | discord.py | discord.py | Voice, slash commands, approval buttons, threads |
| Slack | slack.py | slack-sdk | Socket mode, threads, reactions |
| WhatsApp | whatsapp.py | (platform SDK) | Media, voice notes |
| Signal | signal.py | signal-cli | E2EE |
| Matrix | matrix.py | matrix-nio | E2EE, threads |
| Mattermost | mattermost.py | (REST API) | Channels, threads |
| Feishu | feishu.py | (REST API) | Rich cards, comments |
| WeCom | wecom.py | (REST API) | Callback mode |
| Weixin | weixin.py | (REST API) | Chinese WeChat |
| DingTalk | dingtalk.py | (REST API) | AI Cards, custom protocols |
| QQ Bot | qqbot/ | (protobuf) | Chinese QQ platform |
| Yuanbao | yuanbao.py | (protobuf) | Tencent Yuanbao |
| BlueBubbles | bluebubbles.py | (REST API) | iMessage |
| Email | email.py | smtplib/imap | POP3/IMAP/SMTP |
| SMS | sms.py | twilio | Twilio SMS |
| API Server | api_server.py | FastAPI | OpenAI-compatible API |
| Webhook | webhook.py | FastAPI | GitHub/GitLab events |
| Home Assistant | homeassistant.py | websockets | Smart home control |
| IRC | (plugin) | irc | Text-based chat |
| (others) | (plugin-based) | (varies) | Extensible via PlatformRegistry |

### BasePlatformAdapter Abstract Interface
```python
class BasePlatformAdapter(ABC):
    # Required overrides:
    async def connect(self) -> bool        # Connect and start receiving
    async def disconnect(self) -> None      # Disconnect from platform
    async def send(self, chat_id, content, reply_to=None, metadata=None) -> SendResult

    # Optional overrides:
    async def send_draft(self, chat_id, draft_id, content, metadata=None) -> SendResult
    async def edit_message(self, chat_id, message_id, content, metadata=None) -> SendResult
    async def create_handoff_thread(self, parent_chat_id, name) -> Optional[str]
    def supports_draft_streaming(self, chat_type=None, metadata=None) -> bool

    # Session management:
    set_message_handler(callback)           # Register message handler
    set_busy_handler(callback)              # Register busy-state handler
    handle_message(event)                    # Process incoming message
    mark_session_complete(session_key)       # Mark session as complete
```

### Gateway Message Flow
```
Platform Event (e.g., Discord message)
  → base.py: handle_message(event)
    → Deduplication check
    → Session lookup / creation
    → Authorization check
      → gateway/run.py: _process_message()
        → AIAgent instantiation / reuse (LRU cache, max 128)
        → run_conversation()
          → tool calls via handle_function_call()
          → response via adapter.send()
```

### Two-Guard Message Processing
1. **Base adapter guard** (`_active_sessions`): Queues messages while agent is running
2. **Gateway runner guard** (`_process_message`): Intercepts admin commands (/stop, /new, etc.) before they reach agent

---

## 8. CUSTOMIZATION ROADMAP

### Phase 1: Branding & Display (Config-Only)
1. Create `~/.hermes/skins/jade.yaml` with new colors, agent_name, branding strings
2. Set `display.skin: jade` in config.yaml
3. Set `display.personality`, `display.tool_progress`, `display.language` as needed

### Phase 2: Core Message / System Prompt
1. Create custom `SOUL.md` in HERMES_HOME (overrides default_soul.py)
2. Set up custom `prefill_messages_file` in config.yaml
3. Configure `agent.*` settings (max_turns, gateway_timeout, etc.)

### Phase 3: Plugin Development
1. Create `plugins/jade-core/` with custom tools
2. Create `plugins/jade-memory/` if custom memory provider needed
3. Create `plugins/jade-platforms/` for custom messaging platforms

### Phase 4: Skill Authoring
1. Create skills under `skills/jade/` with standard SKILL.md frontmatter
2. Configure `skills.external_dirs` to point to Jade skill directories
3. Optionally ship skills in `optional-skills/` for explicit install

### Phase 5: Source Fork (if full rebranding required)
If a full "Jade" fork is desired (changing Python package names, internal branding, TUI ASCII art), the following files require modification:

**TUI files to modify:**
- `ui-tui/src/theme.ts` — BRAND constant (name, icon, welcome, goodbye)
- `ui-tui/src/banner.ts` — LOGO_ART and CADUCEUS_ART ASCII art
- `ui-tui/src/components/branding.tsx` — Banner text and tagline
- `ui-tui/src/components/appChrome.tsx` — EMOJI_FRAMES
- `ui-tui/src/components/appLayout.tsx` — Status icon

**Python skin files to modify:**
- `hermes_cli/skin_engine.py` — _BUILTIN_SKINS default branding
- `hermes_cli/default_soul.py` — DEFAULT_SOUL_MD system prompt
- `hermes_cli/banner.py` — Nous Research references

**Python CLI files to modify:**
- `hermes_cli/status.py` — "Hermes Agent Status"
- `hermes_cli/setup.py` — "Hermes Setup", bot_name default
- `hermes_cli/tools_config.py` — "Hermes Tool Configuration"
- `hermes_cli/uninstall.py` — "Hermes Agent Uninstaller"
- `hermes_cli/gateway.py` — "Hermes Gateway Starting..."
- `hermes_cli/config.py` — "Hermes Configuration"
- `hermes_cli/main.py` — Update titles, bot_name defaults, GitHub URLs
- `hermes_cli/slack_cli.py` — Default bot name "Hermes"
- `hermes_cli/claw.py` — Migration banners
- `hermes_cli/_parser.py` — prog="hermes"

**Gateway files to modify:**
- `gateway/config.py` — WhatsApp default header comment

**Package/module renames (major fork):**
- `hermes_cli/` → `jade_cli/`
- `hermes_constants.py` → `jade_constants.py`
- `hermes_state.py` → `jade_state.py`
- `hermes_logging.py` → `jade_logging.py`
- `hermes_bootstrap.py` → `jade_bootstrap.py`
- `hermes_*.py` files → `jade_*.py`
- All `get_hermes_home()` → new function name
- All `display_hermes_home()` → new function name
- `@hermes/ink` npm package rename
- All `HERMES_*` env vars → `JADE_*`
- All `_hermes_core_tools`, `hermes-cli` toolset references
- `hermes` command name → `jade`

---

## 9. KEY FILES REFERENCE

### Must-Read Before Customization
| File | Purpose | Priority |
|------|---------|----------|
| `AGENTS.md` | Development rules and architecture (read first) | **Critical** |
| `hermes_cli/config.py` | DEFAULT_CONFIG and all settings | **Critical** |
| `hermes_cli/skin_engine.py` | Skin/branding system | **Critical** |
| `hermes_cli/default_soul.py` | Default system prompt | **Critical** |
| `ui-tui/src/theme.ts` | TUI theme + branding | **High** |
| `ui-tui/src/banner.ts` | ASCII art logos | **High** |
| `hermes_cli/banner.py` | CLI banner + URLs | **High** |
| `tools/registry.py` | Tool registration | **Medium** |
| `toolsets.py` | Toolset definitions | **Medium** |
| `model_tools.py` | Tool orchestration | **Medium** |
| `gateway/platforms/base.py` | Base adapter class | **Medium** |
| `gateway/platform_registry.py` | Platform registry | **Medium** |
| `gateway/run.py` | Gateway lifecycle (read only, no edit) | **Reference** |
| `cli.py` | CLI orchestrator (read only, no edit) | **Reference** |
| `run_agent.py` | Agent loop (read only, no edit) | **Reference** |

### Files You MAY Modify
- Skin YAML files (`~/.hermes/skins/*.yaml`)
- Config YAML (`~/.hermes/config.yaml`)
- Plugin directories (`plugins/`, `~/.hermes/plugins/`)
- Skill SKILL.md files (`skills/`, `~/.hermes/skills/`)
- `SOUL.md` (`~/.hermes/SOUL.md`)

### Files You MUST NOT Modify
- `run_agent.py`
- `cli.py`
- `gateway/run.py`
- `hermes_cli/main.py`
