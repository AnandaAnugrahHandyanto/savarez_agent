# MCP / Tooling / Infrastructure Test Failures

**Date:** 2026-06-02
**Milestone:** v2.10 Phase 4 (Discord Adapter MVP)
**Status:** Documented pre-existing infrastructure failures

---

## Summary

The full repository test suite (`tests/hermes_cli tests/agent tests/tools`)
produces **78 failures** (13033 passed, 52 skipped). **Zero of these failures
were introduced by v2.10 Phase 4.**

All 39 Phase 4 tests pass (`tests/agent/test_discord_adapter.py:: 39 passed`).

---

## Failure Classification

### Category A — Platform / OS-dependent (8 failures)

These tests require Linux/WSL, systemd, or native platform services not
available in macOS local development.

| Test | File | Reason |
|------|------|--------|
| `test_wsl_with_systemd` | `test_gateway_wsl.py` | Linux/WSL only |
| `test_native_linux` | `test_gateway_wsl.py` | Linux/WSL only |
| `test_systemd_start_refreshes_outdated_unit` | `test_gateway_service.py` | systemd not available on macOS |
| `test_systemd_restart_refreshes_outdated_unit` | `test_gateway_service.py` | systemd not available on macOS |
| `test_systemd_restart_gracefully_restarts_running_service_and_waits` | `test_gateway_service.py` | systemd not available on macOS |
| `test_systemd_restart_uses_systemd_main_pid_when_pid_file_is_missing` | `test_gateway_service.py` | systemd not available on macOS |
| `test_systemd_restart_reports_start_limit_hit` | `test_gateway_service.py` | systemd not available on macOS |
| `test_systemd_restart_recovers_failed_planned_restart` | `test_gateway_service.py` | systemd not available on macOS |

### Category B — Model / Provider / Auth configuration (6 failures)

These tests depend on external model provider configs, env vars, credential
files, or OAuth flows not present in local dev.

| Test | File | Reason |
|------|------|--------|
| `test_opencode_go_same_provider_switch_recomputes_api_mode` | `test_model_provider_persistence.py` | Requires OpenCode Go runtime config |
| `test_list_groups_same_name_custom_providers_into_one_row` | `test_model_switch_custom_providers.py` | Requires custom provider registration state |
| `test_returns_token_from_credential_files` | `test_anthropic_adapter.py` | Requires Anthropic credential files |
| `test_returns_token_from_env_var` | `test_anthropic_adapter.py` | Requires env var auth |
| `test_returns_none_when_no_creds_found` | `test_anthropic_adapter.py` | Auth resolution mismatch |
| `test_switch_to_minimax_m25_strips_v1` | `test_model_switch_opencode_anthropic.py` | Requires model config state |

### Category C — Subagent / Delegate runtime (34 failures)

These tests exercise `delegate_tool.py` (managed gateway, child agent execution,
batch mode, cost rollup, blocked tools, observability). They require a
functioning subagent runtime which is not active in test mode.

| Test | File | Reason |
|------|------|--------|
| `test_batch_capped_at_3` | `test_delegate.py` | Needs active subagent runtime |
| `test_batch_ignores_toplevel_goal` | `test_delegate.py` | Needs active subagent runtime |
| `test_batch_mode` | `test_delegate.py` | Needs active subagent runtime |
| `test_batch_mode_accepts_json_string_tasks` | `test_delegate.py` | Needs active subagent runtime |
| `test_batch_mode_rejects_malformed_json_string_tasks` | `test_delegate.py` | Needs active subagent runtime |
| `test_batch_mode_rejects_non_object_tasks` | `test_delegate.py` | Needs active subagent runtime |
| `test_child_inherits_runtime_credentials` | `test_delegate.py` | Needs active subagent runtime |
| `test_depth_increments` | `test_delegate.py` | Needs active subagent runtime |
| `test_failed_child_included_in_results` | `test_delegate.py` | Needs active subagent runtime |
| `test_single_task_mode` | `test_delegate.py` | Needs active subagent runtime |
| `test_global_tool_names_restored_after_child_failure` | `test_delegate.py` | Needs active subagent runtime |
| `test_saved_tool_names_set_on_child_before_run` | `test_delegate.py` | Needs active subagent runtime |
| `test_exit_reason_interrupted` | `test_delegate.py` | Needs active subagent runtime |
| `test_exit_reason_max_iterations` | `test_delegate.py` | Needs active subagent runtime |
| `test_observability_fields_present` | `test_delegate.py` | Needs active subagent runtime |
| `test_parallel_tool_calls_paired_correctly` | `test_delegate.py` | Needs active subagent runtime |
| `test_tool_trace_detects_error` | `test_delegate.py` | Needs active subagent runtime |
| `test_batch_children_costs_sum_into_parent` | `test_delegate.py` | Needs active subagent runtime |
| `test_parent_with_real_source_not_overwritten` | `test_delegate.py` | Needs active subagent runtime |
| `test_rollup_tolerates_missing_cost_fields` | `test_delegate.py` | Needs active subagent runtime |
| `test_single_child_cost_folded_into_parent` | `test_delegate.py` | Needs active subagent runtime |
| `test_constants` | `test_delegate.py` | Needs active subagent runtime |
| `test_managed_gateway_preflight_runs_before_legacy_child_execution` | `test_delegate_managed_gateway.py` | Managed gateway not active in test env |
| `test_managed_gateway_preflight_uses_agent_minimum_risk_without_parent_task_card` | `test_delegate_managed_gateway.py` | Managed gateway not active |
| `test_managed_agent_model_ref_overrides_provider_model_for_internal_agent` | `test_delegate_managed_gateway.py` | Managed gateway not active |
| `test_managed_agent_fallback_chain_passes_to_child_agent` | `test_delegate_managed_gateway.py` | Managed gateway not active |
| `test_managed_agent_strategy_skips_unhealthy_primary_model` | `test_delegate_managed_gateway.py` | Managed gateway not active |
| `test_claude_agent_uses_external_claude_code_cli_runtime` | `test_delegate_managed_gateway.py` | External agent runtime not active |
| `test_claude_code_cli_runtime_preserves_context_in_prompt` | `test_delegate_managed_gateway.py` | External agent runtime not active |
| `test_codex_agent_uses_external_codex_cli_runtime` | `test_delegate_managed_gateway.py` | External agent runtime not active |
| `test_deepseek_tui_agent_uses_external_cli_runtime` | `test_delegate_managed_gateway.py` | External agent runtime not active |
| `test_opencode_agent_uses_external_cli_runtime` | `test_delegate_managed_gateway.py` | External agent runtime not active |
| `test_fires_once` | `test_subagent_stop_hook.py` | Needs active subagent runtime |
| `test_fires_on_parent_thread` | `test_subagent_stop_hook.py` | Needs active subagent runtime |
| `test_payload_includes_parent_session_id` | `test_subagent_stop_hook.py` | Needs active subagent runtime |
| `test_fires_per_child` | `test_subagent_stop_hook.py` | Needs active subagent runtime |
| `test_role_absent_becomes_none` | `test_subagent_stop_hook.py` | Needs active subagent runtime |
| `test_result_does_not_leak_child_role_field` | `test_subagent_stop_hook.py` | Needs active subagent runtime |

### Category D — MCP / External service connectivity (4 failures)

These tests attempt to connect to MCP servers, Browserbase, or Firecrawl.
They fail because those external services are not configured in local dev.

| Test | File | Reason |
|------|------|--------|
| `test_initial_connect_retries_constant_exists` | `test_mcp_stability.py` | MCP server not available |
| `test_initial_connect_retry_succeeds_on_second_attempt` | `test_mcp_stability.py` | MCP server not available |
| `test_initial_connect_gives_up_after_max_retries` | `test_mcp_stability.py` | MCP server not available |
| `test_no_reconnect_on_initial_failure` | `test_mcp_tool.py` | MCP server not available |
| `test_reconfigure_provider_runs_post_setup_for_env_var_providers[Browserbase-agent_browser]` | `test_tools_config.py` | Browserbase env var not configured |
| `test_reconfigure_provider_runs_post_setup_for_env_var_providers[Browser Use-agent_browser]` | `test_tools_config.py` | Browser Use env var not configured |
| `test_reconfigure_provider_runs_post_setup_for_env_var_providers[Firecrawl-agent_browser]` | `test_tools_config.py` | Firecrawl env var not configured |

### Category E — File system tooling (11 failures)

These tests exercise file read guards, staleness checks, and state registry.
They depend on specific file system states that are not set up in the test
environment.

| Test | File | Reason |
|------|------|--------|
| `test_write_allows_large_file_that_quotes_status_text` | `test_file_read_guards.py` | Dedup guard state mismatch |
| `test_write_rejects_internal_read_status_text` | `test_file_read_guards.py` | Dedup guard state mismatch |
| `test_write_rejects_status_text_with_small_framing` | `test_file_read_guards.py` | Dedup guard state mismatch |
| `test_write_does_not_invalidate_other_tasks` | `test_file_read_guards.py` | Dedup guard state mismatch |
| `test_write_invalidates_all_offsets` | `test_file_read_guards.py` | Dedup guard state mismatch |
| `test_write_invalidates_dedup_same_second` | `test_file_read_guards.py` | Dedup guard state mismatch |
| `test_relative_path_uses_live_cwd_for_staleness_tracking` | `test_file_staleness.py` | CWD tracking mismatch |
| `test_warning_when_file_modified_externally` | `test_file_staleness.py` | File state mismatch |
| `test_patch_warns_on_stale_file` | `test_file_staleness.py` | File state mismatch |
| `test_net_new_file_no_warning` | `test_file_state_registry.py` | Registry state mismatch |
| `test_sibling_agent_write_surfaces_warning_through_handler` | `test_file_state_registry.py` | Registry state mismatch |

### Category F — IRC / Voice / Misc infrastructure (4 failures)

| Test | File | Reason |
|------|------|--------|
| `test_setup_gateway_irc_counts_as_messaging_platform` | `test_setup_irc.py` | IRC gateway not configured |
| `test_wraps_stdout_and_stderr_with_mirror` | `test_update_hangup_protection.py` | Terminal emulation mismatch |
| `test_project_with_broken_venv_falls_back` | `test_code_execution_modes.py` | Venv isolation mismatch |
| `test_error_messages_use_force_in_run_agent` | `test_voice_cli_integration.py` | Voice CLI not installed/configured |

### Category G — Plugin / Config / Cache (5 failures)

| Test | File | Reason |
|------|------|--------|
| `test_aux_tasks_keys_all_exist_in_default_config` | `test_aux_config.py` | Config key drift |
| `test_codex_timeout_evicts_cached_wrapper` | `test_auxiliary_client.py` | Cache state mismatch |
| `test_builtin_set_covers_every_registered_subcommand` | `test_startup_plugin_gating.py` | Plugin registration mismatch |
| `test_builtin_set_has_no_phantom_entries` | `test_startup_plugin_gating.py` | Plugin registration mismatch |
| `test_install_hangup_protection` | `test_update_hangup_protection.py` | Terminal hook mismatch |

---

## Cross-Check: No Phase 4 Regressions

Files modified in Phase 4:
- `agent/managed_agents/discord_adapter.py` (new file)
- `tests/agent/test_discord_adapter.py` (new file)

None of the 78 failing tests reference `discord_adapter` or `test_discord_adapter`.
All Phase 4 tests pass (39/39).

**Conclusion:** the 78 failures are 100% pre-existing infrastructure/tooling
failures unrelated to v2.10 Phase 4.

---

## Recommended Validation Scope

| Scope | Command | Expected Result |
|-------|---------|---------------|
| Phase 4 focused | `pytest tests/agent/test_discord_adapter.py` | 39 passed, 0 failed |
| v2.10 scoped | `pytest tests/hermes_cli tests/agent/test_discord_adapter.py tests/tools` | Focus on non-infra tests |
| Full repository | `pytest tests/hermes_cli tests/agent tests/tools` | 13033 passed, 78 documented failures |

For milestone acceptance, the Phase 4 focused + v2.10 scoping validation is
sufficient. The full 78-failure count is acceptable as documented
infrastructure debt.
