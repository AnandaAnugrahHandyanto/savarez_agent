---
name: ecom-page-builder
description: Generate ecommerce HTML page wireframes (dedicated LPs and product pages) with product-first layouts and brand-matched colors. Use for ecom pages, product page wireframes, or ecommerce LPs.
argument-hint: "[--skip-discovery] [--from-audit]"
---

# Ecommerce Page Builder Skill

Generate a self-contained HTML ecommerce page wireframe with product-first layouts, real persuasive copy, brand-matched colors, and visual placeholders — ready to open in a browser and present to a client.

Built on the **Ecommerce Conversion Engine** framework. Core principle: **proof comes before benefits** because the product image already communicates the value proposition visually.

## Command Format

```
/ecom-page-builder [--skip-discovery] [--from-audit]
```

**Examples:**
- `/ecom-page-builder` — Full interactive mode with 7-question discovery
- `/ecom-page-builder --skip-discovery` — Derive settings from existing context files
- `/ecom-page-builder --from-audit` — Use prior audit/optimize data (skips "use audit data?" confirmation)

---

## Process

### Phase 0: Prerequisites Check

Check required context files:

| File | Required | If Missing |
|------|----------|------------|
| `context/brand.md` | Yes | Prompt: "Run `/ads-context [URL]` first" |
| `context/offer-angles.md` | Yes | Prompt: "Run `/offer-maker angles` first" |
| `context/brand-colours/palette.md` | Yes | Prompt: "Run `/ads-context [URL]` first" |

**Optional files (enhance output if present):**

| File | Used For |
|------|----------|
| `context/business.md` | Business goals, constraints, previous test learnings |
| `context/google-ads/data/keywords.csv` | Primary keywords for message match in headline |
| `context/google-ads/data/ads.csv` | Existing ad copy for message match reference |

**If required files are missing, stop and show:**

```markdown
## Prerequisites Missing

To build an ecommerce page wireframe, the following context is required:

| File | Status | Action |
|------|--------|--------|
| context/brand.md | {status} | Run `/ads-context-gatherer [URL]` first |
| context/offer-angles.md | {status} | Run `/offer-maker angles` first |
| context/brand-colours/palette.md | {status} | Run `/ads-context-gatherer [URL]` first |
```

**Show only the missing files. Do not proceed until all 3 exist.**

---

### Phase 0.25: Peer Context Pull (Cross-Skill Enrichment)

**Mode 2 — context enrichment only.** This sub-phase reads fresh peer audits and extracts ecommerce-page-relevant findings into a `PEER_CONTEXT` buffer that downstream phases (Architecture, Copy, HTML, Summary) consume to bias the generated output. **No gate, no abort, no hard-block.** If peer reports are missing or stale, surface informational notes and proceed.

E-commerce pages depend tightly on peer context: tracking integrity (transactions, AOV, ROAS), competitive differentiation (price/delivery/quality/guarantee), offer angles (which lever to lead with), and search-term language (what real buyers type). Pull this once at the top so both Dedicated LP and Product Page builds bias to it.

#### 0.25.1 — Walk the 10-peer freshness table

For each peer report below, check existence and parse the `**Date:**` field from the report header. Compare against today (`{currentDate}`) and label each as **Fresh**, **Stale**, or **Missing**.

| Peer skill | Report file | Fresh window | Highest-leverage signal for ecom pages |
|---|---|---|---|
| `/quality-score-auditor` | `context/analysis/quality-score-audit.md` | ≤ 7 days | LPE for trust signal density; AR for keyword-matched copy |
| `/search-term-auditor` | `context/analysis/search-term-audit.md` | ≤ 7 days | Product naming language from top n-grams |
| `/keyword-auditor` | `context/analysis/keyword-audit.md` | ≤ 7 days | Category-page theme alignment |
| `/budget-auditor` | `context/analysis/budget-audit.md` | ≤ 7 days | Budget context |
| `/bidding-auditor` | `context/analysis/bidding-audit.md` | ≤ 7 days | Posture context (Smart Shopping, PMax) |
| `/competitive-analyst` | `context/analysis/competitive-audit.md` | ≤ 14 days | Competitor differentiation (price/delivery/quality/guarantee) |
| `/lp-auditor` | `context/analysis/lp-audit.md` | ≤ 14 days | LP benchmarks (ecom module D38–D40 specifically) |
| `/offer-auditor` | `context/analysis/offer-audit.md` | ≤ 30 days | Offer angles for hero (guarantee / shipping / bundle) |
| `/tracking-specialist` | `context/analysis/tracking-audit.md` | ≤ 30 days | Informational warning (e-commerce conversion tracking is critical) |
| `/strategy-specialist` | `context/analysis/strategy-audit.md` | ≤ 30 days | Break-even / posture for pricing emphasis |

#### 0.25.2 — Extract findings into the `PEER_CONTEXT` buffer

For each Fresh report, extract only what biases the page. Skip Stale/Missing reports for the buffer but record them for the freshness summary.

```
PEER_CONTEXT
├── tracking
│     ├── status: Fresh | Stale | Missing
│     ├── ecom_tracking_health: {transactions / AOV / ROAS tracked? Y/N}
│     └── note: "Ecommerce conversion tracking is the foundation of ROAS/AOV reporting — verify before launch"
├── strategy
│     ├── status: ...
│     ├── posture: {growth | efficiency | break-even}
│     ├── target_roas: {value or null}
│     └── pricing_emphasis: {discount-led | margin-led | value-led}
├── offer
│     ├── status: ...
│     ├── lead_offer_angle: {guarantee | free shipping | bundle | discount | premium positioning}
│     ├── trust_angles: [list of authentic trust signals from offer-audit]
│     └── urgency_authentic: {Y/N — only Y if offer-audit confirms urgency is real}
├── competitive
│     ├── status: ...
│     ├── competitor_weak_axis: {price | delivery | quality | guarantee | breadth}
│     ├── recommended_differentiation: {which axis to lead with}
│     └── price_position: {premium | parity | discount}
├── search_term
│     ├── status: ...
│     ├── top_converting_ngrams: [list, ranked]
│     ├── product_naming_language: [phrases real buyers use]
│     └── category_phrases: [for product page category copy]
├── keyword
│     ├── status: ...
│     └── theme_clusters: [for category-page copy alignment]
├── quality_score
│     ├── status: ...
│     ├── lpe_avg: {below avg | avg | above avg}
│     ├── lpe_failing_themes: [campaigns/ad groups with LPE below avg]
│     └── ar_keyword_gaps: [keywords AR is below avg — copy must mirror]
├── lp
│     ├── status: ...
│     ├── ecom_module_score: {D38–D40 from prior lp-audit}
│     └── ecom_specific_findings: [product page elements, cart flow, category quality]
├── budget
│     ├── status: ...
│     └── note: {informational — budget-limited or healthy}
└── bidding
      ├── status: ...
      └── posture_note: {Smart Shopping / PMax / manual — informs CTA wording on Product Page}
```

#### 0.25.3 — Surface informational notes

Print a peer freshness summary to the user. Treat tracking and strategy as priority warnings if dirty.

```markdown
## Peer Context

| Peer | Status | Used for |
|------|--------|----------|
| /tracking-specialist | {Fresh / Stale Nd / Missing} | Ecommerce conversion tracking integrity |
| /strategy-specialist | {Fresh / Stale Nd / Missing} | Pricing emphasis, posture |
| /offer-auditor | {Fresh / Stale Nd / Missing} | Lead offer angle for hero |
| /competitive-analyst | {Fresh / Stale Nd / Missing} | Differentiation axis |
| /search-term-auditor | {Fresh / Stale Nd / Missing} | Product naming language |
| /keyword-auditor | {Fresh / Stale Nd / Missing} | Category-page theme alignment |
| /quality-score-auditor | {Fresh / Stale Nd / Missing} | LPE → trust signal density |
| /lp-auditor | {Fresh / Stale Nd / Missing} | Ecom module benchmarks |
| /budget-auditor | {Fresh / Stale Nd / Missing} | Budget context |
| /bidding-auditor | {Fresh / Stale Nd / Missing} | Posture context |
```

**Surface these informational warnings prominently when present:**

- **M (Measurement) dirty** — if `/tracking-specialist` is Stale or Missing, OR ecom_tracking_health flags missing transactions/AOV/ROAS:
  > "Note: Ecommerce conversion tracking is the foundation of ROAS, AOV, and add-to-cart reporting on this page. Tracking audit is {stale Nd / missing}. Page will still be built, but verify transactions, AOV, and purchase events fire correctly before driving traffic. Consider running `/tracking-specialist` before launch."
- **B (Business / Strategy) dirty** — if `/strategy-specialist` is Stale or Missing:
  > "Note: Strategy audit is {stale Nd / missing}. Page will still be built, but pricing emphasis and posture (premium vs discount-led) will fall back to brand.md / offer-angles.md defaults. Consider running `/strategy-specialist` for tighter pricing voice."

**No gating.** Always proceed to Phase 0.5 / Phase 1 regardless of peer freshness.

---

### Phase 0.5: Prior Audit Integration

Check if prior LP audit and optimization reports exist. If they do, leverage their findings to pre-populate discovery settings and seed copy generation — avoiding redundant analysis.

**If `--from-audit` flag is provided:** Skip the "use audit data?" confirmation (Step 4) and go straight to reduced discovery (Step 5).

#### Step 1 — Detect Reports

Check for:
- `context/analysis/lp-audit.md`
- `context/analysis/lp-optimize-audit.md` (primary — full optimization guidance)
- Any other `context/analysis/lp-optimize-*.md` files (elements, cart, etc.)

**If none exist:** Skip Phase 0.5 entirely. Proceed to Phase 1 as normal.

#### Step 2 — Extract Audit Context

**From `lp-audit.md`** (if exists), extract:

| Field | Where to find it |
|-------|-----------------|
| URL audited | Header: `**URL(s) Audited:**` line |
| Vertical | Header: `**Vertical:**` line |
| Overall score + grade | Header: `**Overall Score:**` line |
| D02: Hero headline quality | Structural Results table — current H1 text + PASS/WARN/FAIL + diagnosis |
| D04: CTA quality | Structural Results table — current CTA text + classification |
| D05: Benefits quality | Structural Results table — feature vs outcome diagnosis |
| D07: Social proof quality | Structural Results table — testimonial gaps (photos, titles, results) |
| D08: Objection handling | Structural Results table — FAQ coverage + objection types addressed |
| D09: Guarantee presence | Structural Results table — present/missing + placement |
| D11: One-page-one-goal | Structural Results table — FAIL status + link counts |
| D12: Section hierarchy | Structural Results table — sections present vs missing |
| D38-D40: Ecommerce diagnostics | Ecommerce Results table (if vertical = ecommerce) — product page elements, cart flow, category quality |

**From `lp-optimize-*.md`** (if exists), extract:

| Field | Where to find it |
|-------|-----------------|
| Recommended H1/tagline | P2 Fix Recommendations table — "Recommended" column for headline fix |
| Recommended CTAs | P2 Fix Recommendations table — "Recommended" column for CTA fix |
| Recommended guarantee text | P2 Fix Recommendations table — "Recommended" column for guarantee fix |
| Recommended benefit rewrites | P2 Fix Recommendations table — "Recommended" column for benefits fix |
| Testimonial/review enhancement plan | P2 Fix Recommendations table — "Recommended" column for social proof fix |
| Recommended urgency text | P2 Fix Recommendations table — "Recommended" column for urgency fix |
| Implementation copy block | "For the Marketer" section — ready-to-use copy drafts |
| Expected impact estimates | Expected Impact table — CVR and CPA projections |

If multiple `lp-optimize-*.md` files exist, prefer `lp-optimize-audit.md` as the primary source. Read others for additional specific fixes.

#### Step 3 — Staleness Check

Parse the `**Date:**` field from the audit report header. If the audit is older than 14 days:

> "Audit report is {N} days old ({date}). Recommendations may be outdated. Consider re-running `/lp-auditor` first."

Still allow the user to proceed.

#### Step 3.5 — Vertical Mismatch Check

If the audit `Vertical:` field is NOT "Ecommerce":

> "The audit was for a **{vertical}** page. You're using the ecommerce page builder. Confirm you want to build an ecommerce page for this product/offer."

This prevents accidental use of the wrong builder. If the user confirms, proceed. If not, suggest `/landing-page-builder` instead.

#### Step 4 — Present Summary and Ask

Show what was found:

```markdown
## Prior Audit Data Detected

I found existing audit and optimization reports for this page:

| Report | Date | Key Info |
|--------|------|----------|
| LP Audit | {date} | {score}% ({grade}) — {url} |
| LP Optimize — {action} | {date} | {P2 fix count} strategic fixes with copy recommendations |

### Key findings that will inform this build:
- **Vertical:** {vertical}
- **Current H1:** "{current_h1}" → **Recommended:** "{recommended_h1}"
- **Current CTAs:** "{current_ctas}" → **Recommended:** "{recommended_ctas}"
- **Missing sections:** {e.g., Urgency/Scarcity, Guarantee badge}
- **Weak sections:** {e.g., Benefits (feature-focused), Social Proof (no photos/titles)}
- **Strong sections to preserve:** {e.g., FAQ coverage, Trust signals}

Would you like to use this audit data to inform the new ecommerce page?
```

AskUserQuestion with options:
- **Yes, use audit data (Recommended)** — Pre-populate settings from audit. You'll confirm just 2 questions instead of 7
- **No, start fresh** — Ignore audit data and run full discovery

If user selects "No, start fresh": proceed to Phase 1 as normal.

#### Step 5 — Reduced Discovery

If user selects "Yes, use audit data" (or `--from-audit` flag was provided): replace Phase 1's 7 questions with this reduced flow.

**Auto-derived settings (no questions needed):**

| Setting | Derived From | Value |
|---------|-------------|-------|
| Product details | `context/offer-angles.md` + audit D01 offer completeness | Auto-populated |
| Social proof level | Audit D07 — reveals exactly what proof exists (review count, photos, titles) | Auto-populated |
| Urgency | Audit D12 (if missing → include) + optimizer recommendation | Auto-populated |
| Page length | Auto-recommended from page type (Full-length for Dedicated LP, Standard for Product Page) | Auto-populated |
| Objections | Audit D08 FAQ items that scored PASS — adapt rather than reinvent | Auto-populated |

Present auto-derived settings in a confirmation table, then ask only these 2 questions:

**Question A: Page Type**

"The audit found the current page has **{D11 details — e.g., full navigation, 42 footer links}**. The recommended approach is a **Dedicated Ecommerce LP** (no navigation, conversion-focused). Is this correct?"

Default: Dedicated Ecommerce LP if D11 = FAIL (navigation/footer issues). Product Page if D11 = PASS.

Options: Dedicated Ecommerce LP | Product Page

**Question B: Shipping & Returns**

"What shipping and returns policy should appear on the page?"

Options: Free shipping + 30-day returns | Free shipping + 60-day returns | Flat rate + 30-day returns | Other/custom

(This question must always be asked — audit data doesn't cover it.)

#### Step 6 — Build Context Objects

After reduced discovery, produce two context blocks that downstream phases consume:

**`AUDIT_ARCHITECTURE_CONTEXT`** (consumed by Phase 3):
```
Sections present: {from D12}
Sections missing: {from D12 — e.g., Urgency/Scarcity}
Section quality:
  - Product Showcase/Hero: {WARN/FAIL} — needs rewrite
  - Customer Evidence/Social Proof: {WARN} — incomplete, needs enrichment
  - Product Benefits: {WARN} — feature-focused, needs outcome rewrite
  - Purchase Confidence: {status} — guarantee/returns coverage
  - Act Now/Urgency: {missing} — add per optimizer
Emphasis overrides:
  - Where audit WARN/FAIL → increase emphasis one level above standard
  - Where audit PASS → maintain standard level
```

**`AUDIT_COPY_SEEDS`** (consumed by Phase 4):
```
hero_tagline: "{recommended tagline from optimizer}" (source: lp-optimize P2 Fix #N)
hero_subhead: "{recommended sub-headline}" (source: optimizer Implementation Notes)
hero_cta: "{recommended CTA}" (source: lp-optimize P2 Fix #N)
guarantee_text: "{recommended badge text}" (source: lp-optimize P2 Fix #N)
benefit_rewrites: ["{outcome-focused rewrites}", ...] (source: lp-optimize P2 Fix #N)
urgency_text: "{recommended urgency}" (source: lp-optimize P2 Fix #N)
review_gaps: "{what's missing — photos, titles, companies, results}" (source: audit D07)
faq_items: ["{existing FAQ items that scored PASS}"] (source: audit D08)
trust_signals: ["{strong signals to preserve}"] (source: audit D06)
expected_impact: "{CVR and CPA projections}" (source: optimizer Expected Impact table)
```

---

### Phase 1: Discovery Questionnaire

**If Phase 0.5 completed with "Yes, use audit data":** Skip Phase 1 entirely. The audit-derived settings and reduced discovery answers replace all 7 questions. Proceed to Phase 2.

**If `--from-audit` flag was provided and Phase 0.5 completed:** Skip Phase 1. Proceed to Phase 2.

**If `--skip-discovery` flag is provided:** Skip to auto-derivation (see below).

Ask 7 questions using the AskUserQuestion tool. Ask questions in batches where possible to reduce back-and-forth.

#### Question 1: Page Type (Decision Gate)

**Question:** "What type of ecommerce page are you building?"

| Option | Description |
|--------|-------------|
| Dedicated Ecommerce LP | No navigation. For paid promotions, seasonal offers, single-product campaigns. Cold traffic from Display/YouTube/Demand Gen. |
| Product Page | With site navigation. For Shopping PLAs, PMax, organic traffic. Visitors may need to browse variants. |

Use AskUserQuestion with these 2 options. multiSelect: false.

Show the decision gate context:
- Dedicated LP = no-nav, full Ecommerce Persuasion Sequence, 4+ CTAs
- Product Page = with nav, 7-section hierarchy, CTA at position 3

#### Question 2: Product Details

**Question:** "Describe the product being sold. Include the product name, type/category, price point, key features, and what makes it different from competitors."

| Option | Description |
|--------|-------------|
| Pull from context | Derive product details from offer-angles.md and brand.md automatically |

If the user selects "Other", they provide free-text product details.

#### Question 3: Shipping & Returns

**Question:** "What are the shipping and return policies for this product?"

| Option | Description |
|--------|-------------|
| Free shipping + 30-day returns | Standard ecommerce defaults |
| Free shipping + 60-day returns | Extended return window |
| Flat rate shipping + 30-day returns | Shipping fee applies |

If the user selects "Other", they provide custom shipping/return details.

#### Question 4: Available Social Proof

**Question:** "What customer evidence do you have available for this product?"

| Option | Description |
|--------|-------------|
| Customer reviews (100+) | Strong review base with photos and specific results |
| Some reviews (10-100) | Moderate reviews, may need supplementing with other proof |
| Few or no reviews | Will use placeholder reviews and alternative trust signals |

If the user selects "Other", they provide specifics (e.g., before/after photos, video testimonials, aggregate stats).

#### Question 5: Urgency/Scarcity

**Question:** "Is there any urgency or scarcity element available for this offer?"

| Option | Description |
|--------|-------------|
| Time-limited promotion | Sale or offer expires on a specific date |
| Stock scarcity | Limited inventory or limited quantities at this price |
| Shipping cutoff | "Order by X for delivery by Y" |
| None | No urgency element — Act Now section will be skipped |

Use AskUserQuestion with these 4 options. multiSelect: false.

#### Question 6: Page Length

**Question:** "How detailed should the page be?"

Based on page type, recommend a default:
- **Dedicated LP** → Full-length (Recommended) — all 7 sections at full depth
- **Product Page** → Standard — all 7 sections at standard depth

| Option | Description |
|--------|-------------|
| Full-length (Recommended for {page type}) | All 7 sections with maximum detail. Best for cold traffic and complex products |
| Standard | All 7 sections at moderate depth. Good for warm traffic and familiar product types |
| Compact | Essential sections only. For high-intent traffic (retargeting, branded search) |

Adjust the "(Recommended for {page type})" label to match the recommended option.
Use AskUserQuestion with these 3 options. multiSelect: false.

#### Question 7: Top 3 Objections

**Question:** "What are the top 3 objections or concerns your visitors are likely to have? These will be addressed in the FAQ section."

Show ecommerce-specific examples:
- "Is the quality good enough?"
- "What if it doesn't fit/work?"
- "How fast is shipping?"
- "Can I return it easily?"
- "Is this worth the price?"
- "How does it compare to [competitor]?"

| Option | Description |
|--------|-------------|
| Use common ecommerce objections | Auto-generate typical objections for this product type |

If the user selects "Other", they provide free-text objections.

#### Auto-Derivation (`--skip-discovery`)

When `--skip-discovery` is provided, derive settings from existing context:

1. **Page type:** Default to Dedicated LP if campaign/promotion mentions found in offer-angles.md, otherwise Product Page.
2. **Product details:** Pull from `context/offer-angles.md` Value Proposition + USPs sections and `context/brand.md`.
3. **Shipping/returns:** Default to free shipping + 30-day returns. Warn user to confirm.
4. **Social proof:** Check `context/offer-angles.md` Social Proof section for review mentions. Default to placeholder reviews.
5. **Urgency:** Default to None unless `context/offer-angles.md` mentions time limits or scarcity.
6. **Page length:** Full-length for Dedicated LP, Standard for Product Page.
7. **Objections:** Use ecommerce defaults: "Is the quality worth the price?", "What if it doesn't fit/work?", "How easy are returns?"

Present derived settings to user for confirmation before proceeding.

---

### Phase 2: Brand Color Resolution

Read `context/brand-colours/palette.md` (required prerequisite, guaranteed to exist) and extract brand colors and fonts.

#### 2.1 Extract from Palette

Read `context/brand-colours/palette.md` and extract:
- **Primary** — from the "Suggested Colour Roles" table, role = Primary
- **Accent** — from the "Suggested Colour Roles" table, role = Accent
- **Background** — from the "Suggested Colour Roles" table, role = Background
- **Text** — from the "Suggested Colour Roles" table, role = Text
- **Heading Font** — from the Typography table, role = Headings
- **Body Font** — from the Typography table, role = Body

#### 2.2 Map to CSS Variables

| Source (from palette) | Maps To |
|-----------------------|---------|
| Primary hex | `--color-primary` |
| Darker shade of primary | `--color-secondary` |
| Accent hex | `--color-accent` |
| Darken accent by ~10% | `--color-accent-hover` |
| Background hex | `--color-bg` |
| Slightly off-white variant of background | `--color-bg-alt` |
| Text hex | `--color-text` |
| Lighter shade of text | `--color-text-light` |
| White (or contrast color on accent) | `--color-text-on-accent` |
| Heading font | `--font-heading` |
| Body font | `--font-body` |

#### 2.3 Present Palette for Confirmation

Show the resolved colors to the user:

```markdown
## Brand Colors (from palette.md)

| Variable | Value |
|----------|-------|
| Primary | {hex} |
| Accent (CTA) | {hex} |
| Background | {hex} |
| Text | {hex} |
| Heading Font | {font-family} |
| Body Font | {font-family} |

Does this look correct?
```

Use AskUserQuestion:
| Option | Description |
|--------|-------------|
| Yes, use these colors | Proceed with this palette |
| No, I'll provide colors | Enter hex codes manually |

---

### Phase 3: Page Architecture

#### 3.1 Read Reference

Read `reference/ecommerce-persuasion-sequence.md` to look up section hierarchy for the selected page type.

#### 3.2 Select Section Sequence

**If `AUDIT_ARCHITECTURE_CONTEXT` exists from Phase 0.5:** Use the audit's section quality data to adjust the standard emphasis levels. Where the audit identifies a section as WARN or FAIL, increase emphasis by one level (e.g., Moderate → Heavy). Where the audit identifies a section as PASS, maintain the standard level. Ensure sections the audit flagged as missing (e.g., Urgency/Scarcity, Guarantee) are included. Add an "Audit Justification" column to the architecture table when presenting to the user.

**If `PEER_CONTEXT` exists from Phase 0.25:** Bias section emphasis using peer findings. Apply for **both Dedicated LP and Product Page** (each maps to its own section list — Customer Evidence/Social Proof, Purchase Confidence/Trust Reinforcement, Act Now, etc.):

- **Trust signal density (QS-audit LPE):**
  - If `peer_context.quality_score.lpe_avg = below avg` OR LPE is in `lpe_failing_themes`, raise Customer Evidence (LP) / Social Proof (PP) and Purchase Confidence (LP) / Trust Reinforcement (PP) by one emphasis level. Place trust badges higher in the page (above-the-fold proof bar on LP, near Add-to-Cart on PP).
  - If LPE is healthy, keep standard emphasis.
- **Differentiation axis (competitive-audit):**
  - Lead the hero/identity section's tagline and proof block on `peer_context.competitive.competitor_weak_axis` (price | delivery | quality | guarantee | breadth).
  - On Dedicated LP, the Product Showcase tagline mirrors this axis. On Product Page, the Offer Stack section foregrounds the axis (e.g., delivery weak → make shipping speed a primary line).
- **Product naming language (search-term-audit):**
  - Reserve `peer_context.search_term.product_naming_language` phrases for hero H1 (LP) / Product Identity title (PP) and Cross-sell anchors. Note in architecture which phrase is reserved per section.
- **Urgency authenticity (offer-audit):**
  - If `peer_context.offer.urgency_authentic = N`, downgrade Act Now (LP) emphasis to Light or Skip even if Q5 supplied an urgency answer. Add note: "urgency demoted — offer-audit found no authentic urgency anchor."
  - If Y, keep emphasis as selected.
- **Pricing emphasis (strategy-audit):**
  - If `peer_context.strategy.pricing_emphasis = discount-led`, raise the price/savings element in Product Showcase (LP) and Offer Stack (PP).
  - If `margin-led` or `value-led`, downplay raw price, raise guarantee + quality differentiator instead.
- **Posture (bidding-audit):**
  - If posture is Smart Shopping / PMax, the Product Page CTA emphasis stays "Add to Cart" (catalog feed-driven). If manual/Search-driven traffic, allow stronger persuasion CTAs.

Add a **"Peer Context Applied"** column to the architecture table when peer findings shaped a row. Print value verbatim (e.g., "QS LPE below avg → Customer Evidence raised to Heavy", "competitive: delivery weak → shipping speed leads Offer Stack").

**If Dedicated Ecommerce LP selected:**

| # | Section | Emphasis | Key Content |
|---|---------|----------|-------------|
| 1 | Product Showcase | Full | Product-as-hero, price above fold, differentiator tagline |
| 2 | Customer Evidence | Heavy | Aggregate rating, curated reviews, UGC |
| 3 | Product Benefits | Heavy | Feature-to-outcome cards |
| 4 | The Details | Moderate | Specs table, what's included, comparison |
| 5 | Purchase Confidence | Heavy | Returns, shipping, sizing, FAQ |
| 6 | Act Now | {Based on Q5} | Urgency type or Skip |
| 7 | Complete Your Purchase | Full | Value recap, price, CTA, express checkout |

**If Product Page selected:**

| # | Section | Emphasis | Key Content |
|---|---------|----------|-------------|
| 1 | Product Identity | Full | Gallery, title, price, variants |
| 2 | Offer Stack | Full | Price, shipping, returns, availability |
| 3 | Add-to-Cart Action | Full | CTA at position 3, express pay |
| 4 | Social Proof | Heavy | Reviews, customer photos, sorting |
| 5 | Product Details | Moderate | Benefit-first description, specs, FAQ |
| 6 | Cross-sell | Moderate | Frequently bought together, related products |
| 7 | Trust Reinforcement | Light | Return policy, security, contact |

#### 3.3 Select Headline and CTA Types

Read `reference/ecommerce-headline-patterns.md` and `reference/ecommerce-cta-patterns.md`:

**For Dedicated LP:**
- Select headline type based on traffic source/awareness (from ecommerce-headline-patterns.md)
- Select CTA type based on traffic source (from ecommerce-cta-patterns.md)

**For Product Page:**
- Headline = Descriptive product title (not a persuasion headline)
- CTA = "Add to Cart" (action-driven)

#### 3.4 Present Page Outline for Approval

Present the architecture to the user:

```markdown
## Page Architecture

**Page Type:** {Dedicated LP / Product Page}
**Product:** {product name}
**Headline Type:** {type} — {formula}
**CTA Type:** {type} — {formula}

### Section Outline

| # | Section | Emphasis | Key Content |
|---|---------|----------|-------------|
| 1 | {section} | {emphasis} | {content approach} |
| 2 | {section} | {emphasis} | {content approach} |
| ... | | | |

Shall I proceed with this structure?
```

Use AskUserQuestion:
| Option | Description |
|--------|-------------|
| Yes, proceed | Generate copy with this architecture |
| Adjust sections | Make changes to emphasis or section order |

---

### Phase 4: Copy Generation

#### 4.1 Read References

Read:
- `reference/ecommerce-headline-patterns.md`
- `reference/ecommerce-cta-patterns.md`
- `reference/ecommerce-section-catalog.md`
- `context/offer-angles.md`
- `context/brand.md`

#### 4.2 Write Copy Section by Section

**If `PEER_CONTEXT` exists from Phase 0.25:** Bias copy generation across both page types:

- **Hero H1 / Product Title (LP Section 1) and Product Identity title (PP Section 1):**
  - Mirror `peer_context.search_term.product_naming_language` — use buyer phrases, not brand-internal taxonomy. Example: if buyers search "waterproof leather hiking boots", the H1/title should contain that exact noun phrase, not "premium outdoor footwear."
  - On Product Page, the descriptive title MUST contain the top n-gram phrase verbatim where SKU naming permits.
- **Hero tagline / Sub-headline:**
  - Lead with `peer_context.offer.lead_offer_angle`. If guarantee → tagline anchors on guarantee. If free shipping → anchors on speed/cost. If bundle → anchors on bundled value. If discount → anchors on savings.
  - Cross-check against `peer_context.competitive.competitor_weak_axis`. Where peers disagree (e.g., offer says "discount" but competitive says competitors are weak on delivery), prefer the competitive axis for differentiation, keep the offer angle for proof, and surface the conflict in the architecture confirmation.
- **Customer Evidence (LP S2) / Social Proof (PP S4):**
  - If `peer_context.quality_score.lpe_avg = below avg`, increase review density (target 5+ curated reviews on LP, 3+ on PP) and add an above-the-fold rating bar.
  - Annotate review placeholders with peer-driven specificity: "[Replace with real review — must reference {peer_context.competitive.competitor_weak_axis} (e.g., delivery speed)]".
- **Product Benefits (LP S3) / Product Details (PP S5):**
  - Frame outcomes around the differentiation axis. If competitor is weak on delivery, lead with "Arrives in X days" as a benefit. If weak on guarantee, lead with risk reversal.
  - Where `peer_context.quality_score.ar_keyword_gaps` exists, ensure benefit headers contain those keyword phrases for AR repair.
- **Purchase Confidence (LP S5) / Trust Reinforcement (PP S7):**
  - Lead with `peer_context.offer.lead_offer_angle` if it is guarantee or returns. Use `peer_context.offer.trust_angles` verbatim for badge text.
  - If `peer_context.tracking.status` is not Fresh, add a soft note in the wireframe comment block (HTML comment) reminding implementer to verify checkout/transaction tracking — does NOT show on rendered page.
- **Act Now / Urgency (LP S6):**
  - Use only if `peer_context.offer.urgency_authentic = Y`. Otherwise the architecture phase will have demoted it; copy this phase echoes that — emit a single-line note "[Urgency demoted: no authentic urgency anchor in offer-audit]" instead of urgency copy.
- **Cross-sell (PP S6) / Complete Your Purchase (LP S7):**
  - Use `peer_context.search_term.category_phrases` and `peer_context.keyword.theme_clusters` to label related-product anchors and category breadcrumbs (PP only — LP has no category nav).
- **CTA microcopy:**
  - LP CTAs: prepend/append the lead offer angle (e.g., "Get mine — free 60-day returns").
  - PP CTA stays "Add to Cart" but the supporting line under the button uses `peer_context.competitive.competitor_weak_axis` (e.g., "Ships in 24h. 60-day returns.").
- Annotate every peer-driven copy line with source: *(peer: {skill-name} → {field})*.

**If `AUDIT_COPY_SEEDS` exists from Phase 0.5:** Use the optimizer's recommended copy as starting points instead of generating from scratch:
- **Product Showcase/Hero tagline:** Present the optimizer's recommended headline as the primary option. Generate 1-2 alternatives. Present all for user selection.
- **Hero CTA:** Use the optimizer's recommended CTA text as default. Generate 1 alternative.
- **Product Benefits:** Seed with the optimizer's outcome-focused rewrites. Apply feature-to-outcome translation on top.
- **Purchase Confidence / Guarantee:** Use the optimizer's recommended badge text verbatim.
- **Act Now / Urgency:** Use the optimizer's recommended urgency text as starting point.
- **Customer Evidence / Social Proof:** Mark review placeholders with the specific gaps from audit D07 (e.g., "[Replace with real review: PHOTO REQUIRED, job title + company REQUIRED, specific result with number REQUIRED]").
- **FAQ items:** Adapt items that scored PASS in audit D08 rather than generating from scratch.
- **Trust signals:** Preserve strong signals identified in audit D06 (e.g., review counts, marketplace ratings).
- Annotate copy with source: *(from optimize report P2 Fix #N)* where applicable.

**For Dedicated Ecommerce LP:**

**Section 1: Product Showcase**
- Key differentiator tagline (under 10 words)
- Sub-headline (mechanism or proof)
- Price display (current, original if discounted, savings)
- CTA button text
- Visual placeholder description (product hero shot)

**Section 2: Customer Evidence**
- Aggregate rating headline ("4.8/5 from 1,200+ reviews")
- 3-5 curated review placeholders using formula: "[Specific result + before/after. E.g., 'Wore these in a downpour, feet stayed completely dry.' — Sarah K., Verified Buyer]"
- UGC photo grid placeholders
- Mark all as `[Replace with real customer review]`

**Section 3: Product Benefits**
- 3-5 benefit cards using feature-to-outcome translation
- Each benefit: outcome headline + supporting detail
- Tie benefits to customer evidence when possible

**Section 4: The Details**
- Specifications table (materials, dimensions, care)
- What's included list
- Comparison table (if applicable)

**Section 5: Purchase Confidence**
- Guarantee statement (from Q3 shipping/returns)
- Shipping detail
- Size/fit guidance (if applicable)
- 5-7 FAQ items addressing Q7 objections

**Section 6: Act Now (if not skipped)**
- Urgency headline based on Q5 answer
- Specific deadline/quantity placeholder `[Replace with real deadline]`

**Section 7: Complete Your Purchase**
- Value recap (product + top 3 benefits + guarantee)
- Price display (repeat with savings)
- CTA button text (strongest version)
- Express checkout mention
- Final microcopy (guarantee reminder)

**For Product Page:**

**Section 1: Product Identity**
- Product title (descriptive, includes key attributes)
- One-line benefit summary
- Price display
- Variant selectors (size, color)
- Gallery placeholder descriptions (hero, angles, lifestyle, detail, scale)

**Section 2: Offer Stack**
- Shipping info display
- Return policy summary
- Availability indicator

**Section 3: Add-to-Cart Action**
- CTA: "Add to Cart"
- Microcopy: shipping/returns promise
- Express checkout mention

**Section 4: Social Proof**
- Star rating + review count
- 2-3 review placeholders
- Review sorting options

**Section 5: Product Details**
- Benefit-first product description
- Specs table
- FAQ section (5-7 items)

**Section 6: Cross-sell**
- "Frequently bought together" items (3 placeholder products)
- Bundle savings

**Section 7: Trust Reinforcement**
- Return policy (expanded)
- Secure checkout badge
- Contact options
- Certification badges (if applicable)

#### 4.3 Copy Guidelines

- **Product is the pitch:** Images and reviews sell, copy supports
- **Visitor-first language:** "Your feet stay dry" not "Our waterproof membrane"
- **Specific numbers:** "Lasts 500+ washes" not "Long-lasting"
- **Benefit translation:** Every feature must answer "So what?"
- **First-person CTAs:** "Get mine" not "Get yours"
- Use exact phrases from `context/offer-angles.md` where they fit naturally
- Match the brand voice from `context/brand.md`
- Active voice, no hedging
- Mark anything that needs real content with `[Replace with...]`

#### 4.4 Present Copy for Approval

Present the full copy draft organized by section:

```markdown
## Copy Draft

### {Section 1 Name}
**Headline/Tagline:** {text}
**Sub-headline:** {text}
**Price:** {display}
**CTA:** {button text}
**Visual:** [{placeholder description}]

### {Section 2 Name}
{content}

...

---
Ready to generate the HTML?
```

Use AskUserQuestion:
| Option | Description |
|--------|-------------|
| Yes, generate HTML | Proceed to HTML generation |
| Revise copy | Make changes before generating |

---

### Phase 5: HTML Generation

#### 5.1 Read HTML Template

Read `reference/ecommerce-html-template.md` for the base HTML structure, CSS variables, and section snippets.

#### 5.2 Build HTML

1. Start with the base HTML structure from the template
2. Populate `:root` CSS variables with colors from Phase 2
3. **If Dedicated LP:** Use the Dedicated LP section snippets (product-showcase hero, no navigation)
4. **If Product Page:** Use the Product Page section snippets (gallery + info layout, header with nav placeholder, breadcrumbs)
5. Generate each section using the approved copy from Phase 4 and the section snippets from the template
6. Apply section emphasis: skip sections marked as "Skip", use lighter content for "Compact" page length
7. Use the appropriate placeholder classes (`.placeholder-product-image`, `.placeholder-customer-photo`, `.placeholder`)
8. **CTA placement:**
   - Dedicated LP: Minimum 4 CTAs (hero, after evidence, after confidence, final section)
   - Product Page: CTA at position 3, sticky mobile bar described
9. Alternate section backgrounds via `section:nth-child(even)` CSS rule
10. **If `PEER_CONTEXT` exists from Phase 0.25:** bias trust badges, review placements, and urgency elements:
    - **Trust badges:** Density and placement scale with `peer_context.quality_score.lpe_avg`. Below avg → above-the-fold trust strip on Dedicated LP, sticky trust band near Add-to-Cart on Product Page. Use `peer_context.offer.trust_angles` for badge labels (verbatim).
    - **Review placements:** If LPE is below avg, render a star-rating-and-review-count micro-component in the hero (LP) or directly under product title (PP), in addition to the main reviews section. Mark explicitly with `[Replace with real aggregate rating]`.
    - **Urgency elements:** Render only if `peer_context.offer.urgency_authentic = Y` AND Q5 supplied an urgency type. Otherwise omit the Act Now visual block entirely (LP) and skip the urgency callout under Add-to-Cart (PP). Add an HTML comment: `<!-- Urgency block omitted: peer offer-audit found no authentic urgency anchor -->`.
    - **Differentiation lead-line:** Render a dedicated `<div class="differentiation-strip">` line in the hero (LP) or Offer Stack (PP) reflecting `peer_context.competitive.competitor_weak_axis` (e.g., "Ships in 24h" / "60-day returns" / "Premium leather, lifetime guarantee").
    - **Tracking warning HTML comment:** If `peer_context.tracking.status` is not Fresh, prepend the saved file with an HTML comment block listing the events the implementer must verify (`view_item`, `add_to_cart`, `begin_checkout`, `purchase` with transaction value, AOV, ROAS attribution). Does not render visibly.

#### 5.3 Output Rules

- Self-contained: all CSS in `<style>`, no external dependencies
- No JavaScript
- **Dedicated LP:** No navigation bar, no footer links (one-page-one-goal)
- **Product Page:** Include header nav placeholder, breadcrumbs, footer placeholder
- Responsive: single breakpoint at 768px, grids collapse, CTAs go full-width, gallery stacks
- Product image placeholders use `.placeholder-product-image` with descriptive text and dimensions
- Customer photo placeholders use `.placeholder-customer-photo`
- CTA button text is consistent across all placements
- Price visible above the fold in both page types

#### 5.4 Save File

Create output directory if needed:

```bash
mkdir -p created/landing-pages
```

Save the HTML file:
- **Dedicated LP:** `{YYYYMMDD}_ecom-lp_{product}.html`
- **Product Page:** `{YYYYMMDD}_product-page_{product}.html`
- **Product name:** From product details in Phase 1, sanitized (lowercase, hyphens, no special chars)

---

### Phase 6: Quality Validation

#### 6.1 Read Checklist

Read `reference/ecommerce-quality-checklist.md`.

#### 6.2 Validate Against Page Type Checks

Run the appropriate checks for the selected page type:

**For Dedicated LP:** Run Cross-page checks + Dedicated Ecommerce LP checks (Structure, Customer Evidence, Product Benefits, The Details, Purchase Confidence, Act Now, Complete Your Purchase, CTA Placement, Copy Quality, One-Page-One-Goal, Brand & Message Match).

**For Product Page:** Run Cross-page checks + Product Page checks (Product Identity, Offer Stack, Add-to-Cart Action, Social Proof, Product Details, Cross-sell and Trust, Brand & Message Match).

**Wireframe adaptations:**
- Skip "Page loads in under 3 seconds" (not applicable to wireframe)
- Skip "Conversion tracking fires correctly" (not applicable to wireframe)
- Skip "Express pay buttons are functional" (not applicable to wireframe)
- Check layout, section order, copy quality, CTA placement, brand colors, responsiveness

#### 6.3 Present Results

```markdown
## Quality Validation Results

**Page Type:** {Dedicated LP / Product Page}

| Category | Pass | Fail | Score |
|----------|------|------|-------|
| Cross-page: Performance & Mobile | X/5 | Y/5 | Z% |
| Cross-page: Trust & Policy | X/4 | Y/4 | Z% |
| {category} | X/N | Y/N | Z% |
| ... | | | |
| **Total** | **X/N** | **Y/N** | **Z%** |

### Action Items
1. {failing item} → {how to fix}
2. ...
```

If any items fail, fix them in the HTML file before proceeding.

---

### Phase 7: Summary & Handoff

Present the final summary:

```markdown
## Ecommerce Page Wireframe Complete

### Output
- **File:** `created/landing-pages/{filename}.html`
- **Page Type:** {Dedicated LP / Product Page}
- **Open in browser to preview**

### Page Structure
| Section | Key Content | Status |
|---------|-------------|--------|
| {Section 1} | {summary} | Complete |
| {Section 2} | {summary} | Complete (placeholders) |
| ... | | |

### Brand Match
- **Colors:** {primary}, {accent}, {background}
- **Fonts:** {heading font}, {body font}
- **Source:** {palette.md / manual / defaults}

### Quality Score: {X}%

### Placeholders to Replace
- [ ] Product images (hero, angles, lifestyle, detail, scale)
- [ ] Customer reviews (5-10 with photos and specific results)
- [ ] Customer UGC photos
- [ ] Urgency deadline/quantity (if applicable)
- [ ] Cross-sell products (if product page)
- [ ] {other [Replace with...] items}

### Audit Integration (if applicable)
- **Informed by:** {lp-audit.md ({date}, {score}%) | lp-optimize-{action}.md ({date}) | N/A}
- **Original page:** {URL from audit | N/A}
- **Compare after live:** Run `/lp-audit` on the new page and compare against the original score ({original_score}%)

### Cross-skill context applied

| Peer | Status | What it shaped on this page |
|------|--------|----------------------------|
| /tracking-specialist | {Fresh / Stale Nd / Missing} | {ecom tracking warning surfaced in HTML comment + handoff notes / N/A} |
| /strategy-specialist | {Fresh / Stale Nd / Missing} | {pricing emphasis = {discount-led / margin-led / value-led} / fell back to brand defaults} |
| /offer-auditor | {Fresh / Stale Nd / Missing} | {hero lead angle = {angle}; urgency block {kept / demoted / omitted}} |
| /competitive-analyst | {Fresh / Stale Nd / Missing} | {differentiation axis = {price / delivery / quality / guarantee / breadth} foregrounded in hero / Offer Stack} |
| /search-term-auditor | {Fresh / Stale Nd / Missing} | {top n-grams used in H1 / product title: "{phrase}"} |
| /keyword-auditor | {Fresh / Stale Nd / Missing} | {theme clusters used for cross-sell / category copy} |
| /quality-score-auditor | {Fresh / Stale Nd / Missing} | {LPE = {below avg / avg / above avg} → trust signal density {raised / standard}} |
| /lp-auditor | {Fresh / Stale Nd / Missing} | {ecom module D38–D40 score informed structural emphasis} |
| /budget-auditor | {Fresh / Stale Nd / Missing} | {informational only} |
| /bidding-auditor | {Fresh / Stale Nd / Missing} | {posture context: {Smart Shopping / PMax / manual} → CTA wording} |

**Dirty audits surfaced as warnings (informational, not blocking):**
- {list any M/B dirty notes from Phase 0.25.3, or "None — all peer audits Fresh"}

### Client Handoff Notes
1. **Review wireframe** in browser (desktop + mobile views)
2. **Collect real assets:**
   - Product photography (minimum 5 shots for product page, hero + lifestyle for LP)
   - Customer reviews with verified buyer status and photos
   - Customer photos/videos for UGC section
   - Trust badges (certifications, security, payment method logos)
3. **Implement** in your ecommerce platform (Shopify, WooCommerce, BigCommerce, etc.)
4. **Configure:**
   - Variant selectors (if product page)
   - Express checkout integrations (Apple Pay, Google Pay)
   - Review widget integration
   - Inventory/stock indicators
5. **After live:** Test full purchase flow on mobile

### Suggested Next Steps
1. Gather real product images and customer reviews
2. Implement in ecommerce platform
3. Set up conversion tracking (product view, add-to-cart, purchase)
4. Launch and monitor for 7 days
5. Run `/lp-audit` to score the live page (includes ecommerce module D38-D40)
6. Run `/lp-optimize` for targeted fix guidance on any issues found
7. If Dedicated LP: A/B test headline or urgency approach
8. If Product Page: Monitor add-to-cart rate, optimize if below benchmark
```

---

## Error Handling

| Error | Message |
|-------|---------|
| Missing `context/brand.md` | "Run `/ads-context [URL]` first to gather brand context" |
| Missing `context/offer-angles.md` | "Run `/offer-maker angles` first to extract offer message angles" |
| Missing `context/brand-colours/palette.md` | "Run `/ads-context [URL]` first to extract brand colours" |
| Palette file incomplete (missing roles) | "Palette file found but some colour roles are missing. Check the palette.md file or re-run `/ads-context [URL]`" |

---

## Integration Points

### Uses (reads from):
- `context/brand.md` — Brand voice, tone, homepage URL, company name
- `context/offer-angles.md` — 6 message angles with headline-ready phrases
- `context/brand-colours/palette.md` (optional) — Brand colours and fonts extracted by `/ads-context`
- `context/business.md` (optional) — Business goals, constraints
- `context/google-ads/data/keywords.csv` (optional) — Primary keywords for message match
- `context/google-ads/data/ads.csv` (optional) — Existing ad copy for message match
- `context/analysis/lp-audit.md` (optional) — Prior audit findings for audit-informed builds (Phase 0.5) and ecom module D38–D40 benchmarks (Phase 0.25, ≤ 14 days)
- `context/analysis/lp-optimize-*.md` (optional) — Prior optimization recommendations with specific copy rewrites (Phase 0.5)
- `context/analysis/quality-score-audit.md` (optional) — Peer context: LPE for trust signal density, AR keyword gaps (Phase 0.25, ≤ 7 days)
- `context/analysis/search-term-audit.md` (optional) — Peer context: top n-grams for product naming language (Phase 0.25, ≤ 7 days)
- `context/analysis/keyword-audit.md` (optional) — Peer context: theme clusters for category-page copy (Phase 0.25, ≤ 7 days)
- `context/analysis/budget-audit.md` (optional) — Peer context: budget posture, informational only (Phase 0.25, ≤ 7 days)
- `context/analysis/bidding-audit.md` (optional) — Peer context: posture (Smart Shopping / PMax) for CTA wording (Phase 0.25, ≤ 7 days)
- `context/analysis/competitive-audit.md` (optional) — Peer context: competitor weak axis for differentiation (Phase 0.25, ≤ 14 days)
- `context/analysis/offer-audit.md` (optional) — Peer context: lead offer angle for hero, urgency authenticity (Phase 0.25, ≤ 30 days)
- `context/analysis/tracking-audit.md` (optional) — Peer context: ecommerce conversion tracking integrity warning (Phase 0.25, ≤ 30 days)
- `context/analysis/strategy-audit.md` (optional) — Peer context: pricing emphasis and posture (Phase 0.25, ≤ 30 days)
- `reference/ecommerce-persuasion-sequence.md` — Ecommerce Persuasion Sequence, decision gate, section emphasis
- `reference/ecommerce-section-catalog.md` — Content patterns per section per page type
- `reference/ecommerce-headline-patterns.md` — 6 headline types with ecommerce formulas
- `reference/ecommerce-cta-patterns.md` — 5 CTA types with ecommerce formulas
- `reference/ecommerce-quality-checklist.md` — Page-type-specific validation checklist
- `reference/ecommerce-html-template.md` — CSS variables, section snippets, responsive rules

### Produces (writes to):
- `created/landing-pages/{YYYYMMDD}_ecom-lp_{product}.html` — Dedicated ecommerce LP wireframe
- `created/landing-pages/{YYYYMMDD}_product-page_{product}.html` — Product page wireframe

### Downstream:
- Client review and feedback
- Implementation in ecommerce platform (Shopify, WooCommerce, BigCommerce, etc.)
- Collection of real assets (product photos, reviews, UGC)
- Conversion tracking setup
- `/quality-score-auditor components` validation on the live version (LP Experience module)

---

## Output Location

All files are created relative to the **current working directory**:
- Output directory: `created/landing-pages/`
- Creates directory if it doesn't exist
- Each run creates a new date-stamped file (never overwrites)
