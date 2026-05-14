---
name: budget-optimizer
description: >
  Apply audit-driven campaign budget mutations (raise / reduce / reallocate /
  fix-shared / pacing-adjust) via the Google Ads API with dry-run approval,
  cascade gates, and a 1.3x step cap.
  Triggered by /budget-optimizer.
disable-model-invocation: true
argument-hint: "[raise|reduce|reallocate|fix-shared|pacing-adjust]"
allowed-tools: Bash(node .claude/skills/budget-optimizer/scripts/mutate.js *) Bash(node .claude/skills/budget-auditor/scripts/pull-all.js *) Bash(node .claude/skills/gads-context/scripts/query.js *) Bash(node .claude/skills/account-changelog/scripts/*) Read Write
---

# Budget Optimizer

Applies campaign budget mutations based on `budget-auditor` findings. **NEVER applies changes directly** — always generates `operations.json` → dry-run (`validate_only=true`) → user approval → live apply.

User-invoke only (`disable-model-invocation: true`) because this mutates a live Google Ads account.

**Actions covered:**
- BUD-E01 / BUD-E07: `raise` (gated)
- BUD-E04 reduce side: `reduce`
- BUD-E02 / BUD-E04 portfolio rebalance: `reallocate`
- BUD-E05: `fix-shared`
- BUD-E06: `pacing-adjust`
- BUD-E03 (scale): handoff chain only — bid leg routes to `/bidding-specialist`
- BUD-E08 (alerts): **deferred to v1.1**

---

## Command Routing

```
/budget-optimizer                              → menu of available actions from latest findings.json
/budget-optimizer raise                        → BUD-E01, BUD-E07 (gated)
/budget-optimizer reduce                       → BUD-E04 reduce side
/budget-optimizer reallocate                   → BUD-E02, BUD-E04 portfolio rebalance
/budget-optimizer fix-shared                   → BUD-E05
/budget-optimizer pacing-adjust                → BUD-E06
```

`raise` and `reduce` are split because the gate asymmetry differs — raise has the extra Eff/Conv soft-block confirmation; reduce does not.

Override flags accepted on any subcommand:
- `--aggressive` — raise step cap from 1.3× to 1.5×.
- `--override-measurement --override-reason="..."` — override M-layer hard block.
- `--override-business --override-reason="..."` — override B-layer hard block.

Soft-block overrides on Eff / Conv / Bid layers are accepted via the SKILL prompt asking the user to type the literal word **"confirm"** + a reason, NOT a CLI flag.

---

## MANDATORY SAFETY RULE

**NEVER apply changes directly via inline API calls.** The process is ALWAYS:

1. Read fresh data (≤1h account-changelog, ≤24h gads-context, fresh `campaign-budgets.csv`)
2. Generate `operations.json` with full `meta` block
3. Run `mutate.js --mode=dry-run`
4. Present the dry-run table to the user
5. Ask for explicit "yes"
6. Only on "yes": run `mutate.js --mode=live`

No exceptions.

---

## Phase 0: Pre-flight

### Phase 0.1 — Audit freshness

1. Read `context/analysis/budget-audit.md`. Absent → "Run /budget-auditor first."
2. Check the report header date. If >24h → "Audit is from {date}. For accurate optimization, run /budget-auditor first. Proceed with stale data, or refresh?"

### Phase 0.2 — Mandatory fresh changelog

The optimizer needs `context/account-changelog.md` ≤ **1 hour** old. Auto-pull if stale:

```bash
node .claude/skills/account-changelog/scripts/<refresh-script>.js
```

After refresh, re-read mtime — abort if still stale. Surfaces error to the user.

### Phase 0.3 — Fresh campaign_budget state

Daily budget values change every time anyone edits the account. Pull fresh state immediately before generating ops:

```bash
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customerId} \
  --login-customer-id={loginCustomerId} \
  --query-file=.claude/skills/budget-optimizer/reference/gaql/campaign-budget-state.gaql \
  --no-date-range --allow-empty \
  --output=context/google-ads/data/campaign-budget-state-fresh.csv
```

Use this file for `resource_name` and `from_micros` values when generating ops — never the cached `campaign-budgets.csv` from the auditor's pull.

### Phase 0.4 — Load context

1. `config/ads-context.config.json → budgetAudit` for thresholds; `customerId` + `loginCustomerId` from `googleAds`; top-level `accountCurrency`.
2. `context/analysis/budget/findings-health.json` + `findings-pacing.json` for risk findings.
3. `context/analysis/budget/opportunities-health.json` + `opportunities-pacing.json` for the actions the user has been pre-approved this session.
4. `context/account-changelog.md` (parsed via `account-changelog` lib helpers).
5. `context/google-ads/data/campaign-budget-state-fresh.csv` (Phase 0.3).

---

## Phase 1: Generate Operations

Read:
- `reference/execute-rules.md` — per-subcommand operation shape.
- `reference/api-constraints.md` — mutable fields + ordering.
- `reference/budget-safety.md` — gate definitions.
- `reference/handoff-matrix.md` — peer-lookup freshness table + Mutation Sensitivity Matrix (consumed in Phase 1.5).

For each operation, populate the `meta` block fully (template in `execute-rules.md`).

### Cascade rendering

For each candidate campaign, decide the cascade verdict by overlaying:

| Layer | Pass condition | Soft-block / blocking source |
|---|---|---|
| measurement | No `/tracking-specialist` finding overlaps the campaign | Tracking findings (when fresh) → `blocking` |
| business | `primaryKPI` + `breakEven` resolved | Either missing → `blocking` |
| bidding | BUD-D05 / D08 / D19 don't fire on this campaign | Any fires → `recommended` (raise softblocks) |
| efficiency | No fresh waste finding from `/search-term-auditor`, `/keyword-auditor`, `/quality-score-auditor` overlapping | Fresh waste finding → `recommended` (raise softblocks; reduce ignores) |
| conversion | No fresh CVR finding from `/lp-auditor`, `/offer-auditor` | Fresh finding → `recommended` (raise softblocks; reduce ignores) |

Hard blocks short-circuit the operation generation: SKILL refuses to write the op unless the corresponding `--override-{measurement|business} --override-reason=...` is on the CLI invocation.

Soft blocks: SKILL writes the op with `confirmed: false` and a `pending_override` flag. Phase 2 prompts the user to type `confirm + reason` per offending campaign before running dry-run.

### Channel sanity

For Search/Shopping raise ops, hydrate `meta.tcpa` from `campaigns-budget-perf.csv` (target_cpa or maximize_conversions.target_cpa). For PMax raise ops, hydrate `meta.pmax_volume_floor` from `budgetAudit.pmaxVolumeFloor` (fallback default $50/day).

### Output file

```
created/budget-ops/operations-{YYYY-MM-DD}-{subcommand}.json
```

Tell the user: "Generated {N} operations: {breakdown by mutation_type}. Cascade summary: {N} clear, {M} soft-block (need 'confirm'), {K} hard-blocked."

---

## Phase 1.5: Peer Pre-flight (cross-skill lookup)

Before any soft-block prompt or dry-run, walk the **10-peer freshness table** in `reference/handoff-matrix.md` and the **Mutation Sensitivity Matrix** in the same file. This is additive to the cascade in Phase 1 — it catches risks that the auditor's cascade tags cannot see (peer mutations made after the audit ran, or peer audits not yet folded into the budget audit).

### Step 1.5.a — Peer audit lookup (10 reports)

For each peer in the freshness table:

1. Check the report file exists at `context/analysis/{peer}.md`.
2. Read the report's **header date** (canonical) — e.g., `Generated: 2026-04-28`. Also read the file mtime as a sanity check.
3. If header_date and mtime disagree by >24h: surface the contradiction. Do not auto-defer to either; tell the user "`/{peer}` audit header says {header_date} but file mtime is {mtime_date} — re-run to disambiguate." Treat the layer as **unknown** for blocking purposes.
4. Compare header date to today; classify as fresh / stale / missing per the per-peer fresh window.
5. If fresh, parse the report for **open findings** that name a campaign in the current op set (or any open M/B finding, which blocks regardless of overlap).

### Step 1.5.b — Apply peer-layer policy

- **M (Measurement) — `/tracking-specialist`** dirty (open finding, fresh) → **HARD-BLOCK** every op. Refuse the dry-run unless `--override-measurement --override-reason="..."` is on the CLI invocation. (This is the same hard-block as `budget-safety.md` Gate 1, surfaced earlier and via a peer-audit path rather than a cascade tag.)
- **B (Business) — `/strategy-specialist`** dirty (`primaryKPI` or `breakEven` missing/placeholder, fresh) → **HARD-BLOCK** every op. Same override flag pattern (`--override-business`).
- **Eff (Efficiency) — `/quality-score-auditor`, `/search-term-auditor`, `/keyword-auditor`** open finding overlapping a campaign in the op set → **SOFT-WARN on `raise` ops only**. Reduce / reallocate / fix-shared / pacing-adjust ignore Eff dirt. Soft-warn merges into Phase 2's `confirm + reason` flow on a per-op basis.
- **Bid (peer) — `/bidding-auditor`** open finding overlapping a campaign in the op set → **SOFT-WARN on `raise` ops only**. Bid/target faults compound a budget raise.
- **Conv (Conversion) — `/lp-auditor`, `/offer-auditor`** open finding overlapping a campaign in the op set → **SOFT-WARN on `raise` ops only**.
- **Comp / Struct — `/competitive-analyst`, `/account-auditor`** → **informational only**. Do not block; surface in Phase 3's "Cross-skill context" section.

If a peer report is missing entirely:
- M / B layers → treat as unknown → hard-block (cannot mutate without proof of clean measurement/business). User can still pass the M/B override flag.
- Eff / Conv / Bid layers → surface "no recent {peer} audit on file — proceeding without that signal" but do not block.

### Step 1.5.c — Account-changelog cross-check (Mutation Sensitivity Matrix)

Re-read `context/account-changelog.md` (already loaded in Phase 0.4). For each op in the set, check the changelog rows whose `change_resource_type` and target campaign overlap with the op's target campaign / `campaign_budget`. Apply per the **Mutation Sensitivity Matrix** in `reference/handoff-matrix.md`:

| Recent peer change | Window | Severity |
|---|---|---|
| Bid / target adjustment (tCPA, tROAS, max-CPC ceiling) on the same campaign | ≤ 2 days | **HARD-WARN** |
| Bid strategy migration (manual→tCPA, tCPA→Max Conv, etc.) on the same campaign | ≤ 14 days | **HARD-WARN** |
| Conversion goal / primary action change on the account or this campaign | ≤ 30 days | **HARD-WARN** |
| Budget change made by `/budget-optimizer` itself on the same `campaign_budget` | ≤ 7 days | **SOFT-WARN** |
| Structural change (new ad group, status flip, network/geo/schedule, rename) on the same campaign | ≤ 30 days | **HARD-WARN** |

**Canonical user-facing example** — handle this explicitly:

> Op: raise Branded Search budget from $100/d → $130/d.
> Changelog: `target_cpa` on Branded Search changed from $40 → $30 two days ago.
> SKILL output: "⚠ Recent change risk: `Branded Search` had a tCPA adjustment on 2026-04-30 (2d ago). Stacking a budget raise on top is risky — smart bidding learning takes 7–14d, so you'd be raising spend mid-learning. Type 'confirm + reason' to proceed, or skip this op."

**Severity behavior:**
- **HARD-WARN** → require user to type `confirm + reason` before the op proceeds to dry-run. Same prompt mechanic as Phase 2 cascade soft-blocks; the prompts merge into a single Phase 2 round.
- **SOFT-WARN** → print inline in cascade summary; no `confirm` required, but appears in Phase 3's cross-skill context.

### Step 1.5.d — Pre-flight summary

After the peer audit walk + changelog cross-check, print a one-block summary before Phase 2:

```
Peer pre-flight (10 audits, 1 changelog):
  ✅ M /tracking-specialist (2026-04-15, 17d ago) — clean
  ✅ B /strategy-specialist (2026-04-20, 12d ago) — primaryKPI=ROAS, breakEven=2.5
  ⚠ Eff /search-term-auditor (2026-04-29, 3d ago) — Branded Search: $420 waste (will soft-warn raise)
  ⚠ Changelog: Branded Search tCPA changed 2d ago — will hard-warn raise on Branded Search
  ✅ ... (remaining peers clean / informational)

Net: 1 hard-block (M cleared via override required: 0), 1 hard-warn (changelog), 1 soft-warn (Eff peer).
Proceeding to Phase 2 prompts.
```

If any HARD-BLOCK is unresolved, abort here with:

> "Pre-flight HARD-BLOCK: {layer} dirty — {one-line reason from peer report}. Resolve via `/{peer-skill}` or pass `--override-{measurement|business} --override-reason=\"...\"`. No mutations generated."

---

## Phase 2: Soft-block + hard-warn prompts

This phase merges two prompt sources into a single round per op:

1. **Cascade soft-blocks** from Phase 1 (Eff/Conv/Bid layers `recommended` against a `raise` op).
2. **Peer pre-flight signals** from Phase 1.5 — both peer-audit soft-warns AND changelog hard-warns from the Mutation Sensitivity Matrix.

For each op with `confirmed: false` AND any active soft-block / hard-warn, prompt the user separately:

> "Cascade for `${target}`: ${cascade summary with ⚠ on flagged layers}.
> ${reason — e.g., 'Raising the budget will multiply existing search-term waste of $420.'}
>
> ${If a Mutation Sensitivity Matrix hard-warn fired:}
> ⚠ Recent change risk: `${target}` had a ${change_type} change on ${date} (${N}d ago). Stacking a ${mutation_type} on top is risky — ${one-line rationale, e.g. 'smart bidding is mid-learning, raising spend now distorts the signal'}.
>
> Recommended: ${peer-skill handoff first} OR wait ${days remaining in window} for stabilization.
>
> Override and proceed with this ${mutation_type} anyway? Type 'confirm' (not 'y') with reason:"

If user types something starting with `confirm`, set `op.meta.confirmed = true` and `op.meta.override_reason = "<their text>"`. Persist the matched changelog rows into `op.meta.changelog_warns: [...]` so the dry-run table can render them. Otherwise drop the op from the file.

After all prompts, regenerate `operations.json` with only the kept ops.

---

## Phase 3: Dry-run

```bash
node .claude/skills/budget-optimizer/scripts/mutate.js \
  --customer-id={customerId} \
  --login-customer-id={loginCustomerId} \
  --operations-file=created/budget-ops/operations-{date}-{subcommand}.json \
  --mode=dry-run \
  [--aggressive] \
  [--override-measurement --override-reason="..."] \
  [--override-business --override-reason="..."]
```

The script:
1. Re-validates all gates (cascade, step cap, channel sanity).
2. Calls `customer.mutateResources(..., { validate_only: true })`.
3. Prints a per-mutation-type table grouped by raise / reduce / reallocate / fix-shared / pacing-adjust.
4. Prints **net monthly impact** (the `+$/mo` running sum) at the bottom.

### Cross-skill context (rendered above the dry-run table)

Before the per-mutation table, render a "Cross-skill context" block summarizing 1–2 fresh peer findings touching any campaign in the plan, plus any informational changelog entries (Comp / Struct layer items, plus SOFT-WARN budget self-stack reminders). Pull from the peer-pre-flight cache (Phase 1.5) and `op.meta.changelog_warns`.

Format:

```
Cross-skill context (peer audits read this session):
- /search-term-auditor (2026-04-29, 3d ago): "Branded Search has $420 of irrelevant
  search-term spend in 30d (top n-gram: 'free trial')." → soft-warned the raise on
  Branded Search; user confirmed override.
- /bidding-auditor (2026-04-30, 2d ago): "Performance Max — Lead Gen tCPA target
  $35 is 1.4x current 30d CPA $25; volume floor not met." → informational.
- Changelog: Branded Search tCPA changed 2d ago — hard-warned, user confirmed.
```

If no fresh peer findings overlap the plan, render: `Cross-skill context: clean (no overlapping peer findings).`

Present the cross-skill context block + the per-mutation table verbatim to the user.

> "These changes have NOT been applied. Ready to apply? (yes / no)"

If "no": ask which entries to remove, regenerate the operations file without those ops, re-run dry-run.

---

## Phase 4: Live apply

Only on explicit "yes":

```bash
node .claude/skills/budget-optimizer/scripts/mutate.js \
  --customer-id={customerId} \
  --login-customer-id={loginCustomerId} \
  --operations-file=created/budget-ops/operations-{date}-{subcommand}.json \
  --mode=live \
  [...override flags from dry-run]
```

The script:
1. Sorts operations: reduce → reallocate → fix-shared → pacing-adjust → raise.
2. Applies in batches of 50, surfacing errors per-batch.
3. Writes `tmp/budget-optimizer/mutations-{ISO}.json` with the full operation list, results, and override flags. **Mutation history is kept indefinitely** — small files, valuable for rollback inspection.
4. Appends `context/analysis/budget-changelog.md`.

---

## Phase 5: Follow-up reminder

After every successful raise (and after any reallocation that includes a raise leg):

1. Write `tmp/budget-optimizer/follow-ups-{campaign}-{date}.md` with a 14-day check task (paste-ready text):
   > "Check {campaign} on {today + 14d}: did profitable +$/mo materialize? Re-run `/budget-auditor limitation` to verify IS Lost (Budget) recovered."
2. Check Google Calendar MCP auth state. If connected → offer "Want me to add this as a calendar event for {today + 14d}? (y / skip)". If not → show the reminder text inline + suggest connecting the MCP.

`/schedule` is **NOT** used (it requires the user's machine to be on). Calendar events fire passively.

---

## Phase 6: Summary

> "Applied {N} mutations: {R} raises, {D} reduces, {Z} reallocations, {S} structural.
> Net monthly impact: {+$X / -$Y} ({accountCurrency}).
>
> History: tmp/budget-optimizer/mutations-{ISO}.json
> Changelog: context/analysis/budget-changelog.md
> Follow-up: {path or 'no follow-up needed'} ({date+14d})"

If the audit is now stale, suggest: "Re-run `/budget-auditor` in 7–14 days to verify allocation moves and capture new opportunities."

---

## Edge Cases

| Scenario | Handling |
|---|---|
| No audit report exists | Run `/budget-auditor` first. |
| `account-changelog` missing or >1h | Hard refuse — auto-pull, retry once, abort if still stale. |
| Campaign not in fresh budget-state CSV | Op rejected with "campaign not found in current state". |
| Same `campaign_budget` already mutated this session | Op rejected (Gate 7 stacking prevention). |
| Step >1.3× without --aggressive | Gate 2 refuses; offer to split into multiple sessions. |
| Step >1.5× even with --aggressive | Refuse; surface as "split into N×1.3× steps over N×14d". |
| Cascade `measurement: blocking` without override | Hard refuse with `/tracking-specialist` handoff. |
| Cascade `business: blocking` without override | Hard refuse with `/strategy-specialist` handoff. |
| Cascade soft block on raise without "confirm" | SKILL drops the op silently; tells user "{N} ops dropped due to declined override." |
| Phase 1.5 peer audit M-layer (`/tracking-specialist`) dirty | Hard refuse all ops without `--override-measurement --override-reason="..."`. Surface top tracking finding inline. |
| Phase 1.5 peer audit B-layer (`/strategy-specialist`) dirty / unit economics missing | Hard refuse all ops without `--override-business --override-reason="..."`. |
| Phase 1.5 changelog hard-warn (e.g., bid change ≤2d on same campaign) | Op held in Phase 2 prompt; user must type `confirm + reason`. Otherwise dropped. |
| Phase 1.5 changelog soft-warn (self-stack ≤7d) | Op proceeds; warning rendered in cross-skill context block; no confirm required. |
| Peer audit header date vs mtime contradiction | Surface contradiction; do not auto-defer; treat layer as unknown (M/B → hard-block, others → no signal). |
| Peer audit missing for M/B layer | Same as M/B dirty — hard-block; user must use `--override-{measurement\|business}`. |
| Peer audit missing for Eff/Conv/Bid layer | Render "no recent {peer} audit on file"; do not block. |
| Shared budget split required (BUD-E05) | v1 writes a markdown handoff under `created/budget-ops/handoff-...md` instead of mutating. |
| Calendar MCP not connected | Skip calendar offer; markdown reminder still written. |
| API error during live | mutate.js logs per-batch error, continues remaining batches; partial-apply state captured in mutation history. |
| Currency mismatch (config vs account) | mutate.js surfaces the account currency in the dry-run header; user reviews before approving. |
| Underspend redeploy with no winners | Pacing-adjust falls back to "do nothing"; SKILL surfaces the unspent dollars and recommends `/budget-optimizer raise` only after winners are identified. |
