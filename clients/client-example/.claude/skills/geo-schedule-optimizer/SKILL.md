---
name: geo-schedule-optimizer
description: Apply geo, schedule, device, and demographic targeting changes via Google Ads API with dry-run approval. Reads geo-schedule-auditor output. Use to fix or apply targeting changes.
argument-hint: "[geo|schedule|demo|all]"
---

# Geo-Schedule Optimizer Skill

Applies geo, schedule, device, and demographic targeting changes to Google Ads accounts. Reads findings from `geo-schedule-auditor`, generates mutation operations, and applies them via the API with mandatory dry-run approval.

**This skill writes to the Google Ads account. Always dry-run first.**

| Action | ID | API Operation | Bid Strategy Gate |
|--------|------|---------------|-------------------|
| Location bid modifiers | GS-E01 | Update `campaign_criterion.bid_modifier` | Manual CPC / eCPC only |
| Exclude zero-conv locations | GS-E02 | Create negative `campaign_criterion` | All strategies |
| Fix location targeting method | GS-E03 | Update `campaign.geo_target_type_setting` | All strategies |
| Ad schedule bid adjustments | GS-E04 | Create/update ad_schedule criterion | Manual CPC / eCPC only |
| Pause dead time windows | GS-E05 | Custom schedule coverage (create active-hour entries, gap = paused) | All strategies |
| Device bid adjustments | GS-E06 | Update device criterion bid_modifier | Modifiers: Manual/eCPC · Exclusion (-100%): All strategies |
| Demographic exclusions | GS-E07 | Update criterion bid_modifier to 0 (-100%) | All strategies |
| Geographic targeting optimization | GS-E08 | Advisory only | N/A |
| Document all changes | GS-E09 | Auto-generated changelog | N/A |
| Schedule next review | GS-E10 | Advisory | N/A |

**Not built by this skill (per de-duplication log):**
- Diagnosing/scoring geo/schedule issues → `geo-schedule-auditor` (`/geo-schedule-auditor`)
- New campaign creation → campaign-builder
- Bid strategy changes → bidding-specialist
- Keyword bid changes → keyword-specialist

## Command Format

```
/geo-schedule-optimizer               # Apply all recommended changes (with dry-run first)
/geo-schedule-optimizer geo           # Apply geo changes only (GS-E01, E02, E03)
/geo-schedule-optimizer schedule      # Apply schedule + device changes only (GS-E04, E05, E06)
/geo-schedule-optimizer demo          # Apply demographic changes only (GS-E07)
```

**Prerequisites:** Requires `context/analysis/geo-schedule-audit.md` from a recent `/geo-schedule-auditor` run. If the audit report is missing or older than 24 hours, tell the user: "Run `/geo-schedule-auditor` first to generate fresh findings."

**Output:**
- Changes applied to Google Ads account (on approval)
- Changelog at `context/analysis/geo-schedule-changelog.md`
- Operations file at `created/geo-schedule-ops/operations-{YYYY-MM-DD}.json`

---

## Data Sources

| File | Required | Purpose |
|------|----------|---------|
| `context/analysis/geo-schedule-audit.md` | Yes | Audit findings to act on |
| `context/google-ads/data/campaign-criteria.csv` | Yes (re-pulled fresh) | Current modifier state for delta computation |
| `context/google-ads/data/campaigns.csv` | Yes | Bid strategy type per campaign |
| `context/google-ads/data/geo-user-location.csv` | Yes (if <24h old) | Performance data for modifier formulas |
| `context/google-ads/data/device-performance.csv` | Yes (if <24h old) | Device performance for modifier formulas |
| `context/google-ads/data/schedule-performance.csv` | Yes (if <24h old) | Schedule performance for modifier formulas |
| `context/business.md` | Recommended | Target CPA/ROAS for formula calculations |
| `config/ads-context.config.json` | Yes | Customer IDs |

---

## Process

---

### Phase 0: Prerequisites & Freshness Check

1. **Check audit report exists:**
   - Read `context/analysis/geo-schedule-audit.md`
   - If missing: STOP → "Run `/geo-schedule-auditor` first to generate findings."
   - If file modification time >24 hours ago: STOP → "Audit report is stale (>24h). Run `/geo-schedule-auditor` first for fresh findings."

2. **Parse subcommand:**
   - `geo` → GS-E01, E02, E03 only
   - `schedule` → GS-E04, E05, E06 only
   - `demo` → GS-E07 only
   - No subcommand → all applicable execute actions

3. **Load config** — read `config/ads-context.config.json`, extract customer IDs

4. **Re-pull current modifier state** (always, regardless of subcommand):
   ```bash
   node .claude/skills/gads-context/scripts/query.js \
     --customer-id={customer_id} \
     --login-customer-id={login_customer_id} \
     --query-file=.claude/skills/geo-schedule-optimizer/reference/campaign-criteria.gaql \
     --no-date-range \
     --allow-empty \
     --output=context/google-ads/data/campaign-criteria.csv
   ```

5. **Experiment exclusion:** All queries exclude experiment campaigns (`campaign.experiment_type = EXPERIMENT`). Only base/non-experiment campaigns are optimized.

6. **Check performance data freshness** — all performance CSVs must be <24 hours old:
   - `geo-user-location.csv`, `device-performance.csv`, `schedule-performance.csv`, `campaigns.csv`
   - If any are stale: re-pull automatically via query.js

7. **Display configuration:**
   ```
   Geo-Schedule Optimizer Configuration:
     Account: {customerId}
     Audit report: {date} ({age}h ago)
     Mode: {geo / schedule / demo / full}
     Performance data: all <24h old ✓
   ```

---

### Phase 1: Read Audit Findings & Apply Execute Rules

**Read `reference/execute-rules.md`** — contains the decision tree for each execute action.

**Read the audit report** and extract all WARN/FAIL findings. For each finding:

1. **Match to execute action** (GS-E01 through GS-E10)
2. **Check bid strategy gate:**
   - Read `campaigns.csv` → get `campaign.bidding_strategy_type` for each affected campaign
   - Smart Bidding (`TARGET_CPA`, `TARGET_ROAS`, `MAXIMIZE_CONVERSIONS`, `MAXIMIZE_CONVERSION_VALUE`):
     - Only -100% modifiers (exclusions, dead window pauses) are valid
     - Skip all bid modifier adjustments — note in output why
   - Manual CPC / eCPC / Max Clicks / Target IS:
     - Full modifier range available
3. **Calculate modifier values** using formulas from `reference/execute-rules.md`
4. **Apply modifier caps:**
   - First-time changes (no existing modifier): cap at +/-30%
   - Existing modifier from prior run: allow up to +/-50%
   - User can say "uncap" during approval to override
5. **Read current modifier values** from `campaign-criteria.csv` to compute deltas

---

### Phase 2: Generate Operations File

Generate `created/geo-schedule-ops/operations-{YYYY-MM-DD}.json` with all planned mutations.

Create the `created/geo-schedule-ops/` directory if it doesn't exist.

**Operations file format:**
```json
{
  "description": "Geo-schedule optimizer changes — {YYYY-MM-DD}",
  "generated_from": "context/analysis/geo-schedule-audit.md",
  "operations": [
    {
      "type": "update|create|remove",
      "resource": "campaign_criterion",
      "resource_name": "customers/{id}/campaignCriteria/{id}~{id}",
      "fields": { ... },
      "meta": {
        "campaign": "Campaign Name",
        "dimension": "location|ad_schedule|device|age_range|gender|income_range|location_exclusion",
        "target": "Human-readable target description",
        "previous_value": 1.0,
        "new_value": 1.25,
        "rationale": "Why this change — references audit finding"
      }
    }
  ]
}
```

**Resource name construction:**
- For **updates**: use `campaign_criterion.resource_name` from `campaign-criteria.csv`
- For **creates** (new exclusions, new schedule entries): use `campaign` resource name as parent
- For **removes** (replacing old schedules): use existing `campaign_criterion.resource_name`

---

### Phase 2.5: Peer Pre-flight (Cross-Skill Gate + Enrichment)

**Read `reference/handoff-matrix.md` first.** It defines the Mutation Sensitivity Matrix and the peer freshness rules used below.

This phase runs **after** the operations file is generated (Phase 2) and **before** the dry-run (Phase 3). It does two jobs:

1. **Mode 1 — Pre-flight gate.** Hard-block on dirty M / B layers; hard-warn / soft-warn on recent peer mutations.
2. **Mode 2 — Enrichment.** Collect quotes from fresh peer audits to embed in the dry-run output.

The list of campaigns being mutated is derived from the `meta.campaign` field on each operation in the operations file. All peer checks are scoped to those campaigns.

#### Step 1 — Hard-block: M layer (Tracking)

Read `context/analysis/tracking-audit.md`.

- **Missing or > 30 days old:** STOP → "Tracking audit is missing or stale (> 30d). Run `/tracking-specialist` first — geo, schedule, device, and demographic modifier formulas all depend on per-campaign conversion data. If tracking is broken, the modifiers will be wrong."
- **Any tracking module score < 70 OR any FAIL on flagged campaigns:** STOP → quote the specific failing diagnostic and route to `/tracking-specialist`.

If clean → continue.

#### Step 2 — Hard-block: B layer (Strategy / Unit Economics)

Read `context/analysis/strategy-audit.md` (and cross-check `context/business.md`).

- **Missing, > 30 days old, OR `primaryKPI` / `breakEven` / target CPA-or-ROAS placeholder/missing:** STOP → "Strategy/business layer is dirty (missing or stale unit economics). Run `/strategy-specialist` first — modifier caps and bid-multiplier formulas are computed against the target. Without it, the optimizer will pick numbers that don't tie to profitability."

If clean → continue.

#### Step 3 — Hard-warn: Smart Bidding migration in last 14 days

Scan `context/account-changelog.md` and `context/analysis/bidding-changelog.md` (if present) for any of the affected campaigns transitioning into a Smart Bidding strategy (`TARGET_CPA`, `TARGET_ROAS`, `MAXIMIZE_CONVERSIONS`, `MAXIMIZE_CONVERSION_VALUE`) within the last 14 days.

If found → HARD-WARN. Tell the user:

> Hard-warn: campaign(s) {names} migrated to Smart Bidding within the last 14d. Manual modifiers are mostly ignored under Smart Bidding (only -100% exclusions still apply). Recommend: proceed with **exclusions only** (skip all bid-modifier tuning ops), or abort and re-evaluate after the new strategy has settled.
>
> Reply: `proceed exclusions only`, or `abort`.

- `proceed exclusions only` → filter the operations file to keep only -100% modifier ops (exclusions, dead-window pauses, demographic exclusions). Drop all other tuning ops with a noted rationale.
- `abort` → stop and preserve the operations file.

#### Step 4 — Soft-warns (continue, but surface in dry-run)

Walk these checks; collect a list of soft-warn lines to embed in the dry-run output. Do not stop.

| Check | Source | Window | Soft-warn line |
|---|---|---|---|
| Bid / target adjustments on overlapping campaigns | `context/analysis/bidding-changelog.md`, `context/account-changelog.md` | 2–7 days | "Bidding adjustment on {campaign} {N}d ago — modifier deltas stack on a still-settling target. Consider smaller modifier caps." |
| Self mutations (prior `/geo-schedule-optimize` run) | `context/analysis/geo-schedule-changelog.md` | ≤ 7 days | "Geo/schedule mutated on {campaign} {N}d ago. Stacking changes risks chasing noise — confirm this is intentional (e.g., rollback)." |
| Budget changes on flagged campaigns | `context/analysis/budget-changelog.md`, `context/account-changelog.md` | ≤ 7 days | "Budget change on {campaign} {N}d ago — performance distributions are still re-shaping. Modifier formulas may be drifting." |

#### Step 5 — Enrichment: Pull fresh peer findings

For each peer in `reference/handoff-matrix.md` "Peer freshness table":

1. Check the report file exists.
2. Apply the **freshness rule** (header date canonical; surface contradictions with mtime; never auto-defer).
3. If fresh → extract 1–3 findings tagged to campaigns appearing in the operations file (filter by campaign name match in the report).
4. If stale or missing → record as "no fresh `/peer` report (last: {date}, window: ≤ Nd)" — do **not** pause or auto-trigger the peer.

Collect all quotes for the dry-run "Cross-skill context" section.

---

### Phase 3: Dry-Run & Approval

Run `mutate.js` in dry-run mode:

```bash
node .claude/skills/geo-schedule-optimizer/scripts/mutate.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --operations-file=created/geo-schedule-ops/operations-{YYYY-MM-DD}.json \
  --mode=dry-run
```

**Present the dry-run output** directly to the user. The script outputs a formatted change table grouped by campaign.

Add context after the table:
- If any Smart Bidding campaigns had modifiers skipped, explain why
- If any modifiers were capped at +/-30%, show the uncapped value
- Total estimated impact (waste eliminated, opportunity captured)

**Cross-skill context** (always render, even if empty):

```
─── Cross-skill context ───────────────────────────────────────────
Soft-warns from Phase 2.5:
  - {soft-warn line 1}
  - {soft-warn line 2}
  (or: "none")

Fresh peer audit findings on mutated campaigns:
  /budget-auditor (2026-04-28, 4d ago):
    > {quoted finding tied to campaign X}
  /bidding-auditor (2026-04-30, 2d ago):
    > {quoted finding tied to campaign Y}
  /search-term-auditor: stale (last 2026-03-12, > 7d window) — no quote
  ...

Hard-warn acknowledgements (if any):
  - Smart Bidding migration on {campaign}: proceeding with exclusions only
─────────────────────────────────────────────────────────────────
```

If no soft-warns and no fresh peer findings, render the section with "No cross-skill flags or fresh peer findings on the mutated campaigns." so the user knows the check ran.

**Wait for user approval.** The user says "yes" / "go ahead" / "apply" to proceed, or "no" to stop.

If the user says "no": preserve the operations file and stop. Tell them: "Operations saved at `created/geo-schedule-ops/operations-{YYYY-MM-DD}.json` for later use."

---

### Phase 4: Live Apply (Only on Approval)

Run `mutate.js` in live mode:

```bash
node .claude/skills/geo-schedule-optimizer/scripts/mutate.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --operations-file=created/geo-schedule-ops/operations-{YYYY-MM-DD}.json \
  --mode=live
```

Add `--allow-remove` only if the operations file contains remove operations (e.g., replacing old ad schedules).

**Report results** to the user:
- Success: "X/Y operations applied successfully."
- Partial failure: "X/Y applied. Z failed: [error details]."
- Full failure: "All operations failed: [error]."

The script automatically writes to `context/analysis/geo-schedule-changelog.md`.

---

### Phase 5: Summary & Next Steps

1. **Confirm changes applied** with summary table
2. **Log to memory** per `memory-logging.md`:
   ```markdown
   ## Geo-Schedule Optimizer Applied
   - Mode: {mode}
   - Account: {customerId}
   - Operations: {applied}/{total}
   - Key changes: {list of changes}
   - Changelog: context/analysis/geo-schedule-changelog.md
   ```
3. **Recommend next steps:**
   - "Re-run `/geo-schedule-audit` in 2-4 weeks to measure impact"
   - If GS-E08 (advisory): "Consider creating dedicated campaigns for high-performing locations"
   - If GS-E10: "Next review scheduled for {date}"
4. **GS-E09 (auto-changelog):** Already handled by `mutate.js` writing to changelog
5. **GS-E10 (next review):** Suggest a review date (30 days for routine, 14 days if significant changes)
