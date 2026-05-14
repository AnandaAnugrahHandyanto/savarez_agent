# Unit Economics Formulas

Agent-readable reference for all unit economics calculations. Used by D01-D09 diagnostics.

## Ecommerce Formulas

### Key Formulas

| Metric | Formula | Example |
|--------|---------|---------|
| **Gross margin %** | (Revenue - COGS - Shipping - Payment fees) / Revenue | (€32.28 - €20.20 - €6.50 - €1.00) / €32.28 = 14.2% |
| **Break-even ROAS** | 1 / Gross margin % | 1 / 0.142 = 704% |
| **Target ROAS** | Break-even ROAS / Acquisition budget share (PAR) | 704% / 0.75 = 939% |
| **Contribution margin** | Revenue - COGS - Shipping - Fees - Ad spend | €32.28 - €20.20 - €6.50 - €1.00 - €4.30 = €0.28 |
| **POAS** | Gross profit / Ad spend | €4.58 / €4.30 = 106% |

### Gross Margin Calculation (Step-by-Step)

| Line item | Source | Example |
|-----------|--------|---------|
| Revenue (order value) | Backend/Shopify | €32.28 |
| Minus: COGS | Backend/supplier | -€20.20 |
| Minus: Shipping cost | Shipping provider | -€6.50 |
| Minus: Payment processing fee | Payment provider | -€1.00 |
| **= Gross profit** | Calculated | **€4.58** |
| **Gross margin %** | Gross profit / Revenue | **14.2%** |

### Break-even ROAS Scale

| Gross margin % | Break-even ROAS | Assessment |
|---------------|-----------------|------------|
| 70% | 143% | Excellent: easy to scale |
| 50% | 200% | Good: standard target achievable |
| 30% | 333% | Tight: limited scaling headroom |
| 15% | 667% | Difficult: very narrow margins |
| 10% | 1000% | Unscalable: unit economics problem |

### AOV Impact on Scalability

| AOV | Gross margin % | Gross profit/order | Break-even ROAS | Scalability |
|-----|---------------|-------------------|-----------------|-------------|
| €100 | 50% | €50 | 200% | High |
| €50 | 50% | €25 | 200% | Moderate |
| €30 | 15% | €4.50 | 667% | Very low |
| €20 | 10% | €2.00 | 1000% | Unscalable |

### Acquisition Budget Share (PAR) Ranges

| PAR | Use case |
|-----|----------|
| 75% (aggressive) | Growth-focused, high-margin products |
| 50% (balanced) | Standard operations, moderate margins |
| 25% (conservative) | Thin margins, efficiency-focused |

---

## Lead Gen Formulas

### Key Formulas

| Metric | Formula | Example |
|--------|---------|---------|
| **Target CPL** | Deal value x Profit margin % x Lead-to-sale rate | €10,000 x 30% x 20% = €600 |
| **Target CAC** | Deal value x Profit margin % | €10,000 x 30% = €3,000 |
| **Profit per deal** | Deal value x Profit margin % - CAC | €10,000 x 30% - €500 = €2,500 |
| **ROI per deal** | Profit per deal / CAC | €2,500 / €500 = 5x |
| **Required lead volume** | Revenue target / (Deal value x Lead-to-sale rate) | €1M / (€10,000 x 20%) = 50 leads/month |

### Lead-to-Sale Rate Impact

| Lead-to-sale rate | Deal value €10K, margin 30% | Max CPL |
|-------------------|---------------------------|---------|
| 50% | High-performing sales team | €1,500 |
| 30% | Good sales process | €900 |
| 20% | Average | €600 |
| 10% | Below average | €300 |
| 5% | Poor: fix sales process first | €150 |

### Deal Value Impact

| Deal value | Margin 30%, L2S 20% | Max CPL | Max CAC |
|-----------|---------------------|---------|---------|
| €50,000 | High-value services | €3,000 | €15,000 |
| €10,000 | Standard services | €600 | €3,000 |
| €5,000 | Small business | €300 | €1,500 |
| €1,000 | Low-ticket | €60 | €300 |

---

## SaaS Formulas

### Key Formulas

| Metric | Formula | Example |
|--------|---------|---------|
| **ARPU** | MRR / Active paying customers | €100K / 1,000 = €100/month |
| **Customer lifetime** | 1 / Monthly churn rate | 1 / 5% = 20 months |
| **LTV** | ARPU x Customer lifetime x Gross margin % | €100 x 20 x 70% = €1,400 |
| **Max CAC (3:1 rule)** | LTV / 3 | €1,400 / 3 = €467 |
| **CAC** | Total acquisition spend / New paying customers | €40,000 / 100 = €400 |
| **LTV:CAC ratio** | LTV / CAC | €1,400 / €400 = 3.5:1 |
| **CAC payback (months)** | CAC / (ARPU x Gross margin %) | €400 / (€100 x 70%) = 5.7 months |

### Customer Lifetime by Churn

| Monthly churn rate | Customer lifetime | Assessment |
|-------------------|------------------|------------|
| 2% | 50 months | Excellent product-market fit |
| 3% | 33 months | Strong retention |
| 5% | 20 months | Average |
| 8% | 12.5 months | Below average: retention problem |
| 15% | 6.7 months | Critical: fix product before scaling |

### LTV:CAC Ratio Interpretation

| LTV:CAC | Interpretation | Action |
|---------|---------------|--------|
| 5:1+ | Highly scalable | Increase spend, test new channels |
| 3:1 - 5:1 | Healthy: sustainable | Maintain pace, optimize incrementally |
| 2:1 - 3:1 | Warning zone | Reduce CAC or improve retention |
| 1:1 - 2:1 | Danger zone | Pause scaling, fix fundamentals |
| Below 1:1 | Losing money | Stop acquisition spend immediately |

### CAC Payback Period

| CAC payback (months) | Assessment |
|---------------------|------------|
| Under 6 | Excellent: fast payback, strong cash flow |
| 6-12 | Good: standard SaaS benchmark |
| 12-18 | Concerning: cash flow pressure |
| 18+ | Problematic: liquidity risk |

---

## Common Mistakes

| Mistake | Problem | Fix |
|---------|---------|-----|
| Using revenue as the benchmark | Ignores COGS, shipping, fees | Use gross margin and profit-based metrics |
| Ignoring return rates (ecommerce) | Returns erode margin after the sale | Factor average return rate into calculations |
| Using blended lead-to-sale rate | Hides channel-specific quality | Calculate per traffic source |
| Ignoring churn rate (SaaS) | Overstates LTV and max CAC | Use actual monthly churn, not annual estimates |
| Setting targets at break-even | Zero profit, no room for error | Set targets at 50-75% of break-even ceiling |
| Not revisiting quarterly | Unit economics change | Recalculate every quarter with fresh data |
