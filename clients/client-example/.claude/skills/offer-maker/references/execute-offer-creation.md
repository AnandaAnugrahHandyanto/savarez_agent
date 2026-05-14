# Execute — Create Irresistible Offer (E01)

Read when `/offer-maker create` is invoked.

## Flow Overview

| Phase | Purpose | Output |
|-------|---------|--------|
| 1. Confirm vertical | Route to correct question set | Vertical type |
| 2. Assess current state | Check existing offer in business.md | Gap list |
| 3. 4-pillar interview | Gather offer elements | Complete offer documentation |
| 4. Validate | Run Offer Audit Checklist | Score (target: 12+/15) |
| 5. Write | Update business.md | Updated offer section |

---

## Phase 1: Confirm Vertical

Ask user (use AskUserQuestion):

**Question:** "What type of business is this?"

**Options:**
1. Lead Gen (services, consultancies, agencies)
2. SaaS (software, subscriptions, digital products)
3. Ecommerce (physical products, online retail)

If business.md already has a vertical, confirm: "I see {vertical} in your business context. Is this still correct?"

---

## Phase 2: Assess Current State

Read business.md for existing offer information. If an offer section exists:

Present to user:
```
I found an existing offer description:

**Current offer:** {extracted text}
**Value prop:** {if found}
**Guarantee:** {if found}
**Pricing:** {if found}

Are we redesigning from scratch, or improving what's here?
```

If no offer section exists: proceed directly to Phase 3.

---

## Phase 3: 4-Pillar Interview

For each pillar, ask the relevant questions based on vertical. Pre-populate from brand.md where possible.

### Pillar 1: Value

**Lead Gen questions:**
1. "What specific deliverable does the customer get?" (Not "a consultation" — what tangible thing?)
2. "What is the perceived monetary value?" (Can you put a number on it?)
3. "What's the dream outcome in one sentence?" (After they use your service, what's different?)

**SaaS questions:**
1. "What's the main thing your product does, in one sentence?"
2. "How fast can someone get their first result?" (Time-to-value)
3. "What's the dream outcome?" (Not features — what changes for them?)

**Ecommerce questions:**
1. "Describe the core product in one sentence."
2. "What makes it better than the generic/cheaper alternative?"
3. "What outcome does the customer achieve?" (Not the product — the result)

### Pillar 2: Uniqueness

**All verticals:**
1. "What can you claim that your top 3 competitors cannot?" (If nothing — that's the problem)
2. "Do you have a proprietary process, method, or technology? What would you name it?"
3. "What's included beyond the core offer?" (Bonuses, extras, bundles — things that make comparison hard)
4. "Who specifically is this for?" (The narrower, the more unique)

### Pillar 3: Urgency

**All verticals:**
1. "Is there a genuine reason to act now? A deadline, limited spots, price change, seasonal factor?"
2. "Is this urgency real or would it be manufactured?" (Be honest — fake urgency damages trust)
3. "How is this communicated to the customer?" (Specific date/number, not vague "limited")

**If no urgency exists:** That's OK. Note the gap, don't force it. Many successful offers work without urgency. Suggest: "Consider adding authentic urgency when a natural opportunity arises (capacity limits, seasonal offers, price increases)."

### Pillar 4: Trust

**All verticals:**
1. "What's your guarantee or risk removal policy?" (Money-back, free trial, satisfaction guarantee, free returns)
2. "What specific terms apply?" (Duration, conditions, process)
3. "What social proof do you have?" (Review scores, customer count, named testimonials, case studies)
4. "What credibility signals exist?" (Certifications, awards, media mentions, years in business, partnerships)

---

## Phase 4: Validate

Run the Offer Audit Checklist (read `reference/offer-audit-checklist.md`) against the collected answers.

Present results:
```
Offer Audit Score: {X}/15

Value:      {X}/4 — {pass/gap details}
Uniqueness: {X}/4 — {pass/gap details}
Urgency:    {X}/3 — {pass/gap details}
Trust:      {X}/4 — {pass/gap details}
```

If score >= 12: "Strong foundation. Ready for angle extraction."
If score 8-11: Flag specific gaps with recommended fixes.
If score < 8: "Offer needs more work. Here are the critical gaps: {list}"

---

## Phase 5: Write to business.md

Ask permission: "Want me to update the Offer section in business.md with this?"

If yes, write/update the Offer section in business.md using this format:

```markdown
## Offer

**One-sentence offer:** {clear, specific statement}
**Vertical:** {Lead Gen / SaaS / Ecommerce}
**Audit Score:** {X}/15

### Value
- **Dream outcome:** {specific, measurable outcome}
- **Core deliverable:** {what they get}
- **Perceived value:** {value framing}

### Uniqueness
- **Unique mechanism:** {proprietary method/tech, named if possible}
- **Differentiators:** {what competitors can't claim}
- **Value stack:** {bundled extras beyond core}
- **Target audience:** {specific segment}

### Urgency
- **Urgency element:** {deadline/limit/scarcity or "None — to be added"}
- **Type:** {authentic/not applicable}

### Trust
- **Guarantee:** {specific terms}
- **Social proof:** {review scores, customer count, named results}
- **Credibility:** {certifications, awards, partnerships}

### Gaps to Address
{List any checklist items that didn't pass, with recommended fixes}
```

**Critical rules:**
1. Only modify the Offer section — never touch other sections of business.md
2. Always ask permission before writing
3. Always update the Last Updated date in the Account section
4. Log to memory after completion
