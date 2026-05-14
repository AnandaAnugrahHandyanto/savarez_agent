# Palette Output Template

Use this template when writing `context/brand-colours/palette.md`.

## Template

```markdown
# Brand Colour Palette - {company_name}

Extracted from: {url}
Generated: {timestamp}

---

## Colour Palette

| Hex | RGB | Usage Contexts | Frequency |
|-----|-----|----------------|-----------|
| {hex} | {rgb} | {contexts} | {count} |

## Typography

| Role | Font Family |
|------|-------------|
| Headings | {heading_font} |
| Body | {body_font} |

## Suggested Colour Roles

| Role | Hex | Rationale |
|------|-----|-----------|
| Primary | {hex} | Most frequent colour in navigation/headings |
| Accent | {hex} | Most frequent colour in CTA buttons |
| Background | {hex} | Body background colour |
| Text | {hex} | Body text colour |
| Link | {hex} | Link text colour |

## Usage Recommendations

### Google Ads
- **Display ads background:** Use Primary or Background colours
- **CTA buttons in display:** Use Accent colour for consistency with brand
- **Text overlays:** Use Text colour on Background, or white on Primary/Accent

### Landing Pages
- **Hero sections:** Primary as background, white text
- **CTA buttons:** Accent colour with white text
- **Body sections:** Background colour with Text colour
- **Section dividers:** Use Primary at reduced opacity

### Brand Consistency Notes
- {note_1}
- {note_2}

---
*Extracted by /ads-context colour analysis*
*Source: {url}*
```

## Field Mapping

| Template Field | Source |
|---------------|--------|
| `{company_name}` | From `context/brand.md` or homepage title |
| `{url}` | Base URL from Step 1 |
| `{timestamp}` | ISO timestamp at generation |
| `{hex}` | RGB converted to hex from extraction results |
| `{rgb}` | Raw RGB value from extraction |
| `{contexts}` | Comma-separated context tags |
| `{count}` | Frequency count from extraction |
| `{heading_font}` | `fonts.heading` from extraction |
| `{body_font}` | `fonts.body` from extraction |

## Role Assignment Logic

- **Primary:** Highest-frequency colour with `navigation-bg` or `h1-text` context
- **Accent:** Highest-frequency colour with `cta-bg` context
- **Background:** Colour with `body-bg` context
- **Text:** Colour with `body-text` context
- **Link:** Colour with `link-text` context

If a role can't be assigned from context, fall back to frequency order (skip colours already assigned to other roles).
