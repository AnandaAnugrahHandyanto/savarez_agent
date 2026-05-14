# Budget Auditor — Handoff Matrix

The 8-layer cascade. Findings carry `blocking` tags that map to layers; this table dictates the order in which Phase 4 sequences handoffs.

| Layer | Type | Trigger conditions | Routes to |
|---|---|---|---|
| **M — Measurement** | BLOCKING | Tracking gap on flagged campaign; attribution fault; zero-conv anomaly | `/tracking-specialist` |
| **B — Business** | BLOCKING (profitability checks) | `primaryKPI` or `breakEven` missing/placeholder/stale | `/strategy-specialist` |
| **Bid — Bidding (peer)** | Sequenced | BUD-D05 (daily<2× tCPA); BUD-D08 (low conv vol); BUD-D19 (portfolio conflict) | `/bidding-specialist` (or `/bidding-auditor`) |
| **Eff — Efficiency Recovery** | Sequenced | Search-term waste; low QS; weak RSAs on flagged campaign | `/search-term-auditor`, `/keyword-auditor`, `/quality-score-auditor`, `/rsa-maker` |
| **Conv — Conversion** | Sequenced | Limited campaigns where CVR is the bottleneck | `/lp-auditor`, `/offer-auditor` |
| **Comp — Competitive** | Informational | IS Lost (Rank) vs IS Lost (Budget) decomposition needed | `/competitive-analyst` |
| **Struct — Structural** | Informational | Zero-spend; daypart-driven exhaustion | `/account-auditor`, `/geo-schedule-auditor`, `/account-changelog` |
| **T — Traffic (own optimizer)** | Last | Cascade cleared | `/budget-optimizer` |

## Per-diagnostic mapping

| Diagnostic | Default blocking tag(s) | When ALL clear, route to |
|---|---|---|
| BUD-D01 (limited status) | — | informs BUD-D03/D04 |
| BUD-D02 (IS-lost severity) | — | informs Comp layer |
| BUD-D03 (profitable+limited) | `business` (when KPI missing) | `/budget-optimizer raise` |
| BUD-D04 (unprofitable+limited) | `business` (when KPI missing); `efficiency`, `conversion` (recommended) | `/budget-optimizer reduce` after Eff/Conv clears |
| BUD-D05 (daily<2× tCPA) | `bidding` | `/bidding-specialist` |
| BUD-D06 (exhaustion timing) | — | `/budget-optimizer raise` OR `/geo-schedule-auditor` if daypart-driven |
| BUD-D07 (2× rule INFO) | — | none |
| BUD-D08 (smart-bidding floor) | `bidding` | `/bidding-specialist` |
| BUD-D09 (MTD vs target) | — | `/budget-optimizer pacing-adjust` |
| BUD-D10 (overspend) | — | `/budget-optimizer reduce` or `pacing-adjust` |
| BUD-D11 (underspend) | — | `/budget-optimizer reallocate` |
| BUD-D12 (seasonality) | — | `/budget-optimizer raise` (preemptive scale) |
| BUD-D13 (winner underfunded) | `business` (when KPI missing) | `/budget-optimizer reallocate` |
| BUD-D14 (loser overfunded) | `business`; `efficiency`/`conversion` (recommended) | `/budget-optimizer reduce` |
| BUD-D15 (cross-campaign efficiency) | `business` (when KPI missing) | `/budget-optimizer reallocate` |
| BUD-D16 (zero-spend active) | — | `/account-auditor` then `/account-changelog` |
| BUD-D17 (shared imbalance) | — | `/budget-optimizer fix-shared` |
| BUD-D18 (mixed objectives) | — | `/budget-optimizer fix-shared` (split pool) |
| BUD-D19 (portfolio conflict) | `bidding` | `/bidding-specialist` |

## Sequencing template (Phase 4 of SKILL.md)

When upstream layers are dirty, present:

> **Top hypothesis:** {layer} — {label}
>
> Before any budget change, run in order:
> 1. **M (blocking):** {handoff line}
> 2. **B (blocking):** {handoff line}
> 3. **Bid (peer):** {handoff line}
> 4. **Eff (recovery):** {handoff line}
> 5. **Conv (recovery):** {handoff line}
> 6. **Comp / Struct (informational):** {handoff line}
> 7. **T — `/budget-optimizer` only after the above:** {subcommand list}

When all upstream layers clear:

> Cascade clears 1–7 are green. Ordered by priority:
> - Always-safe: `/budget-optimizer fix-shared`, `/budget-optimizer pacing-adjust`
> - Reallocate: `/budget-optimizer reallocate`
> - Reduce: `/budget-optimizer reduce`
> - Raise (gated): `/budget-optimizer raise`

## Peer report freshness

Before any handoff, check the peer's report mtime per the auditor's Phase 3.5 lookup:

| Peer | Report path | Fresh window |
|---|---|---|
| `/quality-score-auditor` | `context/analysis/quality-score-audit.md` | ≤ 7 days |
| `/search-term-auditor` | `context/analysis/search-term-audit.md` | ≤ 7 days |
| `/keyword-auditor` | `context/analysis/keyword-audit.md` | ≤ 7 days |
| `/competitive-analyst` | `context/analysis/competitive-audit.md` | ≤ 14 days |
| `/lp-auditor` | `context/analysis/lp-audit.md` | ≤ 14 days |
| `/offer-auditor` | `context/analysis/offer-audit.md` | ≤ 30 days |
| `/bidding-auditor` | `context/analysis/bidding-audit.md` | ≤ 7 days |
| `/tracking-specialist` | `context/analysis/tracking-audit.md` | ≤ 30 days |
| `/strategy-specialist` | `context/analysis/strategy-audit.md` | ≤ 30 days |
| `/account-auditor` | `context/analysis/account-audit.md` | ≤ 30 days |

Fresh report → quote 1–3 findings into the budget audit's executive read; replace "run /peer" with "review existing {date} report at {path}". Stale → keep the re-run handoff.
