# Module 2 — Target Validation (BID-D05 → BID-D09)

Total module weight: 25 points. Highest-leverage module — wrong targets cause systemic loss.

## BID-D05 — tCPA vs. Break-Even (8 pts)

**Inputs:** campaign target_cpa (inline or via portfolio) + `biddingAudit.breakEvenCPA` from config.

**Logic:**

| Condition | Verdict |
|---|---|
| target_cpa > break_even | FAIL |
| target_cpa within 50% of break-even (after applying tCpaSafetyMargin) | WARN |
| target_cpa comfortably below break-even | PASS |
| Strategy is not tCPA, or break-even unset | SKIP |

**Routing:** `/bidding-optimizer adjust-targets` once cascade clears.

## BID-D06 — tROAS vs. Break-Even (8 pts)

**Inputs:** campaign target_roas (or portfolio) + `biddingAudit.breakEvenROAS`.

**Logic:**

| Condition | Verdict |
|---|---|
| target_roas < break_even_roas | FAIL |
| target_roas within 10% margin above break-even | WARN |
| target_roas ≥ break-even with margin | PASS |
| Not tROAS / break-even unset | SKIP |

## BID-D07 — PAR Ratio (3 pts)

**Definition:** PAR = target_cpa / actual_cpa. Above 1.0 means under-target (profitable). Posture-based goal: growth=1.2, balanced=1.5, efficiency=2.0.

**Logic:**

| PAR | Verdict |
|---|---|
| < 1.0 | FAIL — overshooting target |
| < 0.8 × `parTarget` | WARN |
| ≥ posture target | PASS |
| Strategy not tCPA, or no actual data | SKIP |

## BID-D08 — Target vs. Actual Deviation (3 pts)

**Inputs:** `campaigns-bidding-daily.csv` last `tcpaDeviationDays` (default 14).

**Logic:** Compute deviation `(actual - target) / target * 100`. ROAS uses inverse signal.

| Deviation | Verdict |
|---|---|
| Within ±`tcpaDeviationPp` (default 20%) | PASS |
| Outside ±20% sustained for 14d | WARN |

**Routing:** Inform target adjustment recommendation, but never trigger one alone — see synthesis playbook hypothesis Conv1 / Eff1.

## BID-D09 — Starvation Zone (3 pts)

**Definition:** Target so aggressive it limits delivery. Signals:
- search_rank_lost_impression_share > 50%
- search_impression_share < 40%
- Actual CPA / ROAS clearly tighter than target (CPA < 0.7×target, or ROAS > 1.3×target)

**Logic:** All three signals together → WARN, plus emit a starvation-recovery opportunity entry suggesting a 20% target loosening.

**Routing:** `/bidding-optimizer adjust-targets` with `--rationale=starvation-recovery`.

---

## Cross-cutting note: portfolio strategies

When a campaign is a portfolio member (`campaign.bidding_strategy` is set), the auditor resolves the target from `bidding-strategies.csv`. The finding meta carries `target_source: "portfolio"` and `portfolio_name`. The optimizer must respect this when planning a target change — portfolio updates affect every campaign in the portfolio, and need `--confirm-portfolio`.
