# Viability Thresholds

Used by D08 (Viability Verdict) and as context for all unit economics diagnostics.

## The Business Bucket

Unit economics sit in the **Business** constraint bucket — the second tier in the five-bucket hierarchy (Measurement > Business > Conversion > Traffic > Creative). If unit economics are broken, scaling Traffic or optimizing Creative is wasted effort. The hierarchy rule: you do not seriously optimize a lower bucket while an upper bucket is broken.

> If unit economics are broken, scaling campaigns just scales losses. Fix the source before touching Google Ads.

## Go / Conditional Go / No-Go Thresholds

### Ecommerce

| Check | Go | Conditional Go | No-Go |
|-------|-----|----------------|-------|
| Gross margin % | >= 30% | 20-29% | < 20% |
| Break-even ROAS | <= 333% | 334-500% | > 500% |
| AOV vs margin | AOV supports profitable CPCs | Tight but workable | AOV < €20 with margin < 20% |
| Return rate | < 20% | 20-30% | > 30% (erodes margins) |

### Lead Gen

| Check | Go | Conditional Go | No-Go |
|-------|-----|----------------|-------|
| Lead-to-sale rate | >= 15% | 10-14% | < 10% |
| Deal value vs CPL ceiling | CPL ceiling > €50 | CPL ceiling €30-50 | CPL ceiling < €30 |
| Sales team response | < 2 hours | 2-24 hours | > 24 hours |
| Sales process | Documented, CRM in use | Informal but exists | No process, no CRM |

### SaaS

| Check | Go | Conditional Go | No-Go |
|-------|-----|----------------|-------|
| LTV:CAC ratio | >= 3:1 | 2:1 - 3:1 | < 2:1 |
| Monthly churn | < 5% | 5-8% | > 8% |
| ARPU vs max CAC | Max CAC > €100 | Max CAC €50-100 | ARPU < €20/mo with high churn |
| Free-to-paid rate | > 5% | 2-5% | < 2% |
| CAC payback | < 12 months | 12-18 months | > 18 months |

## D08 Viability Verdict Logic

D08 aggregates the results of the vertical-specific diagnostics:

**Ecommerce:** Aggregate D01 + D02
**Lead Gen:** Aggregate D03 + D04
**SaaS:** Aggregate D05 + D06 + D07

| Verdict | Condition |
|---------|-----------|
| **Go** | All active vertical diagnostics PASS |
| **Conditional Go** | At least one WARN, no FAILs — viable with known risks |
| **No-Go** | Any FAIL on a Critical diagnostic — advertising may not be viable |

When rendering the verdict, always include:
- The specific metrics that drove the verdict
- The risk factors (what could make Conditional Go become No-Go)
- What the client needs to change for the verdict to improve

## Warning Signs

These symptoms look like Google Ads problems but are actually unit economics problems:

| Symptom | Actual Root Cause |
|---------|-------------------|
| Can't bid competitively | Target CPA/ROAS too restrictive due to poor margins |
| Stuck in bottom-of-funnel only | Unit economics don't support upper funnel CPAs |
| Over-optimizing for efficiency | No budget room for growth due to thin margins |
| Forced to target only exact-match | Target CPA ceiling too low for broad match CPCs |
| Client says "Google Ads doesn't work" | Margins or sales process can't support paid acquisition |
| Campaigns stall after initial success | Brand traffic masked poor unit economics |

## Root Causes by Vertical

### Ecommerce
| Root Cause | Fix |
|-----------|-----|
| Low gross margins | Renegotiate supplier costs, adjust pricing, reduce shipping costs |
| Low AOV | Product bundles, upsells, free shipping thresholds |
| High return rate | Better product descriptions, sizing guides, quality control |

### Lead Gen
| Root Cause | Fix |
|-----------|-----|
| Poor lead-to-sale rate | Sales training, faster follow-up, lead scoring |
| Low deal value | Focus on higher-value services, create bundles |
| Long sales cycles | Urgency offers, improve proposal process |

### SaaS
| Root Cause | Fix |
|-----------|-----|
| Low ARPU | Move upmarket, adjust pricing, add premium features |
| High churn | Improve onboarding, increase stickiness, customer success |
| High CAC | Optimize conversion funnel, reduce CPC, focus high-intent channels |
