# Geo-Schedule Auditor — Report Template

The report is **explain-then-action**: a reader who only reads the Executive Read at the top should still leave with the right next move. Tables and module breakdowns are reference material for when the reader wants to dig in.

## Full Report: `context/analysis/geo-schedule-audit.md`

```markdown
# Geo-Schedule Audit Report

**Date:** {YYYY-MM-DD}
**Account:** {customer_id}
**Vertical:** {vertical from business.md}
**Mode:** {full / geo / schedule / demo}
**Overall Score:** {x}% — {grade}

---

## Executive read

{Prose only, no bullet lists, ≤300 words. Direct, confident, plain language. Cover all 6 slots in order:}

{**Slot 1 — Score meaning.** State what the score means in plain language for this account, not just the band name. "62% — Needs Attention" tells the reader nothing; "62% means the account is bleeding spend on three locations and one dead daypart that are almost certainly fixable this week" tells them what to do.}

{**Slot 2 — 1–3 things to do this week, ranked, each with the *why*.** Prose form. Name the lever, name the evidence, name the expected impact. Example shape: "First, exclude the three zero-conversion zip codes around {region} — they have absorbed $847 over 90 days with no leads, so the savings move straight to working geos. Second, pause the Mon 01:00–05:00 daypart on {campaign}; it has driven zero conversions in six weeks. Third, the tablet CPA is 68% above account average — on Smart Bidding, a tablet device exclusion is the right lever, not a manual modifier." If the audit found nothing actionable: "Nothing urgent this week — here's what I checked and why it passed."}

{**Slot 3 — What is NOT a problem** (so red text below doesn't waste attention). Call out SKIP'd diagnostics, deliberate-but-flagged choices, and false alarms. Examples: "GS-D11 looks angry but the modifier on {campaign} is harmless — Smart Bidding ignores it; flagging is just a cleanup nudge, not a performance issue." Or: "Demographic outliers in GS-D10 are inside the noise floor at this conversion volume — don't act on them yet." If no false-alarm risks today: "No red findings worth ignoring — every flagged item is real."}

{**Slot 4 — Inline-quoted fresh peer findings from Phase 2.5.** Quote the peer's score, date, and the specific top-line finding when one overlaps a flagged campaign, geo, daypart, device, or demographic segment. Example: "A fresh bidding-audit from {date} ({N} days old) shows {campaign} is on tROAS — that means the GS-D06 tablet-modifier finding here is moot; the right lever is a device exclusion, not a bid adjustment. The two audits are saying the same thing from different angles." If no peers were fresh, omit this slot.}

{**Slot 5 — One line on how to read the rest.** "Module-by-module scoring and the diagnostic table follow below; jump to Critical Issues for the actionable list."}

{**Slot 6 — Score trend.** "Score: 62% — down from 71% last month. The drop is driven by the Schedule & Device module after a tROAS rollout exposed device-CPA variance." Read from `geo-schedule-audit-log.md` to compute. If no prior entry: "Baseline run — no prior score to compare against."}

---

## Module Scores

| Module | Score | Grade | Passed | Warned | Failed | Skipped |
|--------|-------|-------|--------|--------|--------|---------|
| Geographic (GS-D01–D05) | {x}% | {grade} | {n} | {n} | {n} | {n} |
| Schedule & Device (GS-D06–D09) | {x}% | {grade} | {n} | {n} | {n} | {n} |
| Demographics & Advanced (GS-D10–D14) | {x}% | {grade} | {n} | {n} | {n} | {n} |
| **Overall** | **{x}%** | **{grade}** | **{n}** | **{n}** | **{n}** | **{n}** |

---

## Critical Issues

{If any FAIL verdicts exist, list them here ranked by impact (estimated waste). If none, write "No critical issues found."}

| Priority | ID | Issue | Impact | Routing |
|----------|----|-------|--------|---------|
| 1 | GS-DXX | {issue summary} | {$waste or description} | `/geo-schedule-optimizer {subcommand}` |
| 2 | GS-DXX | {issue summary} | {$waste or description} | `/geo-schedule-optimizer {subcommand}` |

---

## Geographic Results (GS-D01–D05)

| ID | Diagnostic | Status | Points | Details |
|----|-----------|--------|--------|---------|
| GS-D01 | Location targeting method | {status} | {earned}/{possible} | {details} |
| GS-D02 | Geographic CPA/ROAS variance | {status} | {earned}/{possible} | {details} |
| GS-D03 | Zero-conversion locations | {status} | {earned}/{possible} | {details} |
| GS-D04 | High-performing location opportunity | {status} | {earned}/{possible} | {details} |
| GS-D05 | Geographic exclusion coverage | {status} | {earned}/{possible} | {details} |

**Module Score:** {earned}/{possible} ({x}%)

{For each WARN or FAIL, add a detail block:}

### GS-DXX: {Name} — {WARN/FAIL}

{Detailed findings with specific campaigns, locations, amounts. Include the recommendation and routing.}

---

## Schedule & Device Results (GS-D06–D09)

| ID | Diagnostic | Status | Points | Details |
|----|-----------|--------|--------|---------|
| GS-D06 | Device CPA variance | {status} | {earned}/{possible} | {details} |
| GS-D07 | Ad schedule waste | {status} | {earned}/{possible} | {details} |
| GS-D08 | Schedule consistency | {status} | {earned}/{possible} | {details} |
| GS-D09 | Bid modifier stacking | {status} | {earned}/{possible} | {details} |

**Module Score:** {earned}/{possible} ({x}%)

---

## Demographics & Advanced Results (GS-D10–D14)

| ID | Diagnostic | Status | Points | Details |
|----|-----------|--------|--------|---------|
| GS-D10 | Demographic CPA outliers | {status} | {earned}/{possible} | {details} |
| GS-D11 | Smart Bidding modifier conflict | {status} | {earned}/{possible} | {details} |
| GS-D12 | Seasonal geo patterns | {status} | {earned}/{possible} | {details} |
| GS-D13 | Demographic exclusion opportunity | {status} | {earned}/{possible} | {details} |
| GS-D14 | Geographic targeting optimization | {status} | {earned}/{possible} | {details} |

**Module Score:** {earned}/{possible} ({x}%)

---

## Recommended Next Steps

{Use the routing table from SKILL.md Phase 5. Match DIAGNOSE results to optimizer commands.}

| Action | Command | Priority | Addresses |
|--------|---------|----------|-----------|
| {action description} | `/geo-schedule-optimizer {sub}` | {P1/P2/P3} | GS-DXX, GS-DXX |

{If score >= 90%:}
> Geo, schedule, and demographic targeting looks solid. Re-audit in 30 days.

{If score < 90%:}
> Run `/geo-schedule-optimizer` to apply all recommended changes (dry-run preview first).
>
> Or target specific modules:
> - `/geo-schedule-optimizer geo` — fix location exclusions and modifiers
> - `/geo-schedule-optimizer schedule` — pause dead time windows and adjust schedule
> - `/geo-schedule-optimizer demo` — apply demographic bid adjustments

---

## Data Freshness

| Data Source | Rows | Last Updated | Status |
|-------------|------|-------------|--------|
| geo-user-location.csv | {n} | {date} | {OK / Stale → re-pulled} |
| device-performance.csv | {n} | {date} | {OK / Stale → re-pulled} |
| campaigns.csv | {n} | {date} | {OK / Stale → re-pulled} |
| campaigns-settings.csv | {n} | {date} | {OK / Stale → re-pulled} |
| campaign-criteria.csv | {n} | {date} | Pulled fresh |
| schedule-performance.csv | {n} | {date} | Pulled fresh |
| demographics-performance.csv | {n} | {date} | Pulled fresh |
| schedule-consistency.csv | {n} | {date} | Generated fresh |
| geo-seasonal-comparison.csv | {n} | {date} | Generated fresh |
```

---

## Log Entry: `context/analysis/geo-schedule-audit-log.md`

Append one entry per audit run. Do not overwrite — this file is an append-only log.

```markdown
## {YYYY-MM-DD} — Score: {score}% ({grade})

- **Mode:** {full / geo / schedule / demo}
- **Account:** {customer_id}
- **Top finding:** {1-line — the single most impactful issue or "Clean — no critical issues"}
- **Fresh peer reports integrated:** {list of peer skills + dates, or "none"}
- **Critical issues:** {count} | **Routing:** {comma-separated list of recommended commands}

| Module | Score | Key Findings |
|--------|-------|-------------|
| Geographic | {x}% | {1-line summary or "Clean"} |
| Schedule & Device | {x}% | {1-line summary or "Clean"} |
| Demographics & Advanced | {x}% | {1-line summary or "Clean"} |
```

---

## Scoring Calculation Rules

1. Start with points possible = sum of all non-SKIPped check severities
2. Start with points earned = points possible
3. For each FAIL: deduct full severity points
4. For each WARN: deduct full severity points (WARNs also reduce score)
5. Score % = (points earned / points possible) * 100
6. Module scores use the same formula but only for checks within that module
7. Grade thresholds: 90-100% = Excellent, 70-89% = Good, 50-69% = Needs Attention, <50% = Critical

## Display Rules

- Always show all 14 checks in the results tables (even SKIP and PASS)
- For SKIP: show the skip reason in the Details column
- For PASS: show "Clean" or a brief positive note in Details
- For WARN/FAIL: show specific data (campaigns, locations, amounts) in Details
- Rank Critical Issues by estimated waste (highest first)
- In the Summary (Phase 5), show the routing table only for WARN/FAIL items
