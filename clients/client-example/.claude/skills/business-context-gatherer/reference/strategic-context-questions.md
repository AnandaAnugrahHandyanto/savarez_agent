# Strategic Context Question Bank

Agent-readable reference for Phases 5-6 of the business-context-gatherer skill.
Distilled from: The Five Buckets & Hierarchy of Constraints, Google Ads Success Formula, Awareness Stage Mental Model.

---

## Campaign Priority Assessment

### Priority Ranking Framework

When ranking campaigns, consider these factors for each:

| Factor | Question |
|--------|----------|
| Profitability | Is this campaign profitable at current targets? |
| Volume | Does this campaign generate meaningful conversion volume? |
| Strategic importance | Does this campaign serve a strategic goal beyond direct ROI? |
| Growth potential | Is there room to scale (impression share, budget, keyword expansion)? |

### Priority Categories

| Priority | Criteria | Action |
|----------|----------|--------|
| P1 — High priority | Profitable + high volume OR strategic importance | Active optimization, scale if possible |
| P2 — Standard | Profitable but lower volume, or volume but marginal ROI | Maintain, optimize incrementally |
| P3 — Low priority | Marginal or unprofitable, low strategic value | Reduce spend, consider pausing |
| P4 — Deprioritize | Unprofitable with no strategic rationale | Pause or sunset |

---

## Competitive Landscape Assessment

### Competitor Analysis Questions

For each competitor (top 3-5):

| Question | Why It Matters |
|----------|---------------|
| Who are they? (name, URL) | Identifies the competitive set |
| How do you differentiate from them? | Informs ad copy and landing page strategy |
| Are they bidding on your brand terms? | Determines brand defense strategy |
| Are you bidding on their brand terms? | Influences competitive campaign decisions |
| What is their perceived market position? | Helps frame messaging and positioning |

### Competitive Bidding Strategy

| Strategy | When to Use | Trade-off |
|----------|-------------|-----------|
| Aggressive | Market leader, strong offer, high margins | Higher CPAs on competitive terms |
| Defensive | Protecting market share, strong brand | May miss offensive opportunities |
| Opportunistic | Budget-constrained, selective battles | May lose share on key terms |

### Win Themes Template

For each competitor, document: `vs [Competitor]: [How we're different/better]`

Example:
- vs Competitor A: We work inside existing tools (no new platform to learn)
- vs Competitor B: Proven scale (10K+ customers vs newer entrant)
- vs Competitor C: Full workflow support vs single-feature tool

---

## Awareness Stage Positioning

### The 5 Stages

| Stage | What They Know | Traffic Sources | Message Focus |
|-------|---------------|----------------|---------------|
| Unaware | Doesn't know the problem | Display, YouTube prospecting | Problem identification |
| Problem Aware | Knows the problem, not solutions | Problem search, Display | Problem validation |
| Solution Aware | Evaluating solution options | Product/service search | Your unique approach |
| Product Aware | Comparing your product to alternatives | Competitor search, remarketing | Benefits + differentiation |
| Most Aware | Ready to buy | Brand search, remarketing, email | Offer details + urgency |

### Positioning Question

"Where does your typical Google Ads visitor fall on the awareness spectrum?"

| Option | Typical For |
|--------|------------|
| Mostly Solution/Product Aware | Search-heavy accounts, established brands |
| Mix of Problem to Product Aware | Accounts with Display/Video + Search |
| Mostly Most Aware | Brand-dominant accounts, remarketing-heavy |

---

## The Five Buckets — Constraint Classification

Use this framework to help users classify known constraints and historical issues.

### Bucket Hierarchy (Top to Bottom)

| Bucket | Core Question | Examples |
|--------|--------------|---------|
| 0. Measurement | Do we see reality clearly? | Tracking discrepancies, missing conversions, tag issues |
| 1. Business | Can the business sustain growth? | Thin margins, sales capacity limits, inventory issues |
| 2. Conversion | Can we turn visitors into customers? | Low landing page CVR, checkout friction, form drop-off |
| 3. Traffic | Are we reaching the right people? | Low impression share, wrong query mix, brand-only volume |
| 4. Creative | Does our message attract correctly? | Low CTR, stale assets, lead quality from ad mismatch |

**Rule:** Do not seriously optimize a lower bucket while an upper bucket is broken.

### Constraint Classification for Historical Context

When the user describes past tests or known issues, classify into buckets:

| User Says | Likely Bucket | Follow-up |
|-----------|--------------|-----------|
| "Leads are low quality" | Business (sales) or Traffic (targeting) | Ask: do they convert on the page but fail in CRM? |
| "CPA is too high" | Could be any bucket | Ask: is conversion rate the problem, or CPC, or both? |
| "Can't scale budget" | Business (economics) or Traffic (demand) | Ask: does increasing budget raise CPA, or is there no more inventory? |
| "Tracking doesn't match backend" | Measurement | Flag as priority constraint |
| "Landing page doesn't convert" | Conversion | Ask: what is the CVR and what has been tested? |

---

## Google Ads Success Formula — 9 Pillars

Reference for understanding which pillar may be the primary constraint.

| Pillar | Domain | Core Question |
|--------|--------|--------------|
| 1. Irresistible Offer | Business/Creative | Does the offer compel the right people to act? |
| 2. Landing Page | Conversion | Does the funnel turn visitors into leads/orders? |
| 3. Unit Economics | Business | Do the numbers support scaling? |
| 4. Goals & KPIs | Foundations | Do we know what success looks like? |
| 5. Conversion Tracking | Measurement | Does data reflect reality? |
| 6. Campaign Structure | Operational | Is data consolidated for Smart Bidding? |
| 7. Targeting | Traffic | Are we reaching the right people? |
| 8. Creatives | Creative | Does the message attract and pre-frame? |
| 9. Bids & Budgets | Execution | Is budget allocated to highest-value opportunities? |

**Mapping to Five Buckets:**

| Bucket | Pillars |
|--------|---------|
| Measurement | 5 |
| Business | 1, 3 |
| Conversion | 2 |
| Traffic | 6, 7 |
| Creative | 8 |

Pillar 4 (Goals) and Pillar 9 (Bids) span multiple buckets.

---

## Seasonal Pattern Assessment

### Seasonality Categories

| Type | Description | Examples |
|------|-------------|---------|
| Strong | Clear peak and trough periods with >30% variance | Retail (Black Friday, Christmas), Travel (summer), Education (back-to-school) |
| Mild | Some variation but mostly consistent, 10-30% variance | B2B services (end-of-quarter), SaaS (January planning) |
| None | Relatively flat year-round, <10% variance | Essential services, infrastructure software |

### Seasonal Questions

| Question | Why It Matters |
|----------|---------------|
| Peak periods (months/events) | Budget allocation, creative planning, inventory |
| Slow periods (months) | Budget conservation, testing opportunities |
| Upcoming events (next 90 days) | Immediate planning needs |
| Seasonal pricing or promotions | Affects ROAS/CPA targets, ad copy rotation |

---

## Organizational Constraints

### Approval Process Assessment

| Area | Question | Impact on Google Ads |
|------|----------|---------------------|
| Ad copy approval | Who approves? How long? | Determines RSA testing velocity |
| Landing page changes | Who implements? Turnaround? | Determines CRO testing velocity |
| Budget changes | Who approves increases? | Determines scaling speed |
| Brand guidelines | How strict? | Determines creative freedom |

### Team Dependencies

| Dependency | Question | Risk |
|-----------|----------|------|
| Dev/Engineering | Tracking implementation, LP changes | Slow turnaround = measurement gaps |
| Design | Creative assets for Display/Video/PMax | No assets = limited campaign types |
| Sales team | Lead follow-up, CRM data | Slow follow-up = wasted leads |
| Legal/Compliance | Ad copy restrictions | Limits messaging options |

### Reporting Cadence

| Cadence | Typical For |
|---------|------------|
| Weekly | Active optimization, high-spend accounts |
| Bi-weekly | Standard maintenance accounts |
| Monthly | Stable accounts, stakeholder summaries |
| Quarterly | Strategic reviews, goal revision |
