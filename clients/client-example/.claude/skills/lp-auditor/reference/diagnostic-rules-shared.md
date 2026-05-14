# LP Auditor — Shared Diagnostic Rules

## Scoring Model

Each diagnostic earns points based on severity. SKIP diagnostics are excluded from the denominator.

| Severity | Points | Criteria |
|----------|--------|----------|
| Critical | 15 | Actively broken: page down, form non-functional, zero conversions on active LP |
| High | 10 | Significant conversion leak: missing hero CTA, message mismatch, slow load, broken URLs |
| Medium | 5 | Optimization opportunity: weak social proof, missing guarantee, redirect chains |
| Low | 3 | Best practice / polish: generic CTA text, missing microcopy, minor image optimization |

### Grade Thresholds

| Score | Grade | Verdict |
|-------|-------|---------|
| 90-100% | Excellent | Maintain & monitor |
| 70-89% | Good | Minor optimizations needed |
| 50-69% | Needs Attention | Targeted fixes required |
| < 50% | Critical | Significant rework or rebuild needed |

Score % = (points earned / points possible) × 100. Exclude SKIP from denominator.

## Module Weights

### Lead Gen / SaaS (ecommerce module excluded)

| Module | Weight |
|--------|--------|
| Structural (D01-D12) | 35% |
| Message Match (D13-D16) | 20% |
| Technical (D17-D24) | 20% |
| Performance (D25-D31) | 15% |
| URL Health (D32-D37) | 10% |
| **Total** | **100%** |

### Ecommerce (all modules included)

| Module | Weight |
|--------|--------|
| Structural (D01-D12) | 30% |
| Message Match (D13-D16) | 20% |
| Technical (D17-D24) | 20% |
| Performance (D25-D31) | 15% |
| URL Health (D32-D37) | 10% |
| Ecommerce (D38-D40) | 5% |
| **Total** | **100%** |

## Diagnostic Result Format

For each check, produce:

```
ID: LP-DXX
Name: {diagnostic name}
Status: PASS | WARN | FAIL | SKIP
Severity: Critical | High | Medium | Low
Points: {earned} / {possible}
Details: {what was found — specific elements, URLs, screenshots}
Recommendation: {if WARN or FAIL, what to fix}
Routing: {skill that handles the fix}
```

## Module Scoring Summary

| Module | Checks | Max Points |
|--------|--------|------------|
| Structural | D01-D12 | 90 |
| Message Match | D13-D16 | 35 |
| Technical | D17-D24 | 66 |
| Performance | D25-D31 | 43 |
| URL Health | D32-D37 | 58 |
| Ecommerce | D38-D40 | 25 |
| **Total** | **40** | **317** |

## Data Sources

### Google Ads data (from gads-context, use existing unless stale)

| File | Key Columns | Used By |
|------|-------------|---------|
| `ads.csv` | `ad_group_ad.ad.responsive_search_ad.headlines`, `ad_group_ad.ad.responsive_search_ad.descriptions`, `ad_group_ad.ad.final_urls`, `campaign.name`, `ad_group.name` | D13-D16, D25, D29, D31, D32-D37 |
| `keywords.csv` | `ad_group_criterion.keyword.text`, `ad_group_criterion.keyword.match_type`, `campaign.name`, `ad_group.name` | D15, D31 |
| `device-performance.csv` | `segments.device`, `metrics.conversions`, `metrics.clicks`, `metrics.cost` | D20, D30 |
| `assets.csv` | `asset.final_urls`, `asset.type` | D36 |

### Script outputs

| Script | Output | Used By |
|--------|--------|---------|
| `page-content-extractor.js` | JSON: `{url, h1, subHeadline, heroText, offerSection, ctaTexts, metaDescription}` per URL | D13-D16 |
| `url-health-check.js` | JSON: `{url, statusCode, redirectChain, finalUrl, responseTime}` per URL | D32-D37 |

### Chrome DevTools

| Action | Data | Used By |
|--------|------|---------|
| Navigate + screenshot | Full-page visual | D01-D12, D38-D40 |
| Evaluate DOM | Headings, sections, CTAs, forms, images, links | D01-D12, D19, D21, D38-D40 |
| Lighthouse audit | Performance score, LCP, INP, CLS, load time | D17-D18 |
| Mobile emulation (375px) | Mobile rendering | D19 |
| Network monitoring | Request sizes, image formats | D24 |

## Filter Rules

- Only audit URLs from ENABLED campaigns and ENABLED ads
- For performance data: use the reporting period from ads.csv (typically 30 days)
- For structural checks: evaluate the current live page state
- Ecommerce module: only run when vertical = ecommerce (from business.md)
