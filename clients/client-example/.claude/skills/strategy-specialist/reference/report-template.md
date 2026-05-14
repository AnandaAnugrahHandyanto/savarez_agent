# Report Template — Strategy Audit

The report is **explain-then-action**: a reader who only reads the Executive read at the top should still leave with the right next move. Tables and module breakdowns are reference material for when the reader wants to dig in.

## Audit Report (`context/analysis/strategy-audit.md`)

Regenerated on each run (overwrites previous).

```markdown
# Strategy Audit Report

**Date:** {YYYY-MM-DD}
**Account:** {client name from business.md}
**Vertical:** {vertical}
**Mode:** {unit-economics / goals / full}
**Overall Score:** {score}% — {grade}

---

## Executive read

{Prose only, no bullet lists, ≤300 words. Direct, confident, plain language. Cover all 6 slots in order:}

{**Slot 1 — Score meaning.** State what the score means in plain language for *this* account, not just the band name. "62% — Needs Attention" tells the reader nothing; "62% means break-even economics aren't yet wired up and one of the two active campaigns is running against a target the account can't actually afford" tells them what to do. For strategy-specialist, name the missing or shaky piece directly: a missing break-even CPA / ROAS, a placeholder LTV, a CVR assumption that hasn't been validated, or a monthly target that's infeasible at current CVR.}

{**Slot 2 — 1–3 things to do this week, ranked, each with the *why*.** Prose form. Name the lever, name the evidence, name the expected impact. Strategy-flavored examples: "Calculate break-even CPA before next week's bid review — D02 flagged the field as empty and tCPA on Brand Search is set 35% above what the gross margin can support, so any bid optimization right now is solving the wrong problem." If the audit found nothing actionable: "Nothing urgent this week — unit economics are wired up, goals are explicit, and bid strategies match. Here's what I checked and why it passed."}

{**Slot 3 — What is NOT a problem** (so red text below doesn't waste attention). Call out SKIP'd diagnostics (e.g., LTV-related D05–D07 SKIP'd on a lead-gen account by design), deliberate-but-flagged choices, and false alarms. If no false-alarm risks today: "No red findings worth ignoring — every flagged item is real."}

{**Slot 4 — Inline-quoted fresh peer findings from Phase 3.5.** Quote the peer's score, date, and the specific top-line finding when one overlaps a flagged input or campaign. Strategy is the B-layer: the peer findings most worth surfacing here are upstream-validation (tracking) and downstream-blocked (bidding, budget). Examples: "A fresh tracking-audit from {date} ({N} days old) scored Measurement at 92% — that's the upstream confirmation that the CVR figure used in the goal-feasibility check is trustworthy, so the 'monthly target infeasible' finding stands." Or, contradicting: "A fresh tracking-audit from {date} flagged the primary conversion event as misfiring on Campaign X — the CVR this audit used to call its target unrealistic is therefore unreliable; treat the goal-feasibility verdict as provisional until tracking is fixed." Or: "A fresh bidding-audit from {date} reported tCPA on the same campaigns set 35% above this audit's calculated break-even CPA — the bidding fix is downstream of the unit-economics fix below." If no peers were fresh, omit this slot.}

{**Slot 5 — One line on how to read the rest.** "Module-by-module scoring and the diagnostic table follow below; jump to Critical Issues for the actionable list and Recommendations for routing."}

{**Slot 6 — Score trend.** "Score: 62% — down from 71% last week. The drop is driven by D12 (target feasibility) flipping to FAIL after the new monthly target was entered." Read from `strategy-audit-log.md` to compute. If no prior entry: "Baseline run — no prior score to compare against."}

---

## Overall Score

| Module | Score | Grade |
|--------|-------|-------|
| Unit Economics | {X}/{Y} ({Z}%) | {grade} |
| Goals & KPIs | {X}/{Y} ({Z}%) | {grade} |
| **Overall** | **{X}/{Y} ({Z}%)** | **{grade}** |

---

## Viability Verdict: {Go / Conditional Go / No-Go}

{1-2 sentence summary of the verdict with key drivers}

---

## Unit Economics Results

| ID | Diagnostic | Status | Pts | Details |
|----|-----------|--------|-----|---------|
| D01 | Gross margin adequacy | {status} | {X}/{Y} | {one-line detail} |
| D02 | Break-even ROAS | {status} | {X}/{Y} | {one-line detail} |
| ... | ... | ... | ... | ... |

{For each WARN or FAIL, include a recommendation paragraph}

---

## Goals & KPIs Results

| ID | Diagnostic | Status | Pts | Details |
|----|-----------|--------|-----|---------|
| D10 | Primary KPI definition | {status} | {X}/{Y} | {one-line detail} |
| D11 | Guardrail KPI definition | {status} | {X}/{Y} | {one-line detail} |
| ... | ... | ... | ... | ... |

{For each WARN or FAIL, include a recommendation paragraph}

---

## Critical Issues

{List only FAIL items with specific fix actions. If no FAILs, omit this section.}

### {FAIL item title}
- **What:** {what was found}
- **Impact:** {why this matters}
- **Fix:** {specific action to take}

---

## Data Freshness

| Source | Last Updated | Status |
|--------|-------------|--------|
| business.md | {date} | {Fresh / Stale} |
| campaigns.csv | {date or "Not used"} | {Fresh / Stale / N/A} |
| account-changelog.md | {date} | {Fresh / Stale} |

---

## Recommendations

1. {Top priority recommendation}
2. {Second recommendation}
3. {Third recommendation}
```

## Audit Log (`context/analysis/strategy-audit-log.md`)

Append-only. One entry per run. Create the file with `# Strategy Audit Log` header if it doesn't exist.

```markdown
## {YYYY-MM-DD} — Score: {score}% ({grade})

- **Mode:** {unit-economics / goals / full}
- **Vertical:** {vertical}
- **Verdict:** {Go / Conditional Go / No-Go}
- **Top finding:** {1-line — the single most impactful issue, e.g. "Break-even CPA empty — D02 FAIL" or "Clean — unit economics + goals wired up"}
- **Fresh peer reports integrated:** {list of peer skills + dates, e.g. "tracking-audit (2026-04-29), bidding-audit (2026-04-30)" — or "none"}
- **FAILs:** {count} — {list IDs}
- **WARNs:** {count} — {list IDs}
- **ASKs:** {count} — {resolved/unresolved}
```

## Memory Log (`context/memory/YYYY-MM-DD.md`)

Append to today's memory log.

```markdown
## Strategy Audit Completed
- Mode: {unit-economics / goals / full}
- Score: {X}% ({grade}) — Verdict: {Go / Conditional Go / No-Go}
- Key issues: {1-2 sentence summary}
- Report: context/analysis/strategy-audit.md
- Log: context/analysis/strategy-audit-log.md
```
