# LP Auditor — URL Health Diagnostics (LP-D32–D37)

Data source: Google Ads data (ads.csv, keywords.csv, assets.csv) + `scripts/url-health-check.js`

**Approach:** Extract ALL unique URLs from ads data first (ad final URLs, keyword-level URLs, sitelink URLs, DSA targets). Run `url-health-check.js` once with the full deduplicated URL list. The script fires parallel HEAD requests with a concurrency limit, follows redirects, and returns status code + full redirect chain for each URL. Chrome DevTools is only used afterward to visually inspect specific broken pages if needed.

---

## LP-D32: HTTP Status Codes
**Severity:** Critical (15 pts) | **Data:** url-health-check.js output (all ad-level final URLs)

**Rule:** All active final URLs must return HTTP 200. Any non-200 status means visitors land on error pages = wasted spend.

**How to check:**
1. Extract all unique final URLs from ads.csv (ENABLED campaigns + ENABLED ads only)
2. Run url-health-check.js against the full list
3. Check HTTP status codes from results
4. Flag: 404 (not found), 500/502/503 (server error), 403 (forbidden), any non-200
5. Report count: healthy (200) vs broken (non-200)

**Pass/Fail:**
- PASS: All URLs return 200
- WARN: 1 URL returns non-200 with low traffic
- FAIL: Any URL returns non-200, especially high-traffic URLs

**Report each broken URL with: status code, campaign(s) using it, estimated traffic impact.**

**Routing on FAIL:** `/lp-optimizer urls`

---

## LP-D33: Redirect Chain Detection
**Severity:** High (10 pts) | **Data:** url-health-check.js output (redirect chains)

**Rule:** URLs with 2+ redirects (301/302 chains) add load time and can lose tracking parameters. Single redirects are acceptable (HTTP→HTTPS, www→non-www).

**How to check:**
1. From url-health-check.js results: extract redirect chain data
2. Flag URLs with 2+ redirects in the chain
3. Report full chain path for each flagged URL (A → B → C → D)
4. Distinguish:
   - Single redirect (HTTP→HTTPS or www normalization) = OK
   - Double redirect (A→B→C) = WARN
   - Triple+ redirect (A→B→C→D+) = FAIL

**Pass/Fail:**
- PASS: No redirect chains (or only single redirects for protocol/www normalization)
- WARN: 1-2 URLs with double redirects
- FAIL: Any URL with 3+ redirects, OR multiple URLs with double redirects

**Routing on FAIL:** `/lp-optimizer urls`

---

## LP-D34: DSA Target URL Health
**Severity:** High (10 pts) | **Data:** ads.csv (DSA campaigns) + url-health-check.js

**Rule:** Dynamic Search Ads auto-select landing pages. If those pages are broken, DSA serves traffic to dead ends.

**How to check:**
1. From ads.csv: identify DSA campaigns (campaign type = SEARCH with DSA ad groups)
2. Extract DSA target URLs (from ad group settings or auto-discovered)
3. If DSA targets exist: include in url-health-check.js batch
4. Check status codes of all DSA target URLs

**Pass/Fail:**
- PASS: All DSA target URLs return 200
- WARN: 1 DSA target URL returns non-200
- FAIL: Multiple DSA target URLs return non-200
- SKIP: No DSA campaigns in the account

**Routing on FAIL:** `/lp-optimizer urls`

---

## LP-D35: Keyword-Level Final URL Health
**Severity:** Medium (5 pts) | **Data:** keywords.csv (keyword-level final URLs) + url-health-check.js

**Rule:** Keywords can have final URLs that override the ad-level URL. These keyword-level URLs must also be healthy.

**How to check:**
1. From keywords.csv: check if any keywords have their own final URL (different from ad-level)
2. If yes: extract those URLs, dedupe
3. Include in url-health-check.js batch
4. Check status codes

**Pass/Fail:**
- PASS: All keyword-level final URLs return 200
- WARN: 1 keyword URL returns non-200
- FAIL: Multiple keyword URLs return non-200
- SKIP: No keyword-level final URLs exist (all use ad-level URLs)

**Routing on FAIL:** `/lp-optimizer urls`

---

## LP-D36: Asset URL Health
**Severity:** Medium (5 pts) | **Data:** assets.csv (sitelink URLs, promotion URLs) + url-health-check.js

**Rule:** Sitelinks, promotions, and other asset-level URLs must be healthy. Broken sitelinks waste valuable ad space.

**How to check:**
1. From assets.csv: extract all sitelink final URLs, promotion URLs, and any other asset-level URLs
2. Dedupe and include in url-health-check.js batch
3. Check status codes

**Pass/Fail:**
- PASS: All asset URLs return 200
- WARN: 1 asset URL returns non-200
- FAIL: Multiple asset URLs return non-200
- SKIP: No asset-level URLs found in data

**Routing on FAIL:** `/lp-optimizer urls`

---

## LP-D37: Final URL Expansion Audit
**Severity:** Critical (13 pts) | **Data:** ads.csv (campaign settings), Chrome DevTools (if needed for page check)

**Rule:** For PMax and Search campaigns with URL expansion enabled, Google may send traffic to auto-discovered URLs that are irrelevant or low-converting. This leaks budget to pages never intended for paid traffic.

**How to check:**
1. From ads.csv/campaign settings: identify campaigns with URL expansion enabled
2. If URL expansion data is available: review auto-generated URLs for relevance
3. Check: are expanded URLs conversion-focused pages or are they blog posts, support articles, etc.?
4. Flag irrelevant expanded URLs that receive significant traffic
5. If expansion data is not available via API: note the limitation and recommend manual review in Google Ads UI

**Pass/Fail:**
- PASS: URL expansion disabled, OR expanded URLs are all relevant conversion pages
- WARN: URL expansion enabled but cannot verify expanded URL quality (data limitation)
- FAIL: URL expansion sending traffic to clearly irrelevant pages (blog, support, about, etc.)
- SKIP: No PMax or Search campaigns, or URL expansion not applicable

**Context notes:**
- URL expansion is enabled by default in Search and PMax campaigns
- Many advertisers don't realize it's on — flagging this awareness is valuable even as WARN
- Recommend exclusion lists for non-conversion pages if expansion is enabled

**Routing on FAIL:** Campaign settings fix + `/lp-optimizer urls`
