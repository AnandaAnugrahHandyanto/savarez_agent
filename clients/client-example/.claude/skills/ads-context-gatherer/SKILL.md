---
name: ads-context-gatherer
description: Scrape brand and marketing context from a website URL into context/ for Google Ads work. Use for brand analysis, ads context gathering, or marketing context from a site.
argument-hint: "<url> [--pages paths]"
---

# Ads Context Gatherer

Gather brand and marketing context from a website URL. Outputs organized markdown files to a `context/` folder in the working directory for use as AI context in Google Ads work.

## Command Format

```
/ads-context-gatherer <URL> [--pages <paths>]
```

**Examples:**
- `/ads-context-gatherer https://acme.com` - Analyze homepage + auto-discover pages
- `/ads-context-gatherer https://acme.com --pages /about,/products,/contact` - Specific pages

**Defaults:**
- Pages: Homepage + auto-discovered from navigation (about, products, services, contact)

## Process

### Step 1: Parse Request

Extract from user input:
1. **Base URL** - The website domain (e.g., `https://acme.com`)
2. **Specific pages** - If provided via `--pages`, use those; otherwise auto-discover

**URL Validation:**
- Must start with `http://` or `https://`
- Extract base domain for page discovery
- If invalid, ask user to provide a valid URL

### Step 2: Fetch Homepage

Use WebFetch to retrieve the homepage:

```
WebFetch URL: {base_url}
Prompt: "Extract all text content from this page in its original language — do NOT translate anything. Include: main headings, paragraphs, navigation links, footer content. List all internal navigation links found. At the very end, state the primary language of the page content as a single line: DETECTED_LANGUAGE: {language code, e.g. en, de, nl, fr, es, ja}"
```

Save the navigation links for Step 3. Save the detected language (e.g., `de`, `nl`, `fr`) for use in Steps 4, 5, and 6. If detection is ambiguous, default to `en`.

### Step 3: Discover Additional Pages

From the homepage content, identify pages to analyze:

**Priority order:**
1. `/about` or `/about-us` - Company information
2. `/products` or `/services` - Offerings
3. `/contact` or `/contact-us` - Contact details
4. Any other prominent navigation links (max 15 additional pages)
5. Important to extract as much content as possible from each page to provide the best context for the brand.

If user specified `--pages`, use those instead of auto-discovery.

### Step 4: Fetch Additional Pages

For each discovered page, use WebFetch:

```
WebFetch URL: {base_url}{page_path}
Prompt: "Extract all text content from this page in its original language — do NOT translate anything. Include headings, paragraphs, lists, and any pricing or product information. Keep all text exactly as written on the page."
```

**Handle errors gracefully:**
- 404/not found: Skip and note in log
- Timeout: Retry once, then skip
- Blocked: Note in log, continue with available content

### Step 4.5: Extract Brand Colours (Chrome DevTools)

Use Chrome DevTools MCP to extract brand colours and fonts from the homepage. This step is **optional** — if Chrome DevTools is not available or extraction fails, skip gracefully and continue to Step 5.

#### 4.5.1 Navigate to Homepage

```
mcp__chrome-devtools__navigate_page → url: {base_url}, type: "url"
```

If navigation fails (Chrome not connected, timeout, error), log a warning and skip to Step 5.

#### 4.5.2 Take a Screenshot

Take a full-page screenshot to use as visual reference:

```
mcp__chrome-devtools__take_screenshot → fullPage: true
```

Read the screenshot file to see the site visually. Hold onto this — you'll use it in step 4.5.4.

#### 4.5.3 Run Extraction Script

Read the JavaScript function from `references/colour-extraction-script.md` and execute it:

```
mcp__chrome-devtools__evaluate_script → function: <script from reference file>
```

The script returns `{colors: [...], fonts: {heading, body}}` with frequency counts and context tags.

Process the raw results:
1. **Convert RGB to hex** — e.g., `rgb(26, 26, 46)` → `#1a1a2e`
2. **Filter out** transparent, pure white (`#ffffff`), and pure black (`#000000`)
3. **Keep top 10** colours by frequency
4. **Assign colour roles** based on context tags:

| Role | Assignment Rule |
|------|----------------|
| Primary | Highest-frequency colour with `navigation-bg` or `h1-text` context |
| Accent | Highest-frequency colour with `cta-bg` context |
| Background | Colour with `body-bg` context |
| Text | Colour with `body-text` context |
| Link | Colour with `link-text` context |

If a role can't be assigned from context, fall back to frequency order (skip colours already assigned).

#### 4.5.4 Visual Verification

**Compare the script results against the screenshot.** You can see the site — use your eyes.

Check for each role:
- **Primary**: Does the extracted primary match the dominant brand colour visible in the header, nav, or hero? If the script says `#333333` but you can clearly see a teal or blue header, the script missed it.
- **Accent**: Does the extracted accent match the CTA button colour visible on the page? If the script returned nothing but you can see coloured buttons, fill it in.
- **Background/Text**: These are usually correct from the script.

**If the script results look wrong or incomplete:**
1. Identify the correct colours visually from the screenshot
2. Run a targeted extraction script for the specific element to get exact hex values:
   ```
   mcp__chrome-devtools__evaluate_script → function: () => {
       const el = document.querySelector('<selector>');
       const style = getComputedStyle(el);
       return {
           bg: style.backgroundColor,
           bgImage: style.backgroundImage,
           color: style.color
       };
   }
   ```
3. Override the script's role assignments with what you can visually confirm

The script is a starting point. Your visual judgement is the final authority on what the brand colours actually are.

#### 4.5.5 Write Palette File

Create `context/brand-colours/` directory if it doesn't exist.

Write `context/brand-colours/palette.md` using the template from `references/palette-output-template.md`, populated with:
- Colour table (hex, RGB, contexts, frequency)
- Typography (heading/body fonts)
- Suggested colour roles with rationale
- Usage recommendations for Google Ads, landing pages, display ads

#### 4.5.6 Error Handling

This step must **never** block the skill. On any failure:

| Failure | Action |
|---------|--------|
| Chrome DevTools not connected | Log warning, skip entire step |
| Navigation fails | Log error, skip to Step 5 |
| Screenshot fails | Continue without visual verification (use script results as-is) |
| JS execution fails | Use screenshot only — visually identify primary, accent, and text colours |
| No meaningful colours from script | Use screenshot to visually identify colours, run targeted extraction scripts for specific elements |

Log all outcomes for Step 7 summary.

---

### Step 5: Extract Brand Context

Combine all fetched page content and analyze using the prompt from `references/brand-extraction-prompt.md`.

Read the prompt file, insert the scraped content and the detected language from Step 2 into the `{detected_language}` placeholder, and generate structured brand analysis covering:
- Company overview
- Tone of voice
- Target audience
- Products/services
- USPs and trust signals
- CTAs

### Step 6: Generate Output Files

Create the following structure in the working directory:

```
context/
├── brand.md              # Full brand analysis
├── business.md           # Business context template (if doesn't exist)
├── brand-colours/
│   └── palette.md        # Brand colour palette (if Chrome DevTools available)
├── website/
│   └── pages/
│       ├── homepage.md   # Homepage content
│       ├── about.md      # About page (if found)
│       └── {page}.md     # Other pages
└── .logs/
    └── {YYYY-MM-DD}.log  # Execution log
```

### Step 6.5: Generate Business Context Template

**Check if `context/business.md` exists:**

- **If exists:** Do not overwrite, note status as "Business context configured"
- **If not exists:** Create template file from `context/business.md` template

**Template to create** (if business.md doesn't exist):

```markdown
# Business Context

Strategic business context for Google Ads optimization. Claude agents and skills reference this file to make business-aligned recommendations.

**Status: TEMPLATE - Please fill in your business details**

---

## Business Goals

### Primary Focus
<!-- Select ONE primary metric -->
**Primary KPI:** [CPA / ROAS / Conversions / Market Share]

### Priority Level
<!-- Select ONE -->
**Mode:** [Growth / Balanced / Cost Control]

---

## Performance Targets

### Current vs Target Metrics

| Metric | Current | Target | Hard Constraint |
|--------|---------|--------|-----------------|
| CPA | $X.XX | $X.XX | Max: $X.XX |
| ROAS | X.Xx | X.Xx | Min: X.Xx |
| Monthly Conversions | X | X | Min: X |

---

## Strategic Priorities

### Campaign Priorities (Ranked)
1. [Campaign Name] - [Why it's priority]
2. [Campaign Name] - [Why it's priority]

---

## Competitive Strategy

### Approach
**Strategy:** [Aggressive / Defensive / Opportunistic]

### Priority Competitors
1. [Competitor domain]
2. [Competitor domain]

---

## Historical Context

### Known Constraints
- [e.g., "Cannot change landing pages without dev team"]
- [e.g., "Legal approval required for ad copy changes"]

---

*Template generated by /ads-context on {timestamp}*
*Fill in the sections above to enable business-aligned recommendations*
```

**brand.md format:**
```markdown
# Brand Context - {Company Name}

## Summary
[High-level overview with key insights]

## Company Overview
- **Name:** {company_name}
- **Tagline:** {tagline}
- **Industry:** {industry}
- **Language:** {detected_language_code}

## Tone of Voice
{tone_description}

**Examples:**
- "{example_phrase_1}"
- "{example_phrase_2}"

## Target Audience
{audience_description}

## Products & Services
{products_list}

## Unique Selling Propositions
{usps_list}

## Trust Signals
{trust_signals}

## Calls to Action
{ctas_used}

---
*Last updated: {timestamp}*
*Source: {url}*
*Pages analyzed: {page_count}*
```

**Page files format:**
```markdown
# {Page Title}

**URL:** {full_url}
**Fetched:** {timestamp}

## Content

{extracted_content}
```

**Log file format:**
```
[{timestamp}] INFO Started context gathering for {url}
[{timestamp}] INFO Fetched homepage
[{timestamp}] INFO Discovered {n} additional pages
[{timestamp}] INFO Fetched /about
[{timestamp}] WARN Page /products returned 404, skipped
[{timestamp}] INFO Generated brand.md
[{timestamp}] INFO Complete. Files written to context/
```

### Step 7: Present Summary

After generating files, present:

```markdown
## Context Gathered

**Website:** {url}
**Pages analyzed:** {count}
**Output:** context/

### Files Created

- `context/brand.md` - Full brand analysis
- `context/brand-colours/palette.md` - Brand colour palette *(if extracted)*
- `context/website/pages/homepage.md`
- `context/website/pages/about.md`
- [additional pages...]

### Brand Colour Extraction

| Status | Details |
|--------|---------|
| [Extracted / Skipped / Partial] | [e.g., "10 colours extracted, 5 roles assigned" / "Chrome DevTools not available" / "Extraction failed, manual identification needed"] |

**If extracted:**
> Brand colours saved to `context/brand-colours/palette.md` with {n} colours and suggested roles.
> The landing-page-builder and other skills will use this palette automatically.

**If skipped:**
> Colour extraction requires Chrome DevTools MCP. Open Chrome and ensure the DevTools MCP server is connected, then re-run `/ads-context` to extract colours. This is optional — all other context was gathered successfully.

### Business Context Status

| File | Status | Action Needed |
|------|--------|---------------|
| context/business.md | [Created template / Already configured / Missing] | [Fill in template / Ready to use / Create manually] |

**If template created:**
> A business context template has been created at `context/business.md`.
> Fill in your business goals, targets, and constraints to enable:
> - Performance vs. target tracking in `/gads-context`
> - Priority-based analysis in QS agents
> - Constraint-aware recommendations
> - Competitive strategy integration

**If already configured:**
> Business context is configured and will be used by all agents and skills.

### Quick Insights

- {insight_1}
- {insight_2}
- {insight_3}

### What's Next?

1. Review brand.md for accuracy
2. **Fill in context/business.md** (if template was created)
3. Run `/gads-context` to pull Google Ads data
4. Start creating ad copy or run `/qs-analyze` for optimization

Type a number or describe what you need.
```

## Error Handling

**Invalid URL:**
```
URL "{input}" is not valid. Please provide a full URL starting with https://

Example: /ads-context https://example.com
```

**Website unreachable:**
```
Could not reach {url}.

Possible causes:
- Website is down
- URL is incorrect
- Site blocks automated access

Try:
1. Verify the URL in a browser
2. Check for typos
3. Try a different page on the site
```

**No content extracted:**
```
Could not extract meaningful content from {url}.

The site may use heavy JavaScript rendering. Options:
1. Try specific pages: /ads-context {url} --pages /about
2. Manually copy key content and ask for analysis
```

## Output Location

All files are created relative to the **current working directory**:
- If running from `/Users/me/clients/acme/`, output goes to `/Users/me/clients/acme/context/`
- Creates directories if they don't exist
- Overwrites existing files (logs are appended)
