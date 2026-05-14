# KPI Framework

Agent-readable reference for KPI tiers, definitions, and benchmarks. Used by D10-D14 diagnostics.

## The Goal Setting Pyramid

```
         ┌─────────────────┐
         │ 1. Business Goals│
         └────────┬────────┘
                  ↓
       ┌──────────────────────┐
       │ 2. Google Ads Goals   │
       └──────────┬───────────┘
                  ↓
    ┌──────────────────────────────┐
    │ 3. Campaign Type Selection    │
    └──────────────┬───────────────┘
                   ↓
  ┌─────────────────────────────────────┐
  │ 4. KPI Selection (Primary/Secondary) │
  └──────────────────┬──────────────────┘
                     ↓
┌─────────────────────────────────────────────┐
│ 5. Execute + Feedback Loop                   │
└─────────────────────────────────────────────┘
```

Each step depends on the one above. Skip a step and everything below becomes unreliable.

## KPI Tiers by Goal Type

### Growth-Focused Primary Goal

| Tier | KPIs | Purpose |
|------|------|---------|
| **Primary** | Conversions, Conversion value, Revenue | Measure growth progress |
| **Secondary (guardrails)** | Minimum ROAS, Maximum CPA, Minimum profit margin | Prevent efficiency collapse |
| **Diagnostic** | Impressions, CTR, CPC, Conversion rate, AOV, IS, QS | Identify drivers and issues |

### Efficiency-Focused Primary Goal

| Tier | KPIs | Purpose |
|------|------|---------|
| **Primary** | CPA, ROAS, Cost per qualified lead, POAS | Measure efficiency progress |
| **Secondary (guardrails)** | Minimum conversion volume, Minimum conversion value, Minimum IS | Prevent volume collapse |
| **Diagnostic** | Impressions, CTR, CPC, Conversion rate, AOV, IS, QS | Identify drivers and issues |

> Every account needs both growth and efficiency KPIs. One is primary (your goal), the other is guardrails (your safety net).

## SMART Goal Requirements

| Element | Requirement | Example |
|---------|-------------|---------|
| **Specific** | Focused on one outcome | "Increase online purchases" |
| **Measurable** | Has a quantifiable target | "by 25%" |
| **Achievable** | Grounded in reality and data | Based on historical performance |
| **Relevant** | Aligned with business strategy | Supports revenue targets |
| **Time-bound** | Has a deadline | "in Q4 2026" |

## Growth vs Efficiency Goals

| | Growth Goals | Efficiency Goals |
|--|-------------|------------------|
| **Objective** | Scale: more reach, customers, revenue | Optimize: better margins, lower costs |
| **Focus** | Market share, customer base | Cost-effectiveness, profitability |
| **Resource** | Expansion and testing | Optimization and refinement |

> You cannot maximize growth and efficiency simultaneously. Set one as primary. Use the other as guardrails.

## Tier 1: Primary KPIs

| KPI | Use When | Vertical |
|-----|----------|----------|
| **Conversions** | Growth: track volume of actions | Lead Gen (leads), SaaS (trials) |
| **Conversion value** | Growth: track revenue | Ecommerce, Lead Gen (pipeline) |
| **CPA** | Efficiency: minimize acquisition cost | Lead Gen, SaaS |
| **ROAS** | Efficiency: maximize return | Ecommerce |
| **POAS** | Efficiency: maximize profitability | Ecommerce (with profit tracking) |
| **Cost per qualified lead** | Efficiency: true acquisition cost | Lead Gen (with OCT) |

## Tier 2: Guardrail KPIs

### For Growth-Focused Accounts

| Guardrail | Prevents | How to Set |
|-----------|----------|------------|
| Minimum ROAS | Unprofitable scaling | At or above break-even ROAS |
| Maximum CPA | Overpaying for conversions | At or below break-even CPA |
| Minimum profit margin | Margin erosion | Minimum acceptable contribution margin |

### For Efficiency-Focused Accounts

| Guardrail | Prevents | How to Set |
|-----------|----------|------------|
| Minimum conversion volume | Campaigns drying out | 30+ conversions/month for Smart Bidding |
| Minimum conversion value | Revenue below needs | Based on revenue targets |
| Minimum impression share | Visibility erosion | Based on auction insights baseline |

## Tier 3: Diagnostic KPIs

| Metric | What It Reveals | Investigate When |
|--------|----------------|-----------------|
| Impressions | Reach/coverage | Volume drops |
| CTR | Ad relevance | Below 3% (Search) |
| CPC | Competition level | Spikes above average |
| Conversion rate | LP/offer effectiveness | Drops below baseline |
| AOV | Revenue per transaction | Decreases unexpectedly |
| Impression share | Growth headroom | Below 60% on core campaigns |
| Quality Score | Ad-keyword-LP alignment | Below 6 |

## Benchmark Ranges by Vertical

### Search Campaigns

| Metric | Ecommerce | Lead Gen | SaaS |
|--------|-----------|----------|------|
| CTR | 2-5% | 3-7% | 2-5% |
| CPC | €0.50-€3 | €2-€15 | €3-€20 |
| CVR | 2-4% | 3-8% | 2-5% |
| CPA | €15-€60 | €30-€200 | €50-€300 |
| ROAS | 300-800% | N/A | N/A |

### Performance Max

| Metric | Ecommerce | Lead Gen | SaaS |
|--------|-----------|----------|------|
| CVR | 1-3% | 2-5% | 1-3% |
| CPA | €20-€80 | €40-€250 | €60-€350 |
| ROAS | 300-700% | N/A | N/A |

> Benchmarks are starting points, not goals. Targets come from unit economics.

## Vanity Metrics to Avoid

| Metric | Why Misleading | The Test |
|--------|---------------|----------|
| High CTR, no conversions | Irrelevant traffic | Does it move a primary KPI? |
| Millions of impressions | Wrong audience | Leading to qualified clicks? |
| Low CPC | Cheap traffic that doesn't convert | Producing conversions at acceptable CPA? |
| High Quality Score | QS of 10, zero conversions = worthless | Translating to lower CPCs and conversions? |

**The universal test:** Can this metric inform a specific optimization action that moves a primary KPI? If not, it is vanity.
