# Diagnostic Rules — Attribution (D30-D35)

Read during Phase 1 when running `/tracking-specialist attribution` or `/tracking-specialist` (full).
Also read `diagnostic-rules-shared.md` first.

## Module Scoring

| ID | Diagnostic | Severity | Pts |
|----|-----------|----------|-----|
| D30 | Attribution Model | Medium | 5 |
| D31 | Click-Through Window | High | 10 |
| D32 | View-Through Window | Medium | 5 |
| D33 | Engaged-View Window | Low | 3 |
| D34 | Over-Attribution Ratio | High | 10 |
| D35 | Conversion Lag Awareness | Medium | 5 |
| **Total** | | | **38** |

---

## GAQL Field Requirements

D30-D33 require attribution fields that are **not** in the current `conversions-all.gaql`. The following fields must be added to a new or extended query:

| Field | Used by | Notes |
|-------|---------|-------|
| `conversion_action.attribution_model_settings.attribution_model` | D30 | Returns: DATA_DRIVEN, GOOGLE_ADS_LAST_CLICK, EXTERNAL, UNKNOWN |
| `conversion_action.click_through_lookback_window_days` | D31 | Returns: integer (1-90) |
| `conversion_action.view_through_lookback_window_days` | D32 | Returns: integer (1-30) |
| `conversion_action.include_in_conversions_metric` | D30-D33 | Useful cross-check for primary status |

**Engaged-view window** (`conversion_action.engaged_view_through_lookback_window_days`) — verify availability in the Google Ads API. If unavailable via GAQL, mark D33 as SKIP and note: "Engaged-view window not queryable via API. Check manually in Google Ads UI > Goals > Conversions > {action} > Settings."

**Recommended approach:** Create a new GAQL file `conversions-attribution.gaql` that extends `conversions-all.gaql` with these fields, or add the fields to the existing query.

---

## D30: Attribution Model
**Severity:** Medium (5 pts)
**Phase:** 1 (API)
**Data:** conversions-audit.csv (with attribution fields) + business.md

**Check:** Verify `conversion_action.attribution_model_settings.attribution_model` for all ENABLED actions.

**Expected:** Data-Driven Attribution (DDA) for all conversion actions. There are no valid exceptions — DDA is the recommended default for every account and vertical per the Configuration Guidelines.

**PASS:** All ENABLED conversion actions use `attribution_model = DATA_DRIVEN`.
**WARN:** One or more ENABLED actions use `GOOGLE_ADS_LAST_CLICK` but are secondary (reporting-only — lower impact since they do not feed Smart Bidding).
**FAIL:** Any primary conversion action uses `GOOGLE_ADS_LAST_CLICK`. This under-credits upper and mid-funnel interactions and degrades Smart Bidding signal quality.

**Additional flags:**
- If `attribution_model = EXTERNAL`: the action uses an externally managed model (e.g., GA4 import). Report as INFO — not a misconfiguration, but note that attribution is controlled outside Google Ads.
- If `attribution_model = UNKNOWN`: WARN — unexpected value, ask user to verify in Google Ads UI.

---

## D31: Click-Through Window
**Severity:** High (10 pts)
**Phase:** 1 (API)
**Data:** conversions-audit.csv (with attribution fields) + business.md (vertical, sales cycle length)

**Check:** Verify `conversion_action.click_through_lookback_window_days` matches the account's sales cycle.

**Lookup table (from business.md vertical and sales cycle):**

| Vertical | Typical Sales Cycle | Recommended Window | Acceptable Range |
|----------|--------------------|--------------------|------------------|
| Ecommerce (impulse) | Same day - 3 days | 7-14 days | 7-30 days |
| Ecommerce (considered) | 1-2 weeks | 14-30 days | 14-60 days |
| Lead Gen (B2C) | 1-2 weeks | 14-30 days | 14-60 days |
| Lead Gen (B2B services) | 2-4 weeks | 30-60 days | 30-90 days |
| Lead Gen (B2B enterprise) | 1-3 months | 60-90 days | 60-90 days |
| SaaS (self-serve trial) | 1-2 weeks | 30-60 days (match trial length) | 14-90 days |
| SaaS (enterprise) | 1-3 months | 60-90 days | 60-90 days |

**Calibration rule:** Window should be at least 2x the average conversion lag. If business.md contains a specific sales cycle length, use it. If not, use the vertical default from the table above.

**PASS:** Click-through window for all primary actions falls within the acceptable range for the vertical.
**WARN:** Window is at the default 30 days and business.md indicates a sales cycle that would benefit from a different setting (e.g., B2B enterprise still at 30 days, or impulse ecommerce at 30 days when 7-14 would reduce over-attribution). The default is functional but not optimized.
**FAIL:** Window is clearly too short for the sales cycle — Smart Bidding is missing late conversions. Specifically:
- B2B services/enterprise with window < 30 days
- SaaS with window shorter than the trial period
- Any vertical where window < 2x the known average conversion lag

**Impact:** A window that is too short causes Smart Bidding to optimize on incomplete data. It systematically under-counts conversions from longer consideration paths, biasing the algorithm toward quick converters only.

---

## D32: View-Through Window
**Severity:** Medium (5 pts)
**Phase:** 1 (API)
**Data:** conversions-audit.csv (with attribution fields) + business.md (campaign types)

**Check:** Verify `conversion_action.view_through_lookback_window_days` is set intentionally.

**Expected defaults:**

| Campaign type | Recommended VTC window |
|---------------|----------------------|
| Search only | 1 day (default) |
| Display / Demand Gen | 1 day (default) for primary actions. 3-7 days acceptable on a separate secondary action for assisted conversion measurement. |
| Video / YouTube | 1 day (default) for primary actions. Longer windows acceptable on secondary actions for upper-funnel measurement. |

**PASS:** View-through window is 1 day for all primary conversion actions. Or: window is intentionally longer on secondary actions used for upper-funnel reporting.
**WARN:** View-through window > 1 day on a primary action. This inflates conversion counts with passive attributions — users who saw an ad but may have converted through another channel. Flag the specific actions and their window length.
**FAIL:** View-through window > 7 days on a primary action. This significantly inflates conversion data and degrades Smart Bidding signal quality with noise from passive ad exposures.

**Note:** If the account runs only Search campaigns (no Display, Video, or Demand Gen), view-through conversions are minimal regardless of window length. Reduce severity to INFO in this case.

---

## D33: Engaged-View Window
**Severity:** Low (3 pts)
**Phase:** 1 (API) — if field available; otherwise SKIP
**Data:** conversions-audit.csv (with attribution fields) + campaign type data

**Check:** Verify engaged-view window is configured for accounts running Video campaigns.

**Context:** Engaged-view conversions credit a conversion when a user watches 10+ seconds of a skippable video ad (or the full ad if shorter) and then converts within the window. The default is 3 days.

**Relevance gate:** Check if the account runs Video or YouTube campaigns. If no Video campaigns exist, mark as SKIP with note: "No Video campaigns — engaged-view window not applicable."

**PASS:** Engaged-view window is set to 3 days (default) or has been intentionally adjusted. Account runs Video campaigns.
**WARN:** Engaged-view window > 10 days on a primary action for Video campaigns. Long windows inflate Video campaign conversion attribution with weak signals.
**FAIL:** N/A — engaged-view misconfiguration is unlikely to cause serious bidding harm. Use WARN as the maximum severity.

**If GAQL field unavailable:** Mark as SKIP. Note: "Engaged-view window cannot be verified via API. Check manually: Google Ads > Goals > Conversions > {action} > Settings > Engaged-view conversion window."

---

## D34: Over-Attribution Ratio
**Severity:** High (10 pts)
**Phase:** 1 (Interactive — ask user)

**Check:** Compare Google Ads reported conversions against actual backend data to identify over-attribution.

This diagnostic follows the same interactive pattern as D17 (Backend Data Cross-Check). If D17 was already run in the same audit session and data was provided, reuse that data here — do not ask the user twice.

**Step 1: Check if D17 data is available:**

If D17 was run and the user provided backend data:
- Reuse the same numbers. Skip to Step 3.
- Note in the output: "Using backend data from D17."

If D17 was skipped or not yet run, ask:

```
For D34 I need to compare Google Ads conversions against your backend to calculate the over-attribution ratio.

What can you provide?
1. CRM export (CSV/Excel) — last 30 days of conversions + revenue
2. Ecommerce platform numbers — total orders + revenue for last 30 days
3. Analytics data — GA4 or other analytics conversion counts
4. Just the numbers — tell me your backend conversion count + revenue for last 30 days
5. Skip this check — I'll flag it for later
```

**Step 2: Based on response:**
- If user provides a **file**: read it via the Read tool, extract total conversions and value for the period
- If user provides **numbers verbally**: use those directly
- If user **skips**: mark as SKIP, note "Over-attribution ratio unknown — backend comparison pending"

**Step 3: Calculate over-attribution ratio:**

```
Over-attribution ratio = Google Ads conversions / Backend conversions
```

| Ratio | Interpretation |
|-------|---------------|
| 0.90 - 1.10 | Normal range (within 10%) |
| 1.10 - 1.30 | Mild over-attribution (10-30%) |
| 1.30 - 1.50 | Moderate over-attribution (30-50%) |
| > 1.50 | Severe over-attribution (50%+) |

**PASS:** Ratio between 0.90 and 1.10 (Google Ads within 10% of backend).
**WARN:** Ratio between 1.10 and 1.30, OR ratio between 0.70 and 0.90 (under-attribution — possible consent blocking, broken tags, or window too short).
**FAIL:** Ratio > 1.30 (over-attribution) OR ratio < 0.70 (severe under-attribution).

**Step 4: Document and recommend:**
- Record the ratio in the report
- If over-attributing: recommend recalibrating efficiency targets using the formula:
  `Adjusted Target = (Google ROAS / Backend ROAS) x Desired ROAS`
  Or for CPA: `Adjusted CPA Target = (Backend CPA / Google CPA) x Desired CPA`
- Suggest documenting the ratio in business.md for ongoing calibration
- If under-attributing: investigate consent blocking (D12), attribution windows too short (D31), or broken tags (D09/D10)

**Cross-reference with D17:** If D17 also ran in this session, the findings should be consistent. If D17 showed volume within 10% but value diverges, the issue is likely value tracking (D15) rather than attribution.

---

## D35: Conversion Lag Awareness
**Severity:** Medium (5 pts)
**Phase:** 1 (business.md review)
**Data:** business.md + conversions-audit.csv (click-through window from D31)

**Check:** Verify whether the user accounts for conversion lag in their reporting and decision-making.

**Context:** Conversion lag is the delay between a click and the resulting conversion. Recent days in Google Ads reports always show incomplete data because conversions from recent clicks have not yet been attributed. Making optimization decisions on incomplete recent data leads to premature bid/budget changes.

**Step 1: Determine expected lag:**

Use business.md sales cycle length. If not specified, estimate from vertical:

| Vertical | Typical Conversion Lag |
|----------|----------------------|
| Ecommerce (impulse) | 0-3 days |
| Ecommerce (considered) | 3-7 days |
| Lead Gen (B2C) | 3-7 days |
| Lead Gen (B2B services) | 7-14 days |
| Lead Gen (B2B enterprise) | 14-30 days |
| SaaS (self-serve) | 3-14 days (trial length) |
| SaaS (enterprise) | 14-30 days |

**Step 2: Check business.md for lag awareness indicators:**

Look for any of the following in business.md:
- Explicit mention of conversion lag or attribution delay
- Reporting exclusion window (e.g., "exclude last 7 days from reporting")
- Reference to "incomplete data" or "allow X days for attribution"
- Sales cycle length documented (implies awareness of lag)

**Step 3: Cross-reference with D31 (click-through window):**

If D31 found that the click-through window matches the sales cycle, it implies the user understands the attribution timeline. If D31 found a mismatch, lag awareness is likely also missing.

**PASS:** business.md explicitly documents conversion lag or reporting exclusion window. Or: sales cycle length is documented AND click-through window (D31) is correctly calibrated — implies awareness.
**WARN:** business.md documents sales cycle length but makes no mention of conversion lag or reporting exclusion. The user may be making decisions on incomplete recent data.
**FAIL:** No sales cycle length, no conversion lag mention, and D31 shows a default 30-day window with no evidence of intentional calibration. High risk of premature optimization decisions based on incomplete data.

**Recommendation (if WARN or FAIL):**
- Add a conversion lag note to business.md: "Exclude the most recent {X} days from performance evaluation. Conversions are incomplete until the full attribution window has elapsed."
- Practical rule: exclude the last {conversion_lag} days from any reporting used for bid/budget decisions
- Reference Phase 4 of the bidding SOPs, which explicitly calls out excluding recent conversion-delay days from evaluation

---

## Execution Summary

### Phase 1 — API Diagnostics (require extended GAQL)
| ID | Name | Severity | Pts | Data Required |
|----|------|----------|-----|---------------|
| D30 | Attribution Model | Medium | 5 | conversions-audit.csv + `attribution_model_settings.attribution_model` field |
| D31 | Click-Through Window | High | 10 | conversions-audit.csv + `click_through_lookback_window_days` field + business.md |
| D32 | View-Through Window | Medium | 5 | conversions-audit.csv + `view_through_lookback_window_days` field |
| D33 | Engaged-View Window | Low | 3 | conversions-audit.csv + engaged-view field (if available) + campaign type data |

### Interactive (ask user for data)
| ID | Name | Method |
|----|------|--------|
| D34 | Over-Attribution Ratio | Reuse D17 backend data if available. Otherwise ask user for backend numbers. SKIP if user declines. |

### Business Context Review
| ID | Name | Method |
|----|------|--------|
| D35 | Conversion Lag Awareness | Review business.md for lag documentation. Cross-reference with D31 findings. No user interaction required. |

### Dependencies
- D31 findings feed into D35 (lag awareness cross-reference)
- D17 data (if available from Tag Health module) feeds into D34 (reuse, do not re-ask)
- D30-D33 require GAQL fields not in the current `conversions-all.gaql` — pull must include attribution fields or these diagnostics are SKIP
