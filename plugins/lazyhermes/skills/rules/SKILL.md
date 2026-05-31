---
name: rules
description: Read and apply repo-local Hermes guidance files before changing code.
---

# LazyHermes Rules

Before editing, inspect the nearest relevant guidance files such as
`AGENTS.md`, `CLAUDE.md`, `HERMES.md`, `README.md`, and repo-local handoff
documents when they exist.

Apply guidance in this order:

1. Current user instruction.
2. Repo-local guidance closest to the files being changed.
3. Existing code style and test patterns.
4. LazyHermes workflow defaults.

Never revert unrelated user work. If guidance conflicts, follow the more
specific current instruction and call out the conflict.
