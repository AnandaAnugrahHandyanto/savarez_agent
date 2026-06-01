# Hermes Heartbeat Research Log

Status: Discovery Complete
Owner: Codex / Agent Team
Purpose: Record verified findings from the Hermes-agent repository before implementation.

---

# Discovery Summary

## Current Recommendation

Choose **Option B: plugin plus minor core patch**.

The heartbeat policy, sources, prompt construction, budgets, cooldowns, and
logging belong in `plugins/heartbeat/`. The repository does not currently expose
a managed periodic-service API or a public proactive-notification API to general
plugins. Add those as generic plugin capabilities rather than heartbeat-specific
branches in core.

`cron/scheduler.py:run_job()` proves that Hermes can already execute a synthetic,
non-interactive agent run. `gateway/run.py:_start_cron_ticker()` proves that the
gateway already owns a background thread with a clean stop event. These are the
reference implementations for a narrow host extension.

For the first implementation, prefer a bounded structured review through
`hermes_cli/plugins.py:PluginContext.llm` and
`agent/plugin_llm.py:PluginLlm.complete_structured()`. Only add a public
synthetic-agent-run adapter if the product requirement explicitly needs the
normal Hermes tool loop.

Treat Main-agent continuity as a required capability, separate from outbound
notification delivery. Persist surfaced findings in a plugin-owned durable
inbox, then register a `pre_llm_call` hook that injects a bounded set of active
findings into the next primary-agent turn. When delivery targets a known gateway
session, also mirror the user-visible notification into that transcript through
the host notification facade. When an external memory provider is active,
publish the delivered finding as an intentional provider observation so recall
systems such as Honcho can reinforce later context.

## Current Risk Level

**Medium.** The policy engine can remain isolated in a plugin, but a pure plugin
would need to start an unmanaged thread during plugin discovery or depend on
private cron/delivery functions.

---

# Evidence Table

| Area | Source | Symbol | Observed behavior | Discovery conclusion |
|---|---|---|---|---|
| Plugin load | `hermes_cli/plugins.py` | `PluginManager.discover_and_load()`, `PluginManager._load_plugin()` | Discovery imports a plugin module and calls `register(ctx)` synchronously. | General plugin registration exists, but it is not a process-service lifecycle. |
| Plugin hooks | `hermes_cli/plugins.py` | `VALID_HOOKS`, `PluginManager.invoke_hook()` | Registered callbacks are invoked synchronously; exceptions are logged and isolated; non-`None` returns are collected. | Hooks are usable for request-scoped integration, not for owning a durable scheduler. |
| Gateway scheduler | `gateway/run.py` | `_start_cron_ticker()` | A gateway-owned background thread calls `cron.scheduler.tick()` every 60 seconds until a stop event is set. | The gateway is the existing host for durable periodic work. |
| Scheduled agent run | `cron/scheduler.py` | `run_job()` | Creates an `AIAgent`, invokes `agent.run_conversation(prompt)`, uses a unique cron session, disables recursive/sensitive toolsets, sets `skip_memory=True`, and closes resources. | Synthetic non-interactive execution is already proven inside cron. |
| Bounded plugin LLM | `hermes_cli/plugins.py`, `agent/plugin_llm.py` | `PluginContext.llm`, `PluginLlm.complete_structured()` | A plugin can request a host-owned bounded structured completion without receiving raw credentials. | Best initial heartbeat reasoning path. |
| CLI injection | `hermes_cli/plugins.py` | `PluginContext.inject_message()` | Enqueues a synthetic CLI turn only when a CLI reference exists; returns `False` in gateway mode. | Not a cross-platform heartbeat trigger. |
| Built-in memory | `tools/memory_tool.py` | `MemoryStore.load_from_disk()` | Loads bounded curated `MEMORY.md` and `USER.md` entries from the profile-aware memory directory. | Suitable lightweight initial memory source. |
| External memory | `agent/memory_provider.py`, `agent/memory_manager.py` | `MemoryProvider.initialize()`, `MemoryProvider.prefetch()`, `MemoryManager.initialize_all()`, `MemoryManager.prefetch_all()` | External recall is provider-managed and session-oriented. Provider initialization receives context flags because non-primary runs can corrupt user representations. | Add only behind a provider-aware read adapter after provider compatibility tests. |
| Session todos | `tools/todo_tool.py`, `run_agent.py` | `TodoStore`, `AIAgent._hydrate_todo_store()` | Todos are held in-memory on an agent instance and may be reconstructed from conversation history. | Not a lightweight global heartbeat source. |
| Kanban reads | `hermes_cli/kanban_db.py` | `list_tasks()`, `board_stats()`, `task_age()` | SQLite accessors provide bounded task listing, counts, and task ages. | Suitable read-only initial task source. |
| Delivery | `cron/scheduler.py`, `tools/send_message_tool.py` | `_deliver_result()`, `_send_to_platform()`, `_send_via_adapter()` | Cron resolves proactive targets and delivery; send-message routing prefers live adapters and can fall back to registered standalone senders. | Extract or wrap a public host-owned notification API. |
| Delivery retries | `gateway/run.py` | `GatewayRunner._kanban_notifier_watcher()` | Polls in the gateway loop, sends through connected adapters, rewinds claims for retry, advances cursors for dedup, and drops repeatedly failing subscriptions. | Existing gateway pattern for reliable proactive notifications. |
| Plugin config | `hermes_cli/config.py` | `read_raw_config()`, `_deep_merge()`, `load_config()` | Raw profile-aware YAML can be read cheaply; deep merge preserves user keys not present in defaults. | A plugin can own a `heartbeat:` config block and local validation. |
| Context engines | `agent/context_engine.py` | `ContextEngine`, `ContextEngine.on_session_start()`, `ContextEngine.on_session_end()` | Context engines expose conversation compaction lifecycle, not an arbitrary heartbeat context-pack API. | Heartbeat should build its own bounded context pack. |
| Main-agent context bridge | `agent/conversation_loop.py`, `gateway/session.py`, `gateway/run.py` | `run_conversation()`, `SessionStore.append_to_transcript()`, `SessionStore.load_transcript()` | `pre_llm_call` context is injected into the current API-only user turn; gateway transcripts can persist an assistant notification and reload it on the next message. | Persist heartbeat findings in a dedicated inbox, inject active findings on primary turns, and mirror delivered notifications into known target transcripts. |
| External-memory reinforcement | `run_agent.py`, `agent/memory_manager.py`, `agent/memory_provider.py`, `plugins/memory/honcho/__init__.py` | `AIAgent._sync_external_memory_for_turn()`, `MemoryManager.sync_all()`, `MemoryProvider.sync_turn()`, `HonchoMemoryProvider.sync_turn()`, `HonchoMemoryProvider.prefetch()` | Completed agent turns are synced to external providers and prefetch is warmed for the next turn. Honcho stores user and assistant peer messages asynchronously and can inject recalled context on later turns. Raw adapter sends do not invoke this path. | Add an intentional provider-observation hook for delivered heartbeat findings; do not assume gateway delivery alone updates external memory. |

---

# Finding 1: Plugin Lifecycle

## Question

Can a plugin safely start and stop a background scheduler?

## Status

**Partially supported; minor core extension required.**

## Evidence

- `hermes_cli/plugins.py:PluginManager.discover_and_load()` is idempotent and
  calls `PluginManager._load_plugin()` for discovered manifests.
- `hermes_cli/plugins.py:PluginManager._load_plugin()` imports the plugin module
  and invokes its `register(ctx)` function synchronously.
- `hermes_cli/plugins.py:PluginManager.__init__()` stores plugins, hooks, tools,
  CLI handlers, dashboards, context engines, and auxiliary tasks. It does not
  store managed periodic callbacks or service shutdown callbacks.
- `gateway/run.py:_start_cron_ticker()` owns a daemon thread with a
  `threading.Event`; it invokes `cron.scheduler.tick()` periodically and exits
  when the stop event is set.
- `gateway/run.py:start_gateway()` starts the cron ticker after runner startup
  and sets its stop event and joins it on the ordinary shutdown path.
- `hermes_cli/cron.py:cron_status()` reports that jobs do not fire
  automatically when the gateway is not running.

## Notes

Starting a heartbeat thread inside `register(ctx)` is technically possible but
unsupported: registration runs during discovery, while the plugin API provides
no matching managed shutdown contract. Add a generic
`PluginContext.register_periodic_task(...)` capability and execute registered
tasks from a gateway-owned lifecycle. The first implementation must explicitly
decide whether gateway-only automatic execution is acceptable.

## Risk

**Medium.** An unmanaged plugin thread could duplicate work across processes or
outlive the runtime that loaded it.

---

# Finding 2: Agent Invocation

## Question

Can a plugin trigger an agent run programmatically?

## Status

**Bounded LLM review is supported; a public full-agent trigger is not exposed.**

## Evidence

- `hermes_cli/plugins.py:PluginContext.llm` lazily creates
  `agent/plugin_llm.py:PluginLlm`.
- `agent/plugin_llm.py:PluginLlm.complete()` and
  `PluginLlm.complete_structured()` expose bounded host-owned completions with
  caller-supplied token and timeout limits.
- `agent/plugin_llm.py:PluginLlm._invoke_sync()` delegates to
  `agent.auxiliary_client.call_llm()`; plugin code does not receive raw API keys.
- `hermes_cli/plugins.py:PluginContext.register_auxiliary_task()` lets a plugin
  declare an `auxiliary.<task_key>` routing block for model selection.
- `cron/scheduler.py:run_job()` constructs `run_agent.py:AIAgent`, then invokes
  `agent.run_conversation(prompt)` in a worker thread.
- `agent/background_review.py:spawn_background_review_thread()` and
  `_run_review_in_thread()` are additional prior art for a restricted forked
  agent review, but that path is triggered by an active conversation and is not
  a general plugin API.

## Notes

Use `ctx.llm.complete_structured(...)` for an initial awareness-only heartbeat.
If normal tool-loop semantics become mandatory, expose a small generic scheduled
agent-run adapter modeled on `cron.scheduler.run_job()`.

## Risk

**Low for bounded LLM review; medium for full-agent execution.** Full-agent runs
need explicit toolset restrictions, unique sessions, cleanup, and idle timeout.

---

# Finding 3: Synthetic Messages

## Question

Can Hermes accept a synthetic heartbeat turn without manual user input?

## Status

**Yes in existing internal paths; not through a general cross-platform plugin API.**

## Evidence

- `hermes_cli/plugins.py:PluginContext.inject_message()` queues a synthetic turn
  through the active CLI reference. The method logs a warning and returns
  `False` when `_cli_ref` is absent, including gateway mode.
- `cron/scheduler.py:_build_job_prompt()` prepends scheduled-run instructions,
  automatic delivery guidance, and the `[SILENT]` suppression contract.
- `cron/scheduler.py:run_job()` passes the constructed prompt directly to
  `AIAgent.run_conversation()`, so scheduled work does not require manual input.
- `cron/scheduler.py:SILENT_MARKER` and `tick()` suppress successful delivery
  when the returned content contains `[SILENT]`, while output persistence still
  occurs.

## Notes

CLI injection is not the heartbeat transport. A bounded plugin LLM review is
enough for the first phase. A future synthetic normal turn should use a generic
host adapter modeled on cron rather than `inject_message()`.

## Risk

**Medium.** Reusing CLI injection would silently fail for gateway-only runtimes.

---

# Finding 4: Memory Access

## Question

Can heartbeat retrieve memory without loading full chat history?

## Status

**Yes for built-in curated memory; external provider recall requires validation.**

## Evidence

- `tools/memory_tool.py:get_memory_dir()` resolves the profile-aware
  `<HERMES_HOME>/memories` directory.
- `tools/memory_tool.py:MemoryStore.load_from_disk()` reads and sanitizes
  `MEMORY.md` and `USER.md` into bounded in-memory entries.
- `agent/agent_init.py` instantiates `MemoryStore` and calls `load_from_disk()`
  during normal agent initialization when memory is enabled.
- `agent/memory_provider.py:MemoryProvider.initialize()` documents a
  session-oriented provider lifecycle and receives `agent_context`, including
  primary, subagent, cron, and flush contexts.
- `agent/memory_provider.py:MemoryProvider.prefetch()` is the fast recall method.
- `agent/memory_manager.py:MemoryManager.initialize_all()` and `prefetch_all()`
  initialize providers and combine recall results while isolating failures.
- `cron/scheduler.py:run_job()` passes `skip_memory=True` to `AIAgent` with the
  source comment that cron system prompts would corrupt user representations.

## Notes

The first heartbeat memory source should instantiate `MemoryStore`, call
`load_from_disk()`, and select a bounded snapshot. External memory recall should
remain opt-in until a provider-aware read adapter can initialize, query, and
shut down providers without writing heartbeat prompts into user memory.

## Risk

**Medium.** Blindly initializing an external provider in a synthetic run can
pollute durable user representation.

---

# Finding 5: Tasks / Kanban Access

## Question

Can heartbeat query active tasks, goals, or Kanban state?

## Status

**Yes for Kanban; no lightweight global session-todo API exists.**

## Evidence

- `tools/todo_tool.py:TodoStore` is an in-memory task list attached to one agent.
- `run_agent.py:AIAgent._hydrate_todo_store()` reconstructs todos by scanning
  prior conversation history because gateway messages create fresh agents.
- `hermes_cli/kanban_db.py:list_tasks()` lists tasks with filters and a limit.
- `hermes_cli/kanban_db.py:board_stats()` returns status and assignee counts plus
  oldest-ready age.
- `hermes_cli/kanban_db.py:task_age()` derives age data for one task.
- `tools/kanban_tools.py:_handle_list()` exposes a bounded agent tool listing
  with a default limit of 50 and maximum of 200, but it also calls board
  recomputation before listing.

## Notes

Use `hermes_cli.kanban_db.connect()`, `list_tasks()`, `board_stats()`, and
`task_age()` directly for a read-only heartbeat source. Do not use
`tools/kanban_tools.py:_handle_list()` because heartbeat collection should not
mutate board readiness as a side effect. Exclude session todos from the first
implementation.

## Risk

**Low.** The Kanban DB API is already used by dashboard and notifier code.

---

# Finding 6: Notification Delivery

## Question

How should heartbeat emit user-visible updates?

## Status

**Existing delivery internals are reusable, but a public plugin API is missing.**

## Evidence

- `cron/scheduler.py:_deliver_result()` resolves cron delivery targets, wraps
  results, prefers connected adapters, and falls back to standalone delivery.
- `tools/send_message_tool.py:_send_via_adapter()` prefers the live gateway
  adapter and then uses
  `gateway/platform_registry.py:PlatformEntry.standalone_sender_fn`.
- `tools/send_message_tool.py:_send_to_platform()` handles platform-specific
  standalone routing and message chunking.
- `gateway/platform_registry.py:PlatformEntry.cron_deliver_env_var` describes
  platform-specific default delivery configuration.
- `gateway/run.py:GatewayRunner._kanban_notifier_watcher()` sends proactive
  messages through connected adapters, rewinds failed claims for retry,
  advances cursors for deduplication, and drops dead subscriptions after three
  consecutive send failures.

## Notes

Expose a generic host-owned notification service to plugins. Its implementation
should wrap or extract the existing routing behavior rather than calling the
agent-facing `send_message` tool from the heartbeat policy layer.

## Risk

**Medium.** Calling private cron functions from a plugin would couple the plugin
to scheduler internals and cron-specific message wrapping.

---

# Finding 7: Plugin Configuration

## Question

Can the heartbeat plugin register and validate config?

## Status

**A plugin can read its config; general schema registration is not exposed.**

## Evidence

- `hermes_cli/config.py:read_raw_config()` reads profile-aware YAML as-is and
  caches by file metadata.
- `hermes_cli/config.py:_deep_merge()` copies override keys even when they are
  absent from defaults.
- `hermes_cli/config.py:load_config()` merges user YAML into `DEFAULT_CONFIG`.
- `hermes_cli/plugins.py:_get_enabled_plugins()` reads the plugin enable list
  from config.
- `hermes_cli/plugins.py:PluginContext.register_auxiliary_task()` validates an
  auxiliary task key and declares default routing metadata for
  `auxiliary.<task_key>`.
- No `PluginContext.register_config_schema()` or equivalent general plugin
  config registration method exists in `hermes_cli/plugins.py:PluginContext`.

## Notes

Store user settings under a plugin-owned top-level `heartbeat:` block and parse
them with a plugin-local defaults-and-validation layer. Declare a heartbeat
auxiliary LLM task if the plugin needs configurable model routing. A setup UI
schema can be a later generic plugin capability if required.

## Risk

**Low.** Runtime config works without a core defaults entry; setup UX is the
missing convenience.

---

# Finding 8: Hook Behavior

## Question

Are lifecycle and LLM hooks usable for heartbeat?

## Status

**Usable for integration, not as the scheduler.**

## Evidence

- `hermes_cli/plugins.py:VALID_HOOKS` includes `pre_llm_call`,
  `post_llm_call`, `on_session_start`, `on_session_end`,
  `on_session_finalize`, and `on_session_reset`.
- `hermes_cli/plugins.py:PluginManager.invoke_hook()` calls callbacks
  synchronously and catches each callback exception.
- `agent/conversation_loop.py:run_conversation()` invokes `pre_llm_call` before
  the tool loop and injects returned context ephemerally into the API messages.
- `agent/conversation_loop.py:run_conversation()` invokes `post_llm_call` after
  a successful final response.
- `agent/conversation_loop.py:run_conversation()` invokes `on_session_end` at
  the end of each conversation run, so this hook is not a process shutdown
  event.
- `cli.py:HermesCLI._notify_session_boundary()` emits
  `on_session_finalize` and `on_session_reset` for CLI boundaries.
- `gateway/run.py` emits `on_session_finalize` and `on_session_reset` when
  gateway sessions roll over.

## Notes

Heartbeat can use hooks to observe or enrich active sessions, but periodic work
must not block `invoke_hook()`. Durable scheduling belongs in the host lifecycle
extension from Finding 1.

## Risk

**Medium.** Long heartbeat work inside synchronous hooks would add latency to
normal conversations.

---

# Finding 9: Context / LCM Integration

## Question

Can heartbeat request or construct a lightweight context pack compatible with
Hermes-LCM?

## Status

**Heartbeat can construct a bounded pack; no arbitrary context-engine pack API is exposed.**

## Evidence

- `agent/context_engine.py:ContextEngine` defines context-window management,
  compaction, optional tools, and session lifecycle methods.
- `agent/context_engine.py:ContextEngine.on_session_start()` and
  `ContextEngine.on_session_end()` are conversation-session callbacks.
- `hermes_cli/plugins.py:PluginContext.register_context_engine()` lets one
  plugin provide a `ContextEngine` implementation.
- `agent/conversation_loop.py:run_conversation()` injects memory-manager recall
  and `pre_llm_call` hook context into API messages without mutating stored
  conversation messages.
- No method on `agent/context_engine.py:ContextEngine` exposes arbitrary
  heartbeat recall-pack construction.

## Notes

Build a heartbeat-specific bounded context pack from configured sources:
active-hour metadata, cooldown/budget state, curated memory, and read-only
Kanban summaries. Do not require full conversation history or direct
context-engine internals.

## Risk

**Low for an explicit pack; unverified for provider-specific LCM recall.**

---

# Finding 10: Test Strategy

## Question

Which existing tests provide the closest patterns?

## Status

**Verified.**

## Evidence

- `tests/hermes_cli/test_plugins.py:TestPluginDiscovery`,
  `TestPluginHooks`, and `TestPluginContext` cover plugin loading, hook
  isolation, and registered plugin capabilities.
- `tests/agent/test_plugin_llm.py` covers `PluginLlm` routing, trust policy,
  structured responses, and async behavior.
- `tests/cron/test_scheduler.py:TestRunJobSessionPersistence`,
  `TestSilentDelivery`, `TestBuildJobPromptSilentHint`, and
  `TestParallelTick` cover scheduled-agent cleanup, suppression, prompt
  guidance, and concurrent ticks.
- `tests/gateway/test_kanban_notifier.py` covers notifier deduplication, claim
  contention, adapter disconnect rewind, and send-exception rewind.
- `tests/hermes_cli/test_kanban_db.py` covers the SQLite Kanban access layer.
- `tests/tools/test_memory_tool_import_fallback.py` instantiates
  `tools.memory_tool.MemoryStore` against a temporary home.

---

# Finding 11: Main-Agent Continuity

## Question

How does the Default or Main agent know what heartbeat surfaced?

## Status

**Requires an explicit durable inbox and next-turn context bridge. Delivery alone is insufficient.**

## Evidence

- `cron/scheduler.py:_deliver_result()` sends cron output through platform
  delivery. It does not append the result to the user's active Main-agent
  conversation.
- `agent/conversation_loop.py:run_conversation()` invokes `pre_llm_call` once per
  conversation turn and accepts plugin-returned context.
- `agent/conversation_loop.py:run_conversation()` appends `pre_llm_call` context
  to the current API-only user message and deliberately does not mutate the
  persisted conversation.
- `gateway/session.py:SessionStore.append_to_transcript()` persists an
  assistant message through `hermes_state.py:SessionDB.append_message()`.
- `gateway/session.py:SessionStore.load_transcript()` reloads canonical SQLite
  conversation rows through
  `hermes_state.py:SessionDB.get_messages_as_conversation()`.
- `gateway/run.py:GatewayRunner._handle_message_with_agent()` loads the active
  transcript with `SessionStore.load_transcript()` before each gateway turn.
- `cli.py:HermesCLI` stores the live CLI transcript in
  `self.conversation_history` and passes it to `AIAgent.run_conversation()`.
  A SQLite-only out-of-band append would not update that in-memory list.
- `tools/memory_tool.py:MemoryStore` freezes its system-prompt snapshot when
  `load_from_disk()` runs. Mid-session writes are durable but do not change the
  active system prompt until the next session start.
- `gateway/run.py` reuses cached `AIAgent` instances for matching gateway
  sessions to preserve the frozen system prompt and tool schemas.
- `run_agent.py:AIAgent._sync_external_memory_for_turn()` mirrors completed
  agent turns into `MemoryManager.sync_all()` and calls
  `MemoryManager.queue_prefetch_all()` for next-turn recall.
- `agent/memory_manager.py:MemoryManager.sync_all()` delegates completed turns
  to each external provider's `sync_turn()` implementation.
- `plugins/memory/honcho/__init__.py:HonchoMemoryProvider.sync_turn()` adds the
  cleaned user and assistant text as Honcho peer messages asynchronously.
- `plugins/memory/honcho/__init__.py:HonchoMemoryProvider.prefetch()` returns
  recalled representation, card, and optional dialectic context for normal
  turn-time injection. It returns no automatic context in tools-only mode.
- `agent/memory_provider.py:MemoryProvider` provides optional hooks such as
  `on_memory_write()` and `on_delegation()`, but it does not currently define a
  general external-observation hook.

## Notes

Add a plugin-owned, profile-aware durable `HeartbeatInbox`. Store structured
findings before delivery with fields such as finding ID, scope, summary,
recommended action, created time, expiry, delivery status, and presentation
status.

Register a heartbeat `pre_llm_call` hook that reads a bounded set of active
findings and returns them as context for primary turns. Filter out heartbeat,
cron, subagent, and auxiliary execution lanes to prevent feedback loops. Keep
findings available until acknowledged or expired; do not consume them merely
because a notification was sent.

The host notification facade should additionally mirror a delivered heartbeat
notification into the known target gateway transcript as an assistant message.
That makes a reply such as "do it" conversationally coherent in the same
channel. Transcript mirroring is supplemental: the durable inbox plus
`pre_llm_call` bridge remains the cross-session and CLI-safe correctness path.

External memory should reinforce this flow when configured. Add a generic
`MemoryProvider.on_observation(event)` optional hook and
`MemoryManager.on_observation(event)` fan-out. After a heartbeat finding is
accepted and delivered, publish a structured assistant-side observation with
clear phrasing, for example:

```text
[HEARTBEAT FINDING SURFACED TO USER]
Finding: <summary>
Recommended action: <action>
Status: notified; keep this active until acknowledged or expired.
```

Honcho can store this as an assistant-peer message so its normal recall path can
surface it later. Other providers may implement their own mapping or inherit a
no-op. Do not call `MemoryManager.sync_all()` with a fabricated user message:
that API models completed user/assistant exchanges, while a delivered heartbeat
finding is a system observation.

Do not assume adapter delivery alone updates external memory. A direct gateway
`adapter.send(...)` is outside `AIAgent._sync_external_memory_for_turn()`.
Transcript mirroring may help providers that perform end-of-session transcript
extraction, but provider behavior differs and Honcho's
`HonchoMemoryProvider.on_session_end()` only flushes pending writes.

Do not write transient heartbeat findings into curated `MEMORY.md`. That store
is intentionally frozen for an active session and is meant for durable personal
notes, not expiring notification state.

## Risk

**High if omitted.** The user could receive a useful proactive notification and
then reply to a Main agent that has no record of the finding.

---

# Proposed Implementation Option

## Option A: Pure Plugin

**Not recommended for production.** A prototype could create a recurring cron
job through `cron/jobs.py:create_job()` or start its own thread during plugin
registration. The former inherits cron-specific full-agent and delivery
semantics; the latter has no managed plugin shutdown contract.

## Option B: Plugin Plus Minor Core Patch

**Recommended.** Add generic managed periodic-task registration and generic
host notification delivery. Keep heartbeat policy and sources entirely inside
`plugins/heartbeat/`. Use `PluginContext.llm` for the initial bounded review.

## Option C: External Supervisor Service

**Not recommended initially.** `gateway/run.py:_start_cron_ticker()` and
`cron/scheduler.py:run_job()` already demonstrate in-process scheduling,
shutdown, synthetic execution, and delivery. An external service would add
deployment and configuration surface without resolving a repository limitation.

---

# Proposed Directory Structure

```text
plugins/heartbeat/
|-- plugin.yaml
|-- __init__.py
|-- config.py
|-- scheduler.py
|-- engine.py
|-- context.py
|-- delivery.py
|-- inbox.py
|-- event_log.py
|-- sources/
|   |-- __init__.py
|   |-- base.py
|   |-- kanban.py
|   `-- memory.py
`-- policies/
    |-- __init__.py
    |-- base.py
    |-- active_hours.py
    |-- cooldown.py
    `-- budget.py

tests/plugins/heartbeat/
|-- test_config.py
|-- test_engine.py
|-- test_inbox.py
|-- test_sources.py
|-- test_policies.py
|-- test_scheduler.py
`-- test_integration.py
```

Do not add `session_history.py` until a bounded unresolved-promise query is
specified and tested. `run_agent.py:AIAgent._hydrate_todo_store()` shows that
session todo recovery currently depends on conversation history.

---

# Risks And Blockers

| Blocker or risk | Evidence | Severity | Proposed resolution |
|---|---|---|---|
| No managed general-plugin periodic lifecycle | `hermes_cli/plugins.py:PluginContext`, `PluginManager.__init__()` expose no periodic service registry; `gateway/run.py:_start_cron_ticker()` is host-owned. | High for pure plugin | Add generic `register_periodic_task(...)` and gateway-owned execution. |
| Automatic periodic execution currently depends on the gateway | `hermes_cli/cron.py:cron_status()` reports that jobs will not fire when no gateway process is running. | Medium | Declare gateway-only support for the first release or add a separate supported scheduler host later. |
| No public plugin notification facade | Delivery is private in `cron/scheduler.py:_deliver_result()` and internal in `tools/send_message_tool.py:_send_to_platform()`. | Medium | Extract or wrap a host-owned plugin notification API. |
| CLI-only injection | `hermes_cli/plugins.py:PluginContext.inject_message()` returns `False` without `_cli_ref`. | Medium | Use bounded plugin LLM review or a generic scheduled-agent adapter. |
| External memory write pollution | `cron/scheduler.py:run_job()` sets `skip_memory=True`; `agent/memory_provider.py:MemoryProvider.initialize()` documents context-sensitive provider behavior. | Medium | Start with `MemoryStore`; add tested read adapters per provider. |
| Session todos are history-bound | `tools/todo_tool.py:TodoStore`, `run_agent.py:AIAgent._hydrate_todo_store()`. | Low | Exclude from first implementation. |
| Direct LCM recall pack is unverified | `agent/context_engine.py:ContextEngine` has no arbitrary recall-pack method. | Low | Construct an explicit bounded heartbeat pack. |
| Proactive delivery does not automatically inform the Main agent | `cron/scheduler.py:_deliver_result()` sends outward; `agent/conversation_loop.py:run_conversation()` provides an API-only `pre_llm_call` injection path; `gateway/session.py:SessionStore.append_to_transcript()` can mirror known-session assistant messages. | High | Add a durable heartbeat inbox, inject active findings on primary turns, and mirror known-session notifications through the host facade. |
| Raw gateway delivery does not automatically update external memory | `run_agent.py:AIAgent._sync_external_memory_for_turn()` calls `MemoryManager.sync_all()` only after completed agent turns; `plugins/memory/honcho/__init__.py:HonchoMemoryProvider.sync_turn()` is the Honcho write path. | Medium | Add generic `MemoryProvider.on_observation(event)` fan-out and publish accepted delivered findings with attention-oriented phrasing. |

---

# Minimal Implementation Plan

1. Add a generic managed periodic-task registration API to
   `hermes_cli/plugins.py:PluginContext` and execute registered callbacks from a
   gateway-owned lifecycle modeled on `gateway/run.py:_start_cron_ticker()`.
2. Add a generic host notification facade that reuses the routing behavior in
   `cron/scheduler.py:_deliver_result()` and
   `tools/send_message_tool.py:_send_via_adapter()`.
3. Scaffold `plugins/heartbeat/` with plugin-local config validation, active
   hours, cooldown, budget, structured logging, and a profile-aware durable
   findings inbox.
4. Register a heartbeat `pre_llm_call` hook that injects a bounded set of
   active inbox findings into primary-agent turns and excludes background
   execution lanes.
5. Add a generic external-memory observation hook and publish delivered
   heartbeat findings with explicit attention-oriented phrasing. Implement a
   Honcho assistant-peer mapping; leave unsupported providers as no-op.
6. Add read-only source adapters for `tools.memory_tool.MemoryStore` and
   `hermes_cli.kanban_db`.
7. Use `PluginContext.register_auxiliary_task()` and
   `PluginContext.llm.complete_structured()` for the bounded heartbeat review.
8. Add integration tests proving silence by default, budget enforcement,
   cooldown enforcement, read-only sources, one managed schedule, clean
   shutdown, adapter delivery, transcript mirroring, and Main-agent next-turn
   awareness.

---

# Files Likely To Change

Core changes should remain generic:

```text
hermes_cli/plugins.py
gateway/run.py
gateway/notifications.py              # proposed shared delivery facade
cron/scheduler.py                     # likely refactor to shared facade
agent/memory_provider.py               # proposed generic observation hook
agent/memory_manager.py                # proposed provider fan-out
plugins/memory/honcho/__init__.py      # proposed assistant-peer observation mapping
tests/hermes_cli/test_plugins.py
tests/gateway/test_plugin_periodic_tasks.py
tests/gateway/test_notifications.py
```

Heartbeat plugin additions:

```text
plugins/heartbeat/plugin.yaml
plugins/heartbeat/__init__.py
plugins/heartbeat/config.py
plugins/heartbeat/scheduler.py
plugins/heartbeat/engine.py
plugins/heartbeat/context.py
plugins/heartbeat/delivery.py
plugins/heartbeat/inbox.py
plugins/heartbeat/event_log.py
plugins/heartbeat/sources/*
plugins/heartbeat/policies/*
tests/plugins/heartbeat/*
```

---

# Test Plan

1. **Plugin lifecycle:** register one periodic callback, assert the gateway host
   runs it once per due interval, prevents duplicate registration, isolates
   callback failure, and stops it on shutdown.
2. **Policy defaults:** assert disabled-by-default behavior, active-hour gates,
   cooldowns, daily budget limits, and no delivery when review returns silence.
3. **Memory source:** use a temporary `HERMES_HOME`, write `MEMORY.md` and
   `USER.md`, call the adapter, and assert bounded sanitized output without
   session history.
4. **Kanban source:** use a temporary SQLite board, create mixed-status tasks,
   call the adapter, and assert bounded read-only summaries with no state
   mutation.
5. **LLM review:** mock `PluginLlm.complete_structured()` and assert schema
   validation, timeouts, token limits, and failure isolation.
6. **Delivery:** reuse fake gateway adapters from
   `tests/gateway/test_kanban_notifier.py`; assert target routing, retry, and
   deduplication.
7. **Synthetic full-agent adapter, only if added:** extend
   `tests/cron/test_scheduler.py` patterns to verify unique session IDs,
   restricted toolsets, `skip_memory=True`, idle timeout, cleanup, and silent
   response handling.
8. **Main-agent continuity:** persist a surfaced finding, simulate notification
   delivery, then run a primary turn and assert the bounded finding is injected
   through `pre_llm_call`. Assert heartbeat and cron lanes do not receive the
   injection. For a known gateway session, assert the delivered assistant
   notification round-trips through `SessionStore.load_transcript()`.
9. **External-memory reinforcement:** publish a delivered finding through the
   proposed observation hook. Assert Honcho stores an assistant-peer message
   with the attention marker, unsupported providers remain no-op, raw adapter
   delivery alone does not claim a provider write, and tools-only Honcho mode
   does not replace the durable inbox guarantee.

---

# Discovery Exit Criteria

- [x] Agent invocation path identified
- [x] Scheduler insertion point identified
- [x] Memory retrieval path identified
- [x] Task retrieval path identified
- [x] Notification strategy identified
- [x] Configuration strategy identified
- [x] Hook behavior verified
- [x] LCM/context strategy identified
- [x] Risk assessment completed
- [x] Recommended implementation option selected

Discovery is complete. No heartbeat production code has been written.
