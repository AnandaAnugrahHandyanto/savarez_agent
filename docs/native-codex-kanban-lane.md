# Native Codex Kanban Lane

This note describes the native Codex CLI lane added for Hermes Kanban.

## Active path

```text
Kanban card assigned to codex
  -> dispatcher claims the task and resolves the workspace
  -> dispatcher directly spawns python -m hermes_cli.codex_worker
  -> codex_worker runs native `codex exec -` in the assigned workspace
  -> worker streams logs and emits heartbeats
  -> worker blocks review-required or codex-failed with metadata
  -> reviewer/verifier inspects evidence and marks done or unblocks for follow-up
```

## Why this lane exists

The default Kanban worker lane is a Hermes profile process. That remains the right default for Hermes-native workers, but external coding CLIs have a different shape. Without a native lane, operators typically need one of these workarounds:

- a Hermes profile whose only job is to call Codex;
- a local bridge script outside the normal dispatcher contract;
- a manually supervised tmux Codex session.

Those are useful as fallback/recovery tools, but they are more operationally complex than a queueable card with a direct worker lane. The native Codex lane keeps the Kanban lifecycle in Hermes while letting Codex own implementation inside the task workspace.

## Review boundary

Codex is an implementation worker, not the final authority. Code-changing success blocks as `review-required:`. A reviewer should inspect:

- task state and run history;
- worker log;
- Codex final receipt;
- run metadata, including git status / changed files / diff summary;
- required gates from the card;
- any residual risk or skipped verification.

Only after that review should the card be marked `done`.

## Fallback paths

- Use interactive tmux Codex for live steering, auth/browser flows, or recovery from a failed non-interactive lane.
- Use a Hermes profile lane when the worker needs Hermes-native tools and agent-loop behavior more than native Codex execution.
- Use the Codex app-server runtime when the desired behavior is “Hermes profile worker running on Codex runtime,” not “Kanban card directly launches Codex CLI.”

## Upstream design note

This implementation intentionally uses one canonical hardcoded assignee (`codex`) as a concrete paved lane. If Hermes later grows a generic external-worker registry, this lane can become the first registered external CLI worker rather than a dispatcher special case.
