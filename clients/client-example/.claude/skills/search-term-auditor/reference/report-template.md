# Report Template — Search Term Auditor

Use this template when writing `context/analysis/search-term-audit.md`. The report is **explain-then-action**: a reader who only reads the Executive read at the top should still leave with the right next move. Tables, evidence ladder, and module breakdowns are reference material for when the reader wants to dig in. The structure is hypothesis-first, not diagnostic-first.

---

```markdown
# Search Term Audit — {YYYY-MM-DD}

**Score:** {score}/100 ({grade})
**Period:** {main}d main, {ngram}d n-grams · **Lag:** {lag}d · **Currency:** {symbol}
**Terms analyzed:** {termsA} (Period A) · {termsB} (Period B) · {pmaxTerms} (PMax)

> Portfolio: "{portfolio_name_1}" (tCPA={$x} | tROAS={y}, applies to: {campaigns})
> Portfolio: "{portfolio_name_2}" (tROAS={y}, applies to: {campaigns})
<!-- Include only when any record has target_source=portfolio. One line per unique portfolio. -->

---

## Executive read

{Prose only, no bullet lists, ≤300 words. Direct, confident, plain language. Cover all 6 slots in order:}

{**Slot 1 — Score meaning.** State what the score means in plain language for this account, not just the band name. "62/100 — Needs Attention" tells the reader nothing; "62/100 means roughly a third of search spend is going to terms the account can't convert at target, and most of it is concentrated in two ad groups" tells them what to do.}

{**Slot 2 — 1–3 things to do this week, ranked, each with the *why*.** Prose form. Name the lever (negate, route upstream, promote, fix conflicts), name the evidence (specific term cluster, n-gram, or campaign), name the expected impact. If the audit found nothing actionable: "Nothing urgent this week — here's what I checked and why it passed."}

{**Slot 3 — What is NOT a problem** (so red text below doesn't waste attention). Call out SKIP'd diagnostics, relevant-but-underperforming terms that look bad in the table but should *not* be negated, deliberate-but-flagged choices, and false alarms. If no false-alarm risks today: "No red findings worth ignoring — every flagged item is real."}

{**Slot 4 — Inline-quoted fresh peer findings from Phase 2.5.** Quote the peer's score, date, and the specific top-line finding when one overlaps a flagged term cluster, n-gram, or campaign. Example: "A fresh tracking audit from {date} ({N} days old) flagged the same campaigns for OCT misfire — the non-converting waste flagged here is partly a measurement artefact, not pure traffic quality." If a fresh peer report contradicts a search-term hypothesis (e.g. keyword-audit shows a flagged n-gram is the lead n-gram in a converting close-variant cluster), surface the contradiction here. If no peers were fresh, omit this slot.}

{**Slot 5 — One line on how to read the rest.** "Diagnosis, the evidence ladder by cascade layer, and the segmented Actions list follow below; jump to Actions for the actionable list."}

{**Slot 6 — Score trend.** "Score: 62/100 — down from 71 last week. The drop is driven by Module 3 (N-grams) — non-converting waste expanded into a new ad group." Read from `search-term-audit-log.md` to compute. If no prior entry: "Baseline run — no prior score to compare against."}

---

## Diagnosis

{One natural-language paragraph stating the root-cause hypothesis and what the reader should do first. Lead with the cascade layer and the specific finding — not a bullet list of symptoms.}

## Evidence Ladder

### Measurement layer
<!-- Only expand if an active Measurement hypothesis exists -->
- {bullet with source file and count} → H1
- {bullet} → H1

### Business layer
- {bullet} → H2
- {bullet} → H2

### Traffic layer
- {bullet} → H3

## Module Scores

| Module | Score | Grade |
|--------|------:|-------|
| 1 — Search Term Quality | {x}/25 | {grade} |
| 2 — Negative Coverage   | {x}/25 | {grade} |
| 3 — N-grams             | {x}/20 | {grade} |
| 4 — Close Variants      | {x}/15 | {grade} |
| 5 — Promotion & PMax    | {x}/15 | {grade} |
| **Total**               | **{score}/100** | **{grade}** |

## Actions

### 🔍 Investigate first
<!-- Only when Measurement or Business hypothesis is active -->
- **{hypothesis name}** → `/tracking-specialist`
- **{hypothesis name}** → `/strategy-specialist`

### 🔧 Structural fix needed
<!-- Used when B2 (relevant-but-underperforming) is active, or when target_source=fallback -->
- **{N} core-relevant terms underperforming** ({$ waste})
  - Root cause: LP conversion / offer fit / target stale — not traffic quality
  - Routes: `/lp-auditor`, `/offer-auditor`, `/strategy-specialist`

### ✅ Act now (safe)
<!-- Always-safe fixes + terms that passed the cascade -->
- **{X} negative conflicts** (ST-D08) → `/search-term-optimizer conflicts`
- **{Y} consolidation opportunities** (ST-D09 + D10) → `/search-term-optimizer consolidate`
- **{Z} legacy +modified +broad** (ST-D11) → `/search-term-optimizer negate` (format convert)
- **{A} irrelevant non-converters** (ST-D01 confirmed) → `/search-term-optimizer negate`
- **{B} n-gram candidates** (ST-D13 + D14 on non-core tokens) → `/search-term-optimizer ngrams`
- **{C} promotion candidates** (ST-D20, non-duplicate) → `/search-term-optimizer promote`

### ⚠️ Do NOT negate
- **{N} core-relevant underperforming terms** — these match your core business tokens and should be fixed upstream, never negated. See "Structural fix needed" above.
- **{M} converting OVER_TARGET terms** — these are profitable at the account-level target. Never negate.

## Module Details

### Module 1 — Search Term Quality

| Diagnostic | Verdict | Evidence |
|-----------|---------|----------|
| ST-D01 Irrelevant spend % | {verdict} | {X}% of {$total} ({$irr_spend}) |
| ST-D02 Non-converting terms | {verdict} | {N} terms, {$cost} (Search: {x}, PMax: {y}) |
| ST-D03 Underperforming | {verdict} | {N} terms, {$cost} |
| ST-D04 Foreign language | {verdict} | {N} terms sampled |
| ST-D05 Trending | INFO | {N} emerging terms |

### Module 2 — Negative Keyword Coverage

| Diagnostic | Verdict | Evidence |
|-----------|---------|----------|
| ST-D06 Campaigns without negatives | {verdict} | {N} campaigns |
| ST-D07 Campaigns without shared lists | {verdict} | {N} campaigns |
| ST-D08 Negative conflicts | {verdict} | {N} exact-match conflicts |
| ST-D09 Repeated ad-group negatives | {verdict} | {N} term/campaign combos |
| ST-D10 Repeated campaign negatives | {verdict} | {N} term combos |
| ST-D11 Legacy +modified +broad | {verdict} | {N} entries |
| ST-D12 Catalog completeness | {verdict} | {claude notes} |

### Module 3 — N-gram Analysis

| Diagnostic | Verdict | Evidence |
|-----------|---------|----------|
| ST-D13 Non-converting n-grams | {verdict} | {N} n-grams, {$cost} |
| ST-D14 Inefficient n-grams | {verdict} | {N} n-grams, {$cost} |
| ST-D15 List staleness | INFO | {N} lists (modified timestamps unavailable) |
| ST-D16 Volume concentration | INFO | Top 5 explain {x}% of flagged waste |

### Module 4 — Close Variant Monitoring

| Diagnostic | Verdict | Evidence |
|-----------|---------|----------|
| ST-D17 Performance drift | {verdict} | {N} variants |
| ST-D18 Spend share | {verdict} | {N} variants > 30% of parent |
| ST-D19 Unintended expansion | {verdict} | {N} semantic mismatches |

### Module 5 — Promotion & PMax

| Diagnostic | Verdict | Evidence |
|-----------|---------|----------|
| ST-D20 High performers not keywords | {verdict} | {N} candidates |
| ST-D21 Cross-campaign duplicates | {verdict} | {N} duplicates |
| ST-D22 Coverage ratio | {verdict} | {x}% of converting terms are keywords |
| ST-D25 PMax brand query % | {verdict} | {x}% of PMax terms match brand |
| ST-D26 PMax/Search overlap | {verdict} | {N} terms in both — handoff to `/keyword-auditor` (KW-D12) |

## Self-Learning Notes

{If the user marked terms as relevant or rejected n-grams during this session, list them here. These will be persisted to `context/analysis/search-term-decisions.json` and skipped on future runs.}

## Next Recommended Action

{Single sentence pointing to the top handoff from Phase 3.}
```

---

## Log append format (`search-term-audit-log.md`)

Append this entry to the log file. Create the file with `# Search Term Audit Log` header if it doesn't exist.

```markdown
## {YYYY-MM-DD} — Score: {score}/100 ({grade})

- **Period:** {main}d main / {ngram}d n-grams | Terms: {count} | Flagged: {count}
- **Top finding:** {1-line — the single most impactful issue or "Clean — cascade clear, no critical issues"}
- **Top hypothesis:** {layer} — {name} (confidence {x})
- **Fresh peer reports integrated:** {list of peer skills + dates, or "none"}
- **Top issues:** {one line per critical finding}
```
