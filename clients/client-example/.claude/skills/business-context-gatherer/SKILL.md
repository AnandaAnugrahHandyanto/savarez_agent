---
name: business-context-gatherer
description: Interview the user to create or update context/business.md with business model, unit economics, goals, and strategic context. Use for client onboarding or business briefings.
argument-hint: "[--quick] [--update]"
---

# Business Context Gatherer Skill

Conduct a structured interview to create or update `context/business.md` — the most important context file in the project. Every downstream skill and agent reads this file for targets, constraints, and strategic context.

The interview covers 8 sections informed by proven Google Ads frameworks: unit economics calculation, goal-setting pyramid, constraint hierarchy, and awareness stage positioning.

## Command Format

```
/business-context-gatherer [--quick] [--update]
```

**Examples:**
- `/business-context-gatherer` — Full interactive interview (all 8 sections)
- `/business-context-gatherer --quick` — Sections 1-3 only (Business Model, Unit Economics, Goals)
- `/business-context-gatherer --update` — Review existing business.md, update only what changed

---

## Domain Rules (Non-Negotiable)

These rules override all other instructions during the interview:

1. **Never skip unit economics.** If the user cannot provide inputs, mark as `[Not provided — ask in follow-up]` and flag prominently in the Gaps section with Critical priority. Without margins, CLV, and CAC, no downstream skill can set meaningful targets.

2. **Goals must be specific and measurable.** Push for specific numbers. "Grow conversions" is not acceptable. "Grow monthly conversions from 100 to 150 by Q3" is acceptable. Apply the SMART framework (Specific, Measurable, Achievable, Relevant, Time-bound).

3. **Validate feasibility immediately.** If targets are mathematically impossible given the collected unit economics (e.g., target CPA below cost to deliver), flag IMMEDIATELY during the Goals phase. Do not wait for the Validation phase.

4. **Do not assume, ask.** The user's stated context overrides any data in CSV files or other context files. If there is a conflict between stated context and data, note it and ask the user which is correct.

5. **Flag gaps, do not skip.** Every unanswered question must appear in the Gaps section with a priority level. Never silently omit a question because the user did not answer it.

---

## Process

### Phase 0: Prerequisites Check

No required context files — this skill creates the foundational file.

Check for optional files that can pre-populate answers:

| File | If Found | Used For |
|------|----------|----------|
| `context/business.md` | Enable Update mode option in Phase 1 | Pre-fill known answers |
| `context/brand.md` | Pre-populate company name, products, target audience | Phase 2 Business Model |
| `context/google-ads/data/campaigns.csv` | Pre-populate campaign priority list | Phase 5 Campaign Priorities |
| `context/google-ads/data/keywords.csv` | Pre-populate keyword theme priorities | Phase 5 Campaign Priorities |

---

### Phase 1: Entry Gate

#### Question 1: Create or Update?

**Only ask if `context/business.md` exists.** If it does not exist, skip directly to Question 2 in Create mode.

**Question:** "A business.md file already exists. What would you like to do?"

| Option | Description |
|--------|-------------|
| Update existing (Recommended) | Review each section, update only what has changed. Faster if most info is current. |
| Start fresh | Discard existing file and run the full interview from scratch. |

Use AskUserQuestion with these 2 options. multiSelect: false.

**If Update selected:** Read `context/business.md` and parse by `##` headers. Store each section's current content for comparison in later phases. See [Update Mode Flow](#update-mode-flow) for section-by-section behavior.

#### Question 2: Interview Mode

**Skip if `--quick` or `--update` flag was provided.** Use the flag value directly.

**Question:** "How comprehensive should this interview be?"

| Option | Description |
|--------|-------------|
| Full (Recommended) | All 8 sections. Best for new accounts or major strategic changes. |
| Quick | Sections 1-3 only: Business Model, Unit Economics, Goals. Best for quick setup. |
| Custom | Choose which sections to cover. |

Use AskUserQuestion with these 3 options. multiSelect: false.

If Custom is selected, present a follow-up:

**Question:** "Which sections do you want to cover?"

| Option | Description |
|--------|-------------|
| Business Model | What you sell, who you sell to, key metrics |
| Unit Economics | Margins, break-even targets, viability assessment |
| Goals & KPIs | Primary KPI, targets, constraints, budget |
| Campaign Priorities | Campaign ranking, deprioritization, upcoming launches |
| Competitive Landscape | Competitors, differentiation, bidding strategy |
| Historical Context | Past tests, lessons learned, known issues |
| Seasonal Patterns | Peak/slow periods, upcoming events |
| Organizational Constraints | Approval process, team dependencies, reporting |

Use AskUserQuestion with these 8 options. multiSelect: true.

**Important:** Unit Economics is always included regardless of selection. If the user deselects it, add it back and show: "Unit Economics is always included — it's required for target validation."

#### Question 3: Business Vertical

This is a decision gate that routes to the correct question bank in Phase 3.

**Question:** "What is the primary business model?"

| Option | Description |
|--------|-------------|
| Lead Gen (B2B) | Generates leads for a sales team. Revenue from closed deals. |
| Lead Gen (B2C) | Generates consumer leads (insurance, education, home services). |
| SaaS | Recurring subscriptions. Free trial or freemium model. |
| Ecommerce | Sells physical or digital products online. |

Use AskUserQuestion with these 4 options. multiSelect: false.

Store the selected vertical — it determines which questions are asked in Phase 3 and which calculation formulas are used.

---

### Phase 2: Business Model

Read `reference/unit-economics-questions.md` Section "Vertical Classification".

**If `context/brand.md` exists:** Read it and pre-populate company name, products/services description, and target audience. Present pre-populated values to the user for confirmation.

**If Update mode:** Show the current Business Model section from existing business.md and ask:

**Question:** "Here's your current Business Model section. Is this still accurate?"

| Option | Description |
|--------|-------------|
| Yes, keep as-is | Skip to next section |
| Needs updating | I'll ask specific questions about what changed |

Use AskUserQuestion with these 2 options. multiSelect: false.

If "Yes, keep as-is" → preserve existing content and skip to Phase 3.

**If Create mode or "Needs updating":**

**Question:** "Tell me about your business:"

Present as a structured free-text prompt:

```
Please provide:

1. What do you sell? (Products, services, subscriptions — be specific)
2. Who do you sell to? (B2B/B2C, specific verticals/industries, customer profile)
3. What is your average order value / deal value / ARPU?
4. What is your typical sales cycle? (Immediate, days, weeks, months)
```

This is a free-text question. The user types their answers directly.

**Vertical-specific follow-up:**

After the core questions, ask vertical-specific follow-ups based on Phase 1 selection:

**Ecommerce follow-up question:** "Any additional ecommerce details?"

| Option | Description |
|--------|-------------|
| Skip for now | Will use defaults, can update later |

The user can type details instead: product categories, bestsellers, return rate, repeat purchase rate.

**Lead Gen follow-up question:** "Any additional lead gen details?"

| Option | Description |
|--------|-------------|
| Skip for now | Will use defaults, can update later |

The user can type details instead: lead qualification stages (MQL, SQL, Opportunity, Won), sales team size, average response time.

**SaaS follow-up question:** "Any additional SaaS details?"

| Option | Description |
|--------|-------------|
| Skip for now | Will use defaults, can update later |

The user can type details instead: pricing tiers and most popular plan, free trial vs freemium vs demo-first, current customer count.

---

### Phase 3: Unit Economics

Read `reference/unit-economics-questions.md` for the vertical-specific question bank.

**Domain rule reminder: NEVER skip this section.** Even in Quick mode, Unit Economics is always included.

**If Update mode:** Show the current Unit Economics section from existing business.md and ask:

**Question:** "Here's your current Unit Economics section. Has anything changed? (pricing, margins, churn, sales process)"

| Option | Description |
|--------|-------------|
| No changes, keep as-is | Skip to next section |
| Numbers have changed | I'll ask for updated inputs |

Use AskUserQuestion with these 2 options. multiSelect: false.

If "No changes" → preserve existing content, but still run the viability check in Phase 7.

**If Create mode or "Numbers have changed":**

Present the vertical-specific input table from the reference file. Use a single free-text question with a structured prompt.

**For Ecommerce:**

**Question:** "I need your unit economics to calculate viable Google Ads targets. Please provide these numbers:"

Present as structured prompt:

```
1. Average Order Value (AOV): Total revenue / Total orders (last 90 days)
2. COGS per order: Direct product cost per average order
3. Shipping cost per order: Average shipping cost paid by business
4. Payment processing fee: Average gateway fee per order
5. Return rate: % of orders returned (last 90 days)
6. Current Google Ads ROAS: Conv value / Cost (non-branded campaigns)

It's OK to say "I don't know" for any of these.
```

This is a free-text question. The user types their numbers directly.

**For Lead Gen:**

**Question:** "I need your unit economics. Please provide:"

Present as structured prompt:

```
1. Average deal value: Revenue from a typical closed deal
2. Profit margin %: (Revenue - delivery costs) / Revenue
3. Lead-to-sale rate: Closed deals / Total leads (last 6 months)
4. Sales cycle length: Average days from lead to close
5. Sales team response time: Average time from lead to first contact
6. Current Google Ads CPA: Cost / Conversions (non-branded campaigns)

It's OK to say "I don't know" for any of these.
```

This is a free-text question. The user types their numbers directly.

**For SaaS:**

**Question:** "I need your unit economics. Please provide:"

Present as structured prompt:

```
1. Monthly Recurring Revenue (MRR): Current total MRR
2. Active paying customers: Current count
3. Monthly churn rate: Customers lost / Total customers (avg last 6 months)
4. Gross margin %: (Revenue - infrastructure costs) / Revenue
5. Current CAC: Total acquisition spend / New paying customers (last 6 months)
6. Free-to-paid conversion rate: Paying / Free trial signups

It's OK to say "I don't know" for any of these.
```

This is a free-text question. The user types their numbers directly.

#### 3.1 Calculate and Present Results

After collecting inputs, immediately run the calculations from `reference/unit-economics-questions.md` and present:

```markdown
## Unit Economics Calculated

| Metric | Value |
|--------|-------|
| {calculated metrics for the vertical} |

**Viability Assessment:** {Go / Conditional Go / No-Go}
```

#### 3.2 Inline Red Flag Detection

Read `reference/validation-rules.md` "Viability Thresholds" section. Check results against thresholds.

**If Critical red flags detected:**

Show immediately:

```markdown
⚠️ **Warning:** {metric} is below the viability threshold.

{Specific message from validation-rules.md}

This limits Google Ads campaign options. Details will appear in the Gaps section.
```

**If "I don't know" on any input:**

Mark as `[Not provided — ask in follow-up]` and show:

```markdown
⚠️ **Unit economics are incomplete.** Missing: {list of missing inputs}.

Downstream targets and recommendations will be less reliable until these are provided.
```

---

### Phase 4: Goals & KPIs

Read `reference/goals-kpis-questions.md`.

**If Quick mode:** This is the last section. After Phase 4, skip to Phase 7 (Validation).

**If Update mode:** Show current Goals & KPIs section and ask if it's still accurate (same pattern as Phase 2/3).

**If Create mode or needs updating:**

#### Question 1: Primary Goal Type

**Question:** "What is your primary Google Ads objective?"

| Option | Description |
|--------|-------------|
| Growth | Scale volume: more conversions, more revenue, new markets. Accept higher costs for scale. |
| Efficiency | Optimize ROI: lower CPA, higher ROAS, better margins. Accept lower volume for efficiency. |
| Balanced | Both growth and efficiency matter roughly equally. |

Use AskUserQuestion with these 3 options. multiSelect: false.

#### Question 2: Primary KPI

**Question:** "What is your single most important metric?"

| Option | Description |
|--------|-------------|
| CPA (Cost Per Acquisition) | Target cost to acquire a customer or lead |
| ROAS (Return On Ad Spend) | Target return per dollar of ad spend |
| Conversions (Volume) | Target number of conversions per month |
| Revenue / Conversion Value | Target revenue from Google Ads |

Use AskUserQuestion with these 4 options. multiSelect: false.

#### Question 3: Specific Targets

Based on the primary KPI selection, ask for specific targets:

**Question:** "Set your specific targets:"

Present as structured prompt:

```
Based on your {primary KPI} focus:

1. Primary KPI target: (e.g., CPA under $200, ROAS above 400%)
2. Hard constraint (non-negotiable limit): (e.g., Max CPA $200, Min ROAS 300%)
3. Monthly budget: (e.g., $50,000 / Uncapped / Flexible)
4. Growth target: (e.g., 20% more conversions QoQ, reach 500 conversions/month)
```

This is a free-text question. The user types their target numbers directly.

#### 4.1 Inline Feasibility Check

Compare stated targets against calculated unit economics from Phase 3:

- If target CPA below calculated break-even → show Critical warning from `reference/validation-rules.md`
- If target ROAS close to break-even → show Warning
- If budget insufficient for stated conversion target → show Warning

Present any issues and ask:

**Question:** "Would you like to adjust your targets based on this analysis?"

| Option | Description |
|--------|-------------|
| Keep targets as stated | I understand the risk, keep my stated targets |
| Adjust targets | Let me revise my numbers |

Use AskUserQuestion with these 2 options. multiSelect: false.

#### Question 4: Guardrail KPIs

**Question:** "What guardrails should protect against over-optimization?"

Present guardrail suggestions based on goal type:

```
Based on your {Growth/Efficiency} focus, recommended guardrails:

Growth primary → Set efficiency floors:
  - Minimum ROAS: {calculated from unit economics, or ask}
  - Maximum CPA: {calculated from unit economics, or ask}

Efficiency primary → Set volume floors:
  - Minimum conversions/month: ___
  - Minimum impression share: ___
```

| Option | Description |
|--------|-------------|
| Use recommended guardrails | Apply the calculated guardrails |
| Set custom guardrails | I'll specify my own thresholds |

Use AskUserQuestion with these 2 options. multiSelect: false.

---

### Phase 5: Campaign Priorities + Competitive Landscape

**Skip if Quick mode.**

Read `reference/strategic-context-questions.md`.

**If Update mode:** Show current sections and ask if still accurate (same pattern).

#### 5.1 Campaign Priorities

**If `context/google-ads/data/campaigns.csv` exists:** Read and present a summary table of campaigns with key metrics (spend, conversions, CPA).

**Question:** "Rank your campaigns by optimization priority. Which campaigns should get the most attention?"

Present pre-populated campaign data if available:

```
Current campaigns from your account:

| Campaign | Spend | Conv | CPA |
|----------|-------|------|-----|
| {from campaigns.csv} |

1. Which campaigns should get the MOST optimization attention? (ranked)
2. Which campaigns should be DEPRIORITIZED or ignored?
3. Any UPCOMING campaign launches or changes?
```

This is a free-text question. The user types their priority ranking directly.

#### 5.2 Competitive Landscape

**Question:** "Tell me about your competitive landscape."

Present as structured prompt:

```
1. Top 3-5 competitors in paid search: (name and URL)
2. How do you differentiate from each?
3. Are competitors bidding on your brand terms?
4. Are you bidding on competitor brand terms?
```

This is a free-text question. The user types their competitive details directly.

#### Question: Competitive Strategy

**Question:** "What is your competitive bidding strategy?"

| Option | Description |
|--------|-------------|
| Aggressive | Bid on competitor terms, outbid on shared keywords, maximize impression share |
| Defensive | Protect brand, maintain position, don't overpay for competitive terms |
| Opportunistic | Bid on competitor terms only when profitable, avoid bidding wars |

Use AskUserQuestion with these 3 options. multiSelect: false.

---

### Phase 6: Historical Context + Seasonal Patterns + Organizational Constraints

**Skip if Quick mode.**

Read `reference/strategic-context-questions.md` for question frameworks.

**If Update mode:** Show current sections and ask if still accurate (same pattern).

#### 6.1 Historical Context

**Question:** "What has been tried before in this Google Ads account?"

Present as structured prompt:

```
1. How long has the account been running?
2. Past tests and their results: (what worked, what failed, key learnings)
3. Known issues or recurring problems:
4. Things that have consistently worked well:
5. Biggest past mistakes or wasted spend:
```

| Option | Description |
|--------|-------------|
| Share history | I'll provide account history |
| No significant history | Account is new or no notable experiments |

Use AskUserQuestion with these 2 options. multiSelect: false.

#### 6.2 Seasonal Patterns

**Question:** "Are there seasonal patterns that affect your business?"

| Option | Description |
|--------|-------------|
| Strong seasonality | Clear peak and slow periods (e.g., retail, travel, education) |
| Mild seasonality | Some variation but mostly consistent |
| No significant seasonality | Business is relatively flat year-round |

Use AskUserQuestion with these 3 options. multiSelect: false.

**If Strong or Mild selected, follow-up:**

**Question:** "Describe your seasonal patterns:"

```
1. Peak periods: (which months/events)
2. Slow periods: (which months)
3. Upcoming events in the next 90 days:
4. Any seasonal pricing or promotions:
```

This is a free-text question. The user types their seasonal details directly.

#### 6.3 Organizational Constraints

**Question:** "What organizational constraints affect Google Ads work?"

Present as structured prompt:

```
1. Ad copy approval: (None / Internal review / Legal review / Client approval — turnaround time?)
2. Landing page changes: (Same day / Days / Weeks / Cannot change)
3. Brand guidelines: (None / Light / Strict — any specific restrictions?)
4. Team dependencies: (Dev for tracking, Design for creatives, Sales for lead follow-up)
5. Reporting cadence: (Weekly / Bi-weekly / Monthly)
```

| Option | Description |
|--------|-------------|
| Describe constraints | I'll provide organizational details |
| No significant constraints | No approval bottlenecks or dependencies |

Use AskUserQuestion with these 2 options. multiSelect: false.

---

### Phase 7: Validation & Feasibility Check

This phase is automated — no user interaction unless issues are found.

Read `reference/validation-rules.md` for all checks.

#### 7.1 Run Cross-Section Checks

**Check 1: Economics vs Targets**
- Compare target CPA/ROAS against calculated break-even from Phase 3
- Use the check conditions and messages from `reference/validation-rules.md` "Cross-Section Validation Checks"

**Check 2: Budget vs Goals**
- If monthly budget is capped, calculate: Budget / Target CPA = max conversions possible
- Compare against stated growth target

**Check 3: Capacity vs Volume** (Lead Gen only)
- If sales team capacity is provided, compare against target lead volume

**Check 4: Goal Specificity**
- Verify goals pass SMART criteria
- Verify guardrails are set

**Check 5: Completeness**
- Count all `[Not provided — ask in follow-up]` gaps
- Classify each using priority rules from `reference/validation-rules.md` "Gap Flagging Rules"

#### 7.2 Present Validation Results

```markdown
## Feasibility Validation

| Check | Status | Details |
|-------|--------|---------|
| Unit Economics Viability | {Pass / Warning / Fail} | {details} |
| Target Feasibility | {Pass / Warning / Fail} | {details} |
| Budget Sufficiency | {Pass / Warning / N/A} | {details} |
| Sales Capacity | {Pass / Warning / N/A} | {details} |
| Goal Specificity | {Pass / Warning} | {details} |
| Data Completeness | {X/Y sections complete} | {gap count} gaps |

### Issues Found
{If any checks failed or warned, list with recommendations}

### Gaps Requiring Follow-up
{List all [Not provided] items with section and priority}
```

**If Critical issues found:**

**Question:** "There are critical issues that may affect recommendations. Would you like to adjust any answers before I generate the business.md file?"

| Option | Description |
|--------|-------------|
| Generate anyway | I understand the risks, proceed with current answers |
| Go back and adjust | Let me fix the issues first |

Use AskUserQuestion with these 2 options. multiSelect: false.

If "Go back and adjust" → ask which section to revisit and re-run that phase.

---

### Phase 8: Output Generation + Summary

#### 8.1 Generate business.md

Read `reference/business-md-template.md` for the output template.

Populate the template with all interview answers:
- Replace all `{placeholders}` with actual values
- Remove HTML comments
- Remove vertical-specific rows that don't apply
- Mark unanswered items as `[Not provided — ask in follow-up]`
- Set `Last updated` to today's date
- Set `Next review` to today + 90 days
- Derive `Notes for Claude` section from goal type:
  - Growth → Aggressive tone, high risk tolerance
  - Efficiency → Conservative tone, low risk tolerance
  - Balanced → Balanced tone, medium risk tolerance

#### 8.2 Handle Existing File

**If Update mode:**
- Show a change summary before writing:

```markdown
## Changes Made

| Section | Status |
|---------|--------|
| Business Model | {Unchanged / Updated: description} |
| Unit Economics | {Unchanged / Updated: description} |
| Goals & KPIs | {Unchanged / Updated: description} |
| ... |
| Gaps | {X resolved, Y new} |
```

**Question:** "Here's what changed. Ready to save?"

| Option | Description |
|--------|-------------|
| Save changes | Write the updated business.md |
| Review first | Show me the full file before saving |

Use AskUserQuestion with these 2 options. multiSelect: false.

**If Create mode and business.md already exists:**
- Show warning: "This will overwrite the existing business.md."
- Proceed after confirmation (already given in Phase 1 "Start fresh" selection).

#### 8.3 Save File

Write the generated content to `context/business.md`.

#### 8.4 Present Summary

```markdown
## Business Context Complete

### Output
- **File:** `context/business.md`
- **Vertical:** {leadgen / saas / ecommerce}
- **Interview Mode:** {full / quick / update}
- **Sections Completed:** {X}/8

### Feasibility Summary

| Check | Status |
|-------|--------|
| Unit Economics | {Pass / Warning / Fail} |
| Target Feasibility | {Pass / Warning / Fail} |
| Budget Sufficiency | {Pass / Warning / N/A} |
| Completeness | {X}% |

### Gaps to Address
{If any:}
1. {gap} — Priority: {Critical / Warning / Info}

### Suggested Next Steps
1. Review `context/business.md` for accuracy
2. {If gaps exist:} Address Critical gaps in a follow-up session (`/business-context-gatherer --update`)
3. Run `/gads-context` to pull Google Ads performance data
4. Run `/ads-context-gatherer [URL]` to gather brand context (if not done)
5. Run `/offer-maker angles` to extract message angles
```

---

## Update Mode Flow

When the user selects "Update existing" in Phase 1:

1. Read existing `context/business.md`, parse by `##` headers
2. For each section included in the interview mode:
   a. Present the current section content in a formatted block
   b. Ask: "Is this section still accurate?"
   c. If "Yes, keep as-is" → preserve existing content unchanged
   d. If "Needs updating" → run the full question set for that section only
3. After all sections: check for `[Not provided — ask in follow-up]` gaps from the previous file
4. For each gap: "You previously couldn't provide {X}. Do you have this information now?"
5. Check for new sections not in the existing file → ask those questions fresh
6. Run Phase 7 validation on the combined (updated + preserved) data
7. Write output with change summary

---

## Error Handling

| Error | Message |
|-------|---------|
| User says "I don't know" for Unit Economics | "Marked as [Not provided — ask in follow-up]. **Warning:** Unit economics are incomplete. This limits target validation and downstream recommendations." |
| User says "I don't know" for Goals | "Marked as [Not provided — ask in follow-up]. **Warning:** Without specific targets, agents cannot validate recommendations against goals." |
| Feasibility check fails | "Your target {metric} of {value} appears to be {below break-even / mathematically impossible} given your unit economics. Would you like to adjust the target, or keep it and note the risk?" |
| Existing business.md has unrecognized format | "The existing business.md has a non-standard format. I'll preserve all content and add missing sections. Some sections may need manual merging." |
| User cancels mid-interview | "Interview stopped. No changes have been saved. Run `/business-context-gatherer` again to restart." |

---

## Integration Points

### Reads from (pre-population):
- `context/business.md` — Previous version (for Update mode)
- `context/brand.md` — Company name, products, target audience
- `context/google-ads/data/campaigns.csv` — Campaign list for priority ranking
- `context/google-ads/data/keywords.csv` — Keyword themes
- `reference/unit-economics-questions.md` — Vertical-specific question banks and calculation formulas
- `reference/goals-kpis-questions.md` — Goal pyramid, KPI tiers, SMART validation
- `reference/strategic-context-questions.md` — Competition, campaigns, awareness stages, constraint hierarchy
- `reference/validation-rules.md` — Feasibility thresholds, red flags, cross-section checks
- `reference/business-md-template.md` — Output template

### Produces (writes to):
- `context/business.md` — The primary output file

### Downstream consumers:
- **ALL downstream skills** — Every skill reads `context/business.md` for targets, constraints, and strategic context
- `/gads-context` — Reads Performance Targets for comparison, Hard Constraints for flagging
- `/search-terms` — Reads CPA/ROAS targets from Performance Targets, business description for relevance judgment
- `/offer-maker angles` — Reads win themes from Competitive Landscape
- `/quality-score-auditor` — Reads priority campaigns, targets, constraints, competitor-campaign classification
- `/landing-page` and `/ecom-page` — Read business goals for page strategy
- All agents in `.claude/agents/` — Read constraints, priorities, targets

---

## Output Location

Output is written to `context/business.md` (overwrites existing file).
- Each run overwrites the previous version (this is intentional — business.md is a living document)
- The file includes a `Last updated` timestamp and `Next review` date
- Previous version can be recovered from git history
