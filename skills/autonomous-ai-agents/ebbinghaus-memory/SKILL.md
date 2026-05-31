---
name: ebbinghaus-memory
description: "Use Ebbinghaus memory sleep, recall, and decay."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [memory, ebbinghaus, sleep, recall, forgetting]
    related_skills: [hermes-agent]
    plugin: plugins/memory/ebbinghaus
    tools: [ebbinghaus_memory]
---

# Ebbinghaus Memory Skill

Use this skill to operate the bundled Ebbinghaus memory plugin as an agent memory routine. It covers durable recall, rehearsal-based consolidation, and idle sleep cleanup.

This skill does not replace other memory providers. Use it when the active memory provider is `ebbinghaus` or when you are helping a user configure that provider.

## When to Use

- Use when the user asks about agent sleep, memory consolidation, Ebbinghaus forgetting, recall, rehearsal, decay, or pruning forgotten memories.
- Use when durable user preferences or operational facts should be stored through the local `ebbinghaus_memory` tool.
- Use when idle memory maintenance should run through `memory.sleep` and the bundled `plugins/memory/ebbinghaus` provider.
- Do not use for unrelated knowledge-base providers such as Hindsight, Supermemory, ByteRover, OpenViking, RetainDB, or Holographic memory unless the task compares providers.

## Prerequisites

- The memory provider is `ebbinghaus`.
- The `ebbinghaus_memory` tool is available from the active memory provider.
- For idle sleep, `memory.sleep.enabled` is true and `memory.sleep.idle_after_seconds` is greater than zero.
- Persistent state is stored by the plugin under `HERMES_HOME`, using the provider's configured SQLite database path.

## How to Run

Use `ebbinghaus_memory` directly when the user asks for explicit memory work.

For manual memory writes, call:

```json
{"action":"remember","content":"User prefers Japanese status updates.","tags":"user-preference,communication","salience":0.9}
```

For recall before answering from memory, call:

```json
{"action":"recall","query":"Japanese status updates","limit":5}
```

For consolidation, call:

```json
{"action":"rehearse","query":"Japanese status updates","limit":1}
```

For sleep maintenance, call:

```json
{"action":"sleep","prune":true,"rehearse_threshold":0.45,"forget_threshold":0.08,"salience_keep_threshold":0.7,"limit":200}
```

## Quick Reference

| Action | Use |
|---|---|
| `remember` | Store a durable fact with cue tags and salience. |
| `recall` | Retrieve matching memories and reinforce retrieval. |
| `rehearse` | Consolidate a known memory by id or query. |
| `decay` | Inspect low-retention traces and optionally prune. |
| `sleep` | Rehearse important low-retention traces and forget low-value traces. |
| `forget` | Delete one memory by `memory_id`. |
| `list` | Inspect stored memories. |
| `stats` | Inspect memory-store counts and retention summary. |

## Procedure

1. Check whether the task is about memory behavior, not ordinary file or session state.
2. If the answer depends on existing memory, call `ebbinghaus_memory` with `action="recall"` before relying on memory.
3. If the user gives a durable preference, fact, or operating constraint, call `action="remember"` with short tags and an appropriate salience value.
4. If a memory is important but retention is low, call `action="rehearse"` or include it in a sleep pass.
5. If the user asks for agent sleep or maintenance, call `action="sleep"` with the configured thresholds unless they specify different values.
6. If the user asks to remove a memory, prefer `action="forget"` for a known `memory_id`; use `action="decay"` with `prune=true` only for threshold-based cleanup.

## Pitfalls

- Do not treat `sleep` as a background thread. The built-in idle path is lazy and runs before the next turn after the idle threshold.
- Do not prune high-salience memories just because retention is low. Sleep should rehearse those memories instead.
- Do not assume a recalled memory is current truth. Use it as context, then verify live state when the fact can drift.
- Do not hardcode `~/.hermes` in instructions or code. The plugin is profile-aware through `HERMES_HOME`.
- Do not use this skill when `memory.provider` is set to another provider unless the user is switching to `ebbinghaus`.

## Verification

- `ebbinghaus_memory` appears in the active tool list.
- `{"action":"stats"}` returns a valid JSON object.
- `remember` followed by `recall` returns the stored content.
- A sleep pass returns `mode: "sleep_cycle"` with `rehearsed`, `forgotten`, and `pruned` arrays.
- Idle sleep is configured under `memory.sleep` if the user expects automatic agent sleep.
