# Ecommerce Page Quality Checklist

Binary pass/fail validation checklist for Dedicated Ecommerce LPs and Product Pages. Run after HTML generation, before handoff.

---

## How to Use

1. Select the page type section that applies
2. Run the Cross-page checks for every audit
3. Count passing and failing items per category
4. Fix any failing items before handoff

### Wireframe Adaptations

Skip these items (not applicable to wireframes):
- "Page loads in under 3 seconds on mobile"
- "Conversion tracking fires correctly"
- "Form/checkout submits correctly"
- "Express pay buttons are functional"

Check everything else: layout, section order, copy quality, CTA placement, brand colors, responsiveness.

### Scoring

| Score | Rating |
|-------|--------|
| 90-100% | Excellent — ready for client review |
| 75-89% | Good — minor fixes needed |
| 60-74% | Fair — several items need attention |
| Below 60% | Needs work — significant gaps |

---

## Cross-Page Checks (All Page Types)

### Performance and Mobile (5 items)

- [ ] All pages are fully responsive: no horizontal scrolling, no cut-off content on mobile
- [ ] Touch targets (buttons, links) are minimum 44x44px with adequate spacing
- [ ] Images use placeholder pattern with descriptive text and recommended dimensions
- [ ] No intrusive elements block content on mobile
- [ ] CTA buttons go full-width on mobile (< 768px)

### Trust and Policy Consistency (4 items)

- [ ] Return/refund policy wording is consistent across all sections where it appears
- [ ] Shipping information is consistent across all mentions
- [ ] Trust badges (security, payment, guarantee) appear near CTAs
- [ ] Brand colors are applied consistently via CSS variables

---

## Dedicated Ecommerce LP Checks

### Structure (6 items)

- [ ] No site navigation: no header nav, no footer links, no exits except the CTA
- [ ] Page follows Ecommerce Persuasion Sequence order: Product Showcase → Customer Evidence → Product Benefits → The Details → Purchase Confidence → Act Now → Complete Your Purchase
- [ ] Product image/video is the hero visual (not a headline-first layout, not a generic brand image)
- [ ] Price is visible above the fold (in Product Showcase section)
- [ ] Key differentiator tagline is present (under 10 words)
- [ ] Sections alternate backgrounds for visual separation

### Customer Evidence (4 items)

- [ ] Aggregate rating is present ("4.8/5 from 1,200+ reviews" or similar)
- [ ] Curated reviews include specific results, not generic praise
- [ ] Customer photo/UGC placeholders are present
- [ ] Reviews are marked as placeholders: "[Replace with real customer review]"

### Product Benefits (4 items)

- [ ] Benefits are translated from features to outcomes (what the visitor experiences)
- [ ] 3-5 benefit blocks are present with supporting descriptions
- [ ] Benefits tie back to customer evidence where possible
- [ ] Lifestyle/product imagery placeholders accompany each benefit

### The Details (3 items)

- [ ] Specifications are presented in a scannable table format
- [ ] "What's in the box" or included items are listed
- [ ] Comparison or how-it-works section is present (if applicable to the product)

### Purchase Confidence (5 items)

- [ ] Return policy is stated with specific window, conditions, and process
- [ ] Shipping details include cost (or free) and estimated delivery timeline
- [ ] Size/fit guidance is present for sized products (apparel, footwear, accessories)
- [ ] FAQ section addresses 5-7 product-specific and transactional questions
- [ ] Guarantee statement is bold and specific ("60-day free returns. No questions asked.")

### Act Now / Urgency (4 items)

- [ ] If urgency section is present: urgency is tied to a real constraint (stock, deadline, shipping cutoff)
- [ ] No fake countdown timers or manufactured scarcity
- [ ] Urgency element includes a specific deadline or quantity placeholder: "[Replace with real deadline]"
- [ ] If no urgency exists: section is skipped entirely (not faked)

### Complete Your Purchase (5 items)

- [ ] Value recap summarizes product, key benefits, and what's included
- [ ] Price display is repeated with savings visible
- [ ] Primary CTA is prominent with highest-contrast styling
- [ ] Express checkout buttons are mentioned/placeholdered (Apple Pay, Google Pay, Shop Pay)
- [ ] Guarantee reminder microcopy appears beneath or near the final CTA

### CTA Placement (4 items)

- [ ] Minimum 4 CTAs on the page
- [ ] CTA appears in Product Showcase (hero) section
- [ ] CTA appears after Customer Evidence section
- [ ] CTA appears in Complete Your Purchase (final) section

### Copy Quality (5 items)

- [ ] Visitor-first language throughout ("You" not "We", outcomes not features)
- [ ] Specific numbers and results used where available (not vague claims)
- [ ] First-person CTA text ("Get mine" not "Get yours")
- [ ] No hedging language ("might", "could", "possibly")
- [ ] Active voice throughout

### One-Page-One-Goal (4 items)

- [ ] No competing offers, products, or CTAs on the page
- [ ] No outbound links except the purchase CTA
- [ ] No navigation menu or footer links
- [ ] Every section serves the single goal of driving the purchase

### Brand & Message Match (4 items)

- [ ] Brand colors are applied to CSS variables (primary, accent, text, background)
- [ ] Brand fonts are applied (heading and body)
- [ ] Hero headline matches the ad copy that will drive traffic to this page
- [ ] Brand voice and tone match the brand.md context

---

## Product Page Checks

### Product Identity (6 items)

- [ ] Image gallery has minimum 5 image placeholders: hero, angles, lifestyle, detail, scale reference
- [ ] Gallery placeholder descriptions are specific ("Product hero shot on white background — 800x800px")
- [ ] Gallery is described as updating with variant selection
- [ ] Product title is descriptive with key attributes (not an internal SKU name)
- [ ] Star rating and review count are visible near the product title
- [ ] Variant selectors (size, color) are present with clear labels

### Offer Stack (5 items)

- [ ] Price is prominent and placed near the add-to-cart button
- [ ] If discounted: original price (strikethrough), new price, and savings are all shown
- [ ] Shipping information is visible near the CTA
- [ ] Return/guarantee policy is summarized near the CTA
- [ ] Stock availability indicator is present ("In stock", "Ships within 24h", or "Only X left")

### Add-to-Cart Action (5 items)

- [ ] Add-to-cart button is the most visually prominent element on the page
- [ ] Quantity selector is present
- [ ] Express pay options (Apple Pay, Google Pay, Shop Pay) are below the main CTA
- [ ] Clear feedback described after adding to cart (button state change)
- [ ] Sticky CTA bar described for mobile (fixed bottom bar when scrolling past main CTA)

### Social Proof (4 items)

- [ ] Customer reviews section is present with star ratings and verified buyer badges
- [ ] Review sorting/filtering is described (most helpful, most recent, by star, photos only)
- [ ] Customer photo placeholders from verified buyers are included
- [ ] Reviews are marked as placeholders: "[Replace with real customer review]"

### Product Details (4 items)

- [ ] Product description leads with benefits, not just features/specs
- [ ] Technical specifications are in a scannable table format
- [ ] FAQ section addresses product-specific questions (5-7 items)
- [ ] Content sections are described as expandable/collapsible on mobile

### Cross-sell and Trust (4 items)

- [ ] "Frequently bought together" or "Complete the set" section is present
- [ ] Related/recommended products section shows 4-6 alternatives (placeholders)
- [ ] Trust reinforcement includes: return policy (expanded), secure checkout badge, contact option
- [ ] Certification badges are placeholdered if applicable

### Brand & Message Match (4 items)

- [ ] Brand colors are applied to CSS variables (primary, accent, text, background)
- [ ] Brand fonts are applied (heading and body)
- [ ] Product title matches how visitors would search for this product
- [ ] Brand voice and tone match the brand.md context

---

## Validation Results Template

```markdown
## Quality Validation Results

**Page Type:** {Dedicated LP / Product Page}

| Category | Pass | Fail | Score |
|----------|------|------|-------|
| Cross-page: Performance & Mobile | X/5 | Y/5 | Z% |
| Cross-page: Trust & Policy | X/4 | Y/4 | Z% |
| {Page-type specific categories...} | | | |
| **Total** | **X/N** | **Y/N** | **Z%** |

### Action Items
1. {failing item} → {how to fix}
2. ...
```
