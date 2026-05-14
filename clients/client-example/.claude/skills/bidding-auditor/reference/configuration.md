# Bidding Auditor — Configuration

The auditor reads `config/ads-context.config.json → biddingAudit`. The block has two sections: analyst-cached values (written during Phase 0 interview) and static defaults (tunable thresholds with stable defaults).

## Analyst-cached values

| Key | Type | Description |
|---|---|---|
| `primaryKPI` | "cpa" \| "roas" | Account's primary success metric. Determines which break-even gate drives the audit. |
| `breakEvenCPA` | number \| null | Highest profitable CPA. Required when primaryKPI = "cpa". |
| `breakEvenROAS` | number \| null | Lowest profitable ROAS, ratio (e.g. 5.3 means 530%). Required when primaryKPI = "roas". |
| `conversionActionValues` | object | Map of action name → $ value. Keys must exactly match `googleAds.conversionActions`. |
| `primaryConversionAction` | string | The action name treated as the headline conversion. |
| `growthEfficiencyPosture` | "growth" \| "balanced" \| "efficiency" | Account-level posture. Drives the PAR target. v1 = account-level only. |
| `parTarget` | number | Profit-to-acquisition ratio target. growth=1.2, balanced=1.5, efficiency=2.0. |
| `tCpaSafetyMargin` | number | Default 0.7 — used to validate tCPA leaves headroom below break-even. |
| `lastConfirmed` | ISO date | Last time the analyst confirmed these values. |
| `businessMdHash` | string | First 16 chars of SHA-256 of business.md content at last confirmation. |
| `targetFallbackMode` | null | Reserved. v1 hard-blocks if break-even is missing — no fallback. |

## Static defaults

| Key | Default | Description |
|---|---|---|
| `smartBiddingMinConv` | 30 | Channel-aware fallback when threshold reference doesn't cover the combination. |
| `manualBiddingMaxConv` | 100 | Above this monthly conv, smart bidding is the default expectation. |
| `tcpaDeviationPp` | 20 | Allowed deviation between actual and target before BID-D08 fires. |
| `tcpaDeviationDays` | 14 | Tail window for deviation analysis. |
| `starvationZoneCvrDropPp` | 30 | Threshold for BID-D09 when CVR drop pattern is checked. |
| `learningWindowDays` | 14 | Smart bidding learning duration. |
| `extendedLearningDays` | 14 | If still in learning beyond this, BID-D10 fires. |
| `stackingPreventionDays` | 14 | Optimizer refuses a second mutation if a prior one is fresher than this. |
| `maxTargetStepPct` | 20 | Default target step cap per mutation. |
| `aggressiveMaxTargetStepPct` | 30 | Max with `--aggressive` flag. |
| `cpcSpikeThresholdPct` | 25 | BID-D22 trigger. |
| `cpcRisingTrendPeriods` | 3 | BID-D23 — number of consecutive 7-day windows. |
| `dataExclusionAutoApply` | false | Reserved for v1.1 — auto-create data exclusions. |
| `valueRulesAllowed` | true | Whether the optimizer's value-bidding subcommand is enabled. |
| `includeExperiments` | false | Include experiment campaigns (`experiment_type ≠ 'BASE'`) in scope. CLI flag `--include-experiments` or the `experiments` token override per-run. Removed and paused campaigns are always excluded at the GAQL layer. |

## Hard-block on missing unit economics

Bidding without break-even is meaningless. Phase 0 hard-blocks if `breakEvenCPA` (or `breakEvenROAS`, depending on KPI) is null/placeholder, and routes the user to `/strategy-audit --execute unit-economics`. This is **the** difference vs. budget-auditor's softer fallback.

## Top-level fields read

The auditor also reads:
- `googleAds.customerId`, `googleAds.loginCustomerId`, `googleAds.dateRange`
- `searchTermAnalysis.conversionLagDays` for lag offset
- `googleAds.conversionActions` to align the per-action values
