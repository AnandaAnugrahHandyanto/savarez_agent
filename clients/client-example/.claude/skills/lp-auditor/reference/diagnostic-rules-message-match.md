# LP Auditor — Message Match Diagnostics (LP-D13–D16)

Data source: Google Ads data (ads.csv, keywords.csv) + `scripts/page-content-extractor.js` output

Reference: `sops/LP Quality Checklist.md` (Message Match section), `sops/Headline Quality Checklist.md`

**Approach:** Extract all unique final URLs from ads.csv. Group ads and keywords by final URL. Run `page-content-extractor.js` once per unique URL to extract H1, hero text, offer section, CTA text. Then compare ad copy vs extracted page content programmatically. Chrome DevTools only used for D16 (visual consistency screenshots).

---

## LP-D13: Ad-to-LP Headline Match
**Severity:** High (10 pts) | **Data:** ads.csv headlines + page-content-extractor output (H1, hero text)

**Rule:** The LP headline must reflect the ad headline language. Visitors who click an ad expect the landing page to deliver on the same promise. Mismatch = bounce.

**How to check:**
1. Group ads by final URL
2. For each unique URL, compare ad headlines to extracted H1 and hero text
3. Check for:
   - **Direct match:** Same core promise in same/similar words
   - **Close match:** Same benefit angle, different phrasing
   - **Mismatch:** Different promise, different angle, or unrelated content
4. Score per URL based on best-matching ad group

**Pass/Fail:**
- PASS: Direct or close match — LP headline delivers the ad's promise
- WARN: Same topic but different angle or phrasing that could confuse visitors
- FAIL: Clear mismatch — ad promises X, LP headline talks about Y

**Context notes:**
- For RSAs: compare all pinned headlines + top-performing headline combinations (if available)
- If multiple ad groups point to the same URL with different themes, check the primary/highest-traffic ad group first
- Dynamic text replacement (DTR) on the LP makes matching easier — note if DTR is detected

**Routing on FAIL:** `/lp-optimizer message-match`

---

## LP-D14: Ad-to-LP Offer Match
**Severity:** High (10 pts) | **Data:** ads.csv descriptions + page-content-extractor output (offer section, CTA text)

**Rule:** The offer mentioned in the ad must appear on the LP. If the ad says "Free consultation", the LP must prominently feature a free consultation CTA.

**How to check:**
1. From ads.csv: extract offer mentions from descriptions (free trial, discount, consultation, demo, download, etc.)
2. From page content: extract offer/pricing section and CTA text
3. Compare:
   - Same offer? (free trial in ad = free trial on page)
   - Same price point? (if price is mentioned in ad)
   - Same CTA action? (if ad says "Book a demo", LP CTA should be demo-related)
4. Flag bait-and-switch: ad promises one thing, LP pushes a different action

**Pass/Fail:**
- PASS: Ad offer = LP offer. Same action, same price point (if mentioned)
- WARN: Offer is present on LP but not prominently featured, or slight variation (ad: "free trial" → LP: "start free")
- FAIL: Ad promises an offer that doesn't appear on the LP, OR LP pushes a different/higher-commitment action

**Routing on FAIL:** `/lp-optimizer message-match`

---

## LP-D15: Keyword-to-LP Relevance
**Severity:** Medium (5 pts) | **Data:** keywords.csv + page-content-extractor output (H1, body text)

**Rule:** Primary keywords from the ad group should appear in the LP headline or body content (exact or close variant). Semantic match is acceptable.

**How to check:**
1. Group keywords by ad group → map to final URL
2. For each ad group's URL: extract the top keywords (by impression share or alphabetical if no metrics)
3. Check if primary keywords appear in:
   - LP H1 (strongest signal)
   - LP sub-headline
   - LP body content
   - LP meta description
4. Accept semantic matches (e.g., keyword "crm software" matching "CRM platform" on LP)
5. Flag ad groups where keywords have zero relevance to their LP content

**Pass/Fail:**
- PASS: Primary keywords appear in LP headline or body (exact or semantic match)
- WARN: Keywords appear only in body text (not headline), or only a weak semantic match
- FAIL: Primary keywords have no relevance to LP content — complete disconnect

**Routing on FAIL:** `/lp-optimizer message-match`

---

## LP-D16: Visual Consistency
**Severity:** High (10 pts) | **Data:** Chrome DevTools screenshot + ad creative context

**Rule:** For Display and Video campaigns, the LP visual style should match the ad creative for recognition continuity.

**How to check:**
1. **First: ASK user** — "Do you run Display or Video campaigns that drive traffic to this LP?"
   - If No: SKIP this diagnostic
   - If Yes: proceed
2. Navigate to LP via Chrome DevTools, take screenshot
3. Check for visual consistency indicators:
   - Color palette match between ad and LP
   - Image/visual style continuity
   - Brand element consistency (logo, fonts)
   - Overall look and feel match
4. This is partially manual — present LP screenshot and findings for human judgment

**Pass/Fail:**
- PASS: Visual style clearly matches (consistent brand elements, colors, imagery style)
- WARN: Partial match — some elements consistent but notable differences
- FAIL: Completely different visual style that would disorient a visitor coming from the ad
- SKIP: No Display/Video campaigns, or user unable to provide ad creative context

**Context notes:**
- This diagnostic is inherently subjective — present evidence and let the user make the final judgment
- For search-only campaigns, this should be SKIP

**Routing on FAIL:** `/lp-optimizer message-match`
