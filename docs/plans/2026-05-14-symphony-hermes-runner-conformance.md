# Symphony Hermes Runner Conformance Checklist

**Date:** 2026-05-14

**Scope:** Checklist for the current Hermes-first `hermes symphony` MVP against OpenAI Symphony SPEC Section 17/18 style requirements. The upstream SPEC is treated as the conceptual source for a Symphony-compatible orchestrator; this implementation deliberately extends the runner model with `agent.runner: hermes`.

**Status labels:**

- `implemented`: present in current code and covered by targeted unit tests or direct implementation.
- `extension`: intentional Hermes-specific behavior that diverges from Codex/app-server assumptions.
- `deferred`: planned but not complete in the current MVP.
- `not applicable`: upstream requirement does not apply to the Hermes runner MVP.

## Section 17-style implementation/conformance requirements

- Workflow file with YAML front matter and Markdown prompt body
  - Status: `implemented`
  - Evidence: `symphony/workflow.py` loads optional front matter and returns config plus prompt template.
  - Notes: CLI-level `validate` is still placeholder, but loader behavior is implemented.

- Default workflow path resolution to `./WORKFLOW.md`
  - Status: `implemented`
  - Evidence: `resolve_workflow_path()` resolves explicit paths or current-directory `WORKFLOW.md`.

- Typed config view with defaults
  - Status: `implemented`
  - Evidence: `symphony/config.py` provides defaults for polling, agent, Hermes runner, workspace, tracker, and Codex placeholder sections.

- Runner selection through workflow config
  - Status: `extension`
  - Evidence: `agent.runner: hermes` is the default and supported runner value.
  - Notes: Upstream Codex/app-server runner assumptions are not the default path.

- Codex runner compatibility path
  - Status: `deferred`
  - Evidence: `agent.runner: codex` is recognized only when `codex.command` is configured.
  - Notes: No full Codex app-server protocol client is implemented.

- Linear tracker candidate issue normalization
  - Status: `implemented`
  - Evidence: `symphony/tracker.py` includes GraphQL query shapes and normalizes issue payloads into `Issue` dataclasses.
  - Notes: Injectable transport is tested. Production HTTP transport and auth wiring are not the focus of this task.

- Linear API key handling through environment variable
  - Status: `implemented`
  - Evidence: `tracker.api_key: $LINEAR_API_KEY` style expansion exists in config loading.
  - Notes: Committed docs and examples use `$LINEAR_API_KEY` only; no secrets are stored.

- Issue dependency/blocker awareness
  - Status: `implemented`
  - Evidence: Linear relation payload normalization extracts blocker IDs; dispatch helper skips issues with non-terminal blockers.

- Deterministic dispatch ordering
  - Status: `implemented`
  - Evidence: dispatch helper sorts by priority presence/value, creation time, and issue identifier.

- Active and terminal state reconciliation
  - Status: `implemented`
  - Evidence: `reconcile_running_issue()` handles terminal cleanup, non-active stop, and active update paths.
  - Notes: This is an MVP helper, not yet a durable daemon loop.

- In-memory claims/running state
  - Status: `implemented`
  - Evidence: `OrchestratorState.running` and `RunningIssue` model current ownership.
  - Notes: Durable claim recovery and full service restart semantics remain deferred.

- Retry scheduling and backoff
  - Status: `implemented`
  - Evidence: `schedule_retry()` maps completed turns to short continuation retry and failures to exponential backoff capped by `max_retry_backoff_ms`.

- Dynamic workflow reload without crashing on invalid config
  - Status: `implemented`
  - Evidence: `symphony/reload.py` and tests cover mtime-based reload behavior and last-known-good retention.
  - Notes: Applied at helper level; full daemon integration is deferred.

- Operator state snapshot
  - Status: `implemented`
  - Evidence: `build_state_snapshot()` emits counts, running rows, retrying rows, totals, latest errors, events, and evidence directories.

- HTTP status/API server
  - Status: `deferred`
  - Evidence: Design reserves endpoints such as `/api/v1/state`; no production server is present in the current MVP.

- Long-running service supervision
  - Status: `deferred`
  - Notes: CLI `run` currently returns `not_implemented`; daemon lifecycle, process supervision, cancellation, and graceful shutdown are future work.

- CLI command surface
  - Status: `implemented`
  - Evidence: `hermes symphony validate|run|state` parser and command wiring exist.
  - Notes: Subcommands are placeholders until validation/execution/state are fully connected.

## Section 18-style runner/safety/evidence requirements

- Hermes runner as a first-class runner backend
  - Status: `extension`
  - Evidence: `HermesRunner` implements subprocess execution for `agent.runner: hermes`.
  - Notes: This is the central extension over Codex-specific runner requirements.

- Subprocess runner mode
  - Status: `implemented`
  - Evidence: `HermesRunner.run_turn()` launches Hermes with `cwd=workspace.path`, captures output, and maps result statuses.

- In-process runner mode
  - Status: `deferred`
  - Evidence: `hermes.mode: in_process` raises `unsupported_runner_mode`.
  - Notes: Deferred until cwd/tool scoping and Hermes global state isolation are hardened.

- Shell-injection resistance for runner command/prompt
  - Status: `implemented`
  - Evidence: command is split to an argv array and invoked with `shell=False`; prompt is passed as one argument.

- Workspace root containment
  - Status: `implemented`
  - Evidence: `workspace_path()` sanitizes issue identifiers and verifies the resolved workspace remains below the resolved root.

- Per-issue workspace creation/reuse
  - Status: `implemented`
  - Evidence: `prepare_workspace()` creates a deterministic issue workspace and evidence directory.
  - Notes: Full Git worktree/clone lifecycle hooks are only helper-level today.

- Lifecycle hooks
  - Status: `implemented`
  - Evidence: `run_hook()` supports fatal defaults for `after_create` and `before_run`, best-effort defaults for `after_run` and `before_remove`.
  - Notes: Hook config parsing/orchestrator integration is deferred.

- Evidence directory creation
  - Status: `implemented`
  - Evidence: current path is `<issue workspace>/.symphony/evidence/`.

- Evidence path exposed to runner
  - Status: `implemented`
  - Evidence: subprocess environment injects `SYMPHONY_EVIDENCE_DIR`; prompt prelude includes the evidence directory.

- Rich runner environment variables for issue/workspace metadata
  - Status: `deferred`
  - Evidence: design reserves variables such as `SYMPHONY_ISSUE_ID`, `SYMPHONY_ISSUE_IDENTIFIER`, `SYMPHONY_ISSUE_URL`, `SYMPHONY_WORKSPACE`, and `SYMPHONY_ATTEMPT`.
  - Notes: Current implementation injects only `SYMPHONY_EVIDENCE_DIR`.

- Screenshot workflow
  - Status: `extension`
  - Evidence: docs and sample workflow instruct Hermes agents to save UI evidence under `SYMPHONY_EVIDENCE_DIR`.
  - Notes: Core Symphony does not upload screenshots; project workflow decides PR attachment or commit policy.

- Artifact upload/publishing
  - Status: `deferred`
  - Notes: Local evidence paths are exposed; GitHub/Linear upload integrations are not implemented.

- Secret minimization in runner environment
  - Status: `implemented`
  - Evidence: runner copies only an allowlist of base environment keys and adds `SYMPHONY_EVIDENCE_DIR`.

- Secret redaction in events/state
  - Status: `implemented`
  - Evidence: observability helpers redact common API key/token/secret/password fields and patterns.

- Runner result status mapping
  - Status: `implemented`
  - Evidence: return code `0` maps to `turn_completed`; non-zero and OS errors map to `turn_failed`; timeout maps to `turn_timeout`.

- Structured token accounting and Codex app-server telemetry
  - Status: `not applicable`
  - Notes: The Hermes subprocess MVP does not implement Codex app-server telemetry. Future Hermes-native telemetry can be added through runner callbacks or event capture.

- Production multi-agent daemon guarantees
  - Status: `deferred`
  - Notes: Concurrency config and state helpers exist, but durable scheduling, process supervision, and operator controls are not production-complete.

## Current MVP summary

- Implemented and tested at unit/helper level: workflow loading, config defaults/validation, prompt rendering, workspace containment, Linear payload normalization, Hermes subprocess runner, retry/reconcile helpers, reload helpers, observability snapshots.
- Hermes-specific extension: `agent.runner: hermes` with `hermes.mode: subprocess` as the safe default.
- Deferred: top-level CLI validation/run/state integration, long-running daemon, HTTP API, Codex runner, full issue metadata environment injection, evidence publishing, production supervision.
