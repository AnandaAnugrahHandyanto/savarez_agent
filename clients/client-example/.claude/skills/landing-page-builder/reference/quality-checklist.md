# Quality Checklist Reference

Agent-readable checklist for validating generated landing page wireframes. Adapted from the LP Quality Checklist for wireframe context (skips PageSpeed, tracking, live-only checks; focuses on layout, copy, CTA, and structure).

---

## When to Use

Run this checklist after generating the HTML wireframe in Phase 6 of the Landing Page Builder skill. Check the generated file against all applicable categories below.

---

## 1. Offer Completeness

- [ ] Core value proposition is stated in one clear sentence
- [ ] Unique selling points are explicitly stated on the page
- [ ] Value boosters are present (bonuses, extras, bundles)
- [ ] Social proof is present (or placeholder marked)
- [ ] Risk removal element exists (guarantee, free trial, return policy)
- [ ] All five Irresistible Offer components are represented

---

## 2. Hero Section

- [ ] Primary headline is under 10 words
- [ ] Headline communicates the core outcome, not a feature
- [ ] Sub-headline adds specificity without repeating the headline
- [ ] A stranger can understand the value proposition within 5 seconds
- [ ] Visual placeholder is present and descriptive (e.g., "[Product Screenshot]")
- [ ] Primary CTA is visible in the hero section
- [ ] CTA button text is benefit-driven and first-person
- [ ] CTA button has contrasting color against the background

---

## 3. Benefits Section

- [ ] Benefits focus on outcomes, not features
- [ ] At least two of three angles covered (functional, business, personal)
- [ ] "So what?" test passed: each benefit answers why the visitor should care
- [ ] No jargon: a non-expert can understand every benefit

---

## 4. Trust/Authority Section

- [ ] At least one trust element is present (or placeholder marked)
- [ ] Trust claims are specific and verifiable, not vague
- [ ] Trust type matches the vertical (institutional for regulated, expertise for services)
- [ ] Trust section appears before social proof section in page order

---

## 5. Social Proof Section

- [ ] At least one form of social proof is present (or placeholder marked)
- [ ] Testimonial placeholders include guidance: "[Replace with: full name, photo, company, specific result]"
- [ ] Social proof is specific with results, not generic
- [ ] Proof matches the target visitor segment

---

## 6. Objection Handling

- [ ] Top 3 visitor objections are identified and addressed
- [ ] FAQ section covers key concerns (pricing, implementation, timing, trust)
- [ ] Guarantee is specific (duration, process, conditions)
- [ ] Guarantee is placed near a conversion point

---

## 7. Urgency/Scarcity (if included)

- [ ] Urgency or scarcity is legitimate (placeholders note "replace with real deadline")
- [ ] Specific numbers and dates are used (not "limited time" or "act now")
- [ ] Reason for limitation is explained or placeholder provided
- [ ] Urgency appears after value and trust are established (correct page position)

---

## 8. Call to Action

- [ ] Primary CTA is repeated at least 3 times throughout the page
- [ ] CTA placement follows hierarchy: hero, after proof, after objections, final section
- [ ] CTA button text is consistent across placements (same action, same language)
- [ ] Microcopy near CTA reinforces the decision (risk removal, social proof, or urgency)
- [ ] Secondary CTA (if used) is clearly subordinate to primary

---

## 9. Copy Quality

- [ ] Active voice throughout ("Get your assessment" not "An assessment can be requested")
- [ ] No hedging language ("Do X" not "You might want to consider X")
- [ ] Visitor-first language (focuses on their reality, not your company)
- [ ] Specific numbers and results where possible
- [ ] No jargon or corporate speak

---

## 10. One-Page-One-Goal Rule

- [ ] No navigation bar (or only anchor links to same-page sections)
- [ ] No footer links (except legal placeholder if needed)
- [ ] No social media icons
- [ ] No competing offers or CTAs that lead away from primary goal
- [ ] Every element either drives conversion or is a placeholder with clear purpose

---

## 11. Visual & Layout (Wireframe-Specific)

- [ ] Sections follow the 7-section hierarchy order
- [ ] Each section has visual separation (alternating backgrounds or spacing)
- [ ] CTA buttons are visually distinct (contrasting color, sufficient size)
- [ ] Image placeholders are descriptive with "[Replace with...]" instructions
- [ ] Layout is responsive: single column below 768px
- [ ] CTAs go full-width on mobile viewport
- [ ] Sufficient white space between sections
- [ ] Brand colors are applied via CSS variables (`:root` block present)
- [ ] Font family matches brand (or sensible fallback)

---

## 12. Brand & Message Match

- [ ] Brand colors are correctly applied (primary, secondary, accent/CTA)
- [ ] Tone matches brand voice from `context/brand.md`
- [ ] Copy uses phrases from `context/offer-angles.md` where appropriate
- [ ] If keywords available: headline contains primary keyword or close variant
- [ ] Offer on page matches what would be promised in ads

---

## Scoring

Count passing items across all applicable categories:

| Score | Rating | Action |
|-------|--------|--------|
| 90-100% | Excellent | Ready for client review |
| 75-89% | Good | Minor fixes needed before sharing |
| 60-74% | Fair | Address failing items before client review |
| Below 60% | Needs Work | Significant revision required |

---

## Result Format

Present as a table:

```markdown
## Quality Validation Results

| Category | Pass | Fail | Score |
|----------|------|------|-------|
| Offer Completeness | X/6 | Y/6 | Z% |
| Hero Section | X/8 | Y/8 | Z% |
| ... | ... | ... | ... |
| **Total** | **X/N** | **Y/N** | **Z%** |

### Action Items
1. [Specific item that failed] → [How to fix]
2. ...
```
