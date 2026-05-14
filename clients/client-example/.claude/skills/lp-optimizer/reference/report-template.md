# LP Optimizer -- Report Template

All optimization guidance reports follow this structure. Adapt sections based on the specific action.

## Report File: `context/analysis/lp-optimize-{action}.md`

```markdown
# LP Optimization Guidance — {Action Name}

**Date:** {YYYY-MM-DD}
**URL:** {target URL}
**Vertical:** {lead gen / SaaS / ecommerce}
**Action:** {action code} ({LP-EXX})
**Audit Report:** {referenced / not available}
**Audit Score:** {X% (Grade) if available}

---

## Cross-skill Context

> Render this section ONLY when Phase 0.5.4 of SKILL.md captured fresh peer findings overlapping the campaigns this LP serves, OR when a soft-warn fired from the mutation-sensitivity matrix. Otherwise omit the entire section. Format defined in `reference/handoff-matrix.md` § 4.

The following peer findings are fresh and overlap the campaigns this LP serves. The LP fixes recommended below should be evaluated alongside (or sequenced with) these signals.

| Peer | Report date | Finding | How it interacts with this LP work |
|---|---|---|---|
| /quality-score-auditor | {date} | LPE Below-Avg on {N} keywords / {imps} imps | Applying these LP fixes targets the QS Auditor's LPE flag — re-run `/quality-score-auditor` 14 days post-implementation to verify recovery |
| {other peer} | {date} | {finding} | {interaction} |

**Recent peer mutations (soft-warn):**
- ⚠ {one-line warn from mutation-sensitivity matrix, when any}

---

## Issue Summary

{What's wrong, quantified where possible. Include data from audit findings.}

| Finding | Source | Impact |
|---------|--------|--------|
| {specific issue} | {audit ID or Chrome DevTools observation} | {conversion/revenue impact} |

---

## Root Cause Analysis

{Why the issues exist — not just symptoms but underlying causes.}

| Issue | Symptom | Root Cause |
|-------|---------|-----------|
| {issue} | {what you see} | {why it happens} |

---

## Fix Recommendations

### P1: Quick Wins (do this week)

| # | Fix | Current State | Recommended | Owner | Expected Impact |
|---|-----|--------------|-------------|-------|-----------------|
| 1 | {description} | {before} | {after} | {role} | {estimated lift} |

### P2: Strategic Fixes (next 2 weeks)

| # | Fix | Current State | Recommended | Owner | Expected Impact |
|---|-----|--------------|-------------|-------|-----------------|
| 1 | {description} | {before} | {after} | {role} | {estimated lift} |

### P3: Technical / Long-term

| # | Fix | Current State | Recommended | Owner | Expected Impact |
|---|-----|--------------|-------------|-------|-----------------|
| 1 | {description} | {before} | {after} | {role} | {estimated lift} |

---

## Implementation Notes

### For the Marketer
{Copy changes, CTA rewrites, content additions}

### For the Developer
{Technical changes, code modifications, speed optimizations}

### For the Designer
{Layout changes, visual improvements, mobile adaptations}

### For the Account Manager
{Google Ads changes: URL updates, ad copy alignment, campaign adjustments}

---

## Expected Impact

{Overall expected improvement if P1+P2 fixes are implemented.}

| Metric | Current | Expected After Fixes | Basis |
|--------|---------|---------------------|-------|
| {metric} | {current value} | {expected value} | {reasoning} |

---

## Screenshots

{Before-state screenshots captured from Chrome DevTools. Include captions explaining the issue.}

### {Issue Name}
{Screenshot reference + caption}

---

## Next Steps

| Action | Command | Priority |
|--------|---------|----------|
| Re-audit after fixes | `/lp-audit` | After P1 fixes implemented |
| {other action} | {command} | {priority} |

---

## Data Freshness

| Source | Used | Date |
|--------|------|------|
| Audit report | {yes/no} | {date of audit} |
| Chrome DevTools | {yes/no} | {today} |
| ads.csv | {yes/no} | {date} |
| keywords.csv | {yes/no} | {date} |
```
