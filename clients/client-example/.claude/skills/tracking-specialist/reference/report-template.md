# Report Template

Output to `context/analysis/tracking-audit.md`. Regenerated on each run (not append-only).

The report is **explain-then-action**: a reader who only reads the Executive read at the top should still leave with the right next move. Tables and module breakdowns are reference material for when the reader wants to dig in.

---

## Structure

```markdown
# Tracking Audit Report

**Date:** YYYY-MM-DD
**Account:** {account name from config}
**Mode:** {completeness / tag-health / consent / attribution / oct / hygiene / advanced / full}
**Vertical:** {ecommerce / lead gen / SaaS from business.md}
**Overall Score:** {score}% — {grade}

---

## Executive read

{Prose only, no bullet lists, ≤300 words. Direct, confident, plain language. Cover all 6 slots in order:}

{**Slot 1 — Score meaning.** State what the score means in plain language for THIS account, not just the band name. "78% — Good" tells the reader nothing; "78% means the conversion signal is mostly trustworthy, but the Purchase action on the main funnel is double-counting and that is silently inflating tROAS this week" tells them what to do. Tracking is the Measurement layer — say in plain English whether downstream skills (bidding, QS, search-term, LP) can trust the numbers right now.}

{**Slot 2 — 1–3 things to do this week, ranked, each with the *why*.** Prose form. Name the lever, name the evidence, name the expected impact. Examples of tracking-shaped levers: "fix the misfiring `purchase` event on /thank-you (D13 FAIL — zero firings in 7 days while sessions are flat)"; "remove the duplicate Lead tag on the contact form thank-you page (D03 FAIL — same event tracked by GTM and a hardcoded gtag, doubling lead counts)"; "repair the stale OCT mapping importing offline conversions against a deprecated action (D38 FAIL)"; "close the Consent Mode v2 gap that's suppressing ~22% of Purchase events (D26 FAIL)"; "fix the enhanced-conversions hash mismatch breaking modeled attribution on Campaign X (D32 WARN)". If nothing is actionable: "Nothing urgent this week — tracking is clean and downstream skills can trust the data."}

{**Slot 3 — What is NOT a problem** (so red text below doesn't waste attention). Call out SKIP'd diagnostics (e.g., D17 backend cross-check is always SKIP — that's expected, not a finding), enhanced-conversions and SST modules that are blocked pending GTM API access, and any flagged item that is a deliberate config choice rather than a bug. Degrade to: "No false alarms — every flagged item is real."}

{**Slot 4 — Inline-quoted fresh peer findings from Phase 3.5.** Quote the peer's score, date, and the specific top-line finding when one overlaps a flagged conversion action, campaign, or tag/consent issue. Because tracking is the constraint-cascade root, also surface contradictions explicitly: e.g., "A fresh `/bidding-auditor` report from {date} ({N} days old) calls Campaign X's tROAS healthy and learned — but D13 above shows that campaign's Purchase event hasn't fired in 7 days. The bid-strategy verdict is built on a broken signal; do not act on it until D13 is fixed." Or: "A fresh `/quality-score-auditor` report from {date} flagged Landing Page Experience on the same campaigns — D26 (Consent Mode v2 gap) is suppressing ~22% of conversions on those exact campaigns, so part of the LPX signal is a tracking artefact, not a page-quality problem." Omit this slot if no peers were fresh.}

{**Slot 5 — One line on how to read the rest.** "Module-by-module scoring and the diagnostic table follow below; jump to Critical Issues for the actionable list."}

{**Slot 6 — Score trend.** "Score: 78% — down from 84% last week. The drop is driven by the new Consent Mode v2 gap (D26)." Read from `context/analysis/tracking-audit-log.md` to compute. If no prior entry: "Baseline run — no prior score to compare against."}

---

## Overall Score

**{score}% — {Excellent / Good / Needs Attention / Critical}**

| Module | Score | Grade |
|--------|-------|-------|
| Completeness (D01-D07) | XX/XX | {grade} |
| Tag Health (D08-D17) | XX/XX | {grade} |
| **Overall** | **XX/XX** | **{grade}** |

## Critical Issues

{Only if any FAIL diagnostics exist. Sorted by severity descending.}

1. **[DXX] {Name}** — {one-line impact statement}
   - Finding: {what's wrong}
   - Impact: {business impact}
   - Fix: {specific action to take}

## Completeness Results (D01-D07)

| ID | Diagnostic | Status | Details |
|----|-----------|--------|---------|
| D01 | Coverage | {PASS/WARN/FAIL} | {one-line detail} |
| D02 | Primary/Secondary | {PASS/WARN/FAIL} | {one-line detail} |
| D03 | Duplicate Detection | {PASS/WARN/FAIL} | {one-line detail} |
| D04 | Naming Consistency | {PASS/WARN/FAIL} | {one-line detail} |
| D05 | Goal Category | {PASS/WARN/FAIL} | {one-line detail} |
| D06 | Counting Method | {PASS/WARN/FAIL} | {one-line detail} |
| D07 | Account Defaults | {PASS/WARN/FAIL} | {one-line detail} |

## Tag Health Results (D08-D17)

| ID | Diagnostic | Tier | Status | Details |
|----|-----------|------|--------|---------|
| D08 | Action Status | API | {PASS/WARN/FAIL} | {detail} |
| D09 | Volume Zero-Check | API | {PASS/WARN/FAIL} | {detail} |
| D10 | Volume Anomaly | API | {PASS/WARN/FAIL} | {detail} |
| D11 | Google Tag Presence | DevTools | {status or SKIP} | {detail} |
| D12 | Conversion Linker | DevTools | {status or SKIP} | {detail} |
| D13 | Tag Firing | DevTools | {status or SKIP} | {detail} |
| D14 | Transaction ID | DevTools | {status or SKIP} | {detail} |
| D15 | Dynamic Value | DevTools | {status or SKIP} | {detail} |
| D16 | Currency | DevTools | {status or SKIP} | {detail} |
| D17 | Backend Cross-Check | Manual | SKIP | Requires manual CRM comparison |

## Recommendations

{Ordered by priority. Tie back to business.md targets.}

1. {Highest priority recommendation}
2. {Second priority}
3. {Third priority}

## Manual Checks Required

{List any diagnostics that were SKIP'd with instructions for manual verification.}

## Data Freshness

| Data Source | Pulled | Age |
|------------|--------|-----|
| conversions-audit.csv | YYYY-MM-DD | {n} days |
| conversions-daily.csv | YYYY-MM-DD | {n} days |
| business.md | YYYY-MM-DD | {n} days |
```

---

## Log Template

Append to `context/analysis/tracking-audit-log.md` (append-only, one entry per run).

```markdown
## {YYYY-MM-DD} — Score: {score}% ({grade})

- **Mode:** {completeness / tag-health / consent / attribution / oct / hygiene / advanced / full}
- **Top finding:** {1-line — the single most impactful issue, e.g. "Purchase event misfiring on /thank-you (D13 FAIL — 0 firings in 7 days)" or "Clean — no critical issues"}
- **Fresh peer reports integrated:** {list of peer skills + dates, e.g. "/bidding-auditor (2026-04-29), /quality-score-auditor (2026-04-30)" or "none"}
- **Completeness:** XX/XX | **Tag Health:** XX/XX | **Consent:** XX/XX | **Attribution:** XX/XX | **OCT:** XX/XX | **Hygiene:** XX/XX | **Advanced:** XX/XX
- **Critical issues:** {count} | **Routing:** {list of next-step commands recommended}

| ID | Status | Detail |
|----|--------|--------|
| D01 | {status} | {brief} |
| ... | ... | ... |

**Top issues:** {comma-separated list of FAIL/WARN IDs}
**Actions taken:** {None / list}
```
