# Execute — Generate Angle Variants (E05)

Read when `/offer-maker variants` is invoked.

## Prerequisites

1. Check `context/offer-angles.md` exists
   - If missing: "No angles found. Run `/offer-maker angles` first to extract your base angles."
   - If exists: proceed
2. Optionally read `context/google-ads/data/search-terms.csv` for customer language

---

## Flow

### Step 1: Load Existing Angles

Read `context/offer-angles.md`. For each of the 6 angles, extract the existing headline-ready phrases.

Present current state:
```
Current angles and phrases:

1. Problem/Pain: "Stop Wasting Ad Spend" (22 chars), "End Agency Churn" (16 chars)
2. Value Prop: "More Demos, Lower CPA" (21 chars), "Google Ads for SaaS" (19 chars)
3. USPs: "SaaS-Only Specialists" (21 chars), "8+ Years SaaS Focus" (19 chars)
...
```

### Step 2: Generate Variants

For each angle, generate 3-5 alternative headline phrases using different framing techniques:

**Variant techniques:**

| Technique | What it does | Example |
|-----------|-------------|---------|
| **Outcome flip** | Reframe from avoiding pain to achieving gain | "Stop Wasting Spend" → "Get More From Every $" |
| **Specificity boost** | Add numbers, percentages, timeframes | "Fast Results" → "Results in 48 Hours" |
| **Customer voice** | Use language from search terms/reviews | "Improve Efficiency" → "End the Spreadsheet Chaos" |
| **Direct address** | Speak to the reader directly | "Professional Service" → "Your Growth, Our Focus" |
| **Proof injection** | Add a data point | "Trusted Agency" → "47 SaaS Clients Served" |
| **Question format** | Ask instead of tell | "Lower CPA" → "CPA Too High?" |
| **Contrast frame** | Compare old vs. new way | "Better Headshots" → "Skip the Photo Studio" |

### Step 3: Validate All Variants

For each variant:
- Verify <=30 characters
- Verify it communicates the same angle (don't drift to a different angle)
- Verify it's genuinely different from existing phrases (not just synonym swaps)
- Verify it could work as a standalone headline (no context needed)

### Step 4: Group for A/B Testing

Suggest testing groups:

```
Testing recommendation:

Group A (current phrases — control):
- H2: "More Demos, Lower CPA"
- H3: "SaaS-Only Specialists"

Group B (outcome-focused variants):
- H2: "Cut CPA by 40%"
- H3: "We Only Do SaaS"

Group C (proof-focused variants):
- H2: "47 SaaS Clients Served"
- H3: "Avg 40% CPA Reduction"
```

---

## Output

Append to `context/offer-angles.md` (don't overwrite existing content):

```markdown
---

## Headline Variants (Generated {YYYY-MM-DD})

### 1. Problem/Pain Variants
**Original:** "[phrase 1]", "[phrase 2]"

| # | Variant | Chars | Technique |
|---|---------|-------|-----------|
| 1 | "[variant]" | [X] | Outcome flip |
| 2 | "[variant]" | [X] | Specificity boost |
| 3 | "[variant]" | [X] | Customer voice |
| 4 | "[variant]" | [X] | Question format |

### 2. Value Proposition Variants
**Original:** "[phrase 1]", "[phrase 2]"

| # | Variant | Chars | Technique |
|---|---------|-------|-----------|
| 1 | "[variant]" | [X] | [technique] |
...

[Repeat for all 6 angles]

---

## Suggested A/B Test Groups

### Test 1: {angle being tested}
- **Control:** [current phrase]
- **Variant A:** [variant phrase] — {technique used}
- **Variant B:** [variant phrase] — {technique used}
- **Hypothesis:** {what we expect to learn}

[Repeat for top 2-3 angles worth testing]
```

---

## Summary Presentation

```
## Angle Variants Generated

**Variants per angle:** 3-5
**Total new phrases:** {count}

| Angle | Original Count | New Variants | Best New Phrase |
|-------|---------------|-------------|-----------------|
| Problem/Pain | 2-3 | +{X} | "[best variant]" |
| Value Prop | 2-3 | +{X} | "[best variant]" |
| USPs | 2-3 | +{X} | "[best variant]" |
| Value Boosters | 2-3 | +{X} | "[best variant]" |
| Social Proof | 2-3 | +{X} | "[best variant]" |
| Risk Removal | 2-3 | +{X} | "[best variant]" |

### What's Next?
1. Review variants in context/offer-angles.md
2. Run `/rsa-maker` to compose RSAs using both original and variant phrases
3. Set up A/B tests with the suggested test groups
```
