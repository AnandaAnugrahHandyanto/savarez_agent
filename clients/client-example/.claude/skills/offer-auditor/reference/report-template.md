# Report Template — Offer Audit

The report is **explain-then-action**: a reader who only reads the Executive Read at the top should still leave with the right next move. Tables and module breakdowns are reference material for when the reader wants to dig in.

## Audit Report (`context/analysis/offer-audit.md`)

Regenerated on each run (overwrites previous).

```markdown
# Offer Audit Report

**Date:** {YYYY-MM-DD}
**Account:** {client name from business.md}
**Vertical:** {vertical}
**Module:** {value / urgency / trust / positioning / full}
**Overall Score:** {score}% — {grade}

---

## Executive read

{Prose only, no bullet lists, ≤300 words. Direct, confident, plain language. Cover all 6 slots in order:}

{**Slot 1 — Score meaning.** State what the score means in plain language for this account, not just the band name. "62% — Needs Attention" tells the reader nothing; "62% means the offer is missing two specific elements — a credible guarantee and a quantified dream outcome — that are blocking conversions and almost certainly fixable this week" tells them what to do. Name the offer's actual weak pillar (value, urgency, trust, positioning) in plain language.}

{**Slot 2 — 1–3 things to do this week, ranked, each with the *why*.** Prose form. Name the lever (e.g., "add a money-back guarantee", "rewrite the value prop to lead with the dream outcome", "replace the generic CTA with a specific commitment", "remove the fake countdown timer"), name the evidence (which diagnostic flagged it), and name the expected impact. If the audit found nothing actionable: "Nothing urgent this week — the offer's four pillars are all carrying weight."}

{**Slot 3 — What is NOT a problem** (so red text below doesn't waste attention). Call out SKIP'd diagnostics, deliberate-but-flagged choices, and false alarms. For example: "The audit flagged D08 (urgency authenticity) but the deadline is real — this is a true scarcity offer, not fake urgency, so the WARN is noise." If no false-alarm risks today: "No red findings worth ignoring — every flagged item is real."}

{**Slot 4 — Inline-quoted fresh peer findings from Phase 3.5.** Quote the peer's score, date, and the specific top-line finding when one overlaps an offer hypothesis. Especially tight integration with `/lp-auditor` — the offer lives on the LP, so an LP finding about hero clarity, guarantee placement, or social proof visibility is often the *real* offer fix. Example: "A fresh LP audit from {date} ({N} days old) flagged the same hero section for missing the guarantee — that's the same root cause this audit is naming from the offer side." If no peers were fresh, omit this slot.}

{**Slot 5 — One line on how to read the rest.** "Module-by-module scoring and the diagnostic table follow below; jump to Critical Issues for the actionable list."}

{**Slot 6 — Score trend.** "Score: 62% — down from 71% last week. The drop is driven by the Trust pillar (D09–D13)." Read from `offer-audit-log.md` to compute. If no prior entry: "Baseline run — no prior score to compare against."}

---

## Overall Score

| Module | Score | Grade |
|--------|-------|-------|
| Value (D01-D06) | {X}/{Y} ({Z}%) | {grade} |
| Urgency (D07-D08) | {X}/{Y} ({Z}%) | {grade} |
| Trust (D09-D13) | {X}/{Y} ({Z}%) | {grade} |
| Positioning (D14-D16) | {X}/{Y} ({Z}%) | {grade} |
| **Overall** | **{X}/{Y} ({Z}%)** | **{grade}** |

---

## Offer Quality Results

| ID | Diagnostic | Status | Pts | Details |
|----|-----------|--------|-----|---------|
| D01 | Value proposition clarity | {status} | {X}/{Y} | {one-line detail} |
| D02 | Dream outcome specificity | {status} | {X}/{Y} | {one-line detail} |
| D03 | Perceived value vs. price gap | {status} | {X}/{Y} | {one-line detail} |
| D04 | Uniqueness/comparison resistance | {status} | {X}/{Y} | {one-line detail} |
| D05 | Unique mechanism | {status} | {X}/{Y} | {one-line detail} |
| D06 | Value stacking depth | {status} | {X}/{Y} | {one-line detail} |
| D07 | Urgency element presence | {status} | {X}/{Y} | {one-line detail} |
| D08 | Urgency authenticity | {status} | {X}/{Y} | {one-line detail} |
| D09 | Risk removal presence | {status} | {X}/{Y} | {one-line detail} |
| D10 | Risk removal strength | {status} | {X}/{Y} | {one-line detail} |
| D11 | Social proof presence | {status} | {X}/{Y} | {one-line detail} |
| D12 | Social proof specificity | {status} | {X}/{Y} | {one-line detail} |
| D13 | Credibility signals | {status} | {X}/{Y} | {one-line detail} |
| D14 | Audience specificity | {status} | {X}/{Y} | {one-line detail} |
| D15 | Offer Audit Checklist score | {status} | {X}/{Y} | {X}/15 items pass |
| D16 | Competitor offer comparison | {status} | {X}/{Y} | {one-line detail} |

---

## Critical Issues

{List only FAIL items with specific fix actions. If no FAILs, omit this section.}

### {FAIL item title}
- **What:** {what was found}
- **Impact:** {why this matters for advertising}
- **Fix:** {specific action — include /offer-maker command if applicable}

---

## Data Freshness

| Source | Last Updated | Status |
|--------|-------------|--------|
| business.md | {date} | {Fresh / Stale} |
| brand.md | {date or "Not found"} | {Fresh / Stale / Missing} |
| competitor-ads/ | {date or "Not found"} | {Fresh / Stale / Missing} |
| offer-angles.md | {date or "Not found"} | {Fresh / Stale / Missing} |

---

## Recommendations

1. {Top priority recommendation}
2. {Second recommendation}
3. {Third recommendation}

---

## Next Steps

{Based on results, suggest specific /offer-maker commands:}

- `/offer-maker create` — {if offer needs fundamental work}
- `/offer-maker angles` — {if offer is solid, extract angles}
- `/offer-maker competitor` — {if competitor comparison missing}
- `/offer-maker diagnose` — {if specific weak elements need fixing}
```

## Audit Log (`context/analysis/offer-audit-log.md`)

Append-only. One entry per run. Create the file with `# Offer Audit Log` header if it doesn't exist.

```markdown
## {YYYY-MM-DD} — Score: {X}% ({grade})

- **Module:** {value / urgency / trust / positioning / full}
- **Vertical:** {vertical}
- **Top finding:** {1-line — the single most impactful issue, e.g., "missing money-back guarantee on lead-gen offer" or "Clean — no critical issues"}
- **Fresh peer reports integrated:** {list of peer skills + dates, e.g., "lp-auditor (2026-04-28), quality-score-auditor (2026-04-30)" or "none"}
- **FAILs:** {count} — {list IDs}
- **WARNs:** {count} — {list IDs}
- **ASKs:** {count} — {resolved/unresolved}
- **D15 (Audit Checklist):** {X}/15
- **Routing:** {list of /offer-maker commands and peer-report references}
```

## Memory Log (`context/memory/YYYY-MM-DD.md`)

Append to today's memory log.

```markdown
## Offer Audit Completed
- Module: {value / urgency / trust / positioning / full}
- Score: {X}% ({grade})
- Key issues: {1-2 sentence summary}
- Report: context/analysis/offer-audit.md
- Log: context/analysis/offer-audit-log.md
```
