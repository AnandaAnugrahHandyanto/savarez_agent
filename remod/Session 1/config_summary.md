# Hermes Config System Analysis - Detailed Summary

## Overview
The hermes_cli/config.py file contains the DEFAULT_CONFIG dictionary (lines 437-1557) which defines all configuration keys and their default values for the Hermes Agent system. The configuration is organized into logical sections including model, agent, terminal, display, compression, auxiliary, memory, skills, curator, gateway platforms, logging, updates, lsp, and many others. Each section contains numerous subkeys with detailed comments explaining their purpose, acceptable values, and behavioral impact.

## Key Sections for Jade Customization

### Display/Branding Section (lines 911-976)
This section controls all visual aspects that would need modification for Jade branding:
- `skin`: Controls color scheme ("default", "ares", "mono", "slate")
- `colors`: Subsection with specific color values for banner, response box, etc.
- `spinner`: Controls spinner faces, thinking verbs, and wings animations
- `branding`: Contains agent_name, welcome message, response_label, prompt_symbol
- `tool_prefix`: The symbol shown before tool output (default: "┊")
- `tool_emojis`: Per-tool emoji mappings
- `response_border`, `response_label`: Response box styling
- `banner_*`: Various banner panel styling options
- `runtime_footer`: Gateway runtime metadata shown in final messages
- `ephemeral_system_ttl`: Auto-deletion time for system notices

### Agent Behavior Section (lines 443-523)
Controls core agent behavior that may need tuning:
- `max_turns`: Tool-calling iterations per conversation (default: 90)
- `gateway_timeout`: Inactivity timeout for gateway agent execution (default: 1800s)
- `restart_drain_timeout`: Graceful drain for gateway stop/restart (default: 180s)
- `api_max_retries`: Retry attempts for API errors (default: 3)
- `tool_use_enforcement`: How strongly to enforce tool use ("auto", true/false, or model substrings)
- `gateway_timeout_warning`: Warning threshold before full timeout (default: 900s)
- `clarify_timeout`: Seconds to wait for clarify-tool response (default: 600s)
- `gateway_notify_interval`: "Still working" notification interval (default: 180s)
- `gateway_auto_continue_freshness`: Freshness window for auto-continue notes (default: 3600s)
- `image_input_mode`: How user images are presented to model ("auto", "native", "text")

### Terminal Settings (lines 525-604)
Controls execution environment:
- `backend`: "local", "docker", "ssh", "modal", "daytona", "singularity"
- `cwd`: Working directory ("." for current directory)
- `timeout`: Command timeout in seconds (default: 180)
- `container_*`: Resource limits for container backends (CPU, memory, disk)
- `persistent_shell`: Keep shell across execute() calls (default: true)
- `auto_source_bashrc`: Source shell rc files in login shell (default: true)
- `docker_*`: Docker-specific settings (image, volumes, env, etc.)
- `shell_init_files`: Files to source for environment snapshot

### Memory & Skills Configuration
- `memory` section (lines 1080-1090): 
  - `memory_enabled`: Toggle persistent memory (default: true)
  - `user_profile_enabled`: Toggle user profile memory (default: true)
  - `memory_char_limit`: System prompt memory limit (default: 2200 chars)
  - `user_char_limit`: User profile memory limit (default: 1375 chars)
  - `provider`: External memory provider ("" for built-in only)
  
- `skills` section (lines 1153-1183):
  - `external_dirs`: Additional skill directories to scan
  - `template_vars`: Substitute ${HERMES_SKILL_DIR} in SKILL.md (default: true)
  - `inline_shell`: Execute !`cmd` snippets in skills (default: false)
  - `inline_shell_timeout`: Timeout for inline shell (default: 10s)
  - `guard_agent_created`: Scan agent-created skills for risky keywords (default: false)
  
- `curator` section (lines 1185-1214):
  - `enabled`: Toggle background skill maintenance (default: true)
  - `interval_hours`: Hours between curator runs (default: 168 = 7 days)
  - `min_idle_hours`: Minimum agent idle before running (default: 2)
  - `stale_after_days`: Days until skill marked stale (default: 30)
  - `archive_after_days`: Days until skill archived (default: 90)
  - `backup`: Pre-run backup settings (enabled: true, keep: 5)

### Tool Output & Compression Limits
- `tool_output` section (lines 704-708):
  - `max_bytes`: Terminal output cap sent to model (default: 50_000 chars)
  - `max_lines`: ReadFile pagination cap (default: 2000)
  - `max_line_length`: Per-line cap for line-numbered view (default: 2000)
  
- `compression` section (lines 728-734):
  - `enabled`: Toggle context compression (default: true)
  - `threshold`: Compress when context usage exceeds this ratio (default: 0.50)
  - `target_ratio`: Fraction of threshold to preserve as recent tail (default: 0.20)
  - `protect_last_n`: Minimum recent messages to keep uncompressed (default: 20)
  - `hygiene_hard_message_limit`: Force-compress threshold by message count (default: 400)

### Gateway/Platform Settings
Platform-specific sections control how Hermes behaves on different messaging platforms:
- `discord` (lines 1233-1255): require_mention, free_response_channels, allowed_channels, auto_thread, reactions, channel_prompts, server_actions, dm_role_auth_guild
- `slack` (lines 1225-1231): Similar Discord settings for Slack platform
- `telegram` (lines 1265-1270): reactions, channel_prompts, allowed_chats
- `mattermost`, `matrix`, `whatsapp`, `bluebubbles`, `qq`, `irc`: Similar platform-specific settings
- `webhook` and `api_server`: Settings for webhook and API server platforms

### Auxiliary Model Configuration (lines 916-909)
Controls provider/model for side-LLM tasks:
- `vision`: Provider/model for image analysis
- `web_extract`: Provider/model for web content extraction
- `compression`: Provider/model for context compression
- `session_search`: Provider/model for searching chat history
- `skills_hub`: Provider/model for skills hub operations
- `approval`: Provider/model for command approval decisions
- `mcp`: Provider/model for MCP operations
- `title_generation`: Provider/model for generating chat titles
- `triage_specifier`: Provider/model for Kanban triage specification
- `curator`: Provider/model for skill curation review

### Special Features
- `checkpoints` (lines 656-683): Automatic snapshots before destructive file operations
- `prompt_caching` (lines 743-747): Anthropic prompt caching settings
- `openrouter` (lines 764-768): OpenRouter-specific settings (response cache, coding score)
- `bedrock` (lines 770-788): AWS Bedrock provider configuration
- `delegation` (lines 1092-1130): Subagent delegation overrides
- `goals` (lines 1137-1151): Persistent cross-turn goals (Ralph-style loop)
- `prefill_messages_file` (line 1135): JSON file for few-shot priming
- `privacy` (lines 984-986): PII redaction settings
- `tts` and `stt` (lines 989-1052): Text-to-speech and speech-to-text configuration
- `voice` (lines 1054-1061): Voice recording settings
- `human_delay` (lines 1063-1067): Artificial delay between agent turns
- `context` (lines 1069-1077): Context window management engine
- `lsp` (lines 1508-1553): Language Server Protocol integration
- `model_catalog` (lines 1427-1446): Remotely-hosted model catalog manifest
- `network` (lines 1448-1454): Network connectivity workarounds
- `sessions` (lines 1456-1482): Session storage and cleanup
- `onboarding` (lines 1484-1489): First-touch onboarding hints
- `updates` (lines 1491-1506): Hermes update behavior

## Configuration Loading Mechanism
The system uses several functions for configuration management:
- `get_config_path()`: Returns path to config.yaml (~/.hermes/config.yaml)
- `get_env_path()`: Returns path to .env file (~/.hermes/.env)
- `load_config()`: Main function that loads and merges DEFAULT_CONFIG with user config
- `read_raw_config()`: Loads user config without merging defaults
- `save_config()`: Saves configuration to disk atomically
- Environment variable bridging: Certain settings in config.yaml are bridged to environment variables for child processes (e.g., terminal.cwd → TERMINAL_CWD)
- Version migration: Automatic migration of config versions via migrate_config() function
- Caching: Sophisticated caching system to avoid repeated YAML parsing (_LOAD_CONFIG_CACHE, _RAW_CONFIG_CACHE)
- Thread safety: Uses RLock (_CONFIG_LOCK) for concurrent access safety
- Validation: validate_config_structure() checks for common configuration errors
- Migration: Handles version upgrades and environment variable deprecations

## Key Learnings for Jade Customization
1. **Never modify core files**: As per AGENTS.md, avoid changing run_agent.py, cli.py, gateway/run.py, hermes_cli/main.py
2. **Branding is in display section**: All visual branding elements are configurable via the display section in config.yaml
3. **Plugin system is extensible**: New tools, skills, and memory providers can be added via plugins without modifying core
4. **Skills use SKILL.md format**: Standard frontmatter with name, description, version, platforms, metadata.hermes.*
5. **Configuration is hierarchical**: Nested sections allow fine-grained control over different subsystems
6. **Environment variables bridge**: .env file handles secrets while config.yaml handles non-secret preferences
7. **Toolsets are configurable**: Enable/disable tools per-platform via config.yaml or hermes tools command
8. **Memory and skills are profile-aware**: Each profile gets isolated memory and skill storage
9. **Gateway settings are platform-specific**: Each messaging platform has tailored configuration options
10. **Auxiliary models allow task-specific routing**: Different providers/models can be used for different side tasks

## Files Examined
- hermes_cli/config.py (primary focus for configuration system)
- Referenced hermes_constants.py for get_hermes_home() function
- Previously examined AGENTS.md for development rules and forbidden files
- Previously examined plugin examples (disk-cleanup, spotify) for plugin structure
- Previously examined skill examples for SKILL.md format

## Next Steps Required
With permission, proceed to:
1. STEP 5: Read TUI files (ui-tui/src/entry.tsx and ui-tui/src/app.tsx)
2. STEP 6: Search for all branding strings (Hermes, NousResearch, etc.)
3. STEP 7: Read gateway structure and Discord platform adapter
4. STEP 8: Compile final summary with all findings