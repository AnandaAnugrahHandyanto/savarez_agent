# Quality Score Auditor — Scoring Model

## Point Allocation

| Module | Max Points | Checks |
|---|---:|---|
| QS Distribution | 20 | D01(6) + D02(4) + D03(4) + D04(3) + D05(2) + D06(1) |
| Component Breakdown | 45 | D07(16) + D08(13) + D09(13) + D10(3) |
| Historical Trends | 15 | D11(6) + D12(4) + D13(3) + D14(2) |
| Competitive Context | 20 | D15(14) + D16(6) |
| **Total** | **100** | **16 diagnostics** |

## Deduction Rules

| Verdict | Deduction | Example (13pt check) |
|---|---|---|
| PASS | 0% — full points retained | 13/13 |
| WARN | 40% of check's points deducted | 7.8/13 |
| FAIL | 100% of check's points deducted | 0/13 |
| SKIP | Check excluded from scoring (denominator reduced) | --/-- |
| INFO | No points at stake | 0/0 |

## Grade Thresholds

| Score | Grade | Meaning |
|---|---|---|
| 90–100 | Excellent | All QS components healthy, stable trajectory |
| 70–89 | Good | Solid foundation with targeted fixes possible |
| 50–69 | Needs Attention | One or more components driving material CPC premium |
| <50 | Critical | Systemic QS issues — multiple components below average |

## Proportional Scoring When Checks Are Skipped

When a diagnostic returns SKIP, its points are removed from both numerator and denominator.

**Formula:**

```
final_score = points_earned / (100 - skipped_points) * 100
```

**Example:** Account has <60d of history (M3 SKIPs 15 pts) and no post-optimization changelog (M3-D13 SKIP absorbed in M3 SKIP).

- Max possible = 100 − 15 = 85
- Points earned = 68
- Final score = 68 / 85 × 100 = 80 (Good)

**Rules:**
- Round final score to nearest integer.
- If all checks in a module are SKIP, the module shows "N/A" instead of a score.
- Module-level scores follow the same proportional formula within their point pool.
- INFO checks (QS-D14 for example, when turned into pure INFO by insufficient data) never affect the denominator.

## Module-Level Scoring

Each module gets its own score for the report breakdown:

```
module_score = module_points_earned / (module_max - module_skipped) * 100
```

| Module | Max | Example Earned | Example Skipped | Module Score |
|---|---:|---:|---:|---:|
| QS Distribution | 20 | 16 | 0 | 80 |
| Component Breakdown | 45 | 30 | 0 | 67 |
| Historical Trends | 15 | 0 | 15 (no history) | N/A |
| Competitive Context | 20 | 14 | 0 | 70 |
| **Overall** | **100** | **60** | **15** | **71 (Good)** |

## Severity Mapping

Severity is reported per diagnostic for prioritization but does not change the point deduction. Deduction is always based on verdict (PASS / WARN / FAIL).

| Severity | Meaning |
|---|---|
| Critical | Directly costing spend (HIGH_SPEND_LOW_QS, BRAND_LOW_QS) |
| High | Significant traffic / efficiency impact (LOST_IS_RANK_QS, FAIL-verdict components) |
| Medium | Measurable optimization opportunity (WARN components, CPC premium) |
| Low | Minor cleanup, best-practice adherence (null QS) |

## Bidding-mode severity adjustment

Every FAIL / WARN verdict carries a **bidding-mode qualifier** so the report communicates the real impact:

- **Manual CPC campaigns:** QS directly scales CPC → keep severity as-is.
- **Smart Bidding campaigns** (tCPA / tROAS / MaxConv / MaxConvValue): QS still feeds Ad Rank and auction eligibility, but the smart bidding algorithm compensates at the CPC layer → severity is annotated with an `(impact dampened by Smart Bidding — investigate, don't silence)` note.

The score itself does not change. This is a reporting tag, not a scoring rule — silencing QS findings on Smart Bidding accounts is an anti-pattern called out in `synthesis-playbook.md`.
