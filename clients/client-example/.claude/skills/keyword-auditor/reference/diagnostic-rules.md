# Keyword Auditor — Diagnostic Rules (KW-D01 to KW-D18)

17 diagnostics across 5 modules. Total: 100 points (D05 and D06 are INFO-only, 0 points).

---

## Module 1: Match Type Health (20 points)

### KW-D01: Match Type Distribution Analysis

**Points:** 3
**Data source:** `keywords.csv` — group by campaign + match_type, calculate percentages. Cross-reference campaign bid strategy from `campaigns-settings.csv`.

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| Distribution aligns with bidding strategy (broad on tCPA/tROAS, exact on Manual CPC) | PASS | -- | 3/3 |
| >50% broad match on campaign with <30 conversions/month | WARN | Medium | 1.8/3 |
| All campaigns have reasonable match type mix for their strategy | PASS | -- | 3/3 |

**Details to include:**
- % broad / phrase / exact per campaign (table)
- Bid strategy for each campaign
- Flag campaigns where match type mix conflicts with strategy

**Routing:** Informational. No direct execute action.

---

### KW-D02: Broad Without Smart Bidding

**Points:** 8
**Data source:** `keyword-flags.csv` filtered to flag_type `BROAD_WITHOUT_SMART_BIDDING`

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| 0 flags | PASS | -- | 8/8 |
| Any flags (broad match keywords on Manual CPC / Maximize Clicks) | FAIL | Critical | 0/8 |

**Details to include:**
- List of flagged keywords with campaign, ad group, bid strategy
- Keyword count affected

**Routing:** KW-E03 (match type restructure)

---

### KW-D03: Match Type Redundancy in Ad Group

**Points:** 4
**Data source:** `keyword-overlaps.csv` filtered to `flag_type = MATCH_TYPE_REDUNDANCY`

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| 0 redundant groups | PASS | -- | 4/4 |
| Any redundant groups (same root keyword in broad + phrase + exact within one AG) | WARN | Low | 2.4/4 |

**Details to include:**
- Count of redundant keyword groups
- Per group: root keyword, match types present, ad group
- Performance comparison across match types if data available

**Routing:** KW-E03 (match type restructure)

---

### KW-D04: Cross-Campaign Match Type Overlap

**Points:** 5
**Data source:** `keyword-overlaps.csv` filtered to `flag_type = CROSS_CAMPAIGN_MATCH_CONFLICT`

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| 0 cross-campaign conflicts | PASS | -- | 5/5 |
| Any conflicts detected (same keyword in multiple campaigns without intentional segmentation) | WARN | Medium | 3/5 |

**Details to include:**
- Count of conflicting keyword groups
- Per group: keyword, match types, campaigns involved
- Spend split between campaigns for each conflict
- Note: intentional alpha/beta structures are not conflicts

**Routing:** KW-E03 (match type restructure) if unintentional

---

## Module 2: Performance Segmentation (30 points)

### KW-D05: Hero Keyword Identification

**Points:** 0 (INFO only)
**Data source:** `keyword-tiers.csv` filtered to tier `HERO`

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| Heroes found | INFO | -- | 0/0 |
| No heroes found | INFO | -- | 0/0 |

**Details to include:**
- Table of hero keywords: keyword, campaign, ad group, conversions, CPA, ROAS, impression share
- % of total account conversions from heroes
- Heroes with declining impression share (flag for attention)

**Routing:** Informational. Heroes inform other diagnostics.

---

### KW-D06: Performance Tier Classification

**Points:** 0 (INFO only)
**Data source:** `keyword-tiers.csv` full dataset

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| Classification complete | INFO | -- | 0/0 |

**Details to include:**
- Summary table per campaign: count and % by tier (HERO, ACTIVE, OVER_TARGET, UNPROFITABLE, PAUSE_CANDIDATE, INSUFFICIENT_DATA, LOW_PERFORMER, ZOMBIE, DISAPPROVED)
- Account-level tier distribution
- Spend distribution by tier
- Tier definitions:
  - **HERO** — top share of spend or primary conversions in the campaign
  - **ACTIVE** — converting within profitability threshold (CPA ≤ break-even CPA / ROAS ≥ break-even ROAS)
  - **OVER_TARGET** — converting profitably but beyond campaign target (CPA above tCPA / ROAS below tROAS) — bid issue, not pause candidate
  - **UNPROFITABLE** — converting but beyond profitability threshold (CPA > break-even CPA / ROAS < break-even ROAS)
  - **PAUSE_CANDIDATE** — zero primary conversions with spend past the statistical pause gate (CPA mode: 2× break-even CPA; ROAS mode: 2× absolute pause floor; ×1.5 patience for core product terms)
  - **INSUFFICIENT_DATA** — has clicks but not enough zero-conv spend to justify a pause call
  - **LOW_PERFORMER** — impressions without clicks
  - **ZOMBIE** — zero impressions in the evaluation window
  - **DISAPPROVED** — ineligible to serve due to policy/content disapproval. Distinct from ZOMBIE because the fix is resolving the disapproval, not pausing. Routed to KW-D08-adjacent reporting but excluded from ZOMBIE scoring.

**Routing:** Informational. Tier data feeds D07, D08, D09.

---

### KW-D07: Unprofitable & Pause-Candidate Detection

**Points:** 15
**Data source:** `keyword-flags.csv` filtered to flag_types `UNPROFITABLE`, `PAUSE_CANDIDATE`, and (informational) `OVER_TARGET`

**Logic:** Scoring uses UNPROFITABLE + PAUSE_CANDIDATE only. OVER_TARGET flags are reported as bid-tuning opportunities and do NOT deduct points — they are profitable, just beyond the campaign target.

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| 0 unprofitable or pause-candidate keywords with material spend | PASS | -- | 15/15 |
| 1-3 flagged keywords, combined wasted spend <10% of account spend | WARN | Medium | 9/15 |
| 4+ flagged OR combined wasted spend >10% of account spend | FAIL | High | 0/15 |

**Details to include:**
- **UNPROFITABLE** — keyword, campaign, spend, primary conversions, efficiency metric (primary CPA or effective ROAS), profitability threshold. These are converting but beyond the profitability threshold.
- **PAUSE_CANDIDATE** — keyword, campaign, spend, clicks, pause gate threshold, core-term flag. These have zero primary conversions past the statistical pause gate (CPA mode: 2× break-even CPA × patience; ROAS mode: 2× absolute pause floor × patience).
- **OVER_TARGET** (info section) — keyword, campaign, efficiency metric (primary CPA / effective ROAS), campaign target, profitability threshold. These are profitable but beyond the campaign target — recommend bid / target adjustment review, NOT pause.
- Core-term flag (`is_core_term = true`) surfaced in report — these keywords got ×1.5 patience before pause because they match the configured coreProductTokens.
- Total wasted spend (UNPROFITABLE + PAUSE_CANDIDATE only) in dollars and as % of account spend.
- Caveat if running in `targetFallbackMode = campaign_target_only` — note that true business profitability analysis is disabled.

**Routing:** KW-E01 (pause/remove) for UNPROFITABLE + PAUSE_CANDIDATE. KW-E02 (bid adjustment / target segmentation) for OVER_TARGET.

---

### KW-D08: Zombie and Low Performer Detection

**Points:** 8
**Data source:** `keyword-flags.csv` filtered to flag_types `ZOMBIE` and `LOW_PERFORMER`

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| 0 zombies/low performers | PASS | -- | 8/8 |
| 1-5 zombies/low performers, <5% of keyword count | WARN | Low | 4.8/8 |
| 6+ OR >5% of keyword count | FAIL | Medium | 0/8 |

**Details to include:**
- Zombie keywords: keyword, campaign, last impression date, days dormant
- Low performers: keyword, campaign, clicks, conversions, quality score
- Count as % of total keywords in account

**Routing:** KW-E07 (cleanup/removal), KW-E02 (bid adjustment)

---

### KW-D09: Tier Shift Detection

**Points:** 7
**Data source:** `keyword-flags.csv` filtered to flag_type `TIER_DEGRADED`

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| No tier degradation detected | PASS | -- | 7/7 |
| 1-3 degraded keywords, none from HERO tier | WARN | Medium | 4.2/7 |
| 4+ degraded OR any HERO degraded to UNPROFITABLE/PAUSE_CANDIDATE/ZOMBIE | FAIL | High | 0/7 |

**Details to include:**
- Degraded keywords: keyword, campaign, previous tier, current tier
- Direction and magnitude of shift (e.g., ACTIVE to UNPROFITABLE = 4-tier drop per rank table)
- Timeframe of degradation
- Flag HERO degradations prominently

**Routing:** Investigate root cause. May route to KW-E02 (bid adjustment) or flag for campaign-level review.

---

## Module 3: Cannibalization & Duplicates (25 points)

### KW-D10: Duplicate Keyword Detection

**Points:** 7
**Data source:** `keyword-overlaps.csv` filtered to `flag_type = DUPLICATE_KEYWORD`

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| 0 duplicate groups | PASS | -- | 7/7 |
| 1-3 duplicate groups | WARN | Medium | 4.2/7 |
| 4+ duplicate groups | FAIL | High | 0/7 |

**Details to include:**
- Duplicate groups: keyword text, match type, campaigns/ad groups where it appears
- Performance delta between duplicates (which one wins auctions)
- Recommended keeper per group (highest QS, best performance)

**Routing:** KW-E04 (dedup/consolidate)

---

### KW-D11: Keyword Cannibalization

**Points:** 10
**Data source:** `keyword-tiers.csv` — Claude reasoning to identify semantic overlap between ad groups that causes auction competition

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| No meaningful semantic overlap between ad groups | PASS | -- | 10/10 |
| Low-impact overlap (ad groups with distinct performance profiles) | WARN | Medium | 6/10 |
| Measurable cannibalization (overlapping keywords splitting impressions/conversions) | FAIL | High | 0/10 |

**Details to include:**
- Overlapping keyword clusters identified
- Ad groups involved and their themes
- Evidence of auction splitting (impression share loss, fragmented conversions)
- Structural recommendation (merge, redefine boundaries, add negatives)

**Routing:** KW-E05 (cannibalization resolution). Flag for keyword-restructurer if structural changes needed.

---

### KW-D12: Search vs PMax Overlap

**Points:** 5
**Data source:** `keyword-overlaps.csv` filtered to `flag_type = PMAX_OVERLAP`

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| No overlap OR intentional exact match priority | PASS | -- | 5/5 |
| Overlap detected but Search still winning auctions | WARN | Medium | 3/5 |
| Significant overlap with PMax outspending Search on those terms | FAIL | High | 0/5 |
| No PMax campaigns in account | SKIP | -- | --/-- |

**Details to include:**
- Overlapping search terms between Search and PMax
- Spend share: Search vs PMax for overlapping terms
- Whether exact match priority is properly leveraged
- Search campaign impression share for overlapping terms

**Routing:** Recommend exact match in Search for high-value terms; adjust PMax asset groups if needed.

---

### KW-D13: Similar Broad Match in Same Ad Group

**Points:** 3
**Data source:** `keyword-tiers.csv` or `keywords.csv` — Claude reasoning on broad match keywords within the same ad group to identify semantic variants

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| No redundant semantic variants in broad match within any AG | PASS | -- | 3/3 |
| Redundant broad match variants found (e.g., "plumber" and "plumbing" in same AG) | WARN | Low | 1.8/3 |

**Details to include:**
- Redundant variant groups: keywords, ad group
- Explanation of why they are semantically equivalent in broad match
- Recommended keyword to keep per group

**Routing:** KW-E04 (dedup/consolidate)

---

## Module 4: Keyword Hygiene (10 points)

### KW-D14: Below First Page Bid

**Points:** 5
**Data source:** `keyword-flags.csv` filtered to flag_type `BELOW_FIRST_PAGE_BID`. Only applicable to Manual CPC campaigns.

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| 0 below-first-page keywords OR no Manual CPC campaigns | PASS | -- | 5/5 |
| Any keywords below first page bid on Manual CPC | WARN | Low | 3/5 |
| No Manual CPC campaigns in account | SKIP | -- | --/-- |

**Details to include:**
- List of keywords below first page bid: keyword, campaign, current bid, estimated first page bid
- Gap between current bid and first page bid

**Routing:** KW-E02 (bid adjustment)

---

### KW-D15: Low Volume Keywords

**Points:** 5
**Data source:** `keywords-structural.csv` filtered to system_serving_status `LOW_SEARCH_VOLUME`

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| 0 low-volume keywords | PASS | -- | 5/5 |
| Low-volume keywords present for >30 days | WARN | Low | 3/5 |

**Details to include:**
- List of low-volume keywords: keyword, campaign, ad group, match type
- Days since keyword was added (if available)
- Recommendation: broaden match type, rephrase, or remove

**Routing:** KW-E07 (cleanup/removal)

---

## Module 5: Intent Alignment (15 points)

### KW-D17: Informational Keywords in Commercial Campaigns

**Points:** 8
**Data source:** Keywords data + Claude reasoning. Claude reads each keyword and flags informational/research intent (e.g. "how to X", "what is X", "X guide", "X tutorial", "X vs Y") semantically — language-agnostic, no pattern list.

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| No informational keywords in commercial campaigns | PASS | -- | 8/8 |
| 1-3 informational keywords with low spend (<5% of campaign) | WARN | Medium | 4.8/8 |
| Informational keywords consuming >5% of campaign spend | FAIL | High | 0/8 |

**Details to include:**
- Informational keywords found: keyword, campaign, spend, conversions
- Reason flagged (e.g., research intent, comparison query)
- Spend as % of campaign total
- Whether any informational keywords are converting (may be intentional)

**Routing:** KW-E01 (pause/remove) or add as negatives

---

### KW-D18: Brand Terms in Non-Brand Campaigns

**Points:** 7
**Data source:** Hybrid approach. Script pre-flags exact brand matches in `keyword-flags.csv` (flag_type `BRAND_IN_NON_BRAND`) using brand terms from context and campaign classification from config. Claude catches variants, misspellings, and partial brand matches. Uses `business.md` / `brand.md` brand name + config `brandedCampaigns` list.

**Logic:**

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| No brand terms in non-brand campaigns | PASS | -- | 7/7 |
| Brand terms found but low spend impact | WARN | Medium | 4.2/7 |
| Brand terms consuming >5% of non-brand campaign spend | FAIL | High | 0/7 |

**Details to include:**
- Brand keywords found: keyword, campaign, match type, spend
- Script-flagged vs Claude-identified (note detection method)
- Spend on brand terms as % of non-brand campaign total
- Whether dedicated brand campaign exists (if not, flag separately)

**Routing:** KW-E01 (pause/remove from non-brand) or add brand negatives to non-brand campaigns
