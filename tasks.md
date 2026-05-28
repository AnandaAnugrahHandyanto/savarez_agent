# Hermes Agent Task Cockpit

This file is the human cockpit for repo-local Agent Project Workspace tasks. The executable queue lives in `.hermes/tasks.yaml`.

## HERMES-G01: Repo-local agent orchestration

outcome: Future agents can claim bounded Hermes Agent repository tasks, receive handoffs, avoid overlapping edits, validate evidence, and commit one task at a time.

deliverables: `.hermes/` project contract, task schema, machine queue, worker/reviewer prompts, claim/finish scripts, and developer documentation.

- [x] HERMES-T001: Implement repo-local Agent Project Workspace workflow | status: done | done: 2026-05-28 | evidence: `.hermes/project.md`, `.hermes/tasks.yaml`, `scripts/next_task.py`, `scripts/finish_task.py`, `.gitignore`, `python3 scripts/finish_task.py --validate-only HERMES-T001`
