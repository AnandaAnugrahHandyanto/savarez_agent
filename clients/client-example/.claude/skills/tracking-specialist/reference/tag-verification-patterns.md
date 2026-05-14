# Tag Verification Patterns

Reference file for Phase 2 Chrome DevTools Diagnostics (D11-D16).
Each section contains the JS to evaluate, what PASS/FAIL looks like, and common edge cases.

---

## D11: Google Tag Detection

### What to check

The site must have either a standalone gtag.js implementation or a Google Tag Manager container loading the Google tag.

### JS to evaluate

```javascript
// Check for gtag function
const hasGtag = typeof gtag === 'function';

// Check for GTM container
const hasGTM = typeof google_tag_manager === 'object' && google_tag_manager !== null;

// Check for dataLayer existence
const hasDataLayer = Array.isArray(window.dataLayer);

// Get GTM container IDs if present
const gtmContainerIds = hasGTM
  ? Object.keys(google_tag_manager).filter(k => k.startsWith('GTM-'))
  : [];

// Check for gtag.js script element in DOM
const gtagScripts = Array.from(document.querySelectorAll('script[src*="gtag/js"]'));
const gtagIds = gtagScripts.map(s => {
  const match = s.src.match(/[?&]id=([A-Z0-9-]+)/);
  return match ? match[1] : null;
}).filter(Boolean);

JSON.stringify({
  gtag: hasGtag,
  gtm: hasGTM,
  gtmContainerIds,
  dataLayer: hasDataLayer,
  dataLayerLength: hasDataLayer ? dataLayer.length : 0,
  gtagScriptIds: gtagIds
});
```

### Interpreting results

| Result | Verdict | Notes |
|--------|---------|-------|
| `gtag: true` and `gtagScriptIds` contains AW- or G- ID | PASS (hardcoded gtag) | Standalone implementation |
| `gtm: true` and `gtmContainerIds` has GTM-XXXXXX | PASS (GTM) | GTM loads the Google tag internally |
| `gtm: true` but `gtag: false` | PASS | GTM may load gtag internally; gtag function is not always exposed globally when GTM manages it |
| All false | FAIL | No Google tag detected |
| `dataLayer: true` but `gtm: false` | WARN | dataLayer exists (possibly from a plugin) but no GTM container is processing it |

### Common false negatives

- **Tag loaded async**: gtag.js loads asynchronously. If the check runs before the script loads, `gtag` may be undefined. Wait for page load before evaluating.
- **GTM loads gtag internally**: When GTM fires the Google Tag, it may not expose a global `gtag` function. Check for `google_tag_manager` object instead.
- **Consent Mode blocking**: If consent has not been granted, tags may load in a restricted mode. The script elements still exist in the DOM.

---

## D12: Conversion Linker Detection

### What to check

The Conversion Linker tag must fire on every page. It sets first-party cookies that store ad click identifiers (GCLID, GBRAID, WBRAID) for cross-page and cross-domain attribution.

### Network request patterns

Look for requests to these endpoints (any match = Conversion Linker active):

```
googleads.g.doubleclick.net/pagead/viewthroughconversion/
pagead/landing
```

### JS to evaluate (cookie check)

```javascript
// Check for Google click cookies set by Conversion Linker
const cookies = document.cookie;
const gclAw = cookies.includes('_gcl_aw');    // Google Ads click
const gclDc = cookies.includes('_gcl_dc');    // DoubleClick/Display
const gclGb = cookies.includes('_gcl_gb');    // GBRAID
const gclGs = cookies.includes('_gcl_gs');    // GCLID stored

// Extract cookie values for inspection
const allCookies = cookies.split(';').map(c => c.trim());
const gclCookies = allCookies.filter(c => c.startsWith('_gcl_'));

JSON.stringify({
  _gcl_aw: gclAw,
  _gcl_dc: gclDc,
  _gcl_gb: gclGb,
  _gcl_gs: gclGs,
  gclCookiesFound: gclCookies.length,
  gclCookies: gclCookies
});
```

### Interpreting results

| Result | Verdict | Notes |
|--------|---------|-------|
| `_gcl_aw: true` | PASS | Conversion Linker active, GCLID stored in first-party cookie |
| Any `_gcl_*` cookie present | PASS | At least one click identifier is being stored |
| No `_gcl_*` cookies and no network requests to doubleclick.net | FAIL | Conversion Linker tag is missing or not firing |
| No cookies but user arrived via direct/organic | INCONCLUSIVE | Cookies are only set when the user arrives via a Google Ads click with GCLID. Test by appending `?gclid=test` to URL |

### How Conversion Linker works

1. User clicks a Google Ads ad. Google appends `gclid`, `gbraid`, or `wbraid` to the landing page URL.
2. Conversion Linker reads the click identifier from the URL parameter.
3. It stores the identifier in first-party cookies (`_gcl_aw`, `_gcl_gb`, etc.).
4. When a conversion tag fires later (even on a different page), it reads the cookie to attribute the conversion back to the click.

Without Conversion Linker, cross-page attribution breaks. The conversion tag on the thank-you page cannot connect back to the original ad click.

---

## D13: Conversion Tag Firing

### What to check

When a conversion event occurs, a network request must fire to Google Ads servers carrying the Conversion ID and Conversion Label.

### Network request patterns

Look for requests matching:

```
googleadservices.com/pagead/conversion/
```

The URL structure:

```
https://www.googleadservices.com/pagead/conversion/CONVERSION_ID/?label=CONVERSION_LABEL&...
```

### JS to evaluate (check via Performance API)

```javascript
// Check recent network requests for conversion pings
const entries = performance.getEntriesByType('resource');
const conversionRequests = entries.filter(e =>
  e.name.includes('googleadservices.com/pagead/conversion') ||
  e.name.includes('google.com/pagead/conversion')
);

const parsed = conversionRequests.map(e => {
  const url = new URL(e.name);
  const pathParts = url.pathname.split('/');
  // Conversion ID is in the path: /pagead/conversion/CONVERSION_ID/
  const conversionId = pathParts.find(p => /^\d+$/.test(p)) || null;
  const label = url.searchParams.get('label');
  const value = url.searchParams.get('value');
  const currency = url.searchParams.get('currency_code');
  const orderId = url.searchParams.get('oid');
  return { conversionId, label, value, currency, orderId };
});

JSON.stringify({
  conversionRequestCount: conversionRequests.length,
  conversions: parsed
});
```

### Interpreting results

| Field | What to verify |
|-------|---------------|
| `conversionId` | Must match the account's Conversion ID from `config.conversion_id` |
| `label` | Must match a known Conversion Label for the expected action |
| `value` | Should be present for ecommerce; numeric and non-zero |
| `currency_code` | Should be present alongside value |
| `oid` (order ID) | The transaction ID parameter; should be non-empty |

| Result | Verdict |
|--------|---------|
| Request found with matching Conversion ID | PASS |
| Request found but Conversion ID does not match config | FAIL - wrong account or tag misconfigured |
| No conversion requests after triggering event | FAIL - tag not firing on this event |
| Multiple requests with same Conversion ID + Label | WARN - possible duplicate firing |

---

## D14: Transaction ID Verification

### What to check

Every conversion event must include a unique `transaction_id` to prevent duplicate counting. Without it, page refreshes, back-button navigation, and bot visits inflate conversion numbers.

### JS to evaluate (dataLayer inspection)

```javascript
// Find purchase/conversion events in dataLayer
const purchaseEvents = (window.dataLayer || []).filter(item =>
  item.event === 'purchase' ||
  item.event === 'form_submit' ||
  item.event === 'form_submission' ||
  item.event === 'conversion' ||
  item.event === 'generate_lead'
);

const results = purchaseEvents.map(item => {
  // Check multiple possible locations for transaction_id
  const txnId =
    item.transaction_id ||
    item.transactionId ||
    (item.ecommerce && item.ecommerce.transaction_id) ||
    (item.ecommerce && item.ecommerce.purchase && item.ecommerce.purchase.transaction_id) ||
    null;

  return {
    event: item.event,
    transaction_id: txnId,
    hasTransactionId: txnId !== null && txnId !== undefined && txnId !== '',
    transactionIdType: typeof txnId,
    transactionIdLength: txnId ? String(txnId).length : 0
  };
});

JSON.stringify({
  conversionEventsFound: purchaseEvents.length,
  events: results
});
```

### dataLayer format examples

**Ecommerce (GA4 standard):**
```javascript
dataLayer.push({
  event: 'purchase',
  ecommerce: {
    transaction_id: 'ORD-2024-78432',
    value: 149.99,
    currency: 'USD'
  }
});
```

**Ecommerce (flat structure):**
```javascript
dataLayer.push({
  event: 'purchase',
  transaction_id: 'ORD-2024-78432',
  value: 149.99,
  currency: 'USD'
});
```

**Lead gen:**
```javascript
dataLayer.push({
  event: 'form_submit',
  transaction_id: 'LEAD-2026-0201-a7b3c9'
});
```

### What constitutes a valid transaction ID

| Check | PASS | FAIL |
|-------|------|------|
| Present | Non-empty string | `null`, `undefined`, `''` |
| Unique per transaction | Different value for each conversion | Same value on every page load |
| Max length | 64 characters or fewer | Exceeds 64 characters |
| Server-generated | Tied to backend record (order ID, CRM ID) | Random client-side ID that regenerates on refresh |
| Format | Alphanumeric with hyphens/underscores | Contains special characters or whitespace |

### Vertical differences

| Vertical | Expected transaction ID source | Examples |
|----------|-------------------------------|----------|
| **Ecommerce** | Order ID from platform | `ORD-2024-78432`, `#1042`, `WC-5678`, `TXN_98765` |
| **Lead Gen** | Form submission ID from CRM or backend | `LEAD-2024-4521`, `GF-entry-1234`, `f47ac10b-58cc-4372-a567-0e02b2c3d479` |
| **SaaS** | User/subscription/trial ID | `USR-20240201-789`, `SUB-stripe-pi_3abc`, `TRIAL-2024-5432` |

### Common issues

- **Client-side random ID**: If the ID changes on page refresh, deduplication fails completely. The ID must be the same value every time the confirmation page loads for the same transaction.
- **Timestamp-only IDs**: A bare timestamp can collide if two conversions happen in the same second. Must include a random suffix or unique record reference.
- **Missing on some checkout paths**: Express checkout (PayPal, Apple Pay), guest checkout, and mobile checkout may skip the data layer push. All paths must be tested.

---

## D15: Dynamic Value Verification

### What to check

For conversion actions that track revenue (ecommerce purchases, valued lead events), the `value` parameter must be dynamic -- reflecting the actual transaction amount, not a hardcoded placeholder.

### JS to evaluate

```javascript
// Extract value from conversion events in dataLayer
const conversionEvents = (window.dataLayer || []).filter(item =>
  item.event === 'purchase' ||
  item.event === 'conversion' ||
  item.event === 'form_submit' ||
  item.event === 'generate_lead'
);

const values = conversionEvents.map(item => {
  const val =
    item.value ||
    (item.ecommerce && item.ecommerce.value) ||
    (item.ecommerce && item.ecommerce.purchase && item.ecommerce.purchase.revenue) ||
    null;

  return {
    event: item.event,
    rawValue: val,
    valueType: typeof val,
    isNumeric: typeof val === 'number' && !isNaN(val),
    isZero: val === 0 || val === '0',
    isNonEmpty: val !== null && val !== undefined && val !== ''
  };
});

JSON.stringify({
  eventsChecked: conversionEvents.length,
  values: values
});
```

### Interpreting results

| Result | Verdict | Notes |
|--------|---------|-------|
| `isNumeric: true`, value > 0, varies between transactions | PASS | Dynamic value correctly implemented |
| `isNumeric: true`, value > 0, same value every time | FAIL | Hardcoded value -- reports fake revenue |
| `valueType: 'string'` but contains a number | WARN | Should be a number type, not a string. May work but can cause issues |
| `isZero: true` | FAIL (ecommerce) / OK (lead gen) | Ecommerce must have non-zero value. Lead gen may legitimately have zero value |
| `rawValue: null` | FAIL (ecommerce) / WARN (lead gen) | Ecommerce must pass value. Lead gen should pass value if available |

### What PASS looks like

- The value is a JavaScript `number` (not a string)
- The value is greater than zero
- The value varies between different transactions (not the same amount every time)
- The value matches the actual order total / transaction amount

### What FAIL looks like

- Hardcoded value (e.g., always `1`, always `99.99`)
- String instead of number (e.g., `"149.99"` instead of `149.99`)
- Always zero
- Includes tax/shipping when it should not (or vice versa) -- compare against business.md if available
- Missing entirely on ecommerce purchase events

---

## D16: Currency Verification

### What to check

The `currency` parameter must be present alongside `value` in conversion events. It must be a valid ISO 4217 three-letter code and match the account's configured currency.

### JS to evaluate

```javascript
// Extract currency from conversion events
const conversionEvents = (window.dataLayer || []).filter(item =>
  item.event === 'purchase' ||
  item.event === 'conversion' ||
  item.event === 'form_submit'
);

const currencies = conversionEvents.map(item => {
  const curr =
    item.currency ||
    (item.ecommerce && item.ecommerce.currency) ||
    (item.ecommerce && item.ecommerce.currencyCode) ||
    null;

  // Common ISO 4217 codes for validation
  const validCodes = [
    'USD','EUR','GBP','CAD','AUD','NZD','CHF','JPY','CNY','INR',
    'BRL','MXN','SEK','NOK','DKK','PLN','CZK','HUF','RON','BGN',
    'HRK','ZAR','SGD','HKD','TWD','KRW','THB','MYR','PHP','IDR',
    'ILS','AED','SAR','TRY','RUB','ARS','CLP','COP','PEN'
  ];

  return {
    event: item.event,
    currency: curr,
    isPresent: curr !== null && curr !== undefined && curr !== '',
    isValidFormat: typeof curr === 'string' && /^[A-Z]{3}$/.test(curr),
    isKnownCode: curr ? validCodes.includes(curr.toUpperCase()) : false
  };
});

JSON.stringify({
  eventsChecked: conversionEvents.length,
  currencies: currencies
});
```

### Interpreting results

| Result | Verdict | Notes |
|--------|---------|-------|
| `isPresent: true`, `isValidFormat: true`, matches account default | PASS | Currency correctly configured |
| `isPresent: true`, `isValidFormat: true`, does NOT match account default | WARN | Multi-currency may be intentional, but verify. Google converts using daily exchange rates |
| `isPresent: false` with `value` present | FAIL | Value without currency causes Google to assume account default, which may be wrong |
| Lowercase code (e.g., `usd` instead of `USD`) | WARN | Should be uppercase ISO 4217. Some implementations handle this, but best to fix |
| Currency symbol instead of code (e.g., `$` instead of `USD`) | FAIL | Must be ISO 4217 three-letter code |

### Cross-reference with API

Compare the currency found on-site against the account's default currency from the Google Ads API:

```
conversion_action.value_settings.default_currency_code
```

If the site sends a different currency than the account default, this is acceptable only when the business operates in multiple currencies. Otherwise, flag it as a mismatch.
