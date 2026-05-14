# Account Auditor — Settings Diagnostics (AUD-D11–D19)

**Data source:** `campaigns-settings.csv` (pulled fresh by this skill using `campaigns-settings-audit.gaql`)

All settings checks filter to `campaign.status != REMOVED`. Type-specific checks note which `advertising_channel_type` they apply to.

---

## AUD-D11: Display Network Opt-In (Search)
**Severity:** High (10 pts) | **Applies to:** SEARCH campaigns only

**Rule:** All Search campaigns must have Display Network OFF. Enabling it creates a hidden Display campaign sharing the Search budget.

**How to check:**
1. Filter to `campaign.advertising_channel_type = SEARCH` AND `campaign.status = ENABLED`
2. Check `campaign.network_settings.target_content_network`
3. FAIL if `true` on ANY Search campaign

**Pass/Fail:**
- PASS: All Search campaigns have `target_content_network = false`
- FAIL: Any Search campaign has `target_content_network = true`

**Why this is critical (from Search Campaign Settings Guidelines):** Google enables Display Network by default on new Search campaigns. This silently diverts Search budget to Display placements with fundamentally different intent signals. The #1 budget-wasting misconfiguration.

**Routing on FAIL:** Fix directly in campaign settings (Settings > Networks > Display Network OFF)

---

## AUD-D12: Search Partners Review
**Severity:** Medium (5 pts) | **Applies to:** SEARCH, SHOPPING campaigns

**Rule:** If Search Partners is enabled, it should have been evaluated for performance. This is a "has it been reviewed?" check, not an automatic fail.

**How to check:**
1. Filter to `campaign.advertising_channel_type IN (SEARCH, SHOPPING)` AND `campaign.status = ENABLED`
2. Check `campaign.network_settings.target_search_network`
3. If enabled: flag as WARN with recommendation to segment and evaluate performance
4. If disabled: PASS

**Pass/Fail:**
- PASS: Search Partners disabled, OR enabled with documented justification
- WARN: Search Partners enabled — recommend reviewing network-segmented performance

**Note:** Search Partners is a "Test" recommendation per the guidelines. It works well for ~50% of accounts. The account-auditor flags it for review, not as automatically wrong.

---

## AUD-D13: Location Targeting Method
**Severity:** High (10 pts) | **Applies to:** ALL campaign types

**Rule:** Location targeting method should be set intentionally. "Presence or interest" is the default and acceptable. "Presence only" is preferred for local/service-area businesses. Flag deprecated or unsafe values.

**How to check:**
1. Check `campaign.geo_target_type_setting.positive_geo_target_type` for all enabled campaigns
2. Expected values: `PRESENCE_OR_INTEREST` (default, acceptable) or `PRESENCE` (restricted, often preferred)
3. FAIL if value is `AREA_OF_INTEREST` (deprecated, shows ads to anyone interested but not present)

**Pass/Fail:**
- PASS: All campaigns use `PRESENCE_OR_INTEREST` or `PRESENCE` consistently
- WARN: Mix of methods across campaigns without clear reason
- FAIL: Any campaign uses `AREA_OF_INTEREST` (deprecated)

---

## AUD-D14: Location Exclusion Method
**Severity:** High (10 pts) | **Applies to:** ALL campaign types

**Rule:** Location exclusion method must be "Presence only" to actually block users physically in excluded areas.

**How to check:**
1. Check `campaign.geo_target_type_setting.negative_geo_target_type` for all enabled campaigns
2. FAIL if NOT `PRESENCE` (i.e., if set to `PRESENCE_OR_INTEREST`)

**Pass/Fail:**
- PASS: All campaigns use `PRESENCE` for exclusions
- FAIL: Any campaign uses `PRESENCE_OR_INTEREST` for exclusions (users in excluded areas can still see ads if they "show interest")

**Why this matters:** If location exclusion is set to "Presence or interest", excluded locations don't actually block users physically there — they only block users who show interest. This defeats the purpose of exclusions.

---

## AUD-D15: Language Targeting Consistency
**Severity:** Medium (5 pts) | **Applies to:** ALL campaign types

**Rule:** Language settings should match ad language and target audience. Multi-language markets need separate campaigns per language.

**How to check:**
1. This check is heuristic — language targeting data is not in the settings GAQL query
2. Check campaign names for language indicators (e.g., `NL_NL_`, `BE_FR_`)
3. Flag campaigns targeting multi-language markets without language separation in naming
4. Cross-reference with `business.md` target market

**Pass/Fail:**
- PASS: Campaign names indicate consistent language targeting per market
- WARN: Campaigns in multi-language markets without clear language separation
- SKIP: Insufficient data to determine (no language indicators in names or business.md)

---

## AUD-D16: Ad Rotation Setting
**Severity:** Low (3 pts) | **Applies to:** SEARCH campaigns primarily

**Rule:** Ad rotation should be "Optimize" for all campaigns except those actively running A/B experiments.

**How to check:**
1. Check `campaign.ad_serving_optimization_status` for all enabled campaigns
2. Expected: `OPTIMIZE` (Google's default and recommendation)
3. `ROTATE_INDEFINITELY` is acceptable only during active testing

**Pass/Fail:**
- PASS: All campaigns set to `OPTIMIZE`
- WARN: 1-2 campaigns set to `ROTATE_INDEFINITELY` (may be testing — flag for review)
- FAIL: Multiple campaigns on `ROTATE_INDEFINITELY` without testing justification

**Note:** Smart Bidding overrides "Do not optimize" anyway (per Search Campaign Settings Guidelines). This setting only truly applies under Manual CPC.

---

## AUD-D17: Ad Schedule Appropriateness
**Severity:** Medium (5 pts) | **Applies to:** ALL campaign types

**Rule:** Campaigns should run all hours/days unless there's documented justification for restrictions (phone-based lead gen during business hours only).

**How to check:**
1. Ad schedule data is not available in the campaign settings GAQL query
2. SKIP this check with note: "Ad schedule validation requires manual review or additional API query"
3. If ad schedule data becomes available, check for:
   - Restricted hours on Smart Bidding campaigns (unnecessary — algorithm handles time optimization)
   - All-day/all-week for most campaign types

**Pass/Fail:**
- SKIP: Ad schedule data not available via current GAQL query. Manual review recommended.

**Exception conditions (acceptable restrictions):**
- Phone-based lead gen: business hours only
- B2B: weekdays/business hours
- Seasonal promotions: custom schedule matching promotion window

---

## AUD-D18: Tracking Template Consistency
**Severity:** Medium (5 pts) | **Applies to:** ALL campaign types

**Rule:** UTM tracking templates should be set consistently at campaign level across all campaigns.

**How to check:**
1. Check `campaign.tracking_url_template` for all enabled campaigns
2. Compare templates across campaigns for consistency
3. Flag campaigns with missing templates (empty/null)
4. Flag campaigns with inconsistent template formats

**Pass/Fail:**
- PASS: All campaigns have consistent tracking templates set
- WARN: >80% have templates but some are missing or inconsistent
- FAIL: <80% have tracking templates, OR wildly inconsistent formats across campaigns

**Note:** Setting tracking at account level is acceptable (in which case campaign-level may be empty). If ALL campaigns show empty templates, check if an account-level template exists before flagging.

---

## AUD-D19: URL Expansion Audit
**Severity:** Medium (5 pts) | **Applies to:** SEARCH, PERFORMANCE_MAX campaigns

**Rule:** Final URL expansion status should be intentionally configured. URL expansion can send traffic to unintended pages if enabled without review.

**How to check:**
1. Filter to `campaign.advertising_channel_type IN (SEARCH, PERFORMANCE_MAX)` AND `campaign.status = ENABLED`
2. Check `campaign.asset_automation_settings` for entries containing `FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION`
3. The field returns a JSON array of `{asset_automation_type, asset_automation_status}` objects. Look for:
   - `asset_automation_type = FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION` with `asset_automation_status = OPTED_IN` → URL expansion ON
   - `asset_automation_type = FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION` with `asset_automation_status = OPTED_OUT` → URL expansion OFF
   - Field empty/missing → default behavior (usually ON for PMax, varies for Search)

**Pass/Fail:**
- PASS: URL expansion status is intentionally configured (OPTED_OUT for strict LP control, or OPTED_IN with documented intent)
- WARN: URL expansion is ON (OPTED_IN or default) on Search/PMax campaigns — flag for review
- SKIP: If `asset_automation_settings` is empty for all campaigns (field not populated)

**Context from PMax Configuration Guidelines:** PMax with URL expansion ON can send traffic to any page on the site. Recommended OFF unless the advertiser intentionally wants broad page coverage.
