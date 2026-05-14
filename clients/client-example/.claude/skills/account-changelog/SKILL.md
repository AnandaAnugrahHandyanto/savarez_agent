---
name: account-changelog
description: Fetch Google Ads account changes from the last N days (max 30) into context/account-changelog.md. Use for account changes, changelog, activity, or recent change history.
argument-hint: "[--days N]"
---

# Account Changelog

Fetch all changes made in the Google Ads account over the last N days using the `change_event` resource and save a readable changelog to `context/account-changelog.md`.

## Command Format

```
/account-changelog [--days N]
```

**Examples:**
- `/account-changelog` - Last 30 days (default)
- `/account-changelog --days 14` - Last 14 days

**Defaults:**
- Days: 30 (max 30 — API limitation for change_event)

## Process

### Step 1: Load Account Configuration

Read `config/ads-context.config.json` and extract:
- `googleAds.customerId`
- `googleAds.loginCustomerId`
- `googleAds.clientName`

If config is missing, show error with setup instructions.

### Step 2: Install Dependencies (if needed)

Check if `node_modules` exists in `.claude/skills/account-changelog/scripts/`:

```bash
cd .claude/skills/account-changelog/scripts && npm install
```

### Step 3: Fetch Change Events

Run the fetch-changes script:

```bash
node .claude/skills/account-changelog/scripts/fetch-changes.js \
  --customer-id={customerId} \
  --login-customer-id={loginCustomerId} \
  --days={days} \
  --output=context/account-changelog.csv
```

**IMPORTANT:**
- The `change_event` resource supports a **maximum 30-day lookback**. The script caps at 30 days automatically.
- The GAQL query is read from `references/change-event.gaql` — do not modify the query structure.

### Step 4: Load Business Context

Read `context/business.md` if it exists to understand:
- What campaigns are active and their goals
- Any recent strategic changes to note in context

### Step 5: Generate Markdown Changelog

Read the CSV output from Step 3 and generate `context/account-changelog.md` with this structure:

```markdown
# Account Changelog — {clientName}

**Date range:** {start_date} to {end_date} ({days} days)
**Total changes:** {total_count}

## Summary

### By Resource Type

- **Campaign:** X created, X updated, X removed (X total)
- **Ad Group:** X created, X updated, X removed (X total)
- **Ad:** X created, X updated, X removed (X total)
- **Keyword/Criterion:** X created, X updated, X removed (X total)
- ...

### By Source

- **Google Ads UI:** X changes (X%)
- **Google Ads Editor:** X changes (X%)
- **Google Ads API:** X changes (X%)
- **Automated Rules:** X changes (X%)
- **Recommendations:** X changes (X%)
- ...

### By User

- **user@email.com:** X changes — mostly updated keywords
- ...

## Change Log

Group changes by date (most recent first). Within each date, use a bullet list:

### {YYYY-MM-DD}

- **HH:MM** — user@email.com — **Updated** Keyword in *Campaign Name > Ad Group Name* — cpc_bid: $1.85 → $1.95
- **HH:MM** — user@email.com — **Updated** Budget for *Campaign Name* — amount: $50.00 → $75.00/day
- **HH:MM** — user@email.com — **Created** Ad in *Campaign Name > Ad Group Name*
- ...

## Insights

- [Notable patterns: e.g., "Bulk keyword additions on Jan 15 via Google Ads Editor (200+ keywords)"]
- [Automation activity: e.g., "Automated rules made 45 bid adjustments"]
- [Unusual activity: e.g., "15 campaigns removed on Jan 20"]
- [Recent focus: e.g., "Most changes in last week focused on Ad Group X keywords"]

---
*Last updated: {timestamp}*
*Date range: {days} days ({start_date} to {end_date})*
```

**Formatting rules:**
- Parse `change_event.change_date_time` to extract date and time separately
- Map `change_event.client_type` enum values to human-readable labels:
  - `GOOGLE_ADS_WEB_CLIENT` → "Google Ads UI"
  - `GOOGLE_ADS_EDITOR` → "Google Ads Editor"
  - `GOOGLE_ADS_API` → "Google Ads API"
  - `GOOGLE_ADS_AUTOMATED_RULE` → "Automated Rules"
  - `GOOGLE_ADS_SCRIPTS` → "Google Ads Scripts"
  - `GOOGLE_ADS_RECOMMENDATIONS` → "Recommendations"
  - `GOOGLE_ADS_RECOMMENDATIONS_SUBSCRIPTION` → "Recommendations (Auto-Applied)"
  - `GOOGLE_ADS_MOBILE_APP` → "Mobile App"
  - `GOOGLE_ADS_BULK_UPLOAD` → "Bulk Upload"
  - `SMART_CAMPAIGN_APP` → "Smart Campaigns"
  - `INTERNAL_TOOL` → "Internal Tool"
  - `SEARCH_ADS_360_SYNC` → "SA360 Sync"
  - `SEARCH_ADS_360_POST` → "SA360 Post"
  - Others → use the raw value
- Map `change_event.change_resource_type` to readable labels:
  - `AD` → "Ad"
  - `AD_GROUP` → "Ad Group"
  - `AD_GROUP_AD` → "Ad"
  - `AD_GROUP_CRITERION` → "Keyword/Criterion"
  - `AD_GROUP_BID_MODIFIER` → "Bid Modifier"
  - `AD_GROUP_ASSET` → "Ad Group Asset"
  - `CAMPAIGN` → "Campaign"
  - `CAMPAIGN_BUDGET` → "Budget"
  - `CAMPAIGN_CRITERION` → "Campaign Criterion"
  - `CAMPAIGN_ASSET` → "Campaign Asset"
  - `CAMPAIGN_ASSET_SET` → "Campaign Asset Set"
  - `CUSTOMER_ASSET` → "Customer Asset"
  - `ASSET` → "Asset"
  - `ASSET_SET` → "Asset Set"
  - `ASSET_SET_ASSET` → "Asset Set Asset"
  - Others → use the raw value
- Map `resource_change_operation` to readable labels:
  - `CREATE` → "Created"
  - `UPDATE` → "Updated"
  - `REMOVE` → "Removed"

**Before/after values (old_resource & new_resource):**

The CSV columns `change_event.old_resource` and `change_event.new_resource` contain JSON objects with the resource's state before and after the change. Parse these to show meaningful diffs in the Change Log:

- For **UPDATE** operations: compare old_resource vs new_resource to show `field: old → new`
- For **CREATE** operations: only new_resource has data — show key fields of what was created
- For **REMOVE** operations: only old_resource has data — show what was removed

**Value conversions when displaying:**
- Fields ending in `_micros` (e.g., `cpc_bid_micros`, `amount_micros`, `target_cpa_micros`): divide by 1,000,000 and format as currency (`$1.85`)
- Fields ending in `_micros` for ROAS targets (e.g., `target_roas`): divide by 1,000,000 and display as multiplier (`2.5x`)
- `status` fields: map numeric values — 0=UNSPECIFIED, 1=UNKNOWN, 2=ENABLED, 3=PAUSED, 4=REMOVED
- `match_type` fields: map — 0=UNSPECIFIED, 1=UNKNOWN, 2=EXACT, 3=PHRASE, 4=BROAD
- For other fields, display the raw value

**Resource identification (change_resource_name):**

Use `change_event.change_resource_name` to identify the specific resource. For keyword changes, the resource name contains the criterion ID which can help distinguish between keywords in the same ad group.

- If the changelog has >200 rows, summarize the Change Log section by showing top 50 most recent changes and a note: "Showing 50 most recent of {total} changes. Full data in context/account-changelog.csv"

### Step 6: Present Summary

```markdown
## Account Changelog Updated

**Account:** {clientName}
**Date range:** {days} days ({start_date} to {end_date})

### Files Created

- **context/account-changelog.csv** — {n} rows of raw change event data
- **context/account-changelog.md** — Formatted changelog

### Quick Stats

- **Total changes:** {count}
- **Top source:** {source} ({count} changes)
- **Top resource:** {resource_type} ({count} changes)
- **Most active user:** {email} ({count} changes)

### What's Next?

1. Review `context/account-changelog.md` for change patterns
2. Cross-reference with `context/business.md` for strategic alignment
3. Use insights to inform optimization decisions
```

## Error Handling

| Error | Message |
|-------|---------|
| Missing config | "Error: Missing ads-context.config.json. Create config/ads-context.config.json with googleAds.customerId and googleAds.loginCustomerId." |
| Missing credentials | "Error: Missing Google Ads credentials. Tell the user to set GOOGLE_ADS_CLIENT_ID, GOOGLE_ADS_CLIENT_SECRET, GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_REFRESH_TOKEN in config/.env. DO NOT read the .env file." |
| No changes found | "No changes found in the last {days} days. The account may have been inactive." |
| API error | Show the error message and suggest checking credentials or API access. |
| Days > 30 | "Warning: change_event supports max 30-day lookback. Using 30 days." |

## Prerequisites

**DO NOT read config/.env** - the scripts load credentials automatically.

1. **config/.env** - Scripts will load these variables (user must configure):
   - GOOGLE_ADS_CLIENT_ID
   - GOOGLE_ADS_CLIENT_SECRET
   - GOOGLE_ADS_DEVELOPER_TOKEN
   - GOOGLE_ADS_REFRESH_TOKEN

2. **config/ads-context.config.json** with:
   - googleAds.customerId
   - googleAds.loginCustomerId

3. **Node.js** with dependencies installed:
   ```bash
   cd .claude/skills/account-changelog/scripts && npm install
   ```

4. **Account access** — Valid Google Ads account with API permissions

## Bundled Resources

- **scripts/fetch-changes.js** — Fetches change_event data via Google Ads API, outputs CSV
- **scripts/package.json** — Node.js dependencies
- **references/change-event.gaql** — GAQL query template for change_event resource

## Integration Points

**Reads from:**
- `config/ads-context.config.json` — Account IDs and client name
- `config/.env` — API credentials
- `context/business.md` — Business context for insight generation (optional)

**Writes to:**
- `context/account-changelog.csv` — Raw change event data
- `context/account-changelog.md` — Formatted, readable changelog

**Downstream consumers:**
- Any analysis skill/agent that needs to understand recent account activity
- Business context updates (`context/business.md`)
