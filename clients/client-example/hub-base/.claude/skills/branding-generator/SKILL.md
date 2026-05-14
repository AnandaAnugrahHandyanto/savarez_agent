---
name: branding-generator
description: Create and manage freelancer/agency branding stored at the hub root (my-brand/) for report generation. Use to set up brand, agency branding, logo, or brand colors.
argument-hint: "[URL] [--update] [--preview]"
---

# Branding Generator

Creates and manages freelancer/agency branding stored at the hub root. This branding is used by the report-generator skill for professional HTML reports.

## Command Format

```
/branding-generator [URL]            # Full setup — scrape website for colors, then confirm
/branding-generator --update         # Update existing branding
/branding-generator --preview        # Show current branding summary
```

**Examples:**
- `/branding-generator https://myagency.com` — Scrape site, extract colors/fonts, create brand
- `/branding-generator` — Interactive setup without website scraping
- `/branding-generator --update` — Modify existing branding
- `/branding-generator --preview` — Display current brand configuration

## Path Resolution

**Always write to `{hub_root}/my-brand/`.**

To find the hub root:
1. Check current directory for `main-config.json` or `clients/` directory
2. If not found, walk up parent directories until found
3. The hub root is where `main-config.json` lives

This skill can be triggered from any directory (hub root or client subfolder). The output always goes to the hub root's `my-brand/` folder.

## Data Sources

| File | Required | Purpose |
|------|----------|---------|
| `my-brand/brand.json` | No | Existing branding (if updating) |
| `reference/brand-schema.md` | Yes | Schema for brand.json output |
| `reference/colour-extraction-script.md` | Yes | Chrome DevTools JS for colour extraction |

## Process

### Phase 0: Path Resolution & Mode Detection

1. Find hub root (walk up from cwd looking for `main-config.json` or `clients/`)
2. Parse command flags:
   - `--preview` → Phase 1 only, then exit
   - `--update` → Load existing, skip to Phase 4
   - URL provided → Proceed to Phase 2 (website scrape)
   - No URL, no flags → Ask for URL in Phase 2

### Phase 1: Detect Existing Branding

Check if `{hub_root}/my-brand/brand.json` exists.

**If exists and `--preview`:**
- Read `my-brand/brand.json`
- Display formatted summary: company name, colors (with hex codes), fonts, logo status
- Exit

**If exists and no `--update`:**
- Show current branding summary
- Ask via AskUserQuestion: "You already have branding configured. What would you like to do?"
  - Options: "Update existing branding" / "Start fresh (overwrite)"
- If "Update" → load existing values as defaults for Phase 4
- If "Start fresh" → proceed to Phase 2

**If not exists:**
- Proceed to Phase 2

### Phase 2: Website URL

If no URL was provided in the command:

Ask via AskUserQuestion:
- "Do you have a website to extract brand colors from?"
  - Options: "Yes, scrape my website" / "No, I'll enter colors manually"
- If yes → Ask for the URL
- If no → Skip to Phase 4 (manual entry, no pre-filled values)

### Phase 3: Website Colour Extraction (Chrome DevTools)

This phase uses Chrome DevTools MCP to extract colours and fonts, then **visually verifies** the results against a screenshot. **Must never block the skill** — on any failure, fall back to manual entry in Phase 4.

#### 3.1 Navigate to Website

```
mcp__chrome-devtools__navigate_page → url: {website_url}, type: "url"
```

If navigation fails, tell the user and ask how to continue.

#### 3.2 Take a Screenshot

Take a full-page screenshot to use as visual reference:

```
mcp__chrome-devtools__take_screenshot → fullPage: true
```

Read the screenshot file to see the site visually. Hold onto this — you'll use it in step 3.4.

#### 3.3 Run Extraction Script

Read the JavaScript function from `reference/colour-extraction-script.md` and execute it:

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
| Secondary | Second-highest frequency colour with `section-bg` or `footer-bg` context |
| Accent | Highest-frequency colour with `cta-bg` context |
| Background | Colour with `body-bg` context (default: `#ffffff`) |
| Background Alt | Colour with `section-bg` context that isn't Secondary (default: `#f8f9fa`) |
| Text | Colour with `body-text` context (default: `#333333`) |
| Text Light | Lighter variant of Text colour, or colour with `footer-text` context (default: `#666666`) |

If a role can't be assigned from context, fall back to frequency order (skip colours already assigned).

5. **Extract fonts**: Use `fonts.heading` and `fonts.body` from the script result. Clean font-family strings (remove fallback fonts, keep primary font name only).

#### 3.4 Visual Verification

**Compare the script results against the screenshot.** You can see the site — use your eyes.

Check for each role:
- **Primary**: Does the extracted primary match the dominant brand colour visible in the header, nav, or hero? If the script says `#333333` but you can clearly see a teal or blue header, the script missed it.
- **Accent**: Does the extracted accent match the CTA button colour visible on the page? If the script returned nothing but you can see gold/orange/green buttons, fill it in.
- **Secondary**: Is there a secondary colour used in sections, cards, or the footer?
- **Background/Text**: These are usually correct from the script.

**If the script results look wrong or incomplete:**
1. Identify the correct colours visually from the screenshot
2. If you need exact hex values, run a targeted extraction script for the specific element:
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

**If the script results look correct:** proceed with them.

The script is a starting point. Your visual judgement is the final authority on what the brand colours actually are.

#### 3.5 Error Handling

| Failure | Action |
|---------|--------|
| Chrome DevTools not connected | Log warning, skip to Phase 4 with no pre-filled values |
| Navigation fails | Log error, skip to Phase 4 |
| Screenshot fails | Continue without visual verification (use script results as-is) |
| JS execution fails | Use screenshot only — visually identify primary, accent, and text colours, ask user to confirm hex values |
| No meaningful colours from script | Use screenshot to visually identify colours, run targeted extraction scripts for specific elements |

### Phase 4: Confirm & Adjust

Present extracted values (or empty fields if no scrape) to the user for confirmation.

Ask via AskUserQuestion (one question at a time or grouped logically):

**Company Info:**
1. Company/Agency name — *required*
2. Tagline — *optional* (empty string if skipped)
3. Contact email — *required*
4. Website URL — *pre-filled from Phase 2 if provided*

**Colours** (show extracted hex values if available, let user confirm or change):
5. Primary colour (hex) — headers, navigation, emphasis. Pre-filled: `{extracted_primary}`
6. Secondary colour (hex) — supporting elements, dark sections. Pre-filled: `{extracted_secondary}`
7. Accent colour (hex) — CTAs, highlights, score badges. Pre-filled: `{extracted_accent}`

Tell the user: "These are the core colours. Background, text, and light text colours will be derived automatically. You can adjust them in `my-brand/brand.json` later if needed."

Auto-derive:
- `background`: `#ffffff` (unless extracted differently)
- `backgroundAlt`: `#f8f9fa` (unless extracted differently)
- `text`: Use extracted or `#333333`
- `textLight`: Use extracted or `#666666`

**Fonts:**
8. Heading font — Pre-filled: `{extracted_heading_font}` or system default
9. Body font — Pre-filled: `{extracted_body_font}` or system default

### Phase 5: Logo

Tell the user:

> Place your logo file in `{hub_root}/my-brand/` and name it `logo.png` (or `logo.svg`, `logo.jpg`).
> The logo will be embedded in generated reports.

Check for logo files in `{hub_root}/my-brand/`:
- Look for: `logo.png`, `logo.svg`, `logo.jpg`, `logo.jpeg`, `logo.webp`
- If found: record the filename and `exists: true`
- If not found: record `exists: false` and note in output that logo is pending

### Phase 6: Write Files

Write two files to `{hub_root}/my-brand/`:

#### `brand.json` (machine-readable)

Use the schema from `reference/brand-schema.md`. Include all collected values with ISO timestamps for `createdAt` and `updatedAt`.

#### `brand.md` (human-readable summary)

```markdown
# My Brand

**Company:** {name}
**Tagline:** {tagline}
**Email:** {email}
**Website:** {website}

## Colours
- Primary: {primary}
- Secondary: {secondary}
- Accent: {accent}
- Background: {background}
- Text: {text}

## Fonts
- Headings: {heading_font}
- Body: {body_font}

## Logo
File: {logo_filename} ({present/pending})

---
*Generated by /branding-generator on {date}*
```

### Phase 7: Summary

Display confirmation:

```
Brand configured successfully!

  Company:  {name}
  Colours:  Primary {primary} | Accent {accent} | Secondary {secondary}
  Fonts:    {heading} / {body}
  Logo:     {status}
  Saved to: {hub_root}/my-brand/

Use /report to generate branded client reports.
```

## Error Handling

| Error | Message |
|-------|---------|
| Hub root not found | "Could not find hub root (no main-config.json). Run this from your PPCOS hub directory." |
| Chrome DevTools unavailable | (silent fallback to manual entry) |
| Invalid hex colour | "Please enter a valid hex colour (e.g., #e94560)" |
| No company name provided | "Company name is required for report branding." |

## Integration Points

### Reads From
- `my-brand/brand.json` (if updating existing branding)

### Produces
- `my-brand/brand.json` — Machine-readable branding data
- `my-brand/brand.md` — Human-readable branding summary

### Downstream Consumers
- `/report` — Uses branding for HTML report generation
