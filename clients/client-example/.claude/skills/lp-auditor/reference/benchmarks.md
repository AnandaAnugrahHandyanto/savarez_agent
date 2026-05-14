# LP Auditor — Industry Benchmarks

Reference data for LP-D25 (CVR vs benchmark) and LP-D29 (CPA comparison).

These are approximate industry averages. Use as directional guidance, not absolute targets. Account-level averages should always take priority over industry benchmarks.

## Conversion Rate Benchmarks by Vertical

| Vertical | Search CVR (avg) | Search CVR (good) | Display CVR (avg) |
|----------|-----------------|-------------------|-------------------|
| Lead Gen (B2B) | 3-5% | 7%+ | 0.5-1% |
| Lead Gen (B2C) | 5-8% | 10%+ | 1-2% |
| SaaS (free trial) | 3-7% | 10%+ | 0.5-1.5% |
| SaaS (demo request) | 2-4% | 6%+ | 0.3-0.8% |
| Ecommerce (general) | 2-4% | 5%+ | 0.5-1.5% |
| Ecommerce (luxury) | 1-2% | 3%+ | 0.3-0.7% |
| Education | 4-7% | 10%+ | 1-2% |
| Healthcare | 3-5% | 7%+ | 0.5-1% |
| Legal | 3-6% | 8%+ | 0.5-1% |
| Real Estate | 2-4% | 6%+ | 0.3-0.8% |
| Finance | 4-7% | 10%+ | 0.5-1.5% |

## CVR Evaluation Thresholds

For LP-D25 scoring, use these relative thresholds:

| Compared to account avg | Verdict |
|-------------------------|---------|
| ≥100% of account avg | PASS |
| 50-99% of account avg | WARN |
| <50% of account avg | FAIL |

## CPA Evaluation Thresholds

For LP-D29 scoring:

| Compared to account avg CPA | Verdict |
|------------------------------|---------|
| ≤100% of account avg | PASS |
| 100-150% of account avg | WARN |
| >150% of account avg | FAIL |

## Mobile vs Desktop CVR Gap

For LP-D20 and LP-D30:

| Mobile CVR as % of desktop | Verdict |
|----------------------------|---------|
| ≥60% | PASS (normal gap) |
| 40-59% | WARN (notable gap) |
| <40% | FAIL (severe gap, likely UX issue) |

## Page Speed Benchmarks

For LP-D17:

| Load time | Performance score | Verdict |
|-----------|------------------|---------|
| <3s | ≥90 | PASS |
| 3-5s | 50-89 | WARN |
| >5s | <50 | FAIL |

## Core Web Vitals Thresholds

For LP-D18 (per Google's published thresholds):

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| LCP | <2.5s | 2.5-4s | >4s |
| INP | <200ms | 200-500ms | >500ms |
| CLS | <0.1 | 0.1-0.25 | >0.25 |

## Notes

- These benchmarks are updated periodically based on industry reports (WordStream, Unbounce, Google)
- Always prioritize account-level averages over industry benchmarks
- Brand campaigns typically have 2-3x the CVR of non-brand — compare like-for-like
- New LPs need minimum 50 clicks and 7 days of data before CVR comparisons are meaningful
