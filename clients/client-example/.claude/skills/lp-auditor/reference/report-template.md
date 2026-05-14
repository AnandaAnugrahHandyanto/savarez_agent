# LP Auditor — Report Template

The report is **explain-then-action**: a reader who only reads the Executive Read at the top should still leave with the right next move. Tables and module breakdowns are reference material for when the reader wants to dig in.

## Full Report (`context/analysis/lp-audit.md`)

```markdown
# Landing Page Audit Report

**Date:** {YYYY-MM-DD}
**URL(s) Audited:** {url(s) or "auto-discovered {n} URLs from ads data"}
**Vertical:** {lead gen / SaaS / ecommerce}
**Mode:** {full / structural / message-match / technical / performance / urls / ecommerce}
**Overall Score:** {score}% — {grade}

---

## Executive read

{Prose only, no bullet lists, ≤300 words. Direct, confident, plain language. Cover all 6 slots in order:}

{**Slot 1 — Score meaning.** State what the score means in plain language for this account, not just the band name. "62% — Needs Attention" tells the reader nothing; "62% means the page is leaking conversions in two specific places that are almost certainly fixable this week" tells them what to do.}

{**Slot 2 — 1–3 things to do this week, ranked, each with the *why*.** Prose form. Name the lever, name the evidence, name the expected impact. If the audit found nothing actionable: "Nothing urgent this week — here's what I checked and why it passed."}

{**Slot 3 — What is NOT a problem** (so red text below doesn't waste attention). Call out SKIP'd diagnostics, deliberate-but-flagged choices, and false alarms. If no false-alarm risks today: "No red findings worth ignoring — every flagged item is real."}

{**Slot 4 — Inline-quoted fresh peer findings from Phase 3.5.** Quote the peer's score, date, and the specific top-line finding when one overlaps a flagged URL or campaign. Example: "A fresh quality-score audit from {date} ({N} days old) flagged the same campaigns for Landing Page Experience — that's the same root cause this audit is naming from a different angle." If no peers were fresh, omit this slot.}

{**Slot 5 — One line on how to read the rest.** "Module-by-module scoring and the diagnostic table follow below; jump to Priority Fixes for the actionable list."}

{**Slot 6 — Score trend.** "Score: 62% — down from 71% last week. The drop is driven by Module 2 (Message Match)." Read from `lp-audit-log.md` to compute. If no prior entry: "Baseline run — no prior score to compare against."}

---

## Module Scores

| Module | Score | Grade | Passed | Warned | Failed | Skipped |
|--------|-------|-------|--------|--------|--------|---------|
| Structural (D01-D12) | {x}% | {grade} | {n} | {n} | {n} | {n} |
| Message Match (D13-D16) | {x}% | {grade} | {n} | {n} | {n} | {n} |
| Technical (D17-D24) | {x}% | {grade} | {n} | {n} | {n} | {n} |
| Performance (D25-D31) | {x}% | {grade} | {n} | {n} | {n} | {n} |
| URL Health (D32-D37) | {x}% | {grade} | {n} | {n} | {n} | {n} |
| Ecommerce (D38-D40) | {x}% | {grade} | {n} | {n} | {n} | {n} |
| **Overall** | **{x}%** | **{grade}** | **{n}** | **{n}** | **{n}** | **{n}** |

---

## Priority Fixes

{List FAIL and WARN diagnostics sorted by severity (Critical > High > Medium > Low), then by points. Include specific details and recommended actions.}

| Priority | ID | Issue | Impact | Fix Command |
|----------|----|-------|--------|-------------|
| 1 | LP-DXX | {issue description} | {what it means for conversions} | {/lp-optimize command} |
| ... | ... | ... | ... | ... |

---

## Structural Results (LP-D01–D12)

| ID | Diagnostic | Status | Points | Details |
|----|-----------|--------|--------|---------|
| LP-D01 | Offer section completeness | {status} | {x}/{y} | {details} |
| LP-D02 | Hero 5-second test | {status} | {x}/{y} | {details} |
| LP-D03 | Above-fold CTA presence | {status} | {x}/{y} | {details} |
| LP-D04 | CTA button quality | {status} | {x}/{y} | {details} |
| LP-D05 | Benefits section quality | {status} | {x}/{y} | {details} |
| LP-D06 | Trust/authority section | {status} | {x}/{y} | {details} |
| LP-D07 | Social proof quality | {status} | {x}/{y} | {details} |
| LP-D08 | Objection handling | {status} | {x}/{y} | {details} |
| LP-D09 | Guarantee presence & placement | {status} | {x}/{y} | {details} |
| LP-D10 | CTA repetition | {status} | {x}/{y} | {details} |
| LP-D11 | One-page-one-goal | {status} | {x}/{y} | {details} |
| LP-D12 | Section hierarchy | {status} | {x}/{y} | {details} |

**Module Score:** {x}/{y} ({z}%)

---

## Message Match Results (LP-D13–D16)

| ID | Diagnostic | Status | Points | Details |
|----|-----------|--------|--------|---------|
| LP-D13 | Ad-to-LP headline match | {status} | {x}/{y} | {details} |
| LP-D14 | Ad-to-LP offer match | {status} | {x}/{y} | {details} |
| LP-D15 | Keyword-to-LP relevance | {status} | {x}/{y} | {details} |
| LP-D16 | Visual consistency | {status} | {x}/{y} | {details} |

**Module Score:** {x}/{y} ({z}%)

---

## Technical Results (LP-D17–D24)

| ID | Diagnostic | Status | Points | Details |
|----|-----------|--------|--------|---------|
| LP-D17 | Page load speed | {status} | {x}/{y} | {details} |
| LP-D18 | Core Web Vitals | {status} | {x}/{y} | {details} |
| LP-D19 | Mobile responsiveness | {status} | {x}/{y} | {details} |
| LP-D20 | Mobile vs desktop CVR gap | {status} | {x}/{y} | {details} |
| LP-D21 | Form field count | {status} | {x}/{y} | {details} |
| LP-D22 | Form functionality | {status} | {x}/{y} | {details} |
| LP-D23 | SSL/HTTPS | {status} | {x}/{y} | {details} |
| LP-D24 | Image optimization | {status} | {x}/{y} | {details} |

**Module Score:** {x}/{y} ({z}%)

---

## Performance Results (LP-D25–D31)

| ID | Diagnostic | Status | Points | Details |
|----|-----------|--------|--------|---------|
| LP-D25 | CVR vs benchmark | {status} | {x}/{y} | {details} |
| LP-D26 | Bounce rate | SKIP | —/5 | Requires GA4 |
| LP-D27 | Scroll depth | SKIP | —/5 | Requires GA4 |
| LP-D28 | Time on page | SKIP | —/3 | Requires GA4 |
| LP-D29 | Per-LP CPA comparison | {status} | {x}/{y} | {details} |
| LP-D30 | Device-specific performance | {status} | {x}/{y} | {details} |
| LP-D31 | Traffic source match | {status} | {x}/{y} | {details} |

**Module Score:** {x}/{y} ({z}%)

---

## URL Health Results (LP-D32–D37)

| ID | Diagnostic | Status | Points | Details |
|----|-----------|--------|--------|---------|
| LP-D32 | HTTP status codes | {status} | {x}/{y} | {details} |
| LP-D33 | Redirect chain detection | {status} | {x}/{y} | {details} |
| LP-D34 | DSA target URL health | {status} | {x}/{y} | {details} |
| LP-D35 | Keyword-level URL health | {status} | {x}/{y} | {details} |
| LP-D36 | Asset URL health | {status} | {x}/{y} | {details} |
| LP-D37 | Final URL expansion audit | {status} | {x}/{y} | {details} |

**Module Score:** {x}/{y} ({z}%)

---

## Ecommerce Results (LP-D38–D40)

{Only shown for ecommerce vertical}

| ID | Diagnostic | Status | Points | Details |
|----|-----------|--------|--------|---------|
| LP-D38 | Product page elements | {status} | {x}/{y} | {details} |
| LP-D39 | Cart & checkout flow | {status} | {x}/{y} | {details} |
| LP-D40 | Category page quality | {status} | {x}/{y} | {details} |

**Module Score:** {x}/{y} ({z}%)

---

## Routing Recommendations

Based on the findings, run these next:

| Action | Why | Priority |
|--------|-----|----------|
| {/lp-optimize command or skill} | {issue found that this addresses} | {high/medium/low} |
| ... | ... | ... |

---

## Data Freshness

| Data Source | Last Updated | Status |
|-------------|-------------|--------|
| ads.csv | {date} | {OK / Stale} |
| keywords.csv | {date} | {OK / Stale} |
| device-performance.csv | {date} | {OK / Stale} |
| assets.csv | {date} | {OK / Stale / N/A} |
| Chrome DevTools | {date} | Live |
```

## Log Entry (`context/analysis/lp-audit-log.md`)

Append this entry to the log file. Create the file with `# LP Audit Log` header if it doesn't exist.

```markdown
## {YYYY-MM-DD} — Score: {score}% ({grade})

- **Mode:** {full / structural / message-match / technical / performance / urls / ecommerce}
- **URL:** {url or "auto-discovered {n} URLs"}
- **Top finding:** {1-line — the single most impactful issue or "Clean — no critical issues"}
- **Fresh peer reports integrated:** {list of peer skills + dates, or "none"}
- **Critical issues:** {count} | **Routing:** {list of /lp-optimize commands recommended}

| Module | Score | Key Findings |
|--------|-------|-------------|
| Structural | {x}% | {1-line summary of issues or "Clean"} |
| Message Match | {x}% | {1-line summary} |
| Technical | {x}% | {1-line summary} |
| Performance | {x}% | {1-line summary} |
| URL Health | {x}% | {1-line summary} |
| Ecommerce | {x}% | {1-line summary or "N/A"} |
```
