---
name: bidding-optimizer
description: >
  Apply audit-driven bid strategy and target mutations via the Google Ads API with dry-run approval, learning-window safety gates, and step caps.
  Triggered by /bidding-optimizer.
disable-model-invocation: true
argument-hint: "[setup|adjust-targets|scale|fix-shared-portfolio|remove-adjustments|cpc-cap|data-exclusion|schedule|modifiers|value-bidding|monitor]"
allowed-tools: Bash(node .claude/skills/bidding-optimizer/scripts/mutate.js *) Bash(node .claude/skills/bidding-auditor/scripts/pull-all.js *) Bash(node .claude/skills/gads-context/scripts/query.js *) Bash(node .claude/skills/account-changelog/scripts/*) Read Write
---

# Bidding Optimizer

Applies bid-strategy mutations based on `bidding-auditor` findings. **NEVER applies changes directly** — always generates `operations.json` → dry-run (`validate_only=true`) → user approval → live apply.

User-invoke only (`disable-model-invocation: true`) because this mutates a live Google Ads account.

**Actions covered:**
- BID-E01 + BID-E02: `setup` (interactive or programmatic for launchers)
- BID-E09: `adjust-targets` (incremental tCPA/tROAS, 20% step cap, learning gate)
- BID-E11: `scale` (target side; pairs with `/budget-optimizer raise`)
- BID-D17 fix: `fix-shared-portfolio`
- BID-E07: `remove-adjustments`
- BID-E08: `cpc-cap`
- BID-E14: `data-exclusion`
- BID-E13: `schedule` (mCPC only)
- BID-E12: `modifiers` (mCPC only)
- BID-E04 / BID-E03: `value-bidding`
- BID-E10: `monitor` (no mutations)

---

## Command Routing

```
/bidding-optimizer                          → menu of available actions from latest findings.json
/bidding-optimizer setup                    → BID-E01 + BID-E02 (interactive); --output=json for launchers
/bidding-optimizer adjust-targets           → BID-E09
/bidding-optimizer scale                    → BID-E11 (target side; coordinates with /budget-optimizer)
/bidding-optimizer fix-shared-portfolio     → resolve BID-D17 conflict
/bidding-optimizer remove-adjustments       → BID-E07
/bidding-optimizer cpc-cap                  → BID-E08
/bidding-optimizer data-exclusion           → BID-E14
/bidding-optimizer schedule                 → BID-E13
/bidding-optimizer modifiers                → BID-E12
/bidding-optimizer value-bidding            → BID-E04 + BID-E03
/bidding-optimizer monitor                  → BID-E10 (no mutations)
```

Override flags accepted on any subcommand:
- `--force-learning --override-reason="..."` — override Gate 2 (learning window)
- `--aggressive` — raise step cap from 20% to 30% on target adjustments
- `--confirm-portfolio` — required for any operation flagged `is_portfolio: true`

---

## MANDATORY SAFETY RULE

**NEVER apply changes directly via inline API calls.** The process is ALWAYS:

1. Read fresh data (≤1h account-changelog, ≤24h gads-context, fresh campaign bid-strategy)
2. Generate `operations.json` with full meta (cascade clearances, learning gate, step cap)
3. Run `mutate.js --mode=dry-run`
4. Present dry-run table to user
5. Ask for explicit "yes"
6. Only on "yes": run `mutate.js --mode=live`

No exceptions.

---

## Phase 0: Pre-flight

### Phase 0.1: Audit freshness

1. Read `context/analysis/bidding-audit.md`. If absent → `/bidding-auditor` first.
2. Check the report header date.
3. >24h old → "Audit is from {date}. For accurate optimization, run `/bidding-auditor` first. Proceed with stale data, or refresh?"

### Phase 0.2: Mandatory fresh changelog

The optimizer needs a `context/account-changelog.md` that is **≤1 hour old**. Auto-pull if stale:

```bash
node .claude/skills/account-changelog/scripts/<refresh-script>.js  # or invoke /account-changelog skill
```

After refresh, re-read the file mtime — abort if still stale (the user will see the error and decide).

### Phase 0.3: Fresh per-campaign state

Smart bidding targets move daily. Pull fresh bid-strategy state immediately before generating operations:

```bash
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customerId} \
  --login-customer-id={loginCustomerId} \
  --query-file=.claude/skills/bidding-optimizer/reference/gaql/campaign-bid-strategy.gaql \
  --days=30 --allow-empty \
  --output=context/google-ads/data/campaign-bid-strategy.csv
```

Never use cached campaign target values for the operation generation — only the freshly-pulled CSV.

### Phase 0.4: Load context

1. `config/ads-context.config.json → biddingAudit` for thresholds and `customerId/loginCustomerId`.
2. `context/analysis/bidding/findings-*.json` (per engine) and `opportunities-*.json` for the actions the user has already approved in this session.
3. `context/account-changelog.md` (parsed via `lib.js → parseAccountChangelog`).
4. `context/google-ads/data/campaign-bid-strategy.csv` (fresh from 0.3).
5. `context/google-ads/data/bidding-strategies.csv` for portfolio resolution.

---

## Phase 0.5: Peer Pre-flight

Cross-skill defensive lookup. Runs **before any operation generation**. Driven by `reference/handoff-matrix.md` — that file is the source of truth for fresh windows and mutation-sensitivity verdicts.

This phase generalizes the existing M/B cascade refusal (`bidding-safety.md → Gate 1`) into an explicit, peer-aware lookup. Gate 1 still re-validates per-operation in `mutate.js`; Phase 0.5 catches the same condition earlier with peer evidence quoted inline.

### Phase 0.5.1: Peer audit freshness sweep

Walk the **Peer Audit Freshness Table** in `reference/handoff-matrix.md` (10 peers; `/bidding-auditor` is excluded as the upstream auditor for this optimizer — `/lp-auditor` takes its slot).

For each row:
1. Read the report file if it exists.
2. Parse the **header date** — that is canonical. Compare to the fresh window.
3. Sanity-check `mtime` vs header date — if mtime is >3 days older than the header, log a `freshness_notes` entry; never auto-defer or auto-override.
4. If fresh and the report flags issues on any campaign in the candidate operations set → classify per the matrix verdict (hard-block / soft-warn / informational).

**Hard-block conditions (universal — refuse the entire session):**
- `/tracking-specialist` audit fresh AND any module fail/critical → hard refuse with the `/tracking-specialist` handoff. Quote the failing finding.
- `/strategy-specialist` audit fresh AND unit economics missing/placeholder (break-even undefined or primary KPI undefined) → hard refuse with the `/strategy-audit --execute unit-economics` handoff. Quote the missing field.

These are the M and B layers from the original cascade design; Phase 0.5 surfaces them with a quoted peer finding instead of just `meta.cascade_clear: blocking`.

### Phase 0.5.2: Account changelog peer-mutation scan

Read `context/account-changelog.md` (already loaded in 0.4, must be ≤1h old per 0.2). For every campaign in the candidate operations set, scan changelog entries within the windows in the **Mutation Sensitivity Matrix**.

For each match:
- **hard-warn** → record on the operation; Phase 2 dry-run must collect a typed "confirm" against the specific campaign + window before Phase 3 can run. Surface in the dry-run "Cross-skill context" section with a `WARN:` prefix.
- **soft-warn** → record and surface as informational only.

Self-mutation hard-warns (target/strategy by `/bidding-optimizer` within 14d) overlap with Gate 2 (learning window). Phase 0.5 still records them so the dry-run output names the actual recent mutation — the operator should rarely override both Gate 2 + the hard-warn.

### Phase 0.5.3: Build the peer-context object

Produce the object documented in `reference/handoff-matrix.md → Output Contract for Phase 0.5`:

```
{ hard_blocks, hard_warns, soft_warns, informational, freshness_notes }
```

Routing:
- `hard_blocks` non-empty → **STOP**. Print the blocks + handoff commands. Do not run Phase 1.
- `hard_warns` non-empty → continue, but Phase 2 must elicit explicit "confirm" per warn before Phase 3.
- `soft_warns` / `informational` / `freshness_notes` → surface in Phase 2 dry-run header; never block.

### Freshness rule (canonical)

The peer report's **header date is canonical**. File `mtime` is a sanity check only — warn (don't block) when mtime is >3 days older than the header. Surface every contradiction (stale-but-fresh-mtime, fresh-but-stale-mtime, peer-says-X-but-bidding-audit-says-Y) in the dry-run "Cross-skill context" output. Never auto-defer to one source or auto-override the operator.

---

## Phase 1: Generate Operations

Read:
- `reference/execute-rules.md` — per-subcommand operation shape
- `reference/api-constraints.md` — mutable fields + ordering
- `reference/bidding-safety.md` — gate definitions
- `reference/handoff-matrix.md` — peer audit freshness + mutation sensitivity (consumed by Phase 0.5; structure here so the operation rationale can quote the peer findings)
- `reference/launcher-interface.md` — `setup --output=json` contract

For each operation, populate the `meta` block fully:

```json
{
  "action_id": "BID-E09",
  "target": "<campaign or portfolio name>",
  "campaign_id": "...",
  "is_portfolio": false,
  "strategy": "TARGET_CPA",
  "field": "target_cpa.target_cpa_micros",
  "old_value": 60000000,
  "new_value": 54000000,
  "mutation_type": "target",
  "step_cap": { "from": 60, "to": 54, "pct": -10 },
  "cascade_clear": {
    "measurement": "pass",
    "business": "pass",
    "efficiency": "pass",
    "conversion": "pass"
  },
  "learning_gate": {
    "last_strategy_change": "2026-03-01",
    "last_target_change": "2026-04-10",
    "days_since_strategy": 61,
    "days_since_target": 21
  },
  "override_flags": [],
  "rationale": "BID-D08 deviation 18% above tCPA over 14d; cascade clears all layers; step cap -10% well within 20%."
}
```

Write to: `created/bidding-ops/operations-{YYYY-MM-DD}-{subcommand}.json`.

Tell the user: "Generated {N} operations: {summary by mutation_type}."

---

## Phase 2: Dry-run

```bash
node .claude/skills/bidding-optimizer/scripts/mutate.js \
  --customer-id={customerId} \
  --login-customer-id={loginCustomerId} \
  --operations-file=created/bidding-ops/operations-{date}-{subcommand}.json \
  --mode=dry-run \
  [--force-learning --override-reason="..."] \
  [--aggressive] \
  [--confirm-portfolio]
```

The script:
1. Re-validates all gates (cascade, learning, stacking, step cap, portfolio).
2. Calls `customer.mutateResources(..., { validate_only: true })`.
3. Prints a per-subcommand table grouped by mutation type (target adjustments / portfolio updates / data exclusions / modifiers).
4. Prints gate clearances at the bottom.

### Dry-run output structure

Render in this order (top → bottom):

1. **Cross-skill context** (one paragraph; pulled from the Phase 0.5 peer-context object). Format:
   - `WARN: {peer} {mutation_type} on {campaign} {N}d ago (matrix window {W}d) — type "confirm {campaign}" to acknowledge.` for each `hard_warn`.
   - `Note: {peer} audit {date} score {N} — {one-line top finding} on {campaign}.` for each `soft_warn`. Quote 1–2 lines verbatim from the peer report when useful.
   - `Freshness: {note}` for each `freshness_notes` entry.
   - If the peer-context object is empty: `Cross-skill context: clean — no fresh peer findings or recent peer mutations on the campaigns in this plan.`
2. **Mutation table** — the existing per-subcommand table grouped by mutation type.
3. **Gate clearances** — the existing summary at the bottom.

Present this output to the user.

> "These changes have NOT been applied. Ready to apply? (yes / no)"

For every `hard_warn` carried in from Phase 0.5, also require a typed `confirm {campaign}` before "yes" is accepted. Record each confirmation in the operation's `meta.peer_confirmations[]` so it survives into the mutation history written by Phase 3.

If "no": ask what to remove, regenerate operations.json without those entries, re-run dry-run (Phase 0.5 re-evaluates against the reduced campaign set — peer-context shrinks accordingly).

---

## Phase 3: Live apply

Only on explicit "yes":

```bash
node .claude/skills/bidding-optimizer/scripts/mutate.js \
  --customer-id={customerId} \
  --login-customer-id={loginCustomerId} \
  --operations-file=created/bidding-ops/operations-{date}-{subcommand}.json \
  --mode=live \
  [...override flags from dry-run]
```

The script:
1. Sorts operations: data-exclusions → portfolios → campaigns → criteria.
2. Applies in batches of 50, surfacing errors per-batch.
3. Writes `tmp/bidding-optimizer/mutations-{ISO}.json` with the full operation list, results, and override flags.
4. Appends `context/analysis/bidding-changelog.md`.

---

## Phase 4: Follow-up reminder (§6.C)

After every successful target or strategy mutation:

1. **Always** write `tmp/bidding-optimizer/follow-ups-{campaign}-{date}.md` with the 14-day check task as paste-ready text.
2. Check Google Calendar MCP auth state.
3. If connected → offer: "Want me to add this as a calendar event for {today + 14d}? (y / skip)"
4. If not connected → show the reminder text inline + suggest connecting the MCP.

`/schedule` is **NOT** used (it requires the user's machine to be on). Calendar events fire passively.

---

## Phase 5: Summary

Present:

> "Applied {N} mutations: {V} target adjustments, {E} data exclusions, {O} other.
>
> History: tmp/bidding-optimizer/mutations-{ISO}.json
> Changelog: context/analysis/bidding-changelog.md
> Follow-up: {path to follow-ups markdown} ({date+14d})"

If the audit is now stale (changes were made), suggest: "Re-run `/bidding-auditor` in 7–14 days to verify learning settled and measure impact."

---

## Edge Cases

| Scenario | Handling |
|---|---|
| No audit report exists | Run `/bidding-auditor` first. |
| `account-changelog` missing | Hard refuse — auto-pull via `/account-changelog`, then retry. |
| Campaign not in fresh bid-strategy CSV | Op rejected with "campaign not found in current state". |
| Strategy/target change <14 days | Gate 2 refuses unless `--force-learning --override-reason` provided. |
| Two operations on same campaign | Gate 3 refuses; stage second op for next session. |
| Step >20% (>30% with --aggressive) | Gate 4 refuses; auditor must clamp before queuing. |
| Portfolio op without `--confirm-portfolio` | Gate 5 refuses. |
| Cascade `measurement: blocking` OR Phase 0.5 `/tracking-specialist` fail/critical | Hard refuse with `/tracking-specialist` handoff (Phase 0.5 quotes the failing finding inline). |
| Cascade `business: blocking` OR Phase 0.5 `/strategy-specialist` unit-economics missing | Hard refuse with `/strategy-audit --execute unit-economics` handoff (Phase 0.5 names the missing field). |
| Phase 0.5 hard-warn (peer mutation in sensitivity window) | Surface in dry-run; require typed `confirm {campaign}` per warn before live apply. Confirmation logged to `meta.peer_confirmations[]` and mutation history. |
| Phase 0.5 freshness contradiction (mtime vs header date) | Surface in `freshness_notes`; do not auto-defer. Operator decides. |
| No fresh peer report at any layer | Note "no fresh {peer}" in dry-run context. Never auto-trigger a peer skill. |
| Calendar MCP not connected | Skip calendar offer; markdown reminder still written. |
| API error during live | mutate.js logs per-batch error, continues remaining batches; partial-apply state captured in mutation history. |
| `setup --output=json` for launcher | No interactive prompts; missing input → JSON `{ "error": ... }` exit 1. |
| `value-bidding` with `valueRulesAllowed: false` | Refuse + reference config. |
| Multiple audits run same day | Use the latest findings file; older sessions' approvals don't carry over (each session re-asks). |
