# Execute — Viability Report (E05)

Generates a stakeholder-facing viability report. Used when `/strategy-specialist --execute viability-report` is invoked.

## Flow

1. Read business.md (Unit Economics + Goals & KPIs sections)
2. Read latest strategy audit results (if available from `context/analysis/strategy-audit.md`)
3. Generate the report
4. Write to `context/analysis/strategy-viability.md`

## Report Template

```markdown
# Advertising Viability Report

**Client:** {client name}
**Date:** {YYYY-MM-DD}
**Prepared by:** {user / Claude}
**Vertical:** {vertical}

---

## Executive Summary

**Viability Verdict: {Go / Conditional Go / No-Go}**

{2-3 sentence summary of whether this business can profitably advertise on Google Ads, and why.}

---

## Unit Economics Overview

| Metric | Value | Benchmark | Status |
|--------|-------|-----------|--------|
| {key metric 1} | {value} | {threshold} | {Pass/Warn/Fail} |
| {key metric 2} | {value} | {threshold} | {Pass/Warn/Fail} |
| ... | ... | ... | ... |

### Key Finding
{1-2 sentences on the most important unit economics insight}

---

## Target Assessment

| Target | Value | Break-even | Margin | Status |
|--------|-------|-----------|--------|--------|
| {CPA/ROAS/POAS} | {target} | {breakeven} | {gap} | {Pass/Warn/Fail} |

### Implied PAR: {value}%
{One sentence on what this means: "X% of gross profit is allocated to acquisition, retaining Y% as net profit."}

---

## Risk Factors

{Numbered list of risks that could change the verdict}

1. **{Risk}:** {explanation and impact}
2. ...

---

## Recommendations

{Numbered list of actions, ordered by priority}

1. **{Action}** — {expected impact}
2. ...

---

## What Needs to Change for Improvement

{If Conditional Go or No-Go, list specific business changes needed}

| Change | Current | Required | Impact on Viability |
|--------|---------|----------|---------------------|
| {change} | {current value} | {required value} | {how it changes the verdict} |

---

## Assumptions

{List all assumptions used in this analysis}

| Assumption | Value | Source | Confidence |
|-----------|-------|--------|------------|
| {assumption} | {value} | {source} | {High/Medium/Low} |

---

## Next Review

**Recommended review date:** {today + 90 days}
**Trigger for earlier review:** {list of triggers: pricing change, churn spike, etc.}
```

## After Writing

1. Confirm to user: "Viability report written to `context/analysis/strategy-viability.md`"
2. Log to memory: "Strategy viability report generated — Verdict: {verdict}"
