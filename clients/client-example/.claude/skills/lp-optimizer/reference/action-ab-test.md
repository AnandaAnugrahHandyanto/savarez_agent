# LP Optimizer -- A/B Test Plan (LP-E12)

Used by: `/lp-optimizer ab-test`

## Investigation Steps

### 1. Identify Test Candidates

Read audit findings to find the highest-impact test opportunities:

**Priority order for test elements:**

| Priority | Element | Typical Impact | Best when audit shows |
|----------|---------|---------------|----------------------|
| 1 | Headline / offer | High (2-5x lift potential) | D02 WARN/FAIL, D13 WARN/FAIL |
| 2 | Above-fold layout | High | D03 FAIL, D12 WARN |
| 3 | Form / CTA | Medium-High | D04 WARN/FAIL, D10 FAIL, D21 WARN |
| 4 | Social proof type | Medium | D07 WARN |
| 5 | Page structure | Medium | D12 FAIL |

### 2. Check Test Readiness

Read performance data to verify the page can support a valid test:

| Requirement | Minimum | Source |
|-------------|---------|--------|
| Monthly visitors (clicks) | 1,000+ | ads.csv or device-performance.csv |
| Monthly conversions | 30+ | ads.csv |
| LP Experience | Average or above | Not Below Average |
| No other active tests | Confirmed | ASK user |
| Stable traffic | No major campaign changes planned | ASK user |

**If traffic is too low:**
- Recommend best-judgment changes instead of testing
- Or recommend testing on a higher-traffic page first

### 3. Form Hypothesis

For the selected test element, write a structured hypothesis:

```
If we change [{element}] from [{current state}] to [{proposed variant}],
then [{primary metric}] will [{direction}] by [{estimated %}]
because [{rationale based on audit data or user behavior}].
```

## Test Plan Template

### Test Parameters

| Parameter | Value |
|-----------|-------|
| Page URL | {url} |
| Element tested | {element name} |
| Test type | A/B (two variants) |
| Traffic split | 50/50 |
| Primary metric | Conversion rate |
| Guardrail metrics | Bounce rate (must not increase >5%), CPA (must not increase >10%) |
| Confidence level | 95% |
| Minimum duration | 14 days (2 full weekly cycles) |
| Minimum conversions per variant | 100 (for 95% confidence at 15% MDE) |

### Duration Calculator

```
Monthly conversions on this page: {N}
Daily conversions: N / 30
Daily per variant (50/50 split): daily / 2
Days to 100 per variant: 100 / (daily / 2)
Estimated test duration: MAX(calculated_days, 14)
```

### Variant Design

| Element | Control (A) | Variant (B) |
|---------|-------------|-------------|
| {element} | {current state} | {proposed change} |
| All other elements | Unchanged | Identical to control |

**Design rules:**
- Change ONE element only
- Make the change meaningful (not minor tweaks)
- Keep everything else identical
- Same URL structure where possible

### Success Criteria

| Outcome | Interpretation | Action |
|---------|---------------|--------|
| Variant wins (95% confidence) | Variant is genuinely better | Deploy variant, document learning |
| Control wins (95% confidence) | Original is better | Keep control, form new hypothesis |
| No significance after full duration | Cannot distinguish | Keep control (simpler), test bolder change |
| Variant wins primary but fails guardrail | Trade-off | Evaluate: is CVR lift worth the guardrail decline? |

### Testing Method Recommendations

| Method | Best for | Setup complexity |
|--------|----------|-----------------|
| LP builder A/B test (Unbounce, Instapage) | Dedicated LPs | Low |
| Third-party tool (VWO, Optimizely, Convert) | Website pages | Medium |
| Google Ads campaign experiment | Campaign-level URL split | Medium |
| Manual URL split | When no tools available | High |

### Monitoring Checklist

| Day | Check | Action if issue found |
|-----|-------|----------------------|
| 1 | Both variants receiving traffic | Verify 50/50 split working |
| 2-3 | No technical issues | Fix and restart test clock |
| Weekly | Traffic distribution balanced | Document anomalies |
| End date | Full results ready | Proceed to analysis |

### Early Termination Rules

Only stop early if:
- Variant CVR drops 50%+ AND holds for 7+ days
- Technical failure (broken tracking, page errors)
- External event invalidates test (outage, major promo)

**Never stop early because one variant "looks better" -- random streaks are common in early data.**

## Report Output Structure

```markdown
## A/B Test Plan

### Test Summary
| Element | Value |
|---------|-------|
| Page | {url} |
| Element tested | {element} |
| Hypothesis | {hypothesis statement} |
| Estimated duration | {days} |

### Variant Design
| | Control (A) | Variant (B) |
|--|-------------|-------------|
| {element} | {current} | {proposed} |

### Setup Instructions
{Step-by-step for the recommended testing method}

### Success Criteria
{Primary metric, guardrails, confidence level}

### Monitoring Schedule
{Day-by-day checklist}

### Post-Test Actions
{What to do with each possible outcome}

### Next Test Candidates
{Prioritized list of what to test after this one}
```
