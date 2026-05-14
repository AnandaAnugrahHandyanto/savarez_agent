# Bidding Auditor — Report Template

Write to: `context/analysis/bidding-audit.md`. The report is organised around the **hypothesis list from Phase 1.5**, not around the diagnostic list.

```markdown
# Bidding Audit — {date}

**Score:** {N}/100 ({grade})
**Window:** {period} days | **Module scope:** {full | strategy | targets | learning | portfolio | adjustments | cpc | value-rules}
**Run by:** /bidding-auditor at {timestamp}

## Executive read

Two to four short paragraphs, written like an analyst briefing the user — not a diagnostic dump. Cover, in order:

1. **What the score means in plain English.** Don't just restate the band. Translate it: "Bidding is in decent shape — the scoring noise comes from X, the genuine concern is Y." If the score looks worse than the reality (e.g. zombie campaigns, structural N/As), say so explicitly.
2. **The 1-3 things that actually matter this week.** Ranked. Each one named in a single sentence with the *why*, not just the *what*. Distinguish "do this" from "investigate this" from "leave alone — it's deliberate."
3. **What is NOT a problem**, briefly. If FAIL counts are inflated by ended experiments, deliberate Manual CPC choices, or N/A modules, name them so the user doesn't waste attention on red text further down.
4. **How to read the rest.** One line: "Skim Module scores → jump to the Risks section for the action list → the Module details are reference."

Tone: direct, confident, plain language. No bullet lists in this section — flowing prose. Keep total length under ~250 words.

## Diagnosis (technical)

{One paragraph stating the root-cause hypothesis, the cascade layer, and what the reader should do first. Lead with "The problem is at the {layer} layer — {one-sentence root cause}." Avoid bullet lists here. This restates the Executive read in cascade-layer terms for downstream skills and the audit log — keep it; don't merge with the Executive read above.}

## Top hypothesis

- **Layer:** {M / B / Vol / Eff / Conv / Bud / Comp / Struct / T}
- **Name:** {hypothesis name}
- **Confidence:** {low / medium / high}
- **Evidence:** {1-3 sentences citing the diagnostics that triggered this hypothesis}

## Module scores

| Module | Score | Status |
|---|---|---|
| Target Validation | {x}/25 | {band} |
| Strategy Selection | {x}/20 | {band} |
| Learning Phase | {x}/15 | {band} |
| Portfolio Health | {x}/15 | {band} |
| CPC & Cost Health | {x}/10 | {band} |
| Conversion Value Rules | {x}/10 | {band} |
| Bid Adjustments | {x}/5 | {band} |
| **Total** | **{x}/100** | **{grade}** |

## Risks (segmented by cascade state)

### 🔍 Investigate first (blocking handoffs)

Populate only when M or B hypotheses are active. Format:

- {finding} → `/{handoff-skill}`

### 🔧 Structural fix needed

For BID-D14, BID-D17, mixed-portfolio, etc.

### 🔄 Recover efficiency first

When Eff or Conv hypotheses are active. Sequence: search-term → keyword-auditor → quality-score → rsa-maker → lp-auditor → offer-auditor.

### ✅ Act now (safe)

Only items that survived all cascade layers above. Each entry names the optimizer subcommand.

### ⚠️ Hold (in learning)

BID-D11, BID-D13. List the campaigns and the date the window clears.

## Opportunities

Cross-cutting list, populated even when there are zero risks:

| # | Type | Campaign | Projected impact | Action |
|---|---|---|---|---|
| 1 | starvation_recovery | {camp} | +{X} conv/30d at projected CPA ${Y} | `/bidding-optimizer adjust-targets` |
| 2 | budget_lost_recovery | {camp} | +{X} conv at ${Y} CPA | `/budget-optimizer raise` paired with `/bidding-optimizer scale` |

## Learning state (permanent fixture)

| Campaign | Strategy | Last strategy change | Last target change | Days since strategy / target | In learning |
|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... |

## Module details

For each diagnostic, list verdict + evidence + suggested next step. Mark INFO-only diagnostics clearly.

## Configuration snapshot

- Primary KPI: {cpa | roas}
- Break-even: ${break_even}
- Posture: {growth | balanced | efficiency} (PAR target {x.y})
- Last confirmed: {date}
```

## Append to audit log `context/analysis/bidding-audit-log.md`:

```markdown
## {date} — Score: {score}/100 ({grade})
- Period: {period}d | Campaigns: {n}
- Top hypothesis: {layer} — {name}
- Active blocking layers: {list}
- Top finding: {1-line}
```
