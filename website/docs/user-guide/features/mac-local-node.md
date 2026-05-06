---
title: Mac Local Node
description: Compact workstation tool surface for controlling a trusted local Mac from a remote Hermes/Tolki brain.
---

# Mac Local Node

The Mac local node is a planned workstation satellite for setups where Hermes runs
remotely (for example on a VPS) but needs Claude Code-like hands on a trusted
local Mac.

The design goal is **high local autonomy with a small prompt footprint**. The Mac
node exposes workstation primitives only; SaaS/account connectors stay in Hermes
or separate MCP servers.

## Six-tool surface

Expose one compact tool per local capability family:

| Tool | Actions | Purpose |
| --- | --- | --- |
| `mac_system` | `status` | Online/offline state, heartbeat, trusted roots, policy mode, and capability map. This replaces separate `mac_status` and `mac_capabilities`. |
| `mac_fs` | `read`, `search`, `write`, `patch` | Token-efficient file operations with pagination, truncation, path policy, and secret denial. |
| `mac_terminal` | `run`, `start`, `poll`, `wait`, `kill`, `input`, `exec_code` | Foreground shell, managed background processes, stdin, and short local code execution. This replaces separate process and `mac_execute_code` tools. |
| `mac_project_context` | `summarize` | One compact preflight summary for a project/repo before edits or tests. |
| `mac_ui` | `screenshot`, `open`, `clipboard`, `osascript` | Mac-native UI primitives. Clipboard reads and AppleScript/JXA are policy-gated. |
| `mac_agent` | `spawn`, `status`, `logs`, `kill` | Local worker orchestration for Codex, Claude, OpenCode, or Pi when installed. |

Do **not** add standalone `mac_git_status`, `mac_git_diff`, or
`mac_git_commit`; git should use `mac_terminal`. Direct `mac_browser` is deferred
for V1. Browser work can initially go through `mac_terminal` scripts,
`mac_ui.screenshot/open`, or a `mac_agent` worker.

## Why keep `mac_fs` if terminal can read and edit files?

Terminal is the universal fallback, but file tools are better for agents:

- `read` can return line ranges, line numbers, and truncation hints instead of
  dumping an entire file into context.
- `search` can filter noisy directories and return structured matches instead of
  raw `rg` output.
- `write` can validate roots and overwrite policy before touching a file.
- `patch` returns diffs and is safer than ad hoc `sed` or shell heredocs.

This matches the ergonomics of local coding agents such as OpenCode and Pi,
which keep read/search/edit/write primitives alongside bash.

## Claude Code-like policy

The Mac local node should be flexible inside trusted roots. A user who points the
agent at a project expects it to read, edit, run tests, start dev servers, and
make local commits without repeated approval prompts.

Trusted roots include user-configured personal/project directories and the work
scope mounted as `/work` (for Rafael/Pazzi this represents `paggo-project`).

Allowed by default inside trusted roots:

- `mac_fs.read/search/write/patch`, except explicit secret/auth paths.
- local test/build/lint/dev commands.
- managed background processes started by the agent.
- local git read commands and local commits.
- local worker agents in scoped workdirs.

Ask or deny for real risk:

- external/publishing actions: `git push`, PR creation/comments, deploys,
  releases, package publishing, Slack/email/Linear writes.
- destructive actions: broad deletes, `git reset --hard`, `git clean -fdx`,
  force push, Docker volume deletion.
- global/system changes: `sudo`, broad `chmod/chown`, system settings, global
  installs, Homebrew mutation.
- secrets/auth material: `.env` unless explicitly requested, SSH keys,
  Keychain, browser cookies/session stores, and auth caches/tokens.
- paths outside trusted roots.

## Structured errors

Mac tools should remain discoverable even when the Mac is offline. `mac_system.status`
still returns the stable capability contract, trusted roots, denied roots, policy
mode, and supported error codes with `online: false`. Other actions return
structured errors instead of disappearing at runtime:

- `MAC_OFFLINE`
- `ACTION_DENIED`
- `APPROVAL_REQUIRED`
- `PATH_DENIED`
- `SECRET_DENIED`
- `TIMEOUT`
- `PROCESS_NOT_FOUND`

## Rollout phases

1. Schema and policy foundation: six-tool action surface, `/work` trusted scope,
   structured offline errors, and docs.
2. `mac_fs` relay implementation with path/secret policy.
3. `mac_terminal` relay implementation with managed processes and `exec_code`.
4. `mac_project_context` and `mac_ui` primitives.
5. `mac_agent` worker orchestration.
6. Optional direct browser harness if UI/browser workflows become common enough
   to justify a dedicated `mac_browser` tool.
