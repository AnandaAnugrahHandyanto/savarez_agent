# Bidding Auditor — Scoring Model

## Module weights

| Module | Max Points | Diagnostics |
|---|---|---|
| Target Validation        | 25 | BID-D05(8) + BID-D06(8) + BID-D07(3) + BID-D08(3) + BID-D09(3) |
| Strategy Selection       | 20 | BID-D01(5) + BID-D02(5) + BID-D03(10) + BID-D04(0) |
| Learning Phase           | 15 | BID-D10(4) + BID-D11(4) + BID-D12(3) + BID-D13(4) |
| Portfolio Health         | 15 | BID-D14(4) + BID-D15(3) + BID-D16(4) + BID-D17(4) |
| CPC & Cost Health        | 10 | BID-D22(4) + BID-D23(3) + BID-D24(3) |
| Conversion Value Rules   | 10 | BID-D25(5) + BID-D26(5) |
| Bid Adjustments          | 5  | BID-D18(2) + BID-D19(1) + BID-D20(1) + BID-D21(1) |
| **Total**                | **100** | **26 diagnostics** |

## Verdict deductions

| Verdict | Deduction |
|---|---|
| PASS  | 0% |
| WARN  | 40% |
| FAIL  | 100% |
| SKIP  | excluded — denominator reduced |
| INFO  | no points at stake (always 0) |

`score = points_earned / (100 - skipped_points) * 100`

## N/A redistribution

Bidding has more "you don't use this feature" cases than budget. Redistribute proportionally across remaining modules:

- No portfolios → Portfolio Health = N/A (15 pts redistribute)
- No mCPC campaigns → Bid Adjustments = N/A (5 pts redistribute, small effect)
- No conversion value rules → Conversion Value Rules = N/A (10 pts redistribute)
- All-smart-bidding accounts: Adjustments + Value Rules can both be N/A (15 pts redistributed across 5 modules)

## Bands

| Score | Grade |
|---|---|
| 90–100 | Excellent |
| 75–89  | Good |
| 60–74  | Needs Attention |
| <60    | Critical |
