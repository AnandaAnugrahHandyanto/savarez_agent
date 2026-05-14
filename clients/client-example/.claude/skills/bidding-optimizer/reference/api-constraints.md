# Bidding Optimizer — Google Ads API Constraints (v23)

Reference for the resources `mutate.js` touches. Always check the latest docs at https://developers.google.com/google-ads/api/docs/release-notes.

## Resources

| Resource | Allowed operations | Used by |
|---|---|---|
| `campaign` | update only (target fields) | adjust-targets, scale, fix-shared-portfolio (campaign side) |
| `bidding_strategy` | update | adjust-targets (portfolio), scale (portfolio) |
| `campaign_criterion` | create / update | modifiers, schedule, remove-adjustments |
| `bidding_data_exclusion` | create / update / remove | data-exclusion (requires `name`, `scope`, `start_date_time`, `end_date_time`) |
| `conversion_value_rule` | create / update / remove | value-bidding |

## Mutable target fields

For `campaign`:
- `target_cpa.target_cpa_micros`
- `target_roas.target_roas`
- `maximize_conversions.target_cpa_micros`
- `maximize_conversion_value.target_roas`
- `target_roas.cpc_bid_ceiling_micros` (cpc-cap)
- `target_impression_share.cpc_bid_ceiling_micros` (cpc-cap)

For `bidding_strategy` (portfolio) — same fields, prefixed with `bidding_strategy.`.

**Never mutate `campaign.bidding_strategy_type` directly** — that's a strategy migration. Use the experiment lifecycle (`migrate`) so existing learning isn't blown away.

## Update mask

Update mask paths must reflect the dotted leaf:

```js
// Correct
update_mask: { paths: ['target_cpa.target_cpa_micros'] }
// Incorrect
update_mask: { paths: ['target_cpa'] }
```

`mutate.js` flattens the `fields` object via `flattenKeys` for `campaign` and `bidding_strategy` resources to enforce this.

## Operation ordering

Server expects all dependent creates before updates. Our local order:

1. `bidding_data_exclusion` (stabilize the model)
2. `bidding_strategy` (portfolio adjustments first)
3. `campaign` (campaign-level target updates)
4. `campaign_criterion` (modifiers / schedule)

## Validate-only dry run

Every mutation runs once with `validate_only: true` before live apply. The mutate.js runtime handles this — never call `customer.mutateResources` outside this script.

## Quotas

- `bidding_data_exclusion`: 50 per account active.
- `conversion_value_rule`: 100 per account.
- `bidding_strategy` (portfolio): 250 per account.

`mutate.js` does not enforce these — it surfaces errors verbatim.

## Status changes

- Strategy / target field updates are accepted while a campaign is ENABLED.
- `bidding_strategy.status = REMOVED` cannot be reversed; we never emit that operation.
