# Business.md Output Template

Agent-readable reference for Phase 8 of the business-context-gatherer skill.
Use this template to generate the `context/business.md` file from interview answers.

Replace all `{placeholders}` with actual values. Remove HTML comments after populating.
Mark unanswered items as `[Not provided — ask in follow-up]`.

---

## Template

```markdown
# Business Context

Strategic business context for Google Ads optimization. Claude agents and skills reference this file to make business-aligned recommendations.

---

## Account

| Field | Value |
|-------|-------|
| Client Name | {client_name} |
| Vertical | {leadgen_b2b / leadgen_b2c / saas / ecommerce} |
| B2B / B2C | {b2b / b2c / both} |
| Account Age | {account_age} |
| Last Updated | {YYYY-MM-DD} |
| Interview Mode | {full / quick / update} |

---

## Business Model

### What We Sell
{description_of_products_or_services}

### Who We Sell To
{target_audience_verticals_customer_profile}

### Key Metrics

| Metric | Value |
|--------|-------|
| Average Order Value / Deal Value / ARPU | {amount} |
| Sales Cycle | {duration} |
<!-- Ecommerce only -->
| Return Rate | {percentage} |
| Repeat Purchase Rate | {percentage} |
<!-- Lead Gen only -->
| Lead Qualification Stages | {stages} |
| Sales Team Size | {number} |
<!-- SaaS only -->
| Pricing Tiers | {description} |
| Free Trial / Freemium / Demo | {model} |
| Current Customer Count | {number} |

---

## Unit Economics

### {Vertical} Economics

| Metric | Value | Source |
|--------|-------|--------|
<!-- Ecommerce -->
| AOV | {amount} | Backend |
| Gross Profit per Order | {amount} | Calculated |
| Gross Margin % | {percentage} | Calculated |
| Break-even ROAS | {percentage} | Calculated |
| Adjusted Break-even ROAS (with returns) | {percentage} | Calculated |
| Target ROAS (operational) | {percentage} | Calculated |
| Current Google Ads ROAS | {percentage} | Google Ads |
<!-- Lead Gen -->
| Average Deal Value | {amount} | CRM |
| Profit Margin % | {percentage} | Finance |
| Profit per Deal | {amount} | Calculated |
| Lead-to-Sale Rate | {percentage} | CRM |
| Break-even CPL | {amount} | Calculated |
| Operational Target CPL | {amount} | Calculated |
| Current Google Ads CPA | {amount} | Google Ads |
<!-- SaaS -->
| ARPU | {amount} | Calculated |
| Monthly Churn Rate | {percentage} | Product Analytics |
| Customer Lifetime (months) | {number} | Calculated |
| LTV | {amount} | Calculated |
| Max CAC (3:1 rule) | {amount} | Calculated |
| Current CAC | {amount} | Finance + Ads |
| LTV:CAC Ratio | {ratio} | Calculated |
| CAC Payback (months) | {number} | Calculated |

### Viability Assessment
**Status:** {Go / Conditional Go / No-Go}
**Notes:** {explanation_and_any_warnings}

### Calculation Details
{show_the_math_for_auditability}

---

## Goals & KPIs

### Primary Focus
**Goal Type:** {Growth / Efficiency / Balanced}
**Primary KPI:** {metric} — Target: {value}

### Performance Targets

| Metric | Current | Target | Hard Constraint |
|--------|---------|--------|-----------------|
| {primary_kpi} | {current} | {target} | {constraint_or_dash} |
| {guardrail_1} | {current} | {threshold} | {constraint_or_dash} |
| {guardrail_2} | {current} | {threshold} | {constraint_or_dash} |

### Hard Constraints
<!-- Non-negotiable limits -->
- {constraint_1}
- {constraint_2}

### Budget
{budget_details_capped_or_uncapped}

### Review Cadence
| Review Type | Frequency |
|-------------|-----------|
| Performance check | {Weekly / Bi-weekly} |
| Stakeholder review | {Monthly} |
| Goal revision | {Quarterly} |

---

## Campaign Priorities

### Priority Ranking
1. {campaign_name} — {reason}
2. {campaign_name} — {reason}
3. {campaign_name} — {reason}

### Keyword Theme Priorities
1. {theme_1}
2. {theme_2}

### What NOT to Prioritize
- {campaign_or_theme} — {reason}

### Upcoming Launches or Changes
- {planned_changes}

---

## Competitive Landscape

### Strategy
**Approach:** {Aggressive / Defensive / Opportunistic}

### Priority Competitors
1. {competitor_name} — Win theme: {differentiation}
2. {competitor_name} — Win theme: {differentiation}
3. {competitor_name} — Win theme: {differentiation}

### General Differentiation
{key_differentiators_bullet_list}

### Brand Bidding
- Competitors bidding on our brand: {yes_no_details}
- Our brand bidding on competitors: {yes_no_details}

---

## Historical Context

### What Has Been Tried

| Test | Date | Result | Learning |
|------|------|--------|----------|
| {test_description} | {date} | {Success / Failed} | {key_learning} |

### What Works Well
- {item}

### What Has Not Worked
- {item}

### Known Constraints
- {item}

---

## Seasonal Patterns

### Pattern Type
**Seasonality:** {Strong / Mild / None}

### Calendar

| Period | Timing | Impact | Strategy Adjustment |
|--------|--------|--------|-------------------|
| Peak | {months_or_events} | {impact_description} | {how_to_adjust} |
| Slow | {months_or_events} | {impact_description} | {how_to_adjust} |

### Upcoming Events (Next 90 Days)
- {event_with_date}

---

## Organizational Constraints

| Constraint | Details |
|-----------|---------|
| Ad Copy Approval | {process_and_turnaround} |
| Landing Page Changes | {turnaround_time} |
| Brand Guidelines | {restrictions} |
| Team Dependencies | {who_is_involved} |
| Reporting Cadence | {frequency} |

---

## Notes for Claude

### Decision-Making Guidance
- {guidance_item}

### Recommendation Tone
- Current tone: {Aggressive / Balanced / Conservative — derived from goal type}
- Risk tolerance: {High / Medium / Low — derived from goal type}

### Things to Always Include
- Business impact estimate
- Implementation difficulty
- Known constraints that affect recommendation
- Alignment with current phase goals

### Things to Never Do
- {restriction}

---

## Gaps

**Items flagged for follow-up:**

| Section | Gap | Priority |
|---------|-----|----------|
| {section_name} | {what_is_missing} | {Critical / Warning / Info} |

---

*Last updated: {YYYY-MM-DD}*
*Next review: {YYYY-MM-DD_plus_90_days}*
*Generated by /business-context-gatherer*
```

---

## Section Notes

### Backward Compatibility
The template preserves key headers that downstream skills grep for:
- `## Goals & KPIs` with `### Performance Targets` table
- `## Campaign Priorities` with ranked list
- `## Competitive Landscape` / `### Strategy`
- `## Historical Context` with test table

### Conditional Sections
- Unit Economics metrics table: include only the rows matching the selected vertical
- Business Model key metrics: include only vertical-specific rows
- Seasonal Calendar table: only if seasonality is Strong or Mild
- Act Now section: skip if seasonality is None

### Placeholder Rules
- Mark every unanswered field as `[Not provided — ask in follow-up]`
- Remove HTML comments (<!-- -->) from the final output
- Remove unused vertical-specific rows
