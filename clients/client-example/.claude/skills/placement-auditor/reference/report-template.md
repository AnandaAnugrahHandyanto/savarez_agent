# Placement Auditor — Report Template

The report is **explain-then-action**: a reader who only reads the Executive Read at the top should still leave with the right next move. Tables and module breakdowns are reference material for when the reader wants to dig in.

## Full Report: `context/analysis/placement-audit.md`

```markdown
# Placement Audit Report

**Date:** {YYYY-MM-DD}
**Account:** {customer_id}
**Vertical:** {vertical from business.md}
**Mode:** {full / performance / safety / hygiene}
**Overall Score:** {x}% — {grade}

---

## Executive read

{Prose only, no bullet lists, ≤300 words. Direct, confident, plain language. Cover all 6 slots in order:}

{**Slot 1 — Score meaning.** State what the score means in plain language for this account, not just the band name. "62% — Needs Attention" tells the reader nothing; "62% means roughly a third of Display spend is going to mobile-game and MFA placements that have never converted, and the exclusion lists meant to catch that aren't linked to the right campaigns" tells them what to do.}

{**Slot 2 — 1–3 things to do this week, ranked, each with the *why*.** Prose form. Name the lever, name the evidence, name the expected impact. Example: "First, exclude the 14 mobile-game app categories that account for $1,240/mo of zero-conversion spend in Demand Gen — these are textbook waste, not a targeting trade-off. Second, link the master negative-placement list to the three campaigns currently running uncovered; the list already exists, this is plumbing." If the audit found nothing actionable: "Nothing urgent this week — every flagged placement falls below the waste threshold or has too little spend to act on."}

{**Slot 3 — What is NOT a problem** (so red text below doesn't waste attention). Call out SKIP'd diagnostics, deliberate-but-flagged choices, and false alarms. Example: "The PMax placement list looks long but most are sub-$5 spend and shouldn't drive any action. Brand-safety inventory is already on Limited for Video — the WARN there is informational." If no false-alarm risks today: "No red findings worth ignoring — every flagged item is real."}

{**Slot 4 — Inline-quoted fresh peer findings from Phase 2.5.** Quote the peer's score, date, and the specific top-line finding when one overlaps a flagged campaign or placement. Example: "A fresh budget-audit from {date} ({N} days old) flagged the same Demand Gen campaign as budget-capped at 60% of recommended — that means the low click volume on flagged placements is partly a budget effect, not pure placement waste. Excluding the worst offenders is still right; expect a smaller dollar-recovery than the raw spend numbers suggest." Or for tracking contradictions: "A fresh tracking-audit from {date} flagged the primary conversion action on this campaign as misfiring — treat the zero-conversion placement flags here as suspect until tracking is fixed." If no peers were fresh, omit this slot.}

{**Slot 5 — One line on how to read the rest.** "Module-by-module scoring and the per-diagnostic table follow below; jump to Recommended Actions for the executable list."}

{**Slot 6 — Score trend.** "Score: 62% — down from 71% last month. The drop is driven by Module 1 (Performance & App Audit), specifically new mobile-game waste in Demand Gen." Read from `placement-audit-log.md` to compute. If no prior entry: "Baseline run — no prior score to compare against."}

---

## Module Scores

| Module | Score | Grade | Passed | Warned | Failed | Skipped |
|--------|-------|-------|--------|--------|--------|---------|
| Performance & App Audit (PL-D01–D04) | {x}% | {grade} | {n} | {n} | {n} | {n} |
| Brand Safety & Coverage (PL-D05–D07) | {x}% | {grade} | {n} | {n} | {n} | {n} |
| Hygiene & Monitoring (PL-D08–D10) | {x}% | {grade} | {n} | {n} | {n} | {n} |
| **Overall** | **{x}%** | **{grade}** | **{n}** | **{n}** | **{n}** | **{n}** |

---

## Critical Issues

{If any FAIL verdicts, list ranked by impact. If none: "No critical issues found."}

| Priority | ID | Issue | Impact | Routing |
|----------|----|-------|--------|---------|
| 1 | PL-DXX | {issue summary} | {$waste or description} | `/placement-optimize {subcommand}` |

---

## Placement Type Breakdown

{From summary JSON `placement_type_breakdown`. One row per type.}

| Type | Placements | Spend | Conversions | CPA | Conv. Value | ROAS | CTR |
|------|-----------|-------|-------------|-----|-------------|------|-----|
| {type} | {n} | ${n} | {n} | ${n} | ${n} | {n} | {n}% |

---

## Top Wasters (0 Conversions)

{From summary JSON `top_wasters`. Up to 20 placements ranked by spend, all with 0 click-through conversions.}

| # | Placement | Type | Campaign | Spend | Clicks | VTC |
|---|-----------|------|----------|-------|--------|-----|
| 1 | {placement} | {type} | {campaign} | ${n} | {n} | {n} |

---

## Performance & App Audit Results (PL-D01–D04)

| ID | Diagnostic | Status | Points | Details |
|----|-----------|--------|--------|---------|
| PL-D01 | Mobile app placement audit | {status} | {earned}/{possible} | {details} |
| PL-D02 | Display placement performance | {status} | {earned}/{possible} | {details} |
| PL-D03 | Video placement quality | {status} | {earned}/{possible} | {details} |
| PL-D04 | Known-bad domain detection | {status} | {earned}/{possible} | {details} |

**Module Score:** {earned}/{possible} ({x}%)

{For each WARN or FAIL, add a detail block:}

### PL-DXX: {Name} — {WARN/FAIL}

{Detailed findings with specifics. Include the recommendation and routing.}

---

## Brand Safety & Coverage Results (PL-D05–D07)

| ID | Diagnostic | Status | Points | Details |
|----|-----------|--------|--------|---------|
| PL-D05 | Exclusion list coverage | {status} | {earned}/{possible} | {details} |
| PL-D06 | Brand safety configuration | {status} | {earned}/{possible} | {details} |
| PL-D07 | PMax placement review | {status} | {earned}/{possible} | {details} |

**Module Score:** {earned}/{possible} ({x}%)

---

## Hygiene & Monitoring Results (PL-D08–D10)

| ID | Diagnostic | Status | Points | Details |
|----|-----------|--------|--------|---------|
| PL-D08 | Demand Gen channel performance | {status} | {earned}/{possible} | {details} |
| PL-D09 | Exclusion list hygiene | {status} | {earned}/{possible} | {details} |
| PL-D10 | Top placement spot-check | {status} | {earned}/{possible} | {details} |

**Module Score:** {earned}/{possible} ({x}%)

---

## Top 10 Placements by Impressions (Spot-Check)

| # | Placement | Type | Campaign | Impressions | Notes |
|---|-----------|------|----------|-------------|-------|
| 1 | {placement} | {type} | {campaign} | {impressions} | {sub-agent flag or "OK"} |

---

## Data Summary

| Metric | Value |
|--------|-------|
| Total placements analyzed | {n} |
| Total flagged | {n} |
| Flagged spend | ${n} |
| Campaigns analyzed | {n} |
| Exclusion lists | {n} |
| App categories excluded | {n}/{total} |

---

## Recommended Actions

{List WARN and FAIL findings with optimizer commands. Group by optimizer subcommand.}

### Immediate (FAIL findings)
- {PL-DXX}: {action} → `/placement-optimize {subcommand}`

### Optimize (WARN findings)
- {PL-DXX}: {action} → `/placement-optimize {subcommand}`

### Advisory (INFO findings)
- {PL-DXX}: {manual review notes}

---

**Would you like me to start the placement optimizer to fix these issues?**
It will show you a dry-run preview of all changes before applying anything.

Report saved: context/analysis/placement-audit.md
```

## Audit Log: `context/analysis/placement-audit-log.md`

Append one entry per run:

```markdown
## {YYYY-MM-DD} — Score: {x}% ({grade})

- **Account:** {customer_id}
- **Mode:** {full / performance / safety / hygiene}
- **Top finding:** {1-line — the single most impactful issue or "Clean — no critical issues"}
- **Fresh peer reports integrated:** {list of peer skills + dates, or "none"}
- **Findings:** {n} PASS, {n} WARN, {n} FAIL, {n} SKIP

| Module | Score | Key Findings |
|--------|-------|-------------|
| Performance & App Audit | {x}% | {1-line summary of issues or "Clean"} |
| Brand Safety & Coverage | {x}% | {1-line summary} |
| Hygiene & Monitoring | {x}% | {1-line summary} |
```
