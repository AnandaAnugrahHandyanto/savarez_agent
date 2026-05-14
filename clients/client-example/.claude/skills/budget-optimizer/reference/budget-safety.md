# Budget Optimizer — Safety Gates

Every operation must clear these gates before dry-run. mutate.js re-validates them; the SKILL fills them in operation-generation.

## Gate 1 — Cascade clearances

Each operation carries `meta.cascade_clear` with one of:

| Value | Meaning | Effect on mutation |
|---|---|---|
| `pass` | Layer is healthy or N/A | Allowed |
| `recommended` | Layer suggests upstream work first (Eff/Conv/Bid soft-blocks) | Soft block — requires `meta.confirmed = true` after the user types "confirm" |
| `soft-block` | Same as `recommended` (synonym) | Soft block |
| `blocking` | Hard fault — measurement/business missing | Hard refuse without `--override-{measurement|business}` |

**Hard blocks (M, B):** Optimizer hard-refuses every mutation. The user must:
1. Resolve via the peer skill, OR
2. Pass `--override-measurement --override-reason="..."` (or `--override-business --override-reason="..."`).

Overrides are LOGGED in mutation history and the changelog.

**Soft blocks (Eff, Conv, Bid):** The auditor recommends sequencing the upstream fix first. The user can choose to override by typing the literal word `confirm` (not `y`) when the SKILL prompts. The SKILL writes `meta.confirmed = true` into the operation; mutate.js reads that flag and allows the mutation.

## Gate 2 — Step cap

Default: **1.3× per single mutation**. With `--aggressive`: up to **1.5×**. Both configured via `budgetAudit.maxSingleMutationMultiplier`.

The cap matches the smart-bidding ~30% learning-reset threshold from /sops/Smart Bidding Mechanics Reference.md — moving the daily budget more than ~30% in one shot risks resetting smart-bidding learning, which delivers worse outcomes than the larger budget would suggest.

For a desired 2× raise, the SKILL splits into two mutations: 1.3× now, then another 1.3× ~14 days later (after smart bidding settles). mutate.js refuses any single op exceeding the cap.

## Gate 3 — Channel sanity (raise only)

For raises, mutate.js verifies:
- **Search / Shopping:** `new_daily_budget >= dailyBudgetToCpaRatio × tcpa` (default 2× tCPA). The SKILL passes `meta.tcpa` into the op; if missing, the gate is skipped (channel may not have a tCPA).
- **PMax:** `new_daily_budget >= meta.pmax_volume_floor` (configured per-account; the rules library surfaces a default). Volume floors live in `execute-rules.md`.

## Gate 4 — Mutation type asymmetry

| Type | Cascade required | Step cap | Sanity check |
|---|---|---|---|
| `raise` | M+B mandatory; Eff/Conv recommended | 1.3× (1.5× aggressive) | Channel-specific |
| `reduce` | M+B mandatory | none | none |
| `reallocate` | M+B mandatory; per-leg checks | per-leg cap | per-leg sanity |
| `fix-shared` | M+B mandatory | n/a | n/a (structural) |
| `pacing-adjust` | M+B mandatory | 1.3× (account-level monthly target adjustment) | none |

A `reallocate` op decomposes into a `reduce` leg + a `raise` leg, each independently gated.

## Gate 5 — Mandatory dry-run

**Every** invocation MUST first run `--mode=dry-run`. The SKILL refuses to call `--mode=live` without a fresh dry-run that PASSED API validation. There is no "skip the dry-run" flag.

## Gate 6 — Fresh data prerequisites

- `context/account-changelog.md` must be ≤ 1 hour old (auto-refresh on stale).
- `context/google-ads/data/campaign-budgets.csv` must exist and reflect the current account state. The SKILL re-pulls just the budget query immediately before generating ops.
- Auditor report `context/analysis/budget-audit.md` must exist.

## Gate 7 — Stacking prevention

Within a single session, the optimizer refuses to mutate the same `campaign_budget` resource_name twice. If the user wants a second mutation on the same budget, they must either run again later (operations are session-scoped) or submit them as a single combined op.

## Override flow

```
User: /budget-optimizer raise

SKILL: "Cascade for `Branded Search`: ✅ measurement ✅ business ⚠ efficiency
       (search-term-auditor flagged $420 of waste). Raising the budget will
       multiply that waste. Recommended: /search-term-optimizer first.

       Override and proceed anyway? Type 'confirm' (not 'y') with reason:"

User: "confirm — branded queries are protected and the waste is on the
       non-brand campaign which I'm handling separately"

SKILL: <writes meta.confirmed=true, meta.override_reason="..." into op>

mutate.js: ✅ soft block honored.
```

## Source

- /sops/Smart Bidding Mechanics Reference.md — 30% learning-reset threshold (origin of 1.3× cap)
- /sops/Budget Pacing Reference.md — 2× daily-spend rule (origin of dailyBudgetToCpaRatio gate)
- /sops/SOP – Scale Bids and Budgets.md — phased 14d cadence
