# LP Experience Methodology (ported from retired landing-page-analyzer)

Use this reference when fixing landing pages for keywords flagged in a `/quality-score-auditor` LP Experience handoff queue — or any time LP Experience is Below Average.

LP Experience answers: **Does the landing page deliver what the ad promised, and does it do so effectively?** Google uses conversion rate as a strong proxy.

---

## The LP 5-Second Test

When someone lands on the page, they subconsciously ask these five questions. A good LP answers all five within 5 seconds of arrival.

| # | Question | What must be visible |
|---|---|---|
| 1 | **Where am I?** | Brand, page topic, keyword-matching headline |
| 2 | **What can I do here?** | Primary offer / action clearly stated |
| 3 | **Why should I do it?** | Benefit, not feature |
| 4 | **Why should I trust you?** | Proof element: logo, rating, testimonial, number |
| 5 | **What do I do next?** | Primary CTA above the fold |

**Audit rubric:**

| Score | Verdict | Action |
|---|---|---|
| 5/5 | PASS | LP hero is strong — look elsewhere for the LP Below Avg signal (speed? mobile?) |
| 3–4 | PARTIAL | Patch the missing questions (usually 4 or 5) |
| 0–2 | FAIL | Hero section rebuild needed |

---

## Attention Ratio (1:1 is the goal)

$$\text{Attention Ratio} = \frac{\text{clickable things on the page}}{\text{clickable things that lead to the conversion goal}}$$

| Ratio | Rating | Action |
|---|---|---|
| 1:1 | Ideal | Dedicated LP — one page, one purpose |
| 2:1 to 5:1 | Acceptable | Reduce distractions (collapse nav, remove footer links) |
| 5:1+ | Poor | Too many exits — every non-CTA link competes with conversion |

**How to audit:** count every clickable element on the page (nav items, footer links, social icons, related products, sidebar links). Then count links that point to the conversion goal. Divide.

**When a high ratio is defensible:** product pages with organic traffic (users often want to compare before buying). Dedicated paid-traffic LPs have no excuse for >3:1.

---

## Hero section — required elements

| Element | Purpose | Required? |
|---|---|---|
| Headline | State main benefit / outcome | Yes |
| Subheadline | Expand on headline (context, specificity) | Yes |
| Hero image / video | Show the product or the outcome | Recommended |
| Primary CTA | Tell the visitor what to do | Yes |
| Trust indicator | Quick credibility (logo bar, rating, user count) | Recommended |

### Headline formulas (proven patterns)

- **Outcome + Timeframe:** *"Double Your Leads in 30 Days"*
- **Outcome + Without [Pain]:** *"Grow Revenue Without Hiring More Reps"*
- **Benefit + For [Audience]:** *"Marketing Automation for B2B Founders"*

Avoid generic headlines like "Welcome to Acme" or "The Best Software". They fail the 5-Second Test on questions 1 and 2.

---

## CTA visibility rules

| Rule | Implementation |
|---|---|
| Above the fold | Primary CTA visible without scrolling on mobile + desktop |
| Contrasting color | CTA stands out from surrounding palette (not blended into brand color) |
| Repeated | CTA appears after each major section (hero, benefits, proof, FAQ) |
| Sticky mobile CTA | Consider fixed bottom bar for mobile LPs with long scroll |
| Specific verb | "Start My Free Trial" beats "Submit"; "Get My Quote" beats "Contact Us" |

### Strong CTAs by vertical

| Vertical | Weak | Strong |
|---|---|---|
| SaaS | "Submit" | "Start My Free Trial" |
| Lead Gen | "Contact Us" | "Get My Free Quote" |
| Ecommerce | "Buy" | "Add to Cart — Free Shipping" |
| Services | "Learn More" | "Schedule My Consultation" |

---

## Trust & transparency checklist

| Element | Lead Gen | SaaS | Ecommerce | Services |
|---|---|---|---|---|
| Company name prominent | ✓ | ✓ | ✓ | ✓ |
| Physical address / location | ✓ | — | — | ✓ |
| Phone number | ✓ | — | — | ✓ |
| Email / contact form | ✓ | ✓ | ✓ | ✓ |
| Privacy policy link | ✓ | ✓ | ✓ | ✓ |
| Terms of service link | — | ✓ | ✓ | — |
| Trust badges / certifications | ✓ | ✓ | ✓ | ✓ |
| Testimonials / reviews | ✓ | ✓ | ✓ | ✓ |
| Case studies / results | B2B | B2B | — | ✓ |
| Industry-specific (HIPAA, SOC2, BBB) | as applicable |

For Lead Gen especially: missing contact info is a major trust killer and a frequent driver of LP Below-Avg ratings.

---

## Message Match fixes (when ad ≠ LP)

**Option A — Align LP to Ads (preferred when one ad group → one LP):**
- Update LP headline to include the core keyword / theme from the ad.
- Ensure the offer mentioned in ads is prominent above the fold.
- Match CTA language between ad and LP (same verb, same benefit).

**Option B — Dynamic Text Replacement (DTR) (when many keyword variants → one LP):**
1. Add a URL parameter to the ad's final URL: `?keyword={keyword}` (or `?kw={keyword}` — any variable).
2. LP reads the parameter and updates the headline dynamically.

**Example DTR behavior:**
```
Ad URL: yoursite.com/crm?keyword=sales+crm+software
LP headline renders: "Sales CRM Software — Close 40% More Deals"
```

DTR is especially useful when a single LP serves many keyword-level intent variants. Works well paired with DKI in the ad copy.

---

## Technical audit reminders (when to use Chrome DevTools)

The `lp-auditor` scoring covers these at the diagnostic level. When fixing, Chrome DevTools MCP gives the deeper picture:

- **Page speed:** PageSpeed Insights for the public score; DevTools Performance trace for waterfall.
- **Core Web Vitals:** LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1 (all "Good" thresholds).
- **Mobile:** min 16px body font, min 44×44px tap targets, no horizontal scroll.

Common quick wins (ordered by effort ÷ impact):
1. Compress + resize hero images (often halves LCP).
2. Defer non-critical JS (improves INP, TBT).
3. Reserve image dimensions to prevent layout shift (fixes CLS).
4. Enable browser caching + CDN for static assets.

---

## Validation windows

| Fix type | Expected LP Experience update |
|---|---|
| Message match / hero rewrite | 14–21 days |
| Speed / technical | 14–30 days |
| Trust element additions | 21–30 days |
| Full LP rebuild | 30+ days |

LP Experience is the slowest-updating QS component. Use **conversion rate movement** as the leading indicator — CVR moves within 7 days of a real improvement, the label follows.
