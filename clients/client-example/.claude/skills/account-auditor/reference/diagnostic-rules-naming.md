# Account Auditor — Naming Diagnostics (AUD-D09–D10)

## AUD-D09: Campaign Naming Convention
**Severity:** Medium (5 pts) | **Data:** `campaigns.csv` → `campaign.name`

**Rule:** Campaign names should follow a consistent, structured convention. The recommended pattern is `[Country]_[Language]_[CampaignType]_[Theme]_[Modifier]` but any consistent convention is acceptable.

**How to check:**
1. Extract all enabled campaign names
2. Check for consistency — do names follow a recognizable pattern?
3. Flag names that are clearly unstructured:
   - "Campaign 1", "Campaign #2", "New Campaign"
   - "Copy of...", "Test", "Untitled"
   - Names with no delimiter pattern (no underscores, hyphens, or other consistent separator)
4. Check formatting rules:
   - Consistent delimiter usage (underscores preferred)
   - No special characters (`&`, `%`, `$`, `#`)
   - Under 75 characters (truncation in UI/tools)

**Scoring:**
- PASS (5 pts): >80% of campaigns follow a recognizable consistent convention
- WARN (3 pts): 50-80% follow a convention (some drift)
- FAIL (0 pts): <50% follow any consistent pattern

**Expected pattern components (from Campaign Naming Convention Reference):**

| Position | Variable | Examples |
|----------|----------|----------|
| 1 | Geographic targeting | `NL`, `USA`, `DE`, `EU`, `Global` |
| 2 | Language | `NL`, `EN`, `FR`, `DE`, `ALL` |
| 3 | Campaign type | `Search`, `Pmax`, `Display`, `Shopping`, `YouTube`, `DemandGen` |
| 4 | Theme/audience | Product category, keyword theme, audience type |
| 5 | Modifier | `Brand`, `NB`, `DSA`, `Remarketing`, `Prospecting`, `Heroes` |

**Important:** The check is for CONSISTENCY, not strict adherence to this exact format. If an account uses a different but consistent convention, that passes.

---

## AUD-D10: Ad Group Naming Consistency
**Severity:** Low (3 pts) | **Data:** `adgroups.csv` → `ad_group.name`

**Rule:** Ad group names should be descriptive. Flag generic/default names.

**How to check:**
1. Extract all enabled ad group names
2. Flag names matching generic patterns:
   - `Ad Group 1`, `Ad Group #2`, `Ad Group 3`
   - `New Ad Group`, `Default`, `Untitled`
   - Single characters or numbers only
3. Calculate percentage of generic vs descriptive names

**Scoring:**
- PASS (3 pts): <10% of ad groups have generic names
- WARN (2 pts): 10-30% have generic names
- FAIL (0 pts): >30% have generic names

**Note:** This check applies primarily to Search and Shopping campaigns. PMax uses asset groups (not ad groups) which have different naming conventions. Filter to `campaign.advertising_channel_type IN (SEARCH, SHOPPING)` for this check.

**Generic name patterns to detect:**
```
/^Ad Group \d+$/i
/^Ad Group #\d+$/i
/^New Ad Group/i
/^Default$/i
/^Untitled$/i
/^\d+$/
/^AG\d+$/i
```
