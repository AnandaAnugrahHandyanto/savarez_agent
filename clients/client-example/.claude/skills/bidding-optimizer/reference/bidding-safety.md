# Bidding Optimizer — Safety Rails

Every operation runs through these gates inside `mutate.js` before either dry-run or live apply. The auditor pre-fills the `meta` block on each operation; the optimizer re-validates and refuses anything that's missing or stale.

## Gate 1 — Cascade clearance

`meta.cascade_clear` carries one of {`pass`, `soft-block`, `blocking`} for each layer:
- `measurement`
- `business`
- `efficiency`
- `conversion`

Rules:
- Any `blocking` → hard refuse with the relevant handoff.
- `soft-block` requires `meta.confirmed === true` (set by SKILL.md after the user types "confirm" — never autopopulated).

## Gate 2 — Learning window

`meta.learning_gate.days_since_strategy` and `days_since_target` come from the freshly-pulled `context/account-changelog.md` (max 1h old). Source of truth: `lib.js → parseAccountChangelog` + `getLearningStatus`.

Rules:
- If either days_since < 14 → hard refuse.
- Override: `--force-learning --override-reason="..."` (logged, surfaced in the dry-run table, written to mutation history).

## Gate 3 — Stacking limit (per session)

Per session = per `mutate.js` invocation. Per-campaign limits:
- ≤ 1 strategy mutation
- ≤ 1 target mutation
- modifier / schedule / exclusion / rule ops are uncapped — each affects a distinct underlying resource

Keys on `meta.campaign_id` (immutable identifier), with `meta.target` only as a fallback for account-level ops with no `campaign_id`.

This prevents a queued batch from compounding two strategy or target changes on one campaign in one window.

## Gate 4 — Target step cap

`meta.step_cap.pct = ((new - old) / old) * 100`. Default cap: 20%. Aggressive cap: 30%. Anything beyond is hard refused.

The auditor must clamp before queuing — the optimizer doesn't quietly adjust the value.

## Gate 5 — Portfolio confirmation

Any operation with `meta.is_portfolio === true` requires `--confirm-portfolio`. Portfolio mutations affect every shared campaign — the dry-run table calls this out explicitly.

## Gate 6 — Value-rules guard

Any operation with `resource === "conversion_value_rule"` is hard-refused unless `biddingAudit.valueRulesAllowed === true` in `config/ads-context.config.json`. This gate is enforced by `mutate.js`, not just documented.

## Override ergonomics

`--force-learning`, `--aggressive`, `--confirm-portfolio` are CLI-only. Reasons must accompany via `--override-reason="..."` when learning is overridden. The mutation history captures all flags + reasons.

## Per-channel sanity

PMax: `mutate.js` blocks any target change when monthly conv volume on the campaign is below the smart-bidding threshold for the channel/strategy combo (per `lib.js → getConvVolumeThreshold`).

Search: standard 20%/30% range applies.

Manual CPC: target adjustment doesn't apply — only `cpc-cap`, `modifiers`, `schedule`.

## What this skill never does in v1

- Mutate `campaign.bidding_strategy_type` directly (use `migrate` with experiments).
- Touch portfolio attachment (`campaign.bidding_strategy`).
- Apply value rules without `valueRulesAllowed=true` in config.
- Auto-create data exclusions (must be approved per-window in dry-run).
- Ramp targets > 30% in a single session.
