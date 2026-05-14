# Ad Relevance Methodology (ported from retired ad-relevance-analyzer)

Use this reference when building or fixing RSAs for ad groups flagged in a `/quality-score-auditor` Ad Relevance handoff queue — or any time an ad group's AR status is Below Average.

Ad Relevance answers one question: **Does Google believe this ad meaningfully matches the user's intent for the keywords that trigger it?** This is a *structural* problem (keyword-to-ad-to-landing coherence), not a creative problem.

---

## The Headline Test (structural coherence check)

Run this BEFORE writing new headlines. The test decides whether the ad group can be rescued with copy, or whether it needs a structural split.

**Method:**

1. List the top 10 keywords in the ad group by impressions (use `context/google-ads/data/keywords.csv`).
2. Ask yourself:
   > *"Can I write ONE single headline that clearly addresses every keyword in this list without sounding generic?"*
3. **YES (pass):** proceed to Intent → Message Alignment, then compose headlines with the relevance methods below.
4. **NO (fail):** the ad group contains divergent intents. Recommend a structural split — do NOT just write more headlines. Route to `keyword-restructurer` (stub: `/keyword-optimizer`) with a proposed split.

**Example (FAIL):**

```
Ad Group: "CRM Software"
Keywords:
- crm software pricing        → wants cost
- what is crm software        → wants definition
- best crm for small business → wants comparison
- crm software free trial     → wants to try

→ FAIL: Cannot write one headline for definitions AND pricing AND comparisons.
→ Action: Split into "CRM - Pricing", "CRM - Compare", "CRM - Trial".
```

**Keyword-level Final URL exception:** If divergent-intent keywords already have keyword-level `ad_group_criterion.final_urls` overrides pointing to intent-matched LPs, a split may not be needed — DKI or ad customizers can route copy-level relevance without an AG split. Check the final_urls column before recommending structural work.

---

## Intent → Message Alignment

After the Headline Test passes, verify the dominant intent matches the ad copy tone.

| Intent | Query signals | Right ad tone |
|---|---|---|
| Informational | "what is", "how to", "guide", "tutorial" | Educational — usually NOT a good fit for a commercial ad group; consider routing to keyword-auditor D17 (pause/negative) |
| Commercial Investigation | "best", "vs", "reviews", "comparison" | Comparison-led: "Compare the Top 5", "Why {brand} Beats {rival}" |
| Transactional | "buy", "price", "discount", "free trial" | Action-led, offer-forward: pricing, guarantees, strong CTA |
| Navigational | brand terms, specific product names | Brand-dominant, confirm "you're in the right place" |

If the dominant intent doesn't match the current ad copy tone → rewrite headlines (Phase 3 of RSA composition), don't just add more.

---

## The 5-Second RSA Test (for Expected CTR)

When Expected CTR is Below Average (not Ad Relevance), the issue is usually competitiveness, not structural relevance. Apply the 5-Second Test to existing RSAs:

A stranger should answer these four questions within 5 seconds of seeing your ad:

1. **What do you sell?** (clarity)
2. **Why should I care?** (value)
3. **What do you want me to do?** (CTA)
4. **Why you vs. competitors?** (differentiation)

| Score | Verdict |
|---|---|
| 4/4 | PASS — ad is competitive |
| 2–3 | PARTIAL — specific element gaps, patch those |
| 0–1 | FAIL — major rewrite needed, likely offer weakness too |

If the ad fails 2+ questions repeatedly across the ad group, route to `/offer-maker` — the underlying offer is probably the root cause, not the copy.

---

## Three methods to bridge keyword → ad semantic gap

Use these when the Headline Test passes and you need to strengthen relevance at the copy layer.

### Method A — Controlled DKI / Ad Customizers

For high-volume, predictable keyword sets.

**Syntax:**
- DKI: `{KeyWord:Default Text}`
- Ad Customizers: `{CUSTOMIZER.headline_1:Default Text}`

**Rules:**
- Place in Headline 1 typically.
- Default text must be strong enough to stand alone.
- Never use generic fallbacks like "Our Products".

**Good:** `{KeyWord:Enterprise CRM}` — falls back to a meaningful phrase.
**Bad:** `{KeyWord:Our Products}` — generic fallback kills relevance when DKI can't fire.

### Method B — Static Anchoring

For sensitive, branded, or complex verticals where DKI risk is high.

Rule: the core semantic root of the keyword appears in Headline 1.

**Example:**
- Keyword: "enterprise crm software"
- ❌ H1: "Boost Your Sales Today" (generic)
- ✅ H1: "#1 Rated Enterprise CRM" (relevant)

### Method C — Semantic Distribution

Don't concentrate relevance signals in one headline. Google assembles RSAs dynamically; if only H1 is relevant, many ad combinations will feel generic.

Rule: spread keyword-theme tokens across multiple headlines (H1 + H3 + H5 minimum) so every shown combination retains at least one relevance anchor.

---

## Bold Text Optimization (description-level relevance)

Google automatically **bolds** description text that exactly matches the user's search query. Use this for a free relevance boost:

- Include the core keyword phrase naturally in at least one description.
- Don't stuff — one natural inclusion per description is enough.

**Example:**
- Keyword: "enterprise crm software"
- Description: "Our **enterprise CRM software** helps sales teams close 40% more deals."
- Result: the phrase bolds in the SERP, visual prominence increases.

---

## When to route out (not fix with copy)

| Signal | Route to |
|---|---|
| Headline Test FAIL (intent divergence) | `keyword-restructurer` (stub: `/keyword-optimizer`) — AG split |
| 5-Second Test FAIL with offer-weakness pattern | `/offer-maker` — fix the offer first |
| LP message-match failing (Below Avg LP per QS) | `/lp-auditor` → `/lp-optimizer` |
| COMPETITOR-class keywords with AR Below Avg | No fix — structural, don't waste copy iterations |
| INFORMATIONAL keywords in commercial AG | `/keyword-auditor` D17 — pause or add as negative |

---

## Validation

After applying these methods, monitor:

- AR label change from Below Avg → Avg+ takes 7–14 days.
- CTR uplift is the leading indicator; AR update lags.
- Re-run `/quality-score-auditor` after 14 days to confirm.
