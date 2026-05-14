# RSA Composition SOP — Reference

Read during RSA creation. This is the assembly framework for building a complete Responsive Search Ad from offer angles.

## Why 7-8 Headlines (Not 15)

More headlines = more combinations = less data per combination = slower learning.

| # Headlines | # 3-Headline Combinations | Min. Impressions Needed |
|-------------|--------------------------|------------------------|
| 6 | 120 | 12,000 |
| 8 | 336 | 33,600 |
| 15 | 2,730 | 273,000 |

**Target: 7-8 headlines and 2-3 descriptions.**

## 4-Phase Framework

| Phase | Purpose | Output |
|-------|---------|--------|
| Phase 1: Headlines | Compose 7-8 headlines covering prioritized angles | 7-8 validated headlines |
| Phase 2: Descriptions | Compose 2-3 descriptions that expand without repeating | 2-3 validated descriptions |
| Phase 3: Extensions | Select and compose relevant extensions | Complete extension package |
| Phase 4: Deploy | Upload assets and configure settings | Live RSA |

---

## Phase 1: Compose Headlines

### Slot Distribution Template

| Slot | Headline Type | Purpose |
|------|--------------|---------|
| H1 | **Relevance Anchor** | Match the search query |
| H2 | **Value Proposition** | Core offer + main benefit |
| H3 | **USP / Benefit** | Why you're different |
| H4 | **Social Proof** | Trust + credibility |
| H5 | **Risk Removal** | Lower barrier to action |
| H6 | **Call-to-Action** | What to do next |
| H7 | **[Lead Angle x2]** | Second slot for priority angle |
| H8 | **(Optional)** | Only if high-volume ad group |

### H7 Assignment by Traffic Temperature

| Traffic | H7 Should Be |
|---------|-------------|
| Cold | Problem/Pain (second variation) |
| Warm | USP or Value Prop (second variation) |
| Hot | Social Proof or Risk Removal (second variation) |

### H1: Relevance Anchor Methods

| Method | When to Use |
|--------|------------|
| Static | Branded, sensitive, controlled |
| DKI `{KeyWord:Default}` | Extensive keyword lists |
| Keyword-level customizers | Need granular relevance control |

**DKI Rule:** Default text must stand alone. Bad: `{KeyWord:Products}`. Good: `{KeyWord:CRM Software}`.

### CTA Tone by Traffic Temperature

| Traffic | CTA Tone | Examples |
|---------|----------|---------|
| Cold | Soft, educational | "See How It Works", "Learn More" |
| Warm | Medium, exploratory | "Get Your Free Demo", "Compare Plans" |
| Hot | Direct, transactional | "Start Free Trial", "Get Started Now" |

### Headline Writing Process (H2-H7)

For each slot:
1. Identify the angle type from the slot distribution
2. Pull your proof point from `context/offer-angles.md`
3. Find a pattern in `reference/headline-angle-catalog.md`
4. Apply your proof point to the pattern
5. Verify <=30 characters

After writing all headlines, validate against `reference/headline-quality-checklist.md`.

---

## Phase 2: Compose Descriptions

### Description Strategy

Descriptions **expand on headlines** — they don't repeat them. Target: 2-3 descriptions.

| Slot | Pattern | Purpose |
|------|---------|---------|
| D1 | **Problem + Solution** | Validate pain, present your answer |
| D2 | **Proof + CTA** | Build trust, drive action |
| D3 | **(Optional) Offer + Urgency** | Promotion details + deadline |

**Include core keyword in D1:** Google bolds text matching the search query. More bold = more visual prominence.

### Description Writing Process

For each slot:
1. Use patterns from `reference/description-expansion-catalog.md`
2. Combine 2 angles per description (e.g., Problem + Solution, Proof + CTA)
3. Verify <=90 characters, target 75-90
4. Ensure no description simply restates a headline

After writing all descriptions, validate against `reference/description-quality-checklist.md`.

**Only include D3 if authentic urgency exists.** Fake scarcity damages trust.

---

## Phase 3: Extensions

### Core Extensions (Required)

| Extension | Minimum | Purpose |
|-----------|---------|---------|
| Sitelinks | 4 | Navigate to key pages |
| Callouts | 4 | Highlight benefits/features |
| Structured Snippets | 2 headers | Categorize offerings |
| Business Name | 1 | Brand identity |
| Business Logo | 1 | Visual recognition |

### Sitelink Strategy (Cover Different Intents)

| Intent | Example |
|--------|---------|
| Learn | "How It Works" |
| Compare | "See Pricing" |
| Trust | "Case Studies" |
| Try | "Free Demo" |

### Callout Strategy (Cover Different Benefits)

| Category | Example |
|----------|---------|
| Trust | "Google Premier Partner" |
| Value | "Free Consultation" |
| Speed | "Same-Day Response" |
| Risk | "No Contracts" |

**Key principle:** Extensions add information. They don't duplicate RSA content.

---

## Phase 4: Pinning Decisions

**Default: Don't pin.** Pinning restricts Google's optimization.

| When to Pin | Action |
|-------------|--------|
| Relevance anchor must always show | Pin H1 to Position 1 |
| Legal/compliance requirement | Pin required text |
| Brand guideline | Pin brand message to Position 1 or 2 |

| When NOT to Pin | Why |
|-----------------|-----|
| "I want this headline to show more" | Let Google optimize |
| "This is my best headline" | Test it, don't assume |

---

## Common Failures

| Failure | Fix |
|---------|-----|
| Too many headlines (15) | Stick to 7-8 |
| All headlines same angle | One headline per angle type |
| Descriptions repeat headlines | Descriptions expand, not repeat |
| Weak DKI default | Default must stand alone |
| Wrong CTA tone | Match CTA to awareness stage |
| Pinned everything | Pin only H1 if anything |
| Skipped extensions | Extensions are required |
