# Budget Auditor — Synthesis Playbook

The auditor must form a root-cause hypothesis BEFORE recommending action. A flat list of "raise this, reduce that" is mechanically correct but strategically wrong when an upstream layer (tracking gap, missing break-even, search-term waste) explains the symptom.

The cascade walks **Measurement → Business → Bidding → Efficiency → Conversion → Competitive → Structural → Traffic** and stops at the first active layer with a usable hypothesis. Two layers are blocking; the rest are sequenced or informational.

## Required checks (every audit)

1. **M layer (Measurement)** — BLOCKING.
   - Tracking-specialist has unresolved findings on a flagged campaign? `/tracking-specialist` first.
   - Recent zero-conv anomaly on a flagged campaign? Don't recommend ANY budget change.

2. **B layer (Business)** — BLOCKING for profitability-dependent diagnostics.
   - `primaryKPI` or `breakEven` missing? BUD-D03/D04/D13–D15 return INFO with `blocking: ['business']` and route to `/strategy-specialist`.
   - Stale unit economics (>90d since `business.md` updated)? Same handoff.

3. **Bid layer (Peer with bidding-specialist)** — Sequenced before budget changes.
   - BUD-D05 fires (daily budget < 2× tCPA)? Daily budget alone won't fix smart-bidding starvation; route to `/bidding-specialist` for tCPA review first.
   - BUD-D08 fires (insufficient conv volume for smart bidding)? Same — strategy-side fix sequences before raise.
   - BUD-D19 fires (shared+portfolio conflict)? Same.

4. **Eff layer (Efficiency)** — Sequenced before raising budgets.
   - Search-term waste on a flagged campaign? `/search-term-auditor` recovers spending headroom WITHOUT raising the budget.
   - Low Quality Score? `/quality-score-auditor` lowers CPCs and frees the same budget to reach more clicks.
   - Weak RSAs? `/rsa-maker` boosts CTR — same effect.

5. **Conv layer (Conversion)** — Sequenced before raising budgets.
   - Low CVR + budget-limited? Raising budget multiplies the leak. `/lp-auditor`, `/offer-auditor` first.

6. **Comp layer (Competitive)** — Informational.
   - High IS Lost (Rank) coexists with IS Lost (Budget)? `/competitive-analyst` decomposes which lever is worth pulling.

7. **Struct layer (Structural)** — Informational.
   - Zero-spend active campaigns? `/account-auditor` (policy/approval/targeting) and `/account-changelog` (recent edit may have caused it).
   - Daily exhaustion before EOD? `/geo-schedule-auditor` if daypart-driven.

8. **T layer (Traffic, own optimizer)** — Last.
   - Cascade clears 1–7 → `/budget-optimizer` is the right next step.

## Hypothesis labels

Every finding emitted by the engines carries a `blocking` tag (zero or more of: `measurement`, `business`, `bidding`, `efficiency`, `conversion`). Phase 1.5 builds a ranked hypothesis list:

- **M1** — Tracking gap on flagged campaign (don't change budget on broken-tracking campaign).
- **M2** — Conversion lag exceeds window (recent budget changes need more time to show effect).
- **B1** — Stale targets / `target_source=fallback` (can't tell profitable from unprofitable).
- **B2** — Profitability threshold may be stale (>90d).
- **Bid1** — Daily budget below 2× tCPA (target adjustment first).
- **Bid2** — Smart-bidding learning constrained by budget (low conv volume — switch strategy).
- **Bid3** — Shared budget + portfolio strategy conflict.
- **Eff1** — Search-term waste — fix before raising budget.
- **Eff2** — Low QS — Quality Score work before raising budget.
- **Eff3** — Weak RSAs — improve creative before raising budget.
- **Conv1** — Low CVR — fix LP/offer before raising budget.
- **Comp1** — IS Lost decomposition (budget vs rank).
- **Struct1** — Zero-spend due to policy/approval/targeting.
- **Struct2** — Budget exhaustion timing = daypart issue.
- **T1** — Pure budget action (raise/reduce/reallocate/share-fix) — only after cascade clears.

## Anti-patterns

- Never recommend a raise while M or B is blocking. Replace with the handoff.
- Never recommend a raise on an unprofitable campaign — that's a reduce candidate.
- Never recommend stacking a raise + reduce on the same campaign in one session.
- Never raise more than `maxSingleMutationMultiplier` (default 1.3×) without explicit `--aggressive` from the user.
- Never write a flat actions table that mixes a tracking handoff with a raise — segment by cascade state.

## Source

- /sops/Budget Allocation Mental Model.md — 4-step framework (rank → reallocate → recover → raise)
- /sops/SOP – Scale Bids and Budgets.md — phased scaling workflow
- /sops/Bid Scaling Mental Model.md — PAR-zone reasoning
