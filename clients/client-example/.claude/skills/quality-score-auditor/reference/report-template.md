# Quality Score Auditor — Report Template

**Purpose:** Shape the Phase 2 report around the hypothesis list from `synthesis-playbook.md`. Downstream skills parse by section header — keep the structure stable.

The report is **explain-then-action**: a reader who only reads the Executive read at the top should still leave with the right next move. Tables, the Diagnosis paragraph, the Evidence Ladder, and module breakdowns are reference material for when the reader wants to dig in.

**Output file:** `context/analysis/quality-score-audit.md` (overwritten each run).
**Log file:** `context/analysis/quality-score-audit-log.md` (appended one-liner).

---

## Full report structure

```markdown
# Quality Score Audit — {date}

**Score: {score}/100 ({grade})**
**Evaluation period:** {period} days (excluding {lag}-day conversion lag)
**Historical period:** {history} days (for M3 trend analysis)
**Campaigns audited:** {count} Search campaigns
**Keywords analyzed:** {count} ({nonNullQs} with QS, {nullQs} null)

## Business Context (yardstick)
- **Primary KPI:** {cpa | roas}
- **Competitor campaigns:** {list or "none configured"}
- **Branded campaigns:** {list}
- **Bidding mode mix:** {n} Smart / {m} Manual campaigns — severity handling annotated per finding

---

## Executive read

{Prose only, no bullet lists, ≤300 words. Direct, confident, plain language. Cover all 6 slots in order:}

{**Slot 1 — Score meaning.** State what the score means in plain language for this account, not just the band name. "62/100 — Needs Attention" tells the reader nothing; "62/100 means Quality Score is dragging down Ad Rank on roughly a third of your active keywords, almost all of it traceable to one fixable layer (Ad Relevance) on two specific campaigns" tells them what to do. If a single component dominates (AR, Expected CTR, or LP Experience), name it here.}

{**Slot 2 — 1–3 things to do this week, ranked, each with the *why*.** Prose form. Name the lever, name the evidence, name the expected impact. Translate cascade language into plain English ("rewrite the RSAs in Campaign X so headlines echo the keywords literally" rather than "fix AR layer"). If the audit found nothing actionable: "Nothing urgent this week — every campaign is at Average or above on all three components, and historical trends are flat or improving." If branded-campaign QS escalation is in play, lead with it.}

{**Slot 3 — What is NOT a problem** (so red text below doesn't waste attention). Call out COMPETITOR-class AR Below Avg findings (structural, not a fix), INFORMATIONAL keywords routed away to `/keyword-auditor`, Smart Bidding `(dampened)` annotations, SKIP'd diagnostics, and false alarms. If no false-alarm risks today: "No red findings worth ignoring — every flagged item is real and in scope."}

{**Slot 4 — Inline-quoted fresh peer findings from Phase 1.6.** Quote the peer's score, date, and the specific top-line finding when one overlaps a flagged ad group, campaign, or URL. Pay special attention to the three structural overlaps. Examples: "A fresh `/lp-auditor` report from {date} ({N} days old) flagged the same campaigns for message-match failures — that's the same root cause this audit is naming as LP Below Avg from a different angle, so the LP fixes are the lever, not new RSAs." Or, when a peer contradicts: "A fresh `/keyword-auditor` report from {date} shows the AGs flagged for AR Below Avg are themed across genuinely different intents — copy fixes won't hold; the structural restructure has to happen first." If no peers were fresh, omit this slot.}

{**Slot 5 — One line on how to read the rest.** "The Diagnosis paragraph below is the client-facing explanation; module-by-module scoring, evidence ladder, and the three handoff queues follow. Jump to the Sequenced Handoff at the bottom for the action list."}

{**Slot 6 — Score trend.** "Score: 62/100 — down from 71 last week. The drop is driven by Module 2 (Component Breakdown), specifically a jump in AR Below Avg on Non-Branded campaigns." Read from `quality-score-audit-log.md` to compute. If no prior entry: "Baseline run — no prior score to compare against."}

---

## Diagnosis

*Write this section specialist-to-client. No "layer", "cascade", "classifier" language. No slash commands. Render money using `{currencySymbol}` resolved from `config.googleAds.currency` (see Phase 2 in SKILL.md). If currency is missing, use the three-letter code ("EUR 4,200/mo"), never a bare `$`.*

**In one line:** {Plain-English summary. What's wrong, in the words a specialist would use briefing their client. No jargon. Example: "Your ad copy doesn't match what people are searching for closely enough, and Google is charging you a CPC premium for it."}

**What's happening.** {2-3 sentences. Frame numbers as consequence, not classifier stats. Example: "134 of your 420 active keywords (32%) have ads Google rates 'below average' for relevance. More than half of all your Quality Score problems trace back to this one thing — it's not your landing pages, it's not your offer, it's the copy itself."}

**Where it hurts most.** {1-2 sentences. The top 2-3 campaigns or ad groups driving the damage, with spend (in the account's currency) or impressions so the reader can sanity-check. Example: "Two campaigns — 'Non-Branded - Generic' and 'Non-Branded - Competitors' — account for ~78% of the flagged keywords and ~{currencySymbol}4,200/mo of the wasted spend."}

**What to do first.** {Plain-English next action. No slash commands — those go in the Handoff Queue sections below. Translate the Headline Test to its meaning ("the keywords cover such different topics that no single ad can match all of them"). Example: "Rewrite the RSAs in those campaigns so the headlines echo the keywords literally. Two ad groups are a special case — the keywords inside them are about genuinely different topics, so no single ad can cover them well. Those need to be broken into separate ad groups before new copy will hold."}

---

**For the record (technical summary)**

- **Top hypothesis ({layer} layer):** {name}
- **Confidence:** {high | medium | low}
- **Explains approximately:** {pct}% of QS-related CPC premium
- **Blocking relationships:** {e.g. "ECTR fixes on {n} keywords are blocked until Ad Relevance is resolved" — or "none"}
- **Secondary hypotheses:**
  - {H2 — one-liner with explained waste %}
  - {H3 — one-liner}

---

## Evidence Ladder

### Business layer — bidding-mode context
- **Manual CPC campaigns:** {n} — QS directly scales CPC → full severity
- **Smart Bidding campaigns:** {n} — severity annotated `(dampened)` where applicable; QS still feeds Ad Rank

### Creative layer — inner cascade
- **AR (QS-D07):** {pct}% Below Avg (excl. COMPETITOR) → {PASS/WARN/FAIL}
- **ECTR (QS-D08):** {pct}% Below Avg → {PASS/WARN/FAIL} {note if AR is blocking}
- **LP (QS-D09):** {pct}% Below Avg → {PASS/WARN/FAIL}
- **Dominant limiting (QS-D10):** {AR / ECTR / LP / balanced}

### Classifier results
- `BRANDED`: {n} keywords — {low-QS count} flagged as brand-low-QS escalation
- `COMPETITOR`: {n} keywords — AR Below Avg count {n} (INFO only, not in handoff queue)
- `INFORMATIONAL` (Claude overlay): {n} keywords — route to `/keyword-auditor` for pause/negative decisions
- `GENERIC`: {n} keywords — standard cascade

### Historical trends (M3)
{If data available} Weighted account QS moved from {x} to {y} over {n} weeks. {n} keywords IMPROVING, {n} DECLINING, {n} STABLE, {n} INSUFFICIENT_DATA.
{Else} Insufficient history — account has < 60 days of stable QS data. M3 skipped.

### Competitive (M4)
{If D15 active} {n} campaigns have Lost IS (rank) > 15% AND weighted QS < 6 — QS is costing traffic.

---

## Module Scores

| Module | Score | Grade | Key Findings |
|---|---:|---|---|
| QS Distribution | {x}/20 | {grade} | {1-line} |
| Component Breakdown | {x}/45 | {grade} | {1-line} |
| Historical Trends | {x}/15 | {grade} | {1-line or "N/A — insufficient history"} |
| Competitive Context | {x}/20 | {grade} | {1-line} |

---

## Actions — segmented by cascade state

### 🔄 Recover creative (ordered by inner cascade)

Routes to downstream optimizers. Never executed by this skill.

| # | Action | Affected | Skill | Blocks |
|---|---|---:|---|---|
| 1 | Fix branded-campaign LP message-match | {n} kw | `/lp-auditor` → `/lp-optimizer` | — |
| 2 | Ad Relevance — copy fixes | {n} kw | `/rsa-maker` | ECTR fixes on same kw |
| 3 | Ad Relevance — structural splits (Headline Test failed) | {n} AGs | `keyword-restructurer` (pending — not yet built; see brief below) | ECTR fixes on same kw |
| 4 | LP Experience (parallel) | {n} kw | `/lp-auditor` → `/lp-optimizer` | — |
| 5 | Expected CTR (after AR resolved) | {n} kw | `/offer-maker` + `/rsa-maker` | — |

### ⚠️ Do NOT recommend fix

| # | Reason | Keywords | Handling |
|---|---|---:|---|
| 1 | COMPETITOR-class AR Below Avg — structural | {n} | INFO in report; excluded from AR handoff queue |
| 2 | Smart Bidding INFO-only findings | {n} | Annotated in report; full severity retained for investigation |
| 3 | INFORMATIONAL overlay — not a QS fix | {n} | Route to `/keyword-auditor` D17 for pause/negative |

---

## Handoff Queue — Ad Relevance (→ /rsa-maker)

Downstream `/rsa-maker` reads this table verbatim. COMPETITOR-class rows are excluded.

| ad_group | campaign | keywords_below_avg | impressions | class | dominant_issue | recommended_action |
|---|---|---:|---:|---|---|---|
| {AG} | {campaign} | {count} | {sum} | {class} | {issue} | copy fix / split |

## Handoff Queue — Expected CTR (→ /offer-maker + /rsa-maker)

Only populated when AR is Average+ on the target keywords.

| ad_group | campaign | keywords_below_avg | impressions | class | ar_status | recommended_action |
|---|---|---:|---:|---|---|---|
| {AG} | {campaign} | {count} | {sum} | {class} | Average+ | offer / CTA / differentiation |

## Handoff Queue — LP Experience (→ /lp-optimizer)

Grouped by `final_url` when possible so one LP fix resolves many keywords.

| final_url | ad_groups | keywords_below_avg | impressions | class_mix | recommended_action |
|---|---|---:|---:|---|---|
| {url} | {n} | {count} | {sum} | {e.g. 2 BRANDED, 5 GENERIC} | message match / speed / mobile / trust |

---

## Module Details

### Module 1: QS Distribution ({score}/20)
{Per-diagnostic breakdown, tables for D01 account-weighted, D02 low-QS %, D03 high-spend table, D04 per-campaign, D05 bottom-10 AG, D06 null-QS note.}

### Module 2: Component Breakdown ({score}/45)

**Classifier banner:** {n} keywords classified as COMPETITOR (AR findings INFO-only). {n} INFORMATIONAL overlay (route to `/keyword-auditor`).

**Required sub-sections, in this order:**

1. **QS-D07 — Ad Relevance** (non-COMPETITOR keywords). Table: ad_group, campaign, Below-Avg count, impressions, dominant issue, Headline Test hint.
2. **QS-D08 — Expected CTR.** Table: same columns + ar_status column flagging where ECTR fix is blocked by AR.
3. **QS-D09 — Landing Page Experience.** Table grouped by `final_url`.
4. **QS-D10 — Dominant limiting component.** Distribution chart (text-based): AR %, ECTR %, LP %.

### Module 3: Historical Trends ({score}/15)
{If active} Per-diagnostic breakdown; otherwise "N/A — account has < 60 days of stable QS history."

### Module 4: Competitive Context ({score}/20)
{D15 table — per-campaign Lost IS Rank, weighted QS, dominant component, recommended route.}
{D16 table — top-20 CPC premium keywords.}

### QS-D17 Customizer Integrity (INFO-only, does not affect score)

{If any AG has `integrity_status = BROKEN` or `EFFECTIVELY_STATIC`:} **WARN** — {n} ad group(s) have customizer references that don't resolve to a real value. Google renders the `:default` fallback every time for these RSAs, so the AG's effective ad pool is smaller than it looks. This is likely contributing to AR Below Avg ratings in these AGs.

**BROKEN** (attribute isn't defined on the account):

| ad_group | campaign | missing_attributes | RSAs_affected |
|---|---|---|---|
| {AG} | {campaign} | {attr1, attr2} | {n} |

**EFFECTIVELY_STATIC** (attribute defined but no binding at keyword / AG / campaign / customer level):

| ad_group | campaign | static_attributes | effective_resolution | RSAs_affected |
|---|---|---|---|---|
| {AG} | {campaign} | {attr1, attr2} | {attr1:NONE, attr2:NONE} | {n} |

{If all AGs are `OK` or `NO_CUSTOMIZERS`:} **PASS / INFO** — no unresolved customizer references detected. {n} AGs use keyword-level customizers, {m} use AG-level customizers, {p} use campaign- or customer-level customizers, {k} use no customizers.

**How to fix:**
- `BROKEN` → create the missing `customizer_attribute` (or remove the `{CUSTOMIZER.<name>}` reference from the RSA).
- `EFFECTIVELY_STATIC` → add a binding at the appropriate hierarchy level (keyword / AG / campaign / customer), or remove the reference and bake the intended value into the headline.

Re-audit after fixing to confirm AR recovery.

---

## Data Sufficiency Notes

{Bullets: null QS count, history depth, changelog freshness, COMPETITOR-classifier confidence, bidding-mode mix.}

{If `context/account-changelog.md` missing:} *Run `/gads-context` or `/account-changelog` to enable QS-D13 post-optimization correlation.*

{If history < 60 days:} *Re-audit in 30 days once M3 history stabilizes.*

{If `qs-ads.csv` missing:} *Ad-relevance keyword-to-ad gap evidence limited — run `/gads-context` for ads pull.*
```

---

## Append to audit log `context/analysis/quality-score-audit-log.md`

Append this entry to the log file. Create the file with `# Quality Score Audit Log` header if it doesn't exist.

```markdown
## {date} — Score: {score}% ({grade})

- **Top finding:** {1-line — the single most impactful issue or "Clean — no critical QS issues"}
- **Fresh peer reports integrated:** {list of peer skills + dates, e.g. "/lp-auditor (2026-04-28), /search-term-auditor (2026-04-30)" — or "none"}
- Period: {period}d | History: {history}d | Keywords: {count} (flagged {count})
- Top hypothesis: {layer} — {name} (confidence {x}, explains ~{pct}%)
- Module scores: M1 {x}/20 · M2 {x}/45 · M3 {x}/15 · M4 {x}/20
- Classifier: {n} BRANDED, {n} COMPETITOR, {n} INFORMATIONAL, {n} GENERIC
```

---

## Language rules for findings

Never conflate:

- **AR Below Avg (GENERIC):** Investigate keyword-to-headline overlap, ad group theming, customizer/DKI usage, RSA count + trajectory before framing. Cite specific evidence ("no headline mentions {X}", "ad group mixes {Y} and {Z} intents", "customizer values haven't been reviewed") — not stock phrasing like "copy needs a rewrite."
- **AR Below Avg (COMPETITOR):** "**INFO only — do NOT recommend AR fixes.** Targeting a competitor's brand with your own ad makes AR Below Avg structurally expected."
- **AR Below Avg (BRANDED):** "**Escalated — usually LP message-match or wrong URL.** Route to `/lp-auditor` first, then `/rsa-maker` if AR persists."
- **ECTR Below Avg on same keyword as AR Below Avg:** "**Blocked — fix AR first.** ECTR problems on weak-relevance keywords are symptoms."
- **ECTR Below Avg (not blocked by AR):** Investigate the RSA copy, ad age, trajectory, and (if available) competitor ads before framing the cause. The diagnosis must cite specific evidence, not default phrasing like "creative fatigue" or "not compelling enough."
- **LP Below Avg:** "Route to `/lp-auditor` → `/lp-optimizer`. Runs in parallel with AR/ECTR work."
- **Smart Bidding INFO:** "QS still feeds Ad Rank, but the algorithm compensates at the CPC layer. Investigate — don't silence."
