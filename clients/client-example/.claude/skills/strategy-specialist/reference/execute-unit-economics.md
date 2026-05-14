# Execute — Calculate Unit Economics (E01/E03)

Interactive SOP for calculating and validating unit economics. Used when `/strategy-specialist --execute unit-economics` is invoked or when DIAGNOSE finds FAIL items in D01-D09.

E01 = first-time calculation. E03 = recalculation (show existing values for comparison).

## Flow Overview

| Phase | Purpose | Output |
|-------|---------|--------|
| 1. Confirm vertical | Route to correct input set | Vertical classification |
| 2. Gather inputs | Structured interview per vertical | Completed input worksheet |
| 3. Calculate | Run formulas from `unit-economics-formulas.md` | Break-even values, viability thresholds |
| 4. Validate | Compare against thresholds from `viability-thresholds.md` | Go / Conditional Go / No-Go verdict |
| 5. Update business.md | Write results to Unit Economics section | Updated business.md (with permission) |

---

## Phase 1: Confirm Vertical

Read vertical from business.md. If already set, confirm:

**Question:** "Business.md shows vertical as {vertical}. Is this correct?"
- Yes → proceed
- No → ask: "Which vertical best describes this business?" Options: Ecommerce, Lead Gen, SaaS

For hybrid businesses: run primary vertical first, note secondary.

---

## Phase 2: Gather Inputs

**If E03 (recalculation):** Show existing values from business.md alongside each question so user can confirm or update.

### Ecommerce Questions

Ask these in order. Use AskUserQuestion for structured input.

1. **"What is your average order value (AOV)?"**
   - Source: Backend (Shopify, WooCommerce), last 90 days
   - Format: Currency amount

2. **"What is your cost of goods sold (COGS) per order?"**
   - Source: Backend/supplier data
   - Include: Direct product cost only

3. **"What is your average shipping cost per order (paid by the business)?"**
   - Source: Shipping provider
   - Note: Cost the business bears, not what customer pays

4. **"What is your average payment processing fee per order?"**
   - Source: Payment provider (Stripe, Mollie, etc.)
   - Typical: 1.5-3% of order value

5. **"What is your return rate?"**
   - Source: Backend, last 90 days
   - Format: Percentage

6. **"What is your current Google Ads ROAS? (non-branded campaigns)"**
   - Source: Google Ads, last 30 days
   - If unknown: mark as N/A

### Lead Gen Questions

1. **"What is your average deal value (revenue per closed deal)?"**
   - Source: CRM, last 6 months

2. **"What is your profit margin percentage?"**
   - Formula: (Revenue - delivery costs) / Revenue
   - Source: Finance/accounting

3. **"What is your lead-to-sale rate?"**
   - Formula: Closed deals / Total leads generated
   - Source: CRM, last 6 months
   - Note: Per traffic source if possible

4. **"What is your average sales cycle length (days from lead to close)?"**
   - Source: CRM

5. **"What is your sales team's average response time to new leads?"**
   - Source: CRM / sales ops

6. **"What is your current Google Ads CPA? (non-branded)"**
   - Source: Google Ads, last 30 days

### SaaS Questions

1. **"What is your Monthly Recurring Revenue (MRR)?"**
   - Source: Billing system

2. **"How many active paying customers do you have?"**
   - Source: Billing system

3. **"What is your monthly churn rate?"**
   - Formula: Customers lost / Total customers (average of last 6 months)
   - Source: Billing system / product analytics

4. **"What is your gross margin percentage?"**
   - Formula: (Revenue - infrastructure/delivery costs) / Revenue
   - Source: Finance

5. **"What is your current CAC (cost to acquire one paying customer)?"**
   - Formula: Total acquisition spend / New paying customers (last 6 months)
   - If unknown: use Google Ads CPA as proxy

6. **"What is your free-to-paid conversion rate? (if applicable)"**
   - Formula: Paying customers / Free trial signups
   - Source: Product analytics

---

## Phase 3: Calculate

Run all formulas from `unit-economics-formulas.md` for the identified vertical.

### Ecommerce Calculations

```
Gross profit = AOV - COGS - Shipping - Payment fees
Gross margin % = Gross profit / AOV
Break-even ROAS = 1 / Gross margin %
Adjusted break-even ROAS = Break-even ROAS / (1 - Return rate)
Target ROAS (balanced, PAR=0.50) = Adjusted break-even ROAS / 0.50
```

### Lead Gen Calculations

```
Profit per deal = Deal value x Profit margin %
Break-even CPL = Profit per deal x Lead-to-sale rate
Break-even CAC = Profit per deal
Operational target CPL = Break-even CPL x 0.75
```

### SaaS Calculations

```
ARPU = MRR / Active paying customers
Customer lifetime = 1 / Monthly churn rate
LTV = ARPU x Customer lifetime x Gross margin %
Max CAC (3:1 rule) = LTV / 3
LTV:CAC ratio = LTV / Current CAC
CAC payback = Current CAC / (ARPU x Gross margin %)
```

**Present results in a table:**

```
Unit Economics Calculation Results:

| Metric | Value | Assessment |
|--------|-------|------------|
| {metric} | {value} | {assessment from thresholds} |
| ... | ... | ... |
```

**If E03 (recalculation):** Show old vs new comparison:

```
| Metric | Previous | Updated | Change |
|--------|----------|---------|--------|
| {metric} | {old} | {new} | {delta} |
```

---

## Phase 4: Validate

Compare calculated values against thresholds from `viability-thresholds.md`.

**Present verdict:**

```
Viability Assessment: {Go / Conditional Go / No-Go}

{1-2 sentence explanation with the key metrics that drove the verdict}

Risk factors:
- {risk 1}
- {risk 2}
```

If No-Go: present root causes and fixes from `viability-thresholds.md`.

---

## Phase 5: Update business.md

**Ask permission:** "Want me to update the Unit Economics section of business.md with these results?"

| Option | Action |
|--------|--------|
| Yes, update | Write to business.md Unit Economics section |
| Review first | Show the section content before writing |
| No, skip | Don't modify business.md |

**When writing to business.md:**

1. Read current business.md
2. Replace ONLY the `## Unit Economics` section (preserve all other sections)
3. Update the `Last Updated` date in the `## Account` section
4. Write the file

**Section format to write:**

```markdown
## Unit Economics

### {Vertical} Economics

| Metric | Value | Source |
|--------|-------|--------|
| {metric} | {value} | {User-provided / Calculated} |
| ... | ... | ... |

### Conversion Action Values

{Preserve existing conversion action values if they exist}

### Viability Assessment
**Status:** {Go / Conditional Go / No-Go}
**Notes:** {1-2 sentence assessment with key drivers}

### Calculation Details
{Show each formula with actual numbers}
```
