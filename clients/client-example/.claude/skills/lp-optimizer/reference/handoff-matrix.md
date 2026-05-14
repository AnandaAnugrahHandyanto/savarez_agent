# LP Optimizer — Handoff Matrix

LP-optimizer is a **guidance** skill (it produces fix-it recommendations rather than mutating the account directly). It still uses the cross-skill peer-lookup pattern in two modes:

- **Pre-flight gate** (Phase 0.5 of `SKILL.md`) — hard-block when upstream M/B layers are dirty, soft-warn when peer mutations have recently shifted the campaigns this LP serves.
- **Context enrichment** — the recommendation report quotes fresh peer findings near the top so the user understands why the LP fixes are being proposed in concert with other work.

This file defines: (1) the 10-peer freshness table, (2) the mutation-sensitivity matrix, (3) the freshness rule, (4) the cross-skill context block.

---

## 1. Peer report freshness table

`/lp-auditor` is the **upstream** auditor for this skill — it is consumed in every run and is **not** included in the peer table (it is a hard prerequisite, not a peer signal).

`/quality-score-auditor` is the **parallel signal** for LP Experience and is the primary integration target — its handoff queue (already wired in Phase 0.0) tells lp-optimizer which URLs to prioritise.

| Peer skill | Report file | Fresh window | Pre-flight role |
|---|---|---|---|
| `/quality-score-auditor` | `context/analysis/quality-score-audit.md` | ≤ 7 days | Parallel — primary integration |
| `/search-term-auditor` | `context/analysis/search-term-audit.md` | ≤ 7 days | Eff — soft-warn |
| `/keyword-auditor` | `context/analysis/keyword-audit.md` | ≤ 7 days | Eff — soft-warn |
| `/budget-auditor` | `context/analysis/budget-audit.md` | ≤ 7 days | Traffic — soft-warn |
| `/bidding-auditor` | `context/analysis/bidding-audit.md` | ≤ 7 days | Traffic — soft-warn |
| `/competitive-analyst` | `context/analysis/competitive-audit.md` | ≤ 14 days | Comp — informational |
| `/offer-auditor` | `context/analysis/offer-audit.md` | ≤ 30 days | Conv — soft-warn (offer ≠ LP) |
| `/tracking-specialist` | `context/analysis/tracking-audit.md` | ≤ 30 days | **M — HARD-BLOCK if dirty** |
| `/strategy-specialist` | `context/analysis/strategy-audit.md` | ≤ 30 days | **B — HARD-BLOCK if dirty** |
| `/account-auditor` | `context/analysis/account-audit.md` | ≤ 30 days | Struct — informational |

> Why `/tracking-specialist` is load-bearing for **lp-optimizer specifically:** if conversion tracking is broken, you cannot measure whether your LP changes worked. There is no point recommending CRO fixes to a CVR you cannot measure. This is the single most important hard-block in this skill.

> Why `/strategy-specialist` is load-bearing: without `primaryKPI` + `breakEven` resolved, the optimizer cannot calibrate "expected impact" estimates and cannot decide whether to push for ecommerce-style trust signals vs lead-gen-style form simplification.

---

## 2. Pre-flight gate logic (Phase 0.5)

Walk the table above. For each peer:

1. Stat the report file's mtime (or use the date in the report header — see freshness rule below).
2. Categorise:
   - **Missing** OR **stale** → no peer signal available; do not block on this peer (except the Universal Hard-Block layer below).
   - **Fresh + clean** → silent.
   - **Fresh + dirty** → apply the role from the table.

### Universal hard-block

Refuse to proceed to the change-recommendation phase when **either**:

- `/tracking-specialist` audit is fresh AND has any FAIL finding affecting the campaigns the LP serves, OR the audit is **missing** for an account where lp-optimizer has never run.
- `/strategy-specialist` audit is fresh AND `primaryKPI` or `breakEven` is unresolved/placeholder, OR the audit is **missing** for an account where lp-optimizer has never run.

When hard-blocked, surface to the user:

> **Pre-flight hard-block — {layer}.**
> {one-line explanation, e.g., "Conversion tracking is broken on the campaigns this LP serves. LP changes cannot be measured until tracking is fixed."}
>
> Run `{recommended_handoff}` first, then re-run `/lp-optimize`.
>
> To override (rare — only when you accept that recommendations will not be measurable), append `--override-measurement --override-reason="..."` (or `--override-business`).

### Soft-warn (non-blocking)

Fresh + dirty findings on Eff / Conv / Traffic peers do not block. Surface them in the cross-skill context block (section 4) so the recommendation report carries the upstream signal.

---

## 3. Mutation Sensitivity Matrix

LP-optimizer is **less sensitive** to recent account-side mutations than bidding/budget optimizers, because LP changes are mostly independent of the account graph. But three classes of recent peer mutation should produce a **soft-warn**: don't shift the LP yet, the test signal isn't stable.

Read `context/account-changelog.md` (only if it exists and is ≤ 7 days old; never auto-pull — lp-optimizer is a guidance skill, not a mutator). For each entry, check whether the mutation overlaps the campaigns the LP serves (resolved from `lp-audit.md` URL→campaign mapping or from `/quality-score-auditor` handoff queue).

| Recent peer mutation | Lookback window | Reason | Action |
|---|---|---|---|
| Ad copy changes (RSA edits, new RSAs) on overlapping ad groups | ≤ 7 days | Mid-test — shifting the LP now contaminates ad-copy A/B signal | **soft-warn:** "RSA was edited {N}d ago. Wait for ad-copy signal to stabilise (≥ 14 days post-change) before applying LP changes, OR proceed and accept that ad-copy + LP impact will be entangled." |
| Active QS optimization on overlapping ad groups (Expected CTR / Ad Relevance fixes) | ≤ 7 days | Quality Score is still moving — LP fixes will land on a moving baseline | **soft-warn:** "QS optimization is in-flight ({N}d ago). Either wait for QS to re-baseline, or sequence LP-Experience fixes immediately after (intentional stack)." |
| Campaign restructure (new campaigns, structural moves, match-type changes, large neg-kw drops) on overlapping campaigns | ≤ 14 days | Traffic mix is shifting — LP audience changes underneath you | **soft-warn:** "Campaign was restructured {N}d ago. The traffic profile hitting this LP is changing. Re-run `/lp-audit` post-restructure to confirm findings still apply, OR proceed with the caveat that current findings reflect pre-restructure traffic." |

### Mutations that do **not** trigger a warn

- Budget raises/reductions (LP is downstream of budget — more or less traffic doesn't change LP findings)
- Bid strategy changes (changes CPC, not LP behaviour)
- Geo/schedule/device targeting changes (changes who sees the LP, but findings about the LP itself remain valid)
- Placement exclusions
- Search-term negatives

These are listed for completeness so future iterations don't accidentally inflate the warn surface.

### Soft-warn rendering

When any soft-warn fires, surface one line per warn at the top of Phase 2's report (in the Cross-skill Context block, section 4) and once interactively before generating the report:

> ⚠ **Recent peer mutation detected.** {one-line warn from the table above}.
>
> Proceed with LP recommendations? (yes / abort)

A user "yes" carries through silently — the warn is preserved in the report so the implementer sees it.

---

## 4. Cross-skill Context block (report enrichment)

Every recommendation report (`context/analysis/lp-optimize-{action}.md`) gets a **Cross-skill Context** section inserted immediately after the report header (above Issue Summary).

Skip the section entirely when no fresh peer findings overlap the target URL/campaigns.

```markdown
## Cross-skill Context

The following peer findings are fresh and overlap the campaigns this LP serves. The LP fixes recommended below should be evaluated alongside (or sequenced with) these signals.

| Peer | Report date | Finding | How it interacts with this LP work |
|---|---|---|---|
| /quality-score-auditor | {date} | LPE Below-Avg on {N} keywords / {imps} impressions | These LP fixes (P1: {primary fix}) directly target LPE — re-running /quality-score-auditor 14 days after implementation should show LPE recovery |
| /search-term-auditor | {date} | {key finding} | {how the LP work changes / is changed by this finding} |
| /offer-auditor | {date} | {key finding} | {…} |

**Recent peer mutations (soft-warn):**
- ⚠ {one-line warn from mutation-sensitivity matrix, if any}
```

When `/quality-score-auditor` flagged LPE on the URL being optimised, **always** include a row that explicitly chains: "applying these LP fixes should resolve QS Auditor's LPE flag — re-run `/quality-score-auditor` 14 days after implementation to verify."

---

## 5. Freshness rule

For all peer reports referenced above:

- **Header date is canonical.** Read the report's first-line `**Date:** YYYY-MM-DD` (or equivalent) and treat that as the report's date for the freshness window calculation. Do not use file mtime as the canonical date — git checkouts, copies, and editor saves can shift mtime in ways that do not reflect when the data was generated.
- **Use mtime only as a tiebreaker** when the header date is missing.
- **Surface contradictions.** If header date is older than mtime by >7 days (suggests a manually edited stale report) or newer than mtime (impossible — surfaces clock skew or a tampered file), surface the contradiction to the user and ask which to trust. Do not silently pick one.
- **Never auto-defer.** Do not silently fall back to "treating stale as fresh" or "skipping the gate because the report is missing." If a peer is missing/stale and the gate requires it, surface it. If the gate is informational, proceed but log "peer not consulted — {reason}".
