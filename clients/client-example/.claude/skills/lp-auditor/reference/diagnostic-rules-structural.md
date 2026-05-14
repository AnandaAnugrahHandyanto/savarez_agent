# LP Auditor — Structural Diagnostics (LP-D01–D12)

Data source: Chrome DevTools (page content + screenshot)

Reference: `sops/LP Hierarchy Mental Model.md`, `sops/LP Quality Checklist.md`, `sops/Conversion Amplifier Mental Model.md`

---

## LP-D01: Offer Section Completeness
**Severity:** High (10 pts) | **Data:** Chrome DevTools DOM extraction

**Rule:** A converting LP needs all 5 Irresistible Offer components present. Missing any component creates a conversion leak.

**How to check:**
1. Extract full page content via Chrome DevTools
2. Check for the 5 components:
   - **Value proposition:** H1/hero headline communicating core outcome
   - **USPs:** Benefits section with differentiated selling points
   - **Value boosters:** Features, stats, bonuses, extras
   - **Social proof:** Testimonials, reviews, logos, case studies
   - **Risk removal:** Guarantee, free trial, return policy, FAQ
3. Score by count of components present

**Pass/Fail:**
- PASS: All 5 components present (5/5)
- WARN: 3-4 components present (missing 1-2)
- FAIL: ≤2 components present (missing 3+)

**Routing on FAIL:** `/lp-optimizer elements`

---

## LP-D02: Hero 5-Second Test
**Severity:** High (10 pts) | **Data:** Chrome DevTools H1 text + above-fold screenshot

**Rule:** 80% of visitors decide to stay or leave based on the hero section. A stranger must understand the value proposition within 5 seconds.

**How to check:**
1. Extract H1 text from page
2. Check: is H1 under 10 words?
3. Check: does H1 communicate an outcome (not a feature)?
4. Extract sub-headline text — does it add specificity without repeating the H1?
5. Take above-fold screenshot — is the value proposition visually clear?
6. Check for hero section mistakes: vague headline, feature-focused, jargon, no visual

**Pass/Fail:**
- PASS: H1 ≤10 words, outcome-focused, sub-headline adds specificity, visual reinforces message
- WARN: H1 is 11-15 words OR outcome is unclear but identifiable OR sub-headline is weak
- FAIL: H1 >15 words, OR headline is vague/feature-focused, OR no sub-headline, OR visual is generic stock

**Routing on FAIL:** `/lp-optimizer elements`

---

## LP-D03: Above-Fold CTA Presence
**Severity:** High (10 pts) | **Data:** Chrome DevTools viewport emulation

**Rule:** A CTA button or link must be visible without scrolling on both desktop and mobile viewports.

**How to check:**
1. Emulate desktop viewport (1440px width)
2. Find all CTA buttons/links in the first viewport (buttons with action text, forms with submit)
3. Emulate mobile viewport (375px width)
4. Check if any CTA is visible without scrolling on mobile
5. Use JS: `document.querySelectorAll('a, button')` filtered by position within viewport height

**Pass/Fail:**
- PASS: CTA visible above fold on both desktop and mobile
- WARN: CTA visible on desktop but not mobile (or requires minor scroll on mobile)
- FAIL: No CTA visible above fold on either device

**Routing on FAIL:** `/lp-optimizer elements`

---

## LP-D04: CTA Button Quality
**Severity:** Medium (5 pts) | **Data:** Chrome DevTools DOM extraction

**Rule:** CTA button text should be benefit-driven and use first-person language. Generic text ("Submit", "Click Here", "Learn More") reduces conversions.

**How to check:**
1. Extract all CTA button text from page (buttons, submit inputs, prominent links)
2. Check each for:
   - Benefit-driven? (communicates what visitor gets, not what they do)
   - First-person? ("Get My..." not "Get Your...")
   - Specific? (includes what happens: "Get My Free Assessment" not "Submit")
3. Flag any generic CTA text: "Submit", "Click Here", "Learn More", "Send", "Go", "Next"

**Pass/Fail:**
- PASS: All CTAs are benefit-driven and specific
- WARN: Primary CTA is good but secondary CTAs are generic
- FAIL: Primary CTA is generic ("Submit", "Click Here", "Send")

**Routing on FAIL:** `/lp-optimizer elements`

---

## LP-D05: Benefits Section Quality
**Severity:** Medium (5 pts) | **Data:** Chrome DevTools page content

**Rule:** Benefits must focus on outcomes (not features) and cover at least 2 of 3 angles: functional, business, personal.

**How to check:**
1. Locate benefits section on page (typically after hero)
2. Extract benefit statements
3. Check: outcome-focused or feature-focused? Apply "so what?" test
4. Categorize each benefit into angle:
   - Functional: time, cost, ease, results
   - Business: efficiency, resources, compliance
   - Personal: stress, confidence, recognition
5. Count how many angles are covered

**Pass/Fail:**
- PASS: Benefits are outcome-focused AND cover 2+ of 3 angles
- WARN: Benefits are outcome-focused but cover only 1 angle, OR cover 2+ angles but some are feature-focused
- FAIL: Benefits are entirely feature-focused OR no benefits section present

**Routing on FAIL:** `/lp-optimizer elements`

---

## LP-D06: Trust/Authority Section
**Severity:** Medium (5 pts) | **Data:** Chrome DevTools page content

**Rule:** Trust must be established before social proof is effective. At least one trust element should be present and match the vertical.

**How to check:**
1. Search page for trust elements:
   - Certification badges (ISO, SOC 2, GDPR)
   - Credential mentions (professional qualifications)
   - Award logos
   - Media mention logos ("As seen in...")
   - Partner logos
   - Specific results claims ("43% average ROI increase")
2. Check vertical match:
   - Regulated industries: institutional trust (certifications, compliance)
   - Services/consulting: expertise trust (results, credentials)
   - B2C: balance of both
3. Check: are trust claims specific and verifiable?

**Pass/Fail:**
- PASS: Trust elements present and match vertical, claims are specific
- WARN: Trust elements present but generic (e.g., "We can be trusted") or wrong type for vertical
- FAIL: No trust elements present at all

**Routing on FAIL:** `/lp-optimizer elements`

---

## LP-D07: Social Proof Quality
**Severity:** Medium (5 pts) | **Data:** Chrome DevTools page content

**Rule:** Social proof must be real, specific, and verifiable. Anonymous or generic testimonials create suspicion.

**How to check:**
1. Find all social proof elements (testimonials, reviews, case studies, stats, logos)
2. For each testimonial, check completeness:
   - Full name present?
   - Photo/avatar present?
   - Company name present?
   - Specific result or metric mentioned?
3. Score by completeness: 4/4 = full, 3/4 = good, 2/4 = weak, 1/4 = anonymous
4. Check for statistical proof ("Used by 50K+ businesses")
5. Check for third-party validation (G2, Trustpilot, Capterra ratings)

**Pass/Fail:**
- PASS: Social proof present with full details (name, photo, company, specific result)
- WARN: Social proof present but incomplete (missing photos or specifics) OR only logos/stats without testimonials
- FAIL: No social proof at all, OR only anonymous testimonials

**Routing on FAIL:** `/lp-optimizer elements`

---

## LP-D08: Objection Handling
**Severity:** Medium (5 pts) | **Data:** Chrome DevTools page content

**Rule:** Top visitor objections must be addressed proactively. An FAQ section should cover pricing, implementation/effort, timing, and trust.

**How to check:**
1. Look for FAQ section or objection-handling content
2. Check if the 4 common objection types are addressed:
   - Pricing: cost justification, ROI, payment options
   - Implementation/effort: complexity, time investment, support
   - Timing: why now, cost of delay
   - Trust: credibility, proof of claims
3. Count how many of 4 are addressed

**Pass/Fail:**
- PASS: 3+ of 4 objection types addressed
- WARN: 1-2 objection types addressed
- FAIL: No objection handling content present

**Routing on FAIL:** `/lp-optimizer elements`

---

## LP-D09: Guarantee Presence & Placement
**Severity:** Medium (5 pts) | **Data:** Chrome DevTools page content

**Rule:** A specific guarantee must be present and placed near a conversion point (not buried in footer).

**How to check:**
1. Search page for guarantee text (money-back, satisfaction, free trial, return policy)
2. Check specificity: duration stated? Process clear? Conditions transparent?
3. Check placement: is it near a CTA button? Near a form? Or buried in footer/fine print?

**Pass/Fail:**
- PASS: Specific guarantee present near a conversion point
- WARN: Guarantee present but vague ("satisfaction guaranteed") OR buried in footer
- FAIL: No guarantee or risk removal statement present

**Routing on FAIL:** `/lp-optimizer elements`

---

## LP-D10: CTA Repetition
**Severity:** Medium (5 pts) | **Data:** Chrome DevTools DOM extraction

**Rule:** CTAs should appear 3+ times throughout the page at key conversion points.

**How to check:**
1. Count all CTA instances on the page (buttons, prominent links with action text)
2. Map their positions to page sections:
   - After hero?
   - After benefits/proof section?
   - After objection handling?
   - Final section?
3. Check: is CTA text consistent across placements?

**Pass/Fail:**
- PASS: 3+ CTAs placed at key conversion points
- WARN: 2 CTAs present (e.g., hero + footer only)
- FAIL: Only 1 CTA on the entire page

**Routing on FAIL:** `/lp-optimizer elements`

---

## LP-D11: One-Page-One-Goal
**Severity:** High (10 pts) | **Data:** Chrome DevTools DOM extraction

**Rule:** Every link that isn't the primary CTA is a conversion leak. Navigation, footer links, social icons, and competing CTAs must be removed.

**How to check:**
1. Check for navigation bar (header menu links)
2. Check for footer links beyond legal requirements
3. Check for social media icons on the page
4. Check for competing outbound links that lead away from conversion
5. Exceptions: anchor links to page sections, legal links (open in new tab), one secondary CTA that advances the same goal

**Pass/Fail:**
- PASS: No navigation, no competing links, footer legal-only, no social icons
- WARN: Navigation exists but is minimal, OR 1-2 non-essential footer links
- FAIL: Full navigation present, OR social icons on page, OR multiple competing CTAs/outbound links

**Routing on FAIL:** `/lp-optimizer elements`

---

## LP-D12: Section Hierarchy
**Severity:** Medium (5 pts) | **Data:** Chrome DevTools DOM extraction + screenshot

**Rule:** Page sections should follow the 7-section LP Hierarchy Blueprint in the correct psychological sequence.

**How to check:**
1. Map page sections to the 7-section blueprint:
   - Hero (above fold)
   - Benefits (first scroll)
   - Trust/Authority (after benefits)
   - Social Proof (after trust)
   - Objection Handling (middle of page)
   - Urgency/Scarcity (before final CTA)
   - CTA (repeated throughout + final)
2. Report: which sections present, which missing
3. Check sequence: is the order correct? (trust before proof, proof before pressure)

**Pass/Fail:**
- PASS: 6+ of 7 sections present in correct sequence
- WARN: 4-5 sections present OR sequence is incorrect (e.g., urgency before trust)
- FAIL: ≤3 sections present OR major sequence violation

**Routing on FAIL:** `/lp-optimizer elements`, or `/landing-page-builder` if rebuild needed
