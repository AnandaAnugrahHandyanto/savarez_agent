# Account Auditor — Structure Diagnostics (AUD-D01–D08)

## AUD-D01: Campaign Type Separation
**Severity:** High (10 pts) | **Data:** `campaigns.csv` → `campaign.advertising_channel_type`, `campaign.name`

**Rule:** Each campaign type (SEARCH, SHOPPING, PERFORMANCE_MAX, DISPLAY, VIDEO, DISCOVERY) should exist in its own campaigns. No campaign should mix traffic types.

**How to check:**
1. Group enabled campaigns by `campaign.advertising_channel_type`
2. For SEARCH campaigns: cross-check with D11 (Display Network opt-in). If `target_content_network = true`, this campaign is mixing Search + Display traffic.
3. Flag any campaign names suggesting mixed intent that doesn't match the channel type

**Pass/Fail:**
- PASS: All campaigns have clean type separation. No Search campaigns with Display Network enabled.
- WARN: 1 campaign has Display Network enabled (minor leak)
- FAIL: Multiple Search campaigns have Display Network enabled, or structural evidence of mixed campaign types

---

## AUD-D02: Brand/Non-Brand Separation
**Severity:** High (10 pts) | **Data:** `campaigns.csv`, `keywords-all.csv`, `business.md`

**Rule:** Brand traffic must be in dedicated brand campaigns. Brand keywords should NOT appear in non-brand campaigns.

**How to check:**
1. Extract brand name from `business.md` (brand name, common variations, misspellings)
2. Identify campaigns likely dedicated to brand (name contains "brand", "branded", or the brand name)
3. Scan `keywords-all.csv` for brand terms in non-brand campaigns
4. For Shopping/PMax: check campaign names for brand separation indicators

**Pass/Fail:**
- PASS: Brand terms exist only in dedicated brand campaigns. Non-brand campaigns have no brand keywords.
- WARN: Brand separation exists but incomplete (some brand terms leaking to non-brand)
- FAIL: No brand separation at all (brand and non-brand mixed in same campaigns), OR brand terms found in >1 non-brand campaign
- SKIP: Account has no brand recognition (brand-new, no brand search volume). Check `business.md`.

**Routing on FAIL:** campaign-builder (restructure), search-term-specialist (add brand negatives)

---

## AUD-D03: Campaign-to-Business Alignment
**Severity:** Medium (5 pts) | **Data:** `campaigns.csv`, `business.md`

**Rule:** Each enabled campaign should map to a clear business objective. Campaign structure should reflect the business model.

**How to check:**
1. Load business goals from `business.md`
2. For each enabled campaign, check if its type and name align with a documented business objective
3. Flag campaigns with no clear purpose (generic names, unclear targeting)
4. Check vertical alignment:
   - Ecommerce: expect Shopping/PMax campaigns
   - Lead Gen: expect Search-heavy structure
   - SaaS: expect Search + potentially PMax

**Pass/Fail:**
- PASS: All campaigns clearly map to business objectives
- WARN: 1-2 campaigns have unclear purpose
- FAIL: >2 campaigns with no clear business alignment
- SKIP: `business.md` missing or has no goals defined

---

## AUD-D04: Campaign Count Efficiency
**Severity:** Medium (5 pts) | **Data:** `campaigns.csv` → `metrics.conversions`, campaign count

**Rule:** Flag accounts with >15 enabled campaigns where any campaign has <30 conversions in the reporting period. More campaigns = more data fragmentation.

**How to check:**
1. Count enabled campaigns
2. If count > 15: check each campaign's `metrics.conversions`
3. Flag campaigns with < 30 conversions (insufficient data for Smart Bidding optimization)
4. Identify consolidation opportunities (campaigns with similar names/themes that could merge)

**Pass/Fail:**
- PASS: <=15 campaigns, OR >15 campaigns but all have 30+ conversions
- WARN: >15 campaigns with 1-3 having <30 conversions
- FAIL: >15 campaigns with 4+ having <30 conversions (significant fragmentation)

**Volume thresholds (from Account Structure Orchestration Mental Model):**
- tCPA campaigns: 30 conversions/month minimum, 50+ recommended
- tROAS campaigns: 50 conversions/month minimum
- Demand Gen: 50 conversions/ad group/month

---

## AUD-D05: Budget Fragmentation
**Severity:** Medium (5 pts) | **Data:** `campaigns.csv` → `campaign_budget.amount`, `campaign.name`, `metrics.conversions`

**Rule:** Flag >5 campaigns with similar intent that have individually insufficient budgets (daily budget < $10 OR <30 conversions/month).

**How to check:**
1. Group campaigns by apparent intent (using name similarity and campaign type)
2. Within each group, check if individual budgets are too small to generate meaningful data
3. Flag groups where consolidation would improve data density

**Pass/Fail:**
- PASS: No budget fragmentation detected. Each campaign has sufficient budget for its bid strategy.
- WARN: 1 group of campaigns could benefit from consolidation
- FAIL: Multiple groups of underfunded campaigns with overlapping intent

---

## AUD-D06: Redundant Targeting Overlap
**Severity:** High (10 pts) | **Data:** `keywords-all.csv` → cross-campaign keyword comparison

**Rule:** Flag campaigns competing against each other on the same keywords or products.

**How to check:**
1. Extract all keywords from `keywords-all.csv`, grouped by campaign
2. Compare keyword texts across campaigns (normalize: lowercase, strip match type)
3. Flag identical keywords appearing in multiple campaigns (excluding brand vs non-brand separation)
4. For Shopping/PMax: check for product overlap (same products in multiple campaigns without priority/exclusion logic)

**Pass/Fail:**
- PASS: No significant keyword overlap across campaigns
- WARN: <10% of keywords duplicated across campaigns
- FAIL: >10% of keywords duplicated, or entire campaigns with overlapping keyword sets

**Routing on FAIL:** keyword-specialist (resolve duplicates, add cross-negatives)

---

## AUD-D07: Zero-Conversion Campaigns
**Severity:** Critical (15 pts) | **Data:** `campaigns.csv` → `campaign.status`, `metrics.conversions`

**Rule:** Flag enabled campaigns with zero conversions in the reporting period (typically 30 days).

**How to check:**
1. Filter to `campaign.status = ENABLED`
2. Check `metrics.conversions = 0`
3. For each zero-conversion campaign, note its type, budget, and impressions for context

**Pass/Fail:**
- PASS: All enabled campaigns have at least 1 conversion
- WARN: 1 campaign with zero conversions but low spend (<$100)
- FAIL: Any enabled campaign with zero conversions and significant spend (>$100)

**Context notes:**
- New campaigns (<14 days old) should be flagged as INFO, not FAIL
- Awareness campaigns (Display/Video) may legitimately have zero direct conversions — flag as WARN with note
- Check if conversion tracking issues exist (cross-reference with tracking-specialist if available)

---

## AUD-D08: Zero-Impression Campaigns
**Severity:** Critical (15 pts) | **Data:** `campaigns.csv` → `campaign.status`, `metrics.impressions`

**Rule:** Flag enabled campaigns with zero impressions in the reporting period.

**How to check:**
1. Filter to `campaign.status = ENABLED`
2. Check `metrics.impressions = 0`
3. These are completely non-serving campaigns — something is structurally wrong

**Pass/Fail:**
- PASS: All enabled campaigns have impressions
- FAIL: Any enabled campaign with zero impressions (completely broken/blocked)

**Common causes:** All keywords paused, all ads disapproved, billing issue, budget exhausted, all products disapproved (Shopping), targeting too narrow

**Routing on FAIL:** compliance-guardian (if disapprovals), bidding-specialist (if bid-related), feed-specialist (if Shopping/PMax feed issue)
