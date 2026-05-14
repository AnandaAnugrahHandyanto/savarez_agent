# Validation Rules

Agent-readable reference for Phase 7 of the business-context-gatherer skill.
Distilled from: SOP_16 Phase 4 (viability checks) + SOP_17 Phase 5 (goal validation).

---

## Viability Thresholds by Vertical

### Ecommerce Red Flags

| Metric | Threshold | Severity | Recommendation |
|--------|-----------|----------|----------------|
| Gross margin % | Below 20% | Critical | Break-even ROAS > 500%. Review pricing, supplier costs, shipping strategy. Google Ads viability is limited. |
| Break-even ROAS | Above 500% | Critical | Nearly impossible on non-branded traffic. Fix margin structure before scaling ads. |
| Return rate | Above 25% | Warning | Returns erode margins significantly. Improve product descriptions, sizing guides, quality control. |
| AOV | Below $20 | Warning | Very low CPCs needed to hit targets. Consider bundles, upsells, free shipping thresholds. |

### Lead Gen Red Flags

| Metric | Threshold | Severity | Recommendation |
|--------|-----------|----------|----------------|
| Lead-to-sale rate | Below 10% | Critical | CPL gets compressed dramatically. Improve sales process, response time, lead qualification. |
| Profit margin % | Below 15% | Warning | Limited room for acquisition spend. Review pricing, delivery costs. |
| Sales response time | Above 24 hours | Warning | Lead quality degrades fast. Every hour of delay reduces close rate. |
| Deal value | Below $500 | Warning | Very tight CPL ceiling. Focus on higher-value services or bundles. |

### SaaS Red Flags

| Metric | Threshold | Severity | Recommendation |
|--------|-----------|----------|----------------|
| LTV:CAC ratio | Below 2:1 | Critical | Approaching break-even over full lifetime. Reduce CAC or improve retention/ARPU. |
| Monthly churn | Above 8% | Critical | Customer lifetime < 13 months. Fix product retention before scaling acquisition. |
| CAC payback | Above 18 months | Warning | Long payback strains cash flow. Improve conversion funnel, reduce CPC. |
| Free-to-paid rate | Below 5% | Warning | Acquisition funnel is leaking. Improve onboarding, trial experience. |

---

## Viability Assessment

| Result | Criteria | Action |
|--------|----------|--------|
| **Go** | All metrics above minimum thresholds | Set targets based on calculated thresholds. Proceed with campaign setup. |
| **Conditional Go** | Some metrics near thresholds (Warning level) | Set conservative targets. Schedule monthly review. Flag risks in business.md. |
| **No-Go** | Key metrics below thresholds (Critical level) | Present findings. Recommend fixing business fundamentals before committing ad spend. |

---

## Cross-Section Validation Checks

### Check 1: Economics vs Targets

| Condition | Severity | Message |
|-----------|----------|---------|
| Target CPA below calculated break-even CPL | Critical | "Target CPA of ${X} is below break-even CPL of ${Y}. This target is mathematically impossible without improving unit economics." |
| Target ROAS above adjusted break-even by less than 25% | Warning | "Target ROAS of {X}% leaves only {Y}% margin above break-even ({Z}%). Very little room for optimization." |
| Target CPA at or near break-even | Warning | "Target CPA of ${X} equals break-even CPL of ${Y}. Zero margin for error or profit." |
| No unit economics data provided | Critical | "Unit economics are incomplete. Cannot validate whether targets are feasible. All downstream recommendations will be less reliable." |

### Check 2: Budget vs Goals

| Condition | Severity | Message |
|-----------|----------|---------|
| Monthly budget / Target CPA < stated conversion target | Warning | "Budget of ${X}/month at ${Y} CPA allows maximum {Z} conversions. Stated target is {N} conversions. Budget is insufficient." |
| Budget is uncapped but no growth target set | Info | "No budget cap is set but no specific growth target either. Consider setting a volume target to measure progress." |

### Check 3: Capacity vs Volume (Lead Gen only)

| Condition | Severity | Message |
|-----------|----------|---------|
| Target lead volume exceeds stated sales capacity | Warning | "Target of {X} leads/month may exceed sales team capacity. Follow-up quality will degrade, reducing close rates." |
| No sales capacity information provided | Info | "Sales team capacity not documented. If leads increase significantly, verify the team can maintain response times." |

### Check 4: Goal Specificity

| Condition | Severity | Message |
|-----------|----------|---------|
| Primary KPI target is vague (e.g., "grow", "improve") | Warning | "Goal is not specific enough. Apply SMART criteria: What exact number? By when?" |
| No hard constraint set | Warning | "No hard constraint (max CPA / min ROAS) defined. Risk of unchecked spend during scaling." |
| Growth + Efficiency both set as primary | Warning | "You cannot maximize growth and efficiency simultaneously. Pick one as primary, use the other as guardrails." |
| No time-bound element in goals | Info | "Goals should have a deadline. Consider adding a review date or quarterly target." |

---

## Completeness Scoring

### Section Priority

| Section | Priority if Missing |
|---------|-------------------|
| Business Model | Critical — downstream skills need vertical classification |
| Unit Economics | Critical — no downstream skill can set meaningful targets without this |
| Goals & KPIs | Critical — agents cannot validate recommendations without targets |
| Campaign Priorities | Warning — agents default to equal priority across campaigns |
| Competitive Landscape | Warning — agents cannot craft differentiated messaging |
| Historical Context | Info — useful but agents can function without it |
| Seasonal Patterns | Info — agents default to no seasonality |
| Organizational Constraints | Info — agents default to no restrictions |

### Gap Flagging Rules

- Any `[Not provided]` in Unit Economics → Priority: **Critical**
- Any `[Not provided]` in Goals & KPIs → Priority: **Critical**
- Any `[Not provided]` in Business Model → Priority: **Warning**
- Any `[Not provided]` in Campaign Priorities or Competitive Landscape → Priority: **Warning**
- Any `[Not provided]` in Historical/Seasonal/Organizational → Priority: **Info**

---

## Common Failures to Check

| Failure | How to Detect | Message |
|---------|--------------|---------|
| Using revenue instead of gross profit | ROAS target set without margin context | "Ensure targets are based on gross margin, not revenue. High ROAS can still mean losses if margins are thin." |
| Goals set at break-even | Target CPA = break-even CPL | "Setting targets at break-even leaves no room for profit or optimization margin." |
| No guardrails set | Primary KPI defined but no secondary constraints | "Growth without efficiency guardrails risks spending spirals. Efficiency without volume guardrails risks market share loss." |
| Assuming linear growth | Growth target exceeds available search volume | "Budget increases face diminishing returns. Validate growth targets against available search volume and impression share." |
