# Execute — Craft Offer Angles (E02)

Read when `/offer-maker angles` is invoked.

## Entry Decision

Check if `context/offer-angles.md` exists and evaluate state:

1. **EXISTS with all 6 angles populated AND no `--refresh` flag?**
   - Report: "Angles exist. Jumping to Phase 3 (reprioritize for campaign)."
   - Skip to Phase 3

2. **EXISTS but incomplete OR `--refresh` flag present?**
   - Report: "Refreshing angles. Starting from Phase 0."
   - Start at Phase 0

3. **DOES NOT EXIST?**
   - Report: "No angles found. Starting extraction."
   - Start at Phase 0

## Prerequisites

**Check for `context/brand.md`:**
- If exists: Continue — will pre-populate ~8 of 13 offer elements
- If missing: Ask user: "Brand context not found. Run `/ads-context-gatherer [URL]` first, or continue with manual interview?"

**Check for `context/business.md`:**
- If exists: Use for win themes, competitive positioning, offer details
- If missing: STOP — tell user to run `/business-context-gatherer` first

**Check offer strength:** If business.md has no Offer section or offer seems thin, suggest: "Consider running `/offer-maker create` first to build a solid offer foundation."

---

## Phase 0: Classify Traffic Temperature

### 0.1 Present Traffic Temperature Matrix

Show user:

| Traffic Source | Typical Stage | Temperature |
|----------------|---------------|-------------|
| Brand Search | Most Aware | Hot |
| Competitor Search | Product Aware | Hot |
| Product/Service Search | Solution Aware | Warm |
| Problem/Symptom Search | Problem Aware | Cold |
| Display prospecting | Unaware - Problem Aware | Cold |
| YouTube prospecting | Unaware - Problem Aware | Cold |
| Remarketing | Product - Most Aware | Hot |

### 0.2 Gather Classification

Ask user (use AskUserQuestion):

**Question:** "What is your primary traffic source for this campaign?"

**Options:**
1. Brand Search (Hot)
2. Competitor Search (Hot)
3. Product/Service Search (Warm)
4. Problem/Symptom Search (Cold)
5. Display/YouTube Prospecting (Cold)
6. Remarketing (Hot)

If `--campaign` flag provided, use that value for campaign name.

### 0.3 Set Angle Priorities

| Angle | Cold | Warm | Hot |
|-------|------|------|-----|
| Problem/Pain | LEAD | Include | Light |
| Value Proposition | Include | LEAD | Include |
| USPs | Light | LEAD | LEAD |
| Value Boosters | Skip | Include | LEAD |
| Social Proof | Light | Include | LEAD |
| Risk Removal | Skip | Include | LEAD |

---

## Phase 1: Document Offer Facts

### 1.1 Pre-populate from Context

Read `context/brand.md` and `context/business.md` to pre-fill:

| # | Element | Source | Pre-fill from |
|---|---------|--------|---------------|
| 1 | What is it? | brand.md | Company Overview, Products & Services |
| 2 | Who is it for? | brand.md | Target Audience |
| 3 | What problem does it solve? | brand.md | Pain Points Addressed |
| 4 | What symptoms? | **ASK USER** | — |
| 5 | Failed alternatives? | business.md | Win Themes, Competitive Strategy |
| 6 | Cost of NOT solving? | **ASK USER** | — |
| 7 | How does it work? | brand.md | Products & Services |
| 8 | Main benefit? | brand.md | Summary, USPs |
| 9 | What makes it different? | brand.md | Unique Selling Propositions |
| 10 | What's included? | brand.md | Products & Services |
| 11 | What proof exists? | brand.md | Trust Signals |
| 12 | What reduces risk? | brand.md | Guarantees/Promises |
| 13 | Price/offer? | brand.md | Pricing |

### 1.2 Interview for Gaps

For elements marked **ASK USER** or not found in context, use questions from `reference/interview-questions.md`.

Present pre-filled elements for confirmation:
> I found the following from your brand context. Please confirm or correct:
>
> **What is it?** [pre-filled value]
> **Who is it for?** [pre-filled value]
> ...

Then ask for missing elements:
> I need additional information for complete angle extraction:
>
> **What symptoms does your audience experience daily?**
> **What's the cost of NOT solving this problem?**

---

## Phase 2: Extract 6 Angles

For each angle, extract from Phase 1 data and generate 2-3 headline-ready phrases (each <=30 characters).

### Problem/Pain Points
**Question it answers:** "Do you understand my struggle?"

| Element | Source |
|---------|--------|
| Primary frustration | #3, #4 |
| Daily symptoms | #4 |
| Failed alternatives | #5 |
| Cost of inaction | #6 |

**Output:** 2-3 headline-ready phrases <=30 chars each

### Value Proposition
**Question it answers:** "What do you offer?"

| Element | Source |
|---------|--------|
| Core offer | #1, #7 |
| Primary benefit | #8 |
| How it works | #7 |

**Output:** 2-3 headline-ready phrases <=30 chars each

### USPs (Unique Selling Points)
**Question it answers:** "Why are you better/different?"

| Element | Source |
|---------|--------|
| Speed advantage | #9 |
| Ease advantage | #9 |
| Technology/Method | #9 |
| Specialization | #9 |
| Quantified proof | #11 |

**Output:** 2-3 headline-ready phrases <=30 chars each

### Value Boosters
**Question it answers:** "What else do I get?"

| Element | Source |
|---------|--------|
| Included extras | #10 |
| Bonus features | #10 |
| Convenience perks | #10 |
| Quantities/Specifics | #10 |

**Output:** 2-3 headline-ready phrases <=30 chars each

### Social Proof & Authority
**Question it answers:** "Can I trust you?"

| Element | Source |
|---------|--------|
| Customer count | #11 |
| Ratings/Reviews | #11 |
| Named customers | #11 |
| Credentials | #11 |
| Results achieved | #11 |

**Output:** 2-3 headline-ready phrases <=30 chars each

### Risk Removal
**Question it answers:** "What if I don't like it?"

| Element | Source |
|---------|--------|
| Guarantee type | #12 |
| Trial structure | #12 |
| Commitment level | #12 |
| Specific terms | #12, #13 |

**Output:** 2-3 headline-ready phrases <=30 chars each

### Headline Phrase Guidelines

- **Max 30 characters** (Google Ads headline limit)
- **Use customer language** from search terms if available (`context/google-ads/data/search-terms.csv`)
- **Be specific**, not generic (e.g., "4.6 on 800+ Reviews" not "Highly Rated")
- **Include proof** where possible (numbers, percentages, timeframes)

---

## Phase 3: Prioritize for Traffic

Apply Phase 0 classification to map angles to headline slots:

**Standard 8-slot RSA structure:**

| Slot | Purpose |
|------|---------|
| H1 | Relevance — keyword insertion `{KeyWord:Default}` |
| H2-H3 | LEAD angles — top priority for this traffic |
| H4-H5 | Include angles — secondary priority |
| H6 | LEAD (secondary) — additional high-priority |
| H7 | CTA — call to action |
| H8 | Light angle — optional/lower priority |

---

## Phase 4: Validate Quality

Run all extracted angles through `reference/offer-angle-quality-checklist.md`.

For each angle, verify:
- Specific (not generic)
- Provable (not just asserted)
- Customer language (not corporate speak)
- 2-3 headline phrases (<=30 chars each)

If any angle fails: flag with recommended action from the gap identification table.

---

## Output

Write to `context/offer-angles.md` using this format:

```markdown
# Offer Angles - [Product Name]

**Last updated:** [YYYY-MM-DD]
**Status:** [Complete / Needs attention]

---

## Traffic Classification

| Field | Value |
|-------|-------|
| Campaign/Traffic | [e.g., "Non-brand Search: AI presentation"] |
| Awareness Stage | [Problem Aware / Solution Aware / Product Aware / Most Aware] |
| Temperature | [Cold / Warm / Hot] |

## Angle Priorities

| Priority | Angles | Headline Slots |
|----------|--------|----------------|
| LEAD | [list] | H2, H3, H6 |
| Include | [list] | H4, H5 |
| Light | [list] | H8 |
| Skip | [list] | — |

---

## Extracted Angles

### 1. Problem/Pain Points
**Question:** "Do you understand my struggle?"

| Element | Extraction |
|---------|------------|
| Primary frustration | [text] |
| Daily symptoms | [text] |
| Failed alternatives | [text] |
| Cost of inaction | [text] |

**Headline-ready phrases:**
- "[phrase 1]" ([X] chars)
- "[phrase 2]" ([X] chars)
- "[phrase 3]" ([X] chars)

**Validation:** [Pass / Needs work: reason]

---

[Repeat for all 6 angles: Value Proposition, USPs, Value Boosters, Social Proof & Authority, Risk Removal]

---

## Slot Distribution

| Slot | Angle | Asset |
|------|-------|-------|
| H1 | Relevance | `{KeyWord:Default}` |
| H2 | [angle] | "[phrase]" |
| H3 | [angle] | "[phrase]" |
| H4 | [angle] | "[phrase]" |
| H5 | [angle] | "[phrase]" |
| H6 | [angle] | "[phrase]" |
| H7 | CTA | "[phrase]" |
| H8 | [angle] | "[phrase]" |

---

## Quality Validation Summary

| Angle | Status | Notes |
|-------|--------|-------|
| Problem/Pain | [Pass / Needs work] | [notes] |
| Value Proposition | [Pass / Needs work] | [notes] |
| USPs | [Pass / Needs work] | [notes] |
| Value Boosters | [Pass / Needs work] | [notes] |
| Social Proof | [Pass / Needs work] | [notes] |
| Risk Removal | [Pass / Needs work] | [notes] |
```

---

## Summary Presentation

After writing output, present:

```
## Offer Angles Extracted

**Product:** [name]
**Traffic:** [campaign/type] ([temperature])
**Status:** [Complete / X of 6 angles need attention]

| Angle | Status | Lead Phrase |
|-------|--------|-------------|
| Problem/Pain | [status] | "[phrase]" |
| Value Proposition | [status] | "[phrase]" |
| USPs | [status] | "[phrase]" |
| Value Boosters | [status] | "[phrase]" |
| Social Proof | [status] | "[phrase]" |
| Risk Removal | [status] | "[phrase]" |

### What's Next?
1. Review angles in context/offer-angles.md
2. Address any quality issues flagged
3. Run `/rsa-maker` to compose RSAs from these angles
4. Run `/offer-maker variants` to generate A/B test alternatives
```
