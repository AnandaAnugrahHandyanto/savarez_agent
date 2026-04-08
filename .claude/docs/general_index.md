# General Index

## Root

- `batch_runner.py` - Parallel batch runner to process datasets through the agent and save trajectories. Key: `AIAgent`, `_process_single_prompt`, `_process_batch_worker`, `_extract_tool_stats`, `ALL_POSSIBLE_TOOLS` [SOURCE_CODE]
- `cli.py` - Interactive terminal CLI for Hermes Agent, TUI, config bridging and browser/CDP auto-launch helpers. Key: `HermesCLI`, `_get_chrome_debug_candidates`, `_load_prefill_messages`, `_parse_reasoning_config`, `load_cli_config` [CLI]
- `hermes_constants.py` - Import-safe, single-source constants and helpers for HERMES_HOME, optional-skills, legacy dirs, reasoning config, and provider URLs. Key: `get_hermes_home`, `get_optional_skills_dir`, `get_hermes_dir`, `display_hermes_home`, `VALID_REASONING_EFFORTS` [SOURCE_CODE]
- `hermes_logging.py` - Centralized, idempotent logging setup with redaction and rotating file handlers.. Key: `_logging_initialized`, `_LOG_FORMAT`, `_LOG_FORMAT_VERBOSE`, `_NOISY_LOGGERS`, `setup_logging` [SOURCE_CODE]
- `hermes_state.py` - SQLite session store with FTS and concurrency handling. Key: `SessionDB`, `SCHEMA_SQL`, `FTS_SQL`, `_execute_write`, `create_session` [SOURCE_CODE]
- `hermes_time.py` - Timezone-aware clock helper that returns a tz-aware datetime based on env/config or server-local time.. Key: `_resolve_timezone_name`, `_get_zoneinfo`, `get_timezone`, `get_timezone_name`, `now` [SOURCE_CODE]
- `mcp_serve.py` - StdIO MCP server and EventBridge that exposes Hermes conversations and events to MCP clients.. Key: `_get_sessions_dir`, `_get_session_db`, `_load_sessions_index`, `_load_channel_directory`, `_extract_message_content` [SOURCE_CODE]
- `mini_swe_runner.py` - Standalone Mini-SWE runner that uses Hermes execution environments and emits Hermes-format trajectories.. Key: `TERMINAL_TOOL_DEFINITION`, `create_environment`, `MiniSWERunner`, `_create_env`, `_cleanup_env` [CLI]
- `model_tools.py` - Tool discovery and dispatch layer that exposes tool schemas and runs tool handlers (sync↔async bridging).. Key: `_get_tool_loop`, `_get_worker_loop`, `_run_async`, `_discover_tools`, `TOOL_TO_TOOLSET_MAP` [SOURCE_CODE]
- `package.json` - Node package metadata for browser tool dependencies [CONFIG]
- `pyproject.toml` - Python project metadata, dependencies and entrypoints [CONFIG]
- `rl_cli.py` - Dedicated CLI entrypoint to run RL training workflows with extended timeouts and RL tools.. Key: `DEFAULT_MODEL`, `DEFAULT_BASE_URL`, `load_hermes_config`, `RL_MAX_ITERATIONS`, `RL_SYSTEM_PROMPT` [CLI]
- `run_agent.py` - Standalone AIAgent implementation: conversation loop, tool-calling, streaming, and tool result handling.. Key: `_SafeWriter`, `IterationBudget`, `_NEVER_PARALLEL_TOOLS`, `_should_parallelize_tool_batch`, `_sanitize_surrogates` [SOURCE_CODE]
- `setup-hermes.sh` - Interactive bootstrap script to provision Python 3.11, install deps, and wire the hermes CLI for local development. Key: `SCRIPT_DIR`, `PYTHON_VERSION`, `UV_CMD`, `VIRTUAL_ENV`, `HERMES_BIN` [BUILD]
- `toolset_distributions.py` - Defines named distributions of toolsets and provides sampling/inspection utilities.. Key: `DISTRIBUTIONS`, `get_distribution`, `list_distributions`, `sample_toolsets_from_distribution`, `validate_distribution` [SOURCE_CODE]
- `toolsets.py` - Defines the canonical toolset manifest and utilities to resolve, validate, and create toolsets.. Key: `_HERMES_CORE_TOOLS`, `TOOLSETS`, `get_toolset`, `resolve_toolset`, `resolve_multiple_toolsets` [SOURCE_CODE]
- `trajectory_compressor.py` - Compresses agent trajectories into token budgets using summarization. Key: `CompressionConfig`, `TrajectoryCompressor`, `TrajectoryMetrics` [SOURCE_CODE]
- `utils.py` - Shared helpers for truthy env coercion and atomic JSON/YAML file writes.. Key: `TRUTHY_STRINGS`, `is_truthy_value`, `env_var_enabled`, `atomic_json_write`, `atomic_yaml_write` [SOURCE_CODE]

## acp_adapter/

- `auth.py` - Detect configured Hermes runtime provider for ACP adapter. Key: `detect_provider`, `has_provider` [SOURCE_CODE]
- `entry.py` - CLI entrypoint for the Hermes ACP adapter server [CLI]
- `events.py` - Factories producing callbacks that forward AIAgent events as ACP updates. Key: `make_tool_progress_cb`, `make_thinking_cb`, `make_step_cb`, `make_message_cb` [SOURCE_CODE]
- `permissions.py` - Bridge ACP permission requests to Hermes approval callbacks. Key: `make_approval_callback`, `_KIND_TO_HERMES` [SOURCE_CODE]
- `server.py` - ACP protocol Agent implementation that exposes Hermes Agent over the Agent Client Protocol. Key: `_executor`, `HERMES_VERSION`, `_extract_text`, `HermesACPAgent`, `on_connect` [SOURCE_CODE]
- `session.py` - ACP session manager mapping ACP sessions to Hermes AIAgents. Key: `SessionState`, `SessionManager`, `_persist`, `_restore`, `_make_agent` [SOURCE_CODE]
- `tools.py` - Helpers to map Hermes tool calls into ACP ToolKind and content. Key: `TOOL_KIND_MAP`, `get_tool_kind`, `make_tool_call_id`, `build_tool_start`, `build_tool_complete` [SOURCE_CODE]

## agent/

- `__init__.py` - Agent subpackage initializer and module grouping [SOURCE_CODE]
- `anthropic_adapter.py` - Anthropic Messages API client and auth helpers. Key: `build_anthropic_client`, `read_claude_code_credentials`, `_is_oauth_token` [SOURCE_CODE]
- `auxiliary_client.py` - Resolver and adapters for auxiliary (side-task) LLM/vision clients. Key: `_select_pool_entry`, `_convert_content_for_responses`, `_CodexCompletionsAdapter`, `CodexAuxiliaryClient`, `_AnthropicCompletionsAdapter` [SOURCE_CODE]
- `builtin_memory_provider.py` - Adapter exposing MEMORY.md/USER.md as the builtin memory provider. Key: `BuiltinMemoryProvider`, `system_prompt_block`, `get_tool_schemas` [SOURCE_CODE]
- `context_compressor.py` - Automatic conversation context compressor and summarizer. Key: `ContextCompressor`, `SUMMARY_PREFIX`, `_prune_old_tool_results`, `_generate_summary`, `should_compress_preflight` [SOURCE_CODE]
- `context_references.py` - Parse and expand @-style context references into attachable content. Key: `ContextReference`, `ContextReferenceResult`, `parse_context_references`, `preprocess_context_references_async`, `_ensure_reference_path_allowed` [SOURCE_CODE]
- `copilot_acp_client.py` - OpenAI-compatible shim that uses GitHub Copilot ACP as a chat backend. Key: `CopilotACPClient`, `_format_messages_as_prompt`, `_extract_tool_calls_from_text`, `_run_prompt`, `ACP_MARKER_BASE_URL` [SOURCE_CODE]
- `credential_pool.py` - Credential pool implementation managing multiple provider credentials, rotation, refreshing, seeding and soft leasing.. Key: `STATUS_OK`, `STATUS_EXHAUSTED`, `AUTH_TYPE_OAUTH`, `CUSTOM_POOL_PREFIX`, `_EXTRA_KEYS` [SOURCE_CODE]
- `display.py` - CLI display utilities: spinners, tool previews and inline diffs. Key: `build_tool_preview`, `capture_local_edit_snapshot`, `extract_edit_diff`, `LocalEditSnapshot`, `_render_inline_unified_diff` [SOURCE_CODE]
- `insights.py` - Analyze session history and produce usage/cost/tool/activity insights. Key: `InsightsEngine`, `_get_tool_usage`, `_get_sessions`, `_estimate_cost` [SOURCE_CODE]
- `memory_manager.py` - Orchestrates builtin and one external memory provider. Key: `MemoryManager`, `sanitize_context`, `build_memory_context_block` [SOURCE_CODE]
- `memory_provider.py` - Abstract base class and lifecycle for memory provider plugins. Key: `MemoryProvider`, `is_available`, `get_tool_schemas`, `on_pre_compress` [SOURCE_CODE]
- `model_metadata.py` - Utilities for discovering and caching model metadata (context lengths, max tokens, pricing) and probing local model servers.. Key: `_PROVIDER_PREFIXES`, `_OLLAMA_TAG_PATTERN`, `_strip_provider_prefix`, `CONTEXT_PROBE_TIERS`, `DEFAULT_CONTEXT_LENGTHS` [SOURCE_CODE]
- `models_dev.py` - Integration with the community models.dev registry: fetch, cache, and expose provider/model metadata and capability helpers.. Key: `ModelInfo`, `ProviderInfo`, `ModelCapabilities`, `PROVIDER_TO_MODELS_DEV`, `_NOISE_PATTERNS` [SOURCE_CODE]
- `prompt_builder.py` - Stateless utilities that assemble the agent's system prompt: identity, platform hints, context files, and skills index (with caching and snapshotting).. Key: `_scan_context_content`, `_find_git_root`, `_find_hermes_md`, `_strip_yaml_frontmatter`, `DEFAULT_AGENT_IDENTITY` [SOURCE_CODE]
- `prompt_caching.py` - Apply Anthropic prompt cache_control markers (system_and_3). Key: `apply_anthropic_cache_control`, `_apply_cache_marker` [SOURCE_CODE]
- `redact.py` - Regex-based secret redaction for logs and outputs. Key: `_REDACT_ENABLED`, `redact_sensitive_text`, `_mask_token`, `RedactingFormatter`, `_PREFIX_RE` [SOURCE_CODE]
- `skill_commands.py` - Slash-command integration and skill invocation helpers. Key: `scan_skill_commands`, `build_skill_invocation_message`, `build_preloaded_skills_prompt`, `_load_skill_payload`, `build_plan_path` [SOURCE_CODE]
- `skill_utils.py` - Lightweight skill metadata utilities and frontmatter parsing. Key: `parse_frontmatter`, `skill_matches_platform`, `get_external_skills_dirs`, `discover_all_skill_config_vars`, `resolve_skill_config_values` [SOURCE_CODE]
- `smart_model_routing.py` - Heuristic cheap-vs-strong model routing per user turn. Key: `choose_cheap_model_route`, `resolve_turn_route`, `_COMPLEX_KEYWORDS`, `_URL_RE` [SOURCE_CODE]
- `subdirectory_hints.py` - Discover and inject project hint files when visiting subdirectories. Key: `SubdirectoryHintTracker`, `_HINT_FILENAMES`, `_load_hints_for_directory` [SOURCE_CODE]
- `title_generator.py` - Asynchronous session title auto-generation from first exchange. Key: `generate_title`, `auto_title_session`, `maybe_auto_title` [SOURCE_CODE]
- `trajectory.py` - Trajectory utilities: format conversion and JSONL saving. Key: `convert_scratchpad_to_think`, `has_incomplete_scratchpad`, `save_trajectory` [SOURCE_CODE]
- `usage_pricing.py` - Normalize usage and estimate token-based costs across providers. Key: `CanonicalUsage`, `PricingEntry`, `estimate_usage_cost`, `normalize_usage`, `resolve_billing_route` [SOURCE_CODE]

## cron/

- `__init__.py` - Cron job scheduler public API and tick entrypoint export. Key: `create_job`, `list_jobs`, `trigger_job`, `tick` [SOURCE_CODE]
- `jobs.py` - Create, schedule, persist, and compute next-run times for cron jobs. Key: `parse_schedule`, `compute_next_run`, `create_job`, `load_jobs`, `save_jobs` [SOURCE_CODE]
- `scheduler.py` - Schedules and executes due cron jobs, runs optional scripts, and delivers outputs to platforms.. Key: `SILENT_MARKER`, `_SCRIPT_TIMEOUT`, `_resolve_origin`, `_resolve_delivery_target`, `_deliver_result` [SOURCE_CODE]

## docker/

- `entrypoint.sh` - Docker image entrypoint: bootstrap HERMES_HOME and run hermes [BUILD]

## environments/

- `__init__.py` - Expose Atropos RL environment integration submodules. Key: `AgentResult`, `HermesAgentLoop`, `ToolContext` [SOURCE_CODE]
- `agent_loop.py` - Reusable multi-turn agent loop with tool-calling dispatch. Key: `HermesAgentLoop`, `AgentResult`, `ToolError`, `resize_tool_pool`, `_extract_reasoning_from_message` [SOURCE_CODE]
- `agentic_opd_env.py` - Atropos environment for on-policy distillation (agentic OPD) on coding tasks. Key: `AgenticOPDConfig`, `AgenticOPDEnv`, `_build_hint_judge_messages`, `_parse_hint_result` [SOURCE_CODE]
- `hermes_base_env.py` - Abstract Atropos RL environment for running Hermes agent rollouts. Key: `HermesAgentEnvConfig`, `HermesAgentBaseEnv`, `_resolve_tools_for_group`, `collect_trajectory` [SOURCE_CODE]
- `patches.py` - Compatibility monkey-patch stub for async tool safety. Key: `apply_patches` [SOURCE_CODE]
- `tool_context.py` - Per-rollout unrestricted tool access wrapper for rewards/verifiers. Key: `ToolContext`, `_run_tool_in_thread`, `terminal`, `upload_file` [SOURCE_CODE]
- `web_research_env.py` - RL environment for multi-step web research tasks. Key: `WebResearchEnvConfig`, `WebResearchEnv`, `compute_reward`, `evaluate` [SOURCE_CODE]

## environments/benchmarks/tblite/

- `run_eval.sh` - Shell script to run the OpenThoughts-TBLite evaluation [BUILD]
- `tblite_env.py` - Configuration and entry for OpenThoughts-TBLite eval environment. Key: `TBLiteEvalConfig`, `TBLiteEvalEnv`, `config_init` [SOURCE_CODE]

## environments/benchmarks/terminalbench_2/

- `terminalbench2_env.py` - Terminal-Bench 2.0 evaluation environment and orchestration. Key: `TerminalBench2EvalConfig`, `TerminalBench2EvalEnv`, `_resolve_task_image`, `rollout_and_score_eval` [SOURCE_CODE]

## environments/benchmarks/yc_bench/

- `yc_bench_env.py` - YC-Bench long-horizon evaluation environment orchestration. Key: `YCBenchEvalConfig`, `YCBenchEvalEnv`, `_read_final_score`, `_compute_composite_score` [SOURCE_CODE]

## environments/hermes_swe_env/

- `hermes_swe_env.py` - SWE-bench environment running code tasks with Modal sandboxes and test-based rewards. Key: `HermesSweEnvConfig`, `HermesSweEnv`, `format_prompt`, `compute_reward` [SOURCE_CODE]

## environments/tool_call_parsers/

- `__init__.py` - Registry and loader for multiple tool-call parsers. Key: `ToolCallParser`, `register_parser`, `get_parser`, `PARSER_REGISTRY` [SOURCE_CODE]
- `deepseek_v3_1_parser.py` - Parser for DeepSeek V3.1 tool call markup. Key: `DeepSeekV31ToolCallParser`, `PATTERN`, `parse` [SOURCE_CODE]
- `deepseek_v3_parser.py` - Parser for DeepSeek V3 tool call format with JSON args. Key: `DeepSeekV3ToolCallParser`, `PATTERN`, `parse` [SOURCE_CODE]
- `glm45_parser.py` - GLM 4.5 tool call parser for arg_key/arg_value tag format. Key: `Glm45ToolCallParser`, `_deserialize_value`, `FUNC_ARG_REGEX` [SOURCE_CODE]
- `glm47_parser.py` - GLM 4.7 parser extending GLM 4.5 with updated regex handling. Key: `Glm47ToolCallParser`, `FUNC_DETAIL_REGEX` [SOURCE_CODE]
- `hermes_parser.py` - Parser for Hermes-format <tool_call>{...}</tool_call> JSON blocks. Key: `HermesToolCallParser`, `PATTERN`, `parse` [SOURCE_CODE]
- `kimi_k2_parser.py` - Parser for Kimi K2 tool call section tokens and id formats. Key: `KimiK2ToolCallParser`, `PATTERN`, `START_TOKENS` [SOURCE_CODE]
- `llama_parser.py` - Llama 3/4 JSON tool call parser using robust JSON decoding. Key: `LlamaToolCallParser`, `JSON_START`, `parse` [SOURCE_CODE]
- `longcat_parser.py` - Longcat parser matching Hermes logic but with longcat tags. Key: `LongcatToolCallParser`, `PATTERN` [SOURCE_CODE]
- `mistral_parser.py` - Mistral tool call parser supporting pre-v11 and v11+ formats. Key: `MistralToolCallParser`, `_generate_mistral_id`, `BOT_TOKEN` [SOURCE_CODE]
- `qwen3_coder_parser.py` - Qwen3-Coder XML-style tool call parser with type-conversion. Key: `Qwen3CoderToolCallParser`, `_try_convert_value`, `TOOL_CALL_REGEX` [SOURCE_CODE]
- `qwen_parser.py` - Qwen-compatible tool call parser adapter. Key: `QwenToolCallParser`, `register_parser` [SOURCE_CODE]

## gateway/

- `__init__.py` - Gateway package public exports for messaging integration. Key: `GatewayConfig`, `SessionStore`, `DeliveryRouter` [SOURCE_CODE]
- `channel_directory.py` - Cached mapping of reachable messaging channels/contacts per platform. Key: `build_channel_directory`, `resolve_channel_name`, `load_directory`, `format_directory_for_display`, `DIRECTORY_PATH` [SOURCE_CODE]
- `config.py` - Load, validate, and represent gateway/platform configuration (env, yaml, legacy json).. Key: `_coerce_bool`, `_normalize_unauthorized_dm_behavior`, `Platform`, `HomeChannel`, `SessionResetPolicy` [SOURCE_CODE]
- `delivery.py` - Resolve and route delivery targets for cron and agent outputs. Key: `DeliveryTarget`, `DeliveryRouter`, `parse_deliver_spec` [SOURCE_CODE]
- `hooks.py` - Discoverable event hook system for gateway lifecycle events. Key: `HookRegistry`, `HOOKS_DIR`, `HookRegistry.discover_and_load`, `HookRegistry.emit` [SOURCE_CODE]
- `mirror.py` - Append delivery-mirror records into session transcripts. Key: `mirror_to_session`, `_find_session_id`, `_append_to_jsonl`, `_append_to_sqlite` [SOURCE_CODE]
- `pairing.py` - Code-based DM pairing approval flow and approved user store. Key: `PairingStore`, `generate_code`, `approve_code`, `_secure_write`, `is_approved` [SOURCE_CODE]
- `run.py` - Gateway lifecycle controller: load gateway config, start adapters, route messages and manage platform reconnection/exit.. Key: `_ensure_ssl_certs`, `_AGENT_PENDING_SENTINEL`, `_normalize_whatsapp_identifier`, `_expand_whatsapp_auth_aliases`, `_load_gateway_config` [SOURCE_CODE]
- `session.py` - Session management: session keys, session context prompt generation, PII redaction, and session metadata model.. Key: `_now`, `_hash_id`, `_hash_sender_id`, `_hash_chat_id`, `_looks_like_phone` [SOURCE_CODE]
- `status.py` - Gateway runtime PID, status and scoped lock management utilities. Key: `write_pid_file`, `get_running_pid`, `acquire_scoped_lock`, `write_runtime_status` [SOURCE_CODE]
- `sticker_cache.py` - Telegram sticker description cache and injection builders. Key: `CACHE_PATH`, `get_cached_description`, `cache_sticker_description`, `build_sticker_injection` [SOURCE_CODE]
- `stream_consumer.py` - Async consumer bridging sync agent token deltas to platform message edits. Key: `StreamConsumerConfig`, `GatewayStreamConsumer`, `on_delta`, `run`, `_clean_for_display` [SOURCE_CODE]

## gateway/builtin_hooks/

- `boot_md.py` - Boot hook to run ~/.hermes/BOOT.md at gateway startup. Key: `BOOT_FILE`, `_build_boot_prompt`, `_run_boot_agent`, `handle` [SOURCE_CODE]

## gateway/platforms/

- `__init__.py` - Exports platform adapter base types. Key: `BasePlatformAdapter`, `MessageEvent`, `SendResult` [SOURCE_CODE]
- `api_server.py` - OpenAI-compatible HTTP API adapter exposing Hermes via REST. Key: `APIServerAdapter`, `ResponseStore`, `cors_middleware`, `_IdempotencyCache`, `_handle_chat_completions` [SOURCE_CODE]
- `base.py` - Common base classes, cache utilities, and message normalization for platforms. Key: `BasePlatformAdapter`, `MessageEvent`, `SendResult`, `cache_image_from_url`, `cache_document_from_bytes` [SOURCE_CODE]
- `dingtalk.py` - DingTalk Stream Mode adapter for messaging gateway. Key: `DingTalkAdapter`, `_IncomingHandler`, `check_dingtalk_requirements`, `MAX_MESSAGE_LENGTH` [SOURCE_CODE]
- `discord.py` - Discord platform adapter with messaging and voice support. Key: `DiscordAdapter`, `VoiceReceiver`, `check_discord_requirements`, `_clean_discord_id` [SOURCE_CODE]
- `email.py` - IMAP/SMTP email adapter for Hermes gateway. Key: `EmailAdapter`, `_extract_text_body`, `_extract_attachments`, `_is_automated_sender`, `check_email_requirements` [SOURCE_CODE]
- `feishu.py` - Feishu/Lark platform adapter for messaging gateway. Key: `FeishuAdapterSettings`, `FeishuPostParseResult`, `parse_feishu_post_content`, `_build_markdown_post_payload`, `_escape_markdown_text` [SOURCE_CODE]
- `homeassistant.py` - Home Assistant WebSocket adapter for event forwarding. Key: `HomeAssistantAdapter`, `check_ha_requirements`, `_format_state_change` [SOURCE_CODE]
- `matrix.py` - Matrix (matrix-nio) gateway adapter with optional E2EE. Key: `MatrixAdapter`, `check_matrix_requirements`, `_format_state_change`, `_STORE_DIR` [SOURCE_CODE]
- `mattermost.py` - Mattermost gateway adapter for sending/receiving messages. Key: `MattermostAdapter`, `check_mattermost_requirements`, `MAX_POST_LENGTH`, `_api_get`, `_upload_file` [SOURCE_CODE]
- `signal.py` - Signal messenger adapter using signal-cli HTTP daemon. Key: `SignalAdapter`, `_sse_listener`, `_handle_envelope`, `_fetch_attachment`, `_render_mentions` [SOURCE_CODE]
- `slack.py` - Async Slack platform adapter using slack-bolt Socket Mode. Key: `SlackAdapter`, `check_slack_requirements`, `SlackAdapter.format_message`, `SlackAdapter.send`, `SlackAdapter._upload_file` [SOURCE_CODE]
- `sms.py` - Twilio SMS adapter with webhook receiver and REST sender. Key: `SmsAdapter`, `_handle_webhook`, `format_message`, `check_sms_requirements` [SOURCE_CODE]
- `telegram.py` - Telegram platform adapter using python-telegram-bot. Key: `check_telegram_requirements`, `_escape_mdv2`, `TelegramAdapter` [SOURCE_CODE]
- `telegram_network.py` - Transport that retries Telegram API requests via fallback IPs preserving TLS/SNI. Key: `TelegramFallbackTransport`, `discover_fallback_ips`, `_rewrite_request_for_ip`, `_normalize_fallback_ips` [SOURCE_CODE]
- `webhook.py` - Generic webhook receiver that triggers agent runs. Key: `check_webhook_requirements`, `WebhookAdapter`, `_validate_signature` [SOURCE_CODE]
- `wecom.py` - WeCom AI Bot WebSocket adapter for inbound/outbound messaging. Key: `WeComAdapter`, `check_wecom_requirements`, `_coerce_list`, `_normalize_entry`, `_entry_matches` [SOURCE_CODE]
- `whatsapp.py` - WhatsApp platform adapter and Node.js bridge manager. Key: `_kill_port_process`, `check_whatsapp_requirements`, `WhatsAppAdapter` [SOURCE_CODE]

## hermes_cli/

- `__init__.py` - Hermes CLI package metadata [CLI]
- `auth.py` - Multi-provider auth subsystem: provider registry, API-key and OAuth handling, and persisted auth state.. Key: `ProviderConfig`, `PROVIDER_REGISTRY`, `_resolve_kimi_base_url`, `_gh_cli_candidates`, `_try_gh_cli_token` [SOURCE_CODE]
- `auth_commands.py` - CLI subcommands for managing the credential pool (add/list/remove/reset/interactive).. Key: `_get_custom_provider_names`, `_normalize_provider`, `_provider_base_url`, `_format_exhausted_status`, `auth_add_command` [CLI]
- `banner.py` - CLI welcome banner, ASCII art, tools/skills summary and update check [CLI]
- `callbacks.py` - Prompt toolkit callbacks bridging terminal_tool interactive prompts [CLI]
- `checklist.py` - Terminal multi-select checklist with curses and text fallback. Key: `curses_checklist` [SOURCE_CODE]
- `claw.py` - OpenClaw → Hermes migration and cleanup CLI commands [CLI]
- `clipboard.py` - Cross-platform clipboard image extraction and saving. Key: `save_clipboard_image`, `has_clipboard_image`, `_is_wsl` [SOURCE_CODE]
- `codex_models.py` - Discover Codex model IDs from API, cache, and config. Key: `get_codex_model_ids`, `_fetch_models_from_api`, `_add_forward_compat_models`, `DEFAULT_CODEX_MODELS` [SOURCE_CODE]
- `colors.py` - ANSI color utilities for CLI output [CLI]
- `commands.py` - Central registry of slash commands, gateway helpers and CLI autocomplete/suggestion logic. Key: `CommandDef`, `COMMAND_REGISTRY`, `_build_command_lookup`, `resolve_command`, `register_plugin_command` [SOURCE_CODE]
- `config.py` - Configuration management and defaults for Hermes Agent (HERMES_HOME config and .env handling). Key: `DEFAULT_CONFIG`, `ensure_hermes_home`, `get_config_path`, `get_env_path`, `get_managed_system` [SOURCE_CODE]
- `copilot_auth.py` - GitHub Copilot OAuth and token utilities. Key: `resolve_copilot_token`, `copilot_device_code_login`, `validate_copilot_token`, `copilot_request_headers` [SOURCE_CODE]
- `cron.py` - CLI subcommands for managing scheduled cron jobs [CLI]
- `curses_ui.py` - Reusable curses-based UI components with fallback. Key: `curses_checklist`, `_numbered_fallback` [SOURCE_CODE]
- `default_soul.py` - Default SOUL.md template seeded into HERMES_HOME. Key: `DEFAULT_SOUL_MD` [SOURCE_CODE]
- `doctor.py` - CLI diagnostic command that inspects Hermes installation, config, and runtime health. Key: `PROJECT_ROOT`, `HERMES_HOME`, `_DHH`, `_PROVIDER_ENV_HINTS`, `_has_provider_env_config` [CLI]
- `env_loader.py` - Helpers to consistently load Hermes .env files with precedence rules. Key: `_load_dotenv_with_fallback`, `load_hermes_dotenv` [SOURCE_CODE]
- `gateway.py` - CLI gateway subcommand: manage and install the messaging gateway [CLI]
- `logs.py` - View, tail and filter Hermes log files from CLI [CLI]
- `main.py` - Top-level CLI entrypoint and orchestration for the hermes command-line tool. Key: `_require_tty`, `_apply_profile_override`, `PROJECT_ROOT`, `_relative_time`, `_has_any_provider_configured` [CLI]
- `mcp_config.py` - Interactive CLI for managing MCP server entries and discovery. Key: `cmd_mcp_add`, `cmd_mcp_remove`, `cmd_mcp_list`, `cmd_mcp_test`, `_probe_single_server` [CLI]
- `memory_setup.py` - Interactive memory provider setup and status CLI [CLI]
- `model_normalize.py` - Normalize model identifiers per-provider expectations. Key: `normalize_model_for_provider`, `detect_vendor`, `_prepend_vendor`, `_normalize_for_deepseek`, `model_display_name` [SOURCE_CODE]
- `model_switch.py` - Shared CLI/gateway model selection and alias-resolution pipeline for provider/model switching. Key: `_HERMES_MODEL_WARNING`, `_check_hermes_model_warning`, `ModelIdentity`, `MODEL_ALIASES`, `DirectAlias` [SOURCE_CODE]
- `models.py` - Model/provider catalogs and helpers for Nous Portal free-tier gating and pricing. Key: `OPENROUTER_MODELS`, `_PROVIDER_MODELS`, `_NOUS_ALLOWED_FREE_MODELS`, `_is_model_free`, `filter_nous_free_models` [SOURCE_CODE]
- `nous_subscription.py` - Helpers to determine Nous subscription managed-tool availability [CLI]
- `pairing.py` - CLI commands for managing gateway DM pairing codes and approvals. Key: `pairing_command`, `_cmd_list`, `_cmd_approve`, `_cmd_revoke` [CLI]
- `plugins.py` - Plugin discovery, loading, and runtime management for Hermes plugins (directory + entry-point + project).. Key: `VALID_HOOKS`, `ENTRY_POINTS_GROUP`, `PluginManifest`, `LoadedPlugin`, `PluginContext` [SOURCE_CODE]
- `plugins_cmd.py` - CLI subcommand implementation for installing, updating, removing, enabling, disabling, and listing Hermes plugins.. Key: `_plugins_dir`, `_sanitize_plugin_name`, `_resolve_git_url`, `_repo_name_from_url`, `_read_manifest` [CLI]
- `profiles.py` - Manage named Hermes profiles (isolated HERMES_HOME directories), aliases, cloning, and exports. Key: `_PROFILE_ID_RE`, `_PROFILE_DIRS`, `_CLONE_CONFIG_FILES`, `_CLONE_SUBDIR_FILES`, `_CLONE_ALL_STRIP` [SOURCE_CODE]
- `providers.py` - Provider identity and resolution layer (models.dev + Hermes overlays). Key: `HermesOverlay`, `ProviderDef`, `get_provider`, `resolve_provider_full`, `determine_api_mode` [SOURCE_CODE]
- `runtime_provider.py` - Resolves the runtime inference provider, base URL, api_mode and credentials for CLI/gateway/cron runtimes.. Key: `_normalize_custom_provider_name`, `_detect_api_mode_for_url`, `_auto_detect_local_model`, `_get_model_config`, `_provider_supports_explicit_api_mode` [SOURCE_CODE]
- `setup.py` - Interactive setup wizard for Hermes Agent configuration [CLI]
- `skills_config.py` - Interactive skills enable/disable UI and persistence helpers [CLI]
- `skills_hub.py` - CLI and slash-command interface for searching, inspecting, and installing skills. Key: `_resolve_short_name`, `do_search`, `do_browse`, `do_install`, `do_inspect` [CLI]
- `skin_engine.py` - Data-driven CLI skin/theme engine and builtin skins [CLI]
- `status.py` - Show diagnostic status of Hermes components and keys [CLI]
- `tools_config.py` - Interactive toolset and provider configuration UI used by Hermes CLI [CLI]
- `uninstall.py` - Interactive uninstaller for Hermes Agent [CLI]
- `webhook.py` - CLI for managing dynamic webhook subscriptions [CLI]

## optional-skills/blockchain/base/scripts/

- `base_client.py` - CLI tool for Base L2 blockchain queries and token prices [CLI]

## optional-skills/blockchain/solana/scripts/

- `solana_client.py` - CLI tool for Solana RPC queries, tokens, NFTs, and prices [CLI]

## optional-skills/creative/meme-generation/scripts/

- `generate_meme.py` - Generate meme images by overlaying text on templates or images [CLI]

## optional-skills/mcp/fastmcp/scripts/

- `scaffold_fastmcp.py` - Scaffold a FastMCP starter template into a working file [CLI]

## optional-skills/mcp/fastmcp/templates/

- `api_wrapper.py` - FastMCP template: HTTP-backed API wrapper example. Key: `mcp`, `_request`, `health_check`, `get_resource`, `search_resources` [SOURCE_CODE]
- `database_server.py` - FastMCP template exposing read-only SQLite queries as tools. Key: `mcp`, `_connect`, `_reject_mutation`, `list_tables`, `query` [SOURCE_CODE]
- `file_processor.py` - FastMCP template for reading, summarizing and searching text files. Key: `mcp`, `_read_text`, `summarize_text_file`, `search_text_file`, `read_file_resource` [SOURCE_CODE]

## optional-skills/productivity/canvas/scripts/

- `canvas_api.py` - CLI wrapper for Canvas LMS API to list courses and assignments [CLI]

## optional-skills/productivity/memento-flashcards/scripts/

- `memento_cards.py` - STDlib flashcard manager with spaced-repetition and CSV I/O [CLI]
- `youtube_quiz.py` - Fetch YouTube transcripts for quiz generation [CLI]

## optional-skills/productivity/telephony/scripts/

- `telephony.py` - Minimal stdlib-based telephony CLI for Twilio, Vapi, Bland integrations [CLI]

## optional-skills/research/domain-intel/scripts/

- `domain_intel.py` - Passive domain intelligence CLI using Python stdlib [CLI]

## optional-skills/research/duckduckgo-search/scripts/

- `duckduckgo.sh` - Wrapper around ddgs CLI for DuckDuckGo searches [CLI]

## optional-skills/security/oss-forensics/scripts/

- `evidence-store.py` - JSON-based evidence registry manager for OSS forensics [CLI]

## packaging/homebrew/

- `hermes-agent.rb` - Homebrew formula to install Hermes Agent [BUILD]

## plugins/memory/

- `__init__.py` - Discovery and dynamic loading for built-in memory provider plugins. Key: `discover_memory_providers`, `load_memory_provider`, `_load_provider_from_dir`, `discover_plugin_cli_commands` [SOURCE_CODE]

## plugins/memory/byterover/

- `__init__.py` - ByteRover memory plugin that integrates brv CLI as a MemoryProvider. Key: `ByteRoverMemoryProvider`, `_run_brv`, `_resolve_brv_path`, `QUERY_SCHEMA` [SOURCE_CODE]

## plugins/memory/hindsight/

- `__init__.py` - Hindsight memory plugin providing cloud/local long-term memory. Key: `HindsightMemoryProvider`, `_get_loop`, `_run_sync`, `RETAIN_SCHEMA` [SOURCE_CODE]

## plugins/memory/holographic/

- `__init__.py` - Holographic structured memory plugin with fact store and retrieval. Key: `HolographicMemoryProvider`, `FACT_STORE_SCHEMA`, `register` [SOURCE_CODE]
- `holographic.py` - HRR phase-vector utilities for holographic memory. Key: `encode_atom`, `bind`, `unbind`, `bundle`, `encode_fact` [SOURCE_CODE]
- `retrieval.py` - Hybrid retrieval strategies combining FTS, Jaccard and HRR. Key: `FactRetriever`, `_fts_candidates`, `search`, `probe`, `contradict` [SOURCE_CODE]
- `store.py` - SQLite-backed memory/fact store with entity resolution and HRR vectors. Key: `MemoryStore`, `_SCHEMA`, `add_fact`, `search_facts`, `record_feedback` [SOURCE_CODE]

## plugins/memory/honcho/

- `__init__.py` - Honcho memory provider plugin integrating Honcho SDK. Key: `HonchoMemoryProvider`, `ALL_TOOL_SCHEMAS`, `PROFILE_SCHEMA` [SOURCE_CODE]
- `cli.py` - CLI management and setup helpers for Honcho memory integration. Key: `clone_honcho_for_profile`, `_ensure_peer_exists`, `cmd_enable`, `cmd_disable`, `cmd_setup` [SOURCE_CODE]
- `client.py` - Honcho client configuration and client singleton resolver. Key: `HonchoClientConfig`, `from_global_config`, `get_honcho_client` [SOURCE_CODE]
- `session.py` - Honcho-backed conversation session manager with local cache and async sync. Key: `HonchoSession`, `HonchoSessionManager`, `_ASYNC_SHUTDOWN`, `get_honcho_client`, `_flush_session` [SOURCE_CODE]

## plugins/memory/mem0/

- `__init__.py` - Mem0 memory provider plugin integrating with the Mem0 Platform API. Key: `Mem0MemoryProvider`, `_load_config`, `PROFILE_SCHEMA`, `SEARCH_SCHEMA` [SOURCE_CODE]

## plugins/memory/openviking/

- `__init__.py` - OpenViking memory plugin integrating with an OpenViking server. Key: `_VikingClient`, `OpenVikingMemoryProvider`, `SEARCH_SCHEMA` [SOURCE_CODE]

## plugins/memory/retaindb/

- `__init__.py` - RetainDB memory provider plugin with durable write-behind queue and file store. Key: `_Client`, `_WriteQueue`, `RetainDBMemoryProvider`, `_build_overlay` [SOURCE_CODE]

## plugins/memory/supermemory/

- `__init__.py` - Supermemory memory provider for semantic long-term memory and profile recall. Key: `_SupermemoryClient`, `SupermemoryMemoryProvider`, `_load_supermemory_config`, `_format_prefetch_context`, `STORE_SCHEMA` [SOURCE_CODE]

## scripts/

- `discord-voice-doctor.py` - Diagnostic CLI tool that validates Discord voice mode dependencies. Key: `check_packages`, `check_system_tools`, `check_env_vars`, `check_bot_permissions`, `main` [CLI]
- `install.sh` - Installer script to provision Python, Node, and Hermes runtime [BUILD]
- `release.py` - Release helper: changelog generation and GitHub release creation [BUILD]
- `sample_and_compress.py` - Script to sample HF datasets and run trajectory compression. Key: `main`, `sample_from_datasets`, `run_compression`, `load_dataset_from_hf` [SOURCE_CODE]

## scripts/whatsapp-bridge/

- `allowlist.js` - Utility helpers to normalize and expand WhatsApp identifiers. Key: `normalizeWhatsAppIdentifier`, `parseAllowedUsers`, `expandWhatsAppIdentifiers`, `matchesAllowedUser` [SOURCE_CODE]
- `bridge.js` - Node.js WhatsApp bridge exposing HTTP endpoints for the gateway. Key: `startSocket`, `formatOutgoingMessage`, `messageQueue`, `app (express)` [SOURCE_CODE]
- `package.json` - Node manifest for Hermes WhatsApp bridge using Baileys [CONFIG]

## skills/creative/excalidraw/scripts/

- `upload.py` - Encrypt and upload .excalidraw files and print share URL [CLI]

## skills/creative/manim-video/scripts/

- `setup.sh` - Prerequisite check for Manim Video skill [CLI]

## skills/creative/p5js/scripts/

- `export-frames.js` - Headless deterministic frame exporter for p5.js sketches [CLI]
- `render.sh` - Render p5.js sketch to MP4 via Puppeteer + ffmpeg [CLI]
- `serve.sh` - Lightweight local HTTP server for p5.js development [CLI]
- `setup.sh` - Dependency and environment checker for p5.js skill [CLI]

## skills/github/github-auth/scripts/

- `gh-env.sh` - Shell helper to detect GitHub auth and repo context [CLI]

## skills/leisure/find-nearby/scripts/

- `find_nearby.py` - Find nearby places using OpenStreetMap (Overpass + Nominatim) [CLI]

## skills/media/youtube-content/scripts/

- `fetch_transcript.py` - Fetch YouTube video transcript and output structured JSON [CLI]

## skills/mlops/training/grpo-rl-training/templates/

- `basic_grpo_training.py` - Minimal GRPO training template using TRL/PEFT for RL fine-tuning. Key: `get_dataset`, `correctness_reward_func`, `format_reward_func`, `setup_model_and_tokenizer`, `main` [SOURCE_CODE]

## skills/productivity/google-workspace/scripts/

- `google_api.py` - CLI wrapper for Google Workspace APIs used by the Google skill. Key: `get_credentials`, `build_service`, `gmail_search`, `calendar_list`, `main` [SOURCE_CODE]
- `setup.py` - Non-interactive Google Workspace OAuth2 setup helper [CLI]

## skills/productivity/ocr-and-documents/scripts/

- `extract_marker.py` - High-quality OCR and document extraction using marker-pdf [CLI]
- `extract_pymupdf.py` - Lightweight document text, images, and table extraction via pymupdf [CLI]

## skills/productivity/powerpoint/scripts/

- `add_slide.py` - CLI script to add or duplicate a slide in an unpacked PPTX folder [CLI]
- `clean.py` - CLI to remove unreferenced files in an unpacked PPTX directory [CLI]

## skills/productivity/powerpoint/scripts/office/

- `pack.py` - CLI to pack an unpacked Office directory into .docx/.pptx/.xlsx [CLI]

## skills/productivity/powerpoint/scripts/office/helpers/

- `merge_runs.py` - Helper to merge adjacent DOCX runs having identical formatting. Key: `merge_runs`, `_merge_runs_in`, `_can_merge`, `_consolidate_text` [SOURCE_CODE]
- `simplify_redlines.py` - Simplify tracked changes by merging adjacent w:ins/w:del with same author. Key: `simplify_redlines`, `_merge_tracked_changes_in`, `get_tracked_change_authors`, `infer_author` [SOURCE_CODE]

## skills/red-teaming/godmode/scripts/

- `auto_jailbreak.py` - Auto-jailbreak pipeline to test and lock working jailbreak prompts. Key: `auto_jailbreak`, `_detect_model_family`, `_get_current_model`, `_get_api_key`, `_write_config` [SOURCE_CODE]
- `godmode_race.py` - Multi-model racing engine to query many models and pick the best response. Key: `race_models`, `ULTRAPLINIAN_MODELS`, `score_response`, `is_refusal`, `race_godmode_classic` [SOURCE_CODE]
- `load_godmode.py` - Loader that imports and exposes godmode helper scripts into a single namespace. Key: `_gm_load` [SOURCE_CODE]
- `parseltongue.py` - Parseltongue input obfuscation engine with many text transforms. Key: `generate_variants`, `obfuscate_query`, `detect_triggers`, `TECHNIQUES`, `TRIGGER_WORDS` [SOURCE_CODE]

## skills/research/arxiv/scripts/

- `search_arxiv.py` - Simple arXiv search CLI printing formatted results [CLI]

## skills/research/polymarket/scripts/

- `polymarket.py` - CLI helper to query Polymarket prediction market APIs [CLI]

## tests/

- `conftest.py` - Pytest fixtures that isolate HERMES_HOME and enforce test timeouts. Key: `_isolate_hermes_home`, `tmp_dir`, `mock_config`, `_ensure_current_event_loop`, `_enforce_test_timeout` [TEST]
- `run_interrupt_test.py` - Standalone script to exercise agent interrupt propagation to child delegates. Key: `main`, `run_delegate` [TEST]
- `test_1630_context_overflow_loop.py` - Unit tests preventing gateway infinite 400 failure / persistence loops. Key: `TestGeneric400Heuristic`, `TestGatewaySkipsPersistenceOnFailure`, `TestContextOverflowErrorMessages`, `TestAgentSkipsPersistenceForLargeFailedSessions` [TEST]
- `test_413_compression.py` - Tests compression & retry behavior for HTTP 413/400 context errors. Key: `_make_tool_defs`, `_mock_response`, `_make_413_error`, `TestHTTP413Compression`, `TestPreflightCompression` [TEST]
- `test_860_dedup.py` - Tests ensuring session transcript deduplication and skip_db behavior. Key: `TestFlushDeduplication`, `TestAppendToTranscriptSkipDb`, `TestFlushIdxInit` [TEST]
- `test_agent_guardrails.py` - Unit tests for AIAgent guardrail utilities before/after LLM calls. Key: `make_tc`, `TestSanitizeApiMessages`, `TestCapDelegateTaskCalls`, `TestDeduplicateToolCalls`, `TestGetToolCallIdStatic` [TEST]
- `test_agent_loop.py` - Unit tests for HermesAgentLoop using mocked servers and tools. Key: `MockServer`, `MockMessage`, `TestAgentResult`, `TestExtractReasoning`, `TestHermesAgentLoop` [TEST]
- `test_agent_loop_tool_calling.py` - Integration tests for HermesAgentLoop tool-calling with real model servers. Key: `CALC_TOOL`, `WEATHER_TOOL`, `LOOKUP_TOOL`, `ERROR_TOOL`, `_fake_tool_handler` [TEST]
- `test_agent_loop_vllm.py` - Integration tests for HermesAgentLoop against a local vLLM server. Key: `_vllm_is_running`, `_make_server_manager`, `WEATHER_TOOL`, `_fake_tool_handler` [TEST]
- `test_anthropic_error_handling.py` - Tests Anthropic API error handling and retry/compression logic. Key: `_make_agent_cls`, `_run_with_agent`, `test_429_rate_limit_is_retried_and_recovers`, `test_prompt_too_long_triggers_compression` [TEST]
- `test_anthropic_oauth_flow.py` - Tests Anthropic OAuth setup and token selection logic. Key: `_run_anthropic_oauth_flow`, `test_run_anthropic_oauth_flow_prefers_claude_code_credentials`, `test_run_anthropic_oauth_flow_manual_token_still_persists` [TEST]
- `test_anthropic_provider_persistence.py` - Tests persistence helpers for Anthropic credential storage and slot semantics. Key: `test_save_anthropic_oauth_token_uses_token_slot_and_clears_api_key`, `test_use_anthropic_claude_code_credentials_clears_env_slots`, `test_save_anthropic_api_key_uses_api_key_slot_and_clears_token` [TEST]
- `test_api_key_providers.py` - Unit tests for provider registry and API-key credential resolution. Key: `TestProviderRegistry`, `TestResolveProvider`, `TestApiKeyProviderStatus`, `TestResolveApiKeyProviderCredentials` [TEST]
- `test_async_httpx_del_neuter.py` - Tests neuter fix and cleanup for AsyncHttpxClientWrapper.__del__ issues. Key: `TestNeuterAsyncHttpxDel`, `TestCleanupStaleAsyncClients` [TEST]
- `test_atomic_json_write.py` - Tests for atomic_json_write utility ensuring crash-safe JSON writes. Key: `TestAtomicJsonWrite` [TEST]
- `test_atomic_yaml_write.py` - Tests for atomic_yaml_write utility ensuring crash-safe YAML writes. Key: `TestAtomicYamlWrite` [TEST]
- `test_auth_codex_provider.py` - Tests Codex (openai-codex) auth helpers and Hermes auth store interactions. Key: `_setup_hermes_auth`, `_jwt_with_exp`, `test_read_codex_tokens_success`, `test_resolve_codex_runtime_credentials_refreshes_expiring_token` [TEST]
- `test_auth_commands.py` - Unit tests verifying CLI auth subcommands behavior backed by the credential pool and auth store.. Key: `_write_auth_store`, `_jwt_with_email`, `test_auth_add_api_key_persists_manual_entry`, `test_auth_add_anthropic_oauth_persists_pool_entry`, `test_auth_remove_reindexes_priorities` [TEST]
- `test_auth_nous_provider.py` - Regression tests for Nous OAuth refresh and agent-key mint interactions. Key: `_setup_nous_auth`, `_mint_payload`, `test_refresh_token_persisted_when_mint_returns_insufficient_credits` [TEST]
- `test_branch_command.py` - Tests for CLI /branch (/fork) session branching functionality. Key: `session_db (fixture)`, `cli_instance (fixture)`, `TestBranchCommandCLI`, `TestBranchCommandDef` [TEST]
- `test_cli_browser_connect.py` - Unit tests for CLI browser/CDP auto-launch discovery and Popen invocation. Key: `TestChromeDebugLaunch`, `test_windows_launch_uses_browser_found_on_path`, `test_windows_launch_falls_back_to_common_install_dirs` [TEST]
- `test_cli_context_warning.py` - Tests for CLI low-context-length warning banner. Key: `cli_obj`, `TestLowContextWarning`, `_isolate` [TEST]
- `test_cli_file_drop.py` - Tests detection of file-drop paths in CLI input. Key: `_detect_file_drop`, `tmp_image / tmp_text / tmp_image_with_spaces`, `TestImageFileDrop / TestNonFileInputs / TestEscapedSpaces / TestEdgeCases` [TEST]
- `test_cli_init.py` - Runtime tests ensuring HermesCLI initializes with sane defaults. Key: `_make_cli`, `TestMaxTurnsResolution`, `TestBusyInputMode`, `TestHistoryDisplay`, `TestRootLevelProviderOverride` [TEST]
- `test_cli_provider_resolution.py` - Unit tests for CLI provider resolution, model flow, and runtime credential interaction.. Key: `_reset_modules`, `_restore_cli_and_tool_modules`, `_install_prompt_toolkit_stubs`, `_import_cli`, `test_hermes_cli_init_does_not_eagerly_resolve_runtime_provider` [TEST]
- `test_cli_save_config_value.py` - Tests atomic save_config_value() behavior for CLI config writes. Key: `save_config_value`, `config_env (fixture)`, `TestSaveConfigValueAtomic` [TEST]
- `test_cli_status_bar.py` - Tests TUI status bar rendering and usage reporting. Key: `HermesCLI`, `_make_cli / _attach_agent`, `TestCLIStatusBar / TestCLIUsageReport / TestStatusBarWidthSource` [TEST]
- `test_codex_execution_paths.py` - Tests codex provider 401 refresh recovery in cron and gateway paths. Key: `_Codex401ThenSuccessAgent`, `_codex_message_response`, `test_cron_run_job_codex_path_handles_internal_401_refresh`, `test_gateway_run_agent_codex_path_handles_internal_401_refresh` [TEST]
- `test_codex_models.py` - Tests for codex model discovery, caching, and defaults. Key: `get_codex_model_ids`, `DEFAULT_CODEX_MODELS`, `test_get_codex_model_ids_prioritizes_default_and_cache` [TEST]
- `test_compression_persistence.py` - Tests persistence of compressed context in DB and gateway. Key: `TestFlushAfterCompression`, `TestGatewayHistoryOffsetAfterSplit`, `_make_agent` [TEST]
- `test_credential_pool.py` - Unit tests for credential pool selection, exhaustion cooldowns, seeding, migration and refresh behavior.. Key: `_write_auth_store`, `test_fill_first_selection_skips_recently_exhausted_entry`, `test_select_clears_expired_exhaustion`, `test_round_robin_strategy_rotates_priorities`, `test_random_strategy_uses_random_choice` [TEST]
- `test_credential_pool_routing.py` - Tests credential pool preservation and rotation on 429/402 errors. Key: `resolve_turn_route`, `TestSmartRoutingPoolPreservation`, `TestEagerFallbackWithPool`, `TestPoolRotationCycle` [TEST]
- `test_display.py` - Tests tool preview and inline diff rendering utilities. Key: `build_tool_preview`, `capture_local_edit_snapshot`, `extract_edit_diff`, `_render_inline_unified_diff`, `_summarize_rendered_diff_sections` [TEST]
- `test_exit_cleanup_interrupt.py` - Tests KeyboardInterrupt-safe cleanup in exit paths. Key: `TestCronJobCleanup`, `scheduler.run_job` [TEST]
- `test_gemini_provider.py` - Tests for Gemini (Google AI Studio) provider integration. Key: `TestGeminiProviderRegistry`, `TestGeminiAliases`, `TestGeminiModelNormalization`, `TestGeminiContextLength`, `TestGeminiModelsDev` [TEST]
- `test_hermes_logging.py` - Unit tests validating hermes_logging setup, idempotency, config reading, and handler behavior.. Key: `_reset_logging_state`, `hermes_home`, `TestSetupLogging`, `TestSetupVerboseLogging`, `TestAddRotatingHandler` [TEST]
- `test_honcho_client_config.py` - Tests Honcho memory plugin client configuration auto-enable rules. Key: `HonchoClientConfig.from_global_config`, `HonchoClientConfig.from_env`, `TestHonchoClientConfigAutoEnable` [TEST]
- `test_large_tool_result.py` - Tests handling and storage of oversized tool responses. Key: `_save_oversized_tool_result`, `_LARGE_RESULT_CHARS`, `_LARGE_RESULT_PREVIEW_CHARS`, `TestSaveOversizedToolResult` [TEST]
- `test_long_context_tier_429.py` - Tests handling of Anthropic Sonnet long-context tier 429 errors. Key: `TestLongContextTierDetection`, `TestContextReduction`, `TestAgentErrorPath` [TEST]
- `test_mcp_serve.py` - Unit, EventBridge, and end-to-end tests for the Hermes MCP server and EventBridge.. Key: `_isolate_hermes_home`, `sessions_dir`, `sample_sessions`, `_create_test_db`, `mock_session_db` [TEST]
- `test_model_normalize.py` - Tests provider-aware model name normalization and vendor detection. Key: `normalize_model_for_provider`, `detect_vendor`, `_DOT_TO_HYPHEN_PROVIDERS`, `_AGGREGATOR_PROVIDERS` [TEST]
- `test_model_provider_persistence.py` - Tests persistence of selected model/provider in config.yaml. Key: `_save_model_choice`, `_model_flow_api_key_provider`, `_model_flow_copilot`, `TestSaveModelChoiceAlwaysDict / TestProviderPersistsAfterModelSave` [TEST]
- `test_model_tools.py` - Unit tests for model_tools: dispatch, coercion/edge error handling, legacy toolsets and backward-compat wrappers.. Key: `TestHandleFunctionCall`, `TestAgentLoopTools`, `TestLegacyToolsetMap`, `TestBackwardCompat` [TEST]
- `test_ollama_cloud_auth.py` - Unit tests for Ollama Cloud auth, model aliases, /model persistence and fallback passthrough. Key: `TestOllamaCloudCredentials`, `TestDirectAliases`, `TestModelSwitchPersistence`, `TestModelTabCompletion`, `TestFallbackBaseUrlPassthrough` [TEST]
- `test_packaging_metadata.py` - Packaging metadata tests for pyproject.toml and MANIFEST.in. Key: `test_faster_whisper_is_not_a_base_dependency`, `test_manifest_includes_bundled_skills` [TEST]
- `test_plugin_cli_registration.py` - Tests for plugin CLI registration and discovery system. Key: `PluginContext.register_cli_command`, `PluginManager`, `discover_plugin_cli_commands`, `TestHonchoRegisterCli` [TEST]
- `test_plugins.py` - Unit tests exercising plugin discovery, loading, hook semantics, and tool visibility.. Key: `_make_plugin_dir`, `TestPluginDiscovery`, `TestPluginLoading`, `TestPluginHooks`, `TestPluginContext` [TEST]
- `test_plugins_cmd.py` - Unit tests for the hermes_cli.plugins_cmd plugin management CLI behaviors.. Key: `TestSanitizePluginName.test_valid_simple_name`, `TestResolveGitUrl.test_owner_repo_shorthand`, `TestRepoNameFromUrl.test_https_with_dot_git`, `TestCmdInstall.test_install_rejects_manifest_name_pointing_at_plugins_root`, `TestPromptPluginEnvVars.test_prompts_for_missing_var_simple_format` [TEST]
- `test_primary_runtime_restore.py` - Tests for primary runtime snapshot/restore, fallback activation, and transport recovery. Key: `AIAgent`, `_make_agent`, `TestPrimaryRuntimeSnapshot`, `TestRestorePrimaryRuntime`, `TestTryRecoverPrimaryTransport` [TEST]
- `test_project_metadata.py` - Regression tests for optional dependency groupings in pyproject.toml. Key: `test_matrix_extra_exists_but_excluded_from_all` [TEST]
- `test_provider_parity.py` - Provider parity tests ensuring AIAgent builds and normalizes API payloads. Key: `TestBuildApiKwargsOpenRouter`, `TestDeveloperRoleSwap`, `TestBuildApiKwargsCodex`, `TestChatMessagesToResponsesInput` [TEST]
- `test_run_agent.py` - Comprehensive unit tests for AIAgent and run_agent behaviours. Key: `_make_tool_defs`, `agent`, `_mock_assistant_msg`, `_mock_response`, `TestExtractReasoning` [TEST]
- `test_runtime_provider_resolution.py` - Unit tests verifying provider resolution precedence, credential pools, explicit overrides, and env/config interactions.. Key: `test_resolve_runtime_provider_uses_credential_pool`, `test_resolve_runtime_provider_anthropic_pool_respects_config_base_url`, `test_resolve_runtime_provider_anthropic_explicit_override_skips_pool`, `test_resolve_runtime_provider_openrouter_explicit`, `test_openrouter_key_takes_priority_over_openai_key` [TEST]
- `test_session_meta_filtering.py` - Tests ensuring session_meta messages are filtered before API calls and CLI restores. Key: `AIAgent._sanitize_api_messages`, `TestSanitizeApiMessagesRoleFilter`, `TestCLISessionRestoreFiltering` [TEST]
- `test_setup_model_selection.py` - Tests for provider model selection logic during setup. Key: `mock_provider_registry`, `_setup_provider_model_selection`, `TestSetupProviderModelSelection` [TEST]
- `test_streaming.py` - Extensive tests for streaming API accumulation, callbacks, fallback and CLI streaming behavior. Key: `_make_stream_chunk`, `_make_tool_call_delta`, `TestStreamingAccumulator`, `TestStreamingCallbacks`, `TestStreamingFallback` [TEST]
- `test_strict_api_validation.py` - Tests sanitization to prevent strict API validation errors (Fireworks/Codex). Key: `_make_agent`, `TestStrictApiValidation` [TEST]
- `test_timezone.py` - Timezone tests for hermes_time, cron scheduling, and code execution env propagation. Key: `hermes_time.now`, `TestHermesTimeNow`, `TestCronTimezone`, `TestCodeExecutionTZ` [TEST]
- `test_token_persistence_non_cli.py` - Tests token usage persistence for non-CLI sessions (telegram/cron). Key: `_make_agent`, `test_run_conversation_persists_tokens_for_telegram_sessions`, `test_run_conversation_persists_tokens_for_cron_sessions` [TEST]
- `test_tool_arg_coercion.py` - Unit and integration tests for coercing tool-call arg types against JSON Schema. Key: `_coerce_number`, `_coerce_boolean`, `_coerce_value`, `coerce_tool_args`, `TestCoerceToolArgs` [TEST]
- `test_toolset_distributions.py` - Unit tests validating distribution definitions and sampling behavior.. Key: `TestGetDistribution`, `TestListDistributions`, `TestValidateDistribution`, `TestSampleToolsetsFromDistribution`, `TestDistributionStructure` [TEST]
- `test_toolsets.py` - Unit tests for toolsets module: resolution, validation, creation, and integrity checks.. Key: `TestGetToolset.test_known_toolset`, `TestResolveToolset.test_leaf_toolset`, `TestResolveToolset.test_composite_toolset`, `TestResolveToolset.test_cycle_detection`, `TestResolveToolset.test_all_alias` [TEST]
- `test_trajectory_compressor.py` - Tests for trajectory compression config, metrics, token counting, and summarization logic. Key: `CompressionConfig`, `TrajectoryMetrics`, `AggregateMetrics`, `TrajectoryCompressor`, `TestFindProtectedIndices` [TEST]
- `test_trajectory_compressor_async.py` - Async client lazy-creation tests ensuring AsyncOpenAI is created per event loop. Key: `TrajectoryCompressor`, `TestAsyncClientLazyCreation`, `TestSourceLineVerification` [TEST]

## tests/agent/

- `test_prompt_builder.py` - Pytest unit tests for prompt_builder: context scanning, truncation, skill parsing, skills prompt, and Nous subscription prompts.. Key: `TestGuidanceConstants`, `TestScanContextContent`, `TestTruncateContent`, `TestParseSkillFile`, `TestPromptBuilderImports` [TEST]

## tests/cron/

- `test_scheduler.py` - Unit tests for cron scheduler: origin/delivery resolution, delivery wrapping, media extraction, and run_job lifecycle.. Key: `TestResolveOrigin`, `TestResolveDeliveryTarget`, `TestDeliverResultWrapping`, `TestRunJobSessionPersistence`, `TestRunJobConfigLogging` [TEST]

## tests/e2e/

- `conftest.py` - E2E test fixtures and helpers for Telegram gateway integration tests. Key: `_ensure_telegram_mock`, `make_runner`, `make_adapter`, `send_and_capture` [TEST]
- `test_telegram_commands.py` - E2E tests for Telegram gateway slash commands and session lifecycle. Key: `make_adapter`, `TestTelegramSlashCommands`, `TestAuthorization`, `TestSendFailureResilience` [TEST]

## tests/gateway/

- `test_approve_deny_commands.py` - Tests for gateway /approve and /deny blocking approval mechanism. Key: `TestBlockingGatewayApproval`, `TestApproveCommand`, `TestDenyCommand`, `TestBlockingApprovalE2E`, `_make_runner` [TEST]
- `test_config.py` - Unit tests for gateway config serialization, YAML bridging, and env overrides.. Key: `TestHomeChannelRoundtrip`, `TestPlatformConfigRoundtrip`, `TestGetConnectedPlatforms`, `TestSessionResetPolicy`, `TestGatewayConfigRoundtrip` [TEST]
- `test_matrix.py` - Unit tests for Matrix adapter behavior and Matrix-related gateway config env handling.. Key: `TestMatrixPlatformEnum`, `TestMatrixConfigLoading`, `TestMatrixMxcToHttp`, `TestMatrixDmDetection`, `TestMatrixReplyFallbackStripping` [TEST]
- `test_runner_fatal_adapter.py` - Unit tests for GatewayRunner fatal-adapter behavior and exit/reconnect semantics.. Key: `_FatalAdapter`, `_RuntimeRetryableAdapter`, `test_runner_requests_clean_exit_for_nonretryable_startup_conflict`, `test_runner_queues_retryable_runtime_fatal_for_reconnection` [TEST]
- `test_session.py` - Unit tests for gateway session behavior: session keying, prompt generation, transcript persistence and recovery.. Key: `TestSessionSourceRoundtrip`, `TestSessionSourceDescription`, `TestBuildSessionContextPrompt`, `TestSessionStoreRewriteTranscript`, `TestLoadTranscriptCorruptLines` [TEST]

## tests/hermes_cli/

- `test_commands.py` - Unit tests for the central command registry, gateway helpers, and CLI autocomplete. Key: `TestCommandRegistry`, `TestResolveCommand`, `TestGatewayConfigGate`, `TestSlashCommandCompleter`, `TestTelegramBotCommands` [TEST]
- `test_gateway_service.py` - Unit tests for gateway service installation and management helpers. Key: `TestSystemdServiceRefresh`, `TestGeneratedSystemdUnits`, `TestLaunchdServiceRecovery`, `TestDetectVenvDir`, `TestSystemUnitHermesHome` [TEST]
- `test_tools_config.py` - Unit tests for hermes_cli.tools_config platform tool persistence and platform/toolset consistency.. Key: `test_get_platform_tools_uses_default_when_platform_not_configured`, `test_get_platform_tools_preserves_explicit_empty_selection`, `test_platform_toolset_summary_uses_explicit_platform_list`, `test_toolset_has_keys_for_vision_accepts_codex_auth`, `test_save_platform_tools_preserves_mcp_server_names` [TEST]
- `test_update_gateway_restart.py` - Tests for gateway auto-restart logic used by hermes update. Key: `_make_run_side_effect`, `TestLaunchdPlistReplace`, `TestCmdUpdateLaunchdRestart`, `TestCmdUpdateSystemService` [TEST]
- `test_webhook_cli.py` - Unit tests for the webhook CLI (subscribe/list/remove) and webhook gating. Key: `_isolate`, `_make_args`, `TestSubscribe`, `TestList`, `TestRemove` [TEST]

## tests/tools/

- `test_approval.py` - Unit tests that exercise dangerous command detection and the approval/session flow.. Key: `TestApprovalModeParsing`, `TestDetectDangerousRm`, `TestSessionKeyContext`, `TestPatternKeyUniqueness` [TEST]
- `test_credential_files.py` - Tests for credential file registration, mount generation, symlink sanitization and cache/skills mounts. Key: `register_credential_file`, `register_credential_files`, `get_credential_file_mounts`, `get_skills_directory_mount`, `iter_cache_files` [TEST]
- `test_delegate.py` - Unit tests validating the delegation/subagent tool behavior and its interactions with subagent creation, tooling, observability, and credential sharing.. Key: `_make_mock_parent`, `TestDelegateRequirements`, `TestChildSystemPrompt`, `TestStripBlockedTools`, `TestDelegateTask` [TEST]

## tools/

- `__init__.py` - Lightweight tools package init with minimal side effects. Key: `check_file_requirements` [SOURCE_CODE]
- `ansi_strip.py` - Remove ANSI/ECMA-48 escape sequences from text. Key: `strip_ansi`, `_ANSI_ESCAPE_RE`, `_HAS_ESCAPE` [SOURCE_CODE]
- `approval.py` - Central dangerous-command detection, per-session approval state, prompting and persistent allowlist.. Key: `DANGEROUS_PATTERNS`, `_normalize_command_for_detection`, `detect_dangerous_command`, `_legacy_pattern_key`, `_approval_key_aliases` [SOURCE_CODE]
- `browser_camofox.py` - HTTP client backend for a self‑hosted Camofox browser exposing browser tool primitives.. Key: `_DEFAULT_TIMEOUT`, `_SNAPSHOT_MAX_CHARS`, `_sessions`, `_sessions_lock`, `get_camofox_url` [SOURCE_CODE]
- `browser_camofox_state.py` - Profile-scoped Camofox browser identity and state paths. Key: `get_camofox_state_dir`, `get_camofox_identity`, `CAMOFOX_STATE_DIR_NAME` [SOURCE_CODE]
- `browser_tool.py` - Browser automation abstraction supporting local and cloud backends. Key: `_get_cloud_provider`, `_is_local_mode`, `_resolve_cdp_override`, `_start_browser_cleanup_thread`, `Cloud provider registry (_PROVIDER_REGISTRY)` [SOURCE_CODE]
- `checkpoint_manager.py` - Filesystem checkpointing via shadow git repositories. Key: `CheckpointManager`, `_run_git`, `_init_shadow_repo`, `_shadow_repo_path` [SOURCE_CODE]
- `clarify_tool.py` - Tool to present clarifying questions and collect user responses. Key: `clarify_tool`, `CLARIFY_SCHEMA`, `check_clarify_requirements` [SOURCE_CODE]
- `code_execution_tool.py` - Sandboxed code execution helper exposing Hermes tools to user scripts. Key: `generate_hermes_tools_module`, `_rpc_server_loop`, `SANDBOX_ALLOWED_TOOLS`, `check_sandbox_requirements`, `_get_or_create_env` [SOURCE_CODE]
- `credential_files.py` - Registry and helpers to expose selected host files (credentials, skills, caches) into remote sandboxes safely.. Key: `_registered_files_var`, `_get_registered`, `_resolve_hermes_home`, `register_credential_file`, `register_credential_files` [SOURCE_CODE]
- `cronjob_tools.py` - Unified cron job management tool with prompt-scanning and API boundary validation. Key: `_scan_cron_prompt`, `_validate_cron_script_path`, `_canonical_skills`, `_resolve_model_override`, `_format_job` [SOURCE_CODE]
- `debug_helpers.py` - Per-tool debug session logger and JSON log exporter. Key: `DebugSession`, `get_hermes_home` [SOURCE_CODE]
- `delegate_tool.py` - Tool for spawning focused subagents (child AIAgent instances) with isolated context, restricted tools, and credential leasing.. Key: `DELEGATE_BLOCKED_TOOLS`, `MAX_CONCURRENT_CHILDREN`, `MAX_DEPTH`, `DEFAULT_MAX_ITERATIONS`, `DEFAULT_TOOLSETS` [SOURCE_CODE]
- `env_passthrough.py` - Session-scoped allowlist for environment variables to passthrough to sandboxes. Key: `register_env_passthrough`, `is_env_passthrough`, `get_all_passthrough`, `clear_env_passthrough`, `_allowed_env_vars_var` [SOURCE_CODE]
- `file_operations.py` - Shell-backed file read/write/patch/search operations for terminal backends. Key: `FileOperations`, `ShellFileOperations`, `ReadResult`, `WRITE_DENIED_PATHS`, `MAX_FILE_SIZE` [SOURCE_CODE]
- `file_tools.py` - File manipulation tools used by the agent (read/write/patch with safety, dedup, and sandboxing).. Key: `_EXPECTED_WRITE_ERRNOS`, `_DEFAULT_MAX_READ_CHARS`, `_get_max_read_chars`, `_BLOCKED_DEVICE_PATHS`, `_is_blocked_device` [SOURCE_CODE]
- `fuzzy_match.py` - Fuzzy matching and replace strategies to robustly edit file content. Key: `fuzzy_find_and_replace`, `_strategy_block_anchor`, `_strategy_context_aware`, `_apply_replacements` [SOURCE_CODE]
- `homeassistant_tool.py` - Home Assistant REST API tools: list entities, get state, list services, call services. Key: `_async_list_entities`, `_async_call_service`, `_handle_call_service`, `_BLOCKED_DOMAINS` [SOURCE_CODE]
- `image_generation_tool.py` - Image generation using FAL.ai FLUX 2 Pro with automatic upscaling. Key: `image_generate_tool`, `_submit_fal_request`, `_ManagedFalSyncClient`, `_upscale_image` [SOURCE_CODE]
- `interrupt.py` - Global interrupt event to signal tool cancellation across threads. Key: `set_interrupt`, `is_interrupted`, `_interrupt_event` [SOURCE_CODE]
- `managed_tool_gateway.py` - Helpers to resolve Nous-managed tool gateway and tokens. Key: `ManagedToolGatewayConfig`, `read_nous_access_token`, `build_vendor_gateway_url`, `resolve_managed_tool_gateway` [SOURCE_CODE]
- `mcp_oauth.py` - OAuth2.1 PKCE browser-based flow glue for MCP servers. Key: `HermesTokenStorage`, `build_oauth_auth`, `_make_callback_handler`, `_redirect_handler`, `_wait_for_callback` [SOURCE_CODE]
- `mcp_tool.py` - MCP client integration for importing external tools into Hermes. Key: `SamplingHandler`, `_build_safe_env`, `_format_connect_error`, `_check_message_handler_support`, `_sanitize_error` [SOURCE_CODE]
- `memory_tool.py` - Durable curated memory store and tool interface. Key: `MemoryStore`, `memory_tool`, `_scan_memory_content`, `get_memory_dir`, `ENTRY_DELIMITER` [SOURCE_CODE]
- `mixture_of_agents_tool.py` - Mixture-of-Agents orchestration: run multiple models and aggregate results. Key: `mixture_of_agents_tool`, `_run_reference_model_safe`, `_run_aggregator_model`, `_construct_aggregator_prompt` [SOURCE_CODE]
- `neutts_synth.py` - Standalone subprocess helper to synthesize speech with NeuTTS and write WAV. Key: `_write_wav`, `main` [SOURCE_CODE]
- `openrouter_client.py` - Lazy shared OpenRouter async client accessor. Key: `_client`, `get_async_client`, `check_api_key` [SOURCE_CODE]
- `osv_check.py` - Check packages against OSV API for malware advisories before MCP launches. Key: `check_package_for_malware`, `_infer_ecosystem`, `_parse_npm_package`, `_query_osv` [SOURCE_CODE]
- `patch_parser.py` - Parser and applier for V4A patch format used by coding agents. Key: `OperationType`, `HunkLine`, `PatchOperation`, `parse_v4a_patch`, `apply_v4a_operations` [SOURCE_CODE]
- `process_registry.py` - Registry for managed background processes with buffering and recovery. Key: `ProcessSession`, `ProcessRegistry`, `spawn_local`, `spawn_via_env`, `CHECKPOINT_PATH` [SOURCE_CODE]
- `registry.py` - Central singleton registry for tool schemas and handlers. Key: `ToolEntry`, `ToolRegistry`, `registry` [SOURCE_CODE]
- `rl_training_tool.py` - Tooling module to discover environments and orchestrate RL training runs. Key: `EnvironmentInfo`, `RunState`, `_scan_environments`, `_get_env_config_fields`, `_spawn_training_run` [SOURCE_CODE]
- `send_message_tool.py` - Cross-platform send_message tool for gateway and CLI. Key: `SEND_MESSAGE_SCHEMA`, `send_message_tool`, `_send_to_platform`, `_send_telegram`, `_parse_target_ref` [SOURCE_CODE]
- `session_search_tool.py` - Search and focused summarization of past sessions using FTS5 and an auxiliary LLM. Key: `session_search`, `_summarize_session`, `_format_conversation`, `SESSION_SEARCH_SCHEMA` [SOURCE_CODE]
- `skill_manager_tool.py` - Agent-managed skill creation, editing and file management. Key: `_create_skill`, `_edit_skill`, `_patch_skill`, `_write_file`, `_validate_frontmatter` [SOURCE_CODE]
- `skills_guard.py` - Regex-based security scanner and install policy for externally sourced skills. Key: `Finding`, `ScanResult`, `THREAT_PATTERNS`, `INSTALL_POLICY` [SOURCE_CODE]
- `skills_hub.py` - Skills Hub adapters, GitHub auth, and hub state management. Key: `GitHubAuth`, `SkillSource`, `GitHubSource`, `SkillMeta`, `SkillBundle` [SOURCE_CODE]
- `skills_sync.py` - Synchronize bundled skills into the user's ~/.hermes/skills with manifest tracking. Key: `sync_skills`, `_dir_hash`, `_read_manifest`, `_write_manifest` [SOURCE_CODE]
- `skills_tool.py` - Skill discovery, metadata parsing, and progressive-disclosure loaders. Key: `SKILLS_DIR`, `SkillReadinessStatus`, `load_env`, `set_secret_capture_callback`, `_get_required_environment_variables` [SOURCE_CODE]
- `terminal_tool.py` - Terminal tool that runs commands across multiple execution backends. Key: `_transform_sudo_command`, `set_sudo_password_callback`, `register_task_env_overrides` [SOURCE_CODE]
- `tirith_security.py` - Wrapper that runs Tirith binary to pre-scan shell commands and auto-installs it if missing. Key: `_load_security_config`, `_install_tirith`, `_resolve_tirith_path`, `_verify_cosign` [SOURCE_CODE]
- `todo_tool.py` - In-session TODO list tool with read/write schema and registry registration. Key: `TodoStore`, `todo_tool`, `TODO_SCHEMA` [SOURCE_CODE]
- `tool_backend_helpers.py` - Helpers to choose and normalize tool backend/provider configuration. Key: `managed_nous_tools_enabled`, `resolve_modal_backend_state`, `normalize_browser_cloud_provider`, `resolve_openai_audio_api_key` [SOURCE_CODE]
- `transcription_tools.py` - Multi-provider speech-to-text utilities (local/Groq/OpenAI). Key: `_transcribe_local`, `_transcribe_groq`, `_transcribe_openai`, `_get_provider`, `_validate_audio_file` [SOURCE_CODE]
- `tts_tool.py` - Text-to-speech orchestration across multiple providers. Key: `text_to_speech_tool`, `_generate_edge_tts`, `_generate_elevenlabs`, `_generate_openai_tts`, `_generate_neutts` [SOURCE_CODE]
- `url_safety.py` - URL safety checks to block private/internal network requests (SSRF protection). Key: `_is_blocked_ip`, `is_safe_url`, `_CGNAT_NETWORK` [SOURCE_CODE]
- `vision_tools.py` - Vision analysis tool: downloads images, encodes, and calls vision LLMs. Key: `vision_analyze_tool`, `_download_image`, `_image_to_base64_data_url`, `_validate_image_url` [SOURCE_CODE]
- `voice_mode.py` - CLI push-to-talk recorder and playback utilities. Key: `AudioRecorder`, `detect_audio_environment`, `play_beep`, `SAMPLE_RATE` [SOURCE_CODE]
- `web_tools.py` - Generic web search/extract/crawl tools with multi-backend support. Key: `process_content_with_llm`, `_get_firecrawl_client`, `_get_backend`, `_extract_web_search_results`, `_is_nous_auxiliary_client` [SOURCE_CODE]
- `website_policy.py` - Load, cache and enforce website blocklist policy for URL tools. Key: `load_website_blocklist`, `check_website_access`, `invalidate_cache`, `_normalize_rule`, `_iter_blocklist_file_rules` [SOURCE_CODE]

## tools/browser_providers/

- `__init__.py` - Re-exports cloud browser provider ABC. Key: `CloudBrowserProvider` [SOURCE_CODE]
- `base.py` - Abstract base class for cloud browser providers. Key: `CloudBrowserProvider` [SOURCE_CODE]
- `browser_use.py` - Provider for Browser Use cloud browser sessions. Key: `BrowserUseProvider`, `_get_or_create_pending_create_key`, `_should_preserve_pending_create_key` [SOURCE_CODE]
- `browserbase.py` - Provider for Browserbase cloud browser sessions. Key: `BrowserbaseProvider`, `_get_config_or_none`, `create_session` [SOURCE_CODE]
- `firecrawl.py` - Provider for Firecrawl cloud browser sessions. Key: `FirecrawlProvider`, `_api_url`, `create_session` [SOURCE_CODE]

## tools/environments/

- `__init__.py` - Re-exports BaseEnvironment for execution backends. Key: `BaseEnvironment` [SOURCE_CODE]
- `base.py` - Abstract base class and helpers for execution environment backends. Key: `BaseEnvironment`, `get_sandbox_dir`, `_build_run_kwargs`, `execute_oneshot` [SOURCE_CODE]
- `daytona.py` - Daytona cloud sandbox execution environment integration. Key: `DaytonaEnvironment`, `_exec_in_thread`, `_sync_skills_and_credentials`, `execute` [SOURCE_CODE]
- `docker.py` - Hardened Docker-based execution environment for sandboxed tasks. Key: `DockerEnvironment`, `find_docker`, `_ensure_docker_available`, `_SECURITY_ARGS`, `_storage_opt_supported` [SOURCE_CODE]
- `local.py` - Local shell execution environment with robust I/O and interrupts. Key: `LocalEnvironment`, `_sanitize_subprocess_env`, `_find_bash`, `_extract_fenced_output`, `_HERMES_PROVIDER_ENV_BLOCKLIST` [SOURCE_CODE]
- `managed_modal.py` - Managed Modal execution environment via a tool gateway. Key: `ManagedModalEnvironment`, `_create_sandbox`, `_start_modal_exec`, `_request` [SOURCE_CODE]
- `modal.py` - Modal SDK execution environment with snapshot persistence. Key: `ModalEnvironment`, `_AsyncWorker`, `_get_snapshot_restore_candidate` [SOURCE_CODE]
- `modal_common.py` - Shared Modal execution flow and helpers for Modal transports. Key: `BaseModalExecutionEnvironment`, `PreparedModalExec`, `ModalExecStart`, `wrap_modal_stdin_heredoc` [SOURCE_CODE]
- `persistent_shell.py` - Persistent shell mixin that manages long-lived bash shells via file IPC. Key: `PersistentShellMixin`, `_init_persistent_shell`, `_execute_persistent_locked`, `_read_persistent_output` [SOURCE_CODE]
- `singularity.py` - Singularity/Apptainer execution environment with persistence. Key: `_ensure_singularity_available`, `_get_or_build_sif`, `SingularityEnvironment` [SOURCE_CODE]
- `ssh.py` - SSH remote execution environment with ControlMaster persistence. Key: `_ensure_ssh_available`, `SSHEnvironment` [SOURCE_CODE]

## website/

- `docusaurus.config.ts` - Docusaurus site configuration for Hermes Agent documentation [CONFIG]
- `package.json` - Docusaurus website package configuration [CONFIG]
- `sidebars.ts` - Docusaurus sidebar structure for documentation navigation [CONFIG]

## website/scripts/

- `extract-skills.py` - Script to extract SKILL.md metadata and produce skills.json for website [BUILD]

## website/src/pages/skills/

- `index.tsx` - React Skills Hub page to browse, search, and filter skills. Key: `SkillsDashboard`, `SkillCard`, `highlightMatch`, `StatCard` [SOURCE_CODE]


---
*This knowledge base was extracted by [Codeset](https://codeset.ai) and is available via `python .claude/docs/get_context.py <file_or_folder>`*
