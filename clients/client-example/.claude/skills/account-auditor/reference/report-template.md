# Account Auditor — Report Template

The report is **explain-then-action**: a reader who only reads the Executive Read at the top should still leave with the right next move. Tables and module breakdowns are reference material for when the reader wants to dig in.

## Full Report (`context/analysis/account-audit.md`)

```markdown
# Account Audit Report

**Date:** {YYYY-MM-DD}
**Account:** {customer_id}
**Vertical:** {vertical from business.md}
**Mode:** {full / structure / naming / settings / adgroups / defaults}
**Overall Score:** {score}% — {grade}

---

## Executive read

{Prose only, no bullet lists, ≤300 words. Direct, confident, plain language. Cover all 6 slots in order:}

{**Slot 1 — Score meaning.** State what the score means in plain language for this account, not just the band name. "62% — Needs Attention" tells the reader nothing; "62% means the account's structure is leaking budget through two specific naming/grouping mistakes that are almost certainly fixable this week" tells them what to do.}

{**Slot 2 — 1–3 things to do this week, ranked, each with the *why*.** Prose form. Name the lever, name the evidence, name the expected impact. Examples for this domain: a campaign-naming pattern that breaks reporting (e.g., "five campaigns mix brand and non-brand under one name — fix the convention before bid strategies inherit muddled history"), an ad-group split issue ("Brand-Search has 47 keywords across 3 themes — split into 3 tight ad groups so ad relevance and QS recover"), or a default conversion goal misconfiguration ("the account-default conversion goal is still 'All Conversions' — switch to the primary goal so Smart Bidding optimises against the right action"). If the audit found nothing actionable: "Nothing urgent this week — here's what I checked and why it passed."}

{**Slot 3 — What is NOT a problem** (so red text below doesn't waste attention). Call out SKIP'd diagnostics, deliberate-but-flagged choices (e.g., a single-ad-group campaign that is intentional for a tiny brand campaign), and false alarms. If no false-alarm risks today: "No red findings worth ignoring — every flagged item is real."}

{**Slot 4 — Inline-quoted fresh peer findings from Phase 2.5.** Quote the peer's score, date, and the specific top-line finding when one overlaps a flagged campaign, ad group, or setting. Example: "A fresh keyword audit from {date} ({N} days old) flagged the same Brand-Search ad group for cannibalisation — that's the same root cause this audit is naming from the structure angle." If no peers were fresh, omit this slot.}

{**Slot 5 — One line on how to read the rest.** "Module-by-module scoring and the diagnostic table follow below; jump to Critical Issues for the actionable list."}

{**Slot 6 — Score trend.** "Score: 62% — down from 71% last week. The drop is driven by Module 2 (Naming)." Read from `account-audit-log.md` to find prior score. If no prior entry: "Baseline run — no prior score to compare against."}

---

## Module Scores

| Module | Score | Grade | Checks Passed | Checks Failed | Checks Skipped |
|--------|-------|-------|---------------|---------------|----------------|
| Structure | {x}% | {grade} | {n} | {n} | {n} |
| Naming | {x}% | {grade} | {n} | {n} | {n} |
| Settings | {x}% | {grade} | {n} | {n} | {n} |
| Ad Groups | {x}% | {grade} | {n} | {n} | {n} |
| Defaults | {x}% | {grade} | {n} | {n} | {n} |
| **Overall** | **{x}%** | **{grade}** | **{n}** | **{n}** | **{n}** |

---

## Critical Issues

{List FAIL diagnostics sorted by severity, highest first. Include specific campaigns/settings affected.}

| Priority | ID | Issue | Impact | Routing |
|----------|----|-------|--------|---------|
| 1 | AUD-DXX | {issue description} | {what it means} | {specialist skill to run} |
| ... | ... | ... | ... | ... |

---

## Structure Results (AUD-D01–D08)

| ID | Diagnostic | Status | Points | Details |
|----|-----------|--------|--------|---------|
| AUD-D01 | Campaign type separation | {status} | {x}/{y} | {details} |
| ... | ... | ... | ... | ... |

**Module Score:** {x}/{y} ({z}%)

---

## Naming Results (AUD-D09–D10)

| ID | Diagnostic | Status | Points | Details |
|----|-----------|--------|--------|---------|
| AUD-D09 | Campaign naming convention | {status} | {x}/{y} | {details} |
| AUD-D10 | Ad group naming consistency | {status} | {x}/{y} | {details} |

**Module Score:** {x}/{y} ({z}%)

---

## Settings Results (AUD-D11–D19)

| ID | Diagnostic | Status | Points | Details |
|----|-----------|--------|--------|---------|
| AUD-D11 | Display Network opt-in | {status} | {x}/{y} | {details} |
| ... | ... | ... | ... | ... |

**Module Score:** {x}/{y} ({z}%)

---

## Ad Group Results (AUD-D20–D23)

| ID | Diagnostic | Status | Points | Details |
|----|-----------|--------|--------|---------|
| AUD-D20 | Thematic tightness | {status} | {x}/{y} | {details} |
| ... | ... | ... | ... | ... |

**Module Score:** {x}/{y} ({z}%)

---

## Defaults Results (AUD-D24)

| ID | Diagnostic | Status | Points | Details |
|----|-----------|--------|--------|---------|
| AUD-D24 | Account-level defaults | {status} | {x}/{y} | {details} |

**Module Score:** {x}/{y} ({z}%)

---

## Routing Recommendations

Based on the findings, run these specialist skills next:

| Specialist | Why | Priority |
|-----------|-----|----------|
| {skill name} | {issue found that this skill addresses} | {high/medium/low} |
| ... | ... | ... |

---

## Data Freshness

| Data Source | Last Updated | Status |
|-------------|-------------|--------|
| campaigns.csv | {date} | {OK / Stale} |
| campaigns-settings.csv | {date} | Pulled fresh |
| adgroups.csv | {date} | {OK / Stale} |
| keywords.csv | {date} | {OK / Stale} |
| ads.csv | {date} | {OK / Stale} |
```

## Log Entry (`context/analysis/account-audit-log.md`)

Append this entry to the log file. Create the file with `# Account Audit Log` header if it doesn't exist.

```markdown
## {YYYY-MM-DD} — Score: {score}% ({grade})

- **Mode:** {full / structure / naming / settings / adgroups / defaults}
- **Account:** {customer_id}
- **Top finding:** {1-line — the single most impactful issue or "Clean — no critical issues"}
- **Fresh peer reports integrated:** {list of peer skills + dates, or "none"}
- **Critical issues:** {count} | **Routing:** {list of specialist skills recommended}

| Module | Score | Key Findings |
|--------|-------|-------------|
| Structure | {x}% | {1-line summary of issues or "Clean"} |
| Naming | {x}% | {1-line summary} |
| Settings | {x}% | {1-line summary} |
| Ad Groups | {x}% | {1-line summary} |
| Defaults | {x}% | {1-line summary} |
```
