# Unit Economics Question Bank

Agent-readable reference for Phase 3 of the business-context-gatherer skill.
Distilled from: SOP_16 (Calculate and Validate Unit Economics) + Unit Economics Mental Model.

---

## Vertical Classification

| If the client... | Vertical | Calculation set |
|-----------------|----------|----------------|
| Sells physical or digital products online | Ecommerce | Gross margin, break-even ROAS, target ROAS |
| Generates leads for a sales team to close | Lead Gen | Target CPL, target CAC, profit per deal |
| Sells recurring subscriptions | SaaS | ARPU, LTV, max CAC, LTV:CAC ratio |

For hybrid businesses: run calculations for the primary revenue stream first.

---

## Ecommerce Inputs

Collect from backend (Shopify, WooCommerce, etc.) and finance:

| # | Input | Definition | Source | Example |
|---|-------|-----------|--------|---------|
| 1 | Average Order Value (AOV) | Total revenue / Total orders (last 90 days) | Backend analytics | $85 |
| 2 | COGS per order | Direct product cost per average order | Finance / supplier invoices | $34 |
| 3 | Shipping cost per order | Average shipping cost paid by business | Fulfillment data | $8 |
| 4 | Payment processing fee | Average payment gateway fee per order | Payment provider | $2.55 |
| 5 | Return rate | % of orders returned (last 90 days) | Backend analytics | 12% |
| 6 | Current Google Ads ROAS | Conv value / Cost (non-branded campaigns) | Google Ads | 350% |

### Ecommerce Calculations

1. **Gross profit per order** = AOV - COGS - Shipping - Payment fees
2. **Gross margin %** = Gross profit / AOV
3. **Break-even ROAS** = 1 / Gross margin %
4. **Adjusted break-even ROAS** (accounting for returns) = Break-even ROAS / (1 - Return rate)
5. **Target ROAS** = Adjusted break-even ROAS / Acquisition budget share
   - Use 0.75 for growth-focused, 0.50 for balanced, 0.25 for conservative

### Ecommerce Results Table

| Metric | Value | Status |
|--------|-------|--------|
| AOV | | |
| Gross profit per order | | Calculated |
| Gross margin % | | Calculated |
| Break-even ROAS | | Calculated |
| Adjusted break-even ROAS (with returns) | | Calculated |
| Target ROAS (operational) | | Calculated |
| Current Google Ads ROAS | | From input |

---

## Lead Gen Inputs

Collect from CRM (HubSpot, Salesforce, etc.) and sales team:

| # | Input | Definition | Source | Example |
|---|-------|-----------|--------|---------|
| 1 | Average deal value | Revenue from a typical closed deal | CRM data (last 6 months) | $10,000 |
| 2 | Profit margin % | (Revenue - delivery costs) / Revenue | Finance | 30% |
| 3 | Lead-to-sale rate | Closed deals / Total leads generated (last 6 months) | CRM data | 20% |
| 4 | Sales cycle length | Average days from lead to close | CRM data | 45 days |
| 5 | Sales team response time | Average time from lead to first contact | CRM data | 2 hours |
| 6 | Current Google Ads CPA | Cost / Conversions (non-branded campaigns) | Google Ads | $150 |

### Lead Gen Calculations

1. **Profit per deal** = Deal value x Profit margin %
2. **Break-even CPL** = Profit per deal x Lead-to-sale rate
3. **Break-even CAC** = Profit per deal
4. **Operational target CPL** = Break-even CPL x 0.75 (leave margin for profit)
5. **ROI per deal** = (Profit per deal - Current CAC) / Current CAC

### Lead Gen Results Table

| Metric | Value | Status |
|--------|-------|--------|
| Average deal value | | |
| Profit margin % | | |
| Profit per deal | | Calculated |
| Lead-to-sale rate | | |
| Break-even CPL | | Calculated |
| Operational target CPL | | Calculated |
| Current Google Ads CPA | | From input |

---

## SaaS Inputs

Collect from billing system and product analytics:

| # | Input | Definition | Source | Example |
|---|-------|-----------|--------|---------|
| 1 | Monthly Recurring Revenue (MRR) | Current total MRR | Billing system | $500,000 |
| 2 | Active paying customers | Current count | Billing system | 5,000 |
| 3 | Monthly churn rate | Customers lost / Total customers (avg last 6 months) | Product analytics | 3% |
| 4 | Gross margin % | (Revenue - infrastructure/delivery costs) / Revenue | Finance | 80% |
| 5 | Current CAC | Total acquisition spend / New paying customers (last 6 months) | Finance + Ads | $300 |
| 6 | Free-to-paid conversion rate | Paying customers / Free trial signups (if applicable) | Product analytics | 15% |

### SaaS Calculations

1. **ARPU** = MRR / Active paying customers
2. **Customer lifetime (months)** = 1 / Monthly churn rate
3. **LTV** = ARPU x Customer lifetime x Gross margin %
4. **Max CAC (golden rule)** = LTV / 3
5. **CAC payback (months)** = Current CAC / (ARPU x Gross margin %)
6. **LTV:CAC ratio** = LTV / Current CAC

### SaaS Results Table

| Metric | Value | Status |
|--------|-------|--------|
| ARPU | | Calculated |
| Monthly churn rate | | |
| Customer lifetime (months) | | Calculated |
| LTV | | Calculated |
| Max CAC (3:1 rule) | | Calculated |
| Current CAC | | From input |
| LTV:CAC ratio | | Calculated |
| CAC payback (months) | | Calculated |

---

## Key Relationships

### Ecommerce
- Higher AOV = more room per click (higher CPC tolerance)
- Higher gross margin = lower break-even ROAS = more bidding flexibility
- Shipping and payment fees eat directly into gross margin — always include them
- Return rate erodes margins after the sale — always factor in

### Lead Gen
- Higher deal value = more acquisition room
- Higher lead-to-sale rate = higher allowable CPL = more competitive bids
- CAC must stay below profit margin per deal
- Low lead-to-sale rate compresses CPL dramatically

### SaaS
- Higher ARPU = higher LTV = more acquisition room
- Lower churn = longer lifetime = exponentially higher LTV
- LTV:CAC below 3:1 = danger zone
- Approaching 1:1 = breaking even over the full customer lifetime
