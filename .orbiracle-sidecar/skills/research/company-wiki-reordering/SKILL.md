---
name: company-wiki-reordering
description: Reorder the canonical workspace/company-wiki into an executive-first landing surface without breaking auto-generated rebuilds.
---

# Company Wiki Reordering

Use this when the user asks to reorganize, realign, or improve the **initial reading order** of the canonical company wiki in this repo.

## When to use
- “초기 위키를 재정렬해”
- “company wiki 첫 화면을 다시 짜”
- “엔티티 나열 말고 대표가 읽는 순서로 바꿔”
- “llm-wiki 방식으로 위키 구조를 다시 정리해”

## Core lesson
In this repo, the canonical wiki is **not** the old docs-root contract alone.
Active authority is:
- `workspace/company-wiki/SCHEMA.md`
- `workspace/company-wiki/index.md`
- `workspace/company-wiki/log.md`

`workspace/docs/llm-wiki/*` and `workspace/docs/company-wiki/*` are still important for orientation, but they are reference/governance layers, not the main user-facing wiki root.

## Required orientation
Before editing anything:
0. Confirm the actual canonical root path first. In some sessions the working directory is the repo subdirectory (for example `workspace/hermes-agent`) while the canonical wiki lives at `../company-wiki`, not `workspace/company-wiki`. If the expected path is missing, locate `company-wiki/SCHEMA.md`, `company-wiki/index.md`, and `company-wiki/log.md` with file search before proceeding.
1. Read `workspace/company-wiki/SCHEMA.md`
2. Read `workspace/company-wiki/index.md`
3. Read recent `workspace/company-wiki/log.md`
4. Read `workspace/docs/company-wiki/schema.md`
5. Read `workspace/docs/slack-org-wiki/llm-wiki-schema.md`
6. Read `workspace/skills/company-wiki.md`

Also inspect current evidence surfaces:
- latest `workspace/company-wiki/raw/run-manifests/*.json`
- latest normalized entries in `workspace/company-wiki/_build/normalized/`
- live GitHub surface (`gh auth status`, `gh repo list orbisoptimus --limit 20`)
- live Orbi MCP signals if relevant
- system crontab via `crontab -l`

## Reordering target
Default to this reading order:
1. `queries/` — executive memo / retained synthesis first
2. `concepts/` — source-overview pages second
3. `entities/` — drill-down pages third
4. `comparisons/` — explicit tradeoff pages when present

This repo’s company wiki should feel **executive-first**, not like a raw catalog.

For Obsidian-friendly operation, also add a human navigation layer at the root:
- `00-start-here.md` — vault landing note
- `01-executive-map.md` — memo/overview-first MOC
- `02-source-map.md` — source-by-source MOC
- `03-retained-memo-map.md` — retained synthesis entry into `queries/`
- `04-comparison-map.md` — tradeoff/comparison entry into `comparisons/`
- `99-obsidian-workspace-guide.md` — operator-facing vault usage guide
- source-specific entity map notes under `concepts/` such as `entity-map-github.md`, `entity-map-slack.md`, `entity-map-notion.md`, `entity-map-orbi.md`

## Obsidian-friendly restructuring target
When the user asks to make the wiki "Obsidian-friendly" or to "옵시디언화" the company wiki, do **not** default to a separate export/sync vault first. Prefer treating the canonical `company-wiki/` itself as the vault-shaped markdown surface unless the user explicitly asks for a separate mirrored vault.

In this repo, check whether `company-wiki/.obsidian/app.json` already exists before proposing new setup. If present, preserve it and verify whether `attachmentFolderPath` already points at `raw/assets`.

Default structural upgrades:
1. keep `company-wiki/` as the single canonical markdown root
2. add a human-facing landing note such as `00-start-here.md`
3. add MOC-style navigation notes such as:
   - `01-executive-map.md`
   - `02-source-map.md`
   - source/entity maps for Slack, GitHub, Notion, Orbi when entity count is large
4. prefer `[[wikilinks]]` in human-facing navigation pages over plain relative markdown links
5. standardize page frontmatter for Obsidian/Dataview friendliness (`title`, `type`, `tags`, `aliases`, `updated`, `source_type`, plus navigation fields such as `status`, `domain`, `navigation_rank`)
6. add explicit related-navigation / related-notes blocks on human-facing MOC/overview pages so backlink structure is readable even before using Graph view
7. add Dataview-oriented dashboard notes when the user wants Obsidian to become a real query surface, for example:
   - `05-refresh-loop.md` — explain the raw refresh → normalized build → wiki rebuild → Obsidian query loop
   - `10-dashboard.md` — top-level Dataview dashboard
   - `11-active-overviews.md`
   - source dashboards such as `12-domain-github.md`, `13-domain-notion.md`, `14-domain-slack.md`, `15-domain-trello.md`, `16-domain-orbi.md`
   - `17-comparisons-dashboard.md`, `18-queries-dashboard.md`
8. document clearly that actual Dataview query execution depends on the Obsidian Dataview community plugin being enabled; the markdown/frontmatter structure alone prepares the vault but does not execute query blocks
9. keep `raw/` and `_build/` in place, but strengthen the reading layer so humans enter through landing/MOC pages rather than raw/generated directories

Heuristic: if `entities/` has grown into the hundreds, do not rely on flat index browsing alone. Add source-level MOC pages so Obsidian navigation happens note-to-note instead of folder-to-folder.

## What to change
### 1. SCHEMA
Add or verify:
- reading order section
- coverage model section
- explicit note that current auto-ingest is source-driven and may include Slack, Trello, GitHub, Orbi, and Notion depending on the live canonical refresh path
- explicit note that skills/docs and cron/runtime state are valid orientation surfaces even when they are not themselves normalized entries

### 1b. Skill/router alignment
After reordering the canonical wiki, also align the surrounding skill and routing layer so the operating model stays coherent:
- `company-wiki` must read as the **top-level canonical company memory surface**
- `slack-org-wiki` must read as a **Slack source-adapter / diagnostics lane**, not a competing wiki root
- Slack cron guidance must distinguish:
  - **substrate cron** — canonical freshness/refresh maintenance
  - **delivery cron** — human-facing Slack report delivery
- if a local skill/doc still frames Slack delivery around old ZeroClaw-era defaults, rewrite it Hermes-first so it prefers native cronjob scheduling before shell wrappers

### 2. Index
Rewrite `workspace/company-wiki/index.md` so it has:
- short executive-first intro
- section counts
- “Start here” block
- source surface map
- then the full section listing

Recommended wording pattern:
- queries first
- concepts second
- entities last
- clearly distinguish:
  - Slack operating signal (auto-ingested)
  - Trello planning signal (auto-ingested)
  - GitHub execution signal (live, not yet auto-ingested)
  - Orbi signal (live, not yet auto-ingested)
  - skills/docs/cron context

### 3. Query memo
Add a retained query page summarizing:
- situation
- evidence snapshot
- analysis
- reordered reading path
- recommendation
- concrete files/scripts/surfaces used as evidence

Put it under `workspace/company-wiki/queries/`.

### 4. Governance alignment around skills and cron
When the user is not only asking for page order but for a broader wiki operating-model reset, also audit and realign the surrounding skill/cron semantics:
- `company-wiki` should stay the single canonical company-memory surface
- `slack-org-wiki` should be documented as a Slack source-adapter / diagnostics lane, not as a competing wiki root
- Slack delivery automation should be distinguished from company-wiki freshness maintenance
- `create_slack_cron` should describe **delivery cron** only, while `run_company_wiki_refresh.sh` + system crontab should be treated as the **substrate refresh** contract

If those semantics are still blurred in skills/docs, fix them in the same cycle and write a retained memo capturing the redefinition.

## Critical implementation finding
The builder used to wipe manual `queries/` or `comparisons/` pages on rebuild because it deleted section directories and regenerated only normalized-entry pages.

When reordering the wiki, preserve manual pages across rebuilds by updating:
- `workspace/bin/company-wiki/wiki_build.py`

Minimum fixes:
1. preserve existing manual pages whose slug is not regenerated from normalized entries
2. restore them after the build directory cleanup
3. ensure they still appear in `index.md`

Without this, any hand-written executive memo disappears on the next build.

## Critical bug to check
The old builder singularized section names by slicing the trailing `s`, which produced:
- `entities` -> `entitie`

Fix with an explicit mapping:
- `entities -> entity`
- `concepts -> concept`
- `comparisons -> comparison`
- `queries -> query`

Verify at least one entity page afterward.

## Verification checklist
Run all of these after edits:

```bash
python3 workspace/bin/company-wiki/wiki_build.py \
  --input workspace/company-wiki/_build/normalized/<latest>.json \
  --root workspace/company-wiki
```

Then verify:
1. `workspace/company-wiki/index.md` shows executive-first order
2. page count includes the manual query page
3. a query search returns the new memo first
4. an entity page frontmatter says `type: entity`
5. `workspace/company-wiki/log.md` contains the rebuild event

Useful query check:

```bash
python3 workspace/bin/company-wiki/wiki_query.py \
  --root workspace/company-wiki \
  --query "initial wiki reordering github orbi cron"
```

## Pitfalls
- Do not assume `workspace/docs/llm-wiki/` is the active company wiki root.
- Do not rebuild before protecting manual query/comparison pages.
- Do not describe GitHub/Orbi as auto-ingested unless the normalized-entry pipeline actually includes them.
- Do not trust `gh api graphql` alone; if it throws intermittent HTTP 502, fall back to `gh repo list` for live verification.
- Do not stop at structure-only edits; verify the wiki query surface still returns the new executive memo.
