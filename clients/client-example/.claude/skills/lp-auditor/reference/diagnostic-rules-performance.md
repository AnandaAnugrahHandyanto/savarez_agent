# LP Auditor — Performance Diagnostics (LP-D25–D31)

Data source: Google Ads data (ads.csv, campaigns.csv, device-performance.csv) + GAQL queries

Reference: `sops/SOP – Monitor Landing Page Performance.md`

**Note:** D26-D28 require GA4 data which is not available via Google Ads API. These are permanently SKIP with notes directing users to GA4.

---

## LP-D25: CVR vs Benchmark
**Severity:** High (10 pts) | **Data:** ads.csv (final URLs, conversions, clicks)

**Rule:** Each LP's conversion rate should be compared against (a) the account average CVR and (b) industry reference ranges. Flag LPs significantly below average.

**How to check:**
1. From ads.csv: group by final URL, calculate CVR per URL (`sum(conversions) / sum(clicks)`)
2. Calculate account-wide average CVR
3. Compare each LP's CVR to account average
4. Cross-reference with industry ranges from `reference/benchmarks.md`
5. Flag LPs with CVR significantly below average (>50% below account avg)

**Pass/Fail:**
- PASS: LP CVR ≥ account average, or within industry normal range
- WARN: LP CVR is 50-75% of account average
- FAIL: LP CVR <50% of account average, or significantly below industry range
- SKIP: Insufficient data (<50 clicks on the LP)

**Context notes:**
- Different campaign types have different expected CVR ranges (brand > non-brand, search > display)
- Compare like-for-like: brand LP vs brand campaign avg, non-brand LP vs non-brand avg
- New LPs with <50 clicks should be SKIP

**Routing on FAIL:** `/lp-optimizer audit`

---

## LP-D26: Bounce Rate
**Severity:** Medium (5 pts) | **Data:** N/A — requires GA4

**Rule:** Bounce rate >60% on paid traffic LPs signals a hero section or message match problem.

**How to check:**
- SKIP — bounce rate is not available via Google Ads API
- Note: "Check Google Analytics > Landing Pages for bounce rate data. Flag LPs with >60% bounce rate on paid traffic."

**Pass/Fail:**
- SKIP: Always. Data not available via Google Ads API.

---

## LP-D27: Scroll Depth
**Severity:** Medium (5 pts) | **Data:** N/A — requires GA4 scroll tracking

**Rule:** If <30% of visitors reach mid-page, the benefits section isn't hooking them.

**How to check:**
- SKIP — scroll depth requires GA4 scroll tracking events
- Note: "Set up GA4 scroll depth events (25%, 50%, 75%, 100%) for this metric. Flag LPs where <30% reach 50% depth."

**Pass/Fail:**
- SKIP: Always. Data not available via Google Ads API.

---

## LP-D28: Time on Page
**Severity:** Low (3 pts) | **Data:** N/A — requires GA4

**Rule:** Unusually short or long time on page can indicate problems (short = bounce, long = confusion).

**How to check:**
- SKIP — time on page requires GA4 engagement metrics
- Note: "Check GA4 avg session duration per LP. Flag unusually short (<15s) or long (>5min) sessions."

**Pass/Fail:**
- SKIP: Always. Data not available via Google Ads API.

---

## LP-D29: Per-LP CPA Comparison
**Severity:** High (10 pts) | **Data:** ads.csv (final URLs, cost, conversions)

**Rule:** Compare CPA across landing pages. Flag any LP with CPA significantly above the account average.

**How to check:**
1. From ads.csv: group by final URL, calculate CPA per URL (`sum(cost) / sum(conversions)`)
2. Calculate account-wide average CPA (across all URLs with conversions)
3. Rank LPs by CPA
4. Flag outliers: LPs with CPA >150% of account average

**Pass/Fail:**
- PASS: LP CPA ≤ account average CPA
- WARN: LP CPA is 100-150% of account average
- FAIL: LP CPA >150% of account average
- SKIP: LP has zero conversions (flagged separately) or <10 clicks

**Context notes:**
- High CPA may be caused by poor LP quality OR by targeting issues (wrong traffic to right page)
- Cross-reference with D31 (traffic source match) to distinguish LP problems from targeting problems

**Routing on FAIL:** `/lp-optimizer audit`

---

## LP-D30: Device-Specific Performance
**Severity:** Medium (5 pts) | **Data:** device-performance.csv

**Rule:** Compare CVR and CPA per device per LP. Flag LPs where mobile CPA is dramatically worse than desktop.

**How to check:**
1. Read `context/google-ads/data/device-performance.csv`
2. For campaigns driving traffic to audited LP(s): compare metrics by device
3. Calculate per-device CVR and CPA
4. Flag: mobile CPA >200% of desktop CPA, or mobile CVR <40% of desktop

**Pass/Fail:**
- PASS: Mobile/desktop performance within normal variance (mobile CPA <150% of desktop)
- WARN: Mobile CPA 150-200% of desktop CPA
- FAIL: Mobile CPA >200% of desktop CPA
- SKIP: Insufficient data (<50 clicks per device)

**Routing on FAIL:** `/lp-optimizer mobile`

---

## LP-D31: Traffic Source Match
**Severity:** Medium (5 pts) | **Data:** ads.csv (campaign names, final URLs)

**Rule:** Verify campaigns send traffic to appropriate LPs. Flag mismatches like brand campaigns going to generic pages or high-intent search going to awareness content.

**How to check:**
1. From ads.csv: map campaigns → final URLs
2. Check for mismatches:
   - Brand campaign → should go to brand-specific LP (not generic homepage)
   - Non-brand high-intent search → should go to conversion-focused LP (not blog/awareness)
   - Display/Video campaigns → should go to awareness/education LP (not hard-sell)
   - Shopping → should go to product pages (not category or generic LP)
3. Flag any URL that seems mismatched to its campaign intent

**Pass/Fail:**
- PASS: All campaigns send traffic to intent-appropriate LPs
- WARN: 1 campaign has a questionable LP match
- FAIL: Multiple campaigns clearly sending traffic to wrong LP types
- SKIP: Cannot determine campaign intent from names

**Routing on FAIL:** `/lp-optimizer audit`
