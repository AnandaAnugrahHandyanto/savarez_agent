# Budget Auditor — Scoring Model

Total: **100 points** across 5 modules.

| Module | Weight | Diagnostics | Why |
|---|---|---|---|
| **Allocation** | 30 | BUD-D13–D16 | Cross-campaign efficiency = highest-leverage budget decision; drifts every month as performance shifts. |
| **Limitation** | 25 | BUD-D01–D04 | Profitable+limited = leaky money lever; unprofitable+limited = active harm. |
| **Pacing** | 15 | BUD-D09–D12 | Important monthly, but a fix-it-once item. |
| **Sufficiency** | 15 | BUD-D05–D08 | Volume floor for smart bidding — matters but binary in practice. |
| **Shared Budgets** | 15 | BUD-D17–D19 | Lower fault rate at most accounts; many users don't use shared at all. |

## Per-diagnostic deduction

| Verdict | Effect on the diagnostic's points |
|---|---|
| PASS | full points retained |
| WARN | 40% deduction |
| FAIL | 100% deduction |
| INFO | no points at stake (informational) |
| SKIP | excluded from scoring (denominator reduced) |

## Per-diagnostic weights (within module)

### Limitation (25 pts)
- BUD-D01 — 5
- BUD-D02 — 5
- BUD-D03 — 10  ⭐ (heaviest in module)
- BUD-D04 — 5

### Sufficiency (15 pts)
- BUD-D05 — 6
- BUD-D06 — 3
- BUD-D07 — INFO (0)
- BUD-D08 — 6

### Pacing (15 pts)
- BUD-D09 — 4
- BUD-D10 — 4
- BUD-D11 — 4
- BUD-D12 — 3

### Allocation (30 pts)
- BUD-D13 — 10  ⭐
- BUD-D14 — 10  ⭐
- BUD-D15 — 5
- BUD-D16 — 5

### Shared Budgets (15 pts)
- BUD-D17 — 5
- BUD-D18 — 5
- BUD-D19 — 5

## N/A redistribution

When all diagnostics in a module return SKIP, the module returns N/A. Its weight redistributes proportionally to the remaining modules. Examples:

- **No shared budgets in account:** Shared module N/A → 15 pts redistribute. Other modules' total goes from 85 to 100.
- **`targetFallbackMode = "no_monthly_target"`:** Pacing N/A → 15 pts redistribute.
- **All-PMax account with no Search/Shopping tCPA campaigns:** BUD-D05 SKIPs (one diagnostic, not the whole module). Sufficiency module still scores on BUD-D08; just BUD-D05's 6 pts redistribute within the module.

## Bands

| Score | Grade |
|---|---|
| 90–100 | Excellent |
| 75–89 | Good |
| 60–74 | Needs Attention |
| <60 | Critical |
