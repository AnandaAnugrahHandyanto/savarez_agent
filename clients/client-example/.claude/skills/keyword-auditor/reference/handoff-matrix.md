# Keyword Auditor — Handoff Matrix

**Purpose:** Map each hypothesis from `synthesis-playbook.md` to the right upstream or peer skill. The keyword auditor is a diagnostic, not a fix-everything skill — its most valuable output is often "do not act on this data yet, run skill X first."

**When to use:** Phase 3, after the hypothesis list is built. Only surface handoffs whose hypothesis survived the cascade.

---

## By hypothesis layer

### Measurement layer (highest priority — blocking)

| Hypothesis trigger | Handoff | Why |
|---|---|---|
| M1 — Duplicate criterion_id attribution anomaly | `/tracking-specialist` | Conversion join logic may be broken; verify tag firing and attribution path before any keyword action |
| M2 — Zero-conv concentration in one campaign | `/tracking-specialist` (scoped to the campaign's LP URLs) | Tag may have stopped firing for a specific LP variant or URL pattern |
| M3 — Conversion lag exceeds window | Re-run keyword audit with longer window (`/keyword-auditor 60` or `/keyword-auditor 90`) | Not a skill handoff — a window correction |
| M4 — Unusual tier volatility | `/tracking-specialist` AND `/account-changelog` | Rule out both tracking regression and manual account changes as causes |

All Measurement handoffs are **blocking**: no KW-D07 pause recommendation can be executed until the handoff closes. The report marks these actions as "Pending measurement verification."

### Business layer

| Hypothesis trigger | Handoff | Why |
|---|---|---|
| B1 — tCPA bleeding (ratio < 0.5) | `/bidding-optimizer adjust-targets` + `/strategy-specialist` for target validation | Campaign-level target raise is now owned by `bidding-optimizer` (not `keyword-optimize`). Pass campaign id, current target, suggested direction (raise tCPA / lower tROAS), and reason in the handoff payload. The bidding-optimizer enforces its own learning-window + step-cap gates. |
| B2 — Profitability threshold may be stale | `/strategy-specialist` | Recompute unit economics from current LTV / CvR / CPC before trusting the profitability threshold gate |
| B3 — Core-term concentration in UNPROFITABLE | `/lp-auditor`, `/offer-auditor`, and inspect ad copy in the dominant campaign | The keywords are correct — the conversion path is failing. Pausing is the wrong action |
| B4 — Single-campaign concentration | Scoped campaign investigation (ad copy + LP + target + structure) | Treat the campaign as the unit of work, not the keywords |

### Conversion layer

| Hypothesis trigger | Handoff | Why |
|---|---|---|
| C1 — Funnel step ratio degrading | `/strategy-specialist` (unit economics) + `/lp-auditor` (micro→macro leak often LP-driven) | Keyword pausing cannot fix a downstream conversion drop |
| C2 — Micro-conv healthy, macro-conv beyond threshold | `/lp-auditor`, `/offer-auditor` | Same reasoning — downstream leak, not acquisition leak |

### Efficiency Recovery layer

| Hypothesis trigger | Handoff | Why |
|---|---|---|
| ER1 — N-gram analysis needed | `/search-term-auditor ngrams` (120–180d, scoped to flagged campaigns) | Verify at search-term level whether specific n-grams explain the waste — exclude those as negatives instead of pausing the keyword |
| ER2 — Offer not recently audited | `/offer-auditor` | Higher CVR from improved offer makes borderline keywords profitable |
| ER3 — LP not recently audited | `/lp-auditor` | Higher CVR from improved LP makes borderline keywords profitable |
| ER4 — Efficiency targets may be too aggressive | `/strategy-specialist` | Validate whether targets are realistic given current market; consider unit economics adjustment as a secondary option |
| ER5 — Bid strategy optimization available | `/bidding-auditor` then `/bidding-optimizer adjust-targets` | Profit-to-acquisition ratio (PAR) optimization may improve efficiency without pausing. Run the audit first to compute PAR + clearance gates. |

Efficiency Recovery handoffs are **sequenced before pause**: the report must present these options before recommending `/keyword-optimize pause` on any UNPROFITABLE keyword. Pausing is always a last resort.

### Traffic / Creative layer

| Hypothesis trigger | Handoff | Why |
|---|---|---|
| T1 — Safe-to-pause list survives cascade | `/keyword-optimize pause` | Standard pause flow for non-core unprofitable keywords, zombies, pause candidates |
| T2 — Structural keyword fixes (duplicates, match conflicts, redundancy, informational) | `/keyword-optimize duplicates`, `/keyword-optimize match-type`, `/keyword-optimize cannibalization` | Always safe regardless of upstream hypothesis |
| T3 — OVER_TARGET keywords beyond campaign target (above tCPA / below tROAS) | `/bidding-optimizer adjust-targets` | Campaign-level target tweak now lives in `bidding-optimizer`. Adjust target (raise tCPA / lower tROAS) or segment, never pause. |

---

## Sequencing rule

When multiple hypotheses are active, the report sequences handoffs by layer, not by confidence:

1. **First** — all Measurement handoffs (blocking)
2. **Then** — Business handoffs (B1 target adjustment, B2 unit economics recheck, B3 LP/offer audit)
3. **Then** — Conversion handoffs (if M and B haven't already covered them)
4. **Then** — Efficiency Recovery handoffs (ER1 n-gram analysis, ER2 offer, ER3 LP, ER4 strategy, ER5 bid optimization)
5. **Then** — Traffic/Creative handoffs (only the ones that survive T1's safe-to-pause filter, plus all T2 structural fixes which are always safe)

Never present the Phase 3 offer as a flat list of `/keyword-optimize *` subcommands. Always frame it as a **sequence**: "Do X first, then Y, then Z."

---

## What to tell the user in Phase 3

The handoff offer in Phase 3 follows this shape:

> **Top hypothesis: {layer} — {name}** (explains ~{pct}% of flagged waste)
>
> Before I touch any keywords, I'd recommend:
>
> 1. **{blocking handoff}** — {one-sentence why}
> 2. **{business-layer handoff}** — {one-sentence why}
> 3. **{safe structural fixes}** — these are safe regardless: `/keyword-optimize duplicates` ({N} groups), `/keyword-optimize match-type` ({M} groups)
>
> Only after (1) and (2) would I run `/keyword-optimize pause`, and even then only on the {K} non-core keywords that survive the cascade — not the {J} core product terms in the UNPROFITABLE list.
>
> Which would you like to start with?

If Layers 1–3 are all clear and only T1/T2 hypotheses are active, the offer reverts to the standard `/keyword-optimize *` menu with no blockers.
