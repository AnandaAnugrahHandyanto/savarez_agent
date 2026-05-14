# Module 5 — Bid Adjustments (BID-D18 → BID-D21)

Total module weight: 5 points (deliberately small — most modifiers are noise on smart bidding).

## Filter rule

`campaigns-criteria-bidding.csv` is pulled with `WHERE bid_modifier != 1.0`. Within the engine, modifiers on smart-bidding campaigns are **informational only** unless `modifier == 0` (full exclusion still applies).

## BID-D18 — Adjustments on Smart Bidding (2 pts)

| Condition | Verdict |
|---|---|
| Modifier ≠ 1.0 on smart bidding, modifier ≠ 0 | INFO ("ignored by smart bidding") |
| Modifier == 0 on smart bidding | INFO with WARN tone — exclusion still applies, confirm intent |
| No such modifiers found | PASS |

## BID-D19 — Device Validity (1 pt)

Valid only on Manual CPC. Surface device modifiers on mCPC; ask the analyst to confirm they reflect current device-level CPC efficiency.

## BID-D20 — Location / Schedule (1 pt)

Same pattern as BID-D19 for location and ad-schedule criteria.

## BID-D21 — Audience (1 pt)

Same pattern as BID-D19 for audience criteria (USER_LIST, USER_INTEREST, AGE_RANGE, GENDER, INCOME_RANGE, PARENTAL_STATUS).

---

## Anti-pattern guard

Never recommend "remove all modifiers" without checking each is on Manual CPC. The optimizer's `remove-adjustments` subcommand is the way to apply this — it filters by strategy type before generating any operations.
