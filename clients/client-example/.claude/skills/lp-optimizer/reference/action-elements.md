# LP Optimizer -- Missing Conversion Elements (LP-E11)

Used by: `/lp-optimizer elements`

## Investigation Steps

### 1. Read Audit Structural Findings

From `context/analysis/lp-audit.md`, extract FAIL/WARN results for:
- D01: Offer section completeness (which of the 5 components are missing?)
- D05: Benefits section quality
- D06: Trust/authority section
- D07: Social proof quality
- D08: Objection handling
- D09: Guarantee presence & placement
- D10: CTA repetition
- D12: Section hierarchy

### 2. Inspect Page via Chrome DevTools

For each missing element identified in the audit:
1. Navigate to the LP
2. Screenshot the current page layout
3. Identify where the missing element should be placed
4. Check what's currently in that position

### 3. Map Missing Elements to Templates

For each missing element, provide specific content templates based on the section catalogs.

## Element Templates by Category

### Missing: Social Proof

**If no testimonials exist:**

```
Option A: Customer quote card
"[Specific result achieved] since switching to [product/service]."
-- [Full Name], [Title], [Company]
[Photo]

Option B: Results-focused testimonial
"We saw [metric] improve by [X%] within [timeframe]."
-- [Full Name], [Company] | [Verification link]

Option C: Review aggregate
[Star rating] [X.X]/5 from [N]+ reviews on [Platform]
```

**Placement:** After benefits section, before objection handling.

**Quality criteria:**
- Full name (not initials)
- Photo or company logo
- Specific result or metric (not vague praise)
- Verifiable (link to original review when possible)

### Missing: Trust/Authority Section

**Lead Gen:**
```
- License/certification badges
- "X+ years in business"
- "[N]+ projects completed"
- Media mentions: "As seen in [Publication]"
- Industry association logos
```

**SaaS:**
```
- Client logos (recognizable names)
- "[N]+ teams trust [Product]"
- Security badges (SOC 2, GDPR, ISO)
- G2/Capterra rating badges
- Integration partner logos
```

**Ecommerce:**
```
- "[N]+ orders shipped"
- Payment security badges
- Money-back guarantee badge
- Shipping partner logos
- "[N]+ 5-star reviews"
```

**Placement:** Below hero section (for authority) or above CTA (for trust reinforcement).

### Missing: Objection Handling (FAQ)

Identify top 3-5 objections for the vertical:

**Lead Gen:**
1. "How much does it cost?" -- Address pricing transparency
2. "How long does it take?" -- Set timeline expectations
3. "Are you licensed/insured?" -- Credibility
4. "What if I'm not satisfied?" -- Guarantee/warranty
5. "Do I need to be home?" -- Logistics

**SaaS:**
1. "Is there a free trial?" -- Risk removal
2. "Can I cancel anytime?" -- Commitment concern
3. "Is my data secure?" -- Security
4. "Does it integrate with [tool]?" -- Compatibility
5. "What support is included?" -- After-purchase

**Ecommerce:**
1. "What's the return policy?" -- Risk removal
2. "How long is shipping?" -- Delivery timeline
3. "Is it authentic?" -- Product legitimacy
4. "What if it doesn't fit?" -- Sizing/compatibility
5. "Is checkout secure?" -- Payment security

**Placement:** After social proof section, before final CTA.

**Format:** Expandable accordion (FAQ-style) with clear question headers.

### Missing: Guarantee

**Templates by vertical:**

```
Lead Gen: "100% satisfaction guarantee. If you're not happy with
our [service], we'll [specific remedy] at no additional cost."

SaaS: "[X]-day money-back guarantee. Try [Product] risk-free.
If it's not right for you, cancel within [X] days for a full refund.
No questions asked."

Ecommerce: "[X]-day hassle-free returns. Not in love with your
purchase? Return it within [X] days for a full refund.
Free return shipping included."
```

**Placement:** Near the primary CTA (within 1 scroll-height) and near the form/checkout.

### Missing: CTA Repetition

Current CTAs should appear in these locations:

| Position | Purpose | CTA Type |
|----------|---------|----------|
| Hero section | Capture high-intent visitors | Primary CTA |
| After benefits | Visitors convinced by value prop | Primary CTA |
| After social proof | Visitors convinced by evidence | Primary CTA |
| After objections/FAQ | Visitors with concerns resolved | Primary CTA |
| Final section | Last chance before exit | Primary CTA with urgency |

**Minimum:** 3 CTA instances on the page.
**Target:** CTA visible after each major persuasion section.

### Missing: Benefits Section

Transform features into benefits using the FAB framework:

```
Feature: What it does
Advantage: Why that matters
Benefit: How the visitor's life improves

Example:
Feature: "AI-powered analytics"
Advantage: "Spots trends humans miss"
Benefit: "Make decisions 3x faster with insights delivered to your inbox every morning"
```

**Structure:**
- 3-4 benefits maximum (avoid overwhelming)
- Each benefit: icon + headline + 1-2 sentence description
- Cover multiple benefit angles: functional, emotional, financial

## Report Output Structure

```markdown
## Missing Conversion Elements Analysis

### Elements Inventory
| Element | Status | Audit ID | Current State |
|---------|--------|----------|--------------|
| Social proof | MISSING | D07 FAIL | No testimonials anywhere |
| Guarantee | MISSING | D09 FAIL | No guarantee text found |
| FAQ/Objections | WEAK | D08 WARN | Only 1 FAQ item |
| CTA repetition | WEAK | D10 WARN | Only 1 CTA on page |

### Recommended Additions
{For each missing element: template, placement, copy draft}

### Page Wireframe Update
{Recommended section order with new elements inserted}

### Implementation Notes
{Who does what: copy (marketer), design (designer), placement (developer)}
```
