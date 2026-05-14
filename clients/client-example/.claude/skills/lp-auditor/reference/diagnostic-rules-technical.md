# LP Auditor — Technical Diagnostics (LP-D17–D24)

Data source: Chrome DevTools (Lighthouse, mobile emulation, network monitoring) + Google Ads data (device-performance.csv)

Reference: `sops/SOP – Improve Landing Page Experience.md`

---

## LP-D17: Page Load Speed
**Severity:** Critical (15 pts) | **Data:** Chrome DevTools Lighthouse audit

**Rule:** Landing pages must load in under 3 seconds. Slow pages increase bounce rates and hurt Google's Landing Page Experience Quality Score signal.

**How to check:**
1. Run Lighthouse audit via Chrome DevTools
2. Extract Performance score and load time metrics
3. Evaluate against thresholds

**Pass/Fail:**
- PASS: Load time <3s AND Performance score ≥90
- WARN: Load time 3-5s OR Performance score 50-89
- FAIL: Load time >5s OR Performance score <50

**Context notes:**
- Test on both mobile and desktop — mobile performance is often worse
- If Lighthouse isn't available via DevTools, note the limitation and recommend Google PageSpeed Insights

**Routing on FAIL:** `/lp-optimizer speed`

---

## LP-D18: Core Web Vitals
**Severity:** High (10 pts) | **Data:** Chrome DevTools Lighthouse audit

**Rule:** Core Web Vitals (LCP, INP, CLS) are direct Google ranking and Quality Score signals.

**How to check:**
1. From Lighthouse audit results, extract:
   - LCP (Largest Contentful Paint)
   - INP (Interaction to Next Paint) — or FID if INP unavailable
   - CLS (Cumulative Layout Shift)
2. Evaluate each individually:
   - LCP: Good <2.5s, Needs Improvement 2.5-4s, Poor >4s
   - INP: Good <200ms, Needs Improvement 200-500ms, Poor >500ms
   - CLS: Good <0.1, Needs Improvement 0.1-0.25, Poor >0.25

**Pass/Fail:**
- PASS: All 3 metrics in "Good" range
- WARN: 1-2 metrics in "Needs Improvement" range, none in "Poor"
- FAIL: Any metric in "Poor" range

**Report each metric individually in Details field.**

**Routing on FAIL:** `/lp-optimizer speed`

---

## LP-D19: Mobile Responsiveness
**Severity:** High (10 pts) | **Data:** Chrome DevTools mobile emulation (375px viewport)

**Rule:** The page must be fully functional on mobile with no horizontal scroll, readable text, and tap-friendly targets.

**How to check:**
1. Emulate mobile viewport (375px width, iPhone)
2. Check for:
   - Horizontal scroll present? (overflow detection)
   - Text readable without zoom? (font size ≥16px for body text)
   - Tap targets ≥44×44px with adequate spacing?
   - CTA buttons full-width or near-full-width on mobile?
   - Images scale properly? (no cut-off or overflow)
   - Content sections stack vertically?
3. Take mobile screenshot for reference

**Pass/Fail:**
- PASS: No horizontal scroll, readable text, tap-friendly targets, proper layout
- WARN: Minor issues — 1 element overflows, or tap targets slightly small
- FAIL: Horizontal scroll present, OR text unreadable, OR CTA not accessible on mobile

**Routing on FAIL:** `/lp-optimizer mobile`

---

## LP-D20: Mobile vs Desktop CVR Gap
**Severity:** Medium (5 pts) | **Data:** `device-performance.csv`

**Rule:** Mobile CVR should be at least 60% of desktop CVR. A large gap indicates mobile UX issues.

**How to check:**
1. Read `context/google-ads/data/device-performance.csv`
2. Filter to campaigns that drive traffic to the audited URL (or overall if URL-level not available)
3. Calculate CVR per device: `metrics.conversions / metrics.clicks`
4. Compare: `mobile_cvr / desktop_cvr`

**Pass/Fail:**
- PASS: Mobile CVR ≥60% of desktop CVR
- WARN: Mobile CVR is 40-59% of desktop CVR
- FAIL: Mobile CVR <40% of desktop CVR
- SKIP: Insufficient data (fewer than 100 clicks on either device)

**Routing on FAIL:** `/lp-optimizer mobile`

---

## LP-D21: Form Field Count
**Severity:** Medium (5 pts) | **Data:** Chrome DevTools DOM extraction

**Rule:** Every extra form field reduces conversions. Lead gen forms should have ≤5 required fields.

**How to check:**
1. Find all `<form>` elements on the page
2. Count required fields (inputs with `required` attribute, or all visible non-optional fields)
3. Categorize by vertical:
   - Lead gen: PASS ≤5, WARN 6-8, FAIL >8
   - SaaS signup: PASS ≤3 (email + name + password), WARN 4-5, FAIL >5
   - Ecommerce checkout: evaluated in D39 instead
4. If no form present: check if the page is a click-through (CTA links elsewhere)

**Pass/Fail:**
- PASS: Required fields ≤5 (lead gen) or ≤3 (SaaS)
- WARN: 6-8 fields (lead gen) or 4-5 (SaaS)
- FAIL: >8 fields (lead gen) or >5 (SaaS)
- SKIP: No form on page (click-through LP or ecommerce)

**Routing on FAIL:** `/lp-optimizer forms`

---

## LP-D22: Form Functionality
**Severity:** Critical (15 pts) | **Data:** Chrome DevTools form interaction (requires user consent)

**Rule:** Forms must submit correctly and lead to a confirmation state. A broken form means zero conversions.

**How to check:**
1. **ASK user for consent:** "May I test the form by filling it with test data and submitting?"
   - If No: SKIP this diagnostic
   - If Yes: proceed
2. Fill form fields with test data (use clearly fake data: "Test User", "test@test.com", etc.)
3. Submit the form
4. Check:
   - Does submission succeed? (no error, no infinite spinner)
   - Does a thank-you page or confirmation state appear?
   - Is there a success message or redirect?
5. If form fails: note the error for debugging

**Pass/Fail:**
- PASS: Form submits successfully, confirmation state appears
- FAIL: Form submission fails, errors out, or no confirmation
- SKIP: User declined form testing

**Context notes:**
- Always use obviously fake test data
- Check if form has CAPTCHA — may need user to complete manually
- If thank-you page exists, verify it has appropriate messaging and no dead-end

**Routing on FAIL:** `/lp-optimizer forms`

---

## LP-D23: SSL/HTTPS
**Severity:** Low (3 pts) | **Data:** URL protocol check + Chrome DevTools

**Rule:** All pages must use HTTPS. HTTP pages lose trust and trigger browser warnings.

**How to check:**
1. Check URL protocol — starts with `https://`?
2. Check for mixed content warnings (HTTP resources loaded on HTTPS page)
3. Verify SSL certificate is valid (no browser security warnings)

**Pass/Fail:**
- PASS: HTTPS with valid certificate, no mixed content
- WARN: HTTPS but mixed content warnings present
- FAIL: HTTP (no SSL) or invalid/expired certificate

**Routing on FAIL:** Developer/hosting fix needed

---

## LP-D24: Image Optimization
**Severity:** Low (3 pts) | **Data:** Chrome DevTools network monitoring

**Rule:** Images should be optimized for web delivery. Large uncompressed images are the most common cause of slow pages.

**How to check:**
1. Monitor network requests during page load via Chrome DevTools
2. Flag issues:
   - Images >200KB
   - Uncompressed formats (BMP, unoptimized PNG)
   - Missing lazy loading for below-fold images
   - Render-blocking scripts
   - Total page weight >3MB
3. List specific offending resources with sizes

**Pass/Fail:**
- PASS: All images <200KB, modern formats (WebP/AVIF or compressed JPEG/PNG), lazy loading used, page <3MB
- WARN: 1-2 images >200KB or page weight 3-5MB
- FAIL: Multiple images >500KB, or uncompressed formats, or page >5MB

**Routing on FAIL:** `/lp-optimizer speed`
