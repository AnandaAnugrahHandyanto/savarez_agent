# Bidding Optimizer — Peer Handoff & Mutation Sensitivity

This optimizer mutates the live account. Before generating any operations, it must consult fresh peer audits and recent peer mutations. Two distinct mechanisms:

1. **Peer Audit Freshness Table** — fresh peer audit reports that gate or contextualize mutations.
2. **Mutation Sensitivity Matrix** — recent peer *mutations* in `context/account-changelog.md` that compound risk if stacked.

Both are consulted in **Phase 0.5: Peer Pre-flight** of `SKILL.md`.

---

## Peer Audit Freshness Table

`/bidding-auditor` is excluded — it is the upstream auditor for this optimizer and is consumed via `context/analysis/bidding-audit.md` in Phase 0.1. `/lp-auditor` takes its slot.

| Peer skill | Report file | Fresh window | Layer | Verdict if dirty/critical |
|---|---|---|---|---|
| `/quality-score-auditor` | `context/analysis/quality-score-audit.md` | ≤ 7 days | Eff | soft-warn |
| `/search-term-auditor` | `context/analysis/search-term-audit.md` | ≤ 7 days | Eff | soft-warn |
| `/keyword-auditor` | `context/analysis/keyword-audit.md` | ≤ 7 days | Eff | soft-warn |
| `/budget-auditor` | `context/analysis/budget-audit.md` | ≤ 7 days | Bud | soft-warn |
| `/competitive-analyst` | `context/analysis/competitive-audit.md` | ≤ 14 days | Comp | informational |
| `/lp-auditor` | `context/analysis/lp-audit.md` | ≤ 14 days | Conv | soft-warn |
| `/offer-auditor` | `context/analysis/offer-audit.md` | ≤ 30 days | Conv | soft-warn |
| `/tracking-specialist` | `context/analysis/tracking-audit.md` | ≤ 30 days | **M** | **HARD-BLOCK** if fail/critical |
| `/strategy-specialist` | `context/analysis/strategy-audit.md` | ≤ 30 days | **B** | **HARD-BLOCK** if unit economics missing |
| `/account-auditor` | `context/analysis/account-audit.md` | ≤ 30 days | Struct | informational |

**Hard-block rule (universal).** If `/tracking-specialist` is fresh and reports failing/critical findings, OR `/strategy-specialist` is fresh and unit economics are missing/placeholder — refuse all mutations. Print the failing finding(s) and the handoff command. This generalizes the existing M/B cascade refusal in `bidding-safety.md → Gate 1`.

**Soft-warn rule.** A fresh peer at Eff/Conv/Bud layers that flags issues on a campaign in the operations plan → surface in the dry-run "Cross-skill context" section, but do not block.

**No fresh peer report.** Never auto-trigger a peer skill. Note "no fresh {peer}" in the dry-run context section so the operator knows the picture is incomplete.

**Freshness rule.** The report header date inside the markdown is canonical. File mtime is a sanity check — if mtime is older than the header date by >3 days, treat the report as suspicious and surface the contradiction in the dry-run output. Never auto-defer to one or auto-override.

---

## Mutation Sensitivity Matrix

Read `context/account-changelog.md` (must be ≤1h old per Phase 0.2). For every campaign in the operations plan, scan changelog entries within the windows below. Verdicts:

- **hard-block** — refuse mutation; require operator to remove that campaign from the plan or pass an explicit override.
- **hard-warn** — list in dry-run "Cross-skill context" with a `WARN:` prefix; require operator to type "confirm" before proceeding.
- **soft-warn** — list in dry-run "Cross-skill context" as informational.

| Peer skill / source | Mutation type | Window | Verdict | Rationale |
|---|---|---|---|---|
| `/budget-optimizer` | budget raise / cut | ≤ 7d | soft-warn | Budget change still propagating; bid mutation now compounds learning noise |
| `/bidding-optimizer` (self) | strategy migration | ≤ 14d | hard-warn | Campaign still inside Gate 2 learning window |
| `/bidding-optimizer` (self) | target adjustment | ≤ 14d | hard-warn | Don't stack a second target move; let the first settle |
| `/tracking-specialist` | conversion goal change | ≤ 30d | hard-warn | Target baseline shifted — historical CPA/ROAS no longer comparable |
| `/account-auditor`, `/account-changelog` | structure change (rebuild, merge, split) | ≤ 30d | hard-warn | Data discontinuity — fresh-strategy decisions can't lean on pre-rebuild data |
| `/geo-schedule-optimizer` | geo / device / schedule modifier | ≤ 7d | soft-warn | Targeting moved; bid math under new traffic mix |
| `/placement-optimizer` | placement exclusion (Display/PMax) | ≤ 7d | soft-warn | Traffic mix moved |
| any peer | manual UI change of bidding fields | ≤ 14d | hard-warn | Treat operator UI edits as equivalent to a self mutation |

Hard-warn confirmations are captured in the mutation history alongside the existing override flags (`--force-learning`, `--aggressive`, `--confirm-portfolio`). The "confirm" prompt is plaintext, single-line, and must reference the specific campaign + window.

**Self-mutation lookup.** Self target/strategy windows already encoded in `meta.learning_gate.days_since_target` / `days_since_strategy` (Gate 2). Phase 0.5 reads the *same* changelog entries and additionally cross-references peer-skill mutations the existing learning gate doesn't see.

**Override.** Hard-warns can be confirmed inline. There is no flag to silence them ahead of time — every session re-prompts on the relevant campaigns.

---

## Output Contract for Phase 0.5

Phase 0.5 produces an in-memory object consumed by Phase 1 (operations generation) and Phase 2 (dry-run rendering):

```json
{
  "hard_blocks": [
    { "peer": "/tracking-specialist", "report": "context/analysis/tracking-audit.md", "date": "...", "finding": "..." }
  ],
  "hard_warns": [
    { "campaign_id": "...", "campaign": "...", "peer": "/budget-optimizer", "mutation": "budget raise +18%", "date": "...", "days_ago": 4, "window": 7 }
  ],
  "soft_warns": [
    { "campaign_id": "...", "campaign": "...", "peer": "/quality-score-auditor", "score": 62, "finding": "..." }
  ],
  "informational": [ ... ],
  "freshness_notes": [ "no fresh /lp-auditor", "/tracking-specialist mtime 5d older than header — suspicious" ]
}
```

If `hard_blocks` is non-empty → Phase 1 does not run.
If `hard_warns` is non-empty → Phase 2 must collect explicit "confirm" before proceeding to Phase 3.
`soft_warns` and `informational` are surfaced in the dry-run "Cross-skill context" block above the mutation table.
