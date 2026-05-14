---
name: competitor-scraper
description: Fetch competitor Google Ads via the DataForSEO API and output one CSV per domain to context/competitor-ads/. Use for scraping or fetching competitor ads.
argument-hint: "[--days N]"
---

# Competitor Ads Scraper

Fetch competitor Google Ads data using the DataForSEO Ads Search API. Outputs one clean CSV file per competitor domain to `context/competitor-ads/`.

## Command Format

```
/competitor-scraper [--days N]
```

**Examples:**
- `/competitor-scraper` - Fetch ads for all configured competitors
- `/competitor-scraper --days 90` - Fetch ads from last 90 days (if supported by API)

**Defaults:**
- Domains: From `config/ads-context.config.json` competitors section
- Location: 2840 (United States)

## Process

### Step 1: Load Configuration

Read competitor domains and location from `config/ads-context.config.json`:

```json
{
  "googleAds": { ... },
  "competitors": {
    "domains": ["chase.com", "capitalone.com", "amex.com"],
    "location_code": 2840
  }
}
```

**Location Code Reference:** Find your target location code in `.claude/skills/competitor-scraper/references/location-codes.json`

Common codes:
- `2840` - United States (default)
- `2826` - United Kingdom
- `2124` - Canada
- `2036` - Australia

For cities/states or other countries, check the reference file or DataForSEO's location database.

**Prerequisites:** The script will automatically load credentials from `config/.env`.
**DO NOT read this file.** The script handles credential loading internally.

Required format (for user setup only):
```
DATAFORSEO_LOGIN=your_dataforseo_login
DATAFORSEO_PASSWORD=your_dataforseo_api_password
```

### Step 1.5: Load Business Context for Prioritization

**Check `context/business.md` for competitor strategy:**

Extract:
- `Competitive Strategy > Approach` (Aggressive/Defensive/Opportunistic)
- `Competitive Strategy > Priority Competitors` (ordered list)

**Prioritization Logic:**

| Strategy | Behavior |
|----------|----------|
| Aggressive | Fetch ALL configured competitors, priority competitors first |
| Defensive | Fetch ONLY priority competitors (skip others to save API cost) |
| Opportunistic | Fetch ONLY priority competitors |

**Domain Order:**
1. Priority competitors from business.md (in listed order)
2. Remaining competitors from config (if Aggressive strategy)

**If business.md not found or no competitive strategy:**
- Fetch all configured competitors in config order
- Note in output: "Business context not configured - fetching all competitors"

### Step 2: Create Output and Temp Directories

```bash
mkdir -p context/competitor-ads
mkdir -p context/competitor-ads/.temp/transparency_urls
mkdir -p context/competitor-ads/.temp/ad-images
```

### Step 3: Fetch Ads for Each Domain

For each domain in `competitors.domains`, run:

```bash
node .claude/skills/competitor-scraper/scripts/fetch-ads.js \
  --domain=chase.com \
  --location=2840 \
  --output=context/competitor-ads/.temp/transparency_urls/chase.com.csv
```

### Step 4: Extract Ad Images from Transparency URLs

```bash
node .claude/skills/competitor-scraper/scripts/extract-ad-images.js \
  --input=context/competitor-ads/.temp/transparency_urls/chase.com.csv \
  --output=context/competitor-ads/.temp/ad-images/chase.com.csv
```

### Step 5: Extract Ad Content from Images (Final Output)

Extract visible ad elements and save final CSV directly to `context/competitor-ads/`:

```bash
node .claude/skills/competitor-scraper/scripts/extract-ad-content.js \
  --input=context/competitor-ads/.temp/ad-images/chase.com.csv \
  --output=context/competitor-ads/chase.com.csv
```

### Step 6: Cleanup Intermediate Files

After all domains are processed, remove the temp directory:

```bash
rm -rf context/competitor-ads/.temp
```

### Step 7: Present Summary

After all domains are processed:

```markdown
## Competitor Ads Fetched

**Location:** {location_code}
**Output:** context/competitor-ads/
**Business Context:** [Loaded/Not configured]

### Competitive Strategy Context

*If business.md configured:*

**Strategy:** [Aggressive/Defensive/Opportunistic]
**Approach:**
- Aggressive: Analyzed all competitors for comprehensive competitive intelligence
- Defensive: Focused on priority competitors to monitor threats
- Opportunistic: Analyzed priority competitors for targeted opportunities

**Priority Competitors:** [list from business.md]
**Win Themes to Emphasize:** [from business.md > Competitive Strategy > Win Themes]

*If business.md not configured: "Configure Competitive Strategy in business.md for strategic competitor analysis"*

### Files Created

| Domain | File | Ads Found | Priority |
|--------|------|-----------|----------|
| chase.com | chase.com.csv | {n} | #1 Priority |
| capitalone.com | capitalone.com.csv | {n} | #2 Priority |
| amex.com | amex.com.csv | {n} | - |

### Quick Competitive Insights

*If business.md configured, reference Win Themes:*
- [Competitor] emphasizes [theme] - Our win theme: [our differentiation]
- [Competitor] uses [offer] - Consider counter with [our offer]

### What's Next?

1. Review competitor ads in context/competitor-ads/
2. Run `/quality-score-auditor components` for competitor-aware ad analysis (ECTR module)
3. Identify gaps using Win Themes from business.md
```

## Output Structure

```
context/
└── competitor-ads/
    ├── chase.com.csv
    ├── capitalone.com.csv
    └── amex.com.csv
```

## Final CSV Output Columns

| Column | Description |
|--------|-------------|
| domain | Competitor domain |
| transparency_url | Link to Google Ads Transparency Center listing |
| headline | Extracted ad headline(s) |
| description | Extracted ad description text |
| display_url | Display URL shown in the ad |
| call_to_action | CTA text (if present) |
| format | Ad format (text, image, video) |
| first_shown | Date ad first appeared |
| last_shown | Date ad last seen |

**Note:** Ad content (headline, description, etc.) is extracted from ad preview images using vision AI. Quality depends on image clarity.

## API Details

**Endpoint:** `POST https://api.dataforseo.com/v3/serp/google/ads_search/live/advanced`

**Request body:**
```json
[{
  "target": "chase.com",
  "location_code": 2840,
  "depth": 40,
  "platform": "google_search",
  "format": "all"
}]
```

## Error Handling

**Missing credentials:**
```
Error: Missing DataForSEO credentials

Tell the user to configure config/.env with:
- DATAFORSEO_LOGIN
- DATAFORSEO_PASSWORD

DO NOT attempt to read or validate the .env file yourself.
```

**No competitors configured:**
```
Error: No competitors configured in config/ads-context.config.json

Add competitors section:
{
  "competitors": {
    "domains": ["competitor1.com", "competitor2.com"],
    "location_code": 2840
  }
}
```

**API error:**
- Show API error message and status code
- Check credentials validity
- Verify API quota/balance

## Prerequisites

**DO NOT read config/.env** - the scripts load credentials automatically.

1. **config/.env** - Scripts will load these variables (user must configure):
   - DATAFORSEO_LOGIN
   - DATAFORSEO_PASSWORD

2. **config/ads-context.config.json** with competitors section

3. **Node.js** with dependencies installed:
   ```bash
   cd .claude/skills/competitor-scraper/scripts && npm install
   ```

## Bundled Resources

- **scripts/fetch-ads.js** - Node.js script for DataForSEO API calls
- **scripts/package.json** - Dependencies
