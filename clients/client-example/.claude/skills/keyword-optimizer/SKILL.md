---
name: keyword-optimizer
description: Apply audit-driven keyword mutations via Google Ads API with dry-run approval. Triggered by keyword-optimizer.
disable-model-invocation: true
argument-hint: "[pause|cleanup|match-type|duplicates|cannibalization|tiers]"
allowed-tools: Bash(node .claude/skills/keyword-optimizer/scripts/mutate.js *) Bash(node .claude/skills/gads-context/scripts/query.js *) Read Write
---

# Keyword Optimizer

Applies keyword mutations based on keyword-auditor findings. **NEVER applies changes directly** — always generates operations.json → dry-run → user approval → live apply.

This skill is user-invoke only (`disable-model-invocation: true`) because it mutates a live Google Ads account.

**Actions:**
- KW-E01: Pause non-converting keywords
- KW-E02: Apply decision matrix quadrant actions
- KW-E03: Fix match type misalignment (remove + create)
- KW-E04: Resolve keyword duplicates
- KW-E05: Resolve cannibalization (cross-negatives)
- KW-E07: Clean up zombie keywords


---

## Command Routing

```
/keyword-optimizer                 → All recommended changes from latest audit
/keyword-optimizer pause           → KW-E01 (pause non-converting, non-core UNPROFITABLE — cascade-gated)
/keyword-optimizer cleanup         → KW-E07 (remove zombies — always safe, no cascade verification)
/keyword-optimizer match-type      → KW-E03 (fix match type misalignment)
/keyword-optimizer duplicates      → KW-E04 (resolve duplicates)
/keyword-optimizer cannibalization → KW-E05 (add cross-negatives)
/keyword-optimizer tiers           → KW-E02 (apply quadrant actions)

```

---

## MANDATORY SAFETY RULE

**NEVER apply changes directly via inline API calls.** The process is ALWAYS:

1. Generate `operations.json`
2. Run `mutate.js --mode=dry-run` (validate_only + show table)
3. Present dry-run table to user
4. Ask for explicit approval
5. Only on "yes": run `mutate.js --mode=live`

No exceptions. No shortcuts.

---

## Phase 0: Prerequisites & Pre-Flight

### Phase 0.1: Audit Freshness Check

1. Read `context/analysis/keyword-audit.md`
2. Check the report date in the header
3. If audit is >24 hours old:
   > "The keyword audit report is from {date} ({N} days ago). For accurate optimization, I recommend running a fresh audit first. Proceed with stale data, or run `/keyword-audit` first?"
4. If no audit report exists:
   > "No keyword audit report found. Running `/keyword-audit` first..."
   Then execute the keyword-auditor skill.

### Phase 0.2: Fresh Negative State Pull

**Always pull fresh negative keyword data** before generating operations (stale negatives = duplicate exclusions):

```bash
# Campaign-level negatives
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customerId} \
  --login-customer-id={loginCustomerId} \
  --query-file=.claude/skills/keyword-optimizer/reference/gaql/negatives-campaign.gaql \
  --no-date-range --allow-empty \
  --output=context/google-ads/data/negatives-campaign-kw.csv

# Shared negative lists
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customerId} \
  --login-customer-id={loginCustomerId} \
  --query-file=.claude/skills/keyword-optimizer/reference/gaql/negatives-shared.gaql \
  --no-date-range --allow-empty \
  --output=context/google-ads/data/negatives-shared-kw.csv

# Ad group-level negatives (for cross-negative conflict check)
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customerId} \
  --login-customer-id={loginCustomerId} \
  --query-file=.claude/skills/keyword-optimizer/reference/gaql/negatives-adgroup.gaql \
  --no-date-range --allow-empty \
  --output=context/google-ads/data/negatives-adgroup-kw.csv
```

**If scope includes KW-E08 (`bids` or full run), also pull fresh campaign bid-strategy state:**

```bash
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customerId} \
  --login-customer-id={loginCustomerId} \
  --query-file=.claude/skills/keyword-optimizer/reference/gaql/campaign-bid-strategy.gaql \
  --days=30 --allow-empty \
  --output=context/google-ads/data/campaign-bid-strategy.csv
```

Never use cached bid-strategy data — smart bidding targets move, and applying a mutation against stale state can push past the max-change rail. See `reference/bid-strategy-safety.md` for the full rationale.

**CSV field reading note:** `query.js` strips the `_micros` suffix and divides by 1,000,000 before writing the CSV, so the current-target columns are dollar strings, not micros. See the "Reading the bid-strategy CSV" table in `reference/bid-strategy-safety.md` for the exact column names per strategy type.

### Phase 0.3: Load Context

1. Read `config/ads-context.config.json` → customerId, loginCustomerId, keywordAudit thresholds
2. Read `context/google-ads/data/keyword-flags.csv` → flagged keywords
3. Read `context/google-ads/data/keyword-overlaps.csv` → overlap issues
4. Read `context/google-ads/data/keyword-tiers.csv` → full tier data (for E02 quadrant decisions)
5. Read `context/analysis/keyword-audit.md` → extract Recommended Actions table
6. **If KW-E08 in scope:** read `context/google-ads/data/campaign-bid-strategy.csv` (fresh from Phase 0.2) and `context/business.md` → `max_profitable_cpa` / `min_profitable_roas`. If unit economics missing → skip E08 and route the user to `/strategy-specialist`.

### Phase 0.4: Peer Pre-flight

**This optimizer mutates a live account. Before generating operations, it must check fresh peer audits and recent peer mutations.** Read `.claude/skills/keyword-optimizer/reference/handoff-matrix.md` for the full Peer Audit Freshness Table and Mutation Sensitivity Matrix.

Two distinct mechanisms — both produce inputs for Phase 1 (operation generation) and Phase 2 (dry-run rendering):

#### 0.4.a — Peer audit freshness sweep

For each of the 10 peer skills in `handoff-matrix.md → Peer Audit Freshness Table`:

1. Stat `context/analysis/{peer}-audit.md`. If absent → record `freshness_notes: "no fresh /{peer}"`.
2. If present, read the **header date** from the report (canonical) and compare to the freshness window. If the file mtime is older than the header date by >3 days, surface as a `freshness_notes` contradiction — header date wins, but flag it.
3. If fresh and the report flags issues on a campaign / ad group in the planned operations:
   - **`/tracking-specialist` failing or critical** → record a `hard_blocks` entry. Mutation is refused.
   - **`/strategy-specialist` reporting unit economics missing/placeholder** → record a `hard_blocks` entry. Mutation is refused. (This generalizes the existing Phase 0.3 KW-E08-only check to *all* mutation types.)
   - Any other peer (Eff / Conv / Bud / Bid / Comp / Struct) flagging the same scope → record a `soft_warns` entry with the peer's score, headline finding, date, and affected campaign/ad-group.

#### 0.4.b — Mutation sensitivity sweep

Read `context/account-changelog.md`. Recommend ≤24h old; if stale, prompt the user to refresh via `/account-changelog` (do not auto-trigger). If they decline, record the gap in `freshness_notes` and proceed.

For every campaign and ad group in the operations plan, scan changelog entries against the Mutation Sensitivity Matrix in `handoff-matrix.md`. Verdicts:

| Peer / source | Mutation type | Window | Verdict |
|---|---|---|---|
| `/rsa-maker`, manual ad edits | new ad / RSA edit / pause | ≤ 7d on overlapping ad group | soft-warn |
| `/bidding-optimizer` | bid strategy or target adjustment | 2–7d on overlapping campaign | soft-warn |
| `/search-term-optimizer` | negatives added / promotions | ≤ 7d on overlapping scope | soft-warn |
| `/account-auditor` / changelog | campaign restructure (rebuild/merge/split) | ≤ 14d on overlapping campaign | hard-warn |
| `/keyword-optimizer` (self) | any prior keyword mutation | ≤ 7d on overlapping scope | soft-warn |
| `/budget-optimizer` | budget raise / cut | ≤ 7d on overlapping campaign | soft-warn |
| `/geo-schedule-optimizer` | geo / device / schedule modifier | ≤ 7d on overlapping campaign | soft-warn |
| `/placement-optimizer` | placement exclusion | ≤ 7d on overlapping campaign | soft-warn |
| `/tracking-specialist` | conversion goal change | ≤ 30d account-wide | hard-warn |
| any peer | manual UI edit of keyword fields | ≤ 14d on overlapping ad group | hard-warn |

**KW-E08-specific tightening:** when operations include KW-E08, all bidding-related rows promote one verdict tier (soft-warn → hard-warn). Stacks on top of the existing 5 KW-E08 rails — does not replace them.

#### 0.4.c — Routing

The sweep produces an in-memory object (see `handoff-matrix.md → Output Contract for Phase 0.4`):

- `hard_blocks` non-empty → **abort.** Print the failing peer findings and the handoff command. Do not enter Phase 1.
- `hard_warns` non-empty → continue to Phase 1; Phase 2 will require explicit "confirm" per affected scope before Phase 3 live apply.
- `soft_warns` and `informational` → continue to Phase 1; Phase 2 surfaces them in the "Cross-skill context" block above the mutation table.
- `freshness_notes` → printed at the bottom of Phase 2's "Cross-skill context" so the operator knows where the picture is incomplete.

#### 0.4.d — Freshness rule

The header date inside each peer's report markdown is **canonical**. File mtime is a sanity check only. **Never auto-defer or auto-override** — surface contradictions in the dry-run output and let the operator decide. **Never auto-trigger a peer skill** from inside the optimizer; just note "no fresh {peer}" or "stale {peer}" in `freshness_notes`.

---

## Phase 1: Generate Operations

Read `.claude/skills/keyword-optimizer/reference/execute-rules.md` for full decision trees.
Read `.claude/skills/keyword-optimizer/reference/api-constraints.md` for mutation constraints.
Read `.claude/skills/keyword-optimizer/reference/handoff-matrix.md` for the Phase 0.4 sweep contract (consumed when stamping `meta.peer_context` and `meta.override_flags` on each operation).

### Scope filtering based on command:

| Command | Execute Actions |
|---------|----------------|
| (all) | E08 + E01 + E02 + E03 + E04 + E05 + E07 |
| pause | E01 |
| cleanup | E07 |
| match-type | E03 |
| duplicates | E04 |
| cannibalization | E05 |
| tiers | E02 |
| bids | E08 |

**KW-E08 generation notes** (full rules: `reference/execute-rules.md` → KW-E08, detailed safety rails: `reference/bid-strategy-safety.md`):
- Only runs on `TARGET_CPA`, `TARGET_ROAS`, `MAXIMIZE_CONVERSIONS` (with target), `MAXIMIZE_CONVERSION_VALUE` (with target). Any other strategy → skip + route to `/strategy-specialist`.
- B1 trigger: keyword-auditor flagged tCPA throttling (current_target / max_profitable_cpa < 0.5).
- T3 trigger: OVER_TARGET keywords represent ≥ 20% of campaign profitable conversions.
- Respects 5 rails: max-change per run (+30% raise / -15% lower), learning-period lockout (7 days), conversion floor (≥15/30d), budget-cap joint constraint, portfolio linkage.
- Portfolio bid strategies (`meta.is_portfolio=true`) are **blocked in v1** — emit an abort + route to `/strategy-specialist`. Do not pass `--confirm-portfolio` until a future version adds full portfolio support.

### For each action in scope:

1. **Read the audit findings** — extract affected keywords from flags/overlaps CSV
2. **Apply decision logic** — per execute-rules.md
3. **Check for conflicts:**
   - Cross-negatives: verify the negative doesn't block a wanted positive keyword in the same AG
   - Duplicates: ensure no negative conflicts with the paused/removed entry
   - Match type swaps: verify the new match type doesn't create a new duplicate
4. **Generate operation** — with full meta (action_id, category, target, campaign, ad_group, rationale)

### Build operations.json:

```json
{
  "description": "Keyword optimizer changes — {YYYY-MM-DD}",
  "generated_from": "context/analysis/keyword-audit.md",
  "generated_at": "{ISO timestamp}",
  "total_operations": {count},
  "operations": [ ... ]
}
```

Write to: `created/keyword-ops/operations-{YYYY-MM-DD}.json`

Tell user: "Generated {N} operations: {V} bid-strategy target updates, {X} pauses, {Y} match type fixes, {Z} cross-negatives, {W} duplicate resolutions."

---

## Phase 2: Dry-Run Validation

```bash
node .claude/skills/keyword-optimizer/scripts/mutate.js \
  --customer-id={customerId} \
  --login-customer-id={loginCustomerId} \
  --operations-file=created/keyword-ops/operations-{YYYY-MM-DD}.json \
  --mode=dry-run \
  --allow-remove
```

Note: `--allow-remove` is needed if any KW-E03 match type swaps exist (they require removing the old keyword). `--confirm-portfolio` is never passed in v1 — portfolio bid-strategy operations are blocked upstream (see Phase 1 notes).

### Present dry-run results to user:

The dry-run output has **two blocks**, in this order:

**Block 1 — Cross-skill context** (above the mutation table). Render the Phase 0.4 sweep result:

```
=== Cross-skill context ===

[hard-warns — REQUIRE CONFIRM]
  WARN: campaign "{campaign}" — restructure logged 9d ago via /account-auditor (window: 14d).
        Data discontinuity risk for KW-E01/E02/E03 on this campaign.
  WARN: campaign "{campaign}" — manual UI bid edit logged 5d ago (window: 14d).
        KW-E08 target update would stack on an in-flight manual experiment.

[soft-warns — informational]
  /quality-score-auditor (2026-04-28, score 62): "AG-level QS 4 on Brand-Core ad group" — affects KW-E03 swap target.
  /search-term-auditor (2026-04-30, score 71): "uncovered n-gram waste 'free' on Generic-Lead" — consider negatives before pausing keywords here.
  /budget-optimizer mutation 4d ago: budget +18% raise on "Generic-Lead" (window: 7d) — pauses will redistribute, not save spend.

[informational]
  /competitive-analyst (2026-04-22): IS Lost (Rank) 34% on Brand-Core — context only.

[freshness notes]
  no fresh /lp-auditor
  /tracking-specialist mtime is 5d older than its header date — surfaced as suspicious; header date wins.
```

**Block 2 — Mutation table.** The script output (per `mutate.js`).

After printing both blocks:

1. **If hard-warns present**, require explicit per-scope confirmation. For each hard-warn scope, prompt:
   > "Confirm hard-warn on {campaign|ad-group} ({reason}, window {N}d)? Type 'confirm' to proceed, anything else to drop this scope from the plan."
   - On "confirm" → log to the operation `meta.override_flags` as `peer_hard_warn_confirmed:{peer}:{window}d` and proceed.
   - On anything else → regenerate operations.json with the affected scope removed; re-run dry-run.

2. Then ask:
   > "These changes have NOT been applied. Ready to apply? (yes / no)"

If user says no:
- Ask what they want to change.
- Regenerate operations.json without the declined items.
- Re-run dry-run (which re-runs Phase 0.4 and re-renders Cross-skill context).

If user wants to approve individual operations:
- Allow selective approval (remove specific operations from the JSON).
- Re-run dry-run with filtered set.

**Hard-blocks never reach Phase 2.** Phase 0.4 aborts before Phase 1 if `hard_blocks` is non-empty.

---

## Phase 3: Live Apply

Only on explicit user "yes":

```bash
node .claude/skills/keyword-optimizer/scripts/mutate.js \
  --customer-id={customerId} \
  --login-customer-id={loginCustomerId} \
  --operations-file=created/keyword-ops/operations-{YYYY-MM-DD}.json \
  --mode=live \
  --allow-remove
```

### Post-apply:

1. **Present summary:**
   > "Applied {N} changes: {V} bid-strategy targets updated, {X} keywords paused, {Y} match types fixed, {Z} cross-negatives added."

2. **mutate.js auto-logs** to `context/analysis/keyword-changelog.md`

3. **Log to memory** — write to `context/memory/{YYYY-MM-DD}.md`:
   ```markdown
   ## Keyword Optimization
   - Applied {N} changes via keyword-optimizer
   - {X} keywords paused (villains + zombies + duplicates)
   - {Y} match types fixed (broad → phrase)
   - {Z} cross-negatives added
   - Operations file: created/keyword-ops/operations-{YYYY-MM-DD}.json
   ```

4. **Suggest next steps** if applicable:
   - "Consider re-running `/keyword-audit` in 7-14 days to measure impact."

---

## Edge Cases

| Scenario | Handling |
|----------|---------|
| No audit report exists | Run keyword-auditor first, then proceed |
| Audit is >24h old | Warn user, let them choose to proceed or re-audit |
| 0 operations generated | "No actionable issues found. The keyword set is healthy." |
| >100 operations | mutate.js blocks by default. Inform user: "Large change set ({N} ops). Proceed with --max-ops={N}?" |
| Match type swap loses history | Dry-run table prominently warns. User must acknowledge. |
| Cross-negative conflicts with positive | Reject the operation. Log why. Suggest manual resolution. |
| Shared negative list near capacity | Pre-flight checks member_count. Warn if >80% of 5,000. |
| Campaign uses portfolio bid strategy (KW-E08) | Abort the operation, route to `/strategy-specialist`. v1 does not mutate portfolios. |
| KW-E08 target clamped to max_profitable_cpa | Emit the clamped operation, note in rationale that the rail limited the raise. |
| KW-E08 campaign in learning period | Skip with "wait N days" rationale. Do not retry until learning period clears. |
| KW-E08 campaign below conversion floor (<15/30d) | Skip, route to `/strategy-specialist` — smart bidding cannot learn at this volume. |
| Recently created keyword | Skip from zombie/low performer pauses. Note as "new — monitoring." |
| Phase 0.4 `/tracking-specialist` failing | Hard-block — refuse all mutations. Print failing finding + `/tracking-specialist` handoff. Do not enter Phase 1. |
| Phase 0.4 `/strategy-specialist` unit-economics missing | Hard-block — refuse all mutations. Print missing field + `/strategy-specialist` handoff. Generalizes the existing E08-only check to all action types. |
| Phase 0.4 hard-warn on a campaign in plan | Continue to Phase 1; Phase 2 prompts for explicit "confirm" per scope; on confirm, stamp `meta.override_flags: ["peer_hard_warn_confirmed:..."]`. |
| Phase 0.4 changelog stale (>24h) | Prompt to refresh via `/account-changelog`. If declined, record gap in `freshness_notes` and proceed (no auto-trigger). |
| Phase 0.4 peer report header date contradicts mtime by >3d | Header date is canonical; surface contradiction in `freshness_notes`. Never auto-defer. |
