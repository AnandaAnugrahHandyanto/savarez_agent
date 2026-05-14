# Competitive Analyst — Diagnostic Rules (CA-D01 to CA-D13)

13 diagnostics across 3 modules. 7 executable (API-native IS metrics), 6 skipped (require Auction Insights). Total active points: 100.

---

## Module 1: IS Health & Trends (30 points)

### CA-D01: Impression Share Trajectory

**Points:** 15
**Data source:** `competitive-flags.csv` filtered to `flag_type = IS_DECLINING`

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| No campaign with IS decline >5pp/30d or >10pp/90d | PASS | -- | 15/15 |
| Any campaign >5pp decline in 30 days | WARN | Medium | 9/15 |
| Any campaign >10pp decline over 90 days | FAIL | High | 0/15 |

**Details to include:**
- Per-campaign IS trajectory table: campaign name, recent 30d avg IS, prior 30d avg IS, 30d delta, 90d delta, trajectory (RISING/STABLE/DECLINING)
- Channel type (Search/Shopping) for each campaign
- Bidding strategy context

**Routing:** Route to constraint cascade in Phase 1.5 to determine whether IS decline is budget-driven (CA-D02) or rank-driven before recommending action.

---

### CA-D02: IS Loss Decomposition

**Points:** 15
**Data source:** `competitive-flags.csv` filtered to `flag_type IN (IS_LOSS_HIGH, IS_LOSS_BUDGET, IS_LOSS_RANK)`

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| No campaign with combined IS loss >15% | PASS | -- | 15/15 |
| Any campaign with combined IS loss 15-20% | WARN | Medium | 9/15 |
| Any campaign with combined IS loss >20% | FAIL | High | 0/15 |

**Details to include:**
- Per-campaign breakdown: campaign name, budget-lost IS %, rank-lost IS %, combined loss %, dominant loss type (BUDGET/RANK)
- Flag campaigns where budget-lost >15% (budget constraint)
- Flag campaigns where rank-lost >15% (quality/bid issue)

**Routing:**
- Budget-lost dominant → `/budget-specialist` for reallocation or increase
- Rank-lost dominant → `/keyword-auditor` (QS), `/ad-copy-specialist` (CTR), `/lp-auditor` (LP experience)

---

## Module 2: Competitive Position (35 points)

### CA-D03: Competitor Identification and Classification (SKIPPED)

**Points:** 0 (SKIP)
**Reason:** Requires Auction Insights data (overlap rate, IS per competitor). This data is only available in the Google Ads UI, not the API.

**Emit:** `SKIP — Requires Auction Insights data. This data is only available in the Google Ads UI, not the API.`

---

### CA-D04: Competitor IS Trajectory (SKIPPED)

**Points:** 0 (SKIP)
**Reason:** Requires per-competitor IS tracking from Auction Insights.

**Emit:** `SKIP — Requires Auction Insights data. This data is only available in the Google Ads UI, not the API.`

---

### CA-D05: Top-of-Page Rate Analysis

**Points:** 15
**Data source:** `competitive-flags.csv` filtered to `flag_type = TOP_IS_DECLINING`

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| No campaign with abs-top-IS or top-IS decline >5pp/30d | PASS | -- | 15/15 |
| Any campaign with abs-top-IS declining >5pp/30d | WARN | Medium | 9/15 |
| Any campaign with abs-top-IS declining >10pp/30d | FAIL | High | 0/15 |

**Details to include:**
- Per-campaign table: campaign name, recent abs-top IS, prior abs-top IS, delta, recent top IS, prior top IS, delta
- Search campaigns only (Shopping has no top-of-page metric)

**Routing:** `/bidding-specialist` to review bid targets and strategy.

---

### CA-D06: Outranking Share Trends (SKIPPED)

**Points:** 0 (SKIP)
**Reason:** Requires per-competitor outranking share from Auction Insights.

**Emit:** `SKIP — Requires Auction Insights data. This data is only available in the Google Ads UI, not the API.`

---

### CA-D07: Geographic Competitive Intensity (SKIPPED)

**Points:** 0 (SKIP)
**Reason:** Requires Auction Insights segmented by geography.

**Emit:** `SKIP — Requires Auction Insights data. This data is only available in the Google Ads UI, not the API.`

---

### CA-D08: Keyword Competitive Position

**Points:** 12
**Data source:** `competitive-flags.csv` filtered to `flag_type IN (KEYWORD_IS_PRESSURE, KEYWORD_POSITION_LOSS)` + `keyword-is.csv` for top 20 keyword table

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| <15% of top-20 keywords flagged | PASS | -- | 12/12 |
| 15-30% of top-20 keywords flagged (3-6 keywords) | WARN | Medium | 7.2/12 |
| >30% of top-20 keywords flagged (7+ keywords) | FAIL | High | 0/12 |

**Details to include:**
- Top 20 keywords by spend table: keyword, campaign, ad group, spend, IS, rank-lost IS, top IS, abs-top IS
- Flagged keywords highlighted with specific pressure type:
  - IS <30% AND rank-lost >40% → "under heavy competitive pressure"
  - Top IS <20% → "losing page position"
- Aggregate: X of 20 keywords under competitive pressure

**Routing:** `/keyword-auditor` for deep-dive on flagged keywords. `/bidding-specialist` for bid strategy review.

---

### CA-D09: Shopping Ad Group Competitive Position

**Points:** 8
**Data source:** `competitive-flags.csv` filtered to `flag_type IN (SHOPPING_AG_IS_ISOLATED_DECLINE, SHOPPING_AG_IS_SEVERE_DECLINE)`

**Availability gate:**
- No standard Shopping campaigns in account → SKIP: "No standard Shopping campaigns found. PMax asset groups do not expose IS metrics."
- Shopping campaigns exist but use single ad groups → SKIP: "Shopping campaigns use single ad groups; campaign-level IS (CA-D01/D02) already covers this."
- Only runs when Shopping campaigns with 2+ ad groups are present.

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| No isolated ad group IS declines | PASS | -- | 8/8 |
| Any ad group with isolated decline >5pp while campaign stable | WARN | Medium | 4.8/8 |
| Any ad group with severe isolated decline >10pp | FAIL | High | 0/8 |

**Details to include:**
- Per Shopping campaign, per ad group IS table: ad group name, recent IS, prior IS, delta, campaign-level delta, isolated decline magnitude
- Flag ad groups declining in isolation (category-specific competition)
- Context: isolated decline points to new competitor in specific product segment

**Routing:** Investigate product category. Check feed quality via `/product-optimizer`, review bids for the ad group.

---

### CA-D10: Seasonal Competitive Patterns (SKIPPED)

**Points:** 0 (SKIP)
**Reason:** Requires Auction Insights history for YoY comparison of competitor behavior.

**Emit:** `SKIP — Requires Auction Insights data. This data is only available in the Google Ads UI, not the API.`

---

## Module 3: Competitive Impact (35 points)

### CA-D11: CPC-Competitive Pressure Correlation

**Points:** 15
**Data source:** `competitive-flags.csv` filtered to `flag_type = CPC_COMPETITIVE_PRESSURE`

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| No campaign with significant negative CPC-IS correlation | PASS | -- | 15/15 |
| Any campaign with moderate negative correlation (r < -0.5) | WARN | Medium | 9/15 |
| Any campaign with strong negative correlation (r < -0.7) | FAIL | High | 0/15 |

**Details to include:**
- Per-campaign correlation table: campaign name, Pearson r, CPC change %, IS change direction, weeks analyzed
- Interpretation: negative correlation (IS down + CPC up) = competitive pressure. Positive or weak = no competitive signal.
- CPC trend chart data (weekly CPC and IS per campaign)

**Routing:** `/bidding-specialist` for bid strategy review. `/competitor-ads` for competitor ad copy intelligence.

---

### CA-D12: New Entrant Threat Assessment (SKIPPED)

**Points:** 0 (SKIP)
**Reason:** Requires Auction Insights to detect new competitors.

**Emit:** `SKIP — Requires Auction Insights data. This data is only available in the Google Ads UI, not the API.`

---

### CA-D13: KPI Impact Assessment

**Points:** 20
**Data source:** `competitive-flags.csv` filtered to `flag_type = KPI_IMPACT`

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| Estimated conversion loss <5% | PASS | -- | 20/20 |
| Estimated conversion loss 5-10% | WARN | Medium | 12/20 |
| Estimated conversion loss >10% | FAIL | High | 0/20 |

**Details to include:**
- Per-campaign impact table: campaign name, IS gap (pp), est. lost impressions, est. lost clicks, est. lost conversions, est. lost value, conv loss as % of total
- Metric tree walkthrough: IS decline → impressions → clicks → conversions → value
- Account-level aggregate: total estimated conversion and value loss
- Materiality assessment: is the loss significant enough to act on?

**Routing:**
- Loss <2% → note but deprioritize
- Loss 2-10% → prioritize IS recovery via budget/bid/quality improvement
- Loss >10% → escalate to `/performance-reviewer` for strategic discussion
