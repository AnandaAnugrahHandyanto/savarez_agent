# M7 — Skill / memory / wiki hygiene (2026-06-09)

## Skill hygiene (verified)

Searched `~/.hermes/profiles/auto-coder/skills` for stale Hermes setup patterns:

| Pattern | Result |
|---------|--------|
| `login --provider` | **0** hits in active skills |
| `raw.githubusercontent.*install` (Hermes installer) | **0** in `hermes-agent` skill; unrelated hits in xurl/himalaya only |

`hermes-agent` skill: secret-redaction mentions are **current** (gateway privacy), not deprecated installer guidance.

**Action:** No mandatory `hermes-agent` SKILL.md patch this slice. Re-audit after M1 merges to upstream skill copy in repo.

## Official docs fingerprints (M6 watermark)

Stored: `~/.hermes/profiles/auto-coder/docs-watcher-watermark.json`

| Source | sha256 (prefix) | notes |
|--------|-----------------|-------|
| sitemap | `2616a402…` | 344 URLs |
| llms.txt | `4db9ca1a…` | |
| llms-full.txt | `4dea7e88…` | ~2.8 MB |
| userStories.json | `b8ffc4bd…` | 262 stories |

## Receipt index (discover without chat)

| Milestone | Path |
|-----------|------|
| Roadmap | `/tmp/hermes-workflows/hermes-roadmap-build-plan/20260609-144338/roadmap-and-build-plan.md` |
| M2b ladder | `/tmp/hermes-workflows/setup-gate-ladder/20260609-171951/` |
| M4 DWF | `/tmp/hermes-workflows/m4-worker-registry/20260609-174233/` |
| M5 gateway | `/tmp/hermes-workflows/m5-gateway-cron-hygiene/20260609-174800/` |
| M6 docs | `scripts/hermes_docs_watcher.py` + watermark above |
| PR bundle | `SollanSystems/hermes-agent` PR **#26**, branch `khall/profile-list-fast-alias-scan` |

## Memory policy

**Keep in MEMORY.md:** DWF not Kanban for setup roadmap; Grok coding policy; gateway owner `auto-coder`; smart routing config-vs-runtime blocker; worktree PR path.

**Do not store:** PR commit SHAs, per-session gate pass/fail, task TODO progress.

## Wiki

Obsidian index: `topics/agentic/2026-06-09-hermes-setup-roadmap-m0-m8-completion.md` (this run).