# Hermes setup roadmap — phase completion (M0–M8)

Worktree: `/home/khall/.hermes/.worktrees/profile-list-fast-alias-scan`  
PR: https://github.com/SollanSystems/hermes-agent/pull/26

## Definition of done (roadmap §487)

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Fast `hermes profile list` + regression tests | **Done** (worktree; PATH CLI after merge) |
| 2 | Docs facts in wiki + hashes | **Done** (M6 watermark + Obsidian index) |
| 3 | Setup gate ladder receipts | **Done** (M2a script + M2b receipt) |
| 4 | Routing/cost policy explicit | **Done** (M3 + Grok policy; runtime smart_routing still absent on main) |
| 5 | Archetypes + registry proposal | **Done** (M4 DWF) |
| 6 | Gateway/cron documented | **Done** (M5 + repair) |
| 7 | Docs watcher | **Done** (M6; cron not registered) |
| 8 | Hygiene loop | **Done** (M7) |

## M8

Explicitly **deferred** — `docs/plans/m8-docs-refresh-v2-decision.md`.

## Remaining operator gates (not blockers for “plan finished”)

- Merge/install M1 on default `hermes` PATH
- Optional: smart_routing merge or config disable
- Optional: M6 cron job
- Optional: M8 full docs v2

## Verification commands

```bash
PYTHONPATH=/home/khall/.hermes/.worktrees/profile-list-fast-alias-scan \
  /home/khall/.hermes/hermes-agent/venv/bin/python -m pytest \
  tests/hermes_cli/test_profiles.py -q

HERMES_HOME=~/.hermes/profiles/auto-coder \
  python /home/khall/.hermes/.worktrees/profile-list-fast-alias-scan/scripts/setup_gate_ladder_audit.py \
  --pythonpath /home/khall/.hermes/.worktrees/profile-list-fast-alias-scan \
  --hermes-home ~/.hermes/profiles/auto-coder
```