# Search Term Auditor — Diagnostic Rules

Authoritative specification for every diagnostic. Each entry lists:

- **What it measures**
- **Source** — where Claude reads the data
- **Threshold logic** — PASS / WARN / FAIL criteria
- **Target-resolution contract** (for threshold diagnostics)
- **Worked example** (when helpful)

> **Target resolution contract (ST-D02, D03, D13, D14, D20):** the analysis scripts call `lib.resolveBiddingStrategy()` per campaign before any threshold math. Every flagged record carries `target_source ∈ { campaign_inline, portfolio, fallback, none }` and `portfolio_name` (when applicable). Never assert "unconstrained" from a null inline target alone — only `target_source=fallback` means no real target exists.

---

## Module 1 — Search Term Quality (25 pts)

### ST-D01 — Irrelevant spend % (5 pts)

**What:** % of total search-term spend on non-converting, irrelevant terms (as judged by Claude against business.md).
**Source:** `search-term-flags.json → quality.irrelevantSpendPct` + Claude judgment on `quality.irrelevantTerms[]`.
**Verdicts:**
- PASS: ≤ 5%
- WARN: 5% – 15%
- FAIL: > 15%

Claude reviews the top 50 `irrelevantTerms[]` and marks each as relevant / irrelevant against core product tokens in `business.md`. The % is computed against *Claude-confirmed* irrelevant terms, not the raw list.

### ST-D02 — Non-converting terms (7 pts)

**What:** Count and cost of terms with zero conversions above the spend threshold (resolved CPA target × configured multiplier, or `minSpendToFlag` if no target).
**Source:** `search-term-flags.json → quality.nonConvertingTerms[]`. Per-campaign-type breakdown in each record.
**Target contract:** Spend threshold is computed from the resolved CPA target (inline or portfolio). If `target_source=fallback`, note that the campaign has no real target.
**Verdicts:**
- PASS: < 20 terms and < 2% of total spend
- WARN: 20–50 terms or 2%–8% of spend
- FAIL: > 50 terms or > 8% of spend

### ST-D03 — Underperforming terms (7 pts)

**What:** Terms that converted but at CPA > target × `inefficientCPAMultiplier` (default 1.5×) or ROAS < target × `inefficientROASMultiplier` (default 0.7×).
**Source:** `search-term-flags.json → quality.underperformingTerms[]`. Per-campaign-type breakdown.
**Target contract:** Uses resolved CPA/ROAS target — portfolio-attached campaigns classify against the portfolio's target, not the global fallback.
**Verdicts:**
- PASS: < 10 terms
- WARN: 10–30 terms or 2%–8% of spend
- FAIL: > 30 terms or > 8% of spend

### ST-D04 — Foreign language detection (3 pts)

**What:** Terms in languages outside the target market(s).
**Source:** Claude reviews a sample of 30 high-cost terms from `quality.irrelevantTerms[]` + `quality.nonConvertingTerms[]`.
**Verdicts:**
- PASS: no non-target-language terms
- WARN: 1–5 terms (< 1% of spend)
- FAIL: > 5 terms or > 1% of spend

### ST-D05 — Trending term detection (3 pts, INFO)

**What:** Emerging query patterns — terms with meaningful Period A spend that were near-zero in Period B.
**Source:** `search-term-flags.json → quality.trendingTerms[]`.
**Verdicts:** INFO only — not scored. Surface top 10 to the user for strategic review.

---

## Module 2 — Negative Keyword Coverage (25 pts)

### ST-D06 — Campaigns without any negatives (5 pts)

**Source:** `negative-flags.json → coverage.campaignsWithoutNegatives[]`.
**Verdicts:**
- PASS: 0 campaigns
- WARN: 1–2 campaigns (or single small campaign)
- FAIL: ≥ 3 campaigns without any negative coverage

### ST-D07 — Campaigns without shared negative lists (5 pts)

**Source:** `negative-flags.json → coverage.campaignsWithoutSharedLists[]`.
**Verdicts:**
- PASS: 0 campaigns
- WARN: 1–2 campaigns
- FAIL: ≥ 3 campaigns not linked to any shared list

### ST-D08 — Negative conflicts (5 pts)

**What:** Active negative keyword that blocks an existing active keyword in the same scope (exact text match).
**Source:** `negative-flags.json → coverage.negativeConflicts[]`.
**Verdicts:**
- PASS: 0 conflicts
- WARN: 1–5 conflicts
- FAIL: > 5 conflicts or ≥ 1 conflict blocking a converting keyword

### ST-D09 — Repeated ad-group negatives (3 pts)

**What:** Same negative term repeated in ≥ 3 ad groups within a campaign (consolidation opportunity).
**Source:** `negative-flags.json → coverage.repeatedAdGroupNegatives[]`.
**Routing filter:** Each entry carries `likely_routing` (boolean) + `routing_evidence`. An entry is flagged routing when the negative-term token appears as a positive keyword or converting search term in OTHER ad groups in the same campaign. Routing entries are reported as INFO only — they do NOT count toward the verdict and must NOT be handed to the optimizer for consolidation.
**Verdicts (count `likely_routing === false` entries only):**
- PASS: < 3 consolidatable term/campaign combinations
- WARN: 3–10 combinations
- FAIL: > 10 combinations

### ST-D10 — Repeated campaign negatives (3 pts)

**What:** Same negative term repeated in ≥ 3 campaigns (potential consolidation opportunity — move to shared list).
**Source:** `negative-flags.json → coverage.repeatedCampaignNegatives[]`.
**Routing filter:** Each entry carries `likely_routing` (boolean) + `routing_evidence`. An entry is flagged routing when the negative-term token appears as a positive keyword or converting search term in OTHER (non-flagged) campaigns — strong signal of intentional traffic routing between campaign clusters. Routing entries are reported as INFO only — they do NOT count toward the verdict and must NOT be promoted to a shared list. The `searchTermAnalysis.routingNegatives` config array force-flags additional terms.
**Verdicts (count `likely_routing === false` entries only):**
- PASS: < 3 consolidatable term combinations
- WARN: 3–10 combinations
- FAIL: > 10 combinations

**Data dependency:** requires `keywords-active.csv` (pulled by `pull-all.js` via `keywords-active.gaql`). Without it, routing detection runs without positive-keyword evidence and a warning is added to `meta.warnings`.

### ST-D11 — Legacy +modified +broad negatives (2 pts)

**What:** Negatives still using the deprecated `+modified +broad` format (e.g. `+free +trial`). Google no longer honors the `+` prefix on negatives.
**Source:** `negative-flags.json → coverage.legacyModifiedBroad[]`.
**Verdicts:**
- PASS: 0 entries
- WARN: 1–10 entries
- FAIL: > 10 entries

### ST-D12 — Catalog completeness (2 pts, WARN/INFO)

**What:** Compare existing negatives against vertical-specific catalog patterns (template/discount/competitor/informational).
**Source:** Claude compares `negative-flags.json → coverage` against the catalog patterns distilled from the Negative Keyword Catalog SOP.
**Verdicts:** WARN (missing obvious categories), INFO (catalog candidates found). Handoff to `/search-term-optimizer catalog`.

---

## Module 3 — N-gram Analysis (20 pts)

### ST-D13 — Non-converting n-grams (7 pts)

**What:** Token sequences (1-grams + 2-grams) that appear in ≥ `minDistinctTerms` terms, clear `minImpressions`/`minClicks` thresholds, and have spend ≥ target × `nonConvertingSpendMultiplier` (default 2×) with 0 conversions.
**Source:** `negative-flags.json → ngrams.nonConverting[]`.
**Target contract:** Threshold uses the dominant campaign's resolved target. Records with `target_source=fallback` should be flagged in synthesis — they may be waste *or* a campaign missing a target.
**Per-campaign-type breakdown:** `campaign_types` field lists which channels the n-gram appears in.
**Verdicts:**
- PASS: < 10 n-grams or < 1% of spend
- WARN: 10–30 n-grams or 1%–5% of spend
- FAIL: > 30 n-grams or > 5% of spend

### ST-D14 — Inefficient n-grams (7 pts)

**What:** N-grams with conversions but CPA > target × `inefficientCPAMultiplier` (default 1.75×) or ROAS < target × `inefficientROASMultiplier` (default 0.7×).
**Source:** `negative-flags.json → ngrams.inefficient[]`.
**Target contract:** Uses dominant campaign's resolved target. Portfolio-attached campaigns honored.
**Verdicts:**
- PASS: < 5 n-grams
- WARN: 5–15 n-grams
- FAIL: > 15 n-grams

### ST-D15 — Shared list staleness (3 pts)

**What:** Shared negative lists not updated recently (≥ 180 days since last modification).
**Source:** `negative-flags.json → ngrams.listStaleness`.
**Current limitation:** The Google Ads API does not expose shared-list modified timestamps in the query we use. Surface as INFO with a warning note and suggest manual review or n-gram cycle run.
**Verdicts:** INFO only until API support improves.

### ST-D16 — Volume concentration (3 pts, INFO)

**What:** Top 5 n-grams' share of total flagged waste. Prioritization signal — if 5 n-grams explain 80% of waste, fix those first.
**Source:** `negative-flags.json → ngrams.volumeConcentration`.
**Verdicts:** INFO only. Always surface `topShareOfFlaggedSpendPct` in the report.

---

## Module 4 — Close Variant Monitoring (15 pts)

### ST-D17 — Performance drift (5 pts)

**What:** Close variants performing differently from the parent keyword (CPA above parent's, or converting poorly while parent converts well).
**Source:** `search-term-flags.json → closeVariants.driftCandidates[]`. Claude compares each variant's CPA/ROAS to the parent's historical norm.
**Verdicts:**
- PASS: no meaningful drift
- WARN: 1–5 variants with CPA > 1.5× parent
- FAIL: > 5 variants or > 2× spend leakage

### ST-D18 — Spend share (5 pts)

**What:** Close variants consuming disproportionate spend share relative to exact matches.
**Source:** `search-term-flags.json → closeVariants.highSpendVariants[]`.
**Verdicts:** Claude judgment — flag any variant > 30% of the parent keyword's spend.
- PASS: no variants > 30% of parent spend
- WARN: 1–3 variants above threshold
- FAIL: > 3 or any variant > 50% of parent spend

### ST-D19 — Unintended expansion (5 pts)

**What:** Variants that match unrelated intent (semantic drift beyond parent keyword).
**Source:** Claude reviews `closeVariants.driftCandidates[]` for semantic mismatch.
**Verdicts:**
- PASS: variants all semantically adjacent
- WARN: 1–5 semantically unrelated variants
- FAIL: > 5 or high-cost unrelated variants

---

## Module 5 — Promotion & PMax (15 pts)

### ST-D20 — High performers not yet keywords (5 pts)

**What:** Converting terms meeting/beating the resolved target that aren't yet keywords in any ad group.
**Source:** `search-term-flags.json → promotion.candidates[]`.
**Target contract:** Uses resolved target for the term's campaign.
**Verdicts:**
- PASS: all candidates have been reviewed
- WARN: 5–20 candidates pending
- FAIL: > 20 candidates pending review

### ST-D21 — Duplicates across campaigns (3 pts)

**What:** Same term appearing in promotion candidate list across multiple campaigns (cannibalization risk).
**Source:** Claude reviews `promotion.candidates[]` grouping by term.
**Verdicts:**
- PASS: no cross-campaign duplicates
- WARN: 1–5 duplicates
- FAIL: > 5 duplicates

### ST-D22 — Coverage ratio (3 pts)

**What:** % of converting terms that are already keywords.
**Source:** `search-term-flags.json → promotion.coverageRatio`.
**Verdicts:**
- PASS: ≥ 70%
- WARN: 50%–70%
- FAIL: < 50%

### ~~ST-D23~~ — Removed (folded into ST-D02 with campaign-type segmentation)

### ~~ST-D24~~ — Removed (folded into ST-D03 with campaign-type segmentation)

### ST-D25 — PMax brand query % (2 pts)

**What:** % of PMax search terms matching brand terms (cannibalization of organic / Branded Search).
**Source:** `search-term-flags.json → pmaxAnalysis.brandQueryPct`.
**Verdicts:**
- PASS: ≤ 10%
- WARN: 10%–25%
- FAIL: > 25%

### ST-D26 — PMax/Search overlap (2 pts)

**What:** Terms appearing in both PMax and Search campaigns.
**Source:** `search-term-flags.json → pmaxAnalysis.searchOverlap[]`. Claude confirms overlap is genuine.
**Verdicts:**
- PASS: < 5% of PMax terms overlap
- WARN: 5%–15%
- FAIL: > 15%

**Handoff:** This is a diagnostic signal only. Remediation is owned by `/keyword-auditor` (KW-D12 Search vs PMax Overlap), which performs the spend-share analysis and recommends exact-match ownership in Search plus PMax asset-group adjustments. Do not route to `/search-term-optimizer`.

---

## Scoring weights (total = 100)

| Module | Points |
|--------|-------:|
| 1 — Quality (D01–D05) | 25 |
| 2 — Coverage (D06–D12) | 25 |
| 3 — N-grams (D13–D16) | 20 |
| 4 — Close Variants (D17–D19) | 15 |
| 5 — Promotion & PMax (D20–D26; D23/D24 removed) | 15 |
| **Total** | **100** |

SKIP diagnostics are removed from both numerator and denominator (e.g. if no PMax campaigns, D25/D26 are removed — Module 5 scores out of 11).
