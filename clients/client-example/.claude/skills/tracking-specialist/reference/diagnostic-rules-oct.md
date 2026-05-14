# Diagnostic Rules — Offline Conversion Tracking (D36-D41)

Read during Phase 1 when running `/tracking-specialist oct` or `/tracking-specialist` (default).
Also read `diagnostic-rules-shared.md` first.

## Module Scoring

| ID | Diagnostic | Severity | Pts |
|----|-----------|----------|-----|
| D36 | OCT Status | High | 10 |
| D37 | Upload Freshness | High | 10 |
| D38 | Error Rate | Medium | 5 |
| D39 | GCLID Capture | Medium | 5 |
| D40 | CRM Pipeline Mapping | Medium | 5 |
| D41 | OCT Value Accuracy | Medium | 5 |
| **Total** | | | **40** |

---

## D36: OCT Status
**Severity:** High (10 pts)
**Data:** conversions-audit.csv + business.md

**Prerequisite check:** Determine if the account should be using OCT. Check business.md for the vertical:

| Vertical | OCT expected? |
|----------|--------------|
| Lead Gen | Yes — OCT is required for importing qualified leads, closed deals |
| SaaS | Yes — OCT is required for importing trial-to-paid, subscription data |
| Ecommerce | No — ecommerce tracks onsite purchases via GACT (OCT only relevant for in-store conversions) |

**If ecommerce:** SKIP D36-D41 entirely. Report as INFO: "Ecommerce account — OCT not applicable (onsite purchases tracked via GACT)."

**Check:** Look for UPLOAD_CLICKS type actions in conversions-audit.csv. Filter for `conversion_action.type = UPLOAD_CLICKS` with `conversion_action.status = ENABLED`.

**PASS:** At least one UPLOAD_CLICKS action exists, is ENABLED, and has `metrics.all_conversions > 0`. The import pipeline is configured and active.
**WARN:** UPLOAD_CLICKS actions exist but have `metrics.all_conversions = 0` (created but never received data — pipeline configured but not yet active or broken before first upload).
**FAIL:** No UPLOAD_CLICKS actions exist for a Lead Gen or SaaS account. Smart Bidding is optimizing on form submissions or signups only, without downstream business outcome data.

**If FAIL (no OCT configured):** Report as INFO: "No OCT configured — this is a Lead Gen/SaaS account that would benefit from offline conversion imports. SKIP D37-D41." Then SKIP D37-D41 as there is nothing further to check.

**Impact:** Without OCT, Smart Bidding optimizes for volume (form fills) instead of quality (qualified leads, closed deals). This is the single biggest measurement gap for Lead Gen and SaaS accounts.

---

## D37: Upload Freshness
**Severity:** High (10 pts)
**Data:** conversions-daily.csv (filtered to UPLOAD_CLICKS actions)

**Prerequisite:** D36 must PASS or WARN. If D36 FAIL or SKIP, SKIP D37.

**Check:** Evaluate whether UPLOAD_CLICKS actions have recent conversions, indicating the import pipeline is actively running.

Filter conversions-daily.csv for rows matching UPLOAD_CLICKS actions identified in D36. Check the most recent date with conversions > 0.

| Freshness | Assessment |
|-----------|-----------|
| Last upload within 7 days | Pipeline active and current |
| Last upload 8-14 days ago | Pipeline may be stalled — could be a cadence issue or early warning of a break |
| Last upload 15-30 days ago | Pipeline likely broken — stale data feeding Smart Bidding |
| Last upload 30+ days ago or no daily data | Pipeline is dead — OCT exists in name only |

**PASS:** UPLOAD_CLICKS actions show conversions within the last 7 days. Upload pipeline is active and feeding Smart Bidding fresh data.
**WARN:** Last upload was 8-14 days ago. May be acceptable for accounts with long sales cycles and infrequent CRM stage changes, but worth confirming with the user.
**FAIL:** Last upload was 15+ days ago, or no conversion data exists in the daily time series. Smart Bidding is working with stale or no offline data.

**Impact:** Stale uploads mean Smart Bidding is optimizing on outdated signals. For lead gen accounts, this can mean the algorithm is still chasing lead quality patterns from weeks ago while the market has shifted.

**Cross-reference:** Check business.md for the expected sales cycle length. A 60-day sales cycle naturally has less frequent stage transitions than a 7-day cycle — adjust freshness expectations accordingly.

---

## D38: Error Rate
**Severity:** Medium (5 pts)
**Data:** `offline_conversion_upload_client_summary` resource (GAQL) — **may require a new data pull**

**Note:** This diagnostic requires upload error data from the `offline_conversion_upload_client_summary` GAQL resource, which provides metrics on successful vs. failed upload rows. If this data is not available in the current audit CSV files, this diagnostic cannot be run automatically.

**Prerequisite:** D36 must PASS or WARN. If D36 FAIL or SKIP, SKIP D38.

**If data is available:** Check the ratio of failed upload rows to total upload rows over the last 30 days.

| Error rate | Assessment |
|-----------|-----------|
| < 2% | Healthy — minimal upload issues |
| 2-5% | Acceptable — some unmatched GCLIDs or format issues are normal |
| 5-10% | Concerning — investigate common error types |
| > 10% | Critical — significant data loss in the import pipeline |

Common error types to look for:
1. **GCLID not found:** Click ID does not match any Google Ads click (expired GCLID, wrong account, bot traffic)
2. **Conversion name mismatch:** Upload template name does not match Google Ads action name exactly
3. **Date format errors:** Timestamp format does not match expected format (YYYY-MM-DD HH:MM:SS)
4. **Outside attribution window:** Conversion happened more than 90 days after the click
5. **Duplicate uploads:** Same conversion uploaded multiple times without a unique order ID

**PASS:** Error rate is below 5% over the last 30 days. Upload pipeline is healthy.
**WARN:** Error rate is 5-10%. Some data is being lost — investigate the most common error type and address it.
**FAIL:** Error rate exceeds 10%. Significant conversion data is not reaching Google Ads, degrading Smart Bidding signal quality.

**If data is unavailable:** SKIP this diagnostic. Report as INFO: "Upload error data not available in current audit files. Manual check required: navigate to Goals > Conversions > Uploads in Google Ads and review recent upload status for error rates. Flag if error rate exceeds 5%."

---

## D39: GCLID Capture
**Severity:** Medium (5 pts)
**Data:** Interactive — ask user

**Prerequisite:** D36 must PASS or WARN. If D36 FAIL or SKIP, SKIP D39.

**Check:** Verify that Google Click IDs (GCLID, GBRAID, WBRAID) are being captured and stored in the CRM for every lead originating from Google Ads.

**This diagnostic cannot be verified via the Google Ads API.** Ask the user the following questions:

1. **"Are hidden fields set up on all lead capture forms to capture GCLID, GBRAID, and WBRAID parameters?"**
   - If no: FAIL — click IDs are not being captured, OCT attribution will be incomplete
   - If yes: continue to next question

2. **"Are the captured click IDs stored as fields on the lead/contact record in your CRM?"**
   - If no: FAIL — click IDs captured on forms but lost before reaching CRM
   - If yes: continue to next question

3. **"Have you verified GCLID capture recently by clicking a Google Ads ad and checking the CRM record?"**
   - If no: WARN — capture is set up but not recently validated (website changes could have broken it)
   - If yes: PASS

**PASS:** Hidden fields capture GCLID/GBRAID/WBRAID on all forms, values are stored in CRM, and capture has been recently verified.
**WARN:** Capture is configured but has not been verified recently, or only covers some form/landing page variants.
**FAIL:** GCLID capture is not set up, or click IDs are not reaching the CRM.

**Impact:** Without GCLID capture, OCT relies entirely on Enhanced Conversions for Leads (EC4L) email matching, which has a lower match rate. GCLID provides direct, deterministic attribution.

---

## D40: CRM Pipeline Mapping
**Severity:** Medium (5 pts)
**Data:** Interactive — ask user + conversions-audit.csv

**Prerequisite:** D36 must PASS or WARN. If D36 FAIL or SKIP, SKIP D40.

**Check:** Verify that CRM pipeline stages are correctly mapped to Google Ads conversion actions, and that the mapping is still current.

**Partial API check:** From conversions-audit.csv, list all UPLOAD_CLICKS actions with their names and categories. Present these to the user and ask:

1. **"Here are the offline conversion actions in the account: [list names]. Do these still match your current CRM pipeline stages?"**
   - If stages have changed in the CRM but actions have not been updated: WARN
   - If mapping is current: continue

2. **"Is only one OCT stage set as primary for Smart Bidding? Which stage is the primary conversion action?"**
   - If multiple OCT stages are set as primary: FAIL (double-counting for Smart Bidding)
   - If the wrong stage is primary (e.g., MQL instead of closed deal when volume supports it): WARN
   - If one correct stage is primary: continue

3. **"Are there any CRM stages that should be tracked but are not yet mapped to a conversion action?"**
   - If yes: WARN — missing stages reduce reporting visibility
   - If no: PASS

**PASS:** CRM stages correctly map to conversion actions. One OCT stage is set as primary. No missing stages.
**WARN:** Mapping is mostly correct but has minor gaps — missing intermediate stages, or primary stage could be upgraded to a more downstream event.
**FAIL:** CRM pipeline has changed significantly and conversion actions are outdated, or multiple OCT stages are set as primary (double-counting).

**Cross-reference:** D02 (Primary/Secondary Classification) may also flag multiple primary OCT actions. D40 focuses specifically on whether the CRM-to-Google-Ads mapping is current and intentional.

---

## D41: OCT Value Accuracy
**Severity:** Medium (5 pts)
**Data:** Interactive — ask user + conversions-audit.csv

**Prerequisite:** D36 must PASS or WARN. If D36 FAIL or SKIP, SKIP D41.

**Check:** Verify that offline conversion values reflect actual deal/order values rather than stale estimates or static placeholders.

**Partial API check:** From conversions-audit.csv, check `conversion_action.value_settings.default_value` for UPLOAD_CLICKS actions:
- If `default_value > 0` and the action is set up for dynamic values: the default is a fallback only (acceptable)
- If `default_value > 0` and all conversions show the same value in conversions-daily.csv: values are likely static, not dynamic

Then ask the user:

1. **"Are the conversion values uploaded with each offline conversion reflecting actual deal values (or calculated proxy values based on stage conversion rates)?"**
   - If values are actual deal amounts: ideal setup
   - If values are calculated proxies (e.g., avg deal value x stage-to-close rate): acceptable
   - If values are static placeholders that have not been updated: WARN

2. **"When was the last time you reviewed or updated the conversion values used in OCT uploads?"**
   - If within the last 90 days: current
   - If 90+ days ago: WARN — values may be stale if deal sizes or conversion rates have changed
   - If never updated since initial setup: FAIL

**PASS:** Values are dynamic (actual deal values) or calculated proxies that have been reviewed within the last 90 days.
**WARN:** Values are proxy-based but have not been reviewed in 90+ days, or some uploads use static placeholder values.
**FAIL:** All uploads use a static placeholder value that has never been updated, or values bear no relationship to actual deal sizes.

**Impact:** Inaccurate values corrupt value-based bidding (tROAS, Maximize Conversion Value). Smart Bidding allocates budget based on predicted value — if the values are wrong, budget allocation is wrong.
