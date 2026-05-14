# LP Optimizer -- Message Match Fix (LP-E09)

Used by: `/lp-optimizer message-match`

## Investigation Steps

### 1. Gather Ad Copy Data

Read `context/google-ads/data/ads.csv`:
- Extract all RSA headlines and descriptions per ad group
- Group by final URL
- Identify top-performing ads by impressions/clicks

Read `context/google-ads/data/keywords.csv`:
- Extract keywords per ad group
- Identify top keywords by spend and conversions

### 2. Extract LP Content

For each unique final URL, use Chrome DevTools:
- Extract H1 headline text
- Extract sub-headline text
- Extract hero section content (first visible section)
- Extract offer/pricing section content
- Extract all CTA button text
- Take above-fold screenshot

If `scripts/page-content-extractor.js` output exists (from audit), use that instead:
- Read `context/analysis/lp-audit-page-content.json`

### 3. Perform Match Analysis

For each ad group --> final URL pair, compare:

| Element | Ad Side | LP Side | Match Types |
|---------|---------|---------|-------------|
| **Headline** | RSA headline assets | H1 + sub-headline | Direct / Close / Mismatch |
| **Offer** | Description line offer mentions | Offer section content | Present / Partial / Missing |
| **CTA** | Description CTA text | Button text | Aligned / Different |
| **Keywords** | Ad group keywords | H1 + body text | Present / Variant / Absent |
| **Tone** | Ad voice and style | LP voice and style | Consistent / Jarring |

**Match scoring:**
- Direct match: Same words/phrasing (PASS)
- Close match: Same meaning, different wording (WARN)
- Mismatch: Different promise or missing element (FAIL)

### 4. Identify Critical Mismatches

Flag the highest-impact mismatches:
1. Ad promises a specific offer --> LP doesn't mention it
2. Ad headline mentions a benefit --> LP H1 talks about something else
3. Top keyword by spend --> not reflected anywhere on the LP
4. Ad CTA says "Get Free Quote" --> LP button says "Contact Us"

## Fix Approaches

### Option A: Align LP to Ads (Easier, for fewer ad groups)

For each mismatch, rewrite the LP element to match the ad promise:

| Element | Current LP | Recommended LP | Reason |
|---------|-----------|---------------|--------|
| H1 | "{current}" | "{recommended}" | Matches top RSA headline |
| Sub-headline | "{current}" | "{recommended}" | Adds specificity from ad description |
| CTA | "{current}" | "{recommended}" | Matches ad CTA language |
| Offer mention | Missing | Add "{offer text}" | Ad promises this offer |

### Option B: Align Ads to LP (When LP is strong but ads diverge)

Sometimes the LP is well-optimized but the ads have drifted. In this case:
- Recommend new RSA headline assets that match the LP
- Bridge to `/rsa-maker` for new ad copy generation
- Flag ad groups where copy diverges from LP messaging

### Option C: Dynamic Text Replacement (Advanced, for many keyword themes)

When there are many keyword themes pointing to one LP:
- Recommend DTR implementation
- Explain how URL parameters work: `?keyword={keyword}`
- LP headline dynamically matches the search query
- Most LP builders (Unbounce, Instapage, Leadpages) have built-in DTR

### Keyword Relevance Fixes

For keyword-to-LP relevance issues:
1. Group keywords by semantic theme
2. Check if each theme is represented on the LP
3. If a keyword theme has no LP relevance:
   - Option A: Add content section addressing that theme
   - Option B: Create a separate LP for that keyword group
   - Option C: Reroute keywords to a more relevant existing LP

## Side-by-Side Comparison Template

Present findings as a visual comparison:

```markdown
### Ad Group: {name}
**Keywords:** {top 3 keywords by spend}

| Element | Ad Copy | Landing Page | Match |
|---------|---------|-------------|-------|
| Headline | "{RSA headline}" | "{LP H1}" | MISMATCH |
| Offer | "{ad offer mention}" | "{LP offer section}" | PARTIAL |
| CTA | "{ad CTA}" | "{LP button}" | MATCH |

**Impact:** {ad group spend} monthly spend with {x} clicks to a mismatched LP
**Recommendation:** {specific fix}
```

## Report Output Structure

```markdown
## Message Match Analysis

### Summary
- Ad groups analyzed: {n}
- Unique final URLs: {n}
- Direct matches: {n} | Close matches: {n} | Mismatches: {n}

### Mismatch Details
{Side-by-side comparison for each mismatched ad group}

### Fix Recommendations
{Option A/B/C fixes with specific copy suggestions}

### Revenue at Risk
{Monthly spend going to mismatched LPs}

### Implementation Priority
1. {Highest-spend mismatch fix}
2. {Next highest}
...
```
