# Launcher Interface — `/bidding-optimizer setup --output=json`

`search-launcher`, `shopping-launcher`, and `pmax-launcher` call this skill during their pre-flight phase to get a single source of truth on bid strategy and initial targets. This document defines the contract.

## CLI

```
/bidding-optimizer setup \
  --campaign-type=SEARCH | SHOPPING | PERFORMANCE_MAX | DISPLAY | DEMAND_GEN | VIDEO \
  --monthly-conv-est=<integer estimate of expected monthly conversions> \
  --primary-kpi=cpa | roas \
  --posture=growth | balanced | efficiency \
  --output=json
```

Optional:
- `--campaign-name=<string>` — for logging
- `--account-snapshot` — read current campaigns to find existing portfolios that could be joined

## Output

```json
{
  "recommendedStrategy": "TARGET_CPA",
  "initialTcpa": 60,
  "initialTroas": null,
  "portfolioAssignment": null,
  "rationale": "Search campaign with 80 expected monthly conv passes the 30/30d functional threshold; balanced posture maps to PAR target 1.5; initial tCPA derived from break-even $X × tCpaSafetyMargin (0.7).",
  "warnings": []
}
```

If the threshold cannot be met (e.g. 5 expected monthly conv on Search) the recommended strategy falls back to MaxConv with `initialTcpa: null` and the rationale documents the volume gap.

## Behaviour

- No interactive prompts in `--output=json` mode. Missing inputs → JSON `{ "error": "...", "missing": [...] }` and exit 1.
- No mutations are emitted — the launcher is responsible for applying the strategy + target via its own `campaign.create` flow.
- Warnings array carries non-blocking notes (e.g. "monthly conv est below recommended; expect 2–4 weeks of learning before performance stabilises").

## Validation rules

- `monthly-conv-est` must be a positive integer.
- `primary-kpi` must match the account's `biddingAudit.primaryKPI` if set; otherwise the value is accepted and noted.
- `posture` defaults to `balanced` if omitted.

The launcher must not bypass this contract — when bidding moves we want one place where the rationale is composed.
