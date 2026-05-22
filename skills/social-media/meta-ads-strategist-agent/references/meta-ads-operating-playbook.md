# Meta Ads Operating Playbook

This playbook converts the transcript-derived course knowledge into reusable operating rules for a Meta/Facebook ads specialist agent.

## First Principles

### 1. Creative is the first lever

Meta/Facebook/Instagram are interruption-based feeds. The first battle is attention. Before assuming the audience is wrong, inspect:

- hook clarity
- visual stopping power
- offer strength
- message-market match
- proof or credibility
- format fit for placement
- landing page continuity

Agent default line of reasoning:

> If Meta delivery is expensive or conversion rate is weak, diagnose creative and offer before chasing narrower targeting.

### 2. Structure should feed learning

The account structure should make it easy for Meta's machine learning system to collect signal. Low-budget accounts should avoid unnecessary campaign/ad set fragmentation.

Prefer:

- fewer campaigns with clear objectives
- enough budget per ad set to gather data
- consolidated audiences where possible
- clear separation only when the hypothesis demands it

Avoid:

- many tiny interest ad sets
- duplicative campaigns with the same objective and audience
- changing too many variables at once
- resetting learning from anxious edits

### 3. Testing must have hypotheses

A test is not just launching more ads. Every test should specify:

- hypothesis
- variable being tested
- control/baseline
- budget or sample threshold
- primary decision metric
- secondary diagnostic metrics
- decision: scale, keep, iterate, pause, inconclusive

### 4. Attribution is not truth by itself

Platform attribution is useful for optimization, but the agent must also ask about business outcomes:

- blended revenue
- MER / blended ROAS
- qualified lead rate
- booked call rate
- close rate
- refund/cancel rate
- customer quality
- profitability

Distinguish:

- **Accountable:** easy to track, visible in platform
- **Effective:** actually grows the business

## Strategy Decision Tree

### Step 1 — Identify business model

- Ecommerce
- Lead generation
- Local service
- B2B pipeline
- App install/subscription
- Info product/course
- Marketplace/catalog

### Step 2 — Identify conversion event maturity

- No pixel/dataset
- Pixel installed but no events
- Some events but low conversion volume
- Stable conversion volume
- Catalog + purchase data available

### Step 3 — Pick primary path

#### New ecommerce account

- Start with sales/conversion objective if tracking exists.
- Use a simple prospecting structure.
- Consider Advantage+ Shopping only if catalog/data/setup supports it.
- Build 3-5 creative hypotheses before scaling budget.

#### Existing ecommerce account with data

- Audit campaign structure and spend concentration.
- Identify creative winners/fatigue.
- Check catalog and Advantage+ opportunities.
- Compare platform ROAS to blended business metrics.

#### Lead generation

- Validate lead quality, not just CPL.
- Use CRM/offline conversion feedback if available.
- Test offer and form friction.
- Compare instant forms vs landing page when relevant.

#### B2B/high-ticket

- Do not judge only by immediate platform conversions.
- Track pipeline quality and sales cycle.
- Use creative that filters/qualifies, not just generates cheap clicks.
- Consider full-funnel sequencing if purchase intent is not immediate.

## Campaign Structure Patterns

### Low Budget Launch

Use when budget is too small for many cells.

```text
Campaign: Prospecting / Sales or Leads
  Ad set: Broad or Advantage audience
    Ads: 3-6 creative concepts
```

Optional retargeting only if warm audience volume is meaningful.

### Creative Testing Structure

```text
Campaign: Creative Testing
  Ad set: Broad / stable audience
    Ad 1: Angle A
    Ad 2: Angle B
    Ad 3: Angle C
    Ad 4: Angle D
```

Keep audience and optimization stable so creative is the main variable.

### Scaling Structure

```text
Campaign: Core Scale
  Ad set: Consolidated winning audience/optimization
    Ads: proven winners + fresh variants
```

Scaling requires creative supply. Do not scale one exhausted winner indefinitely.

### Retargeting Structure

Use only with enough volume:

```text
Campaign: Retargeting
  Ad set: site visitors / engagers / cart / lead-started
    Ads: proof, objection handling, offer reminder, urgency where legitimate
```

Avoid tiny retargeting pools that cannot spend efficiently.

## Creative Testing Matrix

For every client/product, generate at least these angle categories:

1. **Pain point** — name the current frustration.
2. **Desired outcome** — show the future state.
3. **Mechanism** — explain why this solution works differently.
4. **Proof** — testimonials, demo, data, before/after, credibility.
5. **Objection handling** — price, time, trust, complexity, risk.
6. **Comparison** — old way vs new way, competitor/category contrast.
7. **Social identity** — who this is for and what they believe.
8. **Offer/urgency** — bonus, trial, guarantee, deadline, bundle where legitimate.

Each angle should become multiple formats:

- UGC video
- founder video
- product demo
- static image
- carousel
- testimonial/proof ad
- problem/solution ad

## Hook Requirements

A strong hook should be:

- visible or understandable in the first seconds/frame
- specific, not generic
- connected to a real customer tension
- plausible and compliant
- matched to the landing page promise

Weak hooks:

- “Transform your business today”
- “The best solution for everyone”
- “You won't believe this”

Stronger hooks:

- “Your Meta ads aren't failing because of targeting — your first 3 seconds are unclear.”
- “If your CPL is cheap but sales hates the leads, this is the audit to run.”
- “We found the creative pattern that cut demo-booking CPA by 31%.”

## Audit Framework

### Account Structure

Ask:

- Are campaigns organized by objective and funnel role?
- Is spend fragmented across too many ad sets?
- Are audiences duplicative?
- Are budgets large enough for learning?
- Are there campaigns competing against each other?

### Creative

Ask:

- Which ads consume spend?
- Which creatives generate efficient results?
- Which hooks are repeated?
- Is fatigue visible: rising frequency, falling CTR/CVR, rising CPA?
- Are there enough new tests in the pipeline?

### Funnel

Ask:

- Is CTR strong but conversion weak? Landing page/offer problem.
- Is thumbstop/CTR weak? Creative/hook problem.
- Are leads cheap but low-quality? Offer/form/qualification problem.
- Is ROAS unstable? Attribution, AOV, conversion volume, or sample-size issue.

### Measurement

Ask:

- What does Meta report?
- What does the business report?
- Are UTMs consistent?
- Is the pixel/dataset firing correctly?
- Are offline conversions or CRM outcomes imported?

## Optimization Cadence

### Daily

- Check spend anomalies.
- Check disapprovals or delivery issues.
- Avoid overreacting to normal variance.

### Twice Weekly

- Review early creative signals.
- Spot obvious losers after enough spend.
- Confirm tracking and landing pages remain healthy.

### Weekly

- Classify campaigns/ad sets/ads.
- Move budget intentionally.
- Select winners to iterate.
- Generate next creative batch.
- Update test log.

### Monthly

- Review blended performance.
- Reassess funnel and offer.
- Refresh account structure if clutter accumulated.
- Compare performance by creative theme and audience stage.

## Scaling Rules

A campaign/ad is more scale-ready when:

- enough spend has passed to make the signal meaningful
- conversion volume is stable
- CPA/ROAS is within target or strategically acceptable
- business-side quality is acceptable
- creative has not shown severe fatigue
- there are fresh variants ready

Scale cautiously:

- increase budget in controlled increments
- monitor CPA/ROAS volatility
- do not change too many variables at once
- preserve winners while testing variants

## Response Style

When advising the user, use this structure:

1. **Yes/no or direct answer first.**
2. **Diagnosis.** What is probably happening?
3. **Top 3 moves.** What matters most now?
4. **Plan.** What to do next and in what order?
5. **Risks/assumptions.** What could change the recommendation?
6. **Approval boundary.** If execution tools are connected, say what requires approval.
