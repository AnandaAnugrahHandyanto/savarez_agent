# Account Auditor — Shared Diagnostic Rules

## Scoring Model

Each diagnostic earns points based on severity. SKIP diagnostics are excluded from the denominator.

| Severity | Points | Criteria |
|----------|--------|----------|
| Critical | 15 | Actively broken or wasting spend (zero impressions, zero conversions on enabled campaigns) |
| High | 10 | Significant structural issue (Display Network ON, brand leaking, targeting overlap) |
| Medium | 5 | Optimization opportunity (naming inconsistency, ad schedule restriction, URL expansion) |
| Low | 3 | Best practice / polish (generic ad group names, ad rotation setting) |

### Grade Thresholds

| Score | Grade |
|-------|-------|
| 90-100% | Excellent |
| 70-89% | Good |
| 50-69% | Needs Attention |
| < 50% | Critical |

Score % = (points earned / points possible) * 100. Exclude SKIP from denominator.

## Diagnostic Result Format

For each check, produce:

```
ID: AUD-DXX
Name: {diagnostic name}
Status: PASS | WARN | FAIL | SKIP
Severity: Critical | High | Medium | Low
Points: {earned} / {possible}
Details: {what was found — list specific campaigns/ad groups/settings}
Recommendation: {if WARN or FAIL, what to fix}
Routing: {specialist skill that handles the fix, if applicable}
```

## Data Sources

### Performance data (from gads-context, use existing unless stale)

| File | Key Columns | Used By |
|------|-------------|---------|
| `campaigns.csv` | `campaign.name`, `campaign.status`, `campaign.advertising_channel_type`, `campaign.bidding_strategy_type`, `campaign_budget.amount`, `metrics.impressions`, `metrics.clicks`, `metrics.conversions`, `metrics.conversions_value`, `metrics.cost` | D01-D08 |
| `adgroups.csv` | `ad_group.name`, `ad_group.status`, `ad_group.type`, `campaign.name`, `campaign.advertising_channel_type`, `metrics.impressions`, `metrics.clicks`, `metrics.conversions` | D20-D23 |
| `keywords-all.csv` | `ad_group.name`, `campaign.name`, `campaign.advertising_channel_type`, `ad_group.status`, `ad_group_criterion.keyword.text`, `ad_group_criterion.keyword.match_type`, `ad_group_criterion.status` | D02, D06, D20, D23 (pulled fresh — includes ALL keywords, not just those with impressions) |
| `ads.csv` | `ad_group.name`, `campaign.name`, `ad_group_ad.status`, `ad_group_ad.ad.responsive_search_ad.headlines` | D21 |

### Settings data (pulled fresh by this skill)

| File | Key Columns | Used By |
|------|-------------|---------|
| `campaigns-settings.csv` | `campaign.name`, `campaign.status`, `campaign.advertising_channel_type`, `campaign.network_settings.target_content_network`, `campaign.network_settings.target_search_network`, `campaign.geo_target_type_setting.positive_geo_target_type`, `campaign.geo_target_type_setting.negative_geo_target_type`, `campaign.ad_serving_optimization_status`, `campaign.tracking_url_template`, `campaign.asset_automation_settings` | D11-D19 |

### Context data

| File | Used By |
|------|---------|
| `business.md` | D02 (brand name), D03 (business goals), D24 (vertical) |

## Module Scoring Summary

| Module | Checks | Max Points |
|--------|--------|------------|
| Structure | D01-D08 | 75 |
| Naming | D09-D10 | 10 |
| Settings | D11-D19 | 65 |
| Ad Groups | D20-D23 | 35 |
| Defaults | D24 | 5 |
| **Total** | **24** | **190** |

## Filter Rules

- Filter to `campaign.status = ENABLED` for all campaign-level checks unless the check explicitly requires reviewing paused campaigns
- Filter to `ad_group.status = ENABLED` for ad group checks
- Cross-reference campaign type (`campaign.advertising_channel_type`) when checks are type-specific
