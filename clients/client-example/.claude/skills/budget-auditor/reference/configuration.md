# Budget Auditor — Configuration

The auditor reads `config/ads-context.config.json → budgetAudit` (analyst-cached + static defaults) and the top-level `accountCurrency`.

## Top-level

| Key | Type | Description |
|---|---|---|
| `accountCurrency` | string (ISO 4217) | Currency for $-formatting across the audit. Defaults to "USD" if missing. Reusable by other skills. |

## `budgetAudit` block — analyst-cached

| Key | Type | Description |
|---|---|---|
| `monthlyBudgetTotal` | number \| null | Account-level monthly budget target. Required unless `targetFallbackMode = "no_monthly_target"`. |
| `campaignTargets` | object | Optional `{ "campaign name": { "monthly": N, "priority": "protect"|"scale"|"hold" } }`. Campaigns not listed inherit even allocation from the total. |
| `seasonalityProfile.mode` | "flat" \| "highlight_months" | Seasonality behavior. |
| `seasonalityProfile.months` | string[] | Lowercased month names that matter (`["may","november","december"]`). |
| `seasonalityProfile.notes` | string | Human notes. |
| `lastConfirmed` | ISO date | Last analyst confirmation of these values. |
| `businessMdHash` | string | First 16 chars of SHA-256 of `business.md` content at last confirmation. |
| `targetFallbackMode` | null \| "no_monthly_target" | Escape hatch when user can't supply a monthly total — pacing module SKIPs. |
| `accountChangelogConsentForSession` | null \| ISO date | Cache for session-scoped auto-refresh consent (Phase 0.2). |

## `budgetAudit` block — static defaults

| Key | Default | Description |
|---|---|---|
| `dailyBudgetToCpaRatio` | 2.0 | BUD-D05 threshold. |
| `overspendAlertPp` | 10 | BUD-D10 percentage points trigger. |
| `underspendAlertPp` | 10 | BUD-D11 percentage points trigger. |
| `isLostBudgetThreshold` | 10 | BUD-D01 IS-lost-budget percentage trigger. |
| `minConvVolumeForSmartBidding` | 30 | BUD-D08 fallback when channel/strategy combo not in lookup table. |
| `zeroSpendDays` | 7 | BUD-D16 confirmation threshold for "active campaign with no spend." |
| `maxSingleMutationMultiplier` | 1.3 | Optimizer cap — matches smart-bidding ~30% learning-reset threshold. |
| `opportunityProjectionMode` | "is_lost_budget" | Heuristic for opportunity-mode dollarization. v1.1 swaps in Performance Planner. |
| `includeExperiments` | true | Default INCLUDES active experiment variants because they consume real budget. Inverted relative to bidding-auditor. |

## How fields interact with the cascade

- `monthlyBudgetTotal === null` AND `targetFallbackMode !== "no_monthly_target"` → Phase 0.1 fails validation; user must run `reconfirm`.
- `targetFallbackMode === "no_monthly_target"` → pacing module SKIPs entirely; report banners the choice.
- `primaryKPI` + break-even resolved from sibling configs (`biddingAudit`, `searchTermAnalysis.biddingStrategy`, `competitiveAnalyst`). When neither resolves, profitability-dependent diagnostics return INFO with `blocking: ['business']`.

## Phase 0 interview writes

The interview (Phase 0.0 in SKILL.md) writes:
- `monthlyBudgetTotal`
- `campaignTargets` (only when user opts in)
- `seasonalityProfile`
- `lastConfirmed = today`
- `businessMdHash` = `sha256(business.md).slice(0,16)`

It does NOT touch static defaults unless the user explicitly overrides one.

## Adding a new threshold

1. Add the key to the `_staticDefaults` block in `config/ads-context.config.json` with a sensible default.
2. Read it from `lib.js` or the engine via `config.budgetAudit.<key> ?? <default>`.
3. Document it here.
4. Mention it in `diagnostic-rules-*.md` for the diagnostic that consumes it.
