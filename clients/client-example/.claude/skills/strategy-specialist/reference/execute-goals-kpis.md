# Execute — Set Campaign Goals and KPIs (E02/E04)

Interactive SOP for setting or revising campaign goals and KPIs. Used when `/strategy-specialist --execute goals` is invoked or when DIAGNOSE finds FAIL items in D10-D14.

E02 = first-time goal setting. E04 = revise targets based on updated unit economics.

## Flow Overview

| Phase | Purpose | Output |
|-------|---------|--------|
| 1. Define business goal | Structured interview for SMART goal | Documented business goal |
| 2. Translate to Google Ads goal | Platform-specific target with assumptions | Google Ads goal statement |
| 3. Choose KPIs | Three-tier KPI framework | Primary, guardrail, diagnostic KPIs |
| 4. Validate targets | Cross-check against unit economics | Feasibility assessment |
| 5. Update business.md | Write results to Goals & KPIs section | Updated business.md (with permission) |

---

## Phase 1: Define Business Goal

**If E04 (revise):** Show current goals from business.md alongside questions.

### Question Set

1. **"What is your primary business objective for Google Ads?"**

   Options (present via AskUserQuestion):
   - Grow revenue / volume (Growth goal)
   - Improve efficiency / reduce costs (Efficiency goal)
   - Both, but growth is more important
   - Both, but efficiency is more important

2. **"What is the specific target?"**
   - Growth: "What revenue or conversion volume are you targeting? In what timeframe?"
   - Efficiency: "What CPA or ROAS target are you aiming for?"

3. **"What budget is available for Google Ads?"**
   - Options: Uncapped (CPA/ROAS constrained), Fixed monthly budget, Range

4. **"Are there capacity constraints?"**
   - Sales team capacity (Lead Gen)
   - Stock/fulfillment limits (Ecommerce)
   - Onboarding capacity (SaaS)

### SMART Validation

After gathering answers, validate:

```
SMART Check:
| Criterion | Status | Details |
|-----------|--------|---------|
| Specific | {Pass/Fail} | {focused on one outcome?} |
| Measurable | {Pass/Fail} | {has quantifiable target?} |
| Achievable | {Pass/Fail} | {grounded in data?} |
| Relevant | {Pass/Fail} | {aligned with business?} |
| Time-bound | {Pass/Fail} | {has deadline?} |
```

If any criterion fails, ask the user to refine.

---

## Phase 2: Translate to Google Ads Goal

### Goal Translation

Present the translation:

```
Business goal: {what user said}
Google Ads goal: {translated to in-platform metrics}
Assumptions: {channel contribution %, conversion rates, etc.}
```

### Goal Statement Format

```
[Increase/Decrease] [Google Ads metric] [by X%/to X value]
[by/in timeframe]
[while maintaining/not exceeding guardrail metric of X]
```

Example: "Increase monthly trial_converted from 175 to 250 by Q3 2026, while keeping CPA under $200."

---

## Phase 3: Choose KPIs

### Primary KPI Selection

Based on goal type, suggest the appropriate primary KPI:

| Goal Type | Vertical | Suggested Primary KPI |
|-----------|----------|----------------------|
| Growth | Ecommerce | Conversion value / Revenue |
| Growth | Lead Gen | Conversions (leads or qualified leads) |
| Growth | SaaS | Conversions (trials or signups) |
| Efficiency | Ecommerce | ROAS (or POAS if profit tracking) |
| Efficiency | Lead Gen | CPA (cost per lead or qualified lead) |
| Efficiency | SaaS | CPA (cost per trial) |

**Ask:** "Is {suggested KPI} the right primary metric, or would you prefer something else?"

### Guardrail KPIs

Based on goal type, suggest guardrails:

**Growth primary → Efficiency guardrails:**
- "What is the maximum CPA you can accept?" → Cross-check against break-even from Unit Economics
- "What is the minimum ROAS you need?" → Cross-check against break-even ROAS

**Efficiency primary → Volume guardrails:**
- "What is the minimum conversion volume you need per month?"
- "Is there a minimum spend floor?"

**Validate guardrails against unit economics:**
- If max CPA > break-even CPA: WARN — "This guardrail allows spending above break-even"
- If min ROAS < break-even ROAS: WARN — "This guardrail allows spending below break-even"

### Diagnostic KPIs

Auto-select standard diagnostic KPIs: Impressions, CTR, CPC, Conversion rate, AOV (ecommerce), Impression share, Quality Score.

Present the complete framework:

```
KPI Framework:

| Tier | KPI | Target/Threshold |
|------|-----|-----------------|
| Primary | {KPI} | {target} |
| Guardrail | {KPI} | {threshold} |
| Guardrail | {KPI} | {threshold} |
| Diagnostic | Impressions, CTR, CPC, CVR, IS, QS | Monitor (no targets) |
```

---

## Phase 4: Validate Targets

Cross-check the targets against unit economics from business.md:

### Feasibility Check

Read Unit Economics section. Calculate:

**For CPA targets:**
```
Break-even CPA from unit economics: {value}
Target CPA from goals: {value}
Implied PAR: Target / Break-even = {value}
Assessment: {healthy 20-70% / near-breakeven >70% / losing money >100%}
```

**For ROAS targets:**
```
Break-even ROAS from unit economics: {value}
Target ROAS from goals: {value}
Implied PAR: Break-even / Target = {value}
Assessment: {healthy / near-breakeven / below-breakeven}
```

### Present Feasibility Result

```
Target Feasibility:
| Check | Status | Details |
|-------|--------|---------|
| Target vs break-even | {Pass/Warn/Fail} | {explanation} |
| Implied PAR | {value}% | {label: growth-leaning / balanced / etc.} |
| Volume achievability | {Pass/Warn/N/A} | {based on historical data if available} |
```

If FAIL: "Your target {X} exceeds the break-even point of {Y}. You would lose money on every conversion. Suggest adjusting to {recommended value}."

---

## Phase 5: Update business.md

**Ask permission:** "Want me to update the Goals & KPIs section of business.md with these results?"

| Option | Action |
|--------|--------|
| Yes, update | Write to business.md Goals & KPIs section |
| Review first | Show the section content before writing |
| No, skip | Don't modify business.md |

**When writing to business.md:**

1. Read current business.md
2. Replace ONLY the `## Goals & KPIs` section (preserve all other sections)
3. Update the `Last Updated` date in the `## Account` section
4. Write the file

**Section format to write:**

```markdown
## Goals & KPIs

### Primary Focus
**Goal Type:** {Growth / Efficiency}
**Primary KPI:** {KPI name} — Target: {value} ({scope: non-branded only, all campaigns, etc.})

### Performance Targets

**{Scope} Campaigns ({Primary Focus}):**

| Metric | Current | Target | Hard Constraint |
|--------|---------|--------|-----------------|
| {primary KPI} | {current if known} | {target} | {constraint} |
| ... | ... | ... | ... |

### Hard Constraints
- **{Constraint}:** {value} — {scope}

### Guardrail KPIs
- **{Guardrail}:** {threshold} — {what it prevents}

### Budget
{Budget statement from Phase 1}

### Review Cadence

| Review Type | Frequency |
|-------------|-----------|
| Performance check | Weekly |
| Stakeholder review | Monthly |
| Goal revision | Quarterly |
```

---

## E04: Revise Targets Flow

When triggered by updated unit economics (after E01/E03):

1. Read the freshly updated Unit Economics section
2. Read the current Goals & KPIs section
3. Recalculate break-even values from new unit economics
4. Compare current targets against new break-even
5. If targets are now problematic: present old vs new comparison

```
Target Revision Needed:

| Metric | Current Target | New Break-even | Gap | Recommendation |
|--------|---------------|---------------|-----|----------------|
| {metric} | {current} | {new breakeven} | {over/under by X} | {suggested new target} |
```

6. Ask: "Want to revise these targets, or keep current targets with the noted risk?"
7. If revise → update Goals & KPIs section
