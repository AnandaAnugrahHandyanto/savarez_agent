# Quality Score Auditor — Diagnostic Rules (QS-D01 to QS-D17)

16 scored diagnostics across 4 modules (100 points) + 1 INFO-only diagnostic (QS-D17 Customizer Integrity, 0 points).

Thresholds resolve from `config.qualityScoreAudit.thresholds` (populated in Phase 0.0) with SOP-sourced defaults from `sops/Diagnostic Thresholds Reference.md`.

---

## Module 1: QS Distribution (20 points, 6 diagnostics)

### QS-D01: Impression-weighted QS (account)

**Points:** 6
**Data source:** `qs-tiers.csv` — aggregate `quality_score × impressions / sum(impressions)` across all rows with non-null QS.

| Condition | Verdict | Severity | Points |
|---|---|---|---|
| Weighted QS ≥ 7.0 | PASS | -- | 6/6 |
| Weighted QS 5.0–6.9 | WARN | Medium | 3.6/6 |
| Weighted QS < 5.0 | FAIL | High | 0/6 |

**Details to include:** account-level weighted QS, keyword count, impression count, null-QS exclusion count.

**Routing:** Informational at Module level — finding routes through Module 2 components.

---

### QS-D02: Low-QS concentration

**Points:** 4
**Data source:** `qs-tiers.csv` — `count(quality_score ≤ 3) / count(quality_score not null)`.

| Condition | Verdict | Severity | Points |
|---|---|---|---|
| ≤ 10% of active keywords | PASS | -- | 4/4 |
| > 10% | FAIL | High | 0/4 |

**Details to include:** keyword count, % share, example low-QS keywords by spend.

---

### QS-D03: High-spend low-QS

**Points:** 4
**Data source:** `qs-flags.csv` → `flag_type=HIGH_SPEND_LOW_QS` (top 20% by spend AND QS < 5).

| Condition | Verdict | Severity | Points |
|---|---|---|---|
| 0 flagged keywords | PASS | -- | 4/4 |
| Any flagged | FAIL | Critical | 0/4 |

**Details to include:** list of high-spend low-QS keywords with spend, QS, dominant limiting component, class.

**Routing:** Top priority for handoff — route each to the correct optimizer based on `dominant_limiting_component`.

---

### QS-D04: QS by campaign

**Points:** 3
**Data source:** `qs-tiers.csv` — group by campaign_id, weighted QS per campaign.

| Condition | Verdict | Severity | Points |
|---|---|---|---|
| All campaigns weighted QS ≥ 5.0 | PASS | -- | 3/3 |
| Any campaign weighted QS < 5.0 | FAIL | Medium | 0/3 |

**Details to include:** per-campaign weighted QS table (include `bidding_mode`, `target_source`, keyword count).

---

### QS-D05: QS by ad group

**Points:** 2
**Data source:** `qs-tiers.csv` — group by ad_group_id.

| Condition | Verdict | Severity | Points |
|---|---|---|---|
| All ad groups weighted QS ≥ 5.0 | PASS | -- | 2/2 |
| Any ad group weighted QS < 5.0 | FAIL | Medium | 0/2 |

**Details to include:** bottom-10 ad groups by weighted QS with keyword count and dominant limiting component.

---

### QS-D06: Null QS coverage

**Points:** 1
**Data source:** `qs-tiers.csv` — `count(quality_score == '') / count(rows)`.

| Condition | Verdict | Severity | Points |
|---|---|---|---|
| ≤ 30% null QS | PASS | -- | 1/1 |
| > 30% null QS | WARN | Low | 0.4/1 |

**Details to include:** null-QS count, % share, note on insufficient-impressions cause. Report states: "Re-audit in 30 days once impressions accrue."

---

## Module 2: Component Breakdown (45 points, 4 diagnostics)

Each component diagnostic is filtered by keyword `class` — COMPETITOR-classed rows are excluded from AR scoring because structural Below-Avg AR is expected on conquesting keywords.

### QS-D07: Ad Relevance health

**Points:** 16
**Data source:** `qs-flags.csv` → `flag_type=AR_BELOW_AVG` (COMPETITOR-class flagged as `AR_BELOW_AVG_COMPETITOR` and excluded).

**Denominator:** keywords with non-null AR rating AND `class != COMPETITOR`.

| Condition | Verdict | Severity | Points |
|---|---|---|---|
| ≤ 10% Below Avg | PASS | -- | 16/16 |
| 10–25% Below Avg | WARN | Medium | 9.6/16 |
| > 25% Below Avg | FAIL | High | 0/16 |

**Details to include:** count + % Below Avg (excluding COMPETITOR), count of COMPETITOR keywords surfaced as INFO, top-spend AR Below Avg by ad group.

**Routing:** Handoff Queue — Ad Relevance → `/rsa-maker` (copy). When the Headline Test fails (structural intent divergence), the finding is surfaced as a pending `keyword-restructurer` handoff — that skill isn't built yet, so the report carries a structural-split brief with no active route.

---

### QS-D08: Expected CTR health

**Points:** 13
**Data source:** `qs-flags.csv` → `flag_type=ECTR_BELOW_AVG`.

**Denominator:** keywords with non-null ECTR rating.

| Condition | Verdict | Severity | Points |
|---|---|---|---|
| ≤ 10% Below Avg | PASS | -- | 13/13 |
| 10–25% Below Avg | WARN | Medium | 7.8/13 |
| > 25% Below Avg | FAIL | High | 0/13 |

**Details to include:** count + % Below Avg, top-spend ECTR Below Avg by ad group, AR status on same keywords (ECTR fixes are blocked if AR is Below Avg — flag to run AR first).

**Routing:** Handoff Queue — Expected CTR → `/offer-maker` + `/rsa-maker` (only after AR = Average+).

---

### QS-D09: Landing Page Experience health

**Points:** 13
**Data source:** `qs-flags.csv` → `flag_type=LP_BELOW_AVG`.

**Denominator:** keywords with non-null LP rating.

| Condition | Verdict | Severity | Points |
|---|---|---|---|
| ≤ 10% Below Avg | PASS | -- | 13/13 |
| 10–25% Below Avg | WARN | Medium | 7.8/13 |
| > 25% Below Avg | FAIL | High | 0/13 |

**Details to include:** count + % Below Avg, group by effective landing-page URL to identify LP URLs with the most Below Avg keywords, include branded-campaign LP flags separately (escalated severity).

**URL resolution — use the keyword-level override when set.** Google's LP Experience signal is evaluated against the URL actually served:

1. If `ad_group_criterion.final_urls` is populated on the keyword (a keyword-level override) → that is the URL the LP rating applies to. Group by this.
2. Otherwise the ad's `ad_group_ad.ad.final_urls` (from `qs-ads.csv`) is what served — fall back to that for grouping.

Never group by campaign tracking template or AG-level URL defaults — those aren't what Google scored. Column precedence in `qs-tiers.csv`: `final_urls` (keyword-level override, empty when no override is set) → ad-level `final_urls` via `ad_group_id` join to `qs-ads.csv`.

**Routing:** Handoff Queue — LP Experience → `/lp-auditor` → `/lp-optimizer`. LP fixes run parallel to AR/ECTR work.

---

### QS-D10: Dominant limiting component

**Points:** 3
**Data source:** `qs-tiers.csv` — aggregate `dominant_limiting_component` across rows with any Below-Avg component (excluding COMPETITOR for AR).

| Condition | Verdict | Severity | Points |
|---|---|---|---|
| No single component accounts for > 50% of Below-Avg ratings | PASS | -- | 3/3 |
| One component > 50% | WARN | Medium | 1.8/3 |

**Details to include:** distribution % per component (AR / ECTR / LP), conclusion "systemic {component} issue — systemic fix needed" when WARN.

**Routing:** Informational — inform prioritization in Phase 3 handoff.

---

## Module 3: Historical Trends (15 points, 4 diagnostics)

SKIPs entirely if `qs-trends.csv` is empty or every row has `qs_trajectory=INSUFFICIENT_DATA` (account has <60d of stable QS history).

### QS-D11: QS trend overall

**Points:** 6
**Data source:** `qs-trends.csv` — account-level aggregate of `qs_trajectory`.

| Condition | Verdict | Severity | Points |
|---|---|---|---|
| Account weighted QS trajectory STABLE or IMPROVING | PASS | -- | 6/6 |
| Weighted decline 1–2 points (DECLINING majority) | WARN | Medium | 3.6/6 |
| Weighted decline ≥ 2 points (DECLINING_SHARP majority) | FAIL | High | 0/6 |

**Details to include:** account-level first vs last weighted QS, trajectory distribution table, top-declining keywords by impressions.

---

### QS-D12: Component trends

**Points:** 4
**Data source:** `qs-trends.csv` — per-component trajectory counts (`ar_trajectory`, `ectr_trajectory`, `lp_trajectory`).

| Condition | Verdict | Severity | Points |
|---|---|---|---|
| All three components stable or improving | PASS | -- | 4/4 |
| Any component has > 10% declining keywords | WARN | Medium | 2.4/4 |

**Details to include:** per-component counts (IMPROVING / STABLE / DECLINING / INSUFFICIENT_DATA), cross-reference with Module 2 current state.

---

### QS-D13: QS change after optimization

**Points:** 3
**Data source:** `qs-trends.csv` — `changelog_events_near` column (non-zero indicates changes within the trend window).

| Condition | Verdict | Severity | Points |
|---|---|---|---|
| No changelog events AND stable trajectory | PASS | -- | 3/3 |
| Changelog events correlate with IMPROVING trajectory | PASS (+ INFO "optimization working") | -- | 3/3 |
| Changelog events correlate with DECLINING trajectory | WARN (+ INFO "optimization regressed QS") | Medium | 1.8/3 |
| Changelog missing or empty | SKIP | -- | --/-- |

**Details to include:** changelog events found, correlated keyword count, example before/after slopes.

**Routing:** If changelog missing — nudge: "Run `/gads-context` or `/account-changelog` to enable post-optimization trend analysis."

---

### QS-D14: Seasonal QS patterns

**Points:** 2
**Data source:** `qs-trends.csv` — year-over-year comparison (only possible with >52 weeks of data).

| Condition | Verdict | Severity | Points |
|---|---|---|---|
| No seasonal pattern detected OR pattern consistent with prior year | PASS (INFO) | -- | 2/2 |
| Current decline matches prior-year seasonal dip | INFO — "seasonal, not structural" | -- | 2/2 |
| Insufficient history (<52 weeks) | SKIP | -- | --/-- |

**Details to include:** year-over-year QS delta (if any), seasonal windows observed.

---

## Module 4: Competitive Context (20 points, 2 diagnostics)

### QS-D15: Lost IS Rank vs QS

**Points:** 14
**Data source:** `qs-flags.csv` → `flag_type=LOST_IS_RANK_QS` (campaigns with > 15% Lost IS (rank) AND weighted QS < 6).

| Condition | Verdict | Severity | Points |
|---|---|---|---|
| 0 campaigns flagged | PASS | -- | 14/14 |
| Any campaign flagged | FAIL | High | 0/14 |

**Details to include:** per-campaign Lost IS (rank) %, weighted QS, dominant limiting component, recommended route (to Module 2 component optimizer).

**Routing:** High-priority — this is the single clearest signal that QS is costing traffic. Route to the correct Module 2 component optimizer for the campaign.

---

### QS-D16: CPC premium by QS tier

**Points:** 6
**Data source:** `qs-flags.csv` → `flag_type=CPC_PREMIUM_LOW_QS` (avg CPC > 30% above ad-group avg on QS < 5 keywords).

| Condition | Verdict | Severity | Points |
|---|---|---|---|
| 0 flagged | PASS | -- | 6/6 |
| Any flagged | WARN | Medium | 3.6/6 |

**Details to include:** per-keyword CPC premium %, ad-group avg CPC, QS, expected CPC savings if QS reaches 7.

**Routing:** Informs Module 2 priority — CPC premium makes the same QS fix more valuable on these keywords.

---

## QS-D17: Customizer Integrity (INFO-only, 0 points)

**Points:** 0 (INFO-only — does not enter score)
**Data source:** `qs-customizers.csv` — `integrity_status` + `effective_resolution` columns. The analysis script walks the full Google Ads customizer hierarchy (KEYWORD → AD_GROUP → CAMPAIGN → CUSTOMER) to determine whether each `{CUSTOMIZER.<name>}` reference in an RSA actually resolves to a bound value, or falls back to the inline `:default` every time.

**Purpose:** Surface setups where `{CUSTOMIZER.<name>}` references in RSAs don't resolve to a real value. Two failure modes:

- `BROKEN` — the referenced attribute name isn't defined on the account at all (typo, deleted attribute, etc.). Google rejects placement if this happens at ad creation, but definitions can drift afterward.
- `EFFECTIVELY_STATIC` — the attribute is defined but has no binding at keyword / AG / campaign / customer level for this AG. The RSA renders the `:default` fallback every impression.

Both produce false-signal AR Below Avg ratings on ad groups the advertiser thought were covered by customizers.

| Condition | Verdict | Severity |
|---|---|---|
| 0 ad groups with `BROKEN` or `EFFECTIVELY_STATIC` | PASS | -- |
| Any ad group with `BROKEN` | WARN | Medium |
| Any ad group with `EFFECTIVELY_STATIC` (no `BROKEN`) | WARN | Low |
| Both present | WARN | Medium |
| No customizers in use anywhere (`NO_CUSTOMIZERS` for all AGs) | INFO (not a problem) | -- |

**Details to include (when WARN):** list of AGs with each failure mode, the attribute names affected, the `effective_resolution` column per AG (e.g. `headline_1:NONE|path_1:NONE`), and the number of enabled RSAs in each AG affected. Frame as "this is likely why AR is Below Avg on these AGs — Google is rendering the default every time."

**Routing:** No automated handoff. The fix is manual:

- `BROKEN` → create the missing `customizer_attribute`, or remove the `{CUSTOMIZER.<name>}` reference from the RSA.
- `EFFECTIVELY_STATIC` → add a binding at keyword / AG / campaign / customer level (depending on intent), or remove the reference and bake the value into the headline directly.

Flag in the report and re-audit after the fix.

**Note:** D17 does not enter the score calculation — broken setups typically manifest as AR Below Avg (already penalized by D07). D17 exists to surface the root cause without double-counting.

---

## Summary

| Module | Points | Diagnostics |
|---|---:|---|
| M1 QS Distribution | 20 | D01(6) + D02(4) + D03(4) + D04(3) + D05(2) + D06(1) |
| M2 Component Breakdown | 45 | D07(16) + D08(13) + D09(13) + D10(3) |
| M3 Historical Trends | 15 | D11(6) + D12(4) + D13(3) + D14(2) |
| M4 Competitive Context | 20 | D15(14) + D16(6) |
| INFO-only | 0 | D17 Customizer Integrity |
| **Total scored** | **100** | **16 scored diagnostics + 1 INFO-only** |
