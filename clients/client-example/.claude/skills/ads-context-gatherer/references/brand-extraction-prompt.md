# Brand Extraction Prompt

Use this prompt when analyzing scraped website content to extract structured brand context.

## Prompt Template

```
You are analyzing a website to extract marketing and brand context for Google Ads management.

LANGUAGE RULE: The website content is in {detected_language}. All extracted content — phrases, CTAs, taglines, tone examples, product descriptions, USPs, trust signals — MUST stay in the original language exactly as found on the website. Do NOT translate content into English. Section headers and field labels in the output template are in English (for machine readability) but all content values preserve the original language.

Analyze the following website content and extract structured information.

WEBSITE CONTENT:
{scraped_content}

Extract the following information. If something is not found or unclear, mark it as "Not found" or "Unclear" rather than guessing:

1. COMPANY OVERVIEW
- Company name
- Tagline/slogan
- Mission statement (if present)
- Industry/sector

2. TONE OF VOICE
- Overall tone (formal, casual, playful, professional, technical, friendly, etc.)
- Language style notes (describe in English)
- Key phrases or vocabulary they use repeatedly (keep in original language)
- Provide 3-5 example phrases that capture their voice (keep in original language exactly as found on the website)

3. TARGET AUDIENCE
- B2B or B2C (or both)
- Demographics described or implied
- Pain points addressed
- Personas or customer types mentioned

4. PRODUCTS/SERVICES
- List each product/service category
- Key features for each
- Price points (if visible)
- Any product-specific messaging

5. UNIQUE SELLING PROPOSITIONS
- What makes them different
- Guarantees or promises
- Awards or certifications

6. TRUST SIGNALS
- Reviews/testimonials presence
- "As seen in" logos
- Certifications
- Case studies
- Years in business
- Number of customers/clients

7. CALLS TO ACTION
- Primary CTAs used (exact text in original language)
- Secondary CTAs (exact text in original language)
- Conversion goals (buy, book demo, contact, download, etc. — describe in English)

8. COMPETITORS
- Any competitors mentioned
- Comparison claims made
- Positioning statements

Format your response as structured markdown that can be saved directly as a brand context file. Use the following structure:

# Brand Context - [Company Name]

## Summary
[2-3 sentence overview of the brand, their positioning, and primary offering]

## Company Overview
- **Name:** [company name]
- **Tagline:** [tagline in original language, or "Not found"]
- **Mission:** [mission statement in original language, or "Not found"]
- **Industry:** [industry/sector]
- **Language:** [ISO 639-1 code, e.g. en, de, nl, fr, es, ja]

## Tone of Voice
[Description of their communication style]

**Characteristics:**
- [characteristic 1]
- [characteristic 2]
- [characteristic 3]

**Example Phrases (original language):**
- "[phrase 1]"
- "[phrase 2]"
- "[phrase 3]"

## Target Audience
**Type:** [B2B/B2C/Both]

**Demographics:**
[Description of target demographics]

**Pain Points Addressed:**
- [pain point 1]
- [pain point 2]

**Customer Personas:**
- [persona 1]
- [persona 2]

## Products & Services
### [Category 1]
- [Product/Service]: [brief description]
- [Product/Service]: [brief description]

### [Category 2]
- [Product/Service]: [brief description]

**Pricing:** [pricing info or "Not publicly listed"]

## Unique Selling Propositions
1. [USP 1]
2. [USP 2]
3. [USP 3]

**Guarantees/Promises:**
- [guarantee or "None found"]

## Trust Signals
- [trust signal 1]
- [trust signal 2]
- [trust signal 3]

## Calls to Action
**Primary CTA:** "[exact CTA text in original language]" → [goal: buy/demo/contact/etc.]

**Secondary CTAs:**
- "[CTA text in original language]" → [goal]
- "[CTA text in original language]" → [goal]

## Competitive Positioning
[How they position against competitors, or "No explicit competitor mentions found"]

---
*Analysis based on website content from: [pages analyzed]*
```

## Usage

1. Fetch website pages using WebFetch
2. Combine all page content into `{scraped_content}`
3. Run this prompt
4. Save output directly to `context/brand.md`

## Notes

- The prompt instructs Claude to mark missing information as "Not found" rather than guessing
- Output is structured for both human readability and LLM consumption
- Include the source pages at the bottom for reference
