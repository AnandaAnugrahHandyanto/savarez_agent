# Keyword Optimizer — Peer Handoff & Mutation Sensitivity

This optimizer mutates the live account (pause, match-type swap, cross-negatives, duplicate resolution, zombie cleanup, optionally bid-strategy targets via KW-E08). Before generating any operations, it must consult fresh peer audits and recent peer mutations.

Two distinct mechanisms:

1. **Peer Audit Freshness Table** — fresh peer audit reports that gate or contextualize mutations.
2. **Mutation Sensitivity Matrix** — recent peer *mutations* in `context/account-changelog.md` that compound risk if stacked.

Both are consulted in **Phase 0.4: Peer Pre-flight** of `SKILL.md`.

---

## Peer Audit Freshness Table

`/keyword-auditor` is excluded — it is the upstream auditor for this optimizer and is consumed via `context/analysis/keyword-audit.md` in Phase 0.1. Its slot in the 10-peer table is filled by `/account-auditor`.

| Peer skill | Report file | Fresh window | Layer | Verdict if dirty/critical |
|---|---|---|---|---|
| `/quality-score-auditor` | `context/analysis/quality-score-audit.md` | ≤ 7 days | Eff | soft-warn |
| `/search-term-auditor` | `context/analysis/search-term-audit.md` | ≤ 7 days | Eff | soft-warn |
| `/budget-auditor` | `context/analysis/budget-audit.md` | ≤ 7 days | Bud | soft-warn |
| `/bidding-auditor` | `context/analysis/bidding-audit.md` | ≤ 7 days | Bid | soft-warn |
| `/competitive-analyst` | `context/analysis/competitive-audit.md` | ≤ 14 days | Comp | informational |
| `/lp-auditor` | `context/analysis/lp-audit.md` | ≤ 14 days | Conv | soft-warn |
| `/offer-auditor` | `context/analysis/offer-audit.md` | ≤ 30 days | Conv | soft-warn |
| `/tracking-specialist` | `context/analysis/tracking-audit.md` | ≤ 30 days | **M** | **HARD-BLOCK** if fail/critical |
| `/strategy-specialist` | `context/analysis/strategy-audit.md` | ≤ 30 days | **B** | **HARD-BLOCK** if unit economics missing/placeholder |
| `/account-auditor` | `context/analysis/account-audit.md` | ≤ 30 days | Struct | informational |

### Hard-block rule (universal)

If `/tracking-specialist` is fresh and reports failing/critical findings on a campaign in the operations plan, OR `/strategy-specialist` is fresh and unit economics are missing/placeholder — **refuse all mutations**. Print the failing finding(s) and the handoff command. Bid-strategy actions (KW-E08) are particularly sensitive to a missing `max_profitable_cpa` / `min_profitable_roas`; the existing Phase 0.3 already routes E08 to `/strategy-specialist` when those are absent — Phase 0.4 generalizes that gate to *all* mutation types.

**Hard-block is on the M / B layer being dirty**, not on the report being absent. Missing M/B reports degrade to soft-warn ("no fresh /tracking-specialist") — never auto-trigger a peer skill.

### Soft-warn rule

A fresh peer at Eff/Conv/Bud/Bid/Comp/Struct layers that flags issues on a campaign or ad group in the operations plan → surface in the dry-run "Cross-skill context" section, but do not block. Quote 1–3 findings (peer score, headline, date, affected campaign/ad-group when known).

Example surfaces:

- Fresh `/quality-score-auditor` shows QS 4 on an ad group containing keywords queued for KW-E03 match-type swap → soft-warn ("the swap may further hurt QS until ads relearn").
- Fresh `/search-term-auditor` shows uncovered n-gram waste on a campaign queued for KW-E01 pauses → soft-warn (consider negatives first, since pausing keywords doesn't stop the n-gram from triggering on broader matches elsewhere).
- Fresh `/budget-auditor` shows the campaign is budget-limited → soft-warn (pausing keywords here will redistribute spend, not save it).
- Fresh `/lp-auditor` shows LP failures on the campaign queued for cross-negatives (KW-E05) → soft-warn (the cannibalization may be a symptom of LP/offer mismatch, not keyword overlap).

### No fresh peer report

Never auto-trigger a peer skill from inside the optimizer. Note "no fresh {peer}" in the dry-run "Cross-skill context" so the operator knows the picture is incomplete and can run the peer themselves before approving.

### Freshness rule

The report header date inside the markdown is **canonical**. File mtime is a sanity check — if mtime is older than the header date by >3 days, treat the report as suspicious and surface the contradiction in the dry-run output (e.g. "tracking-audit.md header says 2026-04-15 but file mtime is 2026-04-08 — header date wins, but flag for operator review"). Never auto-defer to one or auto-override.

---

## Mutation Sensitivity Matrix

Read `context/account-changelog.md` (recommend ≤24h old; auto-refresh via `/account-changelog` if stale, or note the gap in dry-run if refresh declined). For every campaign and ad group in the operations plan, scan changelog entries within the windows below. Verdicts:

- **hard-block** — refuse mutation; require operator to remove the affected scope from the plan or pass an explicit override.
- **hard-warn** — list in dry-run "Cross-skill context" with a `WARN:` prefix; require operator to type "confirm" before proceeding to live apply.
- **soft-warn** — list in dry-run "Cross-skill context" as informational.

| Peer skill / source | Mutation type | Window | Scope match | Verdict | Rationale |
|---|---|---|---|---|---|
| `/rsa-maker`, manual ad edits | new ad / RSA edit / pause | ≤ 7d | overlapping ad group | soft-warn | Mid-test ad rotation — pausing/swapping keywords now muddies the ad-level read |
| `/bidding-optimizer` | bid strategy or target adjustment | 2–7d | overlapping campaign | soft-warn | Bid math still resettling; keyword pauses change the volume signal smart bidding learns from |
| `/search-term-optimizer` | negatives added / search terms promoted | ≤ 7d | overlapping campaign or ad group | soft-warn | Cohort already shifting; stacking keyword pauses muddies which lever moved efficiency |
| `/account-auditor`, `/account-changelog` | campaign restructure (rebuild, merge, split, ad-group reorg) | ≤ 14d | overlapping campaign | hard-warn | Data discontinuity — keyword history pre-rebuild is not comparable; pause/match-swap decisions on stale tier data are unsafe |
| `/keyword-optimizer` (self) | any prior keyword mutation | ≤ 7d | overlapping campaign or ad group | soft-warn | Don't stack — let the prior change settle before another wave on the same scope |
| `/budget-optimizer` | budget raise / cut | ≤ 7d | overlapping campaign | soft-warn | Budget change still propagating; keyword pauses now compound the volume signal change |
| `/geo-schedule-optimizer` | geo / device / schedule modifier | ≤ 7d | overlapping campaign | soft-warn | Targeting moved; keyword performance is being re-baselined under new traffic mix |
| `/placement-optimizer` | placement exclusion (Display / PMax overlap) | ≤ 7d | overlapping campaign | soft-warn | Traffic mix moved (rare for Search-only optimizer scope; informational) |
| `/tracking-specialist` | conversion goal change | ≤ 30d | account-wide | hard-warn | Conversion baseline shifted — historical CPA/ROAS no longer comparable, so pause/tier decisions built on the audit's tier table need re-validation |
| any peer | manual UI change of keyword fields (status, match type, bid) | ≤ 14d | overlapping ad group | hard-warn | Treat operator UI edits as equivalent to a self mutation — don't overwrite an in-flight manual experiment |

### KW-E08-specific tightening

When operations include KW-E08 (bid-strategy target updates), **all bidding-related entries in the matrix above promote one verdict tier**:

- `/bidding-optimizer` target adjustment 2–7d → **hard-warn** (was soft-warn) — never stack two target moves on the same campaign inside the learning window.
- `/keyword-optimizer` self bid mutation ≤ 7d → **hard-warn** (was soft-warn) — same rationale.
- Any manual UI bid-field edit ≤ 14d → **hard-warn** (already hard-warn; reaffirm).

This stacks on top of the existing 5 KW-E08 rails (max-change, learning lockout, conversion floor, budget-cap joint constraint, portfolio linkage) — it does not replace them.

### Self-mutation lookup

Self-mutation windows already encoded for KW-E08 in `meta.learning_gate` are honored by `mutate.js`. Phase 0.4 reads the *same* `account-changelog.md` plus the optimizer's own `keyword-changelog.md` and additionally cross-references peer-skill mutations the existing learning gate doesn't see.

### Override

Hard-warns can be confirmed inline at the dry-run step (single-line "confirm" with the campaign/ad-group + window referenced explicitly). There is no flag to silence them ahead of time — every session re-prompts on the relevant scope. Hard-block (M/B dirty) cannot be confirmed inline; only fixing the upstream report unblocks.

---

## Output Contract for Phase 0.4

Phase 0.4 produces an in-memory object consumed by Phase 1 (operations generation) and Phase 2 (dry-run rendering):

```json
{
  "hard_blocks": [
    { "peer": "/tracking-specialist", "report": "context/analysis/tracking-audit.md", "date": "...", "finding": "..." }
  ],
  "hard_warns": [
    { "campaign_id": "...", "campaign": "...", "ad_group_id": "...", "ad_group": "...", "peer": "/account-changelog", "mutation": "ad-group restructure", "date": "...", "days_ago": 9, "window": 14 }
  ],
  "soft_warns": [
    { "campaign_id": "...", "campaign": "...", "ad_group": "...", "peer": "/quality-score-auditor", "score": 62, "finding": "AG-level QS 4 on swap-target ad group", "date": "..." }
  ],
  "informational": [ ... ],
  "freshness_notes": [
    "no fresh /lp-auditor",
    "/tracking-specialist mtime 5d older than header — surfaced as suspicious"
  ]
}
```

Routing:

- `hard_blocks` non-empty → Phase 1 does not run; Phase 2 prints the block reasons + handoff commands.
- `hard_warns` non-empty → Phase 2 prints them in the dry-run "Cross-skill context" with `WARN:` prefix and collects an explicit "confirm" line per affected scope before allowing Phase 3 (live apply).
- `soft_warns` and `informational` → surfaced in the dry-run "Cross-skill context" block above the mutation table, no gating.
- `freshness_notes` → printed at the bottom of "Cross-skill context" so the operator knows where the picture is incomplete.

---

## Sequencing reminder

The optimizer does **not** write a sequenced report (that's the auditor's job). The handoff matrix here exists only to:

1. Pre-flight gate the mutation (hard-block / hard-warn / soft-warn).
2. Enrich the dry-run output with quoted peer findings on the campaigns/ad groups being mutated.

The user already chose to run the optimizer. The Cross-skill context section's role is to give them the data to *halt or downscope* the plan before live apply — not to re-route them to other skills.
