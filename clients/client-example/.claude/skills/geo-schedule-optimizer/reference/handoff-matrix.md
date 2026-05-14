# Geo-Schedule Optimizer — Peer Handoff & Mutation Sensitivity

This is the **optimizer** variant of the cross-skill peer-lookup pattern. Optimizers don't write reports — they mutate the account. So the matrix plugs in differently from auditors:

- **Mode 1 — Pre-flight gate** (Phase 3.5): hard-block when the **measurement (M)** or **business (B)** layer is dirty; soft/hard-warn when peers have made recent mutations that would compound or contradict our changes.
- **Mode 2 — Enrichment**: in the dry-run output, append a "Cross-skill context" section that quotes 1–3 findings from fresh peer audit reports relevant to the campaigns being mutated.

`/geo-schedule-auditor` is **excluded** from this table — it is the upstream input the optimizer was already designed to read in Phase 0/1.

---

## Mutation Sensitivity Matrix

What kinds of recent peer activity should gate this optimizer?

| Peer activity | Window | Severity | Why it matters here |
|---|---|---|---|
| Bid / target adjustments on overlapping campaigns (e.g., `/bidding-optimizer`, `/bidding-specialist`, manual tCPA / tROAS edits) | 2–7 days | **Soft-warn** | Geo, schedule, device, and demographic modifiers are **multiplicative on top of base bids/targets**. A recent target change is still settling — stacking modifier deltas on top muddies attribution and risks over-correction. Recommend waiting 7d post-bid-change, or proceeding with smaller modifier caps. |
| Smart Bidding migration (any campaign moving into `TARGET_CPA`, `TARGET_ROAS`, `MAXIMIZE_CONVERSIONS`, `MAXIMIZE_CONVERSION_VALUE`) | ≤ 14 days | **Hard-warn** | Manual location/schedule/device modifiers are **ignored** under most Smart Bidding strategies (only -100% exclusions still apply). After a migration, the optimizer's behavior must adapt: existing manual modifiers should be **removed** (they are noise), not tuned. Block tuning ops; allow only -100% exclusions and modifier-removal ops. |
| Self mutations — prior `/geo-schedule-optimize` run on the same campaigns | ≤ 7 days | **Soft-warn** | Don't stack geo/schedule/device changes on top of fresh ones. The previous run hasn't had time to produce signal yet — a second pass within 7d is almost always premature and risks chasing noise. Recommend waiting until the prior changelog is at least 7d old, unless this run is a corrective rollback. |
| Budget changes on flagged campaigns (`/budget-optimizer`, manual budget edits) | ≤ 7 days | **Soft-warn** | Location and daypart waste shifts with budget. After a budget raise, the campaign sees **new** geo/hour combinations it couldn't reach before — the geo-schedule-auditor's CPA/conv distributions are about to refresh. After a budget cut, the marginal-spend tail compresses. In both cases, modifier formulas computed off pre-change performance data drift from reality. Recommend a 7d cooldown or re-run the auditor after the budget change has settled. |

**Severity behavior:**

- **Hard-block** (M / B layer): Phase 3.5 stops the optimizer outright. No operations file is generated. Output the handoff line and exit.
- **Hard-warn** (Smart Bidding migration): Stop and require explicit acknowledgement. Offer to proceed with **only** -100% exclusion ops (skip all bid-modifier tuning). User must say "proceed exclusions only" or "abort."
- **Soft-warn** (peer mutation): Continue. Surface in the dry-run "Cross-skill context" section as a flag the user must read before approving. Approval still gates Phase 4.

---

## Peer freshness table (Mode 2 enrichment)

For each peer, check the report's mtime against the fresh window. If fresh → quote 1–3 findings tied to campaigns in the operations file into the dry-run "Cross-skill context" section. If stale → omit (don't auto-defer; the user can re-run if they want).

| Peer skill | Report file | Fresh window |
|---|---|---|
| `/quality-score-auditor` | `context/analysis/quality-score-audit.md` | ≤ 7 days |
| `/search-term-auditor` | `context/analysis/search-term-audit.md` | ≤ 7 days |
| `/keyword-auditor` | `context/analysis/keyword-audit.md` | ≤ 7 days |
| `/budget-auditor` | `context/analysis/budget-audit.md` | ≤ 7 days |
| `/bidding-auditor` | `context/analysis/bidding-audit.md` | ≤ 7 days |
| `/competitive-analyst` | `context/analysis/competitive-audit.md` | ≤ 14 days |
| `/lp-auditor` | `context/analysis/lp-audit.md` | ≤ 14 days |
| `/offer-auditor` | `context/analysis/offer-audit.md` | ≤ 30 days |
| `/tracking-specialist` | `context/analysis/tracking-audit.md` | ≤ 30 days **(M layer — hard-block if dirty)** |
| `/account-auditor` | `context/analysis/account-audit.md` | ≤ 30 days |

`/strategy-specialist` is the **B layer** — handled directly in Phase 3.5 as a hard-block, not an enrichment source.

---

## Freshness rule (canonical)

When a peer report exists:

1. **Header date is canonical.** Read the date from the report's first-line `# … — YYYY-MM-DD` header (or the explicit `Generated: {date}` field if present). Use that, not file mtime, when the two disagree.
2. **Surface contradictions.** If header date and file mtime differ by more than 24h, flag it in the dry-run output ("Quality Score audit header says 2026-04-20 but file mtime is 2026-05-01 — review which is correct"). Do not silently pick one.
3. **Never auto-defer.** If a report is stale, the optimizer **does not** automatically pause to wait for a re-run. It simply omits the enrichment quote and notes "no fresh `/peer` report (last: {date}, window: ≤ Nd)" in the Cross-skill context section. The user decides whether to re-run.

The hard-block / hard-warn rules in the Mutation Sensitivity Matrix are **separate** from staleness — those gate on **what changed recently**, not on **what's missing**.

---

## How Phase 3.5 uses this file

1. **M-layer check:** Read `context/analysis/tracking-audit.md`. If header date > 30 days old, OR module score < 70 on any tracking module → **hard-block**.
2. **B-layer check:** Read `context/analysis/strategy-audit.md`. If primaryKPI / breakEven / target-CPA fields are missing, placeholder, or stale → **hard-block**.
3. **Mutation-sensitivity scan:** Read `context/account-changelog.md` and any sibling optimizer changelogs (`context/analysis/bidding-changelog.md`, `context/analysis/budget-changelog.md`, `context/analysis/geo-schedule-changelog.md`). Apply each row of the matrix above against campaigns appearing in the operations file. Emit hard-warn / soft-warn lines.
4. **Enrichment scan:** Walk the peer freshness table. For each fresh peer, pull 1–3 findings tagged to mutated campaigns into the dry-run output.
