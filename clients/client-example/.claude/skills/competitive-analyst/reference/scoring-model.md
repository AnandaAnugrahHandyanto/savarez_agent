# Competitive Analyst — Scoring Model

## Point Allocation

| Module | Max Points | Checks |
|--------|-----------|--------|
| IS Health & Trends | 30 | D01(15) + D02(15) |
| Competitive Position | 35 | D03(SKIP) + D04(SKIP) + D05(15) + D06(SKIP) + D07(SKIP) + D08(12) + D09(8) |
| Competitive Impact | 35 | D10(SKIP) + D11(15) + D12(SKIP) + D13(20) |
| **Total** | **100** | **13 diagnostics (7 active + 6 skipped)** |

## Skipped Checks (6 — Auction Insights required)

CA-D03, CA-D04, CA-D06, CA-D07, CA-D10, CA-D12 are permanently SKIP in Track A (API-native only). Their points are excluded from the denominator.

## CA-D09 Conditional Skip

When CA-D09 is SKIP (no standard Shopping campaigns or single ad group), its 8 points redistribute within Module 2 to CA-D05 and CA-D08:
- CA-D05: 15 → 19 points
- CA-D08: 12 → 16 points

## Deduction Rules

| Verdict | Deduction | Example (15pt check) |
|---------|-----------|---------------------|
| PASS | 0% — full points retained | 15/15 |
| WARN | 40% of check's points deducted | 9/15 |
| FAIL | 100% of check's points deducted | 0/15 |
| SKIP | Check excluded from scoring (denominator reduced) | --/-- |

## Grade Thresholds

| Score | Grade | Meaning |
|-------|-------|---------|
| 90-100 | Excellent | Strong competitive position — visibility stable or growing |
| 70-89 | Good | Solid position with minor competitive pressures |
| 50-69 | Needs Attention | Significant competitive pressure affecting visibility or KPIs |
| <50 | Critical | Severe competitive pressure — material KPI impact, immediate action needed |

## Proportional Scoring When Checks Are Skipped

When a diagnostic returns SKIP, its points are removed from both numerator and denominator.

**Formula:**

```
final_score = points_earned / (100 - skipped_points) * 100
```

**Example — typical account (no Shopping, all 6 Auction Insights skipped):**

Active checks: CA-D01(15) + CA-D02(15) + CA-D05(19*) + CA-D08(16*) + CA-D11(15) + CA-D13(20) = 100 points
(*redistributed from CA-D09 SKIP)

Skipped: CA-D03, D04, D06, D07, D09, D10, D12 = 0 active points (all excluded)

- Max possible = 100 (after redistribution)
- Points earned = 76
- Final score = 76 / 100 * 100 = 76 (Good)

**Example — account with Shopping campaigns (2+ ad groups):**

Active checks: CA-D01(15) + CA-D02(15) + CA-D05(15) + CA-D08(12) + CA-D09(8) + CA-D11(15) + CA-D13(20) = 100 points

Skipped: CA-D03, D04, D06, D07, D10, D12 = 0 active points (all excluded)

- Max possible = 100
- Points earned = 61
- Final score = 61 / 100 * 100 = 61 (Needs Attention)

**Rules:**
- Round final score to nearest integer
- If all checks in a module are SKIP, the module shows "N/A" instead of a score
- Module-level scores follow the same proportional formula within their point pool

## Module-Level Scoring

Each module gets its own score for the report breakdown:

```
module_score = module_points_earned / (module_max - module_skipped) * 100
```

| Module | Active Checks | Max (typical) | Formula |
|--------|--------------|---------------|---------|
| IS Health & Trends | D01 + D02 | 30 | (earned) / 30 * 100 |
| Competitive Position | D05 + D08 [+ D09] | 35* | (earned) / (active max) * 100 |
| Competitive Impact | D11 + D13 | 35 | (earned) / 35 * 100 |

*Module 2 active max varies: 35 with D09 active (Shopping), 35 with D09 SKIP (points redistributed to D05+D08).

## Severity Mapping

Severity is reported per diagnostic for prioritization but does not change the point deduction. Deduction is always based on verdict (PASS/WARN/FAIL).

| Severity | Meaning |
|----------|---------|
| High | Significant competitive pressure — visibility or KPIs materially affected |
| Medium | Moderate competitive pressure — optimization opportunity |
