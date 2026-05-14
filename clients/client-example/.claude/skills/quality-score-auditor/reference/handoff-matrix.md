# Quality Score Auditor — Handoff Matrix

**Purpose:** Map each hypothesis to the correct downstream optimizer. The QS auditor is **diagnose-only** — it never writes fixes itself.

**When to use:** Phase 3, after the hypothesis list is built. Only surface handoffs whose hypothesis survived the cascade.

---

## By hypothesis layer

### Creative — Ad Relevance (inner cascade Step 1)

| Hypothesis trigger | Handoff | Why |
|---|---|---|
| AR Below Avg, class ≠ COMPETITOR, Headline Test PASS, no customizers | `/rsa-maker` | Copy-level fix — improve keyword-to-ad semantic alignment via headline distribution, DKI, static anchoring |
| AR Below Avg, class ≠ COMPETITOR, `headline_test_mode = RELAXED_KW_LEVEL` (working keyword-level customizers) | `/rsa-maker` — framed as "review / expand customizer values" | The static headline template already uses `{CUSTOMIZER.<name>}` substitutions. AR Below Avg here reflects the customizer values themselves, not the static copy. Frame the fix as reviewing attribute values, not rewriting headlines. |
| AR Below Avg, class ≠ COMPETITOR, `integrity_status = BROKEN` (RSA references missing attribute) | No copy handoff — D17 surfaces the setup bug first | Google renders the `:default` fallback every time, so the AG's effective RSA pool is smaller than Google thinks. Advertiser must create the missing `customizer_attribute` (or remove the reference) and re-audit before AR fixes will stick. |
| AR Below Avg, class ≠ COMPETITOR, `integrity_status = EFFECTIVELY_STATIC` (attribute exists, no binding at any hierarchy level) | No copy handoff — D17 surfaces the setup gap first | The RSA references a customizer that has no KEYWORD / AD_GROUP / CAMPAIGN / CUSTOMER binding, so the `:default` fallback renders every time. Advertiser must add a binding at the appropriate level, or remove the reference and bake the intended value into the headline. |
| AR Below Avg, class ≠ COMPETITOR, Headline Test FAIL (intent divergence), AG weekly impressions ≥ `modernSearchMinWeeklyImpressions` | `keyword-restructurer` (pending — not yet built) | Structural split — separate ad groups for divergent intent themes. Until the skill exists, the auditor surfaces a structural-split brief in the report; no active handoff is invoked. |
| AR Below Avg, class ≠ COMPETITOR, Headline Test FAIL, AG weekly impressions **below** `modernSearchMinWeeklyImpressions` | `/rsa-maker` — framed as "tighter theme + add keyword-level customizers / DKI" | Do **not** recommend splitting — low-volume AGs lose Google AI learning signal if split further. Stay in one AG; use customizers (`ad_group_criterion_customizer`) or DKI (`{KeyWord:default}`) to achieve per-keyword relevance, combined with a tighter RSA theme that still covers the divergent intents. |
| AR Below Avg, class = COMPETITOR | No handoff — INFO only | AR Below Avg is structurally expected when targeting competitor brand terms |
| AR Below Avg, class = BRANDED | `/lp-auditor` FIRST, then `/rsa-maker` | Branded AR issues are almost always LP message-match or wrong URL |

### Creative — Expected CTR (inner cascade Step 2)

| Hypothesis trigger | Handoff | Why |
|---|---|---|
| ECTR Below Avg, AR = Average+ | `/offer-maker` + `/rsa-maker` | Competitiveness issue — stronger offer, CTA, differentiation |
| ECTR Below Avg, AR Below Avg on same keyword | **Blocked** — route AR first | ECTR problems on weak-relevance keywords are symptoms, not root cause |
| ECTR Below Avg, class = COMPETITOR | `/offer-maker` (LP-driven offer strength) | COMPETITOR keywords rely on offer + LP to drive ECTR, not AR |

### Creative — LP Experience (parallel to AR/ECTR)

| Hypothesis trigger | Handoff | Why |
|---|---|---|
| LP Below Avg, any class | `/lp-auditor` → `/lp-optimizer` | LP issues are independent of ad copy — run in parallel |
| LP Below Avg, class = BRANDED | `/lp-auditor` (escalated — message match / wrong URL / speed) | Branded LP low-QS is almost always a fix-first priority |
| LP Below Avg concentrated on one `final_url` | `/lp-auditor` scoped to that URL | Single-URL systemic issue — one fix resolves many keywords |

### Competitive / Traffic layer

| Hypothesis trigger | Handoff | Why |
|---|---|---|
| Lost IS Rank > 15% AND weighted QS < 6 (D15) | Route to Module 2 component optimizer for the campaign's dominant limiting component | QS is dragging rank — the QS fix recovers the traffic |
| CPC premium on QS<5 keywords (D16) | Same as D15 — route to Module 2 | Premium is the symptom; fix the component to remove it |

### Edge-case exits

| Scenario | Handoff | Why |
|---|---|---|
| PMax-only or no-enabled-Search-campaigns account | Exit early, no handoff | QS is a Search-campaign concept |
| Null QS > 30% of keywords | Report + "re-audit in 30 days" | Insufficient impressions for QS to stabilize |
| Account < 60 days old | M3 SKIPs; still produce M1/M2/M4 | Historical trends need ≥ 60 days |
| Changelog missing | M3-D13 SKIP + nudge to run `/gads-context` or `/account-changelog` | Post-optimization correlation requires changelog |
| INFORMATIONAL-classed keyword with low QS | `/keyword-auditor` D17 (pause / negative candidate) | Not a QS fix — pause/negate the keyword |
| COMPETITOR campaign AR Below Avg | No handoff — INFO | Structural, not fixable via AR methodology |

---

## Sequencing rule

When multiple hypotheses are active, the report sequences handoffs by:

1. **First** — branded-campaign escalations (small volume, high value)
2. **Then** — AR handoffs (inner cascade Step 1, blocks ECTR)
3. **Then** — LP handoffs (parallel, independent)
4. **Then** — ECTR handoffs (only if AR is Average+ on the target keywords)
5. **Then** — Competitive / Lost-IS-Rank routing (resolves via Module 2)

Never present handoffs as a flat menu. Frame them as a sequence with blocking relationships visible.

---

## Output-contract consumer discovery

Downstream optimizers (`/rsa-maker`, `/lp-optimizer`, `/offer-maker`) check for a fresh `context/analysis/quality-score-audit.md` at the top of their Phase 0 and read the relevant handoff queue section:

- `/rsa-maker` reads `## Handoff Queue — Ad Relevance`
- `/offer-maker` + `/rsa-maker` read `## Handoff Queue — Expected CTR`
- `/lp-optimizer` reads `## Handoff Queue — LP Experience`

Each queue is a table with `ad_group | campaign | keywords_below_avg | impressions | class | dominant_issue | recommended_action`. Downstream skills parse by header.

---

## What to tell the user in Phase 3

Template:

> **Top hypothesis: {layer} — {name}** (explains ~{pct}% of QS-related CPC premium)
>
> Before I hand off, here's what I'd run in order:
>
> 1. **{Branded escalation if present}** — `/lp-auditor` on branded keywords with QS < {brandLowQsCeiling}
> 2. **Ad Relevance fixes** — `/rsa-maker` for copy. AG splits where the Headline Test failed are surfaced as a pending `keyword-restructurer` handoff (skill not yet built; report carries a structural-split brief).
> 3. **LP fixes (parallel)** — `/lp-auditor` → `/lp-optimizer` for keywords with LP Below Avg
> 4. **After AR is Average+, Expected CTR** — `/offer-maker` + `/rsa-maker` on ECTR-Below-Avg keywords
>
> {N} COMPETITOR-class keywords have AR Below Avg — **do not run AR fixes on these**; it's structural.
> {M} INFORMATIONAL overlay keywords — route to `/keyword-auditor` for pause/negative decisions, not QS fixes.
>
> Which queue would you like to start with?
