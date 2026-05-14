# Keyword Auditor — Synthesis Playbook (Phase 1.5)

**Purpose:** Raw diagnostic flags are symptoms. This playbook forces Claude to walk the **constraint cascade (Measurement → Business → Conversion → Efficiency Recovery → Traffic → Creative)** *before* producing any recommendation. The flags are *evidence* for a root-cause hypothesis, not a to-do list.

**When to run:** After Phase 1 (diagnostics) produces `keyword-tiers.csv`, `keyword-flags.csv`, `keyword-overlaps.csv`. Before Phase 2 (scoring & report).

**Output:** An in-memory list of **hypotheses**, ranked by how much of the account's waste they explain. Each hypothesis carries supporting evidence and a recommended handoff (see `handoff-matrix.md`). Phase 2 uses this list to shape the report.

**Core principle:** The higher up the cascade the root cause sits, the less trustworthy any Traffic/Creative-layer action becomes. Never recommend pausing a keyword when a Measurement or Business layer hypothesis is unresolved. It is always better to investigate upstream than to prune downstream based on bad data.

---

## Layer 1 — Measurement (rule out first)

Goal: decide whether the flags can be trusted at all. If tracking is broken, every KW-D07 finding is a phantom.

Run each check against the Phase 1 outputs. Any trip → **Measurement hypothesis is active**.

### M1. Duplicate criterion_id with matching conversion counts

Read `keyword-tiers.csv`. Group by `criterion_id` across campaigns. If the *same criterion_id* appears in ≥2 campaigns with **identical primary conversion counts** but wildly different spend (>3× ratio), flag as **attribution anomaly**.

Why: Google Ads never double-assigns a criterion_id, so identical conv counts across rows almost always mean the report is joining the same conversion action to multiple rows — a tracking/attribution bug.

### M2. Zero-conv concentration in a single campaign

Read `keyword-flags.csv` → rows with `flag_type=PAUSE_CANDIDATE` or `UNPROFITABLE`. If **>60% of flagged spend** sits in a single campaign AND that campaign has **<50% of the account's primary conv share** relative to its spend share → hypothesis: conversion tag may have stopped firing for that campaign (broken URL param, landing page variant not firing pixel, GTM trigger drift).

### M3. Conversion lag mismatch

Read `business.md` for documented conversion lag. If the documented lag exceeds `config.searchTermAnalysis.conversionLagDays` by 2+ days, the evaluation window is still capturing in-flight conversions → efficiency metrics are distorted (CPAs inflated / ROAS deflated). Flag as **lag-inflated**. All KW-D07 findings must be re-stated as "CPA may be inflated — confirm with longer window."

### M4. Tier volatility between Period A and Period B

If `keyword-flags.csv` → `TIER_DEGRADED` count exceeds **20% of active keywords** AND the dominant shift is `OVER_TARGET → UNPROFITABLE` or `ACTIVE → INSUFFICIENT_DATA`, the account is either (a) under real CPC/auction pressure or (b) experiencing a tracking regression. Pair with M2 to disambiguate.

**If Layer 1 trips:** Every KW-D07 pause recommendation gets a "pending measurement verification" tag. Top handoff becomes `/tracking-specialist`. Do **not** recommend `/keyword-optimize pause` until M1–M4 are cleared.

---

## Layer 2 — Business (unit economics / bid strategy)

Goal: decide whether the flags are the account fighting its own bid strategy.

### B1. Campaign target bleeding

Read `campaigns-settings.csv`. For each campaign with flagged UNPROFITABLE keywords, compute:

```
# CPA mode:
bleed_ratio = campaign_tcpa / break_even_cpa
# ROAS mode (inverted — higher target is more aggressive):
bleed_ratio = break_even_roas / campaign_troas
```

- `bleed_ratio < 0.5` AND campaign has ≥5 OVER_TARGET keywords → **bid bleeding hypothesis**. Smart bidding is targeting efficiency far below the account's actual profitability gate, starving profitable keywords of bid. The "UNPROFITABLE" label may be forced by position-forced CvR drops, not by the keywords themselves.
- `bleed_ratio < 0.5` AND ≥30% of campaign's keywords are UNPROFITABLE → **severe bid bleeding**. Adjusting the campaign target (raise tCPA / lower tROAS) is likely the single highest-leverage fix in the audit.

Recommendation flips from "pause keywords" to "adjust campaign target toward profitability threshold (CPA: raise to break-even × 0.6–0.75 / ROAS: lower to break-even × 1.3–1.7), re-run audit after 14 days."

### B2. Profitability threshold drift

If `business.md` was last confirmed >60 days ago AND the account's blended efficiency trend shows current efficiency exceeds threshold by >20% (CPA > break-even × 1.2 / ROAS < break-even × 0.83) across **multiple** campaigns → **profitability threshold may be stale**. The market may have moved (CPC inflation, CvR drop). Handoff to `/strategy-specialist` to recompute unit economics before any keyword action.

### B3. Core-term concentration in UNPROFITABLE

**This is the single most important rule in the playbook.** Read `keyword-flags.csv` → `flag_type=UNPROFITABLE`. Compute:

```
core_term_share = sum(cost where is_core_term=true) / sum(cost where flag_type=UNPROFITABLE)
```

- `core_term_share >= 0.50` → **structural hypothesis: the offer/LP/ad is not converting core product traffic profitably**. The keywords are correct — the front door is broken. Pausing them removes the most relevant traffic the product can get. Handoffs: `/lp-auditor`, `/offer-auditor`, and investigate the dominant campaign's ad copy. **Explicitly recommend against pausing.**
- `0.30 <= core_term_share < 0.50` → **mixed hypothesis**. Split the UNPROFITABLE list: pause only the *non*-core tail, escalate core terms as structural.
- `core_term_share < 0.30` → **keyword-layer hypothesis may be correct**. However, run Layer 3 and Layer 4 (Efficiency Recovery) checks before confirming pause — even non-core keywords deserve an attempt at efficiency recovery before being paused.

### B4. Single-campaign concentration

If **>60% of UNPROFITABLE spend** sits in one campaign → that campaign is the unit of analysis, not individual keywords. Recommendation frames as "restructure campaign X" rather than "pause 47 keywords." Pair with B1 (campaign target check) — a single-campaign concentration almost always co-occurs with target bleeding OR an ad-group/LP-level issue.

---

## Layer 3 — Conversion (funnel mechanics)

Goal: decide whether the problem lives in the upstream conversion step (click → micro-conversion) or the downstream step (micro → macro-conversion) rather than at the keyword level. Micro and macro conversion actions are defined by the user in `conversionActionValues` — examples: lead form → qualified lead, add-to-cart → purchase, trial → paid subscription.

### C1. Funnel step ratio comparison

If `conversionActionValues` in config lists **both** a micro and a macro conversion action, compute:

```
micro_efficiency = spend / micro_conv   (or micro_conv_value / spend for ROAS)
macro_efficiency = spend / macro_conv   (or macro_conv_value / spend for ROAS)
step_ratio       = macro_efficiency / micro_efficiency
```

- Compare `step_ratio` between Period A and Period B at the **account** level.
- If `step_ratio` grew by >15% Period A vs Period B → **funnel leak hypothesis**. The upstream step (click → micro) is fine; the downstream step (micro → macro) is degrading. Keyword pausing cannot fix a downstream conversion drop.
- Handoff: `/strategy-specialist` (unit economics recheck), plus flag that KW-D07 findings are **downstream symptoms** of a funnel leak and should not be acted on until the leak is diagnosed.

### C2. Micro-conversion health per campaign

For each campaign with flagged UNPROFITABLE keywords, compute micro-conversion efficiency (CPA or ROAS for the micro action). If **micro-conversion efficiency is within the acceptable range** but macro-conversion efficiency exceeds the profitability threshold (break-even CPA or break-even ROAS) → the keywords are delivering qualified traffic that isn't converting downstream. Same conclusion as C1 — not a keyword problem.

---

## Layer 4 — Efficiency Recovery (exhaust before pausing)

Goal: for UNPROFITABLE keywords that survived Layers 1–3, determine whether their efficiency can be recovered through upstream improvements before recommending pause. Pausing is always a last resort.

### ER1. Search term verification (n-gram analysis)

Before acting on any UNPROFITABLE keyword, recommend running `/search-term-analyzer ngrams` over a longer timeframe (120–180 days) scoped to the campaigns containing flagged keywords.

Why: the keyword may be viable — specific non-converting or inefficient search term n-grams may be driving the waste. If n-gram analysis reveals bad n-grams that can be excluded as phrase-match negatives, the keyword itself can stay active. This is the most actionable and least disruptive fix.

- If specific n-grams explain >50% of the keyword's waste → **search term hypothesis is active**. Recommendation: exclude those n-grams, do not pause the keyword.
- If the keyword's search terms are broadly poor across all n-grams → strengthens the pause case, but continue to ER2–ER5 before confirming.

### ER2. Offer quality recovery

Route to `/offer-auditor`. A stronger offer raises conversion rate (CVR) across all keywords in the campaign — borderline UNPROFITABLE keywords may become profitable with better offer quality.

### ER3. Landing page quality recovery

Route to `/lp-auditor`. Same logic as ER2 — LP improvements raise CVR, which lowers effective CPA / raises effective ROAS for all keywords driving traffic to that page.

### ER4. Goal and economics viability

Route to `/strategy-specialist`. Two angles:

1. **Targets may be too aggressive** — efficiency goals that are tighter than the market allows will mechanically label viable keywords as UNPROFITABLE. Validating whether targets are realistic is a legitimate step.
2. **Unit economics can be improved** — higher LTV, lower COGS, or better backend conversion rates change the profitability threshold itself.

This is a valid option to consider, not a first grab. Present it but don't frame it as the default recommendation — adjusting targets should follow offer/LP improvement, not replace it.

### ER5. Bid optimization (PAR)

Route to `/bidding-specialist` (not yet built). The profit-to-acquisition ratio (PAR) may be improvable through bid strategy adjustments — sharpening bids can improve efficiency without pausing keywords.

Note: this skill is referenced for future use. Until it's built, the report should mention bid optimization as a consideration without routing to a specific skill.

**If Layer 4 produces any active recovery hypothesis:** The report must present the efficiency recovery sequence before any pause recommendation. Pause moves to "only after recovery options are exhausted or explicitly declined by the user."

---

## Layer 5 — Traffic / Creative (only now consider keyword actions)

Goal: after ruling out Layers 1–4, identify keyword-layer actions that are actually safe.

### T1. Safe-to-pause filter

A keyword can be recommended for pause **only if all of the following are true:**

1. No Layer 1 hypothesis is active for its campaign, OR it was explicitly cleared by a prior `/tracking-audit`.
2. Its campaign is not flagged under B1 (campaign target bleeding) OR the recommendation explicitly sequences "adjust target first, then re-run audit."
3. `is_core_term=false` for the keyword.
4. No Layer 3 funnel leak hypothesis is active at the account level.
6. The efficiency recovery sequence (Layer 4) has been presented in the report, framing pause as the action after recovery options are exhausted or declined.
5. The keyword is one of:
   - `UNPROFITABLE` AND non-core AND exceeds profitability threshold by >50% (CPA > break_even_cpa × 1.5 / ROAS < break_even_roas × 0.67), OR
   - `PAUSE_CANDIDATE` (zero primary conv past statistical gate), OR
   - `ZOMBIE` (zero impressions 30d) — always safe to pause, no cascade check needed.

If any of (1)–(4) fail, the keyword moves from "Act now" to "Investigate first" or "Pending upstream fix" in the report.

### T2. Structural keyword-layer fixes (always safe)

Independent of the cascade, these are always actionable regardless of upstream state:

- Duplicate keyword consolidation (KW-D10) — safe.
- Match type redundancy cleanup (KW-D03) — cosmetic, safe.
- Cross-campaign match conflicts via negatives (KW-D04) — safe.
- Branded below-first-page bid raises (KW-D14, branded only) — safe.
- Clearly informational keywords in commercial campaigns with near-zero converting volume (KW-D17) — safe.
- True zombies (KW-D08 ZOMBIE) — safe.

These go into "Act now (safe)" in the report without cascade gating.

### T3. Over-target is not a pause signal

`OVER_TARGET` keywords (efficiency between campaign target and profitability threshold — CPA between tCPA and break-even, or ROAS between tROAS and break-even) are **profitable**. Never recommend pausing them. Recommendation is always "adjust target (raise tCPA / lower tROAS), segment into a separate-target campaign, or accept above-target efficiency." This is already stated in SKILL.md but the synthesis layer must enforce it — any report section that mixes OVER_TARGET into a pause list is a bug.

---

## Producing the hypothesis list

After walking Layers 1–5, output an ordered list of hypotheses:

```
[
  {
    "id": "H1",
    "layer": "Measurement",
    "name": "Attribution anomaly on shared criterion_ids",
    "evidence": ["M1: criterion_id X in campaigns A and B with identical 17.83 primary conv"],
    "confidence": "high",
    "blocks_downstream_actions": true,
    "handoff": "/tracking-specialist",
    "explains_waste_pct": null  // unknown until verified
  },
  {
    "id": "H2",
    "layer": "Business",
    "name": "Bid bleeding in PowerPoint campaign",
    "evidence": ["B1: campaign target vs profitability threshold (ratio 0.27)", "B4: 71% of UNPROFITABLE spend in this campaign"],
    "confidence": "high",
    "blocks_downstream_actions": false,
    "handoff": "/keyword-optimize bids",
    "explains_waste_pct": 71
  },
  ...
]
```

Rank rules:
1. Measurement-layer hypotheses always sort first (they gate everything below).
2. Within a layer, rank by `explains_waste_pct` descending.
3. A "structural (B3 core-term)" hypothesis outranks individual keyword actions even when its explanatory share is hard to quantify — the downside of wrongly pausing core terms is much larger than the downside of wrongly leaving them running for another week.

This hypothesis list is the spine of Phase 2's report. See `report-template.md` for how it maps into the Diagnosis / Evidence / Actions sections.
