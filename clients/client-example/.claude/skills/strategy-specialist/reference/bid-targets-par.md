# Bid Targets & PAR Framework

Agent-readable reference for CPA/ROAS/POAS target calculations. Used by D12 (Target Feasibility).

## Target Types

| Target Type | Formula | Use Case | Vertical |
|-------------|---------|----------|----------|
| **Target CPA** | Breakeven CPA x PAR | Cost per conversion at a funnel stage | Lead Gen, SaaS |
| **Target ROAS** | Breakeven ROAS / PAR | Revenue return on ad spend | Ecommerce, Lead Gen (VBB) |
| **Target POAS** | Set above 100% based on growth goals | Profit return on ad spend | Ecommerce (with profit tracking) |

> PAR is the universal variable. CPA targets multiply by PAR (lower PAR = lower target). ROAS targets divide by PAR (lower PAR = higher target).

## PAR: Profit-to-Acquisition Ratio

The PAR is a slider between 1% and 100% — the percentage of gross profit reinvested into acquisition.

```
Growth ◄──────────────────────────────────► Efficiency

100% PAR          50% PAR              10% PAR
Max volume        Balanced             Max profit per conversion
Zero profit       Moderate profit      Severe volume loss
= Breakeven       = Sustainable        = Starvation zone
```

| PAR Range | Label | Effect | Risk |
|-----------|-------|--------|------|
| 80-100% | Breakeven zone | Targets near breakeven | Zero profit, unsustainable |
| 50-80% | Growth-leaning | Moderate targets, prioritizes volume | Lower per-conversion profit |
| 30-50% | Balanced | Competitive targets with profit retained | Sustainable for most accounts |
| 10-30% | Efficiency-leaning | Conservative targets, prioritizes margin | May miss growth goals |
| 1-10% | Starvation zone | Extremely tight targets | Volumes dry up, account declines |

### PAR Formula per Target Type

| Target Type | Formula | Direction |
|-------------|---------|-----------|
| Target CPA | Breakeven CPA x PAR | Lower PAR = lower (tighter) CPA |
| Target ROAS | Breakeven ROAS / PAR | Lower PAR = higher (tighter) ROAS |
| Target POAS | Set directly | Lower PAR = higher POAS target |

---

## CPA Targets (Lead Gen / SaaS)

### Universal Pattern

```
Breakeven CAC             = Average Deal Value x Profit Margin
Breakeven CPA (step N)    = Breakeven CPA (step N+1) x Conversion Rate at step N
Target CPA (any step)     = Breakeven CPA (same step) x PAR
```

### 2-Step: Lead → Closed Deal

| Metric | Formula | Example |
|--------|---------|---------|
| Breakeven CAC | Deal Value x Profit Margin | €2,500 x 0.50 = €1,250 |
| Breakeven CPA: Lead | Breakeven CAC x Lead-to-Close Rate | €1,250 x 0.25 = €312.50 |
| Target CPA: Lead | Breakeven CPA Lead x PAR | €312.50 x 0.50 = €156.25 |

### 3-Step: Lead → Qualified Lead → Closed Deal

| Metric | Formula | Example |
|--------|---------|---------|
| Breakeven CAC | €3,000 x 0.50 | €1,500 |
| Breakeven CPA: Qualified Lead | €1,500 x 0.50 | €750 |
| Breakeven CPA: Lead | €750 x 0.25 | €187.50 |
| Target CPA: Lead | €187.50 x 0.40 | €75 |

### SaaS Pattern

| Metric | Formula |
|--------|---------|
| Max CAC | LTV / 3 (golden rule) |
| Target CAC | Max CAC x PAR |
| Breakeven CPA: Trial | Max CAC x Free-to-Paid Rate |
| Target CPA: Trial | Breakeven CPA: Trial x PAR |

---

## ROAS Targets (Ecommerce)

### Basic (margin only)

| Metric | Formula | Example |
|--------|---------|---------|
| Breakeven ROAS | 1 / Profit Margin | 1 / 0.40 = 250% |
| Target ROAS | Breakeven ROAS / PAR | 250% / 0.50 = 500% |

### Intermediate (with order expenses)

| Metric | Formula | Example |
|--------|---------|---------|
| Total Order Expenses | Shipping + Fulfillment + Payment | 3% + 0.5% + 2% = 5.5% |
| Effective Margin | Profit Margin - Expenses | 40% - 5.5% = 34.5% |
| Breakeven ROAS | 1 / Effective Margin | 1 / 0.345 = 290% |
| Target ROAS | Breakeven ROAS / PAR | 290% / 0.50 = 580% |

### Advanced (with returns)

Additional factors: return rate, resale rate, return processing costs.

| Metric | Formula | Example |
|--------|---------|---------|
| Net Return Cost | Return Rate x costs - (Return Rate x Resale Rate x (1-Margin)) | 3.4% |
| Effective Margin | Profit Margin - Order Expenses - Net Return Cost | 40% - 5% - 3.4% = 31.6% |
| Breakeven ROAS | 1 / Effective Margin | 316% |
| Target ROAS | Breakeven ROAS / PAR | 632% |

---

## POAS Targets (Ecommerce with Profit Tracking)

POAS = Gross Profit / Ad Spend. 100% always equals breakeven.

| POAS | Meaning |
|------|---------|
| 100% | Breakeven: gross profit = ad spend |
| 150% | 50% profit on ad spend |
| 200% | 100% profit on ad spend |

POAS advantages over ROAS:
- Calculates margin per order (not average across products)
- Includes all order-level costs
- 100% always equals breakeven regardless of product mix
- Eliminates the margin paradox (optimizing revenue can destroy profit)

> Use POAS when margins vary significantly across products. If margins are uniform, ROAS and POAS tell the same story.

---

## D12 Feasibility Assessment

To assess target feasibility (D12), compare the current target against breakeven:

**For CPA targets:**
- Calculate breakeven CPA from unit economics
- Calculate implied PAR: Target CPA / Breakeven CPA
- If implied PAR > 80%: WARN (near breakeven, unsustainable)
- If implied PAR > 100%: FAIL (target exceeds breakeven, losing money)
- If target > Max CAC (SaaS/Lead Gen): FAIL

**For ROAS targets:**
- Calculate breakeven ROAS from unit economics
- Calculate implied PAR: Breakeven ROAS / Target ROAS
- If implied PAR > 80%: WARN (target too close to breakeven)
- If Target ROAS < Breakeven ROAS: FAIL (target below breakeven)

**For targets without unit economics basis:**
- If business.md target has no documented breakeven calculation: WARN ("target appears arbitrary — not grounded in unit economics")

## Target Validation Methods

| Method | Data Required | Best For |
|--------|---------------|----------|
| Performance Planner | Active campaigns, 7+ days | Forecasting volume at target |
| Bid Simulator | Active campaigns, impression data | Comparing scenarios |
| Historical data | 3+ months history | Gauging achievable ranges |
