# Placement Auditor — Shared Diagnostic Rules

## Scoring Model

Each diagnostic earns points based on severity. SKIP diagnostics are excluded from the denominator.

| Severity | Points | Criteria |
|----------|--------|----------|
| Critical | 15 | Immediate action needed (kids content, brand-unsafe) |
| High | 10 | Significant waste or coverage gap |
| Medium | 5 | Optimization opportunity |
| Low | 3 | Minor hygiene issue |

### Grade Thresholds

| Score | Grade |
|-------|-------|
| 90-100% | Excellent |
| 70-89% | Good |
| 50-69% | Needs Attention |
| < 50% | Critical |

Score % = (points earned / points possible) * 100. Exclude SKIP from denominator.

## Module Scoring Summary

| Module | Checks | Max Deduction |
|--------|--------|---------------|
| Performance & App Audit (PL-D01–D04) | 4 | 35 pts |
| Brand Safety & Coverage (PL-D05–D07) | 3 | 20 pts |
| Hygiene & Monitoring (PL-D08–D10) | 3 | 21 pts |
| **Total** | **10** | **76** |

## Diagnostic Result Format

For each check, produce:

```
ID: PL-DXX
Name: {diagnostic name}
Status: PASS | WARN | FAIL | SKIP
Severity: Critical | High | Medium | Low
Points: {earned} / {possible}
Details: {what was found — list specifics}
Recommendation: {if WARN or FAIL, what to fix}
Routing: {optimizer command that handles the fix}
```

## Standard Post-Query Filters

Apply these filters AFTER data is pulled (cannot use in GAQL WHERE for placement views):

- Exclude `campaign.experiment_type = EXPERIMENT`
- Exclude `campaign.serving_status = ENDED`
- Filter to relevant `campaign.advertising_channel_type` per diagnostic

## Data Source Reference

### Script outputs (pre-processed — Claude reads these, NOT raw CSVs)

| File | Produced by | Used by |
|------|-------------|---------|
| `context/google-ads/data/placement-flags.csv` | `analyze-placement-performance.js` | PL-D02, PL-D03, PL-D04, PL-D07, PL-D08 |
| `context/google-ads/data/placement-flags-summary.json` | `analyze-placement-performance.js` | All (summary stats) |
| `context/google-ads/data/placement-content-flags.csv` | `placement-content-reviewer` sub-agent | PL-D03, PL-D04, PL-D07, PL-D10 |
| `context/google-ads/data/exclusion-coverage.json` | `analyze-exclusion-coverage.js` | PL-D01, PL-D05, PL-D09 |

### Small CSVs (Claude reads directly — low row count)

| File | Used by |
|------|---------|
| `context/google-ads/data/campaign-brand-safety.csv` | PL-D06 |
| `context/google-ads/data/account-exclusions-labels.csv` | PL-D06 |
| `context/google-ads/data/content-suitability-placements.csv` | Deprecated — no classification fields in API. PL-D07 uses pmax-placements.csv, PL-D10 uses placements-for-review.csv |

### Existing data (reuse if <3 days old)

| File | Used by |
|------|---------|
| `context/google-ads/data/campaigns.csv` | Campaign types, bid strategies |
| `context/business.md` | Vertical, brand sensitivity |

## Google-Owned Placements

These are flagged as `GOOGLE_OWNED` (INFO) but NEVER recommended for exclusion:
- `mail.google.com`, `discover.google.com`, `news.google.com`
- `youtube.com` (homepage), `googleapis.com`, `googleusercontent.com`

Report them in the spot-check section for user awareness only.
