# Active Task Workspace Resume Regression Audit - 2026-05-31

## Executive Summary

Hermes has durable session continuity after gateway restart, but it does not have a durable active-task/workspace model. The current restart recovery path can preserve the Discord thread/session transcript through `resume_pending`, and it can sometimes recover host-local background process PIDs through `~/.hermes/processes.json`. It does not persist the user's active goal, repo path, branch, in-progress command, latest runtime summary, or an explicit "safe to continue" recovery plan.

The observed failure is consistent with that model: after restart, Jenny was started from the systemd `WorkingDirectory` (`/home/jenny/.hermes/hermes-context-routing-deploy-20260530`) and the Codex app-server runtime used that process cwd. The prior Signal Room workspace (`/home/jenny/wt/agentic-video-channel-factory`) was present only in transcript/tool outputs, not in a first-class restart recovery record that could be restored before prompt construction.

## Exact Failure Mode

- Expected active task: Signal Room production generation/refill batch in `/home/jenny/wt/agentic-video-channel-factory` on branch `main`.
- Expected user-facing recovery: previous task, repo, branch, active/background process status, latest runtime/log path, safety state, exact next check.
- Actual recovery: a fresh interaction in `/home/jenny/.hermes/hermes-context-routing-deploy-20260530` on branch `hermes-context-routing-deploy-20260530`, followed by "no active code task".

This is not explained by Discord session routing alone. The same Discord thread can resume the transcript while still losing active workspace/task/process state.

## Files and Functions Inspected

- `gateway/run.py`
  - `_handle_message`
  - `_handle_message_with_agent`
  - `_run_agent`
  - `_schedule_resume_pending_sessions`
  - `_drain_active_agents`
  - `_interrupt_running_agents`
  - `_run_process_watcher`
  - startup process recovery and resume scheduling around lines 4073-4367
- `gateway/session.py`
  - `SessionEntry`
  - `SessionStore.get_or_create_session`
  - `mark_resume_pending`
  - `clear_resume_pending`
  - `suspend_recently_active`
  - `build_session_key`
- `tools/terminal_tool.py`
  - `terminal_tool(... background=True ...)`
  - notification metadata assignment for `notify_on_complete` and `watch_patterns`
- `tools/process_registry.py`
  - `ProcessSession`
  - `spawn_local`
  - `spawn_via_env`
  - `_write_checkpoint`
  - `recover_from_checkpoint`
  - `list_sessions`
- `agent/codex_runtime.py`
  - `run_codex_app_server_turn`
- `agent/transports/codex_app_server_session.py`
  - `CodexAppServerSession.__init__`
  - `ensure_started`
- `agent/agent_init.py`
  - `SubdirectoryHintTracker(working_dir=os.getenv("TERMINAL_CWD") or None)`
- Tests searched:
  - `tests/gateway/test_restart_resume_pending.py`
  - `tests/gateway/test_background_process_notifications.py`
  - `tests/tools/test_process_registry.py`
  - `tests/tools/test_notify_on_complete.py`
  - `tests/gateway/test_config_cwd_bridge.py`
  - `tests/agent/transports/test_codex_app_server_session.py`
  - `tests/cli/test_cwd_env_respect.py`

## Current Active-Task Persistence Model

No durable current-active-task record was found.

What exists:

- `SessionEntry.resume_pending`, `resume_reason`, and `last_resume_marked_at` in `gateway/session.py` persist a generic "restart/shutdown interrupted this session" marker in `sessions.json`.
- Transcript rows persist in `state.db`.
- `processes.json` persists background process metadata for `terminal(background=true)` processes.
- `_running_agents` and `_agent_cache` store live agent objects in memory only.

What is missing:

- No durable active goal/task summary.
- No durable active repo path or branch.
- No durable active command/checklist/next poll instruction.
- No durable link from a Discord thread session to a workspace preference.
- No durable "latest runtime summary/log path" field.
- No restart-time user-facing banner with repo/branch/process recovery status.

## Current Workspace/CWD Selection Model

Gateway bootstrap bridges `config.yaml terminal.cwd` to `TERMINAL_CWD` if explicitly configured. If no explicit cwd is configured, gateway falls back to home. Separately, the systemd unit has:

```text
WorkingDirectory=/home/jenny/.hermes/hermes-context-routing-deploy-20260530
```

The terminal tool uses `TERMINAL_CWD` as its default command cwd. For Codex app-server turns, `agent/codex_runtime.py` uses:

```python
cwd = getattr(agent, "session_cwd", None) or os.getcwd()
```

No inspected gateway path sets `agent.session_cwd` from a session/workspace record. Therefore, Codex app-server starts from `os.getcwd()`, which is the gateway process working directory. That explains why Jenny defaulted to the Hermes deployment checkout after restart.

Workspace context may appear in:

- transcript text
- prior tool outputs
- runtime footer cwd display
- `TERMINAL_CWD`
- systemd `WorkingDirectory`
- current process cwd

But there is no first-class workspace binding that overrides systemd cwd on resume.

## Current Long-Running Process Monitor Model

Long-running commands launched through `terminal(background=true)` use `tools.process_registry.ProcessRegistry`.

For local backend:

- `spawn_local()` creates a `ProcessSession` with `command`, `task_id`, `session_key`, `pid`, `cwd`.
- It starts a reader thread and writes `~/.hermes/processes.json`.
- Recovery probes host PIDs and recreates detached `ProcessSession` objects.

For non-local backends:

- `spawn_via_env()` stores sandbox PID/log/exit paths in local variables.
- Checkpointed `pid_scope` is `sandbox`.
- `recover_from_checkpoint()` intentionally skips non-host PIDs because the environment handle is gone.

Important checkpoint gap:

- `spawn_local()` writes the process checkpoint before `terminal_tool.py` later mutates `notify_on_complete`, `watcher_platform`, `watcher_chat_id`, `watcher_thread_id`, and `watcher_interval`.
- Unless another checkpoint write happens later, restart recovery can have stale notification metadata and fail to requeue watchers.

The live `~/.hermes/processes.json` inspected during this audit contained `[]`, so there was no process record to reattach for the Signal Room case.

## What Survives Restart vs. What Is Lost

Survives:

- session key to session id mapping in `~/.hermes/sessions/sessions.json`
- transcript messages in `~/.hermes/state.db`
- generic `resume_pending` markers in `sessions.json`
- host-local process PID/cwd/command metadata in `processes.json`, only if checkpointed and process survived
- restart failure counters in `.restart_failure_counts`

Lost:

- `_running_agents`
- `_agent_cache`
- live Codex app-server sessions/threads
- pending in-memory process watchers not flushed to checkpoint
- pending adapter `_pending_messages`
- active workspace if it was only implicit in tool cwd/transcript
- active task/goal/checklist if it was only in the model's working context
- stdout/stderr stream handles for detached recovered local processes

## Why Jenny Defaulted to the Hermes Deployment Checkout

Ranked evidence:

1. `systemctl --user cat hermes-gateway.service` shows `WorkingDirectory=/home/jenny/.hermes/hermes-context-routing-deploy-20260530`.
2. `agent/codex_runtime.py` starts Codex app-server with `getattr(agent, "session_cwd", None) or os.getcwd()`.
3. `gateway/run.py` constructs `AIAgent(...)` with session/thread metadata, but no `session_cwd` or workspace path.
4. `SessionEntry` serializes session/chat metadata and `resume_pending`, but no repo/workspace/branch.

The deployment checkout was not chosen because it was the user's Signal Room repo. It was the process cwd inherited from systemd.

## Specific Signal Room Evidence

Read-only checks against `/home/jenny/wt/agentic-video-channel-factory` found:

- Repo path: `/home/jenny/wt/agentic-video-channel-factory`
- Branch: `main`
- HEAD: `236c5f1`
- Git state:
  - `main...origin/main [ahead 21]`
  - modified `tests/test_signalroom_daily_queue_refill.py`
  - modified `tools/signalroom_daily_queue_refill.py`
  - untracked `runtime/`
- Active matching Signal Room generation/render/refill process: none found via `ps`.
- Current `~/.hermes/processes.json`: empty list.
- Recent runtime summaries:
  - `runtime/signalroom_daily_refill_20260531T045248Z.json`
  - `runtime/signalroom_daily_refill_20260531T045300Z.json`
  - `runtime/signalroom_daily_refill_20260531T045309Z.json`
- Latest dry-run summary inspected:
  - `runtime/signalroom_daily_refill_20260531T045309Z.json`
  - `dry_run: true`
  - `target_ready_count: 25`
  - `queue_writes.written: false`
  - `topic_backlog.path: config/signalroom_daily_topics.json`
  - `available_approved_unused_count: 24`
- Recent review packages:
  - `review-packages/signalroom-daily-topic-backlog-20260531/app-store-fake-renewal-receipt`
  - `review-packages/signalroom-daily-topic-backlog-20260531/medicare-card-replacement-call`
  - `review-packages/signalroom-daily-topic-backlog-20260531/airport-wifi-login-portal-trap`

State evidence:

- `sessions.json` entry for `Video Channel - Part 28` was current at audit time:
  - session key `agent:main:discord:thread:1510128165974970499:1510128165974970499`
  - session id `20260531_095803_e6ddd7ac`
  - `resume_pending: false`
- `state.db` transcript for that session includes a later manual recovery response that did the correct read-only Signal Room recovery. That is user-driven recovery, not automatic restart restoration.

## Existing Tests and Gaps

Existing coverage:

- `tests/gateway/test_restart_resume_pending.py` covers `resume_pending`, restart note injection, drain-time marking, startup scheduling, and stuck-loop escalation.
- `tests/tools/test_process_registry.py` covers checkpoint recovery and watcher requeueing when checkpoint entries already contain watcher metadata.
- `tests/tools/test_notify_on_complete.py` covers `notify_on_complete` field persistence and recovery when metadata is explicitly present.
- `tests/gateway/test_background_process_notifications.py` covers watcher notification routing.
- `tests/gateway/test_config_cwd_bridge.py` and `tests/cli/test_cwd_env_respect.py` cover `TERMINAL_CWD` bridging.
- `tests/agent/transports/test_codex_app_server_session.py` covers Codex app-server `thread/start` cwd passing.

Gaps:

- No test for durable active task record containing repo path, branch, command, status, and log path.
- No test for same Discord thread restoring workspace before prompt construction.
- No test that cwd selection prefers active-task workspace over systemd/gateway cwd.
- No test that missing active-task record yields an explicit "interrupted/unknown" banner.
- No test proving checkpoint is rewritten after terminal notification metadata is assigned.
- No test for detached process recovery surfacing last known command/log path when stdout cannot be reattached.

Added during this audit:

- `tests/gateway/test_active_task_workspace_resume_audit.py`
  - `xfail` spec for durable active task/workspace snapshot.
  - `xfail` spec for a gateway workspace resolver.
  - `xfail` spec for checkpoint flush after watcher metadata mutations.

These are non-invasive regression specs only; they do not change runtime behavior.

## Likely Root Causes

1. High confidence: no durable active-task/workspace model.
   - `SessionEntry` persists session identity and `resume_pending`, not active repo/branch/command/goal.

2. High confidence: Codex app-server cwd falls back to process cwd.
   - `agent.session_cwd` is not set by gateway; Codex app-server uses `os.getcwd()`.

3. Medium-high confidence: restart resume banner is too generic and model-only.
   - Existing note says the previous turn was interrupted and asks the model to inspect history. It does not provide structured repo/process/log recovery facts.

4. Medium confidence: process watcher checkpoint metadata can be stale.
   - Checkpoint write happens before notification metadata assignment in `terminal_tool.py`.

5. Medium confidence: startup auto-resume is adapter-dependent and opaque.
   - `_schedule_resume_pending_sessions()` synthesizes an empty internal message after adapters start. If no `resume_pending` marker remains, or if it is cleared by a later successful/failed path, there is no banner.

## Proposed Fix Sequence

1. Add a durable `active_tasks` or `session_active_task` store keyed by `session_key`.
   - Fields: `session_key`, `session_id`, `platform`, `chat_id`, `thread_id`, `repo_path`, `branch`, `command`, `status`, `pid/process_session_id`, `latest_log_path`, `last_summary_path`, `updated_at`, `resume_reason`.

2. Add a single workspace resolver before agent construction.
   - Priority: fresh active-task workspace, explicit per-session workspace binding, `TERMINAL_CWD`, systemd/process cwd.
   - Set both `agent.session_cwd` and any app-server/session transport cwd.

3. Persist active-task snapshots when terminal/process tools start long-running work.
   - Background terminal command should write active-task metadata after cwd/command/session_key are known.
   - Foreground long-running loops should checkpoint polling intent if the model says it will continue polling.

4. Fix process checkpoint metadata flush.
   - After `notify_on_complete`/watcher metadata is assigned, call a registry method that updates the session and writes `processes.json`.

5. Add restart recovery banner before prompt construction.
   - Include previous task, workspace, branch, command, process status, latest log/summary path, safety state, and exact next check.
   - If only `resume_pending` exists and no active-task record exists, say the task was interrupted but active workspace/process is unknown.

6. Add operational status command support.
   - `/status` or `/recover` should surface active task records and detached process records for the current thread.

## Proposed Regression Tests Before Behavior Changes

- Active task record roundtrips repo path, branch, command, status, process id, and log path using a temp store.
- Gateway restart reloads the active task record for the same Discord thread/session key.
- Cwd resolver prefers active-task workspace over systemd/gateway cwd.
- Missing active-task record plus `resume_pending` produces an explicit interrupted/unknown banner.
- Background process checkpoint is updated after notification metadata is attached.
- Detached recovered process reports unknown/detached stdout with last known command/cwd/log path.
- Startup auto-resume injects structured recovery facts before model prompt construction.

## Operational Recovery Commands for the Signal Room Batch

Read-only status checks:

```bash
cd /home/jenny/wt/agentic-video-channel-factory
git status --short --branch
git rev-parse --short HEAD
ps -eo pid=,ppid=,stat=,etime=,command= | awk '/signalroom|signal_room|daily_queue_refill|render_signalroom|agentic-video-channel-factory|hyperframes|ffmpeg|python .*tools\\// && $0 !~ /awk/ {print}'
find runtime -maxdepth 1 -type f -name 'signalroom_daily_refill_*.json' -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' | sort | tail -12
python -m json.tool runtime/signalroom_daily_refill_20260531T045309Z.json | sed -n '1,160p'
```

Safe interpretation at audit time:

- No active Signal Room process was visible.
- The latest inspected runtime summary was a dry run, not an executing batch.
- The next safe recovery check is to inspect `config/signalroom_daily_topics.json` and the latest `runtime/signalroom_daily_refill_*.json` before launching any new production run.

## Non-Goals and Safety Notes

- Did not modify production `state.db`, `sessions.json`, memories, task records, process state, `.env`, `config.yaml`, credentials, or browser profiles.
- Did not kill or restart any process.
- Did not send Discord messages.
- Did not call live APIs.
- Did not restart Hermes.
- Added tests are `xfail` audit specs only.
