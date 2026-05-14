---
name: search-term-auditor
description: >
  Audit search term health across 26 diagnostics in 5 modules (quality, negative coverage,
  n-grams, close variants, promotion/PMax). Scores 0-100 per module.
  AUTO-ACTIVATE for: "search term audit", "search term review", "n-gram analysis",
  "negative keyword audit", "irrelevant search terms", "search term waste",
  "promote search terms", "search term coverage".
argument-hint: "[module] [period]"
---

# Search Term Auditor

Audit search term health across 26 diagnostics in 5 modules. Read-only — never modifies the account.

**Scores 0-100** using weighted diagnostics across:
1. Search Term Quality (25 pts)
2. Negative Keyword Coverage (25 pts)
3. N-gram Analysis (20 pts)
4. Close Variant Monitoring (15 pts)
5. Promotion & PMax (15 pts)

**Diagnostic ≠ negation recommendation.** Raw flags are *symptoms*. Phase 1.5 walks the constraint cascade **Measurement → Business** before any negation is recommended. Relevant-but-underperforming terms route upstream (LP, offer, targets) — they are never auto-negated. See `reference/synthesis-playbook.md`.

**Handoff:** Actions route through `reference/handoff-matrix.md` — upstream skills (`/tracking-specialist`, `/strategy-specialist`, `/lp-auditor`, `/offer-auditor`) fire *before* `/search-term-optimizer` whenever an upstream hypothesis is active.

---

## Command Routing

Parse the user's command to determine scope:

```
/search-term-auditor                     → Full audit (all 26 diagnostics, all 5 modules)
/search-term-auditor quality             → Module 1: ST-D01 to ST-D05
/search-term-auditor coverage            → Module 2: ST-D06 to ST-D12
/search-term-auditor ngrams              → Module 3: ST-D13 to ST-D16 (uses 120d by default)
/search-term-auditor variants            → Module 4: ST-D17 to ST-D19
/search-term-auditor promotion           → Module 5: ST-D20 to ST-D26 (D23/D24 removed)
/search-term-auditor {period}            → Full audit with custom main period (60/90/180)
/search-term-auditor {module} {period}   → Module + custom period
/search-term-auditor ngrams 180          → N-gram module over 180d
/search-term-auditor experiments         → Include Experiment campaigns (skips Phase 0 ask)
```

The `experiments` token can be combined with any other arg (e.g. `quality 90 experiments`).

**Default periods:** 60d main, 120d n-grams, 365d catalog (catalog pulled only when optimizer catalog flow runs).
**Period options:** main = 60 / 90 / 180. N-grams = 120 / 180.
**Experiment campaigns:** excluded by default. Pass `experiments` (or set `searchTermAnalysis.includeExperiments: true` in `config/ads-context.config.json`) to include drafts/experiments/A-B test variants.

---

## Phase 0: Prerequisites & Data Collection

### Phase 0.1: Business Context Resolution

Read `context/business.md`. Extract:
- `targetCPA` / `maxCPA` (effective CPA target)
- `targetROAS` (ratio form — if the doc has `530%`, the library normalizes to `5.3`)
- Core product tokens (for ST-D04 relevance judgment)

Read `config/ads-context.config.json` → `searchTermAnalysis` block for thresholds:
- `minSpendToFlag` (default: 20) — ST-D02 threshold
- `conversionLagDays` (default: 14)
- `excludeBrandedCampaigns` (default: true) — filters ST-D01–D05 scope
- `brandedCampaigns` (explicit list, preferred over name-pattern fallback)
- `biddingStrategy` ("cpa" | "roas") — account-level default, per-campaign resolved downstream
- `inefficientCPAMultiplier` (default: 1.5) — ST-D03 ROAS/CPA thresholds
- `inefficientROASMultiplier` (default: 0.7)
- `ngramAnalysis.minImpressions` / `minClicks` / `minDistinctTerms` — ST-D13/D14 filters
- `sharedNegativeLists.ngramNonConverting` / `ngramInefficient` — target list names for optimizer
- `includeExperiments` (default: false) — include drafts/experiments/A-B variants in scope

If the user has passed a `{period}` argument, skip the period ask. Otherwise ask:
> "Main evaluation period? 60 (default) / 90 / 180 days. N-gram window will use 120 days unless you override."

If the user did NOT pass `experiments` AND `searchTermAnalysis.includeExperiments` is not `true`, also ask:
> "Include Experiment campaigns (drafts/experiments/A-B variants) in scope? Default: no."

Skip this ask when either signal is already present. Track the resolved value as `includeExperiments` and pass `--include-experiments` downstream when true.

### Phase 0.2: Data Pull

Pull all 10 queries in one batch (Q5 catalog is on-demand only):

```bash
node .claude/skills/search-term-auditor/scripts/pull-all.js \
  --period={mainPeriod} --ngram-period={ngramPeriod} --lag={conversionLagDays} \
  [--include-experiments]
```

Append `--include-experiments` only when the user opted in.

The script writes CSVs to `context/google-ads/data/` and prints a `__RESULTS_JSON__` summary on the final line. Parse that to surface totals to the user. If any required query fails (search-terms, campaigns-settings), the script exits non-zero — surface the error and stop.

Tell the user: "Pulled {N} search term rows ({M} n-gram rows) across {K} campaigns. Running analysis..."

### Phase 0.3: Script Execution

Run both analysis scripts:

```bash
# Search term quality + promotion + PMax diagnostics
node .claude/skills/search-term-auditor/scripts/analyze-search-terms.js \
  --output=.claude/skills/search-term-auditor/tmp/search-term-flags.json \
  [--include-experiments]

# Negative coverage + n-gram diagnostics
node .claude/skills/search-term-auditor/scripts/analyze-negatives.js \
  --output=.claude/skills/search-term-auditor/tmp/negative-flags.json \
  [--include-experiments]
```

Pass `--include-experiments` to both analyze scripts when the user opted in (must match the value used for `pull-all.js`).

Both scripts call `resolveBiddingStrategy()` per campaign before threshold calcs, so every flagged record carries a `target_source` (`campaign_inline` | `portfolio` | `fallback` | `none`) and `portfolio_name` where applicable. Read the `meta.warnings` array for missing targets or AOV issues.

Tell the user: "Analysis complete. {X} quality flags + {Y} coverage issues + {Z} n-gram candidates."

---

## Phase 1: Run Diagnostics

Read `.claude/skills/search-term-auditor/reference/diagnostic-rules.md` for full diagnostic specifications, including the target-resolution contract for ST-D02/D03/D13/D14/D20.

**CRITICAL:** Read from the pre-processed script outputs (`tmp/search-term-flags.json`, `tmp/negative-flags.json`), NOT the raw GAQL CSVs. The scripts have already done the heavy computation and target resolution.

### Data sources per diagnostic

| ID | Diagnostic | Source | Notes |
|----|-----------|--------|-------|
| ST-D01 | Irrelevant spend % | `search-term-flags.json → quality.irrelevantSpendPct` | Script computes |
| ST-D02 | Non-converting terms | `search-term-flags.json → quality.nonConvertingTerms[]` | Per-campaign-type breakdown included. Uses resolved CPA target |
| ST-D03 | Underperforming terms | `search-term-flags.json → quality.underperformingTerms[]` | Uses resolved CPA/ROAS target |
| ST-D04 | Foreign language | Claude reads sample of high-cost terms from `quality.irrelevantTerms[]` | Semantic judgment |
| ST-D05 | Trending terms | `search-term-flags.json → quality.trendingTerms[]` | Period A vs B delta |
| ST-D06 | Campaigns without negatives | `negative-flags.json → coverage.campaignsWithoutNegatives[]` | Script |
| ST-D07 | Campaigns without shared lists | `negative-flags.json → coverage.campaignsWithoutSharedLists[]` | Script |
| ST-D08 | Negative conflicts | `negative-flags.json → coverage.negativeConflicts[]` | Script |
| ST-D09 | Repeated ad group negatives | `negative-flags.json → coverage.repeatedAdGroupNegatives[]` | Script |
| ST-D10 | Repeated campaign negatives | `negative-flags.json → coverage.repeatedCampaignNegatives[]` | Script |
| ST-D11 | Legacy +modified +broad | `negative-flags.json → coverage.legacyModifiedBroad[]` | Script |
| ST-D12 | Catalog completeness | Claude compares existing negatives against vertical patterns | Uses SOPs |
| ST-D13 | Non-converting n-grams | `negative-flags.json → ngrams.nonConverting[]` | Resolved target |
| ST-D14 | Inefficient n-grams | `negative-flags.json → ngrams.inefficient[]` | Resolved target |
| ST-D15 | Shared list staleness | `negative-flags.json → ngrams.listStaleness` | Script |
| ST-D16 | Volume concentration | `negative-flags.json → ngrams.volumeConcentration[]` | Script |
| ST-D17 | Variant performance drift | Claude reads `search-term-flags.json → closeVariants.driftCandidates[]` | Semantic |
| ST-D18 | Variant spend share | `search-term-flags.json → closeVariants.highSpendVariants[]` | Claude judgment |
| ST-D19 | Unintended expansion | Claude reads variant samples for semantic drift | |
| ST-D20 | High performers not keywords | `search-term-flags.json → promotionCandidates[]` | Resolved target |
| ST-D21 | Duplicates across campaigns | Claude reviews promotion candidates for cannibalization | |
| ST-D22 | Coverage ratio | `search-term-flags.json → coverageRatio` | Script |
| ST-D23 | — REMOVED (folded into ST-D02 segmented) | — | — |
| ST-D24 | — REMOVED (folded into ST-D03 segmented) | — | — |
| ST-D25 | PMax brand query % | `search-term-flags.json → pmaxAnalysis.brandQueryPct` | Script |
| ST-D26 | PMax search overlap | `search-term-flags.json → pmaxAnalysis.searchOverlap[]` | Script + Claude |

### Claude reasoning diagnostics (ST-D04, D12, D17-D19, D21, D26)

These require reading term text and applying semantic judgment:

- **ST-D04 (Foreign language):** Sample high-cost terms, flag terms in languages outside the target market(s).
- **ST-D12 (Catalog completeness):** Compare existing negatives against vertical-specific catalog patterns (template/discount/competitor/informational) from the SOP-distilled reference.
- **ST-D17/D18/D19 (Close variants):** Read variant samples — flag drift (performance divergence from parent keyword), disproportionate spend share, or semantic expansion beyond intent.
- **ST-D21 (Duplicates):** Review terms appearing as promotion candidates across multiple campaigns for cannibalization risk.
- **ST-D26 (PMax overlap):** Confirm script-detected overlaps are genuine (same query vs surface overlap).

### Module execution based on command scope

| Command | Modules to run |
|---------|----------------|
| (full) | All 5 |
| `quality` | Module 1 only |
| `coverage` | Module 2 only |
| `ngrams` | Module 3 only |
| `variants` | Module 4 only |
| `promotion` | Module 5 only |

For each diagnostic, assign a verdict: **PASS**, **WARN**, **FAIL**, **SKIP**, or **INFO**.

---

## Phase 1.5: Synthesis & Constraint Cascade (MANDATORY)

**Read `.claude/skills/search-term-auditor/reference/synthesis-playbook.md` in full before writing any recommendation.** Lighter than keyword-auditor — only the Measurement and Business layers — but the same principle applies: raw flags are symptoms, not action items.

### Required checks

**B0 — Target-source gate (ALWAYS RUN FIRST).** For each flagged record, read `target_source`:

| Value | Interpretation |
|-------|---------------|
| `campaign_inline` | Campaign is constrained. Run all threshold checks normally. |
| `portfolio` | Campaign is constrained by a shared portfolio. Cite `portfolio_name` in the report. |
| `fallback` | Campaign is **unconstrained** — the missing target is itself the issue. Route to `/strategy-specialist` before negating anything. |
| `none` | No spend, no target — skip target-based checks entirely. |

Never assert "unconstrained" from a null inline target alone — portfolio may be supplying it.

When any record has `target_source=portfolio`, open the report with a one-line note: `> Portfolio: {name} (tCPA {$x} | tROAS {y})` for each unique portfolio.

**M1 — Tracking health check.** Read `context/analysis/tracking-audit.md` if it exists. If the tracking audit has active FAILs on attribution, OCT, or consent, flag as a blocking Measurement hypothesis — do not recommend negation until resolved.

**B1 — Are targets current?** Read `context/analysis/strategy-audit.md` if it exists. If unit economics or goal viability failed recently, route users to `/strategy-specialist` before optimizing terms.

**B2 — Relevant-but-underperforming routing.** For every flagged term in ST-D03 (underperforming) or ST-D14 (inefficient n-grams): cross-reference against business.md core tokens. Terms that match core product/service language are **relevant but underperforming** — they are a conversion problem, not a traffic problem. Route to `/lp-auditor` + `/offer-auditor`. **Never auto-negate.**

### What to produce

An ordered hypothesis list ranked by layer (Measurement → Business → Traffic). Each hypothesis drives one row in Phase 2's Evidence Ladder and one entry in the Actions section, routed to the correct bucket.

**Anti-patterns — never do these:**

- Writing "Negate these 47 terms" when any are relevant-but-underperforming and match core business language. Correct output: "These terms match your core product — the problem is conversion (LP / offer / targets), not traffic. Run `/lp-auditor`, `/offer-auditor`, adjust targets first."
- Writing any negation while a Measurement hypothesis is unresolved. Correct output: "Pending `/tracking-specialist` — verify attribution first."
- Asserting "unconstrained campaign" from a null inline target alone. Check `target_source` first.
- Flat "Recommended Actions" table that treats a tracking anomaly and a negation at equal weight. Always segment by cascade state.

---

## Phase 2: Score & Log

### Scoring summary

- PASS = full points retained
- WARN = deduct 40% of check's points
- FAIL = deduct 100% of check's points
- SKIP = excluded from scoring (reduce denominator)
- INFO = no points at stake

Compute: `score = points_earned / (100 - skipped_points) * 100`

### Grade thresholds

| Score | Grade |
|-------|-------|
| 90-100 | Excellent |
| 70-89 | Good |
| 50-69 | Needs Attention |
| 30-49 | Poor |
| 0-29 | Critical |

### Append to log

Append a timestamped entry to `context/analysis/search-term-audit-log.md`. If the file doesn't exist, create it with header `# Search Term Audit Log`. Use the log entry format from `reference/report-template.md`.

---

## Phase 2.5: Peer Report Lookup (MANDATORY before writing the report)

**Don't send the user from one door to the other.** Before recommending any peer-skill handoff in Phase 3, check whether that peer has already produced a fresh report — and if so, **read it and integrate its findings into THIS report** instead of asking the user to re-run.

The whole point of cross-skill awareness is that a user who runs `/tracking-specialist` last week and then runs `/search-term-auditor` this week sees the tracking findings *quoted inside the search-term report*, not a redundant "go run tracking" instruction. Re-running an auditor that already produced a fresh answer wastes time and obscures the search-term-side action.

#### Freshness windows

| Peer skill | Report file | Fresh window |
|---|---|---|
| `/quality-score-auditor` | `context/analysis/quality-score-audit.md` | ≤ 7 days |
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
3. **If fresh:** open the report and read its **executive read / diagnosis / top findings / module scores**. Pull out the 1–3 findings that overlap with this audit's flagged terms, n-grams, ad groups, or campaigns. Use them to:
   - **Enrich the Executive read at the top of `search-term-audit.md`** — quote the peer's score, the headline finding, and the date inline.
   - **Replace** the routing line "run `/peer-skill`" with: **"Review the existing {date} {peer} report at {path} — top finding: '{one-liner}'. Re-run only if you want fresher data."**
   - In Actions / handoff sections, when a peer handoff is the recommended action, quote the peer's specific finding so the user can act without leaving this report.
4. **If stale:** mention "a previous {peer} report exists from {date} but is {N} days old — recommend re-running before relying on it" and keep the handoff as a re-run.
5. **If missing:** standard "run `/peer-skill`" handoff.

#### When a fresh peer report contradicts a search-term hypothesis

Say so explicitly in the Executive read. Example: search-term-auditor flags Campaign X for high non-converting waste — but the fresh tracking-audit shows the conversion event for that campaign is misfiring. The waste finding is then unreliable; negating terms won't help if conversions aren't being recorded. Or: search-term-auditor proposes negating an n-gram that the fresh keyword-audit shows is the lead n-gram in a converting close-variant cluster. **The search-term report must surface the contradiction, not silently propose the negation.**

That cross-skill validation is the entire reason this phase exists. A search-term audit that ignores a fresh tracking, QS, or keyword audit produces a confidently-wrong recommendation.

---

## Phase 3: Write Report

Write `context/analysis/search-term-audit.md` using the template in `reference/report-template.md`. This report is regenerated on each run (overwrites previous). The log (Phase 2) preserves history.

**Lead with the Executive read** — the 6-slot prose contract defined in `reference/report-template.md`. Apply Phase 2.5 lookup results to slot 4 (inline-quoted fresh peer findings) and to every line in the Actions section that points to a peer skill.

The body of the report is organized around the **hypothesis list from Phase 1.5**, not around the diagnostic list. Fill in all sections in this order:

1. **Executive read** (prose, ≤300 words, no bullets) — score meaning, 1–3 priorities w/ why, what's NOT a problem, fresh peer findings inline, how-to-read, score trend.
2. **Diagnosis** — one paragraph stating the root-cause hypothesis and what to do first. Natural language, not bullets.
3. **Portfolio notice** — one-liner per unique portfolio, only when any record has `target_source=portfolio`.
4. **Evidence Ladder** — grouped by cascade layer (Measurement, Business, Traffic). Each bullet a factual observation tagged `→ H{n}`.
5. **Module Scores** — 5-row table.
6. **Actions — segmented by cascade state:**
   - `🔍 Investigate first` — blocking upstream handoffs (Measurement / Business hypotheses). Apply Phase 2.5: every line says either "run /peer" (missing/stale) or "review existing {date} report at {path}" (fresh, with the one-liner finding).
   - `🔧 Structural fix needed` — routes to `/lp-auditor`, `/offer-auditor`, `/strategy-specialist`, or target adjustment. Apply Phase 2.5 to every peer handoff.
   - `✅ Act now (safe)` — terms that survived the cascade: irrelevant non-converters, n-gram candidates on non-core terms, structural fixes (D08/D09/D10/D11).
   - `⚠️ Do NOT negate` — relevant-but-underperforming list with reasoning.
7. **Module Details** — full per-diagnostic breakdown for reference.

---

## Phase 4: Present Results & Sequenced Handoff

Already written in Phase 3; Phase 4 is the user-facing presentation. The reader should be able to act from the **Executive read alone** — that's the bar. Everything else is reference material.

Present to user, in this order:

1. **Executive read** — quote the prose section from the report verbatim, don't re-summarize. It already covers score-meaning, this-week priorities w/ why, what's-NOT-a-problem, fresh peer findings inline, how-to-read, score trend.
2. **Score, grade, and headline diagnosis** — the diagnosis paragraph from Phase 3. Lead with "The problem is at the {layer} layer — {one-sentence root cause}."
3. **Top hypothesis** — name, layer, evidence, confidence, explained waste %.
4. **Module scores** — 5-row table.
5. **Sequenced handoff offer** — read `reference/handoff-matrix.md`. Never present handoffs as a flat menu. **Apply Phase 2.5 lookup results to every peer handoff line:** each handoff says either "review existing {date} report at {path} (top finding: ...)" or "run `/peer-skill`".

Template:

> **Top hypothesis:** {layer} — {name} (explains ~{pct}% of flagged waste)
>
> Before applying any negations, here's what I'd run in order:
>
> 1. **{blocking Measurement handoff}** — {why} → `/tracking-specialist`
> 2. **{Business-layer handoff}** — {why} → `/strategy-specialist`
> 3. **Conversion check** — `/lp-auditor` + `/offer-auditor` for the {N} relevant-but-underperforming terms
> 4. **Safe structural fixes** — `/search-term-optimizer conflicts` ({X} conflicts), `/search-term-optimizer consolidate` ({Y} consolidation opportunities)
> 5. **Negation cycle (only after upstream clear):** `/search-term-optimizer negate`, `/search-term-optimizer ngrams`
> 6. **Promotion candidates ({Z})** — `/search-term-optimizer promote` (respects advertiser's existing match-type setup)
>
> Which would you like to start with?

When no upstream hypothesis is active, revert to the standard menu but still ordered by safety:

> "Found {N} actionable issues. Cascade clear. Ordered by priority:
>
> - **Safest (always-safe structural fixes):** `/search-term-optimizer conflicts`, `/search-term-optimizer consolidate`
> - **Negate & exclude ({X} terms):** `/search-term-optimizer negate`, `/search-term-optimizer ngrams`
> - **Promote ({Y} candidates):** `/search-term-optimizer promote`
> - **PMax brand defense ({Z}):** `/search-term-optimizer brand`"

Only show subcommands that have findings to act on.

---

## Self-Learning

After user reviews the report, if they mark terms as relevant or reject proposed n-grams, update `context/analysis/search-term-decisions.json`:

```json
{
  "relevantTerms": ["term1", "term2"],
  "rejectedNgrams": ["ngram1", "ngram2"],
  "updatedAt": "2026-04-17T..."
}
```

The analysis scripts filter these out on next run. Merge entries; never overwrite.

---

## Edge Cases

| Scenario | Handling |
|----------|----------|
| No search-terms-periodA.csv | Stop — `/search-term-auditor` requires the data pull to complete. |
| No PMax campaigns | Skip ST-D25, D26. Module 5 scoring denominator reduced. |
| Single-campaign account | Skip cross-campaign checks (D10, D21). Note in report. |
| No shared negative lists | ST-D07 = FAIL (coverage gap). Suggest bootstrap via optimizer. |
| Portfolio bid strategy | Resolved automatically via `bidding-strategies.csv`. Every flagged record carries `target_source` and `portfolio_name`. Synthesis treats `target_source=portfolio` as constrained; reserves "unconstrained" for `target_source=fallback`. Surface portfolio name(s) and tCPA/tROAS when present. |
| Branded campaigns | Excluded from scope per `excludeBrandedCampaigns` config. Use explicit `brandedCampaigns` list when available; falls back to name-pattern match. |
| Missing negative CSVs | Module 2 diagnostics SKIP with warning. Run `/gads-context` first or wait for pull-all.js to fetch them. |
| Very large account (>100k terms) | Scripts handle volume. Claude sees only flagged items. Report summarizes totals. |
| targetROAS entered as percentage (e.g. 530) | `normalizeRoasRatio()` coerces to ratio (5.3) with a warning. All downstream logic uses ratio form. |

---

## Integration Points

### Reads from
- `context/business.md` — CPA/ROAS targets, core product tokens
- `context/google-ads/data/*.csv` — raw data (pulled by `pull-all.js`)
- `context/analysis/search-term-decisions.json` — self-learning
- `context/analysis/tracking-audit.md` — upstream measurement check (optional)
- `context/analysis/strategy-audit.md` — upstream business check (optional)
- `config/ads-context.config.json` — thresholds, list names, branded list

### Writes to
- `context/analysis/search-term-audit.md` — full report (overwritten each run)
- `context/analysis/search-term-audit-log.md` — append-only timestamped log
- `context/analysis/search-term-decisions.json` — self-learning updates
- `.claude/skills/search-term-auditor/tmp/*.json` — ephemeral script output

### Related skills
- `/search-term-optimizer` — execute-only counterpart (user-invoke only)
- `/tracking-specialist` — upstream Measurement handoff
- `/strategy-specialist` — upstream Business handoff (targets, unit economics)
- `/lp-auditor`, `/offer-auditor` — Conversion handoffs for relevant-but-underperforming terms
- `/keyword-auditor` — related structural skill (keyword cannibalization from promotions)
- `/competitive-analyst` — PMax brand cannibalization, competitive overlap
