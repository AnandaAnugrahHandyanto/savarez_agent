# Competitive Analyst — Synthesis Playbook (Phase 1.5)

**Purpose:** Raw diagnostic flags are symptoms. This playbook forces Claude to walk a **5-layer cascade (Data Validation → Business Economics → QS/Rank Diagnosis → Strategic Assessment → Tactical Routing)** *before* producing any recommendation. The flags are *evidence* for a root-cause hypothesis, not a fix-it list.

**When to run:** After Phase 1 (diagnostics) completes. Before Phase 2 (scoring & report).

**Output:** An in-memory list of **hypotheses**, ranked by how much of the account's competitive pressure they explain. Each hypothesis carries supporting evidence and a recommended handoff. Phase 2 uses this list to shape the report.

**Core principle:** The higher up the cascade the root cause sits, the less trustworthy any tactical recommendation becomes. Never recommend "bid higher to gain IS" when the account's efficiency already exceeds its profitability threshold. Never recommend "fix rank" without first checking whether rank loss is QS-driven or bid-driven. Never route to a specialist skill without first telling the user *why* that's the right move for *their* business.

---

## KPI Mode & Terminology

This playbook is **KPI-agnostic**. The account's `primaryKPI` (from E1) determines which direction is "good" and which formulas to use. All economics checks use the same logic — only the direction flips.

| Concept | CPA Mode | ROAS Mode |
|---------|----------|-----------|
| **Efficiency metric** | CPA (cost / conversions) | ROAS (conv_value / cost) |
| **Profitability threshold** | `breakEvenCPA` (max acceptable CPA) | `breakEvenROAS` (min acceptable ROAS) |
| **Target** | `targetCPA` (campaign goal) | `targetROAS` (campaign goal) |
| **Profitable** | efficiency < threshold | efficiency > threshold |
| **Unprofitable** | efficiency > threshold | efficiency < threshold |
| **Headroom** | threshold - efficiency (positive = room to bid) | efficiency - threshold (positive = room to bid) |
| **Overshoot** | efficiency - threshold (positive = over limit) | threshold - efficiency (positive = under limit) |
| **"Worse" direction** | higher CPA | lower ROAS |
| **Implied efficiency floor** | avg_cpc / cvr (min possible CPA) | cvr × avg_conv_value / avg_cpc (max possible ROAS) |

When the playbook says **"headroom > 0"**, it means the account is profitable with room to spare, regardless of KPI mode. When it says **"efficiency exceeds threshold"**, it means the account is unprofitable.

Throughout this playbook: `efficiency` = the campaign's or keyword's primary KPI metric. `threshold` = the profitability boundary. `target` = the campaign goal (which may differ from threshold in growth mode).

---

## Data Enrichment (before walking the cascade)

Before starting Layer 1, gather the business context that makes the cascade possible. The competitive analyst already has `keyword-is.csv` and `campaign-is-timeseries.csv` — but it needs business economics to interpret them.

### E1. Business context resolution

Read `context/business.md` and `config/ads-context.config.json` → extract:

- `primaryKPI` ("cpa" or "roas") — from `keywordAudit.primaryKPI` or `searchTermAnalysis.biddingStrategy`
- `breakEvenCPA` or `breakEvenROAS` — from `keywordAudit` block, or compute from `business.md` unit economics
- `targetCPA` or `targetROAS` — from `business.md` goals section
- `growthMode` — boolean: is the account accepting beyond-threshold efficiency for growth? (Read goals section)
- `conversionActions` — which conversion action is the primary KPI driver

If neither `keywordAudit` config nor `business.md` provides a profitability threshold, note as **economics unknown** — the cascade can still run but Layer 2 hypotheses will carry a "pending economics verification" caveat.

### E2. Compute campaign-level economics

From `campaign-is-timeseries.csv`, aggregate per campaign over the evaluation period:

```
campaign_cpa  = total_cost / total_conversions
campaign_roas = total_conversions_value / total_cost
campaign_cvr  = total_conversions / total_clicks
campaign_avg_cpc = total_cost / total_clicks
```

Compute whichever is the primary KPI. Both are available for reference, but the cascade uses `primaryKPI` for all threshold comparisons.

### E3. Compute keyword-level economics

From `keyword-is.csv`, for each of the top 20 keywords (by spend):

```
keyword_efficiency = (CPA mode) cost / conversions  |  (ROAS mode) conv_value / cost
keyword_cvr = conversions / clicks  (if conversions > 0)
keyword_ctr = clicks / impressions

# Implied efficiency floor — best-case efficiency at current auction prices
# CPA mode:  implied_floor = avg_cpc / cvr   (lowest achievable CPA)
# ROAS mode: implied_floor = cvr × avg_conv_value_per_conv / avg_cpc  (highest achievable ROAS)
```

### E4. Read Quality Score data

Read `context/google-ads/data/keywords.csv` (pulled in Phase 0.2.1 using the `gads-context` query tool). This CSV contains actual QS data for every active keyword:

- `ad_group_criterion.quality_info.quality_score` — overall QS (1-10)
- `ad_group_criterion.quality_info.creative_quality_score` — ad relevance component (BELOW_AVERAGE / AVERAGE / ABOVE_AVERAGE)
- `ad_group_criterion.quality_info.post_click_quality_score` — LP experience component
- `ad_group_criterion.quality_info.search_predicted_ctr` — expected CTR component

Match keywords from `keywords.csv` to the flagged keywords from CA-D08 by keyword text + campaign name. This gives Layer 3 direct QS visibility — no proxies needed.

---

## Layer 1 — Data Validation (rule out first)

Goal: decide whether the diagnostic flags can be trusted. If the data is unreliable, every recommendation built on it is speculative.

### DV1. Campaign maturity

Read `campaign-is-timeseries.csv`. For each campaign, count the number of days with data.

- Campaign with <30 days of data → IS trajectory (CA-D01) is unreliable for that campaign. Trend analysis on short windows is noise.
- Campaign with <14 days → CA-D11 CPC correlation is unreliable (needs 4+ weekly data points).
- Flag these campaigns as **data-limited**. Their findings still appear in the report but carry a maturity caveat.

### DV2. Bidding strategy context

Read `campaign.bidding_strategy_type` from `campaign-is-timeseries.csv`.

- **Max Conversions / tCPA / Max Conv Value / tROAS:** These strategies optimize for conversions or value, *not* for impression share. Low IS may be the strategy's deliberate choice — it's opting out of expensive auctions where the expected return doesn't meet the target. This reframes "rank loss" from a problem to a smart bidding trade-off.
- **Manual CPC / Max Clicks / tIS:** These strategies directly control or target impression share. Rank loss on these is a genuine competitive pressure signal.

If all flagged campaigns use conversion-optimizing strategies, add the hypothesis: **"Smart bidding is intentionally trading IS for efficiency — low IS may be a feature, not a bug."** This doesn't dismiss the findings, but it changes the framing from "you're losing 88% of auctions" to "smart bidding is choosing not to enter 88% of auctions because the expected return doesn't meet your target."

### DV3. Conversion data sufficiency

For each campaign in the KPI impact estimate (CA-D13):

- <10 conversions in the evaluation period → efficiency metrics are statistically unreliable. Impact estimates are speculative.
- <30 conversions → efficiency has high variance. Impact estimates are directional, not precise.

Flag affected campaigns. If the top-impact campaign has <10 conversions, the KPI impact section must carry a "low-confidence estimate" caveat.

**If Layer 1 trips:** Findings are still reported, but every recommendation gets a caveat matching the specific data limitation. Do NOT suppress findings — just contextualize them.

---

## Layer 2 — Business Economics (can the account afford to compete?)

Goal: determine whether gaining IS is economically viable *before* recommending it. This is the layer the competitive analyst must never skip — it's the difference between "fix rank" (generic) and "you can't afford to fix rank at current economics" (advisory).

### BE1. Efficiency headroom check

**This is the single most important check in the playbook.**

For each campaign with high rank-lost IS (>40%):

```
# CPA mode:
headroom = breakEvenCPA - campaign_cpa       # positive = profitable
# ROAS mode:
headroom = campaign_roas - breakEvenROAS      # positive = profitable
```

**Interpretation:**

- **Headroom > 0 (profitable)** → The account has room to bid higher. Gaining IS through bids is economically viable. Quantify: "Efficiency is [metric], [headroom] inside the [threshold] profitability threshold — there's room to bid up."

- **Headroom <= 0 (at or beyond threshold)** → **Increasing bids to gain IS will accelerate losses.** The account is already operating at or beyond its profitability limit. The recommendation MUST NOT be "bid higher" or "gain IS through bid adjustments."

  Instead: "Efficiency is [metric], already [overshoot] beyond the profitability threshold. Gaining IS through higher bids would worsen returns. Fix conversion economics first (QS improvement increases IS without raising CPC; LP/offer improvements improve conversion efficiency), then reassess IS recovery."

- **Growth mode exception:** If `business.md` explicitly states the account accepts beyond-threshold efficiency for growth, use the stated target as the ceiling instead of break-even. But still flag the risk: "Operating in growth mode at [efficiency] (target: [target]). Gaining IS at current economics would push efficiency further from target. Recommend efficiency improvements to create headroom before competing for more IS."

**For keyword-level granularity:** Also compute BE1 for the top 20 keywords from `keyword-is.csv`. Some keywords may have excellent economics (profitable, high rank loss) while others are already unprofitable. This segments the recommendation: "Compete harder on [keyword A, B, C] where economics are viable; fix efficiency on [keyword D, E, F] before investing in IS recovery."

### BE2. Implied efficiency floor at auction prices

For each campaign:

```
# CPA mode:  implied_floor = campaign_avg_cpc / campaign_cvr   (lowest achievable CPA)
# ROAS mode: implied_floor = campaign_cvr × avg_conv_value / campaign_avg_cpc  (highest achievable ROAS)
```

This is the theoretical best-case efficiency — what the campaign would achieve if every other variable were optimized. Compare against the profitability threshold:

- **CPA mode:** `implied_floor > breakEvenCPA` → market is structurally too expensive at current CVR
- **ROAS mode:** `implied_floor < breakEvenROAS` → market yields structurally too little value at current CVR

In either case, no amount of IS recovery will make this campaign profitable without:
- Raising CVR (LP, offer, QS improvements)
- Lowering CPC (better QS, bid optimization)
- Improving unit economics (higher AOV, better LTV, different pricing)

**When implied floor fails the threshold:** Flag as **market economics problem**. The recommendation shifts entirely to conversion economics — this is not a competitive position problem that bid strategy can solve.

### BE3. Budget headroom

Cross-reference CA-D02 (IS loss decomposition):

- Budget-lost IS near zero AND rank-lost IS high → The account has budget capacity to absorb more impressions. If rank improves (through QS, not bids), budget can fund the additional volume.
- Budget-lost IS significant (>15%) AND efficiency beyond target → Paradox: spending more budget at current economics wastes more money. Route to efficiency improvement first.
- Budget-lost IS significant AND efficiency within target → Budget increase is viable. This is the one scenario where "spend more" is directly actionable.

### BE4. IS recovery ROI estimate

For campaigns where IS recovery is potentially viable (BE1 headroom > 0):

```
# Estimate marginal economics of recovered IS
additional_impressions = current_impressions × (IS_gap / current_IS)
additional_clicks = additional_impressions × current_CTR
additional_conversions = additional_clicks × current_CVR
additional_cost = additional_clicks × current_CPC  (conservative — marginal CPC may be higher)
additional_value = additional_conversions × avg_conv_value

# CPA mode:  marginal_efficiency = additional_cost / additional_conversions
# ROAS mode: marginal_efficiency = additional_value / additional_cost
```

Compare `marginal_efficiency` against the target. If it exceeds the target (CPA: marginal > target; ROAS: marginal < target), even with headroom, the marginal IS is more expensive than current IS (winner's curse — the last impressions are the most expensive). Quantify: "Recovering the next 10pp of IS would yield [marginal_efficiency] vs your [target] target — the marginal economics exceed your goal."

**If Layer 2 trips (any BE hypothesis active):** Every tactical recommendation must be framed through the economic lens. "Gain more IS" becomes "improve economics to make IS recovery viable." The report's Diagnosis section leads with the economic finding, not the IS finding.

---

## Layer 3 — Quality Score & Rank Diagnosis (what's behind the rank loss?)

Goal: determine whether rank loss is QS-driven (fixable without bid increase) or bid-driven (requires economic viability first). This distinction changes the entire action plan.

**Data source:** `keywords.csv` pulled in Phase 0.2.1 — contains actual QS data (1-10 score + three component scores) for every active keyword. No proxies needed.

### QS1. Read QS for flagged keywords

Match the flagged keywords from CA-D08 to `keywords.csv` by keyword text + campaign name. For each flagged keyword, read:

- `quality_score` (1-10) — the overall QS
- `creative_quality_score` — ad relevance: BELOW_AVERAGE / AVERAGE / ABOVE_AVERAGE
- `post_click_quality_score` — LP experience: BELOW_AVERAGE / AVERAGE / ABOVE_AVERAGE
- `search_predicted_ctr` — expected CTR: BELOW_AVERAGE / AVERAGE / ABOVE_AVERAGE

Note: QS may be null for keywords with very few impressions. Count nulls and note the gap.

### QS2. Interpret QS against rank loss

**Per-keyword diagnosis:**

- **QS >= 7 + high rank loss (>40%)** → **BID-CONSTRAINED**. The ad and LP are competitive — the account is simply being outbid. Cross-reference with BE1:
  - If headroom > 0 → bid increase is viable. Label: **HIGH-VALUE TARGET**.
  - If headroom <= 0 → stuck. Good QS but can't afford to bid higher. The only path is CVR improvement to create headroom, then revisit bids. Label: **FIX-ECONOMICS-FIRST**.

- **QS <= 5 + high rank loss** → **QS-CONSTRAINED**. This is the *good news* scenario: QS improvement raises IS *without* increasing CPC. Drill into the three components to pinpoint the fix:
  - `creative_quality_score = BELOW_AVERAGE` → ad copy / ad relevance is the bottleneck → route to ad copy improvement
  - `post_click_quality_score = BELOW_AVERAGE` → LP experience is the bottleneck → route to `/lp-auditor`
  - `search_predicted_ctr = BELOW_AVERAGE` → expected CTR is low → may be a keyword-ad relevance issue (wrong ad group structure, poor headline matching) → route to keyword restructure + ad copy improvement

- **QS 6 + high rank loss** → **MARGINAL QS**. Some improvement possible through QS, but bid capacity also matters. Check BE1 headroom to decide emphasis.

- **QS null (insufficient data)** → **UNKNOWN**. Can't assess. Note the keyword and its spend. If it's high-spend, flag that we're flying blind on this keyword's rank loss driver.

### QS3. Aggregate QS picture

Compute the weighted average QS across flagged keywords (weighted by spend):

- **Weighted avg QS >= 7** → Account's rank loss is predominantly bid-driven. The synthesis verdict should reflect this.
- **Weighted avg QS <= 5** → Account's rank loss is predominantly QS-driven. The lever is ad/LP quality, not bids.
- **Mixed (weighted avg QS 5.5-6.5)** → Segment: some keywords are QS-constrained, others are bid-constrained. Per-keyword guidance in the report.

Also compute the component breakdown: what percentage of flagged keywords have each component as BELOW_AVERAGE? If 80% have `post_click_quality_score = BELOW_AVERAGE`, the LP is the dominant issue — a single `/lp-auditor` run could move QS on most flagged keywords.

### QS4. QS-IS interaction insight

The most valuable insight for the user is the combination of QS and IS data:

- "12 of your 14 flagged keywords have QS 4-5 with `post_click_quality_score = BELOW_AVERAGE`. Fixing your LP alone could raise QS by 2-3 points, which typically improves IS by 15-25% — without spending a penny more on bids."

- "Your flagged keywords have QS 8-9 but 88% rank loss. The quality is there — you're just being outbid. But with efficiency already beyond your target, higher bids aren't the answer. You need to improve conversion economics first, then bid up with the headroom you've created."

**If Layer 3 produces clear QS findings:** They become the primary evidence for the Diagnosis section. "Rank loss is QS-driven — your LP experience score is BELOW_AVERAGE on 80% of flagged keywords. Fixing the LP gains IS without increasing spend" is fundamentally different advice from "Rank loss is bid-driven — you'd need better economics before you can compete."

---

## Layer 4 — Strategic Assessment (what should the account actually do?)

Goal: synthesize Layers 1-3 into a strategic position verdict — not just "run these skills" but "here's what this means for your business and what I'd advise."

### SA1. Campaign prioritization

Rank campaigns by IS recovery priority using a composite of:

1. **Economic viability** (Layer 2) — campaigns with headroom rank higher
2. **QS opportunity** (Layer 3) — campaigns with QS-driven rank loss rank higher (easier to fix)
3. **KPI impact** (CA-D13) — campaigns with higher estimated lost conversions/value rank higher
4. **Budget availability** (BE3) — campaigns with budget headroom rank higher

Produce a ranked list: "If you could only fix one campaign, start with X because [reason]. Then Y. Campaign Z should wait until [upstream fix] is resolved."

### SA2. Competitive entry response (for CA-D11 findings)

When the branded campaign shows a new competitor signal (CPC up, IS down, r < -0.7):

**Check branded efficiency:**
- Branded efficiency well within target → "Match bids to defend brand. At [branded efficiency], you have headroom. The risk of losing branded traffic to a competitor outweighs the cost of higher CPCs."
- Branded efficiency approaching target → "Monitor but don't over-react. Identify the competitor (run `/competitor-ads`). New entrants often test and pull back. Set a CPC ceiling at the point where branded efficiency would exceed the target."
- Branded efficiency beyond target → "Competitor is making branded auctions expensive. Tactical options: (a) improve branded QS to lower CPCs, (b) run competitor analysis to understand their strategy, (c) consider if defending 100% branded IS is worth the cost vs accepting some branded leakage."

### SA3. Market position verdict

Based on all evidence, assign one of four strategic verdicts:

| Verdict | Conditions | What it means |
|---------|-----------|---------------|
| **Compete aggressively** | Efficiency has headroom, QS-driven rank loss, budget available | Fix QS → IS improves → capture more conversions/value. Clear ROI path. |
| **Fix economics first** | Efficiency at/beyond target, rank loss is secondary to efficiency problem | IS recovery is a downstream goal. Improve CVR through LP, offer, QS. Reassess IS after economics improve. |
| **Selective competition** | Some campaigns viable, others not. Mixed picture. | Invest in viable campaigns, hold on unviable ones. Detailed per-campaign guidance. |
| **Structural challenge** | Implied efficiency floor fails threshold, CVR too low for market CPCs | The market economics don't support this account at current conversion rates. Strategic discussion needed — may need product/pricing/offer changes, not just ads optimization. |

Each verdict maps to a fundamentally different action sequence. The report must name the verdict explicitly.

---

## Layer 5 — Tactical Routing (only now sequence the actions)

After Layers 1-4, produce a segmented action plan. Never a flat table.

### Skill availability gate

Before routing to any skill, verify it exists: check for `.claude/skills/{skill-name}/SKILL.md`. If the skill is not yet built, still include the recommendation but mark it as **(not yet built)** and note what the user can do manually in the meantime. This keeps the playbook forward-looking without producing broken handoffs.

### Action categories (in order):

**1. Investigate first (blocking)** — populated when Layer 1 or Layer 2 raises unresolved questions:
- "Verify conversion tracking on campaign X" (DV3 low conv count)
- "Confirm growth mode targets with stakeholder" (BE1 growth mode ambiguity)

**2. Fix economics first (structural)** — populated when BE1 headroom is negative or BE2 implied floor fails threshold:
- "Improve LP conversion rate on [campaigns]" → `/lp-auditor`
- "Audit offer quality — competitor messaging is winning on [value prop]" → `/offer-auditor`
- "Review QS on [N] keywords — QS improvement lowers CPC and raises IS simultaneously" → `/keyword-auditor`
- "Review campaign targets — smart bidding may be too conservative/aggressive" → `/strategy-specialist`

**3. Compete where viable (tactical)** — populated only for campaigns/keywords where economics support IS recovery:
- "These [N] keywords have headroom and high rank loss — investigate QS or bid strategy" → `/keyword-auditor` or bid strategy review
- "Branded defense: match competitor bids within the efficiency ceiling" → bid strategy review

**4. Strategic discussion (escalation)** — populated when SA3 verdict is "fix economics first" or "structural challenge" AND CA-D13 impact exceeds 10%:
- "[N] conversions at risk but efficiency already exceeds target — this is a strategic discussion, not a tactical fix" → `/strategy-specialist`

**5. Monitor (no action needed)** — for findings that are stable or immaterial:
- "IS is stable — competitive pressure exists but isn't worsening"
- "KPI impact <2% — note but deprioritize"

---

## Producing the hypothesis list

After walking Layers 1-5, output an ordered list of hypotheses:

```
[
  {
    "id": "H1",
    "layer": "Business Economics",
    "name": "Efficiency exceeds target — IS recovery unviable at current economics",
    "evidence": ["BE1: [efficiency metric] vs target [target] — [X]x over", "BE2: implied floor fails threshold"],
    "confidence": "high",
    "blocks_downstream_actions": true,
    "verdict_implication": "fix_economics_first",
    "handoff": "/lp-auditor + /offer-auditor + /keyword-auditor (QS)"
  },
  {
    "id": "H2",
    "layer": "QS/Rank Diagnosis",
    "name": "PowerPoint keywords QS-constrained (QS 4-5, LP experience BELOW_AVERAGE)",
    "evidence": ["QS1: avg QS 4.3 on flagged PowerPoint keywords", "QS3: 80% have post_click_quality_score = BELOW_AVERAGE"],
    "confidence": "high",
    "blocks_downstream_actions": false,
    "verdict_implication": "compete_aggressively_after_qs_fix",
    "handoff": "/lp-auditor → /keyword-auditor"
  },
  ...
]
```

**Rank rules:**
1. Business Economics hypotheses always sort first (they gate everything below — if you can't afford to compete, tactical advice is premature).
2. Within a layer, rank by strategic impact (how much would this change the recommended action?).
3. A "fix economics first" hypothesis outranks any number of tactical findings — the downside of bidding higher when efficiency already exceeds the threshold is catastrophic.
4. Layer 1 (Data Validation) findings are caveats, not top-rank hypotheses — they qualify other findings rather than driving the action plan.

This hypothesis list is the spine of Phase 2's report.

---

## Explicit anti-patterns — never do these

- **"Increase bids to gain IS"** when campaign efficiency exceeds the target. The correct output: "Efficiency is already beyond target — gaining IS through bids would worsen returns. Fix conversion economics first."
- **"Fix rank"** without specifying whether rank loss is QS-driven or bid-driven. The correct output names the driver and routes accordingly.
- **Flat "Recommended Actions" table** that treats a QS audit and a bid increase at equal weight. The correct output segments by economic viability.
- **Routing to a skill** without explaining what the user should expect to learn. The correct output: "Check QS on the 14 flagged keywords — if QS is low, fixing it gains IS without increasing spend."
- **Ignoring business.md** when it contains unit economics, targets, and viability assessment. The competitive audit must connect IS findings to business reality.
- **Presenting lost conversions/value as pure opportunity cost** without noting that recovering them at current efficiency would cost [X] per conversion — which may exceed what the business can afford.
- **CPA-only language** when the account is ROAS-mode. Always use the correct KPI metric and direction for the account.
