# Diagnostic Rules — Consent Mode (D25-D29)

Read during Phase 2 when running `/tracking-specialist consent` or `/tracking-specialist` (default).
Also read `diagnostic-rules-shared.md` first.

## Module Scoring

| ID | Diagnostic | Severity | Pts |
|----|-----------|----------|-----|
| D25 | CM v2 Active | High | 10 |
| D26 | Conversion Modeling | Medium | 5 |
| D27 | Modeling Uplift Reasonableness | Medium | 5 |
| D28 | CMP Functionality | Medium | 5 |
| D29 | Consent Denial Rate | Low | 2 |
| **Total** | | | **27** |

**Region adjustment:** For accounts NOT targeting EU/EEA/UK (check business.md for targeting regions):
- D25 severity drops to Medium (5 pts)
- D28 severity drops to Low (2 pts)
- D29 severity drops to Low (2 pts)
- Adjusted module total: 19 pts

---

## D25: CM v2 Active
**Severity:** High (10 pts) — EU/EEA/UK targeting. Medium (5 pts) — all other regions.
**Phase:** 2 (Chrome DevTools — passive)
**Data:** Network requests + page source

**Check:** Verify Consent Mode v2 is implemented with correct default and update commands. All four consent signals must be present: `ad_storage`, `analytics_storage`, `ad_user_data`, `ad_personalization`.

**Detection methods:**
- `list_network_requests`: look for Google Ads/Analytics requests containing consent mode parameters:
  - `gcs=` parameter (Google Consent State) — values like `G100`, `G110`, `G111` indicate consent signals active
  - `gcd=` parameter (Google Consent Default) — encodes default consent state per signal
- `evaluate_script`: check for consent mode initialization:
  - `typeof gtag !== 'undefined'` then check if consent default/update commands have been issued
  - Look for `window.dataLayer` entries containing `consent` command types (`default` and `update`)
  - Check for CMP integration scripts (Cookiebot, OneTrust, CookieYes, Complianz) that auto-configure consent mode
- `take_snapshot`: verify no console errors related to consent mode initialization

**Interpreting `gcs=` values:**
| Value | Meaning |
|-------|---------|
| `G100` | All consent denied (default state before user interaction) |
| `G110` | Analytics granted, ads denied |
| `G111` | All consent granted |
| `G1--` | Consent mode active (first digit = version, remaining digits = signal states) |

**Expected implementation pattern:**
1. Default command fires BEFORE any Google tags (sets initial consent state)
2. Update command fires AFTER user interacts with consent banner (grants/denies specific signals)
3. All four signals present: `ad_storage`, `analytics_storage`, `ad_user_data`, `ad_personalization`

**PASS:** Consent Mode v2 signals detected in network requests (`gcs=` and `gcd=` parameters present). All four consent signals configured. Default command fires before tag initialization.
**WARN:** Consent Mode detected but only v1 signals (missing `ad_user_data` or `ad_personalization`). Or: default command fires but no update command detected (user interaction not triggering consent update).
**FAIL:** No consent mode parameters in any Google network requests. No consent default/update commands in dataLayer. Consent Mode is not implemented.

**Impact:** Without Consent Mode v2, Google cannot model conversions from users who deny consent. Required for EU/EEA since March 2024. Recommended everywhere for future-proofing and data recovery.

---

## D26: Conversion Modeling
**Severity:** Medium (5 pts)
**Phase:** 1 (API)
**Data:** conversions-audit.csv

**Check:** Compare `metrics.conversions` vs `metrics.all_conversions` across primary actions. If `all_conversions > conversions`, modeled conversions are active and contributing data.

**Detection method:**
1. For each primary ENABLED action, compare:
   - `metrics.conversions` (observed conversions only)
   - `metrics.all_conversions` (observed + modeled conversions)
2. Calculate delta: `all_conversions - conversions`

**Interpreting results:**
| Scenario | Meaning |
|----------|---------|
| `all_conversions > conversions` | Modeled conversions active — consent mode is recovering data |
| `all_conversions = conversions` | No modeled conversions — modeling may not be working or consent mode not active |
| `all_conversions < conversions` | Should not happen — investigate data anomaly |

**PASS:** `all_conversions > conversions` for at least one primary action, indicating modeled conversions are flowing.
**WARN:** `all_conversions = conversions` for all primary actions, but D25 shows Consent Mode is active (modeling should be producing data but isn't — possible low traffic volume or recently enabled).
**FAIL:** `all_conversions = conversions` for all primary actions AND D25 FAIL (no Consent Mode detected). No conversion modeling is occurring.

**Note:** Modeling requires minimum traffic thresholds. Newly enabled Consent Mode may take 1-2 weeks before modeled conversions appear. If D25 PASS but D26 WARN, ask the user when Consent Mode was enabled.

---

## D27: Modeling Uplift Reasonableness
**Severity:** Medium (5 pts)
**Phase:** 1 (API)
**Data:** conversions-audit.csv

**Check:** Calculate the modeled conversion uplift percentage and verify it falls within expected ranges.

**Calculation:**
```
uplift_pct = (all_conversions - conversions) / conversions * 100
```

**Expected ranges:**
| Uplift % | Assessment |
|----------|-----------|
| 0% | No modeling — see D26 |
| 1-5% | Low but acceptable — minimal consent impact or low EU traffic share |
| 5-30% | Normal range — consent mode is recovering data as expected |
| 30-50% | Elevated — investigate CMP configuration, consent banner UX, or regional traffic mix |
| >50% | Abnormally high — likely CMP misconfiguration, overly aggressive denial defaults, or banner display issues |

**PASS:** Uplift between 5-30% (healthy modeling range).
**WARN:** Any of:
- Uplift 1-5% for an account with significant EU/EEA traffic (may indicate Consent Mode is not fully configured)
- Uplift 30-50% (elevated — CMP may be driving excessive denials)
- Uplift 0% but D25 PASS (Consent Mode active but no modeling — check if recently enabled)
**FAIL:** Uplift >50%. This strongly suggests a CMP misconfiguration: consent banner may be broken on certain devices, default state may be wrong, or the banner may be too aggressive. Investigate D28 (CMP functionality) immediately.

**Cross-reference:**
- If D27 FAIL → D28 becomes mandatory (CMP likely misconfigured)
- If D27 WARN (low uplift) + EU targeting → check D25 for v1 vs v2 signals
- Configuration Guidelines reference: modeling uplift 5-20% is the recommended healthy range; >50% triggers investigation

---

## D28: CMP Functionality
**Severity:** Medium (5 pts) — EU/EEA/UK targeting. Low (2 pts) — all other regions.
**Phase:** 2 (Chrome DevTools — passive)
**Data:** Page source + network requests + DOM

**Check:** Verify that the Consent Management Platform (CMP) consent banner is functioning correctly and displaying across devices.

**Detection methods:**
- `navigate_page`: load the site URL (clear cookies first to simulate first visit)
- `take_screenshot`: capture the page to visually confirm consent banner appears
- `list_network_requests`: look for CMP provider requests:
  - Cookiebot: `consent.cookiebot.com`
  - OneTrust: `cdn.cookielaw.org` or `optanon.blob.core.windows.net`
  - CookieYes: `cdn-cookieyes.com`
  - Complianz: `complianz` in script paths
  - Iubenda: `cdn.iubenda.com`
  - Termly: `app.termly.io`
  - Usercentrics: `usercentrics.eu`
- `evaluate_script`: check for CMP-specific global objects:
  - Cookiebot: `typeof Cookiebot !== 'undefined'`
  - OneTrust: `typeof OneTrust !== 'undefined'` or `typeof OptanonActiveGroups !== 'undefined'`
  - CookieYes: `typeof cookieyes !== 'undefined'`
  - Generic TCF v2: `typeof __tcfapi !== 'undefined'` (IAB Transparency & Consent Framework)
- `emulate` + `take_screenshot`: check banner on mobile viewport (375x812) to verify responsive display

**PASS:** CMP detected, consent banner displays on page load (first visit), banner is visible on both desktop and mobile viewports.
**WARN:** CMP detected but banner not displaying on initial page load (may be configured to show only in certain regions — ask user to confirm geo-targeting settings). Or: banner displays on desktop but not verified on mobile.
**FAIL:** No CMP provider detected in network requests or DOM. No consent banner visible on page load. Or: CMP scripts load but banner fails to render (JavaScript error).

**Note:** Some CMPs use geo-targeting and only show banners to EU/EEA visitors. If testing from a non-EU IP, the banner may not appear. Ask the user for their CMP configuration or test with a EU-based proxy if available.

---

## D29: Consent Denial Rate
**Severity:** Low (2 pts)
**Phase:** Interactive (ask user for data)
**Data:** External — cannot be verified via Google Ads API alone

**Check:** Assess whether the consent denial rate is within expected ranges for the account's target market.

**Step 1: Ask the user:**

```
For D29 I need to assess your consent denial rate.

This data isn't available in Google Ads directly. Can you provide any of:
1. CMP dashboard export — consent acceptance/denial rates for last 30 days
2. Analytics data — consent rate from GA4 or your CMP provider
3. Just the numbers — approximate consent acceptance rate (e.g., "about 70% accept")
4. Skip this check — I'll flag it for later
```

**Step 2: Based on response:**
- If user provides a **file** (CSV/screenshot from CMP dashboard): read it, extract acceptance/denial rates
- If user provides **numbers verbally**: use those directly
- If user names their **CMP provider**: note it for reference, then ask for the rate
- If user **skips**: mark as SKIP, note in report as "Consent denial rate pending — check {CMP name if known} dashboard"

**Step 3: Evaluate (if data provided):**

**Expected ranges by region:**
| Primary target region | Expected acceptance rate | Expected denial rate |
|----------------------|------------------------|---------------------|
| EU/EEA (GDPR markets) | 50-80% | 20-50% |
| UK | 55-85% | 15-45% |
| US (CCPA states) | 75-95% | 5-25% |
| Non-regulated markets | 85-99% | 1-15% |

**PASS:** Denial rate within expected range for the account's target region.
**WARN:** Denial rate higher than expected (e.g., >50% in a non-EU market, or >60% in EU). May indicate overly aggressive banner design, poor UX, or dark-pattern avoidance that swings too far. Cross-reference with D27 — high denial should correlate with higher modeling uplift.
**FAIL:** Denial rate >80% in any market. This suggests the consent banner is broken, confusing, or designed in a way that pushes users to deny. Impact: massive data loss even with consent mode modeling.

**Cross-reference:**
- D27 high uplift + D29 high denial = consistent (CMP is denying many users, modeling is compensating)
- D27 low uplift + D29 high denial = inconsistent (Consent Mode may not be properly configured to model denied users)
- D27 high uplift + D29 low denial = inconsistent (modeling uplift should be low if most users accept — investigate)

---

## Execution Summary

### Phase 1 — API Diagnostics
| ID | Name | Severity | Pts |
|----|------|----------|-----|
| D26 | Conversion Modeling | Medium | 5 |
| D27 | Modeling Uplift Reasonableness | Medium | 5 |

### Phase 2 — Chrome DevTools (user provides URL)
| ID | Name | Mode | Pts |
|----|------|------|-----|
| D25 | CM v2 Active | Passive | 10 |
| D28 | CMP Functionality | Passive | 5 |

### Interactive (ask user for data)
| ID | Name | Method |
|----|------|--------|
| D29 | Consent Denial Rate | Ask user for CMP dashboard data or acceptance rate. SKIP if user declines. |

### Trigger Rules
- D25 FAIL → D26 and D27 will likely FAIL (no consent mode = no modeling). Still run them to confirm.
- D27 FAIL (uplift >50%) → D28 becomes **mandatory** (CMP misconfiguration suspected)
- D27 WARN (low uplift) + EU targeting → investigate D25 for v1 vs v2 signal completeness
- D29 SKIP → exclude from denominator, note as pending in report
- Non-EU accounts → adjust severities per region adjustment table above
