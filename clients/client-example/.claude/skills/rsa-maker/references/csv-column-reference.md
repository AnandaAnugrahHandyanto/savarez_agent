# RSA CSV Column Reference

Google Ads Editor import format for Responsive Search Ads.

**IMPORTANT: Always read `rsa-import-template.csv` in this folder and use it as the base for generating new RSAs.**

## Template File

The file `rsa-import-template.csv` contains the exact header row and an example data row. When generating RSAs:

1. **Copy the header row exactly** from the template
2. **Follow the same column order and format** for data rows

## Column Order (46 columns)

```
Campaign,Ad Group,Ad type,Labels,Headline 1,Headline 1 position,Headline 2,Headline 2 position,Headline 3,Headline 3 position,Headline 4,Headline 4 position,Headline 5,Headline 5 position,Headline 6,Headline 6 position,Headline 7,Headline 7 position,Headline 8,Headline 8 position,Headline 9,Headline 9 position,Headline 10,Headline 10 position,Headline 11,Headline 11 position,Headline 12,Headline 12 position,Headline 13,Headline 13 position,Headline 14,Headline 14 position,Headline 15,Headline 15 position,Description 1,Description 1 position,Description 2,Description 2 position,Description 3,Description 3 position,Description 4,Description 4 position,Path 1,Path 2,Final URL
```

## Column Specifications

### Core Fields

| Column | Required | Description | Example |
|--------|----------|-------------|---------|
| Campaign | Yes | Campaign name (exact match) | `2.0 Plus AI \| Search \| Non-Branded - US` |
| Ad Group | Yes | Ad group name (exact match) | `AI presentation maker` |
| Ad type | Yes | Always `Responsive search ad` | `Responsive search ad` |
| Labels | No | Optional label for organization | `` |

### Headlines (15 slots)

| Column Pattern | Required | Max Length | Description |
|----------------|----------|------------|-------------|
| Headline {N} | Min 3 | 30 chars | Headline text |
| Headline {N} position | No | - | Pin position |

**Headline limits:**
- Minimum: 3 headlines
- Maximum: 15 headlines
- Recommended: 7-8 headlines

**Position values:**
| Value | Meaning |
|-------|---------|
| `1` | Pin to position 1 (first shown) |
| `2` | Pin to position 2 (second shown) |
| `3` | Pin to position 3 (third shown) |
| `-` | Unpinned (Google optimizes) |
| `` (empty) | Slot not used |

### Descriptions (4 slots)

| Column Pattern | Required | Max Length | Description |
|----------------|----------|------------|-------------|
| Description {N} | Min 2 | 90 chars | Description text |
| Description {N} position | No | - | Pin position |

**Description limits:**
- Minimum: 2 descriptions
- Maximum: 4 descriptions
- Recommended: 2-3 descriptions

**Position values:**
| Value | Meaning |
|-------|---------|
| `1` | Pin to position 1 (first shown) |
| `2` | Pin to position 2 (second shown) |
| `-` | Unpinned (Google optimizes) |
| `` (empty) | Slot not used |

### URL Fields

| Column | Required | Max Length | Description |
|--------|----------|------------|-------------|
| Path 1 | No | 15 chars | Display URL path segment 1 |
| Path 2 | No | 15 chars | Display URL path segment 2 |
| Final URL | Yes | 2048 chars | Landing page URL |

**Path display example:**
- Path 1: `slides`
- Path 2: `ai-maker`
- Display: `plusai.com/slides/ai-maker`

---

## Character Limits Summary

| Asset | Max Characters |
|-------|----------------|
| Headline | 30 |
| Description | 90 |
| Path 1 | 15 |
| Path 2 | 15 |
| Final URL | 2048 |

---

## Example Row

```csv
Campaign Name,Ad Group Name,Responsive search ad,,{KeyWord:AI Presentation Maker},1,Make Slides 10x Faster,-,Works in Google Slides,-,4.9 Stars | 1M+ Installs,-,Try Free for 7 Days,-,No New App to Learn,-,Try Plus AI Free,3,Stop Wasting Hours on Slides,-,,,,,,,,,,,,,Stop wasting hours on slides. Make presentations 10x faster with AI.,1,1M+ users trust Plus AI. Rated 4.9/5. Try it free today.,-,PDF to slides in seconds. AI images included. 7-day free trial.,-,,slides,ai-maker,https://plusai.com/
```

---

## Validation Rules

1. **Campaign/Ad Group:** Must match existing names exactly (case-sensitive)
2. **Headlines:** At least 3 required, no duplicates allowed
3. **Descriptions:** At least 2 required, no duplicates allowed
4. **Final URL:** Must be valid HTTPS URL
5. **Pinning:** Max 3 assets pinned to same position

---

## Special Characters

| Character | Handling |
|-----------|----------|
| Comma (,) | Wrap field in quotes |
| Quote (") | Escape as `""` |
| Pipe (\|) | Allowed in text |
| Ampersand (&) | Allowed in text |
| Brackets ({}) | Used for keyword insertion |

**Keyword insertion syntax:**
```
{KeyWord:Default Text}
```
- `KeyWord` = Dynamic keyword (capitalizes each word)
- `Default Text` = Fallback if keyword exceeds limit

---

## Source Reference

Based on Google Ads Editor export format. See `rsa-import-template.csv` in project root for template.
