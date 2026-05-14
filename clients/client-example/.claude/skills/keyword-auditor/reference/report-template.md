# Keyword Auditor — Report Template

**Purpose:** Shape the Phase 2.6 report around the hypothesis list produced by `synthesis-playbook.md`, not around the flat diagnostic list. The reader must see the **Executive read** before anything else, the **diagnosis** before the **evidence**, and **actions** must be segmented by whether they are safe now, pending upstream verification, or require a structural fix in another skill.

The report is **explain-then-action**: a reader who only reads the Executive read at the top should still leave with the right next move. Tables, evidence ladders, and module breakdowns are reference material for when the reader wants to dig in.

## Full report: `context/analysis/keyword-audit.md`

```markdown
# Keyword Audit Report — {date}

**Score: {score}/100 ({grade})**
**Evaluation period:** {period} days (excluding {lag}-day conversion lag)
**Period A:** {start} → {end} | **Period B:** {start} → {end}
**Campaigns audited:** {count}
**Keywords analyzed:** {count} ({flagged} flagged)

---

## Executive read

{Prose only, no bullet lists, ≤300 words. Direct, confident, plain language. Cover all 6 slots in order:}

{**Slot 1 — Score meaning.** State what the score means in plain language for this account, not just the band name. "62/100 — Needs Attention" tells the reader nothing; "62/100 means roughly a third of flagged spend is sitting on keywords that look bad on paper but are actually your front door — pausing them would be the wrong move, and the real fix is one campaign target tweak plus an offer review" tells them what to do.}

{**Slot 2 — 1–3 things to do this week, ranked, each with the *why*.** Prose form. Name the lever, name the evidence, name the expected impact. Examples of keyword-domain levers: raise tCPA on the bleeding campaign, exclude bad n-grams via /search-term-auditor, consolidate duplicate keyword groups, fix obvious match-type conflicts, pause non-core zombies. If the audit found nothing actionable: "Nothing urgent this week — here's what I checked and why it passed."}

{**Slot 3 — What is NOT a problem** (so red text below doesn't waste attention). Call out OVER_TARGET keywords (profitable, do not pause), core product terms in UNPROFITABLE (front-door — fix the funnel, not the keyword), low-volume keywords inside statistical gates, and any flagged items already explained by a fresh peer report. If no false-alarm risks today: "No red findings worth ignoring — every flagged item is real."}

{**Slot 4 — Inline-quoted fresh peer findings from Phase 2.5.** Quote the peer's score, date, and the specific top-line finding when one overlaps a flagged keyword, ad group, or campaign. Example: "A fresh tracking-audit from {date} ({N} days old) shows attribution is healthy on the campaigns this audit suspected — that downgrades the Measurement hypothesis and unblocks the safe-pause list below." Or: "The {date} search-term-audit already isolated the bad n-gram driving Campaign X's UNPROFITABLE flag — exclude that n-gram instead of pausing the keyword." If no peers were fresh, omit this slot.}

{**Slot 5 — One line on how to read the rest.** "Diagnosis and the evidence ladder follow below; jump to the segmented Actions tables for the actionable list — Investigate-first comes before Act-now for a reason."}

{**Slot 6 — Score trend.** "Score: 62/100 — down from 71 last week. The drop is driven by Module 2 (Performance Segmentation) — more UNPROFITABLE keywords tipped past the gate." Read from `keyword-audit-log.md` to compute. If no prior entry: "Baseline run — no prior score to compare against."}

---

## Business Context (yardstick)
- **Profitability threshold (${primaryKPI}):** ${primaryKPI === 'cpa' ? '$' + breakEvenCPA : breakEvenROAS + 'x'}
- **Primary KPI:** `{primary}` @ ${value}/event | Secondary: `{secondary}` @ ${value}/event
- **Core product tokens:** {tokens}
- **Target fallback mode:** {disabled / campaign_target_only — with caveat}

---

## Diagnosis

{1 paragraph — the root cause hypothesis, not a symptom list. This section is the reader's biggest takeaway. Written as natural language. States what is probably wrong, at what layer of the constraint cascade, and what the reader should do first.}

**Top hypothesis ({layer} layer):** {name}
**Confidence:** {high / medium / low}
**Explains approximately:** {pct}% of flagged waste

{2-3 sentences that connect the dots: "The fact that 71% of UNPROFITABLE spend sits in one campaign AND that campaign's campaign target (tCPA/tROAS) is set against the profitability threshold AND the dominant keywords are core product terms means this is almost certainly a bid bleeding + offer problem, not a keyword problem. Pausing `example keyword` would remove the most relevant traffic the product can get."}

**Secondary hypotheses:**
- {H2 — one-liner with explained waste %}
- {H3 — one-liner}
- ...

**If all hypotheses above are wrong:** run the Act Now list below and re-audit in 14 days.

---

## Evidence Ladder

Grouped by cascade layer. Only layers with active hypotheses appear. Each bullet is a factual observation from the diagnostics that supports a hypothesis.

### Measurement layer {✅ clear / ⚠️ active}
- **M1 — Attribution anomaly:** {N} criterion_ids with identical primary conv counts across {N} campaigns. Example: `{kw}` in `{campA}` and `{campB}` both show {conv} primary conv on ${costA} vs ${costB} spend. **→ H{n} blocking**
- **M2 — Zero-conv concentration:** {pct}% of flagged spend in `{campaign}` with micro-conv CPA of ${x} (healthy) vs macro-conv CPA of ${y} (unhealthy).
- **M3 — Conversion lag:** configured lag ({n}d) vs documented lag ({m}d) → CPAs inflated by est. {pct}%.
- **M4 — Tier volatility:** {n} degradations; dominant shift is `{from}→{to}` ({pct}%).

### Business layer {✅ clear / ⚠️ active}
- **B1 — Campaign target bleeding in `{campaign}`:** campaign target against profitability threshold = ratio {r}. Campaign has {n} UNPROFITABLE + {m} OVER_TARGET keywords. **→ H{n}**
- **B3 — Core-term concentration:** {pct}% of UNPROFITABLE spend sits on `is_core_term=true` keywords. Core tokens matched: `{tokens}`. **→ H{n}**
- **B4 — Single-campaign concentration:** {pct}% of UNPROFITABLE spend in `{campaign}` (vs {pct}% of account spend). **→ H{n}**

### Conversion layer {✅ clear / ⚠️ active}
- **C1 — Funnel step drift:** micro→macro ratio moved {from}→{to} between Period B and Period A ({pct}% change). **→ H{n}**

### Traffic / Creative layer
- {Standard diagnostic rollups — KW-D01 through KW-D18 summary, kept short. These are the "things we counted" layer, not the root cause.}

---

## Module Scores

| Module | Score | Grade | Key Findings |
|--------|-------|-------|-------------|
| Match Type Health | {x}/20 | {grade} | {1-line} |
| Performance Segmentation | {x}/30 | {grade} | {1-line} |
| Cannibalization & Duplicates | {x}/25 | {grade} | {1-line} |
| Keyword Hygiene | {x}/10 | {grade} | {1-line} |
| Intent Alignment | {x}/15 | {grade} | {1-line} |

---

## Actions — segmented by cascade state

### 🔍 Investigate first (blocking — do not touch keywords yet)

Only populated if Measurement or Business or Conversion hypotheses are active. Each item includes the skill to run, the hypothesis it resolves, and what will unblock afterwards.

| # | Action | Skill | Resolves hypothesis | What this unblocks |
|---|---|---|---|---|
| 1 | {description} | `{/skill}` | H{n} — {name} | {downstream actions that become safe} |

### 🔧 Structural fix needed (needs another skill)

Core-term concentration in UNPROFITABLE, bid strategy at account level, LP/offer issues. Each routes to the right specialist, **not** to `/keyword-optimize pause`.

| # | Action | Skill | Affected | Est. impact |
|---|---|---|---|---|
| 1 | Adjust target (raise tCPA / lower tROAS) for `{campaign}` ${current}→${proposed} | `/keyword-optimize bids` (campaign-level) | {n} keywords | Unlock profitable volume currently bleeding |
| 2 | Audit offer/LP for `{campaign}` | `/lp-auditor` + `/offer-auditor` | Core product terms | Fix conversion path before pruning traffic |

### 🔄 Recover efficiency first

Before pausing any UNPROFITABLE keyword, attempt to recover its efficiency. Ordered by impact:

| Step | Skill | What it addresses | Expected impact |
|------|-------|-------------------|-----------------|
| 1 | `/search-term-auditor ngrams` (120–180d) | Verify at search-term level — exclude bad n-grams instead of pausing keywords | High — most actionable, least disruptive |
| 2 | `/offer-auditor` | Improve offer quality → higher CVR → borderline keywords become profitable | High — affects all keywords in campaign |
| 3 | `/lp-auditor` | Improve LP quality → higher CVR → same effect | High — affects all keywords to that LP |
| 4 | `/strategy-specialist` | Validate efficiency targets and unit economics | Medium — consider after offer/LP |
| 5 | `/bidding-specialist` (future) | Optimize profit-to-acquisition ratio (PAR) | Medium — bid strategy refinement |

Populated whenever UNPROFITABLE keywords exist that passed Layers 1–3. These keywords are converting but beyond the profitability threshold — recovery is preferred over removal.

{N} keywords totaling ${X} spend recommended for efficiency recovery before any pause action.

### ✅ Act now (safe regardless of cascade)

Only keywords/actions that survived the T1 safe-to-pause filter + all T2 always-safe structural fixes. Pause is ONLY listed here after the efficiency recovery sequence above has been presented — it is a last resort when recovery options have been exhausted or do not apply.

| # | Action | Keywords | Est. impact | Optimizer command |
|---|---|---|---|---|
| 1 | Pause {n} non-core UNPROFITABLE keywords | {list or sample} | ${x}/mo recovered | `/keyword-optimize pause` |
| 2 | Pause {n} ZOMBIE keywords | — | Signal cleanup | `/keyword-optimize cleanup` |
| 3 | Consolidate {n} duplicate keyword groups | — | Reduce self-competition | `/keyword-optimize duplicates` |
| 4 | Fix {n} match type conflicts via negatives | — | Reduce auction overlap | `/keyword-optimize match-type` |

### ⚠️ Do NOT pause (profitable, above campaign target)

OVER_TARGET keywords — profitable by profitability threshold but above campaign target (tCPA/tROAS). Recommendation: adjust target (raise tCPA / lower tROAS) or accept above-target performance.

| Keyword | Campaign | Spend | Primary CPA / Eff. ROAS | Max | Action |
|---|---|---:|---:|---:|---|
| ... | ... | ... | ... | ... | Bid review / adjust target (raise tCPA / lower tROAS) |

---

## Module Details

### Module 1: Match Type Health ({score}/20)
{KW-D01–D04 detail, short}

### Module 2: Performance Segmentation ({score}/30)

**Target source banner (required when any campaign uses a portfolio bid strategy):** Open Module 2 with a one-line banner listing the portfolios in use and the target each supplies, e.g. *"N campaigns run on portfolio bid strategy '{portfolio_name}' at tROAS {value}."* Use `target_source` + `portfolio_name` from `keyword-tiers.csv` to populate. If one or more campaigns fall back to a computed target (`target_source=fallback`), banner those separately as **unconstrained** and list their names — this is the only state that justifies an "effective Maximize Conversion Value / no efficiency floor" finding.

**Required sub-sections for KW-D07, in this order — never mix them:**

1. **Hypothesis-framed summary first.** Before any list, state: "X% of UNPROFITABLE spend sits on core product terms — the synthesis playbook flagged this as a structural hypothesis, not a pause candidate. See Diagnosis above." If the hypothesis is active, list core-term keywords in a "do not pause" table, with the reasoning.
2. **Non-core UNPROFITABLE** — these are the genuine pause candidates that survived the cascade. Table with keyword, campaign, spend, primary CPA / eff. ROAS, profitability threshold.
3. **PAUSE_CANDIDATE** — zero primary conv past statistical gate. Table. Note any with `is_core_term=true` still flagged — these got ×1.5 patience and may still warrant human judgment.
4. **OVER_TARGET (info, no pause)** — profitable, above campaign target (tCPA/tROAS). Always do-not-pause.
5. **Business context box** — show profitability threshold (break_even_cpa or break_even_roas based on primaryKPI), `primary_conversion_action`, `core_product_tokens` so the reader knows the yardstick. If `targetFallbackMode=campaign_target_only`, banner the caveat.

### Module 3: Cannibalization & Duplicates ({score}/25)
{KW-D10–D13 detail}

### Module 4: Keyword Hygiene ({score}/10)
{KW-D14–D15 detail}

### Module 5: Intent Alignment ({score}/15)
{KW-D17–D18 detail}

---

## Data Sufficiency Notes
{Conversion lag, window length, low-conv warnings, attribution anomaly caveats, portfolio bid strategy caveats}
```

## Append to audit log `context/analysis/keyword-audit-log.md`

Append this entry to the log file. Create the file with `# Keyword Audit Log` header if it doesn't exist. Lead with the date + score header so the log doubles as a trend index.

```markdown
## {date} — Score: {score}% ({grade})

- **Period:** {period} days | **Keywords:** {count} | **Flagged:** {count}
- **Top finding:** {1-line — the single most impactful issue or "Clean — no critical issues"}
- **Top hypothesis:** {layer} — {name} (confidence {high/medium/low}, explains ~{pct}% of flagged waste)
- **Fresh peer reports integrated:** {list of peer skills + dates, e.g. "tracking-audit (2026-04-29), search-term-audit (2026-04-30)" — or "none"}
- **Critical issues:** {count} | **Routing:** {list of /skill commands recommended, sequenced by cascade layer}

| Module | Score | Key Findings |
|--------|-------|-------------|
| Match Type Health | {x}/20 | {1-line summary or "Clean"} |
| Performance Segmentation | {x}/30 | {1-line summary} |
| Cannibalization & Duplicates | {x}/25 | {1-line summary} |
| Keyword Hygiene | {x}/10 | {1-line summary} |
| Intent Alignment | {x}/15 | {1-line summary} |
```

## Language rules for KW-D07 findings (unchanged — reinforced by synthesis layer)

Never conflate these three buckets:

- **UNPROFITABLE (non-core, cascade cleared)** = "pause — efficiency metric exceeds profitability threshold (CPA ${primary_cpa} > max ${break_even_cpa} / ROAS ${effective_roas} < min ${break_even_roas}) and cascade checks cleared."
- **UNPROFITABLE (core-term or cascade blocked)** = "**do NOT pause** — core product term or upstream hypothesis active. Route to {handoff}."
- **PAUSE_CANDIDATE** = "pause — $${cost} spent with 0 primary conversions past the statistical gate of $${pause_spend_threshold}" (mention core-term ×1.5 patience if `is_core_term=true`).
- **OVER_TARGET** = "**do NOT pause** — this keyword is profitable (efficiency metric within profitability threshold). Adjust target (raise tCPA / lower tROAS), segment, or accept the above-target performance."

Core product terms (`is_core_term=true`) always get a relevance caveat: "Core product term — ×1.5 patience applied before pause gate."
