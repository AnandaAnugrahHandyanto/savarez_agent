# Geo-Schedule Auditor — Shared Diagnostic Rules

## Scoring Model

Each diagnostic earns points based on severity. SKIP diagnostics are excluded from the denominator.

| Severity | Points | Criteria |
|----------|--------|----------|
| Critical | 15 | Immediate action needed, blocking revenue |
| High | 10 | Significant waste or missed opportunity |
| Medium | 5 | Optimization opportunity, schedule for next cycle |
| Low | 3 | Minor hygiene issue, low urgency |

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
ID: GS-DXX
Name: {diagnostic name}
Status: PASS | WARN | FAIL | SKIP
Severity: Critical | High | Medium | Low
Points: {earned} / {possible}
Details: {what was found — list specific campaigns/locations/time slots}
Recommendation: {if WARN or FAIL, what to fix}
Routing: {optimizer command that handles the fix}
```

## Module Scoring Summary

| Module | Checks | Max Points |
|--------|--------|------------|
| Geographic | GS-D01 to GS-D05 | 35 |
| Schedule & Device | GS-D06 to GS-D09 | 28 |
| Demographics & Advanced | GS-D10 to GS-D14 | 28 |
| **Total** | **14** | **91** |

## Data Sources

### Existing data (from gads-context, reuse if fresh)

| File | Key Columns | Used By | Max Age |
|------|-------------|---------|---------|
| `geo-user-location.csv` | `campaign.name`, `geographic_view.country_criterion_id`, `geographic_view.location_type`, `metrics.clicks`, `metrics.conversions`, `metrics.cost_micros`, `metrics.cost_per_conversion` | D02, D03, D04, D05, D14 | 3 days |
| `device-performance.csv` | `campaign.name`, `segments.device`, `metrics.clicks`, `metrics.conversions`, `metrics.cost_micros`, `metrics.cost_per_conversion` | D06 | 3 days |
| `campaigns.csv` | `campaign.name`, `campaign.bidding_strategy_type`, `metrics.conversions`, `metrics.cost_micros` | D02-D14 (avg CPA calc) | 3 days |
| `campaigns-settings.csv` | `campaign.name`, `campaign.geo_target_type_setting.positive_geo_target_type` | D01 | 7 days |

### Fresh data (pulled by this skill each run)

| File | GAQL Source | Key Columns | Used By |
|------|------------|-------------|---------|
| `campaign-criteria.csv` | `campaign-criteria.gaql` | `campaign_criterion.type`, `campaign_criterion.bid_modifier`, `campaign_criterion.location.geo_target_constant`, `campaign_criterion.ad_schedule.*`, `campaign_criterion.device.type`, `campaign_criterion.negative`, `campaign_criterion.resource_name` | D05, D09, D11 |
| `schedule-performance.csv` | `schedule-performance.gaql` | `campaign.name`, `segments.hour`, `segments.day_of_week`, `metrics.clicks`, `metrics.conversions`, `metrics.cost_micros` | D07, D08 |
| `demographics-age.csv` | `demographics.gaql` (age_range_view) | `campaign.name`, `ad_group_criterion.age_range.type`, `metrics.clicks`, `metrics.conversions`, `metrics.cost_micros` | D10, D13 |
| `demographics-gender.csv` | `demographics-gender.gaql` (gender_view) | `campaign.name`, `ad_group_criterion.gender.type`, `metrics.clicks`, `metrics.conversions`, `metrics.cost_micros` | D10, D13 |
| `demographics-income.csv` | `demographics-income.gaql` (income_range_view) | `campaign.name`, `ad_group_criterion.income_range.type`, `metrics.clicks`, `metrics.conversions`, `metrics.cost_micros` | D10, D13 |

### Script-generated data

| File | Script | Used By |
|------|--------|---------|
| `geo-seasonal-comparison.csv` | `analyze-geo-seasonal.js` | D12 |
| `schedule-consistency.csv` | `analyze-schedule-consistency.js` | D08 |

### Context data

| File | Used By |
|------|---------|
| `business.md` | D01 (vertical for targeting method exemption), D03 (target CPA/ROAS) |

## Data Sufficiency Gates

Each check has a minimum data requirement. If unmet, the check is **SKIPped** (not FAILed).

| Check | Minimum Data | SKIP Reason |
|-------|-------------|-------------|
| GS-D01 | Any active campaign | Always runs (setting check) |
| GS-D02 | 50+ clicks per location | "Insufficient location data — need 50+ clicks per location" |
| GS-D03 | 50+ clicks per location + target CPA known | "Need target CPA from business.md or strategy-specialist" |
| GS-D04 | 50+ clicks per location + IS data available | "IS data not available for this location granularity" |
| GS-D05 | Campaign criteria data pulled | Always runs |
| GS-D06 | 100+ clicks per device type | "Insufficient device data — need 100+ clicks per device" |
| GS-D07 | 50+ clicks per time slot (or grouped block) | "Insufficient schedule data — group into broader time blocks" |
| GS-D08 | 4+ weeks of data | "Need 4+ weeks to confirm patterns" |
| GS-D09 | 2+ active modifier types on a campaign | "No modifier stacking detected" |
| GS-D10 | 100+ clicks per demographic segment | "Insufficient demographic data" |
| GS-D11 | Any Smart Bidding campaign with modifiers | Always runs |
| GS-D12 | 12+ months of account data | "Insufficient historical data for YoY comparison" |
| GS-D13 | 60+ days of data, 100+ clicks per segment | "Need 60+ days to confirm sustained poor performance" |
| GS-D14 | Same as GS-D04 | Same as GS-D04 |

## Filter Rules

- Filter to `campaign.status = ENABLED` for all checks unless noted otherwise
- Exclude experiment campaigns (`campaign.experiment_type = EXPERIMENT`) — only audit base/non-experiment campaigns
- Use account-level average CPA/ROAS as the baseline for variance calculations
- Calculate average CPA: total cost / total conversions across all enabled campaigns
- For ROAS-based accounts: use conversions_value / cost as the baseline
- Determine CPA vs ROAS mode from `business.md` goals or `campaign.bidding_strategy_type`

## Enum Fields Requiring Mapping

When pulling data via `query.js`, these GAQL fields need `enumFieldMap` entries:

| GAQL Field | Enum Type |
|------------|-----------|
| `campaign_criterion.type` | CriterionType |
| `campaign_criterion.status` | CampaignCriterionStatus |
| `campaign_criterion.ad_schedule.day_of_week` | DayOfWeek |
| `campaign_criterion.ad_schedule.start_minute` | MinuteOfHour |
| `campaign_criterion.ad_schedule.end_minute` | MinuteOfHour |
| `campaign_criterion.device.type` | Device |
| `campaign_criterion.age_range.type` | AgeRangeType |
| `campaign_criterion.gender.type` | GenderType |
| `campaign_criterion.income_range.type` | IncomeRangeType |
| `segments.day_of_week` | DayOfWeek |
| `ad_group_criterion.age_range.type` | AgeRangeType |
| `ad_group_criterion.gender.type` | GenderType |
| `ad_group_criterion.income_range.type` | IncomeRangeType |
| `ad_group_criterion.parental_status.type` | ParentalStatusType |

**Note:** `campaign.geo_target_type_setting.positive_geo_target_type` and `segments.device` are already mapped in `query.js`. No new entries needed for those.
