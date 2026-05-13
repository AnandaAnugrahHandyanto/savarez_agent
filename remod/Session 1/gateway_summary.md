# Gateway System Analysis

## STEP 7: Gateway/Messaging System

### Architecture Overview
The gateway is the messaging-platform integration layer that allows Hermes to run as a persistent bot on Telegram, Discord, WhatsApp, Slack, and 20+ other platforms. It uses an extensible adapter pattern where each platform inherits from `BasePlatformAdapter` and implements 3 abstract methods: `connect()`, `disconnect()`, and `send()`.

### Directory Structure (23 gateway/ + 34 platforms/)
```
gateway/
├── run.py                  # GatewayRunner — main lifecycle (16672 lines)
├── config.py               # Platform enum, PlatformConfig, HomeChannel, SessionResetPolicy (1803 lines)
├── session.py              # Gateway session management
├── platform_registry.py    # Extensible PlatformRegistry for plugin adapters
├── delivery.py             # Cross-platform message delivery
├── display_config.py       # Per-platform display overrides
├── hooks.py                # Gateway lifecycle hooks
├── mirror.py               # Cross-platform message mirroring
├── pairing.py              # Device/link pairing for gateway authentication
├── restart.py              # Graceful restart logic
├── session_context.py      # Session context management
├── slash_access.py         # Slash command access control
├── status.py               # Gateway status reporting
├── stream_consumer.py      # Streaming response consumers
├── channel_directory.py    # Channel/chat directory for discovery
├── runtime_footer.py       # Footer metadata appended to responses
├── shutdown_forensics.py   # Diagnostics on shutdown
├── sticker_cache.py        # Sticker/media caching
├── whatsapp_identity.py    # WhatsApp-specific identity management
├── builtin_hooks/          # Extension point for always-registered hooks
└── platforms/              # 34 platform adapter implementations (34 entries)
    ├── base.py             # BasePlatformAdapter ABC (3716 lines)
    ├── telegram.py         # Telegram adapter (largest)
    ├── discord.py          # Discord adapter (5101 lines)
    ├── slack.py            # Slack adapter
    ├── whatsapp.py         # WhatsApp adapter
    ├── signal.py           # Signal adapter
    ├── matrix.py           # Matrix adapter
    ├── mattermost.py       # Mattermost adapter
    ├── feishu.py           # Feishu/Lark adapter
    ├── wecom.py            # WeCom adapter
    ├── weixin.py           # Weixin/WeChat adapter
    ├── dingtalk.py         # DingTalk adapter
    ├── email.py            # Email adapter
    ├── sms.py              # SMS adapter
    ├── api_server.py       # OpenAI-compatible API server
    ├── webhook.py          # Webhook receiver
    ├── homeassistant.py    # Home Assistant adapter
    ├── bluebubbles.py      # iMessage via BlueBubbles
    ├── qqbot/              # QQ Bot adapter (directory with proto files)
    ├── yuanbao.py          # Yuanbao adapter
    ├── helpers.py          # Shared helpers (MessageDeduplicator, ThreadParticipationTracker)
    └── ADDING_A_PLATFORM.md  # Guide for adding new platforms
```

### Platform Config (gateway/config.py)
- `Platform` enum (31+ values): All built-in platform identifiers + dynamic `_missing_()` for plugin platforms
- `PlatformConfig` dataclass: enabled, token, api_key, home_channel, reply_to_mode, gateway_restart_notification, extra (platform-specific settings)
- `HomeChannel` dataclass: platform, chat_id, name, thread_id — default delivery target per platform
- `SessionResetPolicy` dataclass: mode (daily/idle/both/none), at_hour, idle_minutes, notify
- Plugin platforms auto-discovered by scanning `plugins/platforms/` for directories with `__init__.py` + `plugin.yaml`

### BasePlatformAdapter (gateway/platforms/base.py, 3716 lines)
Abstract base class with:
- **Abstract methods**: `connect()`, `disconnect()`, `send()`
- **Session management**: `_active_sessions` dict, `_pending_messages`, `_session_tasks` for interrupt support
- **Message handling**: `handle_message()` → `_process_message()` flow
- **Media helpers**: `cache_image_from_url/bytes`, `cache_audio_from_url/bytes`, `cache_document_from_bytes`
- **Streaming support**: `send_draft()`, `edit_message()`, `supports_draft_streaming()`
- **Voice support**: Auto-TTS, typing indicators, voice activity detection
- **Approval**: Button-based approval UI (Telegram, Discord, Slack)
- **Security**: Token locks for profile isolation, user authorization, role filtering
- **Maintenance**: `set_message_handler()`, `set_busy_handler()`, `set_session_store()`, `acquire_scoped_lock()`

### GatewayRunner (gateway/run.py, 16672 lines)
Main class managing the gateway lifecycle:
- **Startup**: Reads config → resolves platform list → creates adapters → connects each → enters main loop
- **Main loop**: asyncio event loop dispatching platform events to `_process_message()`
- **Message flow**: Platform event → `handle_message()` → session lookup → AIAgent creation/reuse → `run_conversation()` → response delivery via adapter's `send()`
- **Session cache**: LRU agent cache (max 128 agents, 1h idle TTL)
- **Agent lifecycle**: Per-session AIAgent instantiation with isolated context, toolsets, memory
- **Slash commands**: `/stop`, `/new`, `/reset`, `/status`, `/approve`, `/deny`, `/help`, `/info`, etc. — routed inline bypassing agent loop
- **Interrupt handling**: Agent cancellation, graceful drain on restart
- **Cross-platform delivery**: `delivery.py` → route messages to multiple platforms
- **Handoff**: CLI→gateway session handoff watcher

### DiscordAdapter (gateway/platforms/discord.py, 5101 lines)
Key platform-specific implementation:
- Uses `discord.py` with `commands.Bot` subclass
- MAX_MESSAGE_LENGTH = 2000 (Discord limit)
- Voice channel support (join/leave/play/receive)
- Native slash commands (`/ask`, `/reset`, `/status`, `/stop`)
- Button-based approval UI for dangerous commands
- Thread auto-creation and participation tracking
- Text batching (merges rapid successive messages with delay)
- Typing indicator loops per channel
- Reaction-based feedback (`_add_reaction_interaction`)
- User ID/role authorization via `_allowed_user_ids` / `_allowed_role_ids`
- Message deduplication across reconnects (Discord RESUME replay)
- `DISCORD_ALLOWED_ROLES` env var for guild-level access control
- Channel-specific configurations via `discord` config section

### Platform Registry (gateway/platform_registry.py)
- `PlatformEntry` dataclass: name, label, adapter_factory, check_fn, validate_config, required_env, install_hint, setup_fn, platform_hint, etc.
- `PlatformRegistry` singleton: register/unregister/get/create_adapter/all_entries
- Plugin platforms register via `plugin_context.register_platform()` in their `__init__.py`
- Built-in adapters still use the legacy if/elif chain in `_create_adapter()`
- Override semantics: last-writer-wins (plugins can replace built-in adapters)

### Key Design Patterns
1. **Adapter Pattern**: All platform adapters implement `BasePlatformAdapter` ABC with connect/disconnect/send
2. **Registry Pattern**: `platform_registry` singleton for discovery, creation, and validation
3. **Singleton GatewayRunner**: Manages the main event loop, agent cache, and platform coordination
4. **Session Isolation**: Each chat/conversation gets its own AIAgent instance with isolated context
5. **Two-guard Message Processing**: Messages are guarded by (1) base adapter's `_active_sessions` and (2) gateway runner's skip lists for admin commands
6. **Token-level Locking**: `acquire_scoped_lock()` prevents two profiles from using the same bot credential
7. **Plugin Extensibility**: New platforms added via `PlatformEntry` registration without modifying core gateway files

### Key Branding Issues for Jade Customization
- Platform names "Hermes" appear in config defaults (e.g., WhatsApp header "⚕ *Hermes Agent*")
- Bot display name defaults to "Hermes" in CLI args (slack_cli.py line 117, main.py line 9629)
- `gateway/run.py` banners display "⚕ Hermes Gateway Starting..."
- `gateway/config.py` line 1260 references "⚕ *Hermes Agent*" header comment
- Platform `PlatformEntry` `label` values (e.g., "Nous Portal (Nous Research subscription)")
- No "Nous Research" strings in gateway adapter files themselves — they come from the skin/branding layer

### Next Step Required
With permission, proceed to:
- STEP 8: Compile final summary with all findings for Jade customization
