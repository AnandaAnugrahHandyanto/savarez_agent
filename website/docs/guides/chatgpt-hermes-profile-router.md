---
sidebar_position: 7
title: "ChatGPT Hermes Profile Router"
description: "Security and setup notes for using ChatGPT as the controller for Hermes profile-router MCP tools without Hermes model calls"
---

# ChatGPT Hermes Profile Router

The ChatGPT ↔ Hermes Profile Router is a strict, no-model MCP surface for letting ChatGPT operate selected Hermes profiles while Hermes stays the runtime for metadata, policy, context, filesystem reads, and future gated local actions.

Current status: **developer preview / local stdio only**. Do not expose it on a public HTTP endpoint until the auth, origin, logging, configuration UX, and approval decisions below are complete.

## No-model contract

ChatGPT is the only LLM/controller. Profile-router tool execution must not call:

- `hermes chat` or the Hermes profile agent loop
- `run_conversation`
- `delegate_task`
- Codex, Claude, Gemini, OpenAI, or other AI/model CLIs
- scheduled future model work unless a future tool is explicitly designed and approved for that cost class

Every router tool has explicit model/cost metadata. The default public MCP surface is limited to tools with `cost_class: no_model` and `llm_calls: 0`.

## Public MCP surface today

Run the local stdio server with:

```bash
hermes mcp serve --profile-router
```

The public `--profile-router` server registers only these tools:

- `profiles_list`
- `profile_get`
- `profile_health`
- `profile_context_get`
- `workspace_open`
- `workspace_instructions_get`
- `workspace_context_status`
- `workspace_get`
- `workspace_close`
- `file_read`
- `file_search`

The server intentionally does **not** register conversation messaging, `file_patch`, `file_write`, `workspace_diff`, `terminal_run`, cron, deploy, Git push/merge, or agent-loop execution tools on the public MCP surface.

## Required flow for ChatGPT

1. Call `profiles_list` and choose a fully qualified profile ref such as `local:business-features`.
2. Call `profile_context_get(profile_ref)` before operating as that profile.
3. Call `workspace_open(profile_ref, root)` for an explicitly allowed root.
4. Call `workspace_instructions_get(workspace_id)` and keep the returned context token/state in the conversation.
5. Use `file_read` and `file_search` for bounded, read-only inspection.
6. Call `workspace_context_status(workspace_id)` before any future write or terminal-capable path.
7. Call `workspace_close(workspace_id)` when done so the server-side workspace registry entry is removed.

Custom GPT instructions can remind ChatGPT to follow this flow, but they are not the security boundary. The router enforces context hydration server-side before powerful direct tools and fails closed when context is missing or stale.

## Policy configuration shape

The router is deny-by-default. Missing `profile_router` config exposes no profiles and grants no filesystem, terminal, messaging, cron, deploy, or model-consuming capability.

A minimal read-only local profile policy looks like:

```yaml
profile_router:
  hosts:
    local:
      enabled: true
      allowed_roots:
        - /Users/you/projects
  profiles:
    "local:business-features":
      enabled: true
      allowed_tool_groups:
        - profile_router
      allowed_roots:
        - /Users/you/projects/my-safe-worktree
      filesystem:
        read: true
        write: false
      terminal:
        enabled: false
      messaging:
        enabled: false
      cron:
        enabled: false
      git:
        allow_push: false
        protected_branches:
          - main
          - master
          - develop
      deploy:
        enabled: false
      model_tools:
        allow_model_tools: false
        allowed_cost_classes:
          - no_model
```

`allowed_roots` are host-local absolute paths. Profile roots must stay inside the corresponding host `allowed_roots`; symlink escapes and secret paths are rejected.

## Context and file safety

Context hydration returns bounded, sanitized context for the selected profile/workspace, including profile policy and project instruction files such as `SOUL.md`, `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, and `DESIGN.md` when present.

Sensitive files are never context or read targets. The denylist includes:

- `.env` and `.env.*`
- `auth.json`
- `.ssh`
- `mcp_tokens` / `mcp_tokens.json`
- `.hermes/*` local plan/state artifacts
- `funciones.txt` content

`funciones.txt` is local deployment/project metadata. Router context may report that project-local deployment metadata exists and must be kept out of PRs, but it must not expose the file contents.

## Direct-only tools that remain non-public

Some direct/internal wrappers exist for focused tests and staged implementation, but are not registered by `hermes mcp serve --profile-router`:

- `file_patch`
- `file_write`
- `workspace_diff`
- `terminal_run`

These tools require fresh workspace context first. `terminal_run` also requires explicit `terminal.enabled` plus `terminal.execution` allowlist policy, uses no-shell sanitized subprocess execution, blocks model/destructive/protected-Git/deploy command patterns, bounds output, and redacts workspace roots. Keep these tools non-public until public exposure is reviewed.

## Blockers before public HTTP / ChatGPT connector exposure

Do not put the profile router behind a public HTTP endpoint or ChatGPT connector until these decisions are complete:

- authenticated HTTP or OAuth-compatible serving mode
- token storage, rotation, expiry, revocation, and log redaction
- allowed origins / private network exposure policy
- audit logging that records profile ref, workspace id, tool name, outcome, and `llm_calls=0` without raw secrets or host roots
- configuration UX for explicit `profile_router` policy entries, instead of relying on hand-edited YAML
- policy for direct-only write/diff/terminal tools and whether they remain private, require approvals, or stay disabled
- Mac broker/SSH routing design that keeps Mac secrets, sessions, `.env`, and `auth.json` on the Mac
- security review of filesystem containment, terminal command classification, public tool registration, and context-staleness enforcement
- explicit Arturo approval before pushing/opening a public PR, deploying, or exposing the endpoint

Until then, treat the feature as a local developer-preview MCP server for no-model profile metadata, context hydration, and read-only workspace inspection.
