# Placement Optimizer — Peer Handoff & Mutation Sensitivity

This optimizer mutates the live account (placement exclusions, brand-safety settings, exclusion-list edits). Before generating any operations, it must consult fresh peer audits and recent peer mutations. Two distinct mechanisms:

1. **Peer Audit Freshness Table** — fresh peer audit reports that gate or contextualize mutations.
2. **Mutation Sensitivity Matrix** — recent peer *mutations* in `context/account-changelog.md` that compound risk if stacked.

Both are consulted in **Phase 0.5: Peer Pre-flight** of `SKILL.md`.

---

## Peer Audit Freshness Table

`/placement-auditor` is excluded — it is the upstream auditor for this optimizer and is consumed via `context/analysis/placement-audit.md` in Phase 0. `/account-auditor` takes its slot in the 10-peer rotation.

| Peer skill | Report file | Fresh window | Layer | Verdict if dirty/critical |
|---|---|---|---|---|
| `/quality-score-auditor` | `context/analysis/quality-score-audit.md` | ≤ 7 days | Eff | soft-warn |
| `/search-term-auditor` | `context/analysis/search-term-audit.md` | ≤ 7 days | Eff | soft-warn |
| `/keyword-auditor` | `context/analysis/keyword-audit.md` | ≤ 7 days | Eff | soft-warn |
| `/budget-auditor` | `context/analysis/budget-audit.md` | ≤ 7 days | Bud | soft-warn |
| `/bidding-auditor` | `context/analysis/bidding-audit.md` | ≤ 7 days | Eff | soft-warn |
| `/competitive-analyst` | `context/analysis/competitive-audit.md` | ≤ 14 days | Comp | informational |
| `/lp-auditor` | `context/analysis/lp-audit.md` | ≤ 14 days | Conv | soft-warn |
| `/offer-auditor` | `context/analysis/offer-audit.md` | ≤ 30 days | Conv | soft-warn |
| `/tracking-specialist` | `context/analysis/tracking-audit.md` | ≤ 30 days | **M** | **HARD-BLOCK** if fail/critical |
| `/account-auditor` | `context/analysis/account-audit.md` | ≤ 30 days | Struct | informational |

**Hard-block rule (universal M/B cascade).** Refuse all mutations if either:
- `/tracking-specialist` is fresh and reports failing/critical findings (M layer dirty), OR
- `/strategy-specialist` (`context/analysis/strategy-audit.md`, ≤ 30 days, **B** layer) is fresh and unit economics are missing/placeholder.

`/strategy-specialist` is not in the 10-peer rotation table above (the user-specified rotation reserves that slot for `/account-auditor`), but the universal M/B cascade still applies — the optimizer must check `strategy-audit.md` and refuse when the B layer is dirty. Print the failing finding(s) and the handoff command.

**Soft-warn rule.** A fresh peer at Eff/Conv/Bud layers that flags issues on a campaign in the operations plan → surface in the dry-run "Cross-skill context" section, but do not block.

**No fresh peer report.** Never auto-trigger a peer skill. Note "no fresh {peer}" in the dry-run context section so the operator knows the picture is incomplete.

**Freshness rule.** The report header date inside the markdown is canonical. File mtime is a sanity check — if mtime is older than the header date by >3 days, treat the report as suspicious and surface the contradiction in the dry-run output. Never auto-defer to one or auto-override.

---

## Mutation Sensitivity Matrix

Read `context/account-changelog.md` (must be ≤1h old per Phase 0.2 — auto-pull if stale). For every campaign in the operations plan, scan changelog entries within the windows below.

Verdicts:

- **hard-block** — refuse mutation; require operator to remove that campaign from the plan or pass an explicit override.
- **hard-warn** — list in dry-run "Cross-skill context" with a `WARN:` prefix; require operator to type "confirm" before proceeding.
- **soft-warn** — list in dry-run "Cross-skill context" as informational.

| Peer skill / source | Mutation type | Window | Verdict | Rationale |
|---|---|---|---|---|
| `/budget-optimizer` | budget raise / cut on overlapping campaign | ≤ 7d | soft-warn | Excluding placements + budget shift = compounded traffic-mix change; bidding still re-balancing |
| `/bidding-optimizer` | bid / target adjustment | ≤ 2d | soft-warn | Bidder still inside fresh learning window; new exclusions move the auction set under it |
| `/bidding-optimizer` | bid / target adjustment | 2–7d | soft-warn | Bid math just settled — new exclusions reshape traffic mix again |
| `/placement-optimizer` (self) | placement exclusion / list edit | ≤ 7d | soft-warn | Don't stack exclusions in tight succession — let the prior exclusion's traffic-mix change settle first |
| `/account-auditor`, `/account-changelog` | campaign restructure (rebuild, merge, split) | ≤ 14d | hard-warn | Data discontinuity — placement-performance signals can't lean on pre-restructure data |
| `/tracking-specialist` | conversion goal change | ≤ 30d | hard-warn | Conversion baseline shifted — placement-performance verdicts derived from old conversions are unreliable |
| `/geo-schedule-optimizer` | geo / device / schedule modifier | ≤ 7d | soft-warn | Targeting moved; placement traffic mix already shifting under it |
| any peer | manual UI change of placement / exclusion-list fields | ≤ 14d | hard-warn | Treat operator UI edits as equivalent to a self mutation — don't stack |

Hard-warn confirmations are captured inline in the session. The "confirm" prompt is plaintext, single-line, and must reference the specific campaign + window.

**Self-mutation lookup.** Self-exclusion windows are read from `context/account-changelog.md` only — there is no `meta.learning_gate` analog in placement-optimizer. Phase 0.5 is the single point where stacked-exclusion guards run.

**Override.** Hard-warns can be confirmed inline. There is no flag to silence them ahead of time — every session re-prompts on the relevant campaigns.

---

## Output Contract for Phase 0.5

Phase 0.5 produces an in-memory object consumed by Phase 1 (operations generation) and Phase 3 (dry-run rendering):

```json
{
  "hard_blocks": [
    { "peer": "/tracking-specialist", "report": "context/analysis/tracking-audit.md", "date": "...", "finding": "..." }
  ],
  "hard_warns": [
    { "campaign_id": "...", "campaign": "...", "peer": "/account-auditor", "mutation": "campaign restructure (split)", "date": "...", "days_ago": 9, "window": 14 }
  ],
  "soft_warns": [
    { "campaign_id": "...", "campaign": "...", "peer": "/budget-optimizer", "mutation": "budget raise +18%", "date": "...", "days_ago": 4, "window": 7 }
  ],
  "informational": [
    { "peer": "/competitive-analyst", "score": 72, "finding": "IS lost to budget 31% on Display" }
  ],
  "freshness_notes": [
    "no fresh /lp-auditor",
    "/tracking-specialist mtime 5d older than header — suspicious"
  ]
}
```

If `hard_blocks` is non-empty → Phase 1 does not run.
If `hard_warns` is non-empty → Phase 3 must collect explicit "confirm" before proceeding to Phase 4 (live apply).
`soft_warns` and `informational` are surfaced in the dry-run "Cross-skill context" block above the mutation table.
