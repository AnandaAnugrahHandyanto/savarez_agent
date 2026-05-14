# Diagnostic Rules — Data Hygiene (D42-D45)

Read during Phase 1 when running `/tracking-specialist hygiene` or `/tracking-specialist` (default).
Also read `diagnostic-rules-shared.md` first.

## Module Scoring

| ID | Diagnostic | Severity | Pts |
|----|-----------|----------|-----|
| D42 | Conversion Adjustments Cadence | Medium | 5 |
| D43 | Data Exclusions Coverage | High | 10 |
| D44 | Deprecated Actions | Medium | 5 |
| D45 | GA4 Import Duplication | Critical | 15 |
| **Total** | | | **35** |

---

## D42: Conversion Adjustments Cadence
**Severity:** Medium (5 pts)
**Data:** conversions-audit.csv

**Prerequisite check:** Determine if the account uses Conversion Adjustments. Look for UPLOAD_CLICKS type actions where the name or category suggests adjustment activity (e.g., RESTATE or RETRACT uploads), or check if any actions have `conversion_action.type = UPLOAD_CLICKS` with evidence of adjustment workflows. Also check business.md for mentions of return handling, lead value updates, or adjustment schedules.

**If the account does not use Conversion Adjustments:** SKIP this diagnostic. Report as INFO: "No Conversion Adjustments detected — not applicable for this account."

**Check:** If adjustments are in use, evaluate upload regularity against the expected cadence:

| Vertical | Expected cadence | Source |
|----------|-----------------|--------|
| Ecommerce | Daily or weekly (returns, partial refunds) | Configuration Guidelines |
| Lead Gen | Weekly or as CRM stages update (qualified, closed, lost) | Configuration Guidelines |
| SaaS | Weekly or as subscription events occur (upgrade, downgrade, churn) | Configuration Guidelines |

Look for gaps in adjustment uploads by checking conversions-daily.csv for UPLOAD_CLICKS actions — irregular patterns or long gaps (14+ days without activity) indicate a broken or neglected upload pipeline.

**PASS:** Adjustments are uploading at the expected cadence for the vertical. No gaps exceeding 14 days.
**WARN:** Adjustments exist but cadence is irregular — gaps of 14-30 days between uploads, suggesting a manual process that is not consistently maintained.
**FAIL:** Adjustments have not been uploaded for 30+ days despite being configured, or adjustment activity stopped abruptly (pipeline likely broken).

**Cross-reference:** Check business.md for return rates (ecommerce) or CRM pipeline stages (lead gen/SaaS) to assess how critical regular adjustments are for this account.

---

## D43: Data Exclusions Coverage
**Severity:** High (10 pts)
**Data:** conversions-audit.csv + conversions-daily.csv + Google Ads Data Exclusions (if accessible)

**Prerequisite check:** This diagnostic cross-references D10 (Volume Anomaly Detection) results. If D10 was not run or found no anomalies, SKIP this diagnostic. Report as INFO: "No volume anomalies detected in D10 — data exclusions check not applicable."

**Check:** If D10 identified volume anomalies (sudden drops to zero or near-zero conversions for 1+ days), verify that Data Exclusions exist for those periods.

Anomaly indicators from D10 that require exclusion coverage:
1. Conversion volume dropped to zero for a full day or more
2. Conversion volume dropped by more than 80% compared to the 7-day rolling average without a known cause (budget change, paused campaigns)
3. Multiple consecutive days of abnormally low volume followed by a sudden recovery (classic tracking outage pattern)

For each anomaly period identified:
- Check if a Data Exclusion exists covering that time window
- Verify the exclusion scope matches the affected campaigns/devices (not over-broad)
- Verify exclusion start/end times are precise (not excluding valid data before or after the outage)

**PASS:** All volume anomalies identified in D10 have corresponding Data Exclusions with correct scope and timing.
**WARN:** Data Exclusions exist but are imprecise — scope is too broad (all campaigns when only some were affected), or timing extends beyond the actual outage period.
**FAIL:** One or more volume anomalies from D10 have no Data Exclusion applied. Smart Bidding learned from corrupted data during those periods.

**Impact:** Missing Data Exclusions after a tracking outage cause Smart Bidding to interpret zero conversions as poor performance, leading to bid suppression and a recovery spiral that can take 2-4 weeks to correct.

---

## D44: Deprecated Actions
**Severity:** Medium (5 pts)
**Data:** conversions-audit.csv + conversions-daily.csv

**Check:** Identify ENABLED conversion actions that appear to be obsolete and should have been paused or removed.

Deprecated action indicators:
1. **Name-based signals:** Action names containing "old", "legacy", "deprecated", "test", "backup", "v1", "copy", "duplicate", or "do not use" (case-insensitive)
2. **Zero volume for 30+ days:** ENABLED actions with `metrics.all_conversions = 0` over the last 30 days in conversions-daily.csv, where the action is not newly created (check if it ever had volume)
3. **Superseded actions:** Two actions tracking the same event where one has recent volume and the other has none (the zero-volume action is likely the deprecated version)

**Exclusions — do not flag:**
- GOOGLE_HOSTED origin actions (these are system-managed)
- Actions created within the last 14 days (may not have fired yet)
- Secondary actions intentionally kept for historical reporting (note these as INFO)

**PASS:** No ENABLED actions show deprecated indicators. All active actions have recorded conversions within the last 30 days or are recently created.
**WARN:** 1-2 ENABLED actions show deprecated signals (zero volume for 30+ days or legacy naming) but are set to secondary (low impact — not affecting Smart Bidding).
**FAIL:** ENABLED actions with deprecated signals are set to primary, or 3+ deprecated actions are cluttering the account regardless of primary/secondary status.

**Note:** Deprecated actions set to primary are worse than clutter — if they are in the account-default goal set and have zero volume, they dilute Smart Bidding's understanding of what constitutes a successful conversion.

---

## D45: GA4 Import Duplication
**Severity:** Critical (15 pts)
**Data:** conversions-audit.csv

**Check:** Detect double-counting from GA4 event imports running alongside native GACT pixel tracking for the same conversion event.

Duplication indicators:
1. **Same category, both primary:** Two ENABLED actions with the same `conversion_action.category` where one has `conversion_action.type = WEBPAGE` (GACT pixel) and the other has a GA4-import pattern — look for `conversion_action.origin` values suggesting GA4 import, or action names containing "GA4", "Firebase", or matching GA4 event naming conventions (e.g., "generate_lead", "purchase" with snake_case)
2. **Same event, different sources:** Actions with semantically identical names (e.g., "Purchase" WEBPAGE type + "purchase" or "GA4 - Purchase" with a different type) where both have `primary_for_goal = true`
3. **Volume correlation:** Both actions show similar conversion volumes for the same period (strong signal of double-counting)

**PASS:** No pairs of GA4-import + GACT actions exist for the same event with both set to primary. Or: GA4 imports exist but are correctly set to secondary (reporting only, not feeding Smart Bidding).
**WARN:** A GA4-import action exists alongside a GACT action for the same event, but only one is primary. The secondary one is acceptable for reporting backup — flag as INFO with a note to ensure it stays secondary.
**FAIL:** Both a GACT pixel action and a GA4-import action for the same conversion event are set to primary. This double-counts conversions for Smart Bidding, inflating conversion volume and deflating CPA/ROAS — directly corrupting bid signals.

**Impact:** Double-counting is one of the most damaging tracking errors. Smart Bidding sees 2x the actual conversions, leading to overbidding, inflated performance metrics, and budget waste. If detected, recommend immediately setting one action to secondary.

**Cross-reference:** D03 (Duplicate Detection) may also flag this. D45 specifically targets the GA4-import + GACT pattern which is the most common source of duplication in accounts that have migrated or added GA4 imports without removing/demoting the original GACT actions.
