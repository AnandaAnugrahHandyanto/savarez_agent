# Clean-session kickoff (post M0–M7)

Use after roadmap phase or when resuming Hermes setup work.

```text
Load hermes-agent, hermes-dynamic-workflows, senior-production-hermes.
Target repo: /home/khall/.hermes/hermes-agent (or active worktree).
Read:
  docs/plans/roadmap-completion.md (in PR #26 worktree)
  /mnt/c/Users/khall/Documents/Obsidian Vault/topics/agentic/2026-06-09-hermes-setup-roadmap-m0-m8-completion.md
  ~/.hermes/profiles/auto-coder/docs-watcher-watermark.json

Re-ground: pwd, git worktree list, git status --short --branch, gh pr view 26 (if open).

Policies:
  DWF orchestration on auto-coder; Kanban dispatch frozen unless operator opts in.
  Coding: grok-composer-2.5-fast. No push/merge/gateway/cron/config without explicit approval.

Next work (pick one):
  A) PR #26 review / merge M1 fix to fork main
  B) M2c — port gate ladder into CLI (after merge plan approved)
  C) smart_routing: merge worktree slice OR disable smart_model_routing in config (approval)
  D) M8 exhaustive docs refresh (only if operator requests)
  E) Register M6 watcher as cron (approval)

Run scripts/setup_gate_ladder_audit.py with PYTHONPATH=<worktree> before any profile/gateway edits.
```