# Diagnostic Rules — Advanced Features (D46-D50)

Read during Phase 1 and Phase 2 when running `/tracking-specialist advanced` or `/tracking-specialist` (default).
Also read `diagnostic-rules-shared.md` first.

## Module Scoring

| ID | Diagnostic | Severity | Pts |
|----|-----------|----------|-----|
| D46 | Cart Data Tracking | Medium | 5 |
| D47 | New Customer Tracking | Medium | 5 |
| D48 | Custom Variables | Low | 2 |
| D49 | Cross-Device Assessment | Low | 2 |
| D50 | Measurement Maturity Scoring | — | 0 |
| **Total** | | | **14** |

**Vertical adjustment:** D46 applies to ecommerce only. For non-ecommerce accounts, exclude D46 from scoring (adjusted total: 9 pts).

---

## D46: Cart Data Tracking
**Severity:** Medium (5 pts) — ecommerce only. SKIP for non-ecommerce.
**Phase:** 2 (Chrome DevTools — requires conversion test) + Phase 1 (API supplemental)
**Data:** dataLayer on conversion page + conversions-audit.csv

**Check:** Verify cart-level data (product ID, price, quantity) is flowing to Google Ads with purchase conversion events. Cart data enables product-level ROAS analysis in Shopping and Performance Max campaigns.

**Detection methods — Chrome DevTools:**
- `evaluate_script`: inspect `window.dataLayer` for purchase events containing an `items` array:
  - Each item should include: `item_id` (or `id`), `item_name` (or `name`), `price`, `quantity`
  - Optional but valuable: `item_brand`, `item_category`, `discount`
- `list_network_requests`: look for conversion requests to `googleads.g.doubleclick.net/pagead/conversion/` containing:
  - `aw_merchant_id=` parameter (Merchant Center ID)
  - `aw_feed_country=` parameter
  - `aw_feed_language=` parameter
  - `discount=` parameter
  - `items=` or encoded item data in the request payload

**Expected dataLayer structure (GA4 ecommerce):**
```
items: [
  { item_id: "SKU-123", item_name: "Product Name", price: 29.99, quantity: 2 },
  { item_id: "SKU-456", item_name: "Another Product", price: 15.00, quantity: 1 }
]
```

**API supplemental check:**
- In conversions-audit.csv, look for purchase actions. Cart data configuration is not directly visible in the API, but if the action has `category = PURCHASE` and dynamic values, cart data may be configured at the tag level.

**PASS:** dataLayer purchase event contains `items` array with `item_id`, `price`, and `quantity` per product. Conversion request includes merchant ID and feed parameters.
**WARN:** dataLayer has an `items` array but missing key fields (e.g., `price` or `quantity` absent). Or: items array present but only contains one item when the test cart has multiple (partial implementation).
**FAIL:** No `items` array in the purchase dataLayer event. No cart-level parameters in the conversion request. Cart data is not implemented.

**Passive mode:** Only detectable if visiting a post-conversion page with dataLayer still populated. Mark as SKIP if no purchase data visible.
**Full test mode:** Complete a test purchase with multiple items. Inspect dataLayer immediately after the purchase event fires. This is the reliable way to verify D46.

**Impact:** Without cart data, Shopping and PMax campaigns cannot optimize at the product level. Enables product-level ROAS reporting and profit-based bidding when combined with COGS in the product feed.

---

## D47: New Customer Tracking
**Severity:** Medium (5 pts)
**Phase:** 1 (API) + Interactive
**Data:** conversions-audit.csv + campaign data

**Check:** Verify whether new vs. returning customer identification is configured. This enables New Customer Acquisition (NCA) campaigns and customer lifetime value optimization.

**Detection methods — API:**
1. In conversions-audit.csv, look for conversion actions with names or categories suggesting new customer tracking:
   - Action names containing "new customer", "first purchase", "new buyer", "acquisition"
   - Check for `new_customer` related parameters in conversion action configuration
2. Check campaign-level settings: NCA goal may be configured at the campaign level for Shopping/PMax campaigns

**Detection methods — Chrome DevTools:**
- `evaluate_script`: check dataLayer for `new_customer` parameter in purchase events:
  - `new_customer: true/false` in the purchase event data
  - Customer list-based: checks against a hashed customer list uploaded to Google Ads
  - Tag-based: `new_customer` parameter set dynamically based on first-purchase logic

**Implementation methods (for context):**
| Method | How it works | Visibility |
|--------|-------------|-----------|
| Tag-based detection | `new_customer` parameter in conversion tag | Visible in dataLayer and conversion request |
| Customer list upload | Hashed customer emails uploaded to Google Ads | Not visible in tags — configured in Google Ads UI |
| Auto-detection (Google) | Google determines based on its own data | Not visible — requires NCA campaign goal enabled |

**PASS:** New customer parameter detected in dataLayer purchase events (`new_customer: true/false`). Or: user confirms NCA goal is configured in campaign settings.
**WARN:** No `new_customer` parameter in dataLayer, but account runs Shopping/PMax campaigns where NCA would be valuable. API visibility is limited — ask user to confirm status.
**FAIL:** No new customer tracking detected AND account has active Shopping/PMax campaigns with customer acquisition as a business goal (per business.md).

**Interactive fallback:**
```
For D47 I need to check if new customer tracking is configured.

I couldn't detect a `new_customer` parameter in the conversion tags. Can you confirm:
1. Is NCA (New Customer Acquisition) goal enabled on any Shopping/PMax campaigns?
2. Have you uploaded a customer list for new customer detection?
3. Is the conversion tag passing a `new_customer` parameter?
4. Not configured — we haven't set this up
5. Skip this check
```

**Note:** New customer tracking is an enhancement feature — not required for all accounts. Severity is Medium because it directly improves bidding for acquisition-focused campaigns. If business.md does not mention customer acquisition as a priority, downgrade to Low (2 pts).

---

## D48: Custom Variables
**Severity:** Low (2 pts)
**Phase:** Interactive (ask user)
**Data:** Account-specific — no standard API query

**Check:** Assess whether custom variables (custom parameters) are set up for enhanced reporting segmentation.

**Step 1: Ask the user:**

```
For D48 I need to check if you're using custom variables for conversion segmentation.

Custom variables let you segment conversion data by custom dimensions (e.g., lead quality tier, product category, subscription plan).

1. Yes — I have custom variables set up (please describe what they track)
2. No — we haven't configured custom variables
3. Not sure — I'd need to check
4. Skip this check
```

**Step 2: Based on response:**
- If user describes **active custom variables**: record what they track, verify they align with business reporting needs from business.md
- If user says **no**: assess whether custom variables would add value based on the account's vertical and complexity
- If user is **unsure**: suggest checking Google Ads > Goals > Conversions > Settings for custom variable configuration, or checking GTM for custom parameters in conversion tags
- If user **skips**: mark as SKIP

**Step 3: Evaluate:**

**Custom variable value by vertical:**
| Vertical | High-value custom variables |
|----------|---------------------------|
| Ecommerce | Product category, margin tier, shipping method, first vs. repeat purchase |
| Lead Gen | Lead quality tier, lead source, service type, estimated deal value bucket |
| SaaS | Plan type, trial source, feature usage tier, annual vs. monthly |

**PASS:** Custom variables configured and actively used for reporting segmentation that aligns with business goals.
**WARN:** No custom variables configured, but account complexity and business.md suggest they would add reporting value (e.g., lead gen with multiple service types, ecommerce with varied margins).
**FAIL:** Not applicable — custom variables are a nice-to-have. Maximum severity for this diagnostic is WARN.

**Note:** This diagnostic is informational and intended to surface optimization opportunities. It should never block or significantly impact an audit score.

---

## D49: Cross-Device Assessment
**Severity:** Low (2 pts)
**Phase:** 1 (API — informational)
**Data:** conversions-audit.csv + conversions-daily.csv

**Check:** Assess whether the account meets volume thresholds for Google's cross-device conversion modeling and note coverage adequacy.

**Detection method:**
Cross-device conversions are a Google modeling feature that cannot be directly configured or verified. Assessment is based on whether the account has sufficient conversion volume for cross-device models to activate.

1. Calculate monthly conversion volume from conversions-daily.csv:
   - Sum `metrics.all_conversions` for all primary actions over the last 30 days
2. Evaluate against volume thresholds:

| Monthly conversions | Cross-device modeling |
|--------------------|---------------------|
| <50 | Unlikely to have cross-device modeling active |
| 50-100 | May have limited cross-device modeling |
| 100-500 | Cross-device modeling likely active |
| >500 | Cross-device modeling reliably active |

**Supplemental check — device performance:**
- If `device-performance.csv` is available in `context/google-ads/data/`, check conversion distribution across devices
- A healthy cross-device account shows conversions across mobile, desktop, and tablet
- If 95%+ of conversions come from a single device type, cross-device modeling has limited impact

**PASS:** Account has >100 monthly conversions across primary actions. Conversions distributed across multiple device types.
**WARN:** Account has 50-100 monthly conversions (cross-device modeling may be limited). Or: >95% of conversions from a single device type.
**FAIL:** Account has <50 monthly conversions. Cross-device modeling is unlikely to be active. Note as informational — this is a volume issue, not a configuration issue.

**Note:** This is an informational diagnostic. Cross-device modeling is automatic when volume thresholds are met. No configuration action is required from the user. The purpose is to set expectations about cross-device data coverage in the audit report.

---

## D50: Measurement Maturity Scoring
**Severity:** Not scored (0 pts) — meta-diagnostic
**Phase:** Final (runs after all other modules complete)
**Data:** Results from all diagnostic modules

**Check:** Calculate an overall measurement sophistication rating based on all completed diagnostic modules. This is a meta-diagnostic that produces a summary assessment, not a standalone check.

**Calculation:**

1. Collect scores from all completed modules:
   - Completeness (D01-D07): X / 80 pts
   - Tag Health (D08-D17): X / 80 pts
   - Consent Mode (D25-D29): X / 27 pts (or adjusted total for non-EU)
   - Advanced Features (D46-D49): X / 14 pts (or adjusted for non-ecommerce)
   - Any other active modules: include their scores

2. Calculate overall percentage:
   ```
   total_earned = sum of all earned points across modules
   total_possible = sum of all possible points across modules (excluding SKIPs)
   maturity_pct = total_earned / total_possible * 100
   ```

3. Apply maturity tier:

| Score % | Maturity Tier | Description |
|---------|--------------|-------------|
| 0-40% | Basic | Only essential tracking in place. Conversion data is unreliable for Smart Bidding. Significant gaps in foundational features. Priority: fix Critical and High severity issues before optimizing campaigns. |
| 41-70% | Intermediate | Good foundation with some advanced features. Core tracking works but enhancement features are missing or misconfigured. Priority: address remaining High severity issues and enable key enhancements. |
| 71-90% | Advanced | Comprehensive tracking with most features configured. Data quality is good. Minor improvements available in consent mode, advanced features, or data hygiene. Priority: fine-tune and monitor. |
| 91-100% | Expert | Full measurement stack implemented. Tracking is production-grade with all relevant enhancement features active. Priority: maintain and monitor for regressions. |

**Output format:**

```
## Measurement Maturity: [Tier] ([X]%)

| Module | Score | Rating |
|--------|-------|--------|
| Completeness (D01-D07) | X/80 | [Excellent/Good/Needs Attention/Critical] |
| Tag Health (D08-D17) | X/80 | [Excellent/Good/Needs Attention/Critical] |
| Consent Mode (D25-D29) | X/27 | [Excellent/Good/Needs Attention/Critical] |
| Advanced Features (D46-D49) | X/14 | [Excellent/Good/Needs Attention/Critical] |
| **Overall** | **X/Y** | **[Tier]** |

### Top Priority Actions
1. [Highest-impact FAIL item from any module]
2. [Second-highest-impact FAIL item]
3. [Third-highest-impact FAIL or highest WARN]
```

**Per-module rating thresholds (same as shared scoring):**
| Score % | Rating |
|---------|--------|
| 90-100% | Excellent |
| 70-89% | Good |
| 50-69% | Needs Attention |
| < 50% | Critical |

**Priority action selection:**
1. List all FAIL items sorted by severity (Critical > High > Medium > Low)
2. Within same severity, prioritize items with higher point values
3. Cap at 5 priority actions — more than 5 overwhelms the user
4. For each action, include: diagnostic ID, what's wrong, and the recommended fix

**Note:** D50 is always the last diagnostic to run. It depends on results from all other modules. If any modules were skipped entirely (not individual diagnostics, but whole modules), note which modules are missing and that the maturity score is partial.

---

## Execution Summary

### Phase 1 — API Diagnostics
| ID | Name | Severity | Pts |
|----|------|----------|-----|
| D47 | New Customer Tracking | Medium | 5 |
| D49 | Cross-Device Assessment | Low | 2 |

### Phase 2 — Chrome DevTools (user provides URL)
| ID | Name | Mode | Pts |
|----|------|------|-----|
| D46 | Cart Data Tracking | Full test (consent required) | 5 |

### Interactive (ask user for data)
| ID | Name | Method |
|----|------|--------|
| D47 | New Customer Tracking | API first, then ask user if inconclusive. SKIP if user declines. |
| D48 | Custom Variables | Ask user directly — no automated detection. SKIP if user declines. |

### Meta-Diagnostic (runs last)
| ID | Name | Method |
|----|------|--------|
| D50 | Measurement Maturity Scoring | Calculated from all other module results. Always runs. |

### Trigger Rules
- D46: SKIP automatically for non-ecommerce accounts (check business.md vertical)
- D47: If business.md lists customer acquisition as a goal → severity stays Medium. If not mentioned → downgrade to Low (2 pts)
- D48: Maximum result is WARN (never FAIL) — informational only
- D49: Informational only — no configuration action required from user
- D50: Always runs last. Requires at least Completeness + Tag Health modules to produce a meaningful score. If only one module completed, note the score is partial.
