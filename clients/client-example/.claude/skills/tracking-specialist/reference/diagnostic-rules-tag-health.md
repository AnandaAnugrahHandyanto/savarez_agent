# Diagnostic Rules — Tag Health (D08-D17)

Read during Phase 1 (D08-D10 API) and Phase 2 (D11-D16 Chrome DevTools) when running `/tracking-specialist tag-health` or `/tracking-specialist` (default).
Also read `diagnostic-rules-shared.md` first.

## Module Scoring

| ID | Diagnostic | Severity | Pts |
|----|-----------|----------|-----|
| D08 | Action Status | Critical | 15 |
| D09 | Volume Zero-Check | Critical | 15 |
| D10 | Volume Anomaly | High | 10 |
| D11 | Google Tag Presence | Medium | 5 |
| D12 | Conversion Linker | Medium | 5 |
| D13 | Tag Firing Verification | Medium | 5 |
| D14 | Transaction ID Population | Medium | 5 |
| D15 | Dynamic Value Accuracy | Medium | 5 |
| D16 | Currency Correctness | Medium | 5 |
| D17 | Backend Data Cross-Check | High | 10 |
| **Total** | | | **80** |

---

## D08: Action Status
**Severity:** Critical (15 pts)
**Phase:** 1 (API)
**Data:** conversions-audit.csv

**Check:** Verify `conversion_action.status` for all primary actions.

**PASS:** All primary actions have `status = ENABLED`.
**WARN:** A secondary action is PAUSED or HIDDEN (may be intentional — flag for review).
**FAIL:** Any primary action has `status` other than ENABLED (PAUSED, HIDDEN, or REMOVED but still set as primary).

**Note:** "Recording conversions" in the UI is a combination of status = ENABLED AND recent conversion volume > 0. A primary action that is ENABLED but has zero recent volume is caught by D09.

---

## D09: Volume Zero-Check
**Severity:** Critical (15 pts)
**Phase:** 1 (API)
**Data:** conversions-audit.csv (for lifetime) + conversions-daily.csv (for recent)

**Check:** Flag primary actions with zero conversions in the last 7+ days.

Using conversions-daily.csv (last 14 days):
1. Sum `metrics.all_conversions` for last 7 days per primary action
2. Compare against prior 7 days

**PASS:** All primary actions have `metrics.all_conversions > 0` in the last 7 days.
**WARN:** Primary action had conversions in prior 7 days but zero in last 7 days (recent breakage).
**FAIL:** Primary action has zero conversions in both the last 7 days AND prior 7 days (tag likely never worked or is broken).

**Note:** For lifetime check, if `metrics.all_conversions = 0` in conversions-audit.csv (no date filter), the action has NEVER recorded a conversion — always FAIL.

---

## D10: Volume Anomaly
**Severity:** High (10 pts)
**Phase:** 1 (API)
**Data:** conversions-daily.csv (last 14 days)

**Check:** Detect sudden drops in conversion volume for primary actions.

1. Calculate sum of last 7 days vs prior 7 days per primary action
2. Calculate drop percentage: `(prior_7d - last_7d) / prior_7d`
3. Check for any single day with 0 conversions when 7-day average > 1/day

**PASS:** No period-over-period drop exceeding 50%. No unexpected zero-conversion days.
**WARN:** Drop of 30-50% (could be seasonal or competitive — flag for investigation).
**FAIL:** Drop of >50% sustained across the 7-day period. Or zero-conversion days when 7-day average > 1/day.

**If FAIL:** Highest priority issue — likely a tracking outage. Triggers D11-D16 Chrome DevTools checks as mandatory. Recommend Data Exclusion for the affected period.

---

## D11: Google Tag Presence (Chrome DevTools)
**Severity:** Medium (5 pts)
**Phase:** 2 (Chrome DevTools — passive)
**Data:** Page source + network requests

**Check:** Verify Google Tag (gtag.js) or GTM container loads on tracked pages.

**Detection methods:**
- `evaluate_script`: check `typeof gtag !== 'undefined'`, `typeof google_tag_manager !== 'undefined'`, `Array.isArray(window.dataLayer)`
- `list_network_requests`: look for requests to `googletagmanager.com` (both `/gtm.js` for GTM and `/gtag/js` for gtag)

**PASS:** Google Tag or GTM container loads. Network requests to `googletagmanager.com` successful.
**WARN:** Tag loads on conversion page but not on landing page (Conversion Linker missing on entry).
**FAIL:** No Google Tag or GTM container detected on the conversion page.

**Note:** Check both landing page AND conversion page. Server-side GTM uses custom subdomain instead of `googletagmanager.com`.

---

## D12: Conversion Linker (Chrome DevTools)
**Severity:** Medium (5 pts)
**Phase:** 2 (Chrome DevTools — passive)
**Data:** Network requests + cookies on landing page

**Check:** Verify Conversion Linker fires and sets click-attribution cookies.

**Detection methods:**
- `list_network_requests`: look for requests to `googleads.g.doubleclick.net/pagead/viewthroughconversion/`
- `evaluate_script`: check for `_gcl_aw` or `_gcl_dc` cookies via `document.cookie`

**PASS:** Conversion Linker fires. `_gcl_aw` cookie present.
**WARN:** Conversion Linker fires but no `_gcl_` cookies visible (may be blocked by consent or ITP).
**FAIL:** No Conversion Linker network request detected. No `_gcl_` cookies set. Click attribution broken.

---

## D13: Tag Firing Verification (Chrome DevTools)
**Severity:** Medium (5 pts)
**Phase:** 2 (Chrome DevTools — requires conversion test)
**Data:** Network requests on conversion page

**Check:** Verify conversion tag fires when a conversion event occurs.

**Detection methods:**
- `list_network_requests`: look for requests to `googleads.g.doubleclick.net/pagead/conversion/` containing:
  - `label=` parameter (Conversion Label)
  - `value=` parameter (conversion value)
  - `oid=` parameter (Transaction ID / order ID)
  - `currency_code=` parameter

**PASS:** Conversion request fires with label, value (if ecommerce), and Transaction ID.
**WARN:** Conversion fires but `oid=` empty (no Transaction ID) or `value=` is 0/missing for ecommerce.
**FAIL:** No conversion request detected after triggering the conversion event.

**Passive mode:** Only detectable if visiting a post-conversion page that still has the conversion request in the browser. Mark as SKIP if no conversion data visible.
**Full test mode:** Trigger a real conversion (form submit, add-to-cart) with user consent. Conversion request should fire within seconds. This is the reliable way to verify D13.

---

## D14: Transaction ID Population (Chrome DevTools)
**Severity:** Medium (5 pts)
**Phase:** 2 (Chrome DevTools — requires conversion test)
**Data:** dataLayer on conversion page

**Check:** Verify `transaction_id` is present and populated in conversion events.

**Detection methods:**
- `evaluate_script`: inspect `window.dataLayer` for events with `transaction_id` or nested `ecommerce.transaction_id`
- Check `oid=` parameter in conversion network requests (D13)

**Expected by vertical:**
| Vertical | Transaction ID source |
|----------|----------------------|
| Ecommerce | Order ID (e.g., "ORD-12345") |
| Lead Gen | Form submission ID or timestamp-based unique ID |
| SaaS | Subscription/signup ID |

**PASS:** `transaction_id` present, non-empty, appears unique.
**WARN:** `transaction_id` present but appears generic/auto-generated (e.g., always "1", timestamps only).
**FAIL:** No `transaction_id` in dataLayer or conversion request. Deduplication impossible.

**Passive mode:** Only visible if visiting a post-conversion page with dataLayer still populated. Mark as SKIP otherwise.
**Full test mode:** After triggering a conversion (form submit / add-to-cart), check the dataLayer immediately. This is the reliable way to verify D14.

**Impact:** Without Transaction ID: no deduplication, no Conversion Adjustments (RESTATE/RETRACT), unreliable data.

---

## D15: Dynamic Value Accuracy (Chrome DevTools)
**Severity:** Medium (5 pts)
**Phase:** 2 (Chrome DevTools — requires conversion test)
**Data:** dataLayer on conversion page + conversion network requests

**Check:** Verify conversion `value` parameter is dynamic and matches actual transaction amounts.

**Detection methods:**
- `evaluate_script`: check dataLayer for `value` in purchase/conversion events
- Check `value=` parameter in conversion network request (D13)

**PASS:** Value is numeric, non-zero, and appears dynamic (varies per transaction). For ecommerce: matches order total.
**WARN:** Value present but appears static (same value on every page load — may be a default value). Or value is a string instead of number.
**FAIL:** Value is 0 or missing for ecommerce purchases. Or value = 1.00 (common static placeholder).

**Vertical expectations:**
| Vertical | Expected |
|----------|----------|
| Ecommerce | Dynamic order total (must vary) |
| Lead Gen (no OCT) | 0 or estimated average acceptable |
| Lead Gen (with OCT) | Dynamic deal values via import |
| SaaS | Dynamic subscription/plan value |

---

## D16: Currency Correctness (Chrome DevTools + API)
**Severity:** Medium (5 pts)
**Phase:** 2 (Chrome DevTools) + Phase 1 (API)

**Check:** Verify currency code matches account settings.

**API check:** Read `conversion_action.value_settings.default_currency_code` from conversions-audit.csv.
**Chrome DevTools check:** Inspect dataLayer for `currency` parameter in conversion events. Check `currency_code=` in conversion network requests.

**PASS:** Currency code is a valid ISO 4217 code AND matches the account's reporting currency. API and on-page values align.
**WARN:** Currency code present but differs between API setting and on-page value (possible multi-currency setup — flag for review).
**FAIL:** No currency code set in either location for ecommerce. Or invalid/malformed currency code.

**Note:** For single-currency accounts, this is straightforward. For multi-currency, the on-page currency should be the transaction currency (auto-converted by Google Ads to the account currency).

---

## D17: Backend Data Cross-Check
**Severity:** High (10 pts)
**Phase:** 1 (Interactive — ask the user)

**Check:** Compare Google Ads conversion counts to actual backend transactions.

**Step 1: Ask the user what backend data they can provide:**

```
For D17 I need to compare Google Ads conversions against your actual backend data.

What can you provide?
1. CRM export (CSV/Excel) — last 30 days of closed deals / conversions
2. Ecommerce platform numbers — total orders + revenue for last 30 days
3. Analytics data — GA4 or other analytics conversion counts
4. Just the numbers — tell me your backend conversion count + revenue for last 30 days
5. Skip this check — I'll flag it for later
```

**Step 2: Based on response:**
- If user provides a **file** (CSV/Excel): read it via the Read tool, extract total conversions and value for the period, compare against conversions-audit.csv
- If user provides **numbers verbally**: use those directly
- If user says **which CRM** they use (HubSpot, Salesforce, Pipedrive, etc.): note it in the report for future automation potential, then ask for the numbers or an export
- If user **skips**: mark as SKIP, note in report as "Backend comparison pending — ask {CRM name if known} for export"

**Step 3: Compare (if data provided):**

**Acceptable thresholds:**
- Volume: Google Ads within 10% of backend count
- Value: Google Ads within 15% of backend revenue

| Discrepancy | Likely cause |
|-------------|-------------|
| Google Ads > backend by >10% | Duplicates, missing Transaction IDs, or double-firing |
| Google Ads < backend by >10% | Consent blocking, broken tags, or attribution window too short |
| Within 10% | Normal (DDA modeling and consent modeling cause minor differences) |

**PASS:** Volume within 10%, value within 15%.
**WARN:** Volume 10-20% off OR value 15-25% off.
**FAIL:** Volume >20% off OR value >25% off.

**Step 4: Document findings:**
- Record the over-attribution ratio in the report
- If the user shared their CRM name, note it for future reference
- Suggest documenting the ratio in business.md for ongoing calibration

---

## Execution Summary

### Phase 1 — API Diagnostics (always run)
| ID | Name | Severity | Pts |
|----|------|----------|-----|
| D08 | Action Status | Critical | 15 |
| D09 | Volume Zero-Check | Critical | 15 |
| D10 | Volume Anomaly | High | 10 |

### Phase 2 — Chrome DevTools (optional, user provides URL)
| ID | Name | Mode | Pts |
|----|------|------|-----|
| D11 | Google Tag Presence | Passive | 5 |
| D12 | Conversion Linker | Passive | 5 |
| D13 | Tag Firing Verification | Full test (consent required) | 5 |
| D14 | Transaction ID Population | Full test (consent required) | 5 |
| D15 | Dynamic Value Accuracy | Full test (consent required) | 5 |
| D16 | Currency Correctness | Passive + API | 5 |

### Interactive (ask user for data)
| ID | Name | Method |
|----|------|--------|
| D17 | Backend Data Cross-Check | Ask user for CRM export or numbers. SKIP if user declines. |

### Trigger Rules
- D10 FAIL → D11-D16 become **mandatory** (tracking outage suspected)
- D10 PASS → D11-D16 are **recommended** (standard audit)
- D17: ask user during Phase 1 — never auto-skip without asking first
