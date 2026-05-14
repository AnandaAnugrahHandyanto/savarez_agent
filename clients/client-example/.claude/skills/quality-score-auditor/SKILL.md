---
name: quality-score-auditor
description: >
  Audit Quality Score health across 16 diagnostics in 4 modules (distribution, components,
  trends, competitive). Scores 0-100 per module. Diagnose-only — findings route to
  /rsa-maker, /offer-maker, /lp-optimizer via a handoff matrix.
  AUTO-ACTIVATE for: "quality score audit", "QS audit", "check quality score",
  "ad relevance audit", "expected CTR audit", "landing page experience audit",
  "QS health", "QS declining", "QS by campaign", "QS by ad group".
argument-hint: "[module] [period]"
---

# Quality Score Auditor

Audit Quality Score health across 16 diagnostics in 4 modules. Read-only — never modifies the account, never writes fixes.

**Scores 0-100** using weighted diagnostics across:

1. **QS Distribution** (20 pts) — account-level weighted QS, low-QS concentration, high-spend/low-QS, per-campaign / per-ad-group rollups
2. **Component Breakdown** (45 pts) — AR, ECTR, LP health + dominant limiting component
3. **Historical Trends** (15 pts) — account QS trend, per-component trends, post-optimization correlation, seasonal
4. **Competitive Context** (20 pts) — Lost-IS-Rank vs QS, CPC premium by QS tier

**Diagnose-only.** No RSA writes, no LP changes, no offer rewrites, no keyword pauses. Actions route through `reference/handoff-matrix.md` to `/rsa-maker`, `/offer-maker`, `/lp-optimizer`.

**Two-cascade synthesis (Phase 1.5).** Raw flags are symptoms:

- **Outer cascade (whole-business):** does QS *matter* for this campaign's bidding mode? Manual CPC → direct CPC impact (high severity). Smart Bidding → algorithm compensates at CPC (severity annotated `(dampened)`, never silenced).
- **Inner cascade (creative):** AR → ECTR → LP, per `sops/Improve Quality Score.md`. AR fixes block ECTR work. LP runs in parallel.
- **Keyword classifier:** `BRANDED` (escalate — usually tracking/LP), `COMPETITOR` (AR Below Avg is structural — do not fix), `INFORMATIONAL` (Claude semantic overlay — route to `/keyword-auditor` instead), `GENERIC` (standard cascade).

See `reference/synthesis-playbook.md` for the full cascade logic and anti-patterns.

---

## Command Routing

```
/quality-score-auditor                        Full audit (all 4 modules, 16 diagnostics)
/quality-score-auditor distribution           Module 1 only (QS-D01 to QS-D06)
/quality-score-auditor components             Module 2 only (QS-D07 to QS-D10)
/quality-score-auditor trends                 Module 3 only (QS-D11 to QS-D14)
/quality-score-auditor competitive            Module 4 only (QS-D15 to QS-D16)
/quality-score-auditor {period}               Full, custom period (30/60/90)
/quality-score-auditor {module} {period}      Module + period combo
/quality-score-auditor "AG Name"              Scoped to one ad group (cross-module)
```

Default evaluation period: **30 days**. Options: 30, 60, 90. Default historical period (M3): **180 days**.

---

## Phase 0: Prerequisites & Data Collection

### Phase 0.0: Business Context Resolution

**Purpose:** QS findings are only meaningful when COMPETITOR and BRANDED campaigns are classified correctly. COMPETITOR AR Below Avg is structural (conquesting), not a bug — misclassifying it produces "pause the brand" level wrong recommendations. The classifier depends on configured campaign lists.

**Read:** `config/ads-context.config.json` → `qualityScoreAudit`.

**Branch A — cached values exist and are fresh:**

Check: `qualityScoreAudit.lastConfirmed` exists AND `businessMdHash` matches current hash of `business.md` AND `lastConfirmed` is less than 60 days old.

If all three hold, one-line reconfirmation:

> "Using cached QS context: primary KPI **{primaryKPI}**, competitor campaigns **{list or 'none'}**, branded campaigns **{list}**, eval period **{n}d**, history **{n}d**, currency **{accountCurrency}**. Last confirmed {date}. Proceed? (y / update)"

If "y" or no objection → Phase 0.1. If "update" → Branch B.

**Branch B — first run, stale, or user requested update:**

1. Read `business.md` + existing config.
2. Read `config.searchTermAnalysis.brandedCampaigns` (authoritative for BRANDED class) and `config.keywordAudit.primaryKPI` (pre-fill).
3. Pull campaign names from Google Ads (or read `context/google-ads/data/campaigns-settings.csv` if fresh). Scan for competitor signals: any campaign name containing `conquest`, `competitor`, `conquesting`, or matching rival brand names from `business.md`.
4. Present step-through interview:

   > "I've read your business.md and scanned your campaign list for conquesting signals. Please confirm or correct:
   >
   > **1. Primary KPI:** `${draft_kpi}` (CPA or ROAS)
   >
   > **2. Evaluation period:** 30 / 60 / 90 days (default 30)
   >
   > **3. Historical period for trends:** `${history}` days (default 180)
   >
   > **4. Competitor campaigns** — I scanned your campaign list and found these conquesting-style names:
   > - `${scanned_1}`
   > - `${scanned_2}`
   >
   > Is this list correct? (add / remove / confirm)
   >
   > Reason I ask: on COMPETITOR campaigns, Ad Relevance Below Avg is structurally expected (you're targeting a rival's brand with your own ad). If I misclassify these, I'll wrongly recommend AR fixes.
   >
   > **5. Competitor brand names** (for keyword-text-level checks, optional): `${draft_or_'none'}`
   >
   > **6. Thresholds** — SOP defaults loaded. Any overrides? (review `qualityScoreAudit.thresholds` or type 'accept defaults')"

5. If user cannot confirm competitor campaigns, save `competitorCampaigns: []`. Classifier treats everything as GENERIC. Report carries a banner that conquesting campaigns (if any) may have structurally expected AR findings — re-run Phase 0.0 to classify.

6. **Currency:** If top-level `accountCurrency` is missing (or not a valid ISO-4217 three-letter code), ask:
   > "Account currency? (default USD)"

   Write to top-level config (shared with budget-auditor and other peers — never inside `qualityScoreAudit`).

7. Write `qualityScoreAudit` block with `lastConfirmed = today (YYYY-MM-DD)` and `businessMdHash = first16(sha256(business.md))`.

See `reference/configuration.md` for full config schema.

### Phase 0.1: Prerequisites & Early Exits

**Read `context/google-ads/data/campaigns-settings.csv`** (or pull fresh in Phase 0.2 if missing).

**Early exits:**

- **PMax-only or no enabled Search campaigns:** Stop. Message: *"Quality Score is a Search-campaign concept. No enabled Search campaigns found. Nothing to audit."*
- **Fresh account (<60 days old based on business.md or earliest campaign date if inferable):** Proceed with M1/M2/M4; M3 SKIPs with a data-sufficiency note.

**Date ranges:**

```
conversionLagDays = config.searchTermAnalysis.conversionLagDays ?? 8
evaluationPeriod  = user-selected (30 | 60 | 90)
historicalPeriod  = user-selected (default 180)
```

Confirm with user: "Using {period}d evaluation window with {lag}d conversion lag, and {history}d history for M3 trends. OK?"

### Phase 0.2: Data Pull

```bash
node .claude/skills/quality-score-auditor/scripts/pull-all.js \
  --period={evaluationPeriod} --lag={conversionLagDays} --history={historicalPeriod}
```

This runs all 11 GAQL files in one process (delegating to `gads-context/scripts/query.js`), writing CSVs to `context/google-ads/data/`:

| # | Output | Source | Date handling |
|---|---|---|---|
| Q1 | `keywords-qs-period.csv` | `keywords-qs-period.gaql` | `--days={period} --lag-offset={lag}` |
| Q2 | `keywords-qs-timeseries.csv` | `keywords-qs-timeseries.gaql` | `--days={history} --lag-offset={lag} --allow-empty` |
| Q3 | `qs-ads.csv` | `ads.gaql` | `--no-date-range --allow-empty` |
| Q4 | `campaigns-settings.csv` | `campaigns-settings.gaql` | `--no-date-range` |
| Q5 | `bidding-strategies.csv` | `bidding-strategies.gaql` | `--no-date-range --allow-empty` |
| Q6 | `campaigns-is.csv` | `campaigns-is.gaql` | `--days={period} --lag-offset={lag}` (authoritative D15 source) |
| Q7 | `customizer-attributes.csv` | `customizer-attributes.gaql` | `--no-date-range --allow-empty` (feeds Headline Test + D17) |
| Q8 | `ad-group-customizers.csv` | `ad-group-customizers.gaql` | `--no-date-range --allow-empty` |
| Q9 | `keyword-customizers.csv` | `keyword-customizers.gaql` | `--no-date-range --allow-empty` |
| Q10 | `campaign-customizers.csv` | `campaign-customizers.gaql` | `--no-date-range --allow-empty` |
| Q11 | `customer-customizers.csv` | `customer-customizers.gaql` | `--no-date-range --allow-empty` |

Parse the `__RESULTS_JSON__` summary. If any query errors, surface before proceeding.

Tell the user: *"Pulled {N} keyword-period rows, {M} timeseries rows, {K} RSAs across {J} campaigns. Running analysis..."*

### Phase 0.3: Script Execution

Run both analysis scripts:

```bash
# Point-in-time: tier classification, class assignment, flags
node .claude/skills/quality-score-auditor/scripts/analyze-quality-score.js

# Time-series: trajectory per keyword, component trends, changelog correlation
node .claude/skills/quality-score-auditor/scripts/analyze-qs-trends.js

# Customizer integrity: per-AG summary + broken-setup detection (feeds Headline Test + D17)
node .claude/skills/quality-score-auditor/scripts/analyze-customizers.js
```

Outputs (read by Phase 1):
- `context/google-ads/data/qs-tiers.csv` — one row per keyword (tier, class, components, high-spend flag, priority score)
- `context/google-ads/data/qs-flags.csv` — one row per flagged keyword-diagnostic pair
- `context/google-ads/data/qs-trends.csv` — one row per keyword with trajectory + slope (empty if no history)
- `context/google-ads/data/qs-customizers.csv` — one row per ad group with customizer-binding state, RSA references, `effective_resolution` (per referenced attribute: `KEYWORD` / `AD_GROUP` / `CAMPAIGN` / `CUSTOMER` / `NONE` / `MISSING`), and `integrity_status` (OK / NO_CUSTOMIZERS / BROKEN / EFFECTIVELY_STATIC) + `headline_test_mode` (STANDARD / AG_LEVEL_CONSTANT / RELAXED_KW_LEVEL)

Tell the user: *"Analysis complete. {X} keywords classified, {Y} flags generated across {Z} diagnostics. {Trajectory distribution}."*

**Adaptive threshold check (low-volume accounts):** After `analyze-qs-trends.js` runs, read `qs-trends.csv` and compute the share of rows with `qs_trajectory = INSUFFICIENT_DATA`. If that share is **> 50%**, surface a prompt before moving to Phase 1:

> "{pct}% of your keywords fell below the weekly-impression threshold ({current}) and were excluded from trend analysis. This is common on low-volume accounts. Want to lower the threshold and re-run? Options: 10 (very low volume) / 25 (default) / 50 / keep current."

If the user picks a new threshold, write it to `config.qualityScoreAudit.thresholds.minImpressionsPerWeek` and re-run `analyze-qs-trends.js` before continuing. Otherwise proceed — M3 will still score on the qualifying subset and the report's Data Sufficiency Notes will call out the exclusion rate.

**INFORMATIONAL overlay (Claude semantic step):**

After scripts run but before Phase 1 scoring, read `qs-tiers.csv` and semantically tag INFORMATIONAL keywords (research intent: "how to", "what is", "guide", "tutorial", "vs", "comparison" — language-agnostic). Write the tag back as an in-memory overlay — the Handoff Queue — Ad Relevance must exclude these, routing them instead to `/keyword-auditor` D17.

---

## Phase 1: Run Diagnostics

Read `reference/diagnostic-rules.md` for full specifications of the 16 diagnostics.

**CRITICAL:** Read from the pre-processed script outputs (`qs-tiers.csv`, `qs-flags.csv`, `qs-trends.csv`), NOT the raw GAQL CSVs.

### Data sources per diagnostic:

| Diagnostic | Primary Source | Computation |
|---|---|---|
| QS-D01 Account weighted QS | qs-tiers.csv | `SUM(qs × impressions) / SUM(impressions)` across non-null QS |
| QS-D02 Low-QS concentration | qs-tiers.csv | `count(qs ≤ 3) / count(qs not null)` |
| QS-D03 High-spend low-QS | qs-flags.csv → HIGH_SPEND_LOW_QS | — |
| QS-D04 QS by campaign | qs-tiers.csv grouped by campaign_id | Weighted QS per campaign |
| QS-D05 QS by ad group | qs-tiers.csv grouped by ad_group_id | Weighted QS per AG |
| QS-D06 Null QS coverage | qs-tiers.csv | `count(qs == '') / count(rows)` |
| QS-D07 AR health | qs-flags.csv → AR_BELOW_AVG (COMPETITOR-class excluded) | `count(AR_BELOW_AVG non-COMPETITOR) / count(non-null AR non-COMPETITOR)` |
| QS-D08 ECTR health | qs-flags.csv → ECTR_BELOW_AVG | `count(ECTR_BELOW_AVG) / count(non-null ECTR)` |
| QS-D09 LP health | qs-flags.csv → LP_BELOW_AVG | `count(LP_BELOW_AVG) / count(non-null LP)` |
| QS-D10 Dominant limiting | qs-tiers.csv | Distribution of `dominant_limiting_component` across rows with Below Avg |
| QS-D11 QS trend overall | qs-trends.csv | Account-level trajectory distribution |
| QS-D12 Component trends | qs-trends.csv | Per-component trajectory counts |
| QS-D13 Post-opt correlation | qs-trends.csv `changelog_events_near` | Correlate events with trajectory |
| QS-D14 Seasonal patterns | qs-trends.csv | YoY if history > 52 weeks; else SKIP |
| QS-D15 Lost IS Rank vs QS | qs-flags.csv → LOST_IS_RANK_QS | — |
| QS-D16 CPC premium | qs-flags.csv → CPC_PREMIUM_LOW_QS | — |

### Module execution based on command scope:

| Command | Modules to Run |
|---|---|
| (full) | M1 + M2 + M3 + M4 |
| distribution | M1 only |
| components | M2 only |
| trends | M3 only (SKIPs entirely if no qs-trends data) |
| competitive | M4 only |
| "AG Name" | All modules scoped to that ad group |

For each diagnostic, assign a verdict: **PASS**, **WARN**, **FAIL**, **SKIP**, or **INFO**.

### Ad-group-scoped runs

When the user passes an ad-group name, filter all script outputs by `ad_group_name` before scoring. The report narrows to that ad group (skip campaign-level rollups; D04 SKIPs, D15 SKIPs unless any keyword's campaign is flagged).

---

## Phase 1.5: Synthesis & Two-Cascade (MANDATORY)

**Read `reference/synthesis-playbook.md` in full before writing any recommendation.**

Produce an ordered hypothesis list that drives Phase 2's report and Phase 3's handoff queue. Each hypothesis carries layer (Creative-AR / Creative-ECTR / Creative-LP / Competitive), evidence, confidence, whether it blocks downstream actions, and the handoff.

### Required checks (see playbook for detail)

1. **Keyword classifier** — every keyword already has `class` in qs-tiers.csv (BRANDED / COMPETITOR / GENERIC). Overlay INFORMATIONAL via Claude semantic check on keyword text. No class = no valid hypothesis.

2. **Outer cascade — bidding mode** — walk each flagged keyword's `bidding_mode`. Manual CPC → keep severity. Smart Bidding → annotate `(dampened)`. Never silence.

3. **Inner cascade — AR → ECTR → LP:**
   - **AR Below Avg, non-COMPETITOR** → handoff to `/rsa-maker` (or `keyword-restructurer` if Headline Test fails — not yet built, surface as pending handoff in report)
   - **AR Below Avg, COMPETITOR** → INFO only, no handoff
   - **AR Below Avg, BRANDED** → escalate to `/lp-auditor` FIRST
   - **ECTR Below Avg with AR Average+** → `/offer-maker` + `/rsa-maker`
   - **ECTR Below Avg with AR Below Avg on same keyword** → BLOCKED, route AR first
   - **LP Below Avg** → `/lp-auditor` → `/lp-optimizer` (parallel)

4. **Headline Test** (Claude reasoning, per ad group with AR Below Avg):
   For each AG with AR Below Avg on non-COMPETITOR keywords, read top-10 keywords by impressions and ask: *"Can I write one headline that addresses every one of these without sounding generic?"* If YES → copy fix via `/rsa-maker`. If NO → structural split — surface as a pending-handoff finding in the report (named target: `keyword-restructurer`, not yet built). No active skill invocation today; the finding carries a structured restructure brief (source AG, proposed theme split, keywords to move).

5. **Anti-pattern guard** (explicit checks):
   - Any COMPETITOR keyword in the AR handoff queue → remove
   - Any ECTR fix on a keyword with AR Below Avg → blocked, flag as pending AR fix
   - Any INFORMATIONAL keyword in any QS handoff queue → remove, route to `/keyword-auditor`
   - Smart Bidding finding silenced → re-inject with `(dampened)` tag

### What to produce

An ordered hypothesis list ranked by:

1. Branded-campaign escalations first (within their layer)
2. AR hypotheses before ECTR (inner cascade)
3. LP hypotheses in parallel
4. Within layer, by `explains_waste_pct` desc

Each hypothesis drives one row in Phase 2's **Evidence Ladder** and one handoff queue entry in Phase 3.

---

## Phase 1.6: Peer Report Lookup (MANDATORY before writing the report)

**Don't send the user from one door to the other.** Before recommending any peer-skill handoff in Phase 2 / Phase 3, check whether that peer has already produced a fresh report — and if so, **read it and integrate its findings into THIS report** instead of asking the user to re-run.

The whole point of cross-skill awareness is that a user who runs `/lp-audit` last week and then runs `/quality-score-auditor` this week sees the LP findings *quoted inside the QS report*, not a redundant "go run /lp-auditor" instruction. QS is uniquely entangled with three peers because its three components map directly to them: **Ad Relevance ↔ `/rsa-maker` (and `/search-term-auditor` / `/keyword-auditor` for query-side evidence)**, **Expected CTR ↔ `/search-term-auditor` + `/keyword-auditor`**, **Landing Page Experience ↔ `/lp-auditor`**. A fresh report from any of those is direct evidence for or against this audit's hypothesis — surface it, don't re-run it.

#### Freshness windows

| Peer skill | Report file | Fresh window |
|---|---|---|
| `/search-term-auditor` | `context/analysis/search-term-audit.md` | ≤ 7 days |
| `/keyword-auditor` | `context/analysis/keyword-audit.md` | ≤ 7 days |
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
3. **If fresh:** open the report and read its **executive read / diagnosis / top findings / module scores**. Pull out the 1–3 findings that overlap with this audit's flagged ad groups, campaigns, or URLs — paying special attention to the three structural overlaps: LP findings against the LP-Experience handoff queue, search-term/keyword findings against the AR and ECTR queues. Use them to:
   - **Enrich the Executive read at the top of `quality-score-audit.md`** — quote the peer's score, the headline finding, and the date inline.
   - **Replace** the routing line "run `/peer-skill`" with: **"Review the existing {date} {peer} report at {path} — top finding: '{one-liner}'. Re-run only if you want fresher data."**
   - In the Handoff Queues and Sequenced Handoff offer, when a peer handoff is the recommended action, quote the peer's specific finding so the user can act without leaving this report.
4. **If stale:** mention "a previous {peer} report exists from {date} but is {N} days old — recommend re-running before relying on it" and keep the handoff as a re-run.
5. **If missing:** standard "run `/peer-skill`" handoff.

#### When a fresh peer report contradicts a QS hypothesis

Say so explicitly in the Executive read. Example: this audit flags Ad Relevance as the dominant limiting component on Campaign X — but a fresh `/keyword-auditor` report shows the AGs in question are themed across genuinely different intents (a structural problem, not a copy problem). The AR-copy hypothesis is then unreliable; rewriting RSAs won't help if the ad group is mistaked. **The QS report must say this, not silently push `/rsa-maker` work.** Likewise: if `/lp-auditor` shows Campaign Y's LPs are passing every structural and message-match check but QS says LP Below Avg, surface the contradiction — the QS LP signal may be lagging, or another factor (speed, mobile) is dominating — and don't auto-route to `/lp-optimizer` without naming the conflict.

That cross-skill validation is the entire reason this phase exists. A QS audit that ignores a fresh LP, search-term, or keyword audit produces a confidently-wrong recommendation.

---

## Phase 2: Score & Report

Read `reference/scoring-model.md` for the scoring model.

### Scoring summary

- PASS = full points | WARN = −40% | FAIL = −100% | SKIP = excluded from denominator | INFO = no points

```
score = points_earned / (100 - skipped_points) * 100
```

### Grade thresholds

| Score | Grade |
|---|---|
| 90–100 | Excellent |
| 70–89 | Good |
| 50–69 | Needs Attention |
| <50 | Critical |

### Resolve currency before writing the report

Read top-level `accountCurrency` from `config/ads-context.config.json` (ISO-4217, e.g. `USD`, `EUR`, `GBP`). This is the same shared key the budget-auditor and other peer skills use — never bake `$` into the report.

Format every money value via `Intl.NumberFormat('en-US', { style: 'currency', currency: accountCurrency })` so the symbol/placement/decimals follow the locale of the resolved currency (`€4,200`, `CHF 4,200`, `¥4,200`). The analyzer scripts already do this — see `scripts/lib.js → formatCurrency / formatCurrencyPrecise` — and Claude must follow the same rule when writing prose in the report.

If `accountCurrency` is missing, default to `USD` and surface a one-line warning at the top of the report: *"accountCurrency not set in config — money values rendered in USD. Run `/quality-score-auditor reconfirm` to set the correct currency."* The Diagnosis section writes spend numbers, so this must be resolved before the report is written.

### Write audit report to `context/analysis/quality-score-audit.md`

**Read `reference/report-template.md` for the full template.** The report is organized around the hypothesis list from Phase 1.5, not around the diagnostic list. **Lead with the Executive read** — the 6-slot prose contract defined in `reference/report-template.md`. Apply Phase 1.6 lookup results to slot 4 (inline-quoted fresh peer findings) and to every line in the Handoff Queues and Sequenced Handoff offer that points to a peer skill.

Downstream skills parse by header — keep section names stable:

- `## Executive read` — prose, ≤300 words, no bullets, 6 slots in order (score meaning, this-week priorities w/ why, what's NOT a problem, fresh peer findings inline, how-to-read, score trend)
- `## Diagnosis` — one paragraph, natural language
- `## Evidence Ladder` — grouped by cascade layer
- `## Module Scores` — 4-row table
- `## Actions — segmented by cascade state` — apply Phase 1.6 results: every peer-skill row says either "run /peer" (missing/stale) or "review existing {date} report at {path}" (fresh, with the one-liner finding)
- `## Handoff Queue — Ad Relevance` (→ /rsa-maker) — if a fresh `/search-term-auditor` or `/keyword-auditor` report exists, quote its overlapping finding inline in the queue's recommended_action column
- `## Handoff Queue — Expected CTR` (→ /offer-maker + /rsa-maker)
- `## Handoff Queue — LP Experience` (→ /lp-optimizer) — if a fresh `/lp-auditor` report exists, quote its overlapping finding inline so the user doesn't get bounced to a re-run
- `## Module Details`
- `## Data Sufficiency Notes`

**Handoff queue construction — impressions column is mandatory.** Downstream skills use impressions to prioritize. For each queue, aggregate from `qs-tiers.csv`:

- **AR queue** — group `LP_BELOW_AVG=false, AR=BELOW_AVG, class!=COMPETITOR` rows by `ad_group_id`; `keywords_below_avg = count`, `impressions = SUM(impressions)`.
- **ECTR queue** — group `ECTR=BELOW_AVG` rows by `ad_group_id`; same aggregation.
- **LP queue** — group `LP=BELOW_AVG` rows by their *effective URL* (keyword-level `final_urls` if populated, else the ad's `ad_group_ad.ad.final_urls` from `qs-ads.csv` via `ad_group_id` join); same aggregation. This ensures downstream `/lp-optimizer` receives the URL Google actually scored, not a campaign template or an AG default.

Never leave the `impressions` column blank or as `—`. If a row has no impressions in the window, exclude it from the queue (it wouldn't be actionable anyway).

### Append entry to `context/analysis/quality-score-audit-log.md`

If the file doesn't exist, create it with header `# Quality Score Audit Log`. Append a timestamped entry using the log template from `reference/report-template.md`. The entry leads with `## {date} — Score: X% ({grade})` and includes a top-finding line and a "fresh peer reports integrated" line so the log surfaces both severity and cross-skill signal in scan view.

```markdown
## {date} — Score: {score}% ({grade})

- **Top finding:** {1-line — single most impactful issue or "Clean"}
- **Fresh peer reports integrated:** {peer skills + dates, or "none"}
- Period: {period}d | History: {history}d | Keywords: {count} (flagged {count})
- Top hypothesis: {layer} — {name} (confidence {x}, explains ~{pct}%)
- Module scores: M1 {x}/20 · M2 {x}/45 · M3 {x}/15 · M4 {x}/20
- Classifier: {n} BRANDED, {n} COMPETITOR, {n} INFORMATIONAL, {n} GENERIC
```

---

## Phase 3: Present Results & Sequenced Handoff

The reader should be able to act from the **Executive read alone** — that's the bar. Everything else is reference material.

Present to user, in this order:

1. **Executive read** — quote the `## Executive read` section from the report verbatim, do not re-summarize. It already covers score-meaning, this-week priorities w/ why, what's-NOT-a-problem, fresh peer findings inline, how-to-read, score trend.
2. **Score, grade, headline diagnosis** — present the `## Diagnosis` section verbatim (In-one-line → What's happening → Where it hurts most → What to do first). Do **not** lead with cascade-layer terminology in the spoken summary. The machine-readable hypothesis/confidence/blocking data lives in the "For the record" footer for downstream skills.
3. **Top hypothesis** — layer, evidence, confidence, explained %.
4. **Module scores** — 4-row table.
5. **Classifier results** — BRANDED / COMPETITOR / INFORMATIONAL / GENERIC counts so the user sees what got routed away from QS fixes.
6. **Sequenced handoff offer** — apply Phase 1.6 lookup results to every line. Each peer handoff says either "review existing {date} report at {path} (top finding: ...)" or "run `/peer-skill`". See below.
7. **Note location of full report:** `context/analysis/quality-score-audit.md`.

### Sequenced handoff offer

Read `reference/handoff-matrix.md` for the mapping. The offer is always sequenced by inner cascade, not by convenience.

Template:

> **Top hypothesis: {layer} — {name}** (explains ~{pct}% of QS-related CPC premium)
>
> Here's what I'd run in order:
>
> 1. **{Branded-campaign escalation if any}** — `/lp-auditor` on branded keywords with QS < {brandLowQsCeiling}
> 2. **Ad Relevance fixes** — `/rsa-maker` for copy ({N} kw). {M} AGs also fail the Headline Test — those are surfaced as a pending `keyword-restructurer` handoff (skill not yet built; see restructure brief in report).
> 3. **LP Experience (parallel, independent of AR/ECTR)** — `/lp-auditor` → `/lp-optimizer` ({K} kw grouped under {J} URLs)
> 4. **Expected CTR (only after AR resolved)** — `/offer-maker` + `/rsa-maker` ({P} kw)
>
> **Do NOT run AR fixes on these {C} COMPETITOR-class keywords** — AR Below Avg is structural when targeting a rival's brand.
>
> **Do NOT run QS fixes on these {I} INFORMATIONAL keywords** — route to `/keyword-auditor` for pause/negative decisions.
>
> Which queue would you like to start with?

When no active hypothesis (all modules clear), revert to a brief "nothing actionable — re-audit in 30 days once {history}d more data accrues" message.

---

## Edge Cases

| Scenario | Handling |
|---|---|
| Null QS > 30% of keywords | M1-D06 WARN. M2 excludes null-QS rows from denominator. Report notes: *"Re-audit in 30d."* |
| Low-impression instability (<1000 imps) | `tier=UNSTABLE_QS` in qs-tiers.csv. Excluded from M2 component scoring denominators. |
| All-Smart-Bidding account | M1/M2 run with severity `(dampened)` annotation. Report opens with *"QS still feeds Ad Rank — CPC impact dampened by Smart Bidding, not eliminated."* |
| Competitor-only campaign | All keywords class=COMPETITOR. D07 denominator = 0 → SKIP with note *"All keywords in scope are COMPETITOR-classed; AR Below Avg is structural."* D08/D09 still run (offer + LP apply). |
| Brand campaign with low QS | Severity escalated — `BRAND_LOW_QS` flag. Route FIRST to `/lp-auditor` (message match / speed / wrong URL), then `/rsa-maker` if AR persists. |
| Fresh account (<60d) | M3 SKIPs entirely. Report states insufficient history. Still produces M1/M2/M4. |
| New keywords <14d | Claude overlay as `LEARNING` class — exclude from recommendations, informational only. |
| PMax-only or no enabled Search campaigns | Exit in Phase 0.1. Message: *"QS is a Search-campaign concept. No enabled Search campaigns found."* |
| Stale or missing `qs-ads.csv` | D07 keyword-to-ad gap evidence limited. Prompt: *"Run `/gads-context` first for full AR analysis."* |
| Missing `context/account-changelog.md` | M3-D13 SKIPs. Nudge: *"Run `/gads-context` or `/account-changelog` to enable post-optimization correlation."* |
| User-configured `competitorCampaigns=[]` | Classifier treats all as GENERIC. Report banner: *"No competitor campaigns configured. Re-run Phase 0.0 if your account runs conquesting."* |
| Portfolio bid strategy | Portfolio resolution runs in `analyze-quality-score.js`. `target_source` and `portfolio_name` surface in the per-campaign breakdown so severity interpretation is visible. |
| Ad-group-scoped run on AG not found | Stop with: *"Ad group '{name}' not found in the data. Available ad groups: {list}."* |
| Currency other than USD | All money columns formatted via top-level `accountCurrency` (ISO-4217). Analyzer scripts use `scripts/lib.js → formatCurrency / formatCurrencyPrecise`; Claude uses `Intl.NumberFormat` when writing the report. |
| `accountCurrency` missing from config | Defaults to `USD` with a one-line warning at the top of the report. Phase 0.0 Branch B prompts the user to set it; cached Branch A surfaces it in the reconfirmation line. |
