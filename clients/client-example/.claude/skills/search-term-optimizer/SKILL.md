---
name: search-term-optimizer
description: >
  Apply search term mutations (negatives, promotions, n-gram exclusions, conflict resolution,
  brand defense, foreign language negatives) via Google Ads API with dry-run approval.
  Reads search-term-auditor output. Use to fix search terms, apply negatives, or promote
  high-performing terms.
disable-model-invocation: true
argument-hint: "[negate|ngrams|promote|conflicts|consolidate|catalog|brand|foreign]"
allowed-tools: Bash(node .claude/skills/search-term-optimizer/scripts/mutate.js *) Bash(node .claude/skills/gads-context/scripts/query.js *) Bash(node .claude/skills/search-term-auditor/scripts/pull-all.js *) Read Write
---

# Search Term Optimizer

Applies search-term mutations based on `search-term-auditor` findings. **NEVER applies changes directly** — always generates `operations.json` → dry-run (validate_only=true) → user approval → live apply.

This skill is user-invoke only (`disable-model-invocation: true`) because it mutates a live Google Ads account.

**Actions (9 total):**
- **ST-E01** — Negate irrelevant search terms (Search + PMax, shared list default)
- **ST-E02** — N-gram exclusion cycle (two canonical lists, Search + PMax)
- **ST-E03** — Promote high-performing terms (respect advertiser's existing match-type setup)
- **ST-E04** — Resolve negative conflicts
- **ST-E05** — Consolidate ad-group negatives → shared list
- **ST-E06** — Consolidate campaign negatives → shared list
- **ST-E07** — Catalog-validated negative proposal (365d lookback)
- **ST-E09** — PMax brand defense (brand list criterion)
- **ST-E10** — Negate foreign language queries (Exact match shared list)

_ST-E08 and ST-E11 were folded in / removed per the PRD._

---

## Command Routing

```
/search-term-optimizer                  → All applicable actions from audit findings
/search-term-optimizer negate           → ST-E01 only
/search-term-optimizer ngrams           → ST-E02 only
/search-term-optimizer promote          → ST-E03 only (respects existing setup)
/search-term-optimizer conflicts        → ST-E04 only
/search-term-optimizer consolidate      → ST-E05 + ST-E06
/search-term-optimizer catalog          → ST-E07 only (propose-only, 365d validation)
/search-term-optimizer brand            → ST-E09 only
/search-term-optimizer foreign          → ST-E10 only
```

---

## MANDATORY SAFETY RULE

**NEVER apply changes directly via inline API calls.** The process is ALWAYS:

1. Generate `created/search-terms/operations-{YYYY-MM-DD}.json`
2. Run `mutate.js --mode=dry-run` (validate_only + show table)
3. Present dry-run table to user
4. Ask for explicit approval
5. Only on "yes": run `mutate.js --mode=live`

No exceptions. No shortcuts. `--max-ops` caps at 100 by default.

---

## Phase 0: Prerequisites & Pre-Flight

### Phase 0.1: Audit Freshness Check

1. Read `context/analysis/search-term-audit.md`.
2. Check the report date in the header.
3. If audit is > 24 hours old:
   > "The search term audit is from {date} ({N} days ago). For accurate optimization, I recommend running a fresh audit first. Proceed with stale data, or run `/search-term-auditor` first?"
4. If no audit report exists:
   > "No search term audit found. Running `/search-term-auditor` first..."
   Then execute the auditor skill.

### Phase 0.2: Fresh Negative State Pull

Always pull fresh negative + shared-list link state before generating operations (stale state → duplicate exclusions or wrong scope):

```bash
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customerId} --login-customer-id={loginCustomerId} \
  --query-file=.claude/skills/search-term-auditor/reference/gaql/negatives-campaign.gaql \
  --no-date-range --allow-empty \
  --output=context/google-ads/data/negative-keywords-campaign.csv
```

Repeat for `negatives-shared.gaql`, `negatives-adgroup.gaql`, and `negatives-shared-campaigns.gaql`.

### Phase 0.3: Load Context

1. Read `config/ads-context.config.json` — customerId, loginCustomerId, sharedNegativeLists, negativeMatchType, conversion targets.
2. Read `.claude/skills/search-term-auditor/tmp/search-term-flags.json` and `tmp/negative-flags.json` — source of truth for what to act on.
3. Read `context/analysis/search-term-audit.md` — recommended actions.
4. Read `context/business.md` — for match-type resolution (ST-E03 respects existing setup).
5. If ST-E07 (catalog) in scope: trigger pull-all.js with `--pull-catalog` and 365d window if `search-terms-catalog.csv` is missing.

### Phase 0.4: Peer Pre-Flight Gate

Before generating any operations, run the cross-skill peer pre-flight per `reference/handoff-matrix.md`. The optimizer mutates the live account — peer signals can hard-block, hard-warn, or soft-warn the apply.

**Read `reference/handoff-matrix.md` in full before proceeding.** It defines the 10-peer freshness table, the freshness rule (header date canonical, never auto-defer), and the Mutation Sensitivity Matrix.

**Two modes run here:**

1. **Mode 1 — Pre-flight gate.** Evaluate each peer report (10 total, excludes `/search-term-auditor` which is the upstream input):
   - Parse the **header date** of each peer report — canonical freshness signal. Never use file mtime.
   - **Hard-block** on dirty Measurement (`/tracking-specialist`) or Business (`/strategy-specialist`) per the handoff matrix. Refuse to generate operations until resolved or explicitly overridden.
   - **Hard-warn** on data-discontinuity peer activity (campaign restructure within 14d on overlapping campaigns). Require explicit confirmation.
   - **Soft-warn** on cohort-shifting peer activity per the Mutation Sensitivity Matrix:
     - Recent keyword changes within 7d on overlapping ad groups (term cohort shifting)
     - Bid / target adjustments within 2–7d on overlapping campaigns (negatives shift CPL)
     - Recent ad-copy changes within 7d on overlapping ad groups (CTR signal mid-test)
     - Self mutations within 7d (don't stack)
     - QS optimization activity within 7d on overlapping ad groups (cohort signal not stabilized)
2. **Mode 2 — Enrichment.** Collect fresh peer findings scoped to the campaigns / ad groups in mutation scope. Stash them for the Phase 2 "Cross-skill context" section. Surface contradictions between peers — never auto-defer to one date or one finding.

**Freshness rule (binding):**
- The header date in each peer report is canonical. Parse it explicitly.
- Inside the fresh window → signal is active, surface it.
- Outside the fresh window → stale, do not surface as fresh, do not block. Note as "consider re-running".
- If the header date contradicts other dating in the report body, surface the contradiction in the Cross-skill context section. Never auto-defer.
- Never auto-run a peer skill from inside the optimizer. Only suggest.

**Gate outcomes:**
- **Hard-block triggered** → STOP. Print the hard-block message from the handoff matrix and exit. Do not proceed to Phase 1.
- **Hard-warn triggered** → Print the warning, require explicit `y/N` confirmation (default no). On confirmation, proceed to Phase 1 with the warning recorded.
- **Soft-warn(s) triggered** → Note them; surface in Phase 2's Cross-skill context section + apply prompt. Proceed to Phase 1.
- **All clear** → Proceed to Phase 1; Cross-skill context section will list "no fresh signal from {peers}" and any active findings.

---

## Phase 1: Generate Operations

Read `reference/execute-rules.md` for full decision trees per action.
Read `reference/export-formats.md` for the `operations.json` schema.

### Scope filter by command

| Command | Actions executed |
|---------|-----------------|
| (all) | E01 + E02 + E03 + E04 + E05 + E06 + E09 + E10 (E07 only on explicit opt-in) |
| `negate` | E01 |
| `ngrams` | E02 |
| `promote` | E03 |
| `conflicts` | E04 |
| `consolidate` | E05 + E06 |
| `catalog` | E07 |
| `brand` | E09 |
| `foreign` | E10 |

### Shared-list default policy (applies to E01, E02, E05, E06, E07, E10)

Per PRD §2 decision 9b:

1. **Pre-flight:** verify the target shared list exists. If not, add a `create_shared_set` primitive and attach to all active Search + PMax campaigns.
2. **Pre-flight:** verify link coverage — every active Search and PMax campaign must be linked to the relevant list. Missing links are created in the same batch.
3. Campaign-level negatives only when the negative is genuinely campaign-specific (brand carve-out, single-campaign experiment).

### N-gram routing (ST-E02)

Route each finding to one of two canonical lists based on source diagnostic:
- ST-D13 findings → `Negative N-grams — Non-Converting`
- ST-D14 findings → `Negative N-grams — Inefficient`

Both auto-attached to Search + PMax. List names configurable via `searchTermAnalysis.sharedNegativeLists` in `ads-context.config.json`.

### Promotion match type (ST-E03)

**Respect advertiser's existing setup.** For each promotion candidate:
1. Detect the target ad group / campaign's current match-type mix (exact-only, exact+phrase, broad-heavy).
2. Promote into that same pattern.
3. Never auto-apply Broad-on-Smart-Bidding — if the setup suggests experimentation is warranted, surface as an **opt-in 50/50 campaign experiment nudge** in the report, not in the operation set.
4. Resolve the campaign's bidding strategy via `lib.resolveBiddingStrategy` (honor portfolio attachments) before choosing between manual vs smart-bidding-specific patterns.

### Build operations.json

```json
{
  "description": "Search term optimizer — {YYYY-MM-DD}",
  "generated_from": "context/analysis/search-term-audit.md",
  "generated_at": "{ISO timestamp}",
  "total_operations": {count},
  "operations": [ ... ]
}
```

Write to `created/search-terms/operations-{YYYY-MM-DD}.json`.

### Cross-op resource references (temp negative IDs)

`mutate.js` sends every operation in a single `mutateResources` call — it does **not** chain responses or resolve string placeholders like `{{INEFFICIENT_LIST_RN}}`. Any op that needs to reference a resource created *within the same batch* (e.g. a newly-created shared set used by its attachments and criteria) must use Google Ads' **temporary negative-ID** convention:

1. On the `shared_set` create op, assign `fields.resource_name = "customers/{customerId}/sharedSets/-1"`. The API treats any negative ID as a temp identifier and returns the real resource name in the response.
2. In every dependent op within the same batch, reference that exact temp string as `shared_set` (or wherever the FK would go). Use distinct negatives (`-1`, `-2`, ...) for multiple new entities.

Example — bootstrapping a new list in-batch:

```json
// 1. Create the list with a temp negative ID
{
  "type": "create", "resource": "shared_set",
  "fields": {
    "resource_name": "customers/8208553062/sharedSets/-1",
    "name": "Inefficient N-grams",
    "type": "NEGATIVE_KEYWORDS",
    "status": "ENABLED"
  },
  "meta": { "action_id": "PREFLIGHT", "list_name": "Inefficient N-grams" }
}
// 2. Attachment references the same temp ID
{
  "type": "create", "resource": "campaign_shared_set",
  "fields": {
    "campaign": "customers/8208553062/campaigns/23577230782",
    "shared_set": "customers/8208553062/sharedSets/-1",
    "status": "ENABLED"
  },
  "meta": { "action_id": "PREFLIGHT" }
}
// 3. Criterion on the new list — same temp ID
{
  "type": "create", "resource": "shared_criterion",
  "fields": {
    "shared_set": "customers/8208553062/sharedSets/-1",
    "keyword": { "text": "ai gamma", "match_type": "PHRASE" },
    "type": "KEYWORD"
  },
  "meta": { "action_id": "ST-E02" }
}
```

**Never use string placeholders** (`{{…}}`) — the API rejects them as malformed resource names. Existing lists always use their real resource name from `negative-keywords-shared.csv`.

Tell user: "Generated {N} operations: {V} negatives, {X} n-gram exclusions, {Y} promotions, {Z} conflicts resolved, {W} brand exclusions."

---

## Phase 2: Dry-Run Validation

```bash
node .claude/skills/search-term-optimizer/scripts/mutate.js \
  --customer-id={customerId} --login-customer-id={loginCustomerId} \
  --operations-file=created/search-terms/operations-{YYYY-MM-DD}.json \
  --mode=dry-run
```

`mutate.js` emits per-category **preview CSVs** to `created/search-terms/{YYYY-MM-DD}_preview_{bucket}.csv` (ngrams, negate, foreign, promote, removals, preflight, brand). These are the human-review artifact — the user can scan hundreds of n-gram/negate rows in a spreadsheet before approving. Make sure they are sorted logically. ngrams by spend, promotion terms by conversions.

Present formatted table (grouped by action code), list the preview CSV filenames, **then surface the Cross-skill context section** (collected in Phase 0.4 Mode 2), and ask for approval.

### Cross-skill context section (required in dry-run output)

Render a `## Cross-skill context` section using the Phase 0.4 Mode 2 enrichment. Format per `reference/handoff-matrix.md`:

```
## Cross-skill context

Mutation scope: {N} campaigns, {M} ad groups.

Fresh peer signals on this scope:
- /{peer} ({age} days old, header date {YYYY-MM-DD}): {module/diagnostic-id} — {one-clause why it matters for this batch}.
- ...

Soft-warns from Mutation Sensitivity Matrix:
- {peer activity} on {surface} within {window} → {why it shifts the cohort}.

Hard-warns (require explicit confirmation):
- {data-discontinuity finding}.

Stale peer signals (consider re-running):
- /{peer}: report from {N} days ago, fresh window is {window}.

No fresh signal from: /{peer}, /{peer}, ...

Contradictions surfaced (do not auto-defer):
- /{peer-a} says {finding}, /{peer-b} says {opposing finding}. Decide before approving.
```

If there are no fresh signals, no soft-warns, and no contradictions, render the section with the single line `No fresh peer signals on the mutation scope. Proceed at your discretion.` — never omit the section.

### Approval prompt

> "Preview CSVs written. Review them in `created/search-terms/`. Cross-skill context shown above lists {K} fresh peer signals, {S} soft-warns, {H} hard-warns. These changes have NOT been applied. Ready to apply? (yes / no)"

If hard-warns are present, the prompt requires explicit `y` confirmation per warning before the apply prompt is offered.

If user declines, offer selective approval or regeneration.

---

## Phase 3: Live Apply

Only on explicit "yes":

```bash
node .claude/skills/search-term-optimizer/scripts/mutate.js \
  --customer-id={customerId} --login-customer-id={loginCustomerId} \
  --operations-file=created/search-terms/operations-{YYYY-MM-DD}.json \
  --mode=live
```

### Operation ordering (enforced by mutate.js)

1. **Shared set creates + campaign attachments** — lists must exist before populating.
2. **Negative creates at shared list level** (E01, E02, E06, E07, E10).
3. **Negative creates at campaign level** (E01 fallback, E05 fallback).
4. **Negative removes** (E04, E05 remove-step, E06 remove-step) — after creates to avoid coverage gaps.
5. **Brand exclusions** (E09).
6. **Keyword creates** (E03) — last, lowest risk.

### Post-apply

- mutate.js auto-logs to `context/analysis/search-term-changelog.md`.
- Export CSVs to `created/search-terms/{timestamp}_{action}.csv` for manual reference / rollback.
- Suggest: "Consider re-running `/search-term-auditor` in 14–30 days to measure impact."

---

## Edge Cases

| Scenario | Handling |
|----------|----------|
| No audit report | Run `/search-term-auditor` first, then proceed. |
| Audit > 24h old | Warn user; let them proceed or re-audit. |
| 0 operations generated | "No actionable issues found for this scope." |
| > 100 operations | mutate.js blocks. Inform user: "Large change set ({N} ops). Proceed with --max-ops={N}?" |
| Shared list doesn't exist | Pre-flight creates it + attaches to all Search + PMax campaigns. |
| Campaign missing shared-list link | Pre-flight creates the `campaign_shared_set` link as part of the batch. |
| Promotion candidate with no clear parent AG match-type pattern | Default to Exact; note in operation meta. |
| Portfolio bid strategy | Resolved upstream by auditor. E03 reads `target_source` + `portfolio_name` for match-type heuristics. Mutations are on the ad-group criterion, not the portfolio — no special handling needed. |
| Catalog candidate blocked by data (would hide a converting query) | Filter out in Phase 1; surface to user as "skipped — would block converting traffic." |
| Brand exclusion list (ST-E09) already attached | Pre-flight checks; no duplicate operation emitted. |
| Foreign-language exclusion at Exact match | Default to Exact because foreign terms are specific (vs Phrase for irrelevant categories). |
| Legacy +modified +broad rewrite (ST-E01 format-convert mode) | Remove legacy entry + create replacement in Phrase match in the same batch. |

---

## Integration Points

### Reads from
- `.claude/skills/search-term-auditor/tmp/search-term-flags.json`
- `.claude/skills/search-term-auditor/tmp/negative-flags.json`
- `context/analysis/search-term-audit.md` — auditor findings (freshness check)
- `context/google-ads/data/*.csv` — fresh negative + link state (re-pulled in Phase 0.2)
- `context/business.md` — match-type resolution for ST-E03
- `config/ads-context.config.json` — shared list names, match-type defaults
- **Peer reports for Phase 0.4 pre-flight gate + dry-run enrichment** (per `reference/handoff-matrix.md`):
  - `context/analysis/tracking-audit.md` — M layer (hard-block if dirty, ≤ 30d)
  - `context/analysis/strategy-audit.md` — B layer (hard-block if dirty, ≤ 30d)
  - `context/analysis/quality-score-audit.md` — ≤ 7d
  - `context/analysis/keyword-audit.md` — ≤ 7d
  - `context/analysis/budget-audit.md` — ≤ 7d
  - `context/analysis/bidding-audit.md` — ≤ 7d
  - `context/analysis/competitive-audit.md` — ≤ 14d
  - `context/analysis/lp-audit.md` — ≤ 14d
  - `context/analysis/offer-audit.md` — ≤ 30d
  - `context/analysis/account-audit.md` — ≤ 30d
- **Changelogs for Mutation Sensitivity Matrix** (recent peer mutations on overlapping surfaces):
  - `context/analysis/keyword-changelog.md` — keyword changes within 7d
  - `context/analysis/bidding-changelog.md` — bid / target adjustments within 2–7d
  - `context/analysis/search-term-changelog.md` — self mutations within 7d
  - `context/analysis/quality-score-changelog.md` (or RSA / LP changelogs) — copy / QS activity within 7d

### Writes to
- `created/search-terms/operations-{YYYY-MM-DD}.json` — intermediate artifact
- `created/search-terms/{timestamp}_*.csv` — export files for manual reference
- `context/analysis/search-term-changelog.md` — append-only mutation log

### Related skills
- `/search-term-auditor` — diagnose-only counterpart (run first)
- `/tracking-specialist`, `/strategy-specialist` — upstream M / B layers; hard-block enforced by Phase 0.4 peer pre-flight gate
- `/quality-score-auditor`, `/keyword-auditor`, `/budget-auditor`, `/bidding-auditor`, `/competitive-analyst`, `/lp-auditor`, `/offer-auditor`, `/account-auditor` — peer signals surfaced via Phase 0.4 enrichment + dry-run Cross-skill context section per `reference/handoff-matrix.md`
