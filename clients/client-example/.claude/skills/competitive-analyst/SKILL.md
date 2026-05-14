---
name: competitive-analyst
description: >
  Audit competitive position across 7 API-native diagnostics in 3 modules. Scores 0-100.
  DIAGNOSE-ONLY — findings route to specialist skills via handoff matrix.
  AUTO-ACTIVATE for: "competitive audit", "competitive analysis", "competitive position",
  "impression share audit".
---

# Competitive Analyst

Audit competitive position using API-native impression share metrics across 7 diagnostics in 3 modules. Read-only — never modifies the account.

**Scores 0-100** using weighted diagnostics across:
1. IS Health & Trends (30 pts) — CA-D01, CA-D02
2. Competitive Position (35 pts) — CA-D05, CA-D08, CA-D09
3. Competitive Impact (35 pts) — CA-D11, CA-D13

**DIAGNOSE-ONLY.** No EXECUTE actions. All findings route to specialist skills via `reference/handoff-matrix.md`:
- Budget-constrained IS loss → `/budget-specialist`
- Rank-driven IS loss → `/keyword-auditor`, `/ad-copy-specialist`, `/lp-auditor`
- CPC competitive pressure → `/bidding-specialist`, `/competitor-ads`
- Shopping ad group decline → `/product-optimizer`
- Material KPI impact → `/performance-reviewer`

---

## Command Routing

```
/competitive-analyst                → Full audit (all 7 active checks)
/competitive-analyst {period}       → Full audit with custom period (30/60/90, default 90)
```

Default evaluation period: **90 days**. IS trends need longer windows than keyword performance to distinguish real trajectory from noise.

---

## Phase 0: Prerequisites & Data Collection

### Phase 0.0: Business Context Resolution

**Purpose:** The competitive analyst needs the primary KPI mode and conversion lag to compute date ranges and estimate KPI impact (CA-D13). Reuse cached values from `keywordAudit` or `searchTermAnalysis` when available.

**Read:** `config/ads-context.config.json` → `competitiveAnalyst` block, falling back to `keywordAudit` block.

**Cached values needed:**
- `primaryKPI` ("cpa" or "roas") — reuse from `keywordAudit.primaryKPI` if available
- `breakEvenCPA` or `breakEvenROAS` — reuse from `keywordAudit` if available
- `conversionLagDays` — reuse from `searchTermAnalysis.conversionLagDays`
- `lastConfirmed` (ISO date)

**Branch A — Cached values exist (from keyword-auditor or prior run):**

One-line reconfirmation:

> "Using cached context: primary KPI **{kpi}**, conversion lag **{lag}d**. Proceed? (y / update)"

If "y" → continue to Phase 0.1.

**Branch B — First run, no cached values:**

Minimal interview — only needs KPI mode and conversion lag. If `keywordAudit` block exists, inherit from there (no duplicate interview).

> "I need two values to run the competitive analysis:
>
> **1. Primary KPI:** CPA or ROAS? (determines how CA-D13 estimates business impact)
> **2. Conversion lag:** How many days between click and conversion? (shifts the analysis window to avoid counting in-flight conversions)
>
> If you've already run `/keyword-auditor`, I'll inherit these from that config."

Write to `config/ads-context.config.json` → `competitiveAnalyst` block:
- `primaryKPI`
- `breakEvenCPA` or `breakEvenROAS` (if available from keywordAudit)
- `conversionLagDays`
- `lastConfirmed` (ISO date string, today)

### Phase 0.1: Config Validation

Read `config/ads-context.config.json`:

1. Verify `googleAds.customerId` exists
2. Resolve evaluation period: **90 days** default. User may pass 30, 60, or 90.
3. Compute date ranges:
   ```
   conversionLagDays = config.searchTermAnalysis.conversionLagDays
   evaluationPeriod  = 90 (default)

   end   = today - conversionLagDays
   start = end - evaluationPeriod + 1
   ```
4. Confirm with user: "Analyzing **{period}-day** competitive position with **{lag}-day** conversion lag. Period: **{start} → {end}**. OK?"

### Phase 0.2: Data Pull

Run `pull-all.js` — executes queries in batch:

```bash
node .claude/skills/competitive-analyst/scripts/pull-all.js \
  --period={evaluationPeriod} --lag={conversionLagDays}
```

| # | Output CSV | GAQL Source | Notes |
|---|-----------|-------------|-------|
| Q1 | `campaign-is-timeseries.csv` | `campaign-is-timeseries.gaql` | Search + Shopping campaigns, segmented by date |
| Q2 | `keyword-is.csv` | `keyword-is.gaql` | Period aggregate, all enabled keywords with impressions |
| Q3 | `shopping-adgroup-is-timeseries.csv` | `shopping-adgroup-is-timeseries.gaql` | **Conditional** — only if Q1 contains Shopping campaigns |

Q3 gate: The script checks Q1 output for SHOPPING campaigns. If found, runs Q3 to get ad-group-level IS. The analysis script determines if any Shopping campaign has 2+ ad groups for CA-D09.

Parse `__RESULTS_JSON__` from script output. Report to user: "Pulled {N} campaign-days across {M} campaigns and {K} keywords."

### Phase 0.2.1: QS Data Pull

Pull keyword-level Quality Score data using the shared `gads-context` query tool.

```bash
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customerId} \
  --login-customer-id={loginCustomerId} \
  --query-file=.claude/skills/gads-context/references/keywords.gaql \
  --days={evaluationPeriod} --lag-offset={conversionLagDays} \
  --output=context/google-ads/data/keywords.csv
```

This pulls `keywords.csv` with:
- `ad_group_criterion.quality_info.quality_score` (1-10)
- `ad_group_criterion.quality_info.creative_quality_score` (BELOW_AVERAGE / AVERAGE / ABOVE_AVERAGE)
- `ad_group_criterion.quality_info.post_click_quality_score` (LP experience component)
- `ad_group_criterion.quality_info.search_predicted_ctr` (expected CTR component)

Phase 1.5 uses this to determine whether rank loss is QS-driven or bid-driven — the most important diagnostic distinction in the audit.

### Phase 0.3: Script Execution

```bash
node .claude/skills/competitive-analyst/scripts/analyze-competitive-position.js \
  --timeseries-csv=context/google-ads/data/campaign-is-timeseries.csv \
  --keyword-csv=context/google-ads/data/keyword-is.csv \
  [--shopping-adgroup-csv=context/google-ads/data/shopping-adgroup-is-timeseries.csv] \
  --output=context/google-ads/data/competitive-flags.csv
```

The `--shopping-adgroup-csv` argument is optional. If Q3 was skipped, omit it.

Parse `__RESULTS_JSON__` from script output. Report: "Analysis complete. {N} competitive flags found."

---

## Phase 1: Run Diagnostics

Read `.claude/skills/competitive-analyst/reference/diagnostic-rules.md` for full diagnostic specifications.

**Read from:** `competitive-flags.csv` (pre-processed script output) + `keyword-is.csv` for CA-D08 keyword table.

### Data sources per diagnostic:

| Diagnostic | Primary Source | Notes |
|-----------|---------------|-------|
| CA-D01 | competitive-flags.csv → `IS_DECLINING` | Campaign-level IS trajectory |
| CA-D02 | competitive-flags.csv → `IS_LOSS_HIGH`, `IS_LOSS_BUDGET`, `IS_LOSS_RANK` | IS loss decomposition |
| CA-D05 | competitive-flags.csv → `TOP_IS_DECLINING` | Search campaigns only |
| CA-D08 | competitive-flags.csv → `KEYWORD_IS_PRESSURE`, `KEYWORD_POSITION_LOSS` + keyword-is.csv | Top 20 keywords |
| CA-D09 | competitive-flags.csv → `SHOPPING_AG_IS_ISOLATED_DECLINE`, `SHOPPING_AG_IS_SEVERE_DECLINE` | Conditional on Shopping |
| CA-D11 | competitive-flags.csv → `CPC_COMPETITIVE_PRESSURE` | CPC-IS correlation |
| CA-D13 | competitive-flags.csv → `KPI_IMPACT` | Metric tree impact estimation |
| CA-D03,04,06,07,10,12 | — | SKIP |

### CA-D09 availability gate:

1. Check if any Shopping campaigns exist in the data
2. If none → CA-D09 emits `SKIP — No standard Shopping campaigns found. PMax asset groups do not expose IS metrics.`
3. If Shopping campaigns exist but use single ad groups → `SKIP — Shopping campaigns use single ad groups; campaign-level IS (CA-D01/D02) already covers this.`
4. Only runs when Shopping campaigns with 2+ ad groups are present

For each diagnostic, assign a verdict: **PASS**, **WARN**, **FAIL**, or **SKIP**.

---

## Phase 1.5: Synthesis & Business-Grounded Cascade (MANDATORY)

**Read `.claude/skills/competitive-analyst/reference/synthesis-playbook.md` in full before writing any recommendation.** This phase is non-optional. Skipping it produces a "here's the data, go fix it" report instead of business-grounded strategic advice.

Output of this phase is a **ranked hypothesis list** that drives Phase 2's report structure and Phase 3's handoff offer. Each hypothesis carries: layer, evidence, confidence, whether it blocks downstream actions, strategic verdict, and the upstream skill handoff.

### Data Enrichment (before the cascade)

Before walking the 5-layer cascade, gather business context:

1. **Read `context/business.md`** — extract break-even CPA/ROAS, target CPA/ROAS, growth mode status, unit economics
2. **Read `config/ads-context.config.json`** — extract `keywordAudit.breakEvenCPA` or `keywordAudit.breakEvenROAS` if populated; `searchTermAnalysis.biddingStrategy`
3. **Compute campaign-level economics** from `campaign-is-timeseries.csv` — CPA, ROAS, CVR, avg CPC per campaign
4. **Compute keyword-level economics** from `keyword-is.csv` — CPA, CVR, CTR per keyword (top 20)
5. **Read QS data** from `context/google-ads/data/keywords.csv` (pulled in Phase 0.2.1) — read `quality_score`, `creative_quality_score`, `post_click_quality_score`, `search_predicted_ctr` for the flagged keywords. This is real QS, not a proxy.

### Required cascade layers (see playbook for thresholds and formulas)

1. **Data Validation** — DV1 campaign maturity (<30 days), DV2 bidding strategy context (Max Conv intentionally trades IS for efficiency), DV3 conversion data sufficiency (<10 conv = unreliable efficiency metrics).

2. **Business Economics** — **the most important layer.** KPI-agnostic: works in CPA or ROAS mode (see playbook KPI Mode table). BE1 efficiency headroom (if efficiency already exceeds the profitability threshold, gaining IS through bids accelerates losses — route to conversion improvement, not bid increase). BE2 implied efficiency floor (best-case metric at current auction prices — if it fails the threshold, market is structurally unviable). BE3 budget headroom (cross-reference with CA-D02). BE4 IS recovery ROI (marginal efficiency for recovered IS).

3. **QS & Rank Diagnosis** — Read actual QS from `keywords.csv` (pulled in Phase 0.2.1). For each flagged keyword: check `quality_score` (1-10), plus the three components (`creative_quality_score`, `post_click_quality_score`, `search_predicted_ctr`). QS >= 7 + high rank loss = bid-driven. QS <= 5 = QS-driven (and names which component is weak). This is real data, not a proxy.

4. **Strategic Assessment** — SA1 campaign prioritization (rank by IS recovery ROI). SA2 competitive entry response for branded CPC pressure (check branded CPA before advising bid defense). SA3 market position verdict: one of **Compete aggressively** / **Fix economics first** / **Selective competition** / **Structural challenge**.

5. **Tactical Routing** — segmented action plan: Investigate first → Fix economics first → Compete where viable → Strategic discussion → Monitor. Never a flat table. Read `reference/handoff-matrix.md` for routing.

### What to produce

A ranked hypothesis list and a strategic verdict (SA3). The verdict is the lead of Phase 2's Diagnosis section. Example:

- **"Fix economics first"** — efficiency exceeds target, rank loss is real but gaining IS at current economics would accelerate losses. Fix conversion path, then compete.
- **"Compete aggressively"** — efficiency has headroom, QS is the lever, budget is available. Fix QS to gain IS without increasing spend.
- **"Selective competition"** — some campaigns are viable, others are not. Invest selectively.
- **"Structural challenge"** — implied efficiency floor fails the profitability threshold. Needs strategic discussion, not tactical optimization.

### Explicit anti-patterns — never do these

- Saying "increase bids to gain IS" when campaign efficiency exceeds the target
- Saying "fix rank" without specifying whether it's QS-driven or bid-driven
- Presenting a flat "Recommended Actions" table with equal-weight rows
- Routing to a skill without explaining what the user will learn
- Presenting lost conversions/value as pure opportunity cost without noting the efficiency cost to recover them
- Using CPA-only language for a ROAS-mode account

---

## Phase 2: Score & Log

Read `.claude/skills/competitive-analyst/reference/scoring-model.md` for the scoring model.

### Scoring summary:
- PASS = full points retained
- WARN = deduct 40% of check's points
- FAIL = deduct 100% of check's points
- SKIP = excluded from scoring (reduce denominator)

Compute: `score = points_earned / (100 - skipped_points) * 100`

### CA-D09 point redistribution:

When CA-D09 is SKIP, its 8 points redistribute within Module 2:
- CA-D05: 15 → 19 points
- CA-D08: 12 → 16 points

### Grade thresholds:

| Score | Grade |
|-------|-------|
| 90-100 | Excellent |
| 70-89 | Good |
| 50-69 | Needs Attention |
| <50 | Critical |

### Append log to `context/analysis/competitive-audit-log.md`

If file doesn't exist, create it with header `# Competitive Audit Log`.

Append a timestamped entry using the log template from `reference/report-template.md`. The log entry leads with `## {date} — Score: X% (grade)` and includes a `Top finding:` line and a `Fresh peer reports integrated:` line that lists which peer reports were quoted in this run (populated after Phase 2.5).

---

## Phase 2.5: Peer Report Lookup (MANDATORY before writing the report)

**Don't send the user from one door to the other.** Before recommending any peer-skill handoff in Phase 3's report or Phase 4's user summary, check whether that peer has already produced a fresh report — and if so, **read it and integrate its findings into THIS report** instead of asking the user to re-run.

The whole point of cross-skill awareness is that a user who runs `/quality-score-auditor` last week and then runs `/competitive-analyst` this week sees the QS findings *quoted inside the competitive report*, not a redundant "go run QS" instruction. Re-running an auditor that already produced a fresh answer wastes time and obscures the competitive-side action.

Competitive findings are typically **explainers, not root causes**. IS-lost-rank can be driven by QS (peer: `/quality-score-auditor`), by budget (peer: `/budget-auditor`), or by bid (peer: `/bidding-auditor`). These three are the most common "the competitive symptom is actually an X-side cause" overlaps — peer-lookup integration must be tight on those, because the LP/offer/tracking peers explain second-order effects, but QS/budget/bid peers often **rewrite the diagnosis itself**.

#### Freshness windows

| Peer skill | Report file | Fresh window |
|---|---|---|
| `/quality-score-auditor` | `context/analysis/quality-score-audit.md` | ≤ 7 days |
| `/search-term-auditor` | `context/analysis/search-term-audit.md` | ≤ 7 days |
| `/keyword-auditor` | `context/analysis/keyword-audit.md` | ≤ 7 days |
| `/budget-auditor` | `context/analysis/budget-audit.md` | ≤ 7 days |
| `/bidding-auditor` | `context/analysis/bidding-audit.md` | ≤ 7 days |
| `/lp-auditor` | `context/analysis/lp-audit.md` | ≤ 14 days |
| `/offer-auditor` | `context/analysis/offer-audit.md` | ≤ 30 days |
| `/tracking-specialist` | `context/analysis/tracking-audit.md` | ≤ 30 days |
| `/strategy-specialist` | `context/analysis/strategy-audit.md` | ≤ 30 days |
| `/account-auditor` | `context/analysis/account-audit.md` | ≤ 30 days |

#### Procedure for each peer that the routing or synthesis would otherwise hand off to

1. **Check if the file exists.** If not → keep the handoff as a plain "run `/peer-skill`" line.
2. **Check the date in the report header against the freshness window.** The report header date is canonical. mtime is a sanity check — if mtime is *older* than the header date, warn the user that something is off.
3. **If fresh:** open the report and read its **executive read / top findings / module scores**. Pull out the 1–3 findings that overlap with this audit's flagged campaigns, ad groups, or keywords. Use them to:
   - **Enrich the Executive read at the top of `competitive-audit.md`** — quote the peer's score, the headline finding, and the date inline.
   - **Replace** the routing line "run `/peer-skill`" in the Actions section with: **"Review the existing {date} {peer} report at {path} — top finding: '{one-liner}'. Re-run only if you want fresher data."**
   - In the Diagnosis and the QS & Rank Diagnosis evidence layer, quote the peer's specific finding so the user can act without leaving this report.
4. **If stale:** mention "a previous {peer} report exists from {date} but is {N} days old — recommend re-running before relying on it" and keep the handoff as a re-run.
5. **If missing:** standard "run `/peer-skill`" handoff.

#### Tight integration on the three rank-loss peers

When CA-D02 flags `IS_LOSS_RANK` or CA-D08 flags `KEYWORD_POSITION_LOSS`, the synthesis hypothesis is "rank-driven." Before finalizing that hypothesis:

- **`/quality-score-auditor` fresh report exists?** Quote the QS distribution and the LP-experience / ad-relevance / expected-CTR component scores for the flagged campaigns. If QS audit names the same campaigns, the rank loss is QS-driven and the recommendation is "fix QS, don't raise bids."
- **`/bidding-auditor` fresh report exists?** Quote the bid strategy state, learning state, and target validation. If the bidding audit shows tCPA is in learning or target is too aggressive, the rank loss is **bid-driven on purpose** — not a problem to solve.
- **`/budget-auditor` fresh report exists?** When CA-D02 flags `IS_LOSS_BUDGET`, quote the budget audit's verdict on whether the budget is sufficient or whether shared-budget contention is starving the campaign.

#### When a fresh peer report contradicts a competitive hypothesis

Say so explicitly in the Executive read. Example: competitive-analyst flags Campaign X for high rank-lost IS — but the fresh quality-score-audit shows QS is 8/10 on that campaign with strong components, while the bidding-audit shows tCPA was tightened 3 days ago. The rank loss is then **intentional** (bid trade-off), not a problem. **The competitive report must say this, not silently propose bid increases or QS work.**

That cross-skill validation is the entire reason this phase exists. A competitive audit that ignores a fresh QS, budget, or bidding audit produces a confidently-wrong recommendation.

---

## Phase 3: Write Report

**Read `.claude/skills/competitive-analyst/reference/report-template.md` for the full report template.** The report is organized around the **hypothesis list from Phase 1.5** and the **peer findings from Phase 2.5**, not around the diagnostic list.

Write `context/analysis/competitive-audit.md`. This report is regenerated on each run (overwrites previous). The log (Phase 2) preserves history.

**Lead with the Executive read** — the 6-slot prose contract defined in `reference/report-template.md`. Apply Phase 2.5 lookup results to slot 4 (inline-quoted fresh peer findings) and to every line in the Actions section that points to a peer skill.

Fill in all sections in this order:

1. **Executive read** (prose, ≤300 words, no bullets) — score meaning, 1–3 priorities w/ why, what's NOT a problem, fresh peer findings inline (especially QS / bidding / budget for rank-loss findings), how-to-read, score trend.
2. **Score summary** — overall score, grade, per-module breakdown
3. **Diagnosis** — root-cause hypothesis paragraph with strategic verdict (SA3). Written as business advice, not a diagnostic readout. Leads with the verdict: "Fix economics first" / "Compete aggressively" / "Selective competition" / "Structural challenge." When peer reports are fresh, quote them inline (e.g., "the {date} QS audit confirms QS 4/10 on these same campaigns — rank loss is QS-driven, not bid-driven").
4. **Business Economics Context** — campaign-level and keyword-level economics tables connecting IS findings to CPA/ROAS reality. Shows headroom, implied CPA floor, and "Can afford more IS?" per campaign.
5. **Evidence Ladder** — grouped by cascade layer (Data Validation, Business Economics, QS/Rank Diagnosis, Strategic Assessment). Only layers with active hypotheses appear. The QS & Rank Diagnosis layer is the natural place to inline fresh peer findings from `/quality-score-auditor`, `/bidding-auditor`, `/budget-auditor`.
6. **IS Trend Dashboard** — campaign-level trajectory table
7. **IS Loss Decomposition** — budget vs rank per campaign, with "Can Afford More IS?" column
8. **Top-of-Page Position Analysis** — abs-top IS and top IS trends per Search campaign
9. **Keyword Competitive Pressure** — top 20 keywords table with IS metrics + economic status column
10. **Shopping Ad Group Breakdown** — conditional on Shopping campaigns
11. **CPC-Competition Correlation** — per-campaign correlation analysis with SA2 competitive entry response for branded
12. **KPI Impact Estimate** — metric tree with economic reality check: recovery CPA vs target CPA
13. **Skipped Diagnostics** — list of 6 skipped checks
14. **Competitor Ad Copy Insights** — conditional on `/competitor-ads` data
15. **Actions — segmented by cascade state:** Investigate first → Fix economics first → Compete where viable → Strategic discussion → Monitor. Apply Phase 2.5 results: every peer-skill line says either "run /peer" (missing/stale) or "review existing {date} report at {path}" (fresh, with the one-liner finding). **Never a flat table.**

---

## Phase 4: Present Results & Sequenced Handoff

Already written in Phase 3; Phase 4 is the user-facing presentation. The reader should be able to act from the **Executive read alone** — that's the bar. Everything else is reference material.

### Skill availability gate

Before routing to any skill in the handoff, check if `.claude/skills/{skill-name}/SKILL.md` exists. If the skill is **not yet built**, still include the recommendation but:
- Mark it as **"(not yet built)"** in the action table
- Add a one-line manual alternative: what the user can do in the Google Ads UI or with other available tools until the skill is built
- Example: "Review ad copy for QS improvement → `/ad-copy-specialist` **(not yet built)** — until then, manually review RSAs in the Google Ads UI for the flagged keywords: check headline relevance, ensure keyword insertion, and test new ad variants."

This keeps recommendations forward-looking and complete. When the skill gets built, the gate auto-resolves — no playbook update needed.

### Present to user, in this order:

### 1. Executive read (verbatim from the report)

Quote the **Executive read** prose section from `context/analysis/competitive-audit.md` verbatim — do not re-summarize. It already covers score-meaning, this-week priorities w/ why, what's-NOT-a-problem, fresh peer findings inline, how-to-read, and score trend.

### 2. Score, grade, run timestamp, and strategic verdict

> **Competitive Position: {score}/100 ({grade})** — {period}-day analysis run {timestamp}
>
> **Verdict: {Fix economics first / Compete aggressively / Selective competition / Structural challenge}**

### 3. Module scores

| Module | Score | Grade | Key Finding |
|--------|-------|-------|-------------|
| IS Health & Trends | {x}/30 | {grade} | {1-line} |
| Competitive Position | {x}/35 | {grade} | {1-line} |
| Competitive Impact | {x}/35 | {grade} | {1-line} |

### 4. Sequenced handoff offer (hypothesis-driven, not a flat menu)

The offer is sequenced by the cascade — economics before tactics, always. Never present as a flat menu of equal-weight options.

**Apply Phase 2.5 lookup results to every line.** Each peer handoff says either "review existing {date} report at {path} (top finding: ...)" (fresh peer report exists) or "run `/peer-skill`" (missing/stale). Never silently ask the user to re-run an auditor whose report is already fresh — the QS / budget / bidding peers especially are likely to have run within the last week.

**When "Fix economics first" or "Structural challenge":**

> Based on the economic analysis, here's what I'd recommend in order:
>
> 1. **Check QS on the {N} flagged keywords** — if QS is low, fixing it gains IS without increasing spend (the cheapest path to more visibility) → `/keyword-auditor performance`
> 2. **Audit landing page conversion rate** — at {CVR}%, your CPA floor is ${floor}. Improving CVR creates the headroom you need to compete → `/lp-auditor`
> 3. **Review offer positioning** — competitors are winning with {angle}. A stronger offer raises CVR across all keywords → `/offer-auditor`
> 4. **Then reassess competitive position** — after efficiency improvements, re-run this audit to see if IS has improved and whether tactical bid adjustments are now viable
>
> The {N} lost conversions (${value}) are real opportunity cost, but recovering them at current economics would cost ~${recovery_cpa}/conv. Fix what converts, then compete for more traffic.

**When "Compete aggressively":**

> Economics support IS recovery — CPA ${x} with ${headroom} headroom. Recommended sequence:
>
> 1. **Verify QS on flagged keywords** — if QS-driven, fix QS first (gains IS without spending more) → `/keyword-auditor performance`
> 2. **If bid-driven, review bid strategy** → `/bidding-specialist`
> 3. **Competitor intelligence** → `/competitor-ads` for ad copy angles
> {+ branded defense recommendation if CA-D11 active}

**When "Selective competition":**

> Mixed picture — some campaigns are viable, others aren't. Per-campaign guidance:
>
> - **{Campaign A}**: CPA ${x}, ${headroom} headroom — compete here. {QS or bid recommendation}
> - **{Campaign B}**: CPA ${x}, ${overshoot} over target — fix economics first. {LP/offer recommendation}
> - ...

Read `reference/handoff-matrix.md` for the full routing table. Only show handoffs that have findings to act on.

### 5. Artifacts

Note location of full report and log:
- Full report: `context/analysis/competitive-audit.md`
- Audit log: `context/analysis/competitive-audit-log.md`

---

## Edge Cases

| Scenario | Handling |
|----------|---------|
| Single campaign account | All checks run normally on one campaign. Note in report. |
| No Search campaigns | Skip CA-D05, CA-D08. Note in report. Score based on remaining checks. |
| No Shopping campaigns | CA-D09 = SKIP. Points redistribute to CA-D05 and CA-D08. |
| PMax-only account | Most checks produce limited data. Note that PMax does not expose IS metrics. |
| All IS values null / " --" | Campaign excluded from analysis. Note count of excluded campaigns. |
| Very short period (<30 days) | CA-D01 90-day trajectory unavailable. Note limitation. |
| Single week of data | Insufficient for trend analysis. Warn user and suggest 90-day period. |
| CPC data sparse | CA-D11 needs 4+ weeks. SKIP if insufficient weeks. |
| No conversions in period | CA-D13 cannot estimate impact. SKIP with note. |
| No business.md / no break-even CPA | Phase 1.5 Business Economics layer runs with caveats. CPA headroom checks use campaign targets only. Report carries a banner: "Business economics not available — recommendations are based on campaign targets, not verified profitability thresholds." |
| QS data in keywords.csv | Phase 1.5 reads QS directly from Phase 0.2.1 pull. Full component-level diagnosis (ad relevance, LP experience, expected CTR). |
| QS null on flagged keywords | Keywords with too few impressions may have null QS. Note count and flag as UNKNOWN in report. |
