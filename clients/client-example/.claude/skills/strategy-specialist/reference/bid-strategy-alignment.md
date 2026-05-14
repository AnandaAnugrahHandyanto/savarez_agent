# Bid Strategy Alignment

Agent-readable reference for goal-to-bid-strategy mapping. Used by D13 (Goal-to-Bid Strategy Alignment).

## The Goal-to-Strategy Pyramid

```
         ┌──────────────────────┐
         │  1. Business Goal     │
         └──────────┬───────────┘
                    ↓
       ┌────────────────────────────┐
       │  2. Google Ads Goal         │
       │  (Growth + Efficiency)      │
       └────────────┬───────────────┘
                    ↓
    ┌────────────────────────────────────┐
    │  3. Optimization Objective          │
    │  (Visibility / Traffic / Conv /     │
    │   Conv Value)                       │
    └────────────────┬───────────────────┘
                     ↓
  ┌──────────────────────────────────────────┐
  │  4. Data Readiness Check                  │
  └──────────────┬───────────────────────────┘
                 ↓
┌────────────────────────────────────────────────┐
│  5. Bid Strategy Selection                      │
└────────────────────────────────────────────────┘
```

## The Six Bid Strategies

| Strategy | Optimizes For | Efficiency Control | Data Requirement | Best For |
|----------|-------------|-------------------|-----------------|----------|
| Manual CPC | Clicks (manual) | Full control | None | Brand, new accounts, experiments |
| Maximize Clicks | Click volume | None (budget only) | None | Data gathering, traffic goals |
| Target Impression Share | Visibility | IS % target | None | Brand defence, competitive dominance |
| Maximize Conversions | Conversion volume | None (budget only) | 15 min / 30 func / 50+ rec | Growth-first goals |
| Target CPA | Conversion volume | CPA target | 15 min / 30 func / 50+ rec | Lead gen, SaaS, efficiency guardrails |
| Maximize Conv Value | Conversion value | None (budget only) | 30 min / 50 func / 50+ rec | Revenue/profit max |
| Target ROAS | Conversion value | ROAS target | 30 min / 50 func / 50+ rec | Ecommerce, VBB, efficiency goals |

## Optimization Objective Hierarchy

```
What are you optimizing for?
│
├─ Visibility (impressions)
│  └─ Target Impression Share
│
├─ Traffic (clicks)
│  └─ Maximize Clicks
│
├─ Conversion volume (leads, transactions)
│  ├─ With efficiency target → Target CPA
│  └─ Without efficiency target → Maximize Conversions
│
└─ Conversion value (revenue, profit, LTV)
   ├─ With efficiency target → Target ROAS
   └─ Without efficiency target → Maximize Conversion Value
```

## Data Readiness Thresholds

| Strategy | Absolute Min | Functional Min | Recommended |
|----------|-------------|----------------|-------------|
| Target CPA | 15 conv/month | 30 conv/month | 50+ conv/month |
| Target ROAS | 30 conv/month | 50 conv/month | 50+ conv/month |
| Portfolio level | Same thresholds, pooled across campaigns |

## D13 Alignment Rules

Check each enabled campaign's bid strategy against business.md goals:

### Goal-to-Strategy Alignment

| Primary Goal (business.md) | Compatible Strategies | Misaligned Strategies |
|---------------------------|----------------------|----------------------|
| Growth (volume) | Maximize Conversions, Maximize Conv Value, Target CPA (loose), Target ROAS (loose) | Manual CPC (too conservative), Target IS (wrong objective) |
| Efficiency (CPA) | Target CPA, Target ROAS | Maximize Conversions (no efficiency control), Maximize Clicks (wrong objective) |
| Efficiency (ROAS) | Target ROAS, Target CPA (with value tracking) | Maximize Clicks, Target IS |
| Brand defence | Target IS, Manual CPC | Maximize Conversions (overkill for brand) |

### Target-to-Strategy Alignment

| business.md Target | Expected Bid Strategy Config | Misalignment Signal |
|--------------------|------------------------------|---------------------|
| Target CPA: $X | Campaigns using Target CPA with target near $X | Campaign target >30% off from business.md target |
| Target ROAS: X% | Campaigns using Target ROAS with target near X% | Campaign target >30% off from business.md target |
| Growth: uncapped | Maximize Conversions or Max Conv Value | Using tight Target CPA when goal is volume |

### Campaign Type Expectations

| Campaign Type | Typical Strategy | Flag If |
|--------------|------------------|---------|
| Brand Search | Manual CPC or Target IS | Using aggressive automated bidding |
| Non-Brand Search | Target CPA or Target ROAS | Using Maximize Clicks long-term (data gathering only) |
| Shopping | Target ROAS or Max Conv Value | Using Target CPA (revenue-based is better) |
| PMax | Target CPA or Target ROAS | No strategy set (runs on Maximize Conv by default) |

### Volume Sufficiency Check

For campaigns using Target CPA or Target ROAS:
- Check conversion volume from campaigns.csv metrics
- If conversions < 15/month: WARN — insufficient data for smart bidding
- If conversions < 30/month: INFO — functional but may be volatile
- If conversions >= 50/month: OK — sufficient for stable performance

## Progression Check

Bid strategies should progress over time:
- Phase 1 (launch): Manual CPC or Maximize Clicks — acceptable for first 2 weeks
- Phase 2 (stabilize): Migrate to Target CPA / Target ROAS
- Phase 3+ (optimize): Should be on conversion/value-based bidding

If a campaign has been running 60+ days and is still on Manual CPC or Maximize Clicks without a clear reason (e.g., brand campaign), flag as WARN.
