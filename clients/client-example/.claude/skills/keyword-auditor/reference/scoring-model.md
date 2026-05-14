# Keyword Auditor — Scoring Model

## Point Allocation

| Module | Max Points | Checks |
|--------|-----------|--------|
| Match Type Health | 20 | D01(3) + D02(8) + D03(4) + D04(5) |
| Performance Segmentation | 30 | D05(0) + D06(0) + D07(15) + D08(8) + D09(7) |
| Cannibalization & Duplicates | 25 | D10(7) + D11(10) + D12(5) + D13(3) |
| Keyword Hygiene | 10 | D14(5) + D15(5) |
| Intent Alignment | 15 | D17(8) + D18(7) |
| **Total** | **100** | **17 diagnostics** |

D05 and D06 are INFO-only. They surface hero keywords and tier classification data for the report but contribute zero points to the score.

## Deduction Rules

| Verdict | Deduction | Example (8pt check) |
|---------|-----------|---------------------|
| PASS | 0% -- full points retained | 8/8 |
| WARN | 40% of check's points deducted | 4.8/8 |
| FAIL | 100% of check's points deducted | 0/8 |
| SKIP | Check excluded from scoring (denominator reduced) | --/-- |
| INFO | No points at stake | 0/0 |

## Grade Thresholds

| Score | Grade | Meaning |
|-------|-------|---------|
| 90-100 | Excellent | Keywords are well-structured, performing, and clean |
| 70-89 | Good | Solid foundation with minor optimization opportunities |
| 50-69 | Needs Attention | Significant issues impacting performance or efficiency |
| <50 | Critical | Structural problems requiring immediate intervention |

## Proportional Scoring When Checks Are Skipped

When a diagnostic returns SKIP, its points are removed from both numerator and denominator to avoid penalizing accounts for inapplicable checks.

**Formula:**

```
final_score = points_earned / (100 - skipped_points) * 100
```

**Example:** Account has no PMax campaigns (D12 SKIP, 5pts) and no Manual CPC (D14 SKIP, 3pts).

- Max possible = 100 - 5 - 3 = 92
- Points earned = 78
- Final score = 78 / 92 * 100 = 84.8 (Good)

**Rules:**
- Round final score to nearest integer
- If all checks in a module are SKIP, the module shows "N/A" instead of a score
- Module-level scores follow the same proportional formula within their point pool
- INFO checks (D05, D06) never affect the denominator since they carry 0 points

## Module-Level Scoring

Each module gets its own score for the report breakdown:

```
module_score = module_points_earned / (module_max - module_skipped) * 100
```

| Module | Max | Example Earned | Example Skipped | Module Score |
|--------|-----|---------------|-----------------|--------------|
| Match Type Health | 20 | 16 | 0 | 80 |
| Performance Segmentation | 30 | 22 | 0 | 73 |
| Cannibalization & Duplicates | 25 | 20 | 5 (D12 SKIP) | 100 |
| Keyword Hygiene | 10 | 7 | 3 (D14 SKIP) | 100 |
| Intent Alignment | 15 | 8 | 0 | 53 |
| **Overall** | **100** | **73** | **8** | **79 (Good)** |

## Severity Mapping

Severity is reported per diagnostic for prioritization but does not change the point deduction. Deduction is always based on verdict (PASS/WARN/FAIL).

| Severity | Meaning |
|----------|---------|
| Critical | Immediate action required -- actively harming performance |
| High | Significant waste or structural problem |
| Medium | Optimization opportunity with measurable impact |
| Low | Minor cleanup, best practice adherence |
