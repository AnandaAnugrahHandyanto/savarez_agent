# Goals & KPIs Question Bank

Agent-readable reference for Phase 4 of the business-context-gatherer skill.
Distilled from: SOP_17 (Set Campaign Goals and KPIs) + Goals and KPIs Mental Model.

---

## Goal Setting Pyramid

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

---

## Step 1: Goal Classification

### The Two Goal Types

| | Growth Goals | Efficiency Goals |
|--|-------------|-----------------|
| Objective | Scale: more customers, more revenue, new markets | Optimize: lower CPA, higher ROAS, better margins |
| Focus | Market share, customer base expansion | Cost-effectiveness, waste reduction, profitability |
| Trade-off | Higher CPAs, lower short-term efficiency | Lower volume, potential impression share loss |
| Resource | Expansion and testing | Optimization and refinement |

**Rule: You cannot maximize growth and efficiency simultaneously.** Set one as primary. Use the other as guardrails.

### SMART Goal Validation

Every business goal must pass all 5 criteria:

| Criterion | Test Question | Pass Example | Fail Example |
|-----------|--------------|-------------|-------------|
| Specific | Focused on one outcome? | "Increase online purchases" | "Improve marketing" |
| Measurable | Has a quantifiable target? | "by 25%" | "significantly" |
| Achievable | Grounded in data and capacity? | Based on historical performance | "10x revenue next month" |
| Relevant | Aligned with business strategy? | Supports company revenue targets | Vanity metric |
| Time-bound | Has a deadline? | "in Q4 2026" | "eventually" |

### Growth Goal Examples
- Increase sales revenue by 20% in the next 6 months
- Increase new customer transactions by 10% next quarter
- Generate 100 closed deals per month

### Efficiency Goal Examples
- Reduce CAC by 10% next quarter
- Hit a blended ROAS of at least 500% in the next 6 months
- Keep CAC below $200 this year

---

## Step 2: Google Ads Goal Translation

Google Ads is one channel. Calculate its share of the overall goal.

### Channel Contribution Table

| Channel | Current Contribution | Growth Potential | Target Contribution |
|---------|---------------------|-----------------|-------------------|
| Google Ads | | | |
| Organic | | | |
| Social | | | |
| Email | | | |
| Other | | | |
| **Total** | | | **= Business Goal** |

### Translation Examples

| Business Goal | Google Ads Translation | Key Insight |
|--------------|----------------------|-------------|
| Increase revenue by 20% in 6 months | Increase conversion value by 20% | May need to overdeliver if other channels underperform |
| Generate 100 closed deals/month | Generate 150 leads at 50% lead-to-sale rate | Account for lead-to-sale rate |
| Reduce CAC by 10% | Decrease CPA by 10% by cutting spend on generic queries + improving CVR | Make it tactically actionable |
| Hit blended ROAS of 500% | Achieve average ROAS of 350% in Google Ads | Google Ads ROAS can be lower than blended |

### Document Assumptions

| Assumption | Value | Source |
|-----------|-------|--------|
| Google Ads channel contribution | | Channel analysis |
| Average conversion rate | | Historical data |
| Expected CPC range | | Auction data |
| Conversion lag | | Days-to-conversion report |

---

## Step 3: KPI Framework

### Tier 1: Primary KPIs (North Star)

| Growth Primary | Efficiency Primary |
|---------------|-------------------|
| Conversions | CPA |
| Conversion value | ROAS |
| Revenue | Cost per qualified lead |
| | POAS (if profit tracking enabled) |

### Tier 2: Secondary KPIs (Guardrails)

| Growth Primary → Efficiency Guardrails | Efficiency Primary → Volume Guardrails |
|---------------------------------------|---------------------------------------|
| Minimum ROAS: ___ (from unit economics) | Minimum conversions/month: ___ |
| Maximum CPA: ___ (from unit economics) | Minimum conversion value/month: ___ |
| Minimum profit margin: ___ | Minimum impression share: ___ |

### Tier 3: Diagnostic KPIs (Investigation Tools)

| Diagnostic KPI | What It Reveals |
|----------------|----------------|
| Impressions | Reach and market coverage |
| CTR | Ad relevance and message resonance |
| CPC | Competition level and bid efficiency |
| Conversion rate | Landing page and offer effectiveness |
| AOV | Revenue per transaction trend |
| Impression share (budget/rank) | Growth headroom and competitive position |
| Quality Score | Ad relevance, landing page, expected CTR |

### Vanity Metrics to Avoid
- High CTR with no conversions = irrelevant traffic
- Millions of impressions with no clicks = wrong audience
- Low CPC with low conversion rate = cheap traffic that doesn't convert

**The test:** Can this metric inform a specific optimization action? If not, it's vanity.

---

## Step 4: Goal Reality Check

### Validation Tools

| Tool | What to Check |
|------|--------------|
| Keyword Planner | Enough search volume for growth targets? |
| Google Trends | Seasonal patterns that affect targets? |
| Performance Planner | Forecast matches goal at current targets? |
| Bid Simulator | Volume changes at different bid levels? |
| Auction Insights | Room to grow impression share? |

### Red Flags

- Goal assumes linear growth with increased budgets (diminishing returns exist)
- Goal requires simultaneous growth and efficiency maximization
- Budget is insufficient for stated targets
- Timeline is unrealistic
- Technical limitations block KPI measurement

---

## Review Cadence

| Review Type | Frequency | Focus |
|-------------|-----------|-------|
| Performance check | Weekly | Primary and guardrail KPIs |
| Campaign optimization | Bi-weekly | Diagnostic KPIs, tactical changes |
| Stakeholder review | Monthly | Goal progress, adjustments needed |
| Goal revision | Quarterly | Revisit business goals, recalibrate |
