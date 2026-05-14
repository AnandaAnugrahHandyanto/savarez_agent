# Geo-Schedule Auditor — Geographic Diagnostics (GS-D01–D05)

**Threshold source:** Diagnostic Thresholds Reference (REF_69), Geographic section

---

## GS-D01: Location Targeting Method
**Severity:** Medium (5 pts) | **Data:** `campaigns-settings.csv`

**Rule:** Location targeting should be set intentionally. "Presence or interest" is the Google default and expands reach to people who *show interest* in a location but aren't physically there. This is acceptable for tourism, travel, relocation, and e-commerce verticals but wasteful for local/service-area businesses.

**How to check:**
1. Read `campaigns-settings.csv` → filter to `campaign.status = ENABLED`
2. Check `campaign.geo_target_type_setting.positive_geo_target_type` for each campaign
3. Read `business.md` → check vertical/industry
4. If vertical is tourism, travel, relocation, or pure e-commerce → "Presence or interest" is acceptable
5. Otherwise, "Presence or interest" without documented justification → WARN

**Pass/Fail:**
- PASS: All campaigns use `PRESENCE`, OR `PRESENCE_OR_INTEREST` is justified by vertical
- WARN: Any campaign uses `PRESENCE_OR_INTEREST` without vertical justification — recommend review
- SKIP: Never (always runs)

**Routing on WARN:** `/geo-schedule-optimizer geo` to fix location targeting settings

---

## GS-D02: Geographic CPA/ROAS Variance
**Severity:** Medium (5 pts) WARN / High (10 pts) FAIL | **Data:** `geo-user-location.csv`

**Rule:** Locations with CPA significantly above or ROAS significantly below the account average are wasting budget. Tier the response based on severity.

**How to check:**
1. Read `geo-user-location.csv` → filter to locations with 50+ clicks
2. Calculate account-level average CPA (total cost / total conversions across all locations)
3. For each location, compute CPA deviation: `(location_CPA - avg_CPA) / avg_CPA * 100`
4. Tier the results:
   - **Tier 1 (WARN):** CPA 30-49% above average (or ROAS 30-49% below average)
   - **Tier 2 (FAIL):** CPA 50%+ above average (or ROAS 50%+ below average)

**Pass/Fail:**
- PASS: No locations exceed 30% CPA variance (with 50+ clicks)
- WARN: Locations with CPA 30-49% above avg — list top 5 by spend
- FAIL: Locations with CPA 50%+ above avg — list all, ranked by wasted spend
- SKIP: Fewer than 3 locations with 50+ clicks

**Scoring:**
- WARN: 5 pts severity → deduct 5 pts
- FAIL: 10 pts severity → deduct 10 pts
- If both WARN and FAIL locations exist, use the higher severity (FAIL, 10 pts)

**Details format:** "X locations with CPA 30-49% above avg (${wasted}), Y locations with CPA 50%+ above avg (${wasted})"

**Routing on WARN/FAIL:** `/geo-schedule-optimizer geo` to apply location bid modifiers

---

## GS-D03: Zero-Conversion Locations
**Severity:** High (10 pts) | **Data:** `geo-user-location.csv`

**Rule:** Locations with zero conversions but significant spend are pure waste. Flag locations that have spent more than 2x the target CPA with 50+ clicks and zero conversions.

**How to check:**
1. Read `geo-user-location.csv` → filter to locations with 50+ clicks AND 0 conversions
2. Read `business.md` → get target CPA (or derive from account average)
3. Calculate waste threshold: 2x target CPA
4. Flag all locations where cost > waste threshold AND conversions = 0 AND clicks >= 50

**Pass/Fail:**
- PASS: No zero-conversion locations exceed the waste threshold
- FAIL: Locations with 0 conversions + spend >2x target CPA + 50+ clicks — list all with spend amounts
- SKIP: Target CPA unknown (not in `business.md` and no strategy-specialist audit) → "Need target CPA from business.md or strategy-specialist"

**Details format:** "X locations with zero conversions, total waste: ${amount}. Top offenders: [location1 ($X), location2 ($X)]"

**Routing on FAIL:** `/geo-schedule-optimizer geo` to exclude zero-conversion locations

---

## GS-D04: High-Performing Location Opportunity
**Severity:** Medium (5 pts) | **Data:** `geo-user-location.csv` + `campaigns.csv`

**Rule:** Locations performing well (CPA 20%+ below average) that are also losing impression share to budget represent untapped opportunity. These could benefit from dedicated campaigns or budget increases.

**How to check:**
1. Read `geo-user-location.csv` → filter to locations with 50+ clicks AND conversions > 0
2. Calculate account-level average CPA
3. Identify locations where CPA is 20%+ below average
4. **IS check:** The Google Ads API does NOT support `search_impression_share` on `geographic_view` or `location_view`. Use campaign-level IS from `campaigns.csv` as a proxy — if the campaign serving this location has IS lost to budget >10%, flag it.
5. Flag high-performing locations in IS-limited campaigns

**Pass/Fail:**
- PASS: No high-performing locations are in IS-limited campaigns
- WARN: High-performing locations (CPA 20%+ below avg) in campaigns with IS lost to budget >10% — opportunity to scale
- SKIP: No campaign-level IS data available → "IS data not available"

**Details format:** "X high-performing locations with IS lost to budget >10%. Top: [location1 (CPA $X, IS lost XX%)]"

**Routing on WARN:** `/geo-schedule-optimizer geo` to boost high-performing locations — or consider dedicated campaigns (advisory)

---

## GS-D05: Geographic Exclusion Coverage
**Severity:** Medium (5 pts) | **Data:** `campaign-criteria.csv` + `geo-user-location.csv`

**Rule:** If the account is serving ads in locations outside the intended target set, those locations should be excluded. Cross-reference with WD-D11 threshold: >3% of spend in non-target locations.

**How to check:**
1. Read `campaign-criteria.csv` → filter to `campaign_criterion.type = LOCATION` and `campaign_criterion.negative = false` to get target locations
2. Read `geo-user-location.csv` → identify locations receiving traffic
3. Cross-reference: find locations receiving impressions/spend that are NOT in the target set
4. Calculate non-target spend as a percentage of total spend
5. WARN if non-target spend >3% of total

**Pass/Fail:**
- PASS: Non-target location spend <3% of total, OR all serving locations are in the target set
- WARN: Non-target location spend >3% — list top locations by spend
- SKIP: Never (always runs with criteria data)

**Details format:** "Non-target location spend: ${amount} (X% of total). Top non-target: [location1 ($X), location2 ($X)]"

**Routing on WARN:** `/geo-schedule-optimizer geo` to add location exclusions
