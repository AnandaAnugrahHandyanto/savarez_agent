# Interview Questions for Offer Angle Extraction

Reference file for `/offer-maker` skill. Contains structured questions for Phase 0 (Classification) and Phase 1 (Offer Facts) interviews.

---

## Phase 0: Traffic Classification Questions

### Primary Traffic Source

**Question:** What is your primary traffic source for this campaign?

**Options:**
1. **Brand Search** - People searching for your brand name
   - Temperature: Hot
   - Awareness: Most Aware

2. **Competitor Search** - People searching for competitor names
   - Temperature: Hot
   - Awareness: Product Aware

3. **Product/Service Search** - People searching for what you sell
   - Temperature: Warm
   - Awareness: Solution Aware

4. **Problem/Symptom Search** - People searching for problems you solve
   - Temperature: Cold
   - Awareness: Problem Aware

5. **Display/YouTube Prospecting** - Targeting new audiences
   - Temperature: Cold
   - Awareness: Unaware to Problem Aware

6. **Remarketing** - People who've visited your site
   - Temperature: Hot
   - Awareness: Product to Most Aware

### Campaign Specificity

**Question:** What specific keywords or themes define this campaign?

Examples:
- "Non-brand Search: AI presentation software"
- "Competitor Search: Canva alternatives"
- "Problem Search: slow presentation creation"

---

## Phase 1: Offer Facts Interview

### Questions for Missing Elements

Use these questions when context files don't provide sufficient information.

---

### Element 4: Symptoms (Usually missing from brand.md)

**Question:** What symptoms does your audience experience daily?

**Prompts to help user respond:**
- What frustrates them on a regular basis?
- What takes too long or feels too hard?
- What do they complain about to colleagues?
- What's the thing that makes them say "there has to be a better way"?

**Example responses we're looking for:**
- "Spending hours on slides that should take minutes"
- "Constantly reformatting after copying from other decks"
- "Starting from scratch every time instead of building on past work"

---

### Element 5: Failed Alternatives (Partial in business.md)

**Question:** What have your customers tried before that didn't work?

**Prompts to help user respond:**
- What solutions did they try before finding you?
- What's wrong with the "default" way of doing this?
- Why didn't competitor solutions work for them?
- What workarounds were they using?

**Example responses we're looking for:**
- "Tried Canva but it's not professional enough"
- "Used templates but they all look the same"
- "Hired designers but too slow and expensive"

---

### Element 6: Cost of NOT Solving (Usually missing)

**Question:** What's the cost of NOT solving this problem?

**Prompts to help user respond:**
- What happens if they keep doing things the old way?
- What opportunities are they missing?
- What's the time/money/stress cost of the status quo?
- What's the worst case scenario if this problem continues?

**Example responses we're looking for:**
- "Wasted hours every week on manual slide work"
- "Presentations that don't win deals"
- "Looking unprofessional in important meetings"
- "Burning out creative teams on repetitive work"

---

### Confirmation Questions for Pre-filled Elements

Use these to validate information extracted from brand.md:

**Element 1 - What is it?**
> I found this description of your product: "[extracted text]"
> Is this accurate, or would you describe it differently?

**Element 2 - Who is it for?**
> Your target audience appears to be: "[extracted text]"
> Is this accurate? Any segments I'm missing?

**Element 3 - What problem does it solve?**
> The main problem you solve seems to be: "[extracted text]"
> Is this the primary pain point, or is there something more fundamental?

**Element 8 - Main benefit?**
> The primary benefit appears to be: "[extracted text]"
> If a customer could only remember one thing about you, is this it?

**Element 9 - What makes it different?**
> Your key differentiators seem to be: "[extracted text]"
> Which of these can competitors NOT claim?

**Element 11 - What proof exists?**
> I found these trust signals: "[extracted text]"
> Any additional proof points I should know about?

**Element 12 - What reduces risk?**
> Your risk reducers appear to be: "[extracted text]"
> Are there any guarantees or policies I'm missing?

---

## Interview Flow Template

### Opening

```
I'll extract your 6 message angles for RSA composition. This requires understanding your offer deeply.

I've found the following from your brand context. Let me confirm a few things and fill in the gaps.
```

### Pre-fill Confirmation Section

```
## From Your Brand Context

**Product:** [extracted]
**Audience:** [extracted]
**Main Problem Solved:** [extracted]
**Key Differentiators:** [extracted]
**Trust Signals:** [extracted]
**Risk Reducers:** [extracted]

Do these look accurate? Let me know if anything needs correction.
```

### Gap Interview Section

```
## I Need Additional Information

To complete angle extraction, please answer:

1. **What symptoms does your audience experience daily?**
   (The frustrations, struggles, daily annoyances they face)

2. **What have they tried before that didn't work?**
   (Failed alternatives, competitor shortcomings, workarounds)

3. **What's the cost of NOT solving this problem?**
   (Consequences of inaction - time, money, stress, opportunities)
```

### Closing

```
Thanks! I now have everything needed to extract your 6 message angles.

Proceeding to angle extraction...
```

---

## Tips for Quality Responses

### Signs of a Good Response

- **Specific:** "4 hours per week on slide formatting" not "saves time"
- **Emotional:** "dreading the weekly presentation" not "dislike presentations"
- **Customer language:** Uses words customers actually say
- **Quantified:** Includes numbers where possible

### Signs of a Weak Response

- **Generic:** "improves efficiency" (everyone says this)
- **Feature-focused:** "has AI" (not benefit-focused)
- **Internal language:** Jargon customers don't use
- **Unquantified:** "very fast" (how fast?)

### Follow-up Prompts for Weak Responses

If user gives generic response:
> "Can you give me a specific example of that?"

If user gives feature response:
> "What outcome does that feature create for the customer?"

If user seems unsure:
> "What do your customers say in reviews or sales calls about this?"

---

## Character Count Guidelines for Headline Phrases

When generating headline-ready phrases, verify character counts:

| Characters | Guideline |
|------------|-----------|
| ≤25 | Ideal - guaranteed to display |
| 26-30 | Good - meets Google limit |
| 31+ | Too long - needs shortening |

**Counting tips:**
- Spaces count as characters
- Numbers count (30% = 3 characters)
- Punctuation counts
- Emoji typically = 1-2 characters

**Shortening techniques:**
- Remove articles (a, an, the)
- Use symbols (& vs "and", % vs "percent")
- Use numerals (7 vs "seven")
- Remove redundant words
