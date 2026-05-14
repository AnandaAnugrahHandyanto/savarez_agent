# LP Optimizer -- Performance Monitoring Setup (LP-E13)

Used by: `/lp-optimizer monitor`

## Purpose

Sets up a recurring LP performance monitoring system. This action produces a monitoring checklist with metrics, thresholds, cadences, and alerting recommendations.

## Investigation Steps

### 1. Inventory Active Landing Pages

From `context/google-ads/data/ads.csv`:
- Extract all unique final URLs from enabled ads in enabled campaigns
- Classify each by traffic level:
  - High traffic: 500+ clicks/month
  - Standard traffic: 100-500 clicks/month
  - Low traffic: < 100 clicks/month

### 2. Set Monitoring Thresholds

Use account-specific data to set meaningful thresholds (not generic benchmarks):

| Metric | How to calculate threshold | Default if no data |
|--------|---------------------------|-------------------|
| CVR floor | 50% of account average CVR for that campaign type | 1.0% |
| CVR decline trigger | 3 consecutive review periods with declining CVR | N/A |
| Bounce rate ceiling | 70% for lead gen/SaaS, 50% for dedicated LP | 70% |
| Mobile PageSpeed floor | Below 50 | 50 |
| Desktop PageSpeed floor | Below 70 | 70 |
| Mobile LCP ceiling | Above 4 seconds | 4s |
| CLS ceiling | Above 0.25 | 0.25 |
| Mobile CVR gap | Mobile CVR < 40% of desktop | 40% |
| CPA ceiling | 150% of account average CPA | varies |

### 3. Define Monitoring Cadence

| Traffic level | Review cadence | Rationale |
|--------------|----------------|-----------|
| High traffic (500+ clicks/wk) | Bi-weekly | Enough data for signal |
| Standard (100-500 clicks/wk) | Monthly | Need 2-4 weeks for reliable trends |
| Low traffic (< 100 clicks/wk) | Quarterly | Insufficient weekly data |

### 4. Set Up Google Ads Custom Columns (if applicable)

Recommend creating these custom columns for the Landing Pages report:

| Column Name | Formula | Purpose |
|-------------|---------|---------|
| LP CVR | Conversions / Clicks | Per-LP conversion rate |
| LP CPA | Cost / Conversions | Per-LP cost per acquisition |
| Mobile CVR Gap | (Mobile CVR / Desktop CVR) * 100 | Mobile performance relative to desktop |

### 5. Set Up Automated Rules (if applicable)

Recommend Google Ads automated rules for critical thresholds:

| Rule | Trigger | Action | Frequency |
|------|---------|--------|-----------|
| LP CVR alert | Any LP CVR drops below {threshold} for 14+ days | Email notification | Weekly |
| High-spend low-CVR | LP spend > ${X} AND CVR < {threshold} | Email notification | Weekly |

## Monitoring Review Template

Produce a reusable review template:

```markdown
# LP Performance Review — {Date}

## Account: {name}
## Period: {start} - {end}
## Review type: {Bi-weekly / Monthly / Quarterly}

### Page-Level Performance

| URL | Clicks | Conv | CVR | CPA | Mobile CVR | Speed (M) | Status |
|-----|--------|------|-----|-----|-----------|-----------|--------|

### Flagged Pages

| URL | Issue | Severity | Diagnosis | Action |
|-----|-------|----------|-----------|--------|

### Trend Tracking

| URL | Period 1 CVR | Period 2 CVR | Period 3 CVR | Trend |
|-----|-------------|-------------|-------------|-------|

### Actions from Previous Review

| Action | Status | Notes |
|--------|--------|-------|

### Next Review Date: {date}
```

## Report Output Structure

```markdown
## LP Performance Monitoring Setup

### Active Landing Pages
| URL | Traffic Level | Review Cadence |
|-----|-------------|---------------|

### Monitoring Thresholds
| Metric | Threshold | Source |
|--------|-----------|--------|

### Review Calendar
| Cadence | Pages Covered | Next Review Date |
|---------|--------------|-----------------|

### Custom Columns (Google Ads)
{Recommended custom column configurations}

### Automated Rules (Google Ads)
{Recommended automated rule configurations}

### Review Template
{Reusable template for each monitoring review}

### Routing Guide
| Issue Found | Route To |
|-------------|----------|
| CVR problem | /lp-optimizer audit |
| Speed problem | /lp-optimizer speed |
| Mobile problem | /lp-optimizer mobile |
| Message match | /lp-optimizer message-match |
| Declining trend, no clear cause | /lp-optimizer ab-test |
| Multiple severe issues | /landing-page-builder (rebuild) |
```
