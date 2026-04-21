---
name: memory-offload
description: Offload an overgrown MEMORY.md into an archive snapshot and rebuild a compact live memory that still matches the memory tool state.
---

# Memory Offload

Use when long-term memory is full, bloated, duplicated, or blocking new memory writes.

## Goal

Preserve recoverable history while shrinking the injected live memory to only high-value durable facts.

## When to use

- `memory` tool says the store is full or near full
- `MEMORY.md` has grown into a historical log instead of a compact working memory
- many entries are duplicates, superseded, or too detailed for every-session injection
- the user asks to offload, prune, compact, or archive memory

## Core lesson

There are two surfaces to keep in sync:
1. file surface: `workspace/MEMORY.md`
2. injected memory-tool surface managed by the `memory` tool

Updating only the file is not enough. If the memory tool still holds the old blob, capacity will stay blocked.

## Procedure

1. Read current `workspace/MEMORY.md`.
2. Save a full archive snapshot first under `workspace/memory/archive/`.
   - Example: `workspace/memory/archive/MEMORY-full-YYYY-MM-DD-pre-offload.md`
3. Build a compact replacement that keeps only:
   - user identity
   - current default operating stance
   - highest-value preferences
   - stable workflow rules
   - current environment/setup facts
   - pointer to the archive file
4. Write the compact version back to `workspace/MEMORY.md`.
5. Verify the file size actually dropped.
   - Example: `wc -c workspace/MEMORY.md <archive-file>`
6. Sync the memory-tool surface using `memory(action='replace', target='memory', old_text='# MEMORY.md — Long-Term Memory', content='<new compact memory>')`.
7. Confirm memory capacity is available again.

## Compression rules

Keep:
- stable user preferences that prevent future correction
- stable environment facts that are expensive to rediscover
- current strategic stance/routing rules
- one canonical fact per topic

Offload/archive:
- old hardware deliberations after a final decision exists
- repeated variants of the same preference
- detailed project histories better kept in daily notes or archive
- completed-work logs and stale open loops
- verbose duplicates where one compact line is enough

## Good compact-memory shape

- Key Facts
- Preferences
- Stable Workflow Rules
- Environment
- Archive pointer

Aim for a small file that can fit comfortably in injected memory, not a comprehensive diary.

## Pitfalls

- Do not overwrite live memory before saving an archive snapshot.
- Do not assume the `memory` tool auto-reads the file you edited.
- Do not keep multiple synonymous entries when one line will do.
- Do not archive away still-active routing or delivery rules.
- In some environments, scripted file operations may run with a different working directory than the main workspace. If a code-execution helper cannot find `workspace/MEMORY.md`, fall back to `terminal`, `read_file`, and `write_file` with verified paths instead of assuming relative paths will resolve.
- The first `memory(action='replace', ...)` may still exceed capacity if the compact memory is a bit too verbose or if another stale entry is still present. Shorten the replacement further, then remove any stray outdated entry if needed and retry.

## Verification

Success means all of these are true:
- archive snapshot exists
- `workspace/MEMORY.md` is much smaller than before
- `memory(action='replace', ...)` succeeds
- new memory writes are unblocked

## Example outcome

- archive: `workspace/memory/archive/MEMORY-full-2026-04-13-pre-offload.md`
- live memory reduced from ~55 KB to ~2 KB
- memory tool usage dropped below capacity and accepted the replacement
