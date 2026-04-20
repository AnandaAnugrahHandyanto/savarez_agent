# Claude Code Project Context

This repository uses a shared local Autorunne workspace under `.autorunne/`.

## Read order before multi-step work
1. `.autorunne/README.md`
2. `.autorunne/NEXT_ACTION.md`
3. `.autorunne/TASKS.md`
4. `.autorunne/DECISIONS.md`
5. `.autorunne/PROJECT_CONTEXT.md`
6. `.autorunne/snapshots/latest.json`
7. `AGENTS.md`

## Working rule
- Treat `.autorunne/` as the project-state memory layer shared with Hermes and Codex.
- After meaningful verified progress, update `TASKS.md`, `SESSION_LOG.md`, and `NEXT_ACTION.md` so the next session can resume quickly.
- Keep `.autorunne/` local-first and out of public release output.
