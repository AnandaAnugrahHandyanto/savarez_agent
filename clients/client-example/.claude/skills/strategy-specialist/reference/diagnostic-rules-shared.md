# Diagnostic Rules — Shared (Strategy Specialist)

Read this file first before any module-specific rules.

## Scoring

| Severity | Points | Used when |
|----------|--------|-----------|
| Critical | 15 | Core viability metric missing or failing — blocks profitable advertising |
| High | 10 | Important metric out of range — limits scaling or creates risk |
| Medium | 5 | Supporting metric suboptimal — should be addressed but not blocking |

## Grade Scale

| Score | Grade | Meaning |
|-------|-------|---------|
| 90-100% | Excellent | Business fundamentals fully support profitable advertising |
| 70-89% | Good | Fundamentals mostly sound, minor gaps to address |
| 50-69% | Needs Attention | Significant gaps that limit campaign viability or scaling |
| 0-49% | Critical | Business fundamentals do not support profitable advertising — fix before optimizing campaigns |

## Diagnostic Statuses

| Status | Meaning |
|--------|---------|
| PASS | Metric documented and within healthy thresholds |
| WARN | Metric documented but in warning range — monitor or improve |
| FAIL | Metric missing, below minimum, or fundamentally broken |
| SKIP | Diagnostic not applicable to this vertical (excluded from scoring denominator) |
| ASK | Required data not found in business.md — user input needed to evaluate |

**ASK status flow:**
1. Run all diagnostics with available data
2. Collect all ASK items into a single batch
3. Present the batch to the user as one consolidated question set
4. After user provides answers, re-run affected diagnostics
5. Offer to update business.md with the new data (ask permission)

## Data Sources

The primary data source is `context/business.md`. Key sections:

| Section | Diagnostics |
|---------|-------------|
| Account > Vertical | All (determines which D01-D07 diagnostics run) |
| Account > Last Updated | D09 (staleness) |
| Unit Economics | D01-D08 (vertical-specific formulas and values) |
| Goals & KPIs | D10-D14 (primary KPI, guardrails, targets, alignment) |
| Campaign Priorities | D13 (cross-reference with bid strategies) |

Secondary data:
- `context/google-ads/data/campaigns.csv` — D13 (bid strategy per campaign)
- `context/account-changelog.md` — recent target/budget changes

## Vertical Routing

Each diagnostic in `diagnostic-rules-unit-economics.md` has a `**Vertical:**` field.
If the account's vertical does not match, set status to SKIP.
The scoring denominator excludes SKIP and ASK diagnostics.

| Vertical | Unit Economics Diagnostics | Goals Diagnostics |
|----------|---------------------------|-------------------|
| Ecommerce | D01, D02, D08, D09 | D10-D14 |
| Lead Gen | D03, D04, D08, D09 | D10-D14 |
| SaaS | D05, D06, D07, D08, D09 | D10-D14 |

## Result Format

For each diagnostic, produce:

```
ID: STR-DXX
Name: {diagnostic name}
Status: PASS | WARN | FAIL | SKIP | ASK
Severity: Critical | High | Medium
Points: {earned} / {possible}
Details: {what was found}
Recommendation: {if WARN or FAIL, what to do}
```
