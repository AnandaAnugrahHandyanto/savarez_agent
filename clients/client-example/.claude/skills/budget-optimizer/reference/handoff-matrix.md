# Budget Optimizer — Handoff Matrix

This is the **peer-lookup** matrix for the optimizer. Unlike auditors (which write reports for users), optimizers mutate the account — so this matrix has two distinct uses:

1. **Pre-flight gate** (Phase 3.5 in `SKILL.md`) — read fresh peer audits + the account-changelog before showing any dry-run / mutation. Hard-block on M/B dirty; soft-warn on Eff/Conv dirty; hard-warn on recent overlapping peer mutations per the **Mutation Sensitivity Matrix** below.
2. **Context enrichment** — the dry-run output's "Cross-skill context" section quotes 1–2 fresh peer findings touching campaigns in the plan.

The optimizer does **not** consume the per-diagnostic routing patterns the auditor uses — its job is to mutate, not to refer out. Refusal to mutate IS the handoff.

---

## Peer report freshness table (10 peers)

`/budget-auditor` is excluded — it's the upstream audit feeding this optimizer (already loaded in Phase 0).

| Peer skill | Report file | Fresh window | Layer | On dirty (any open finding overlapping mutation campaigns) |
|---|---|---|---|---|
| `/tracking-specialist` | `context/analysis/tracking-audit.md` | ≤ 30 days | **M (Measurement)** | **HARD-BLOCK** — refuse all mutations until resolved or `--override-measurement --override-reason="..."` is passed |
| `/strategy-specialist` | `context/analysis/strategy-audit.md` | ≤ 30 days | **B (Business)** | **HARD-BLOCK** — refuse all mutations until `primaryKPI` + `breakEven` resolved or `--override-business --override-reason="..."` is passed |
| `/quality-score-auditor` | `context/analysis/quality-score-audit.md` | ≤ 7 days | Eff (Efficiency) | Soft-warn on `raise` only; reduce/reallocate/fix-shared/pacing-adjust ignore |
| `/search-term-auditor` | `context/analysis/search-term-audit.md` | ≤ 7 days | Eff (Efficiency) | Soft-warn on `raise` only |
| `/keyword-auditor` | `context/analysis/keyword-audit.md` | ≤ 7 days | Eff (Efficiency) | Soft-warn on `raise` only |
| `/bidding-auditor` | `context/analysis/bidding-audit.md` | ≤ 7 days | Bid (peer) | Soft-warn on `raise` only — bid/target faults compound a budget raise |
| `/lp-auditor` | `context/analysis/lp-audit.md` | ≤ 14 days | Conv (Conversion) | Soft-warn on `raise` only |
| `/offer-auditor` | `context/analysis/offer-audit.md` | ≤ 30 days | Conv (Conversion) | Soft-warn on `raise` only |
| `/competitive-analyst` | `context/analysis/competitive-audit.md` | ≤ 14 days | Comp | Informational — surface in dry-run "Cross-skill context", do not block |
| `/account-auditor` | `context/analysis/account-audit.md` | ≤ 30 days | Struct | Informational — surface in dry-run "Cross-skill context", do not block |

### Freshness rule (canonical)

The **header date** inside each report (e.g., `Generated: 2026-04-28`) is canonical; the file mtime is a sanity check only.

- If header date and mtime disagree by >24h, **surface the contradiction** in the pre-flight summary ("`tracking-audit.md` header says 2026-04-12 but file mtime is 2026-04-30 — re-run to disambiguate"). Do not silently auto-defer to either.
- If a report is missing entirely, treat the layer as **unknown** — for M/B that means hard-block (cannot mutate without proof of clean measurement/business); for Eff/Conv/Bid that means surface "no recent {peer} audit on file" but do not block.
- Stale (older than the fresh window): treat as missing for blocking purposes; quote the stale finding in the dry-run "Cross-skill context" with a `[stale: {N}d]` tag so the user sees it.

### "Open finding overlapping mutation campaigns"

A peer report's finding is **open and overlapping** when:
1. It has not been marked resolved in the report's status frontmatter or executive read.
2. The finding's affected `campaign.id` (or campaign_name fallback) appears in the operation set being generated.

For M/B layers, the finding need not name a specific campaign — any open M/B fault hard-blocks every mutation regardless of overlap (you cannot trust budget moves on an account whose tracking or unit economics are dirty).

---

## Mutation Sensitivity Matrix (account-changelog cross-checks)

In addition to peer audits, the optimizer reads `context/account-changelog.md` and checks **recent peer mutations** against the campaigns being touched. Stacking changes within these windows compounds the cascade and makes the budget mutation risky.

| Recent change in changelog | Window | Severity | Trigger condition |
|---|---|---|---|
| Bid / target adjustment (tCPA, tROAS, max-CPC ceiling) on a campaign in this op set | **≤ 2 days** | **HARD-WARN** | Canonical case: "bid change 2d ago + budget raise = dangerous" — the budget multiplies a not-yet-stabilized bid change. Smart bidding learning takes 7–14 days; 2 days is mid-learning. |
| Bid strategy migration (e.g., manual→tCPA, tCPA→Max Conv) on a campaign in this op set | **≤ 14 days** | **HARD-WARN** | Strategy migrations reset learning entirely. A budget mutation during the 14-day re-learning window distorts the strategy's signal. |
| Conversion goal / primary action change on the account or any campaign in this op set | **≤ 30 days** | **HARD-WARN** | Goal swaps invalidate historical CPA/ROAS used to size the budget; 30d covers one full learning + validation cycle. |
| Budget change made by `/budget-optimizer` itself (this skill, prior session) on the same `campaign_budget` resource | **≤ 7 days** | **SOFT-WARN** | Don't stack budget changes; let the previous mutation stabilize. Gate 7 (in `budget-safety.md`) blocks within-session stacking; this matrix extends that across sessions. |
| Structural change on a campaign in this op set (new ad group, status flip, network setting change, geo/schedule swap, campaign rename) | **≤ 30 days** | **HARD-WARN** | Structure changes alter the traffic mix the budget is feeding. Wait for spend to normalize on the new structure. |

### Severities defined

- **HARD-WARN:** Optimizer prints the warning, names the recent change with date + actor, and **requires the user to type `confirm + reason`** (same flow as soft-block cascade overrides) before adding the op to the dry-run set. Distinct from `--override-measurement` / `--override-business` (which are CLI flags for true hard-blocks).
- **SOFT-WARN:** Optimizer prints the warning inline in the cascade summary. The user does not need to type `confirm` — but the warning shows in the dry-run table.
- **HARD-BLOCK** (M/B from peer audits): same as `budget-safety.md` Gate 1 — refuse without the corresponding CLI override.

### How changelog parsing works

Use the `account-changelog` lib helpers (already imported in Phase 0.4). Match on `change_resource_type`:

- `BIDDING_STRATEGY`, `CAMPAIGN.bidding_strategy_type`, `CAMPAIGN.target_cpa`, `CAMPAIGN.target_roas`, `CAMPAIGN.maximize_conversions.target_cpa`, `CAMPAIGN.maximize_conversion_value.target_roas` → bid/target adjustment
- Strategy type swap (old → new differs) → strategy migration
- `CONVERSION_ACTION`, `CUSTOMER_CONVERSION_GOAL`, `CAMPAIGN_CONVERSION_GOAL` → conversion goal change
- `CAMPAIGN_BUDGET` (where the actor is this skill — see `tmp/budget-optimizer/mutations-*.json` history) → self-stacking
- `AD_GROUP` (new), `CAMPAIGN.status`, `CAMPAIGN.network_settings`, `CAMPAIGN.geo_target`, `CAMPAIGN.ad_schedule`, `CAMPAIGN.name` → structural

Date math uses the changelog row's `change_date_time` vs `now`. Round to whole days (UTC).

---

## Cross-skill context — dry-run rendering

Phase 3 of `SKILL.md` includes a "Cross-skill context" section above the per-mutation table. It quotes 1–2 fresh peer findings touching any campaign in the plan, formatted:

```
Cross-skill context (peer audits read this session):
- /search-term-auditor (2026-04-29, 3d ago): "Branded Search has $420 of irrelevant
  search-term spend in 30d (top n-gram: 'free trial')." → soft-warned the raise on
  Branded Search.
- /bidding-auditor (2026-04-30, 2d ago): "Performance Max — Lead Gen tCPA target
  $35 is 1.4x current 30d CPA $25; volume floor not met." → informational.
```

If no fresh peer findings overlap the plan, render `Cross-skill context: clean (no overlapping peer findings).`

---

## Phrasing rules (Phase 3.5)

| Situation | What the SKILL says |
|---|---|
| Peer report fresh + dirty + overlaps | "Fresh `/{peer}` audit ({date}, {N}d ago) flags `{campaign}`: {one-line finding}. {Action: hard-block / soft-warn / informational}." |
| Peer report fresh + clean | (silent — no surface) |
| Peer report stale | "`/{peer}` audit is {N}d old (>{window}d window). Treating as missing — re-run for current state, or proceed if context is unchanged." |
| Peer report missing + M/B layer | "No `/{peer}` audit on file. {Layer} is required clean before mutating. Run `/{peer}` first, or pass `--override-{measurement\|business} --override-reason=\"...\"`." |
| Peer report missing + Eff/Conv/Bid layer | "No `/{peer}` audit on file — proceeding without that signal." |
| Changelog match (HARD-WARN) | "⚠ Recent change risk: `{campaign}` had a {bid/target/strategy/conversion-goal/structure} change on {date} ({N}d ago). Stacking a budget {raise/reduce} on top is risky. Type 'confirm + reason' to proceed, or skip this op." |
| Changelog match (SOFT-WARN) | "ℹ Recent budget change on `{campaign_budget}` from {date} ({N}d ago) by /budget-optimizer. Letting it stabilize is recommended." |
| Header date vs mtime mismatch | "`/{peer}` audit header says {header_date} but file was modified {mtime_date} — contradiction. Re-run to disambiguate." |
