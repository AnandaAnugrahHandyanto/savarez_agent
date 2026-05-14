# Synthesis Playbook — Search Term Auditor

Convert raw diagnostic flags into a ranked hypothesis list before writing any recommendation. Lighter than keyword-auditor's cascade — the search-term auditor only walks **Measurement → Business → Traffic**, because by the time a term is showing up as waste, Conversion and Creative are the wrong layers to intervene at (use the Conversion handoff instead).

**Always run B0 first.** The target-source gate is non-optional and catches the most common false finding.

---

## B0 — Target-source gate (MUST run first)

The analysis scripts call `lib.resolveBiddingStrategy()` per campaign and tag every flagged record with `target_source` ∈ `{ campaign_inline, portfolio, fallback, none }`. Interpret:

| target_source | Interpretation | What to do |
|---------------|----------------|-----------|
| `campaign_inline` | Campaign has its own target. Constrained. | Run all threshold checks normally. |
| `portfolio` | Campaign inherits a portfolio target. Constrained. | Cite `portfolio_name` in the report; do not call the campaign "unconstrained." |
| `fallback` | No inline, no portfolio — analysis used the global business.md default. Campaign is **unconstrained**. | The missing target is the issue. Route to `/strategy-specialist` *before* negating any flagged term. |
| `none` | No target available anywhere and no meaningful spend. | Skip target-based checks. |

When any record has `target_source=portfolio`, **open the report with a one-line portfolio notice**:

```
> Portfolio: "Aggressive ROAS" (tROAS=5.3, applies to: Campaign A, Campaign B, Campaign C)
```

List each unique portfolio once.

**Never write "campaign X is unconstrained" from a null inline target alone.** That produces false positives every time a portfolio supplies the target. Always read `target_source` first.

---

## M1 — Measurement layer

Read `context/analysis/tracking-audit.md` if it exists. Conditions that activate a **Measurement hypothesis** (blocks all negation recommendations until resolved):

- Tracking audit score < 70 on any of: completeness, tag health, attribution, OCT.
- Measurement FAILs flagged within the last 14 days that haven't been resolved.

When active, the only action on the search-term side is: "Pending `/tracking-specialist` — verify attribution before touching traffic."

If no tracking-audit.md exists, note the gap but don't block progress — measurement may be fine; the auditor is simply unverified.

---

## B1 — Business layer: targets current?

Read `context/analysis/strategy-audit.md` if it exists. Conditions that activate a **Business hypothesis**:

- Strategy audit score < 70 on targets or unit economics.
- `target_source=fallback` on any flagged campaign (campaign is using the business.md default, not a real target).

When active, route the user to `/strategy-specialist` before applying negations or promotions. Negating traffic when the target is wrong just compresses the account — it doesn't fix the underlying math.

---

## B2 — Business layer: relevant-but-underperforming

The most important rule in this playbook, and the most common false-negative trap.

For every flagged term in:
- `quality.underperformingTerms[]` (ST-D03)
- `ngrams.inefficient[]` (ST-D14)

…cross-reference against `business.md` core product / service tokens. Terms that match core business language are **relevant but underperforming** — they are a conversion problem (LP, offer, targets), not a traffic problem.

**Do not recommend negation for these.** The correct routing is:
- `/lp-auditor` — is the landing page converting this audience?
- `/offer-auditor` — does the offer match this intent?
- `/strategy-specialist` — is the target achievable with current unit economics?
- Only after those are addressed should the auditor consider a narrower negation scoped to sub-patterns.

Tag each such term with `relevance: core` in the Evidence Ladder and segment them into the `⚠️ Do NOT negate` bucket in Phase 2.

---

## Traffic layer — safe-to-act filter

A term is only safe to negate when **all** of these hold:

- No active Measurement hypothesis blocking its campaign
- `target_source ≠ fallback` on its campaign (if it is fallback, route to strategy first)
- Term is not core-relevant (B2 clear)
- Term is non-converting at meaningful spend (ST-D02/D13) OR clearly inefficient (ST-D03/D14) AND the query semantically mismatches the offer

Always-safe structural fixes pass without cascade verification:
- ST-D08 — negative conflicts (removing a bad negative never harms traffic)
- ST-D09 / D10 — consolidation **only when `likely_routing === false`** (see routing guard below)
- ST-D11 — legacy +modified +broad cleanup (deprecated format; no behavior change)

### Routing guard for ST-D09 / D10

Repeated negatives are NOT always a hygiene problem. A negative deliberately repeated across a cluster of campaigns or ad groups is often **intentional traffic routing** — the negative blocks a query in cluster A so it gets picked up by cluster B (which targets that query as a positive keyword). Promoting such a negative to a shared list linked to all campaigns will silently delete the routing.

**Worked example:** An account has a cluster of `Category-A` campaigns and a cluster of `Category-B` campaigns. The shared umbrella term for category B (`<term-B>`) is added as a campaign-level negative on every Category-A campaign so those queries route to the Category-B campaigns where `<term-B>` is a positive keyword. ST-D10 sees `<term-B>` repeated on ≥3 campaigns and flags it as a consolidation candidate. Promoting it to a shared list linked to ALL campaigns would also block `<term-B>` queries from Category-B — breaking the routing. That traffic just disappears.

**How the routing guard works:** `analyze-negatives.js` annotates every ST-D09/D10 entry with `likely_routing: true|false` and `routing_evidence`. An entry is flagged routing when the negative-term token appears as a positive keyword OR a converting search term in OTHER (non-flagged) campaigns / ad groups. Token matching is exact + substring (length ≥ 3) so compound words (e.g. a token nested inside a longer keyword in another language or domain) correctly trigger on the embedded token.

**Rules:**
- Only consolidation candidates with `likely_routing === false` may flow to `/search-term-optimizer consolidate`.
- Routing-flagged entries are reported as INFO only and excluded from the verdict count and the optimizer payload.
- The `searchTermAnalysis.routingNegatives` config array force-flags additional terms the user has already validated as routing.
- Required data: `keywords-active.csv` (pulled by `pull-all.js`). If missing, a warning is added to `meta.warnings` and the guard runs without positive-keyword evidence — false positives may pass through, so prefer re-running `pull-all.js` over acting on a degraded run.

---

## Hypothesis production

Produce an ordered list of hypotheses. Each hypothesis carries:

```yaml
id: H1
layer: Measurement | Business | Traffic
name: <short label>
evidence:
  - <bullet with source file and count>
  - <bullet with source file and count>
confidence: high | medium | low
blocks_negation: true | false
handoff: /tracking-specialist | /strategy-specialist | /lp-auditor | /offer-auditor | (none)
affected_waste_pct: <number>
```

The hypothesis list drives:
- The **Diagnosis** paragraph in Phase 2
- The **Evidence Ladder** (grouped by layer, each bullet tagged `→ H{n}`)
- The **Actions** segmentation (Investigate first / Structural fix / Act now / Do NOT negate)
- The **Sequenced handoff** in Phase 3

---

## Anti-patterns

Never do any of these:

1. **Assert "unconstrained" from null inline target alone.** Check `target_source` first. The portfolio-target bug is the exact reason the target-resolution contract was added (see keyword-auditor commit a8ae34f).
2. **Negate core-relevant terms.** If core tokens from business.md appear, these are front-door traffic. Route to LP/offer/target review.
3. **Negate before resolving Measurement.** Attribution anomalies can make terms look dead when they're actually converting. Always block negation on active Measurement hypothesis.
4. **Flat "Recommended Actions" table.** Always segment by cascade state. A tracking fix and a negation are not equivalent actions.
5. **Skip the portfolio notice.** When any record has `target_source=portfolio`, the header line must name the portfolio(s) and their targets. It prevents readers from assuming campaign-inline math.

---

## Checklist (run in order)

1. Read portfolio flags from every flagged record. Any `target_source=portfolio`? Write the portfolio notice.
2. B0 — bucket records by `target_source`. `fallback` records → Business hypothesis + route to strategy.
3. M1 — read tracking-audit.md. Active Measurement issues → block negations.
4. B1 — read strategy-audit.md. Stale targets → block negations; route to strategy.
5. B2 — cross-reference flagged terms against core tokens. Relevant terms → `⚠️ Do NOT negate` bucket.
6. Traffic — remaining terms pass the safe-to-act filter → `✅ Act now (safe)` bucket.
7. Always-safe structural fixes (D08/D09/D10/D11) → add to Act-now list regardless of cascade.
8. Rank hypotheses by layer (Measurement first) and within layer by explained waste %.
9. Produce the hypothesis list. Tag evidence bullets. Generate the report.
