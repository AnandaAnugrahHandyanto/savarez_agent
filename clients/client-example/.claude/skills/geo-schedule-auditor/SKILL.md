---
name: geo-schedule-auditor
description: Audit geographic, ad schedule, device, and demographic targeting across 14 diagnostics in 3 modules. Scores 0-100 per module. Use for geo, schedule, device, or demographic audits.
argument-hint: "[geo|schedule|demo]"
---

# Geo-Schedule Auditor Skill

Audits geographic, schedule, device, and demographic targeting health across 3 modules (14 diagnostics). DIAGNOSE-ONLY — findings route to `geo-schedule-optimizer` for execution.

| Module | IDs | Checks |
|--------|-----|--------|
| **Geographic** | GS-D01–D05 | Location targeting method, CPA/ROAS variance, zero-conversion locations, high-performing opportunity, exclusion coverage |
| **Schedule & Device** | GS-D06–D09 | Device CPA variance, ad schedule waste, schedule consistency, modifier stacking |
| **Demographics & Advanced** | GS-D10–D14 | Demographic CPA outliers, Smart Bidding modifier conflict, seasonal geo patterns, demographic exclusion opportunity, geographic targeting optimization |

**Not checked by this skill (per de-duplication log):**
- Applying bid modifiers/exclusions → `geo-schedule-optimizer` (`/geo-schedule-optimizer`)
- Bid strategy changes → bidding-specialist
- Keyword performance → keyword-specialist
- Campaign structure → account-auditor

## Command Format

```
/geo-schedule-auditor                  # Full audit (all 14 checks)
/geo-schedule-auditor geo              # GS-D01 to GS-D05 only
/geo-schedule-auditor schedule         # GS-D06 to GS-D09 only
/geo-schedule-auditor demo             # GS-D10 to GS-D14 only
```

**Examples:**
- `/geo-schedule-auditor` — Full audit across all modules
- `/geo-schedule-auditor geo` — Geographic targeting check
- `/geo-schedule-auditor schedule` — Schedule & device efficiency check
- `/geo-schedule-auditor demo` — Demographic targeting check

---

## Data Sources

| File | Required | Purpose |
|------|----------|---------|
| `context/google-ads/data/campaigns.csv` | Yes (from gads-context) | Campaign performance + bid strategy types |
| `context/google-ads/data/campaigns-settings.csv` | Yes (from gads-context or account-auditor) | Geo targeting method for GS-D01 |
| `context/google-ads/data/geo-user-location.csv` | Yes (from gads-context) | Location performance for GS-D02–D05, D14 |
| `context/google-ads/data/device-performance.csv` | Yes (from gads-context) | Device performance for GS-D06 |
| `context/google-ads/data/campaign-criteria.csv` | Yes (pulled fresh) | Current bid modifiers, schedules, exclusions |
| `context/google-ads/data/schedule-performance.csv` | Yes (pulled fresh) | Hour x day performance for GS-D07 |
| `context/google-ads/data/demographics-age.csv` | Yes (pulled fresh) | Age range performance for GS-D10, D13 |
| `context/google-ads/data/demographics-gender.csv` | Yes (pulled fresh) | Gender performance for GS-D10, D13 |
| `context/google-ads/data/demographics-income.csv` | Yes (pulled fresh) | Income range performance for GS-D10, D13 |
| `context/google-ads/data/schedule-consistency.csv` | Generated (script) | Weekly consistency for GS-D08 |
| `context/google-ads/data/geo-seasonal-comparison.csv` | Generated (script) | YoY geo comparison for GS-D12 |
| `context/business.md` | Recommended | Vertical, target CPA/ROAS |
| `config/ads-context.config.json` | Yes | Customer IDs |

---

## Process

---

### Phase 0: Prerequisites & Route

1. **Parse subcommand:**
   - `geo` → GS-D01–D05 only
   - `schedule` → GS-D06–D09 only
   - `demo` → GS-D10–D14 only
   - No subcommand (default) → run all modules sequentially

2. **Load config** — read `config/ads-context.config.json`, extract:
   - `googleAds.customerId` and `googleAds.loginCustomerId`

3. **Load business.md** — extract:
   - Vertical (ecommerce / lead gen / SaaS / tourism / travel / relocation)
   - Target CPA or target ROAS (needed for GS-D03)
   - If business.md is missing: WARN but continue (most checks work without it)

4. **Display configuration:**
   ```
   Geo-Schedule Audit Configuration:
     Account: {customerId}
     Vertical: {vertical}
     Target CPA: ${target_cpa} (or Target ROAS: {target_roas})
     Mode: {geo / schedule / demo / full}
   ```

---

### Phase 0.5: Data Collection

**Pull fresh data that this skill needs. Reuse existing gads-context data if fresh enough.**

#### Always pull fresh (every run):

```bash
# Campaign criteria — current modifiers, schedules, exclusions (no date range — structural)
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query-file=.claude/skills/geo-schedule-auditor/reference/campaign-criteria.gaql \
  --no-date-range \
  --allow-empty \
  --output=context/google-ads/data/campaign-criteria.csv

# Schedule performance — hour x day matrix (30 days)
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query-file=.claude/skills/geo-schedule-auditor/reference/schedule-performance.gaql \
  --days=30 \
  --output=context/google-ads/data/schedule-performance.csv

# Demographic performance — age ranges (90 days — GS-D13 needs 60+ days)
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query-file=.claude/skills/geo-schedule-auditor/reference/demographics.gaql \
  --days=90 \
  --allow-empty \
  --output=context/google-ads/data/demographics-age.csv

# Demographic performance — gender (90 days)
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query-file=.claude/skills/geo-schedule-auditor/reference/demographics-gender.gaql \
  --days=90 \
  --allow-empty \
  --output=context/google-ads/data/demographics-gender.csv

# Demographic performance — income (90 days)
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query-file=.claude/skills/geo-schedule-auditor/reference/demographics-income.gaql \
  --days=90 \
  --allow-empty \
  --output=context/google-ads/data/demographics-income.csv
```

#### Pull only if subcommand requires and data is stale:

**For GS-D08 (schedule consistency):** Only when running `schedule` or `full` mode:
```bash
node .claude/skills/geo-schedule-auditor/scripts/analyze-schedule-consistency.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --days=30 \
  --output=context/google-ads/data/schedule-consistency.csv
```

**For GS-D12 (seasonal geo):** Only when running `demo` or `full` mode:
```bash
node .claude/skills/geo-schedule-auditor/scripts/analyze-geo-seasonal.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --days=30 \
  --output=context/google-ads/data/geo-seasonal-comparison.csv
```

#### Reuse existing (check freshness):

| File | Max Age | If Stale |
|------|---------|----------|
| `geo-user-location.csv` | 3 days | Re-pull via `/gads-context` or query.js with `geo-user-location.gaql` |
| `device-performance.csv` | 3 days | Re-pull via `/gads-context` or query.js with `device-performance.gaql` |
| `campaigns.csv` | 3 days | Re-pull via `/gads-context` |
| `campaigns-settings.csv` | 7 days | Re-pull via query.js with `campaigns-settings-audit.gaql` |

**Check freshness** by reading file modification time. If stale, re-pull automatically:
```bash
# Example re-pull for stale geo-user-location.csv
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query-file=.claude/skills/gads-context/references/geo-user-location.gaql \
  --days=30 \
  --output=context/google-ads/data/geo-user-location.csv
```

**Display data pull summary:**
```
Data Sources:
| File                          | Rows | Last Updated         | Status              |
|-------------------------------|------|----------------------|---------------------|
| geo-user-location.csv         | {n}  | {date}               | OK (Xh ago)         |
| device-performance.csv        | {n}  | {date}               | OK (Xh ago)         |
| campaigns.csv                 | {n}  | {date}               | OK (Xh ago)         |
| campaigns-settings.csv        | {n}  | {date}               | OK (Xd ago)         |
| campaign-criteria.csv         | {n}  | —                    | Pulled fresh        |
| schedule-performance.csv      | {n}  | —                    | Pulled fresh        |
| demographics-age.csv          | {n}  | —                    | Pulled fresh        |
| demographics-gender.csv       | {n}  | —                    | Pulled fresh        |
| demographics-income.csv       | {n}  | —                    | Pulled fresh        |
| schedule-consistency.csv      | {n}  | —                    | Generated fresh     |
| geo-seasonal-comparison.csv   | {n}  | —                    | Generated fresh     |
```

If campaigns.csv has zero enabled campaigns, STOP: "No enabled campaigns found."

**Experiment exclusion:** All queries and analysis exclude experiment campaigns (`campaign.experiment_type = EXPERIMENT`). Only base/non-experiment campaigns are audited. This is enforced in GAQL WHERE clauses and script queries.

**Enum field mapping note:** The campaign-criteria.gaql and demographics.gaql queries return enum fields. Before running these queries for the first time in an account, verify that `query.js` has the necessary `enumFieldMap` entries. Required mappings are listed in `reference/diagnostic-rules-shared.md` under "Enum Fields Requiring Mapping." If any are missing, add them to `query.js` before proceeding.

---

### Phase 1: Run Diagnostics

**Read `reference/diagnostic-rules-shared.md` first** (scoring model, severity definitions, data sufficiency gates).

**Then read ONLY the module-specific rules for the requested subcommand:**

| Subcommand | Reference files to load |
|---|---|
| `geo` | `diagnostic-rules-geo.md` |
| `schedule` | `diagnostic-rules-schedule.md` |
| `demo` | `diagnostic-rules-demo.md` |
| Default (all) | Run modules sequentially. Load and release each module's references before loading the next. |

**Important:** When running all modules (default), do NOT load all reference files at once. Run geo first, then schedule, then demo — loading each module's references fresh for that phase.

Read CSV data files into working memory.

Run each diagnostic in order per the module-specific rules. For each, produce a structured result:

```
ID: GS-DXX
Name: {diagnostic name}
Status: PASS | WARN | FAIL | SKIP
Severity: Critical | High | Medium | Low
Points: {earned} / {possible}
Details: {what was found — list specific campaigns/locations/time slots}
Recommendation: {if WARN or FAIL, what to fix}
Routing: {optimizer command that handles the fix}
```

**After each module, display results table:**

```
{Module Name} Diagnostic Results:
| ID      | Diagnostic                    | Status | Pts   | Detail                                    |
|---------|-------------------------------|--------|-------|-------------------------------------------|
| GS-D01  | Location targeting method     | PASS   | 5/5   | All campaigns use PRESENCE                 |
| GS-D02  | Geographic CPA/ROAS variance  | WARN   | 0/5   | 3 locations CPA 30%+ above avg            |
| ...     | ...                           | ...    | ...   | ...                                       |
```

---

### Phase 2: Score & Log

**Calculate scores:**

1. Tally points earned vs points possible (exclude SKIP diagnostics from denominator)
2. Calculate module scores:
   - Geographic: GS-D01–D05 (max 35 pts)
   - Schedule & Device: GS-D06–D09 (max 28 pts)
   - Demographics & Advanced: GS-D10–D14 (max 28 pts)
   - Overall: total earned / total possible as percentage
3. Assign grade:
   - 90-100%: Excellent
   - 70-89%: Good
   - 50-69%: Needs Attention
   - < 50%: Critical

**Append to log:** `context/analysis/geo-schedule-audit-log.md`

Follow the log entry format from `reference/report-template.md`. Create the file if it doesn't exist, or append to it.

---

### Phase 2.5: Peer Report Lookup (MANDATORY before writing the report)

**Don't send the user from one door to the other.** Before recommending any peer-skill handoff in Phase 3 or Phase 4, check whether that peer has already produced a fresh report — and if so, **read it and integrate its findings into THIS report** instead of asking the user to re-run.

The whole point of cross-skill awareness is that a user who runs `/bidding-auditor` last week and then runs `/geo-schedule-audit` this week sees the bidding findings *quoted inside the geo-schedule report*, not a redundant "go run bidding" instruction. Re-running an auditor that already produced a fresh answer wastes time and obscures the targeting-side action.

#### Freshness windows

| Peer skill | Report file | Fresh window |
|---|---|---|
| `/quality-score-auditor` | `context/analysis/quality-score-audit.md` | ≤ 7 days |
| `/search-term-auditor` | `context/analysis/search-term-audit.md` | ≤ 7 days |
| `/keyword-auditor` | `context/analysis/keyword-audit.md` | ≤ 7 days |
| `/budget-auditor` | `context/analysis/budget-audit.md` | ≤ 7 days |
| `/bidding-auditor` | `context/analysis/bidding-audit.md` | ≤ 7 days |
| `/competitive-analyst` | `context/analysis/competitive-audit.md` | ≤ 14 days |
| `/lp-auditor` | `context/analysis/lp-audit.md` | ≤ 14 days |
| `/offer-auditor` | `context/analysis/offer-audit.md` | ≤ 30 days |
| `/tracking-specialist` | `context/analysis/tracking-audit.md` | ≤ 30 days |
| `/account-auditor` | `context/analysis/account-audit.md` | ≤ 30 days |

#### Procedure for each peer that the routing would otherwise hand off to

1. **Check if the file exists.** If not → keep the handoff as a plain "run `/peer-skill`" line.
2. **If it exists, check the date in the report header against the freshness window.** The report header date is canonical. mtime is a sanity check — if mtime is *older* than the header date, warn the user that something is off.
3. **If fresh:** open the report and read its **executive read / top findings / module scores**. Pull out the 1–3 findings that overlap with this audit's flagged campaigns, locations, time windows, devices, or demographic segments. Use them to:
   - **Enrich the Executive read at the top of `geo-schedule-audit.md`** — quote the peer's score, the headline finding, and the date inline.
   - **Replace** the routing line "run `/peer-skill`" with: **"Review the existing {date} {peer} report at {path} — top finding: '{one-liner}'. Re-run only if you want fresher data."**
   - In Critical Issues / Recommended Next Steps, when a peer handoff is the recommended action, quote the peer's specific finding so the user can act without leaving this report.
4. **If stale:** mention "a previous {peer} report exists from {date} but is {N} days old — recommend re-running before relying on it" and keep the handoff as a re-run.
5. **If missing:** standard "run `/peer-skill`" handoff.

#### When a fresh peer report contradicts a geo-schedule hypothesis

Say so explicitly in the Executive read. Example: geo-schedule-auditor flags GS-D06 (device CPA variance) for tablets — but the fresh bidding-audit shows the campaign is using tROAS Smart Bidding, which means manual device modifiers are ignored. The device-modifier finding is then misleading; the fix is at the bid-strategy or device-exclusion level, not a modifier. Or: GS-D03 flags zero-conversion locations, but the fresh tracking-audit shows the conversion event is misfiring on mobile in those geos — exclusions would punish geos that may actually be working. **The geo-schedule report must say this, not silently propose targeting changes.**

That cross-skill validation is the entire reason this phase exists. A geo-schedule audit that ignores a fresh tracking, bidding, or QS audit produces a confidently-wrong recommendation.

---

### Phase 3: Write Report

**Write full report:** `context/analysis/geo-schedule-audit.md` (overwrites each run).

Follow the full report template from `reference/report-template.md`.

**Lead with the Executive read** — the 6-slot prose contract defined in `reference/report-template.md`. Apply Phase 2.5 lookup results to slot 4 (inline-quoted fresh peer findings) and to every line in Recommended Next Steps that points to a peer skill.

Fill in all sections in this order:
1. **Executive read** (prose, ≤300 words, no bullets) — score meaning, 1–3 priorities w/ why, what's NOT a problem, fresh peer findings inline, how-to-read, score trend.
2. Overall score + grade
3. Module scores breakdown
4. Critical issues ranked by impact — with peer findings integrated when fresh
5. Per-module results tables with detail blocks for WARN/FAIL items
6. Recommended next steps — apply Phase 2.5 results: every line says either "run /peer" (missing/stale) or "review existing {date} report at {path}" (fresh, with the one-liner finding)
7. Data freshness summary

---

### Phase 4: Summary & Next Steps

Already written in Phase 3; Phase 4 is the user-facing presentation. The reader should be able to act from the **Executive read alone** — that's the bar. Everything else is reference material.

Print to user in this order:

1. **Executive read** (the prose section from the report — quote it verbatim, don't re-summarize). It already covers score-meaning, this-week priorities w/ why, what's-NOT-a-problem, fresh peer findings inline, how-to-read, score trend.
2. **Overall score and grade**, mode, run timestamp.
3. **Module score table.**
4. **Top issues** (max 3, ranked by severity/waste).
5. **Recommended next steps** using the routing table below — apply Phase 2.5 lookup results to every line. Each peer handoff says either "review existing {date} report at {path} (top finding: ...)" or "run `/peer-skill`".

#### DIAGNOSE → Optimizer Routing Table

| DIAGNOSE Result | Suggested Action |
|---|---|
| GS-D01 WARN (wrong targeting method) | "Run `/geo-schedule-optimize geo` to fix location targeting settings" |
| GS-D02 WARN/FAIL (high-CPA locations) | "Run `/geo-schedule-optimize geo` to apply location bid modifiers" |
| GS-D03 FAIL (zero-conv locations) | "Run `/geo-schedule-optimize geo` to exclude zero-conversion locations" |
| GS-D04 WARN (high-performing locations) | "Run `/geo-schedule-optimize geo` to boost high-performing locations — or consider dedicated campaigns (advisory)" |
| GS-D05 WARN (non-target spend) | "Run `/geo-schedule-optimize geo` to add location exclusions" |
| GS-D06 FAIL (device CPA variance) | "Run `/geo-schedule-optimize schedule` to apply device bid modifiers (or device exclusion for Smart Bidding)" |
| GS-D07 FAIL (dead time windows) | "Run `/geo-schedule-optimize schedule` to pause dead time windows" |
| GS-D08 WARN (unconfirmed patterns) | "Re-run `/geo-schedule-audit schedule` in 2 weeks to confirm pattern before acting" |
| GS-D09 WARN (modifier stacking) | "Run `/geo-schedule-optimize` to review and flatten stacked modifiers" |
| GS-D10 WARN (demographic outliers) | "Run `/geo-schedule-optimize demo` to apply demographic bid adjustments" |
| GS-D11 WARN (Smart Bidding conflict) | "Run `/geo-schedule-optimize` to remove ignored modifiers from Smart Bidding campaigns" |
| GS-D12 WARN (seasonal patterns) | "Flag for seasonal review — no automated action recommended" |
| GS-D13 FAIL (demographic exclusion) | "Run `/geo-schedule-optimize demo` to apply demographic exclusions (-100%)" |
| GS-D14 WARN (geo optimization opportunity) | "Advisory: consider dedicated campaign for high-performing locations" |
| Multiple FAILs across modules | "Run `/geo-schedule-optimize` (no subcommand) to apply all recommended changes" |
| All PASS | "Geo, schedule, and demographic targeting looks solid. Re-audit in 30 days." |

6. Note location of full report: `context/analysis/geo-schedule-audit.md`.

**Example summary output:**

```
## Geo-Schedule Audit Summary

Score: 62% — Needs Attention

### Top Issues

1. **GS-D03 FAIL** — 3 locations with zero conversions spending >2x target CPA ($847 wasted)
2. **GS-D07 FAIL** — 2 dead time windows (Mon 01:00-05:00, Sun 02:00-06:00) with 0 conversions over 6 weeks
3. **GS-D06 FAIL** — Tablet CPA 68% above account average ($43 vs $26)

### Recommended Next Step

Run `/geo-schedule-optimize` to apply all recommended changes (dry-run preview first).

Or target specific modules:
- `/geo-schedule-optimize geo` — fix location exclusions and modifiers
- `/geo-schedule-optimize schedule` — pause dead time windows and adjust schedule

Report: context/analysis/geo-schedule-audit.md
```

**Log to memory** per `memory-logging.md` rules:
```markdown
## Geo-Schedule Audit Completed
- Mode: {mode}
- Account: {customerId}
- Score: {score}% ({grade})
- Key findings: {list of FAIL/WARN items}
- Routing: {recommended commands}
- Report: context/analysis/geo-schedule-audit.md
```
