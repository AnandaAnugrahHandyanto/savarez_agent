# Project State: Understand-Anything → Flywheel Integration

> **Created:** 2026-05-30
> **Strategy doc:** `.plans/ua-incorporation-strategy.md`
> **Review doc:** `understand-anything-to-flywheel-review.md`

## Current Phase

**Phase 1: Foundation** — PENDING
- All deliverables defined in strategy doc, none yet implemented
- Phase 2 plan ready for approval

## Deliverable Status

| Phase | Deliverable | File Path | Status |
|---|---|---|---|
| 1 | scan_project.py | `scripts/code-scan/scan_project.py` | ⬜ Not started |
| 1 | language_registry.py | `scripts/code-scan/language_registry.py` | ⬜ Not started |
| 1 | graph_schema.py | `scripts/code-scan/graph_schema.py` | ⬜ Not started |
| 1 | .hermesignore | `.hermesignore` | ⬜ Not started |
| 2 | extract_imports.py | `scripts/code-scan/extract_imports.py` | ⬜ Not started |
| 2 | code-scan SKILL.md | `skills/code-analysis/code-scan/SKILL.md` | ⬜ Not started |
| 2 | validation-gate SKILL.md | `skills/code-analysis/validation-gate/SKILL.md` | ⬜ Not started |
| 2 | requesting-code-review integration | `skills/software-development/requesting-code-review/` | ⬜ Not started |
| 3 | fingerprints.json | `.hermes/code-state/fingerprints.json` | ⬜ Not started |
| 4 | tree-sitter, cross-batch, neighbor maps | — | ⬜ Deferred |

## Dependencies / Prereqs

- Phase 1 must complete before Phase 2 can begin
- Phase 2 plan (this file) must be approved before execution
- No Understand-Anything repo currently available locally for direct comparison
- Existing dirty files (`tools/skills_sync.py`, `tests/tools/test_skills_sync.py`) are unrelated — do not modify

## Reference Repos

| Repo | Location | Purpose |
|---|---|---|
| hermes-agent | `hermes-agent/` | Main source tree (reference) |
| hermes-workspace | `hermes-workspace/` | Workspace variant (reference) |
| mission-control | `mission-control/` | Deprecated (reference only) |
| cass_memory_system | `cass_memory_system/` | Memory system (reference) |

## Notes

- Documentation cleanup completed 2026-05-30: path references corrected, cross-references added
- Phase 1 deliverables all target `scripts/code-scan/` (not `hermes/tools/schema/` — original paths were incorrect)
- Phase 2 execution plan: `.plans/phase-2-flywheel-ua-integration.md`
- Do NOT commit or push from subagent — all changes await review
