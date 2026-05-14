# Budget Auditor — Report Template

Write to: `context/analysis/budget-audit.md`. The report is organised around the **hypothesis list from Phase 1.5 + the cross-skill peer findings from Phase 3.5**, NOT around the diagnostic list. The reader should be able to act from the Executive read alone.

```markdown
# Budget Audit — {date}

**Score:** {N}/100 ({grade})
**Window:** {period} days | **Module scope:** {full | limitation | sufficiency | pacing | allocation | shared | opportunities}
**Run by:** /budget-auditor at {timestamp}
**Campaigns audited:** {N} enabled+serving ({M} base + {E} active experiment variants{; experiments excluded if base-only})
**Currency:** {accountCurrency}

## Executive read

Two to four short paragraphs, written like an analyst briefing the user — not a diagnostic dump. Cover, in order:

1. **What the score means in plain English.** Don't just restate the band. Translate it: "Budget health is in good shape — the score is anchored by X, the genuine concern is Y." If the score looks worse than reality (a SKIP'd Pacing module, a single shared budget dragging Module 5, a single unprofitable campaign concentrating the FAIL), say so.
2. **The 1–3 things that actually matter this week.** Ranked. Each one named in a single sentence with the *why*, not just the *what*. Distinguish "do this" from "investigate this" from "leave alone — it's deliberate."
3. **What is NOT a problem**, briefly. If FAIL counts are inflated by a deliberate branded shared pool, an under-funded geo test, an N/A module, or a flagged campaign whose tracking is broken (so the "unprofitable" label is unreliable), name them so the user doesn't waste attention on red text further down.
4. **Cross-skill integration.** If Phase 3.5 surfaced a fresh peer report whose finding overlaps a flagged campaign, **quote it inline here** — score, date, the specific top-line finding. Example: "The fresh quality-score-audit from 2026-04-27 (5 days old) found Landing Page Experience driving 90% rank-lost IS on the same non-branded campaigns I see flagged for IS Lost (Budget) — raising those budgets won't recover the lost traffic; LP fixes will." This is the single most valuable line in the report.
5. **How to read the rest.** One line: "Skim Module scores → jump to Risks for the action list → Module details are reference."

Tone: direct, confident, plain language. **No bullet lists in this section** — flowing prose. Keep total length under ~300 words.

## Diagnosis (technical)

One paragraph stating the root-cause hypothesis, the cascade layer, and what the reader should do first. Lead with: "The leverage point is at the **{layer}** layer — {one-sentence root cause}." Cite the diagnostics that triggered the hypothesis. Avoid bullet lists. This restates the Executive read in cascade-layer terms for downstream skills and the audit log — keep both sections; don't merge.

## Top hypothesis

- **Layer:** {M / B / Bid / Eff / Conv / Comp / Struct / T}
- **Name:** {hypothesis label, e.g. "Profitable+limited campaigns blocked by stale break-even" or "Allocation drift toward unprofitable PMax"}
- **Confidence:** {low / medium / high}
- **Evidence:** {1–3 sentences citing the diagnostics that triggered + any peer-report cross-validation from Phase 3.5}

## Module scores

| Module | Score | Status |
|---|---|---|
| Allocation | {x}/30 | {band} |
| Limitation | {x}/25 | {band} |
| Pacing | {x}/15 (or N/A) | {band or "redistributed"} |
| Sufficiency | {x}/15 | {band} |
| Shared Budgets | {x}/15 (or N/A) | {band or "redistributed"} |
| **Total** | **{x}/100** | **{grade}** |

## Risks (segmented by cascade state)

Render only sections that have content.

### 🔍 Investigate first (blocking handoffs)

Populate when M (measurement) or B (business) hypotheses are active. Each entry names the campaign, the specific failure mode, and the next skill — quoting an existing peer report's findings if Phase 3.5 found a fresh one.

- **{Campaign}** — {one-line failure}. {If fresh peer report exists: "Review the existing {date} {peer} report at `{path}` — top finding: '{one-liner}'."} → `/{handoff-skill}`

### 🔧 Bidding-side fix first (Bid layer — peer with budget)

When BUD-D05 / BUD-D08 / BUD-D19 fire, the budget side is downstream of a tCPA / portfolio decision. Examples:

- **{Campaign}** — daily budget ${X} is below 2× tCPA ${Y}. Smart bidding can't bid up to target inside this daily ceiling. The fix isn't more budget; it's reconciling the tCPA with the spending ceiling. → `/bidding-specialist` (then return to `/budget-optimizer raise` once tCPA is resolved).

### 🔄 Recover efficiency first (Eff / Conv layer — top hypothesis)

When Eff or Conv hypotheses are active, **always integrate the fresh peer report's specific findings** here, not just a "go run X" line. Example shape:

- **LP Experience driving 90% rank-lost IS on `/google-slides-ai`** → Review the existing **2026-04-27 quality-score-audit.md** (5 days old, fresh) — top finding: *"Systemic LP Below Avg driving Ad Rank suppression across non-branded campaigns; fix `/ai-powerpoint-maker` and `/google-slides-ai` first."* Then: `/lp-auditor` on those two URLs → `/lp-optimizer`. Re-run `/quality-score-auditor` only if you want fresher data.

Sequence the handoffs: search-term → keyword-auditor → quality-score-auditor → rsa-maker → lp-auditor → offer-auditor.

### ⚖️ Allocation moves (after upstream layers clear)

For BUD-D13, BUD-D14, BUD-D15. Each entry names the leg of the reallocation:

- **Reduce {Campaign A}** ($X/day → $Y/day, freeing ~$Z/mo) → `/budget-optimizer reduce`
- **Raise {Campaign B}** ($X/day → $Y/day, paired) → `/budget-optimizer raise` (or combine into one `/budget-optimizer reallocate`)

### ✅ Act now (T layer — pure budget, cleared cascade)

Only items where every upstream layer has cleared. Each entry names the optimizer subcommand and the projected `+$/mo` (or freed `-$/mo`).

- **{Campaign}** — raise daily $X → $Y (+$Z/mo) → `/budget-optimizer raise`. Cascade: ✅ all clear.

### ⚠️ Hold (recently changed)

Campaigns whose budget changed within the last 14 days appear here with a note "in learning — verify on {date+14d before reacting}". The optimizer hard-refuses any further mutation on these in the same session.

### ℹ️ Confirm intent (INFO — review, not action)

Findings that look red but are usually deliberate: shared budget heavily skewed by design (branded-pool routing), zero-spend on a campaign you paused yesterday but is still ENABLED, a low daily budget on a deliberate small geo test. Name each one so the user doesn't worry about the FAIL count.

## Opportunities

Always present, even when there are zero risks. Cross-cutting list:

| # | Type | Campaign / scope | Projected impact | Action |
|---|---|---|---|---|
| 1 | profitable_limited_recovery | {camp} | +{X} conv/30d at projected ${Y} CPA (within ${break_even}) → +${M}/mo at projected profit | `/budget-optimizer raise` |
| 2 | winner_underfunded | {camp} | Currently {N}% of total spend at profitable margin {%}; reallocating $X/day from {camp B} buys +{Y} conv/30d | `/budget-optimizer reallocate` |
| 3 | seasonality_ramp | Account | Highlight month "{november}" begins in {N} days; ramp profitable campaigns preemptively | `/budget-optimizer raise` |
| 4 | underspend_redeploy | Account | Projecting ${X} unspent this month — deploy to winners or hold | `/budget-optimizer reallocate` |

If `breakEven` was missing, mark profit projections as "investigate" instead of dollarizing them, and add a note that resolving unit economics (`/strategy-specialist`) unlocks the projections.

## Pacing snapshot (only when Module 3 ran)

```
MTD spend:        {X} {currency}
Days elapsed:     {n} of {m}
Avg daily so far: {Y} {currency}
Projected month:  {Z} {currency} ({+/-pct}% vs target {target})
Seasonality:      {currentMonth} ({"highlight" | "approaching highlight" | "flat"})
```

CSV reference: `context/analysis/budget/pacing-projection.csv` (account daily series + projected daily run-rate to month end).

## Sequenced handoffs

Render the Phase 4 template here. **Apply Phase 3.5 lookup results to every line** so each handoff says either "run /peer" (missing/stale) or "review existing {date} report at {path}" (fresh, with the one-liner finding).

When upstream layers are dirty, the Sequenced handoffs section should read like a numbered protocol the user can follow top-to-bottom without thinking — e.g.:

> **Top hypothesis:** Eff — LP Experience suppressing rank-lost IS account-wide.
>
> Before any budget change, here's what to do, in order:
>
> 1. **Eff (active):** Review the existing 2026-04-27 quality-score-audit.md — top finding: *"…fix `/ai-powerpoint-maker` and `/google-slides-ai` first."* Then `/lp-auditor` on those two URLs → `/lp-optimizer`.
> 2. **Conv (peer):** No fresh `/lp-auditor` report — run after Eff layer clears.
> 3. **T (after the above):** {N} reallocation moves → `/budget-optimizer reallocate`. {K} raises gated until Eff clears → `/budget-optimizer raise` (will refuse without `confirm` keyword while QS findings are unresolved).

When all layers are clear, Sequenced handoffs collapses to a short ordered list of safe optimizer subcommands.

## Module details

For each diagnostic, list verdict + one-line evidence + suggested next step. Mark INFO-only diagnostics clearly. SKIP'd diagnostics get a single line stating why (e.g. "BUD-D17 SKIP — no shared budgets in account; module N/A; 15 pts redistributed").

```
### Module 1 — Limitation (X/25)

| ID | Campaign | Verdict | Note |
|---|---|---|---|
| BUD-D01 | {camp} | WARN | IS Lost (Budget) {pct}% — {next-step pointer} |
| BUD-D02 | (account) | PASS | 0 campaigns ≥ 25% IS Lost (Budget) |
| BUD-D03 | {camp} | WARN | Profitable + limited; opportunity row #1 above |
| BUD-D04 | {camp} | PASS | No unprofitable + limited |
```

(Repeat for Modules 2–5.)

## Configuration snapshot

- Monthly target: `{monthlyBudgetTotal}` {currency} ({"fallback mode active" | "configured"})
- Per-campaign overrides: {N}
- Seasonality: {mode}; highlight months: {list or "—"}
- Daily budget : tCPA ratio threshold: {value} (default 2.0)
- Max single-mutation multiplier: {value} (default 1.3×)
- Last analyst confirmation: {date}
- Primary KPI / break-even (resolved from sibling configs): {kpi} / {breakEven}
- Experiments scope: {INCLUDED (active variants count) | excluded (base-only)}

---

## Append to audit log `context/analysis/budget-audit-log.md`:

```markdown
## {date} — Score: {score}/100 ({grade})
- Period: {period}d | Campaigns: {n} | Consumers (after experiment grouping): {m}
- Top hypothesis: {layer} — {label}
- Active blocking layers: {list or "none"}
- Top finding: {1-line}
- Cross-skill peer reports integrated: {list of {peer, date} or "none"}
```
```

---

## Style guidelines (for the SKILL.md to follow when generating)

- **Prose first, tables second.** The Executive read and Diagnosis sections are paragraphs. Tables appear only when the data benefits from columns (Module scores, Opportunities, Module details).
- **Quote, don't link.** When a peer report is fresh, paste the one-liner finding into THIS report. Don't say "see the QS audit" — extract the headline and put it in the Risks section, attributed by date and path.
- **Sequence, don't menu.** Handoffs are a numbered protocol. Never present a flat menu of "you could try X or Y or Z" when the cascade gives a clear order.
- **Round to whole dollars** in `+$/mo` projections — transparency over tidy numbers.
- **Name reality, not just verdict.** A FAIL on BUD-D04 isn't "fix this" — it's "this campaign is losing money at the current target; the right move is reduce or pause, not optimize." Say that.
- **Surface deliberate red.** A 90%-dominated branded shared budget might be intentional. Flag it as INFO with "confirm intent — likely deliberate".
- **Limit Executive read to ~300 words.** Long reports are skimmed; tight reads are acted on.
