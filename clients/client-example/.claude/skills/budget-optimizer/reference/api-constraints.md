# Budget Optimizer — API Constraints

The optimizer mutates `campaign_budget` resources via `customer.mutateResources(...)` from `google-ads-api`.

## Resource shape

```js
{
  resource_name: "customers/{cid}/campaignBudgets/{bid}",
  amount_micros: 50_000_000,            // $50.00/day in micros
  // immutable post-create:
  // explicitly_shared, period, type
}
```

## Mutable fields

| Field | Mutable? | Notes |
|---|---|---|
| `amount_micros` | YES | The lever this skill pulls. |
| `name` | YES (rare) | Avoid mid-life rename — disrupts reporting and analyst recall. |
| `delivery_method` | YES | STANDARD ↔ ACCELERATED — but ACCELERATED is being deprecated; don't change unless explicitly requested. |
| `total_amount_micros` | YES (CUSTOM_PERIOD only) | Lifetime total for non-daily budgets; rare in PPCOS workflows. |
| `explicitly_shared` | NO | Cannot toggle individual ↔ shared in place. To convert, the optimizer creates a new budget and updates each campaign's `campaign.campaign_budget`. v1 surfaces this as a manual handoff. |
| `period` | NO | Cannot change DAILY ↔ CUSTOM_PERIOD. |
| `type` | NO | Cannot change STANDARD ↔ FIXED_CPA. |

## Update mask

Always submit only the fields being changed. mutate.js auto-generates the mask from the keys present in `op.fields`.

```js
{
  entity: 'campaign_budget',
  operation: 'update',
  resource: { resource_name, amount_micros: 65_000_000 },
  update_mask: { paths: ['amount_micros'] }
}
```

## Atomic batches

`mutateResources` accepts an array. The skill batches in groups of 50 with `partial_failure: false` (default) — any single failure rolls back the entire batch. For per-op error isolation, set `partial_failure: true` and inspect the response error blob; v1 keeps it strict.

## Validate-only dry-run

```js
await customer.mutateResources(ops, { validate_only: true });
```

A pass throws no error; a fail throws with `e.errors[0].message` describing the violation. mutate.js prints PASSED/FAILED + the error.

## Common failures

| Error | Likely cause |
|---|---|
| `BudgetError.BUDGET_REMOVED` | Budget already removed; refresh `campaign-budgets.csv` and retry. |
| `OperationAccessDenied` | Login customer mismatch or insufficient OAuth scope. |
| `RangeError` | `amount_micros` below minimum or absurdly high. Empirically: 0 micros is rejected; 500,000 micros (~$0.50/day) is accepted under `validate_only=true`. The exact floor sits somewhere between, and Google does not publish it. Don't rely on a $1/day floor. |
| `BiddingStrategyConstraint` | A portfolio strategy attached to the campaign refuses the new daily budget. Surface as Bid-layer violation. |
| `MutateError.PARENT_RESOURCE_NOT_FOUND` | Stale resource_name; re-pull. |

## Currency

`amount_micros` is always in the **account's** currency, regardless of `accountCurrency` in config. Validate currency match before submission. mutate.js surfaces `accountCurrency` in the dry-run table for analyst clarity.

## Recommended budget (informational)

`campaign_budget.has_recommended_budget` and `recommended_budget_amount_micros` come from Google's `BudgetCommonService`. v1 reads but doesn't blindly apply — the synthesis playbook treats Google's recommendation as one signal, not a directive (avoids the recommendation-parrot loop).
