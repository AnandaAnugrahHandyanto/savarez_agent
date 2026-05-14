---
name: keyword-auditor
description: >
  Audit keyword health across 17 diagnostics in 5 modules. Scores 0-100 per module.
  AUTO-ACTIVATE for: "keyword audit", "check keywords", "keyword health",
  "keyword performance check", "audit keywords", "keyword score",
  "match type audit", "duplicate keywords", "keyword cannibalization".
---

# Keyword Auditor

Audit keyword set health across 17 diagnostics in 5 modules. Read-only — never modifies the account.

**Scores 0-100** using weighted diagnostics across:
1. Match Type Health (20 pts)
2. Performance Segmentation (30 pts)
3. Cannibalization & Duplicates (25 pts)
4. Keyword Hygiene (10 pts)
5. Intent Alignment (15 pts)

**Diagnostic ≠ pause recommendation.** Raw flags are *symptoms*. Phase 1.5 walks the constraint cascade **Measurement → Business → Conversion → Efficiency Recovery → Traffic/Creative** to form a root-cause hypothesis before any action is written. Never jump from "KW-D07 FAIL" to "pause these keywords" without the cascade. Pausing is always a last resort. See `reference/synthesis-playbook.md`.

**Handoff:** Actions route through `reference/handoff-matrix.md` — upstream skills (`/tracking-specialist`, `/strategy-specialist`, `/lp-auditor`, `/offer-auditor`) fire *before* `/keyword-optimize` whenever a Measurement, Business, or Conversion hypothesis is active.

---

## Command Routing

Parse the user's command to determine scope:

```
/keyword-auditor                    → Full audit (all 17 checks)
/keyword-auditor match-type         → Module 1: KW-D01 to KW-D04
/keyword-auditor performance        → Module 2: KW-D05 to KW-D09
/keyword-auditor duplicates         → Module 3: KW-D10 to KW-D13
/keyword-auditor hygiene            → Module 4: KW-D14 to KW-D15
/keyword-auditor intent             → Module 5: KW-D17 to KW-D18
/keyword-auditor {period}           → Full audit with custom period (30/60/90)
/keyword-auditor {module} {period}  → Module + period combo
```

Default evaluation period: **30 days**. Options: 30, 60, 90.

---

## Phase 0: Prerequisites & Data Collection

### Phase 0.0: Business Context Resolution (analyst judgment layer)

**Purpose:** Keyword audits are only meaningful when measured against real business economics (profitability thresholds, conversion action values, product relevance). The analysis script is deterministic — Claude interprets the freeform `business.md`, confirms with the user, and caches the result in `config/ads-context.config.json` → `keywordAudit`. On subsequent runs this is a one-line reconfirmation.

**Read:** `config/ads-context.config.json` → `keywordAudit` block.

**Branch A — Cached values exist and are fresh:**

Check: `keywordAudit.lastConfirmed` exists, AND `keywordAudit.businessMdHash` matches current hash of `business.md`, AND `lastConfirmed` is less than 60 days old.

If all three hold, show a single-line reconfirmation to the user:

> CPA mode: "Using cached business context: primary KPI **CPA**, break-even CPA **${breakEvenCPA}**, primary action **${primaryConversionAction}** (${conversionActionValues[primary]}), secondary actions **{list}**, relevance tokens **[{coreProductTokens}]**. Last confirmed {lastConfirmed}. Proceed? (y / update)"
>
> ROAS/POAS mode: "Using cached business context: primary KPI **ROAS or POAS**, break-even ROAS **${breakEvenROAS}**, primary action **${primaryConversionAction}** (${conversionActionValues[primary]}), secondary actions **{list}**, relevance tokens **[{coreProductTokens}]**. Last confirmed {lastConfirmed}. Proceed? (y / update)"

- If "y" or no objection → continue to Phase 0.1
- If "update" or any correction → jump to Branch B

**Branch B — First run, stale, or user requested update:**

Run the interview. Do NOT parse `business.md` with regex or assume field positions — read it as natural language and extract the concepts.

1. **Read `business.md`** and form a draft for each field below. If a concept isn't present, leave the draft blank and use an open question instead of a pre-filled suggestion.

2. **Read `config.googleAds.conversionActions`** — this is the authoritative list of Google Ads conversion action names already captured by the ads-context-gatherer skill. Never hardcode action names in this skill.

3. **Determine the primary KPI.** Read `config.searchTermAnalysis.biddingStrategy` — this indicates whether the account optimizes toward CPA or ROAS. If not set, infer from the dominant bidding strategy type across campaigns (TARGET_CPA / MAXIMIZE_CONVERSIONS → "cpa"; TARGET_ROAS / MAXIMIZE_CONVERSION_VALUE → "roas"). Confirm with user.

4. **Present draft → user interview:**

   > "I've read your business.md to set up the keyword audit. Please confirm or correct each:
   >
   > **1. Primary KPI:** `${draft_kpi}` (CPA or ROAS — determines which profitability gate drives the analysis)
   >
   > **2. Profitability threshold:**
   > - If CPA: **Break-even CPA** (highest CPA per conversion before it's considered waste):
   >   Draft: `${draft_max_cpa or "[not found — please provide]"}` — Source: `${quoted_snippet_from_business_md}`
   > - If ROAS: **Break-even ROAS** (lowest ROAS before it's considered waste, entered as a ratio — e.g. `5.3` for 530%, not `530`):
   >   Draft: `${draft_min_roas or "[not found — please provide]"}` — Source: `${quoted_snippet_from_business_md}`
   >
   > **3. Conversion action values** — I found these actions in your config: `${config.googleAds.conversionActions}`. Please confirm the $ value per action and which one is the primary KPI:
   > - `${action_1}`: Draft value `${draft_value_1}` → primary? (y/n)
   > - `${action_2}`: Draft value `${draft_value_2}` → primary? (y/n)
   >
   > **4. Core product tokens** (keywords containing these get extra patience before being flagged for pause — typically your product category, platform, or defining features):
   > Draft: `${draft_tokens or "[please list 5-10]"}` — Source: `${quoted_what_we_sell_snippet}`
   >
   > Reply field-by-field or paste corrected values. I'll save to ads-context.config.json."

5. **Handle the no-values-available case:** If user cannot provide the profitability threshold or conversion action values, do NOT silently fall back. Stop with:

   > "Cannot produce a business-grounded keyword audit without a profitability threshold and conversion action values. Options:
   > (a) provide the values now, or
   > (b) proceed in fallback mode — audit will use campaign targets only, and every report will carry a caveat that analysis is limited without true business targets. Which would you like?"

   If user picks (b) → set `targetFallbackMode: "campaign_target_only"` in config. The report must include a warning banner in every section that uses profitability thresholds.

6. **Write to `ads-context.config.json`** → `keywordAudit` block:
   - `primaryKPI` ("cpa" or "roas")
   - `breakEvenCPA` (number, required when primaryKPI = "cpa")
   - `breakEvenROAS` (number, required when primaryKPI = "roas")
   - `conversionActionValues` (object mapping action name → number)
   - `primaryConversionAction` (string — one of the action names)
   - `coreProductTokens` (array of lowercase strings)
   - `lastConfirmed` (ISO date string, today)
   - `businessMdHash` (SHA-256 first 16 chars of current business.md content)
   - `targetFallbackMode` (null or "campaign_target_only")

7. **Action name alignment:** The action names written to `conversionActionValues` must exactly match the strings in `config.googleAds.conversionActions` (case-sensitive). If the user's business.md uses a slightly different spelling, use the Google Ads config spelling and note the alignment to the user before saving.

### Phase 0.1: Config Validation

Read `config/ads-context.config.json`:

1. **keywordAudit section — required analyst-cached values** (populated by Phase 0.0):
   - `primaryKPI` ("cpa" or "roas")
   - `breakEvenCPA` (required when primaryKPI = "cpa") or `breakEvenROAS` (required when primaryKPI = "roas") — or `targetFallbackMode: "campaign_target_only"`
   - `conversionActionValues`
   - `primaryConversionAction`
   - `coreProductTokens`

   If any are missing after Phase 0.0, stop and re-run Phase 0.0.

2. **Other required config values:**
   - `searchTermAnalysis.conversionLagDays` (e.g., 8)
   - `searchTermAnalysis.brandedCampaigns` (array of branded campaign names)
   - `searchTermAnalysis.biddingStrategy` ("cpa" or "roas")
   - `keywordAudit.*` static threshold values

3. **Read context/business.md** — Extract brand name, vertical, target metrics for D17/D18. (Business economics already resolved in Phase 0.0 — do not re-parse.)

4. **Ask user:** Evaluation period (30/60/90, default 30). If user passed period in command, use that.

5. **Compute date ranges:**
   ```
   conversionLagDays = config.searchTermAnalysis.conversionLagDays
   evaluationPeriod  = user-selected: 30 | 60 | 90

   Period A (current):
     end   = today - conversionLagDays
     start = end - evaluationPeriod + 1

   Period B (prior, for D09 tier shifts):
     end   = Period_A_start - 1
     start = end - evaluationPeriod + 1
   ```

6. **Confirm with user:** "Using {period}-day evaluation period with {lag}-day conversion lag. Period A: {start} → {end}. Period B: {start} → {end}. OK?"

### Phase 0.2: Data Pull

Pull all 9 queries in a single batch call:

```bash
node .claude/skills/keyword-auditor/scripts/pull-all.js \
  --period={evaluationPeriod} --lag={conversionLagDays}
```

This runs every query listed below in one process (delegating each to `query.js`), writing CSVs to `context/google-ads/data/`:

| # | Output | Source GAQL | Date handling |
|---|--------|------------|---------------|
| Q1 | `keywords-periodA.csv` | `keywords-period.gaql` | `--days={period} --lag-offset={lag}` |
| Q2 | `keywords-periodB.csv` | `keywords-period.gaql` | `--days={period} --lag-offset={lag + period}` |
| Q2a | `keywords-conv-by-action-periodA.csv` | `keywords-conversions-by-action.gaql` | Period A offsets |
| Q2b | `keywords-conv-by-action-periodB.csv` | `keywords-conversions-by-action.gaql` | Period B offsets |
| Q3 | `keywords-structural.csv` | `keywords-structural.gaql` | `--no-date-range` |
| Q4 | `campaigns-settings.csv` | `campaigns-settings.gaql` | `--no-date-range` |
| Q5 | `pmax-search-terms.csv` | `pmax-search-terms.gaql` | Period A offsets |
| Q6 | `negatives-campaign-kw.csv` | `negatives-campaign.gaql` | `--no-date-range` |
| Q7 | `negatives-shared-kw.csv` | `negatives-shared.gaql` | `--no-date-range` |
| Q8 | `negatives-shared-campaigns.csv` | `negatives-shared-campaigns.gaql` | `--no-date-range` |
| Q9 | `negatives-adgroup-kw.csv` | `negatives-adgroup.gaql` | `--no-date-range` |

The script prints a per-query row count and a `__RESULTS_JSON__` summary on the last line. Parse that to report totals to the user. If any query errors, the script exits with code 1 — surface the error before proceeding to Phase 0.3.

Tell the user: "Pulled {N} keywords across {M} campaigns. Running analysis..."

### Phase 0.3: Script Execution

Run both analysis scripts:

```bash
# Performance analysis: tier classification + mechanical flags
node .claude/skills/keyword-auditor/scripts/analyze-keyword-performance.js \
  --period-a-csv=context/google-ads/data/keywords-periodA.csv \
  --period-b-csv=context/google-ads/data/keywords-periodB.csv \
  --conv-by-action-a-csv=context/google-ads/data/keywords-conv-by-action-periodA.csv \
  --conv-by-action-b-csv=context/google-ads/data/keywords-conv-by-action-periodB.csv \
  --campaigns-csv=context/google-ads/data/campaigns-settings.csv \
  --portfolios-csv=context/google-ads/data/bidding-strategies.csv \
  --tiers-output=context/google-ads/data/keyword-tiers.csv \
  --flags-output=context/google-ads/data/keyword-flags.csv

# Overlap analysis: duplicates, conflicts, PMax overlap, negative coverage
node .claude/skills/keyword-auditor/scripts/analyze-keyword-overlap.js \
  --structural-csv=context/google-ads/data/keywords-structural.csv \
  --period-a-csv=context/google-ads/data/keywords-periodA.csv \
  --pmax-csv=context/google-ads/data/pmax-search-terms.csv \
  --negatives-campaign-csv=context/google-ads/data/negatives-campaign-kw.csv \
  --negatives-shared-csv=context/google-ads/data/negatives-shared-kw.csv \
  --campaign-shared-sets-csv=context/google-ads/data/negatives-shared-campaigns.csv \
  --negatives-adgroup-csv=context/google-ads/data/negatives-adgroup-kw.csv \
  --output=context/google-ads/data/keyword-overlaps.csv
```

Check script output for data sufficiency warnings. If <15 conversions in period:
- Surface warning to user
- Ask: "Only {N} conversions in {period}-day window. Re-run with longer window (/keyword-auditor {next_period}), or proceed with current data?"

Tell the user: "Analysis complete. {X} keyword flags + {Y} overlap issues."

---

## Phase 1: Run Diagnostics

Read the reference file `.claude/skills/keyword-auditor/reference/diagnostic-rules.md` for full diagnostic specifications.

**CRITICAL:** Read from the pre-processed script outputs (`keyword-tiers.csv`, `keyword-flags.csv`, `keyword-overlaps.csv`), NOT the raw GAQL CSVs. The scripts have already done the heavy computation. For structural checks (D15), read `keywords-structural.csv`.

### Data sources per diagnostic:

| Diagnostic | Primary Source | Secondary Source |
|-----------|---------------|-----------------|
| KW-D01 | keyword-tiers.csv (aggregate by campaign) | — |
| KW-D02 | keyword-flags.csv → BROAD_WITHOUT_SMART_BIDDING | — |
| KW-D03 | keyword-overlaps.csv → `flag_type=MATCH_TYPE_REDUNDANCY` | — |
| KW-D04 | keyword-overlaps.csv → `flag_type=CROSS_CAMPAIGN_MATCH_CONFLICT` | — |
| KW-D05 | keyword-tiers.csv → tier=HERO | — |
| KW-D06 | keyword-tiers.csv (full dataset) | — |
| KW-D07 | keyword-flags.csv → UNPROFITABLE + PAUSE_CANDIDATE (+ OVER_TARGET info) | — |
| KW-D08 | keyword-flags.csv → ZOMBIE + LOW_PERFORMER | — |
| KW-D09 | keyword-flags.csv → TIER_DEGRADED | — |
| KW-D10 | keyword-overlaps.csv → `flag_type=DUPLICATE_KEYWORD` | — |
| KW-D11 | keyword-tiers.csv (grouped by ad group) | Claude reasoning |
| KW-D12 | keyword-overlaps.csv → `flag_type=PMAX_OVERLAP` | — |
| KW-D13 | keyword-tiers.csv (broad match, same AG) | Claude reasoning |
| KW-D14 | keyword-flags.csv → BELOW_FIRST_PAGE_BID | — |
| KW-D15 | keywords-structural.csv → system_serving_status | — |
| KW-D17 | keyword-tiers.csv (keyword text analysis) | Claude reasoning |
| KW-D18 | keyword-tiers.csv (keyword text analysis) | business.md brand name, config brandedCampaigns |

### Module execution based on command scope:

| Command | Modules to Run |
|---------|---------------|
| (full) | All 5 modules |
| match-type | Module 1 only |
| performance | Module 2 only |
| duplicates | Module 3 only |
| hygiene | Module 4 only |
| intent | Module 5 only |

For each diagnostic, assign a verdict: **PASS**, **WARN**, **FAIL**, **SKIP**, or **INFO**.

### Claude reasoning diagnostics (D11, D13, D17, D18):

These require reading keyword text and applying semantic analysis:

**D11 (Cannibalization):** Read keyword-tiers.csv grouped by ad group across campaigns. Look for:
- Different keywords targeting the same searcher intent
- Keywords in different ad groups that would match the same queries
- Ad groups competing for the same auction
If cannibalization stems from poor AG structure, flag for `keyword-restructurer`.

**D13 (Similar broad match):** Read keyword-tiers.csv, filter to broad match within same ad group. Identify semantic variants (e.g., "crm software" and "crm tool" and "crm platform") where one broad keyword would cover the others.

**D17 (Informational intent):** Read each keyword and flag ones seeking information rather than a product/service — language-agnostic semantic analysis (research queries, how-to/what-is phrasings, comparisons, tutorials, definitions in any language). Cross-reference with campaign goal.

**D18 (Brand terms):** Check keyword text against brand name from `business.md` and competitor names. Identify misspellings, abbreviations, brand+modifier combos. Cross-reference with `config.searchTermAnalysis.brandedCampaigns`.

---

## Phase 1.5: Synthesis & Constraint Cascade (MANDATORY)

**Read `.claude/skills/keyword-auditor/reference/synthesis-playbook.md` in full before writing any recommendation.** This phase is non-optional. Skipping it produces mechanically-correct but strategically-wrong reports (e.g., "pause the core product terms that are the front door of your business").

Output of this phase is a **ranked hypothesis list** that drives Phase 2's report structure and Phase 3's handoff offer. Each hypothesis carries: layer (Measurement/Business/Conversion/Traffic/Creative), evidence, confidence, whether it blocks downstream actions, and the upstream skill handoff.

### Required checks (see playbook for thresholds and formulas)

1. **Measurement layer** — M1 duplicate criterion_id attribution anomalies, M2 zero-conv concentration in one campaign, M3 conversion-lag vs window mismatch, M4 tier volatility. Any trip → Measurement hypothesis is active and **blocks** all KW-D07 pause recommendations.

2. **Business layer** — B1 bleed_ratio (campaign target vs profitability threshold; < 0.5 flags bid bleeding), B2 stale profitability threshold, **B3 core-term concentration in UNPROFITABLE** (the single most important rule — if ≥50% of UNPROFITABLE spend is on `is_core_term=true`, **do not recommend pause**; route to `/lp-auditor` + `/offer-auditor` + adjust target), B4 single-campaign concentration.

3. **Conversion layer** — C1 funnel step ratio drift between Period A and Period B (micro→macro efficiency degrading >15%), C2 healthy micro-conv efficiency but unhealthy macro-conv efficiency.

4. **Efficiency Recovery layer** — ER1 search term verification via `/search-term-auditor ngrams` (120–180d), ER2 offer quality recovery via `/offer-auditor`, ER3 LP quality recovery via `/lp-auditor`, ER4 goal/economics viability via `/strategy-specialist`, ER5 bid optimization via `/bidding-specialist` (future). **Pausing is always a last resort** — the report must present efficiency recovery options before any pause recommendation.

5. **Traffic/Creative layer** — T1 safe-to-pause filter: a keyword is only recommended for pause if **all** of (no active M hypothesis blocking its campaign, no B1 bleeding on its campaign OR target adjustment sequenced first, `is_core_term=false`, no C hypothesis active, efficiency recovery sequence presented) hold. T2 always-safe structural fixes (duplicates, match conflicts, zombies, branded below-first-page bids, obvious informational keywords). T3 OVER_TARGET is never a pause signal.

### What to produce

An ordered hypothesis list ranked by layer (Measurement first, then Business, then Conversion, then Traffic) and within each layer by explained waste %. Each hypothesis drives one row in Phase 2's **Evidence Ladder** and one entry in Phase 2's **Actions** section, routed to the right bucket: `🔍 Investigate first`, `🔧 Structural fix needed`, or `✅ Act now (safe)`.

**Explicit anti-patterns — never do these:**

- Writing "Pause these 47 UNPROFITABLE keywords" when B3 core-term concentration ≥ 50%. The correct output is "These keywords are your front door — the problem is somewhere else. Run `/lp-auditor`, `/offer-auditor`, and adjust campaign X's target first."
- Writing any pause recommendation while a Measurement hypothesis is unresolved. The correct output is "Pending `/tracking-specialist` — verify attribution before acting."
- Writing any pause recommendation without first presenting the efficiency recovery sequence (Layer 4: n-gram analysis, offer audit, LP audit, strategy review, bid optimization). Pausing is always a last resort.
- Mixing OVER_TARGET keywords into any pause list. They are profitable by the profitability threshold gate.
- Flat "Recommended Actions" table that treats a tracking anomaly and a keyword pause at equal weight. Always segment by cascade state.

---

## Phase 2: Score & Log

Read `.claude/skills/keyword-auditor/reference/scoring-model.md` for the scoring model.

### Scoring summary:
- PASS = full points retained
- WARN = deduct 40% of check's points
- FAIL = deduct 100% of check's points
- SKIP = excluded from scoring (reduce denominator)
- INFO = no points at stake

Compute: `score = points_earned / (100 - skipped_points) * 100`

### Grade thresholds:
| Score | Grade |
|-------|-------|
| 90-100 | Excellent |
| 70-89 | Good |
| 50-69 | Needs Attention |
| <50 | Critical |

### Append to audit log `context/analysis/keyword-audit-log.md`

If the file does not exist, create it with the header `# Keyword Audit Log`. Append a timestamped entry using the log template in `reference/report-template.md` — the entry leads with `## {date} — Score: X% ({grade})`, includes a top-finding line and a "fresh peer reports integrated" line, and preserves history (never overwrites).

The log append happens **before** Phase 2.5 so the historical record exists even if peer lookup fails. The Phase 4 report is the only artifact regenerated each run.

---

## Phase 2.5: Peer Report Lookup (MANDATORY before writing the report)

**Don't send the user from one door to the other.** Before recommending any peer-skill handoff in Phase 3 (or in the report's Actions section), check whether that peer has already produced a fresh report — and if so, **read it and integrate its findings into THIS report** instead of asking the user to re-run.

The whole point of cross-skill awareness is that a user who runs `/tracking-specialist` last week and then runs `/keyword-auditor` this week sees the tracking findings *quoted inside the keyword report*, not a redundant "go run tracking" instruction. Re-running an auditor that already produced a fresh answer wastes time and obscures the keyword-side action.

#### Freshness windows

| Peer skill | Report file | Fresh window |
|---|---|---|
| `/quality-score-auditor` | `context/analysis/quality-score-audit.md` | ≤ 7 days |
| `/search-term-auditor` | `context/analysis/search-term-audit.md` | ≤ 7 days |
| `/budget-auditor` | `context/analysis/budget-audit.md` | ≤ 7 days |
| `/bidding-auditor` | `context/analysis/bidding-audit.md` | ≤ 7 days |
| `/competitive-analyst` | `context/analysis/competitive-audit.md` | ≤ 14 days |
| `/lp-auditor` | `context/analysis/lp-audit.md` | ≤ 14 days |
| `/offer-auditor` | `context/analysis/offer-audit.md` | ≤ 30 days |
| `/tracking-specialist` | `context/analysis/tracking-audit.md` | ≤ 30 days |
| `/strategy-specialist` | `context/analysis/strategy-audit.md` | ≤ 30 days |
| `/account-auditor` | `context/analysis/account-audit.md` | ≤ 30 days |

#### Procedure for each peer that the routing would otherwise hand off to

1. **Check if the file exists.** If not → keep the handoff as a plain "run `/peer-skill`" line.
2. **If it exists, check the date in the report header against the freshness window.** The report header date is canonical. mtime is a sanity check — if mtime is *older* than the header date, warn the user that something is off.
3. **If fresh:** open the report and read its **executive read / diagnosis / top findings / module scores**. Pull out the 1–3 findings that overlap with this audit's flagged keywords, ad groups, or campaigns. Use them to:
   - **Enrich the Executive read at the top of `keyword-audit.md`** — quote the peer's score, the headline finding, and the date inline.
   - **Replace** the routing line "run `/peer-skill`" with: **"Review the existing {date} {peer} report at {path} — top finding: '{one-liner}'. Re-run only if you want fresher data."**
   - In the Investigate-first / Structural-fix / Recover-efficiency action tables, when a peer handoff is the recommended action, quote the peer's specific finding so the user can act without leaving this report.
4. **If stale:** mention "a previous {peer} report exists from {date} but is {N} days old — recommend re-running before relying on it" and keep the handoff as a re-run.
5. **If missing:** standard "run `/peer-skill`" handoff.

#### When a fresh peer report contradicts a keyword hypothesis

Say so explicitly in the Executive read. Surface the contradiction — never auto-defer or auto-override. Examples:

- keyword-auditor's Phase 1.5 raises a Measurement hypothesis (M1 attribution anomaly) — but the fresh tracking-audit shows tracking is healthy with no duplicate-attribution issue. The keyword report must say so and downgrade M1's confidence, not silently keep blocking pauses.
- keyword-auditor flags `KW-D07 UNPROFITABLE` for a campaign — but the fresh search-term-audit already isolated the bad n-gram driving the waste. Quote that finding inline so the user excludes the n-gram instead of pausing the keyword.
- keyword-auditor's B3 core-term concentration says "don't pause, fix the offer" — but a fresh offer-audit shows the offer scores high and a fresh lp-audit shows the LP is solid. Then the bleed is unlikely to be offer/LP-driven; redirect the structural-fix recommendation to `/strategy-specialist` (target/economics) or `/bidding-auditor` (bid strategy) and say so.

That cross-skill validation is the entire reason this phase exists. A keyword audit that ignores a fresh tracking, search-term, offer, or LP audit produces a confidently-wrong recommendation.

---

## Phase 2.6: Write Report

Write `context/analysis/keyword-audit.md` using `reference/report-template.md`.

This report is regenerated on each run (overwrites previous). The log (Phase 2) preserves history.

**Lead with the Executive read** — the 6-slot prose contract defined in `reference/report-template.md`, placed at the very top of the report before the Business Context box and Diagnosis section. Apply Phase 2.5 lookup results to slot 4 (inline-quoted fresh peer findings) and to every line in the Actions tables that points to a peer skill.

Fill in all sections in this order:

1. **Executive read** (prose, ≤300 words, no bullets) — score meaning, 1–3 priorities w/ why, what's NOT a problem, fresh peer findings inline, how-to-read, score trend.
2. **Business Context box** — profitability threshold, primary KPI, core product tokens, fallback mode caveat if applicable.
3. **Diagnosis** — one paragraph stating the root-cause hypothesis, the cascade layer, and what the reader should do first. Written as natural language, not a bullet list.
4. **Evidence Ladder** — grouped by cascade layer (Measurement, Business, Conversion, Traffic/Creative). Only layers with active hypotheses get expanded. Each bullet is a factual observation that supports a specific hypothesis (tagged `→ H{n}`).
5. **Module Scores** — standard 5-row table.
6. **Actions — segmented by cascade state:**
   - `🔍 Investigate first` — blocking upstream handoffs (Measurement / Business / Conversion hypotheses). Apply Phase 2.5 results: every peer handoff says either "run /peer" (missing/stale) or "review existing {date} report at {path}" (fresh, with the one-liner finding).
   - `🔧 Structural fix needed` — routes to `/lp-auditor`, `/offer-auditor`, `/strategy-specialist`, or campaign-level target adjustment. Same Phase 2.5 substitution rule.
   - `🔄 Recover efficiency first` — ER1–ER5 sequence for UNPROFITABLE keywords that passed Layers 1–3. When a peer report (search-term, offer, LP, strategy) is fresh, quote its finding inline instead of asking the user to re-run.
   - `✅ Act now (safe)` — only keywords that survived the T1 safe-to-pause filter + always-safe T2 fixes (duplicates, match conflicts, zombies, informational). Pause is framed as last resort after recovery options.
   - `⚠️ Do NOT pause` — OVER_TARGET list with reasoning.
7. **Module Details** — full per-diagnostic breakdown for reference.

Never emit a flat "Recommended Actions" table that mixes a tracking anomaly with a keyword pause at equal weight — the segmentation is the whole point.

---

## Phase 3: Present Results & Sequenced Handoff

Already written in Phase 2.6; Phase 3 is the user-facing presentation. The reader should be able to act from the **Executive read alone** — that's the bar. Everything else is reference material.

Print to user, in this order:

1. **Executive read** (the prose section from the report — quote it verbatim, don't re-summarize). It already covers score-meaning, this-week priorities w/ why, what's-NOT-a-problem, fresh peer findings inline, how-to-read, score trend.
2. **Score, grade, and headline diagnosis** — the diagnosis paragraph from Phase 2.6. Lead with "The problem is at the {layer} layer — {one-sentence root cause}."
3. **Top hypothesis** — name, layer, evidence, confidence, explained waste %.
4. **Module scores** — 5-row table.
5. **Sequenced handoff offer** — see below. Never present the handoffs as a flat menu. Apply Phase 2.5 lookup results to every peer handoff line: each one says either "review existing {date} report at {path} (top finding: ...)" or "run `/peer-skill`".
6. Note location of full report: `context/analysis/keyword-audit.md`.

### Sequenced handoff offer

Read `.claude/skills/keyword-auditor/reference/handoff-matrix.md` for the full mapping. The offer is always sequenced by cascade layer — Measurement → Business → Conversion → Traffic — not by convenience.

Template:

> **Top hypothesis:** {layer} — {name} (explains ~{pct}% of flagged waste)
>
> Before I touch any keywords, here's what I'd run in order:
>
> 1. **{blocking Measurement handoff}** — {one-sentence why} → `/{skill}`
> 2. **{Business-layer handoff}** — {one-sentence why} → `/{skill}`
> 3. **Verify at search-term level** — `/search-term-auditor ngrams` over 120–180d to check if specific n-grams explain the waste (exclude those instead of pausing keywords)
> 4. **Recover efficiency** — `/offer-auditor` + `/lp-auditor` to improve CVR, `/strategy-specialist` to validate targets
> 5. **Safe structural fixes** (always safe): `/keyword-optimize duplicates` ({N} groups), `/keyword-optimize match-type` ({M} groups), `/keyword-optimize cleanup` ({K} zombies)
>
> Only after (1)–(4) are exhausted would I recommend pausing — and only as a last resort, only on the **{K} non-core** keywords that survive the cascade — **not** the **{J} core product terms** in the UNPROFITABLE list (those are your front door — pausing them is almost certainly wrong).
>
> Which would you like to start with?

**When no upstream hypothesis is active** (Measurement, Business, Conversion all clear), the offer reverts to the standard menu — but still ordered by safety, not by alphabet:

> "Found {N} actionable issues. Cascade layers 1–3 clear. Ordered by priority:
>
> - **Safest (always-safe structural fixes):** `/keyword-optimize duplicates`, `/keyword-optimize match-type`, `/keyword-optimize cleanup`
> - **Recover efficiency first ({X} UNPROFITABLE keywords):** Before pausing, try these in order:
>   1. `/search-term-auditor ngrams` (120–180d) — verify at search-term level
>   2. `/offer-auditor` + `/lp-auditor` — improve CVR
>   3. `/strategy-specialist` — validate targets
> - **Last resort pauses (non-core, after recovery):** `/keyword-optimize pause` — only after efficiency recovery is exhausted
> - **Bid review (profitable, beyond target):** `/keyword-optimize bids` — {Y} OVER_TARGET keywords. **Never pause these.**"

Only show subcommands that have findings to act on. Never list `/keyword-optimize pause` when B3 core-term concentration is ≥ 50% — replace it with the structural handoff. Even when B3 is clear, always present the efficiency recovery sequence before pause.

---

## Edge Cases

| Scenario | Handling |
|----------|---------|
| Single campaign account | Skip cross-campaign checks (D04 cross-campaign, D10 cross-campaign, D12). Note in report. |
| No PMax campaigns | Skip D12. Note in report. |
| All broad on smart bidding | D02=PASS. D01=INFO showing 100% broad (valid modern strategy). |
| All exact on Manual CPC | Valid. D02=PASS. D01=INFO, note if >30 conv/month could benefit from broad+smart. |
| Campaign has 0 conversions | Use cost as proxy. Note "no conversions — efficiency unavailable." |
| Recently created keyword (<14 days) | Current dataset does not include created date. Do not auto-exclude; note the limitation if freshness is a concern. |
| QS = null | Include in analysis, exclude from QS context. Note count. |
| Very large account (>5000 KW) | Scripts handle volume. Claude sees only flagged items. Report summarizes totals. |
| Brand name is common word | Flag as "potential brand term — verify" not definitive. |
| Portfolio bid strategy | Resolved automatically: `bidding-strategies.csv` is joined on `campaign.bidding_strategy`. Each keyword row carries `target_source` (`campaign_inline` \| `portfolio` \| `fallback`) and `portfolio_name`. Synthesis must treat `target_source=portfolio` as a constrained campaign (target exists) and reserve the "unconstrained / effective Maximize Conv Value" finding for rows where `target_source=fallback`. When any campaign is on a portfolio, surface the portfolio name(s) and tROAS/tCPA in Module 2 so the assumption is visible. |
