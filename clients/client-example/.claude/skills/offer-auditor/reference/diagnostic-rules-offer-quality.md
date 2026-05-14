# Diagnostic Rules — Offer Quality (D01-D16)

Read during Phase 2 when running `/offer-auditor`.

## Module Scoring

| ID | Diagnostic | Severity | Pts | Module |
|----|-----------|----------|-----|--------|
| D01 | Value proposition clarity | Critical | 10 | Value |
| D02 | Dream outcome specificity | High | 10 | Value |
| D03 | Perceived value vs. price gap | Critical | 10 | Value |
| D04 | Uniqueness/comparison resistance | High | 10 | Value |
| D05 | Unique mechanism | High | 10 | Value |
| D06 | Value stacking depth | Medium | 5 | Value |
| D07 | Urgency element presence | Medium | 5 | Urgency |
| D08 | Urgency authenticity | Medium | 5 | Urgency |
| D09 | Risk removal presence | Critical | 10 | Trust |
| D10 | Risk removal strength | High | 10 | Trust |
| D11 | Social proof presence | High | 10 | Trust |
| D12 | Social proof specificity | Medium | 5 | Trust |
| D13 | Credibility signals | Medium | 5 | Trust |
| D14 | Audience specificity | High | 10 | Positioning |
| D15 | Offer Audit Checklist score | High | 10 | Positioning |
| D16 | Competitor offer comparison | Medium | 5 | Positioning |

**Max score (all modules):** 120 points

---

## Evaluation Method

Unlike strategy-specialist diagnostics which use numeric thresholds, offer quality diagnostics are **qualitative assessments**. Evaluate based on the presence, specificity, and strength of each element.

**General evaluation principles:**
- **Specific > vague**: "4.8/5 on 800+ reviews" passes; "highly rated" does not
- **Quantified > generic**: "Save 10 hours/week" passes; "saves time" does not
- **Customer language > corporate speak**: "Stop wasting ad spend" passes; "optimize marketing ROI" is weaker
- **Unique > copyable**: Only you can claim it = strong; any competitor could say it = weak

---

## D01: Value Proposition Clarity
**Severity:** Critical (10 pts)
**Module:** Value
**Data:** business.md (offer/value prop sections) + brand.md (Summary, Products & Services)

**Check:** Is there a clear, specific statement of what the customer gets?

**PASS:** One-sentence value prop is present. It names the customer, the outcome, and how. Not generic. A stranger could understand it in 5 seconds.
**WARN:** Value prop is present but vague, feature-focused ("we use AI"), or could apply to any competitor in the space.
**FAIL:** No value prop found, or it's a company description rather than a customer-facing promise.
**ASK:** Insufficient data in business.md/brand.md to evaluate. Ask: "Can you summarize in one sentence what your customer gets and why it matters to them?"

**Details to report:** The value prop found (or absence), and whether it's specific or generic.

---

## D02: Dream Outcome Specificity
**Severity:** High (10 pts)
**Module:** Value
**Data:** business.md (offer sections) + brand.md (Summary, Pain Points)

**Check:** Is the customer's desired outcome described in concrete, measurable terms?

**PASS:** Outcome is specific and measurable. Examples: "Professional headshots in 2 hours", "Reduce CPA by 40%", "Setup in 2 minutes". The customer can picture the result.
**WARN:** Outcome is mentioned but not quantified or concrete. "Better results", "improved efficiency", "peace of mind".
**FAIL:** No clear outcome described. Only features listed, no transformation articulated.
**ASK:** No outcome language found. Ask: "What specific, measurable result does your customer achieve? Think time saved, money earned, problem eliminated."

**Details to report:** The outcome statement and whether it's measurable.

---

## D03: Perceived Value vs. Price Gap
**Severity:** Critical (10 pts)
**Module:** Value
**Data:** brand.md (Pricing) + business.md (offer details)

**Check:** Does the perceived value significantly exceed the price/effort required?

**PASS:** Multiple value amplifiers present: stacked bonuses, bundled services, "valued at X" framing, or price anchoring against alternatives. The customer would feel they're getting a deal.
**WARN:** Price is documented but no value amplification. No comparison to alternatives, no stacking, no anchoring. The value-to-price gap is unclear.
**FAIL:** Price appears high relative to stated value, or no pricing context exists to evaluate. Offer seems to compete primarily on price.
**ASK:** Pricing not documented. Ask: "What is your pricing, and how does the customer perceive the value relative to what they pay?"

**Vertical-specific notes:**
- **Ecommerce:** Check for bundling, threshold incentives, comparison to retail. "Was $X, now $Y" is basic but sufficient.
- **SaaS:** Free tier or trial is strong. Check time-to-value claims. "Free forever" > "free trial" > "contact sales".
- **Lead Gen:** The lead magnet itself needs perceived value. "Free consultation" is weak. "Free audit valued at $X" is stronger.

**Details to report:** Price point, value amplifiers present (or absent), gap assessment.

---

## D04: Uniqueness/Comparison Resistance
**Severity:** High (10 pts)
**Module:** Value
**Data:** brand.md (Unique Selling Propositions) + business.md (Competitive Strategy)

**Check:** Is the offer difficult to directly compare with competitors?

**PASS:** Offer has structural uniqueness — proprietary bundle, unique methodology, category-defining positioning, or niche specialization that prevents apples-to-apples comparison.
**WARN:** Some differentiation exists but competitors could make similar claims. Differentiation is in degree ("faster", "better") rather than kind.
**FAIL:** Offer is functionally identical to competitors. Customer would compare purely on price. No structural barriers to comparison.
**ASK:** USPs not documented. Ask: "If a customer compared your offer side-by-side with your top 3 competitors, what would they see that's genuinely different — not just better, but different?"

**Details to report:** USPs found, whether they're defensible, whether competitors could claim the same.

---

## D05: Unique Mechanism
**Severity:** High (10 pts)
**Module:** Value
**Data:** brand.md (Products & Services, USPs) + business.md (offer details)

**Check:** Is there a proprietary process, method, or technology that differentiates the offer?

**PASS:** Named or described unique mechanism. Examples: "AI-powered matching algorithm", "The 5-Step Growth Framework", proprietary technology, patented method. Gives the "how" a name.
**WARN:** Process exists but isn't named or distinctly positioned. "We use machine learning" (everyone does). The mechanism exists but isn't leveraged for differentiation.
**FAIL:** No unique mechanism described. The "how" is generic or unexplained.
**ASK:** No process/method information found. Ask: "Do you have a proprietary process, methodology, or technology? Something you'd give a name to — like 'The [Your] Method'?"

**Details to report:** Mechanism described (or absent), whether it's named, whether competitors have something similar.

---

## D06: Value Stacking Depth
**Severity:** Medium (5 pts)
**Module:** Value
**Data:** brand.md (Products & Services) + business.md (offer details)

**Check:** Are there multiple bonuses, additions, or bundled elements that increase perceived value?

**PASS:** 3+ stacked value elements beyond the core offer. Examples: free shipping + bonus guide + templates + priority support. Each element is specific and named.
**WARN:** 1-2 additional elements present, but stacking is minimal. "Includes support" is too vague. Some specificity needed.
**FAIL:** No value stacking. The offer is just the core product/service with nothing added. Easy to price-compare.
**ASK:** Cannot determine what's included. Ask: "Beyond the core product/service, what else does the customer get? Think bonuses, templates, support, extras."

**Details to report:** Number of stacked elements, what they are, specificity level.

---

## D07: Urgency Element Presence
**Severity:** Medium (5 pts)
**Module:** Urgency
**Data:** brand.md (Offers/Promotions) + business.md (offer details)

**Check:** Is there a genuine time or quantity constraint that creates a reason to act now?

**PASS:** Clear urgency element present: limited-time offer, seasonal deadline, capacity limit, price increase date, limited inventory (real).
**WARN:** Soft urgency exists but is implicit. "Book now" without a clear deadline. "Limited availability" without specifics.
**FAIL:** No urgency element. Customer has no reason to act today vs. next week.
**ASK:** No urgency information found. Ask: "Is there a genuine reason for customers to act now? A deadline, limited spots, price change, or seasonal factor?"

**Details to report:** Urgency element described (or absent), whether it has a specific deadline/limit.

---

## D08: Urgency Authenticity
**Severity:** Medium (5 pts)
**Module:** Urgency
**Data:** Same as D07

**Check:** If urgency exists, is it real and not manufactured?

**PASS:** Urgency is verifiably authentic. Real capacity limits, real seasonal deadlines, genuine inventory constraints, documented price increase dates.
**WARN:** Urgency plausible but unverifiable. "Limited spots" without specific numbers. Evergreen "sale" that never ends.
**FAIL:** Urgency appears manufactured. Fake countdown timers, perpetual "limited time" offers, artificial scarcity.
**SKIP:** No urgency element (D07 = FAIL). Cannot evaluate authenticity of something that doesn't exist.

**Details to report:** Assessment of urgency authenticity, supporting evidence.

---

## D09: Risk Removal Presence
**Severity:** Critical (10 pts)
**Module:** Trust
**Data:** brand.md (Guarantees/Promises) + business.md (offer details)

**Check:** Is there a guarantee, risk reversal, or commitment reducer offered?

**PASS:** Clear risk removal present: money-back guarantee, free trial, no-credit-card signup, satisfaction guarantee, free returns, "no obligation" promise.
**WARN:** Weak risk removal. Standard return policy without emphasis. "Contact us for refund" (friction). Industry-standard terms with no differentiation.
**FAIL:** No risk removal found. Customer bears all the risk. No trial, no guarantee, no easy exit.
**ASK:** No guarantee/trial information found. Ask: "What happens if the customer isn't satisfied? Is there a guarantee, trial period, refund policy, or cancellation process?"

**Details to report:** Risk removal mechanism (or absence), strength vs. industry standard.

---

## D10: Risk Removal Strength
**Severity:** High (10 pts)
**Module:** Trust
**Data:** Same as D09

**Check:** Is the guarantee specific with clear terms (duration, process, conditions)?

**PASS:** Guarantee is specific and strong: named duration ("90-day money-back"), clear process ("no questions asked"), and low friction ("free return shipping"). Terms remove ambiguity.
**WARN:** Guarantee exists but is vague. "Satisfaction guaranteed" without terms. "Returns accepted" without duration or process. Customer can't be sure what happens.
**FAIL:** Guarantee is restrictive, conditional, or buried. "Subject to terms", restocking fees, approval required. This adds friction rather than removing risk.
**SKIP:** No risk removal present (D09 = FAIL). Cannot evaluate strength of something absent.

**Details to report:** Guarantee terms, specificity, friction level, comparison to competitors if known.

---

## D11: Social Proof Presence
**Severity:** High (10 pts)
**Module:** Trust
**Data:** brand.md (Trust Signals) + business.md (social proof sections)

**Check:** Are there testimonials, reviews, case studies, or usage metrics supporting the offer?

**PASS:** Multiple types of social proof present: customer count + ratings + testimonials, or case studies + named clients + usage metrics.
**WARN:** Some social proof exists but limited to one type. Only a rating score, or only "trusted by X companies" without specifics.
**FAIL:** No social proof found. No reviews, no testimonials, no customer counts, no case studies.
**ASK:** Cannot determine social proof status. Ask: "What social proof do you have? Think: review scores, customer count, testimonials, case studies, named clients, awards."

**Details to report:** Types of social proof found, volume, specificity.

---

## D12: Social Proof Specificity
**Severity:** Medium (5 pts)
**Module:** Trust
**Data:** Same as D11

**Check:** Does the proof include names, photos, specific results, and verifiable details?

**PASS:** Proof is specific and verifiable. Named individuals with photos, specific results ("grew revenue 40% in 3 months"), star ratings with review counts ("4.8/5 on 800+ reviews"), named client logos.
**WARN:** Proof exists but is generic. "Hundreds of happy customers", anonymous testimonials, results without context.
**FAIL:** Proof is vague or unverifiable. "Trusted by thousands", no named sources, no specific outcomes.
**SKIP:** No social proof present (D11 = FAIL).

**Details to report:** Specificity assessment, examples of what's present, what's missing.

---

## D13: Credibility Signals
**Severity:** Medium (5 pts)
**Module:** Trust
**Data:** brand.md (Trust Signals, Company Overview) + business.md

**Check:** Are there certifications, awards, media mentions, or institutional credibility markers?

**PASS:** 2+ credibility signals present. Examples: industry certifications, awards, media mentions, partnerships, years in business, team credentials. Signals are relevant to the customer's concern.
**WARN:** 1 credibility signal or signals that are tangential. "Established in 2015" is weak alone. Certifications that customers don't recognize.
**FAIL:** No credibility signals found. Nothing beyond the product itself supports trustworthiness.
**ASK:** Cannot determine credibility. Ask: "Do you have certifications, awards, media features, notable partnerships, or team credentials that customers would find reassuring?"

**Details to report:** Credibility signals found, relevance to customer concerns.

---

## D14: Audience Specificity
**Severity:** High (10 pts)
**Module:** Positioning
**Data:** business.md (Target Audience) + brand.md (Target Audience)

**Check:** Does the offer clearly target a defined segment rather than "everyone"?

**PASS:** Audience is specific and named. "B2B SaaS companies with 10-200 employees", "Remote teams managing distributed projects", "Homeowners in [region] planning kitchen renovations". The offer speaks to this audience specifically.
**WARN:** Audience is described but broad. "Small businesses", "professionals", "homeowners". Some targeting but not specific enough to tailor messaging.
**FAIL:** No audience definition, or the offer tries to serve everyone. "Anyone who needs [product]".
**ASK:** Audience not documented. Ask: "Who is this offer specifically for? Describe your ideal customer — industry, size, role, situation."

**Details to report:** Audience definition, specificity level, whether the offer speaks to this segment.

---

## D15: Offer Audit Checklist Score
**Severity:** High (10 pts)
**Module:** Positioning
**Data:** All data from D01-D14 + `reference/offer-audit-checklist.md`

**Check:** Run the 15-item Offer Audit Checklist against available data. This is a composite diagnostic.

**How to evaluate:** Read `reference/offer-audit-checklist.md`. For each of the 15 checklist items, assess whether the item passes based on all available data (business.md, brand.md, and answers collected during this audit). Count the passing items.

**PASS:** 12+ of 15 items pass. Strong offer foundation. Ready for angle extraction and RSA composition.
**WARN:** 8-11 items pass. Gaps to address. Flag specific missing items.
**FAIL:** <8 items pass. Significant offer work needed before advertising at scale.

**Details to report:** Score (X/15), which items passed, which failed, specific gaps.

---

## D16: Competitor Offer Comparison
**Severity:** Medium (5 pts)
**Module:** Positioning
**Data:** `context/competitor-ads/*.csv` + business.md + brand.md

**Check:** Has the offer been assessed against top competitor offers?

**PASS:** Competitor offer data exists AND the offer has clear advantages on at least 2 of 4 pillars (Value, Uniqueness, Urgency, Trust) vs. competitors.
**WARN:** Competitor data exists but advantages are unclear or only on 1 pillar. Or: no formal comparison done but some competitive awareness exists in business.md.
**FAIL:** No competitor offer data available and no competitive positioning documented.
**ASK:** No competitor data found. Suggest: "Run `/competitor-scraper [domain]` to pull competitor ad copy, then re-run this diagnostic."

**How to evaluate (when competitor data exists):**
1. Read competitor ad CSVs
2. Extract competitor offer elements (value props, guarantees, pricing, proof)
3. Compare across 4 pillars: Value, Uniqueness, Urgency, Trust
4. Assess whether our offer wins, ties, or loses on each pillar

**Details to report:** Number of competitors assessed, pillar comparison results, key advantages/disadvantages.
