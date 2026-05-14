# Account Auditor — Ad Group Diagnostics (AUD-D20–D23)

**Data sources:** `adgroups.csv`, `keywords-all.csv`, `ads.csv`

All checks filter to enabled campaigns and enabled ad groups. Primarily applies to SEARCH campaigns (Shopping has product groups, PMax has asset groups).

---

## AUD-D20: Thematic Tightness
**Severity:** Medium (5 pts) | **Data:** `keywords-all.csv` → `ad_group.name`, `ad_group_criterion.keyword.text`

**Rule:** Keywords within an ad group should share tight thematic intent. One RSA should be able to credibly serve all keywords in the group.

**How to check:**
1. Filter `keywords-all.csv` to `ad_group_criterion.status = ENABLED` and `campaign.advertising_channel_type = SEARCH`
2. Group keywords by `ad_group.name` (within each campaign)
3. For each ad group with 3+ keywords, analyze thematic consistency:
   - Extract root terms (strip match type brackets/quotes, lowercase)
   - Check word overlap between keywords
   - Flag ad groups where keywords span clearly different intents

**Thematic analysis approach (from Search Ad Group Structure Mental Model):**

Apply the Single Ad Test: "Can one RSA serve all keywords without feeling generic?"

| Divergence type | Split needed? |
|----------------|---------------|
| Funnel stage (informational vs commercial) | Always split |
| Audience segment (SMB vs enterprise) | Usually split |
| Product/service type (CRM vs project management) | Always split |
| Commercial modifier (CRM vs best CRM) | Usually no |
| Synonym/variant (CRM vs customer relationship management) | Never |

**Scoring:**
- PASS (5 pts): >80% of ad groups have thematically tight keywords
- WARN (3 pts): 50-80% are tight
- FAIL (0 pts): <50% are tight (many ad groups mixing unrelated intents)

**Heuristic indicators of poor tightness:**
- Keywords in same ad group with no shared root words
- Mix of informational queries ("what is X") and transactional queries ("buy X")
- Mix of different product/service categories

---

## AUD-D21: Ads Per Ad Group
**Severity:** High (10 pts) | **Data:** `ads.csv` → `ad_group.name`, `ad_group_ad.status`

**Rule:** Every active ad group must have at least 1 enabled RSA.

**How to check:**
1. Get list of all enabled ad groups from `adgroups.csv` (filter `ad_group.status = ENABLED`, `campaign.advertising_channel_type = SEARCH`)
2. From `ads.csv`, count enabled ads per ad group (filter `ad_group_ad.status = ENABLED`)
3. Match ad groups to their ad counts
4. Flag ad groups with 0 enabled ads

**Pass/Fail:**
- PASS: All active Search ad groups have at least 1 enabled ad
- WARN: 1-2 ad groups missing ads (small gap)
- FAIL: Any active ad group with significant impressions has 0 enabled ads

**Note:** The `ads.csv` contains RSA data (`ad_group_ad.ad.responsive_search_ad.headlines`). If this field is populated, the ad is an RSA. Ad groups should have RSAs, not just legacy expanded text ads.

---

## AUD-D22: Impression Distribution
**Severity:** Medium (5 pts) | **Data:** `adgroups.csv` → `metrics.impressions`

**Rule:** Flag ad groups receiving too few impressions to generate meaningful data (<1000 impressions/week equivalent).

**How to check:**
1. Filter to enabled ad groups in enabled campaigns
2. Check `metrics.impressions` for each ad group
3. Calculate approximate weekly impressions (divide total by number of weeks in the date range)
4. Flag ad groups with <1000 impressions/week

**Pass/Fail:**
- PASS: All ad groups have >10 impressions/week (sufficient data)
- WARN: 1-5 ad groups below threshold
- FAIL: >5 ad groups with negligible impressions (data starvation)

**Context:** Ad groups with too few impressions cannot optimize effectively. They indicate either:
- Keywords too narrow or low-volume
- Budget not reaching these ad groups
- Bid too low to compete
- Consolidation opportunity (merge with related ad groups)

---

## AUD-D23: SKAG Detection
**Severity:** Medium (5 pts) | **Data:** `keywords-all.csv` → group by `ad_group.name`, count keywords

**Rule:** Flag outdated single-keyword ad groups (SKAGs) that fragment data unnecessarily.

**How to check:**
1. Filter `keywords-all.csv` to `ad_group_criterion.status = ENABLED` and `campaign.advertising_channel_type = SEARCH`
2. Group by `campaign.name` + `ad_group.name`
3. Count keywords per ad group
4. Flag ad groups with exactly 1 keyword (SKAGs)
5. Calculate SKAG percentage: (SKAG count / total ad groups) * 100

**Pass/Fail:**
- PASS: <10% of ad groups are SKAGs
- WARN: 10-30% are SKAGs (some legacy structure)
- FAIL: >30% are SKAGs (outdated structure fragmenting data)

**Why SKAGs are outdated (from Search Ad Group Structure Mental Model):**
- Modern Smart Bidding optimizes at the query level, not keyword level
- RSAs with 7-8 headlines can cover multiple angles
- Dynamic Keyword Insertion adapts H1 to the search query
- SKAGs create data poverty — each ad group gets too few impressions to learn
- The consolidation principle: more data in fewer ad groups = faster learning

**Exception:** A single high-value keyword in its own ad group is fine IF it has sufficient volume (>100 impressions/week). The check targets fragmentation, not isolation of important keywords.
