# Quality Score Auditor — Synthesis Playbook (Phase 1.5)

**Purpose:** Raw flags are symptoms. This playbook forces Claude to walk a **two-cascade synthesis** before recommending any action:

1. **Outer cascade (whole-business):** does QS *matter* for this campaign's bidding mode, and has the keyword class been resolved?
2. **Inner cascade (creative layer):** AR → ECTR → LP ordering per the SOP chain.

Output is an in-memory **hypothesis list** that drives Phase 2's report and Phase 3's handoff queue.

**Core principle:** QS is calculated on exact-match impressions only. Irrelevant search terms triggered by broad/phrase match and advertiser-side conversion tracking do **not** feed the QS signal — they are not legitimate QS cascade layers. Route search-term waste to `/search-term-auditor`, not here.

---

## Phase 1.5.0 — Keyword classifier (runs first)

Every keyword in `qs-tiers.csv` carries a script-assigned `class`:

| Class | Source | Interpretation |
|---|---|---|
| `BRANDED` | Campaign name matches `config.searchTermAnalysis.brandedCampaigns` | QS should be ≥ 8. Low QS here is almost always tracking, wrong URL, or LP message-match — **escalate severity**. |
| `COMPETITOR` | Campaign name matches `config.qualityScoreAudit.competitorCampaigns` | AR will always be Below Avg (you're targeting a competitor's brand with your own ad). Do NOT recommend AR fixes. Focus on LP + offer-driven ECTR. **Severity = INFO for AR.** |
| `GENERIC` | Default | Standard cascade applies. |

INFORMATIONAL overlay (Claude semantic check, applied in Phase 1.5 before cascade):

- Claude reads each keyword text in `qs-tiers.csv` and flags research/education intent (language-agnostic: "how to", "what is", "guide", "tutorial", "vs", "comparison"). Low QS on informational keywords is **expected**, not a QS fix — route to `/keyword-auditor` D17 for a pause/negative decision. Flag these as `INFORMATIONAL` overlay.

---

## Phase 1.5.1 — Outer cascade: Business layer

### Step 1 — Does QS matter for this campaign's bidding mode?

Read `bidding_mode` on each flagged keyword:

| Bidding mode | QS impact | Severity handling |
|---|---|---|
| `MANUAL` (Manual CPC, Maximize Clicks) | QS directly scales CPC — every QS point below 7 costs materially more per click | **Keep severity as-is.** High-leverage fixes. |
| `SMART` (tCPA, tROAS, MaxConv, MaxConvValue) | QS still feeds Ad Rank + auction eligibility, but the algorithm compensates at the CPC layer | **Annotate severity `(impact dampened by Smart Bidding)`.** Never silence. |

### Step 2 — Does the keyword class change the interpretation?

| Class | AR Below Avg | ECTR Below Avg | LP Below Avg |
|---|---|---|---|
| `BRANDED` | **Escalate** — almost always structural | Medium | **Escalate** — likely the root cause |
| `COMPETITOR` | **INFO only — do not recommend fix** | Medium — focus here | Medium |
| `GENERIC` | Standard | Standard | Standard |
| `INFORMATIONAL` overlay | Route to `/keyword-auditor` D17 instead of QS fix |

---

## Phase 1.5.2 — Inner cascade: Creative layer (AR → ECTR → LP)

This preserves the SOP chain in `sops/Improve Quality Score.md`:

### Ad Relevance first

- **If AR = Below Avg AND class ≠ COMPETITOR:** route to `/rsa-maker` (copy). If the Headline Test fails, surface a pending `keyword-restructurer` finding instead — that skill isn't built yet, so the report carries a structural-split brief rather than an active handoff.
- **AR fixes block ECTR work** — if AR is Below Avg, any ECTR problem may be a symptom of relevance mismatch, not creative weakness. Do not recommend ECTR fixes on the same keyword until AR is Average+.

**Before writing an AR finding, investigate — don't label.**

When a keyword or ad group has AR Below Avg, look at the actual signals before framing the cause. At minimum check:

1. **Keyword-to-copy overlap** — read the headlines and descriptions in `qs-ads.csv` for the affected ad group. Does the keyword text (or a close semantic variant) appear literally in any headline? Is there a headline that clearly speaks to this keyword's intent?
2. **Ad group theming** — list the top-10 keywords by impressions in the AG. Are they a coherent cluster (one theme, one ad can cover them) or a mixed bag (multiple distinct intents)? This is the Headline Test, but stated outside a yes/no gate so it feeds the narrative.
3. **Customizers / DKI in play** — read `qs-customizers.csv` for this AG's `headline_test_mode` and `integrity_status`. If the RSA uses `{CUSTOMIZER.<name>}` (keyword-level or AG-level) or `{KeyWord:default}` substitutions, the "Below Avg" rating reflects the substituted text, not a bare headline. The fix is to review the customizer values or DKI defaults, not rewrite the static copy. If `integrity_status = BROKEN`, the referenced attribute doesn't exist and Google renders the `:default` every time — fix the attribute first, re-audit after.
4. **Number and age of RSAs** — one weak RSA is a different finding than 3+ RSAs all rating Below Avg. The latter points to a deeper theming or targeting issue, not a copy-rotation gap.
5. **AR trajectory** — was AR always Below Avg, or did it drop recently (from `qs-trends.csv`)? A recent drop often ties to an RSA rotation; a stable Below Avg points to structural mismatch.
6. **Class-specific framing** — BRANDED AR Below Avg almost always reflects LP/tracking, not copy. COMPETITOR AR Below Avg is structural (already excluded from the handoff queue). Don't write a copy-fix narrative for either.

Let the evidence dictate the finding. If the keyword isn't in any headline → say "no headline in this ad group mentions {keyword_theme}". If three RSAs all rate Below Avg → say "the ad group's ads collectively don't align with the keyword theme — this is a theming issue, not an RSA rewrite." If customizers are in play → say "the Below Avg rating reflects the customizer values, not static copy." **Do not default to** "the copy needs a rewrite" as a stock narrative.

Routing is unchanged — `/rsa-maker` for copy-level fixes, pending `keyword-restructurer` for structural splits. But the diagnosis must cite what the evidence actually shows.

### Expected CTR second

- **Only after AR = Average+ on the same keyword.** Route to `/offer-maker` + `/rsa-maker`.

**Before writing an ECTR finding, investigate — don't label.**

When a keyword or ad group has ECTR Below Avg, look at the actual signals before framing the cause. At minimum check:

1. **The RSA copy itself** (from `qs-ads.csv`) — read the headlines and descriptions. Are they generic? Do they contain an offer, a CTA, a differentiator? Are they keyword-relevant or boilerplate?
2. **Ad age and trajectory** — how long have these RSAs been running? Is ECTR flat-low (weak copy from day one) or declining from a higher starting point (possible fatigue)? Use `qs-trends.csv` to check.
3. **Trajectory vs the AR signal** — if AR is Average+ but ECTR is declining, the ads were once relevant-enough to click; something changed. If AR and ECTR are both Below Avg, ECTR is downstream of AR (already handled by the inner cascade).
4. **Competitor context** — if `context/competitor-ads/` exists from `/competitor-scraper`, read a few competitor ads targeting the same keywords. Does the client's offer stand out, blend in, or get beaten?

Let the evidence dictate the finding. If the headlines are bland and competitor copy is sharper → say so. If ads are 18 months old with a smooth CTR decline → fatigue is defensible. If AR is Average+ but the RSA has no CTA and no offer → call that out. **Do not default to a stock phrase** ("creative fatigue", "not compelling enough") that the evidence doesn't specifically support.

Routing is unchanged — `/offer-maker` + `/rsa-maker` either way. But the diagnosis the user reads must reflect what the evidence actually shows, not a plausible-sounding placeholder.

### LP Experience parallel

- **Independent of ad copy.** LP fixes can run in parallel with AR or ECTR work.
- Route to `/lp-auditor` → `/lp-optimizer`.
- Branded campaigns with LP Below Avg almost always have a message-match or wrong-URL issue — escalate.

### Headline Test

For each ad group with AR Below Avg on a non-COMPETITOR keyword, **first check the AG's customizer state** in `qs-customizers.csv` (column `headline_test_mode`), then apply the test:

| `headline_test_mode` | Interpretation | How to run the test |
|---|---|---|
| `STANDARD` | No customizers bound, or RSAs don't reference any | Ask the classic question: *"Can I write ONE headline that clearly addresses every top-10-by-impression keyword in this AG without sounding generic?"* |
| `AG_LEVEL_CONSTANT` | Only AG-level customizers bound — headline stays constant within the AG but renders a customizer value | Ask the standard question, but **note in the finding** that the AG uses AG-level customizers. If AR is still Below Avg, the customizer value itself may be the weak link — flag "review AG-level customizer values" alongside the copy recommendation. |
| `RELAXED_KW_LEVEL` | Keyword-level customizers are bound AND RSAs reference them — effective headline varies per keyword | **Relax the question:** *"Given the customizer substitutions per keyword, does each top-10 keyword get a headline that speaks to it?"* Don't conclude "intent divergence" just because the static headline is generic — that's the point of customizers. If AR is still Below Avg here, the fix is almost always to **review or expand the customizer attribute values**, not rewrite static headlines. |

Broken customizer setups (`integrity_status = BROKEN` in `qs-customizers.csv`) must be called out before the Headline Test runs — see QS-D17 in `diagnostic-rules.md`. An AG that references `{CUSTOMIZER.X}` with no attribute named `X` renders the `:default` fallback every time, so its "effective" headlines are fewer than Google sees.

- **Test PASSES (classic or relaxed):** no structural split needed → copy-level fix via `/rsa-maker`. If `RELAXED_KW_LEVEL`, frame the handoff as "review/expand customizer values" instead of "rewrite headlines".
- **Test FAILS:** intent divergence → apply the **weekly-impression volume gate** before recommending a split (see below).

### Volume gate — don't split low-volume ad groups

Modern Search structure best practice (see `sops/Modern Search Campaign & Ad Group Structure.md`): ad groups below ~300 weekly impressions starve Google's AI features (Smart Bidding, RSA asset selection) of learning signal. Splitting them produces two underpowered AGs instead of one that could learn.

Before emitting a structural-split recommendation, compute the AG's weekly impressions: sum `impressions` for the AG from `qs-tiers.csv` and divide by `(evaluation_period_days / 7)`. Compare against `config.qualityScoreAudit.thresholds.modernSearchMinWeeklyImpressions` (default 300).

| AG weekly impressions | Recommendation on Headline Test FAIL |
|---|---|
| ≥ threshold | Emit structural-split brief as normal (pending `keyword-restructurer`). |
| Below threshold | **Do NOT recommend splitting.** Emit a WARN finding instead: "This AG has {n} weekly impressions — below the {threshold} threshold for Modern Search. Splitting would starve both resulting AGs of learning signal. Recommend: (a) add keyword-level customizers via `ad_group_criterion_customizer` to make the RSA dynamically relevant per-keyword, (b) use DKI (`{KeyWord:default}`) in the RSA headline, and/or (c) tighten the AG's RSA themes to cover the divergent intents within one ad." Route to `/rsa-maker` with the tighter-theme framing. |
| Split would leave any resulting AG below threshold | Same WARN — splitting one healthy AG into two underpowered ones is net-negative. |

The volume gate applies only to **structural splits via keyword-restructurer**. Copy-level fixes via `/rsa-maker` are unaffected — they always run.

---

## Phase 1.5.3 — Anti-patterns (must never produce)

| Anti-pattern | Why it's wrong | Correct output |
|---|---|---|
| Flagging AR Below Avg on COMPETITOR keywords as FAIL | You're targeting a competitor's brand with your ad — structurally expected | INFO-only; route to LP + ECTR instead |
| Silencing QS findings on Smart Bidding accounts | QS still drives auction eligibility; algorithm only compensates CPC | Keep findings, annotate severity with `(dampened)` note |
| Treating brand-campaign low-QS as standard | Almost always LP or tracking, not ad copy | Escalate severity; route to `/lp-auditor` first |
| Routing low QS to `/search-term-auditor` on broad/phrase waste | QS is exact-match-based; search-term cleanup is a CPA/waste fix, not a QS fix | Do not route |
| Writing ECTR fixes while AR is Below Avg on the same keyword | AR issues cause ECTR problems; ECTR fix won't hold | Block ECTR handoff, route AR first |
| Mixing INFORMATIONAL keywords into the handoff queue | These are `/keyword-auditor` D17 candidates (pause/negative), not QS fixes | Surface as overlay, route to `/keyword-auditor` |

---

## Phase 1.5.4 — Producing the hypothesis list

After running the classifier, outer cascade, and inner cascade, emit an ordered hypothesis list:

```
[
  {
    "id": "H1",
    "layer": "Creative — Ad Relevance",
    "name": "Systemic AR Below Avg in non-brand campaigns",
    "evidence": [
      "QS-D07: 32% of non-COMPETITOR keywords with non-null AR are Below Avg",
      "QS-D10: AR is the dominant limiting component (57% of Below-Avg ratings)"
    ],
    "confidence": "high",
    "blocks_downstream_actions": false,
    "handoff": "/rsa-maker (copy) and keyword-restructurer (structural)",
    "explains_waste_pct": "~60% of QS-related CPC premium"
  },
  {
    "id": "H2",
    "layer": "Creative — LP",
    "name": "Branded-campaign LP message-match gap",
    "evidence": [
      "QS-D09: 4 branded keywords with LP Below Avg, QS 5",
      "BRAND_LOW_QS flag active"
    ],
    "confidence": "high",
    "blocks_downstream_actions": false,
    "handoff": "/lp-auditor → /lp-optimizer",
    "explains_waste_pct": "~8% (small volume but high-value brand traffic)"
  },
  ...
]
```

**Rank rules:**

1. Branded-campaign findings sort first within their layer (downside of ignoring is largest).
2. Within a layer, rank by `explains_waste_pct` descending.
3. AR hypotheses outrank ECTR hypotheses when both are present in the same campaign (inner cascade).
4. LP hypotheses run in parallel — do not block other layers.
5. COMPETITOR-class AR findings never appear in the hypothesis list (INFO-only).
