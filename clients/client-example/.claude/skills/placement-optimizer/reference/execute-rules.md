# Placement Optimizer — Execute Rules

## Safety Rule (MANDATORY)

> **The placement-optimizer MUST NEVER apply changes directly.** Every run follows this exact sequence:
> 1. Generate operations.json (all planned mutations)
> 2. Run `mutate.js --mode=dry-run` — produces a human-readable change table
> 3. **Present the dry-run output to the user and ask for explicit approval**
> 4. Only on user approval ("yes", "go ahead", "apply") → run `mutate.js --mode=live`
> 5. If user says "no" → stop, preserve operations file for later
>
> There is no shortcut. There is no "auto-apply" mode.

---

## Pre-Flight Checks (Before Generating Operations)

### 1. Shared Set Account Limit
- Query all `shared_set` where `type = NEGATIVE_PLACEMENTS`
- Google Ads allows ~20 placement exclusion lists per account
- If at or near limit: do NOT create new lists — add to existing or recommend consolidation

### 2. Already-Excluded Deduplication
Before adding ANY exclusion, check all three levels:
1. Account-level: `customer_negative_criterion` (placement, youtube_channel, youtube_video, mobile_app_category)
2. Shared lists: `shared_criterion` across all NEGATIVE_PLACEMENTS shared sets
3. Campaign-level: `campaign_criterion` where `negative = true`

**Normalize URLs before comparing:** strip www, lowercase, remove trailing slash.
- If already excluded at account-level → skip everywhere (account covers all including PMax)
- If already in shared list linked to target campaign → skip
- If already excluded at campaign-level for that campaign → skip

### 3. PMax Exclusion Constraint
PMax campaigns ONLY support account-level exclusions. MUST NOT:
- Create `campaign_criterion` with `negative=true` for PMax
- Link `campaign_shared_set` to PMax
When a placement fails in PMax but performs well elsewhere → note conflict in dry-run for manual decision.

---

## PL-E01: Exclude Mobile App Placements

**Triggered by:** PL-D01 WARN/FAIL

**Decision tree:**
1. Pull all `mobile_app_category_constant` entries (IDs 60000-60062 for Google Play, 60500-60587 for App Store)
2. Pull current `customer_negative_criterion` where `type = MOBILE_APP_CATEGORY`
3. Compare: find categories NOT yet excluded
4. Generate `create` operations for each missing category
5. Check for `adsenseformobileapps.com` placement exclusion — add if missing

**Exception gate:** If `business.md` indicates an app install campaign, warn user and exclude only non-relevant categories.

**Operations.json:**
```json
{
  "type": "create",
  "resource": "customer_negative_criterion",
  "fields": {
    "mobile_app_category": {
      "mobile_app_category_constant": "mobileAppCategoryConstants/{id}"
    }
  },
  "meta": {
    "action_id": "PL-E01",
    "category": "mobile_app_exclusion",
    "target": "{category name}",
    "rationale": "App category not excluded at account level"
  }
}
```

---

## PL-E02: Exclude Performance-Failing Placements

**Triggered by:** PL-D02 FAIL

**Decision tree:**
1. Read PL-D02 findings → list of failing placements with violation type
2. Check current exclusion state → skip already-excluded
3. **Cross-campaign check** for each placement:
   - Fails in ALL campaigns → account-level or shared list exclusion
   - Fails in SOME campaigns → campaign-level exclusion for failing campaigns only
   - Fails in one, insufficient data in others → campaign-level for failing, monitor note
4. Find or create shared exclusion list "PPCOS — Performance Exclusions"
5. Add exclusions as `shared_criterion` to the list
6. Link list to all active Display/Video/DG campaigns

**Minimum data thresholds:**
- Zero-click: 1,000+ impressions, 0 clicks
- Accidental clicks: CTR >10%
- Invalid traffic: CTR >3%, 0 conversions, 100+ clicks
- High CPA: CPA >3x campaign average, 100+ clicks

**Criterion type selection:**
- **Website/domain** → `placement: { "url": "bad-domain.xyz" }`
- **Mobile app** (ID starts with `2-` or `1-`, or is a package name like `com.xxx.xxx`) → `mobile_application: { "app_id": "2-com.example.app" }`
  - Google Play format: `2-{package_name}` (e.g. `2-com.example.app`)
  - iOS App Store format: `1-{numeric_id}` (e.g. `1-6754315344`)
  - The `2-` / `1-` prefixes map directly to placement IDs in the performance CSV
- **YouTube channel** → `youtube_channel: { "channel_id": "UCxxxxxxxx" }`
- **YouTube video** → `youtube_video: { "video_id": "xxxxxxxxxxx" }`

> **IMPORTANT:** The Google Ads API `placement` criterion type only accepts website URLs. Passing an app package name as `placement.url` will fail. Always use `mobile_application` with `app_id` for app exclusions. `mutate.js` has a safety net that auto-converts, but operations JSON should use the correct type from the start.

**Operations.json (website):**
```json
{
  "type": "create",
  "resource": "shared_criterion",
  "fields": {
    "shared_set": "{perf_list.resource_name}",
    "placement": { "url": "bad-domain.xyz" }
  },
  "meta": {
    "action_id": "PL-E02",
    "category": "placement_exclusion",
    "target": "bad-domain.xyz",
    "rationale": "CPA 4.2x campaign avg ($185 vs $44), 230 clicks"
  }
}
```

**Operations.json (mobile app):**
```json
{
  "type": "create",
  "resource": "shared_criterion",
  "fields": {
    "shared_set": "{perf_list.resource_name}",
    "mobile_application": { "app_id": "2-com.example.spamapp" }
  },
  "meta": {
    "action_id": "PL-E02",
    "category": "placement_exclusion",
    "target": "2-com.example.spamapp",
    "rationale": "CPA 4.2x campaign avg ($185 vs $44), 230 clicks"
  }
}
```

---

## PL-E03: Exclude Brand-Unsafe Video Placements

**Triggered by:** PL-D03 FAIL

**Decision tree:**
1. Read PL-D03 findings → brand-unsafe video placements
2. Kids content and spam → **account-level** via `customer_negative_criterion` (universal)
3. Campaign-specific quality issues → add to shared exclusion list

**Operations.json (account-level):**
```json
{
  "type": "create",
  "resource": "customer_negative_criterion",
  "fields": {
    "youtube_channel": { "channel_id": "UCxx_KidsChannel" }
  },
  "meta": {
    "action_id": "PL-E03",
    "category": "brand_safety_exclusion",
    "target": "Kids Cartoon Channel (UCxx_KidsChannel)",
    "rationale": "Children's content — brand safety + COPPA risk"
  }
}
```

---

## PL-E04: Exclude Known-Bad Domains

**Triggered by:** PL-D04 FAIL

**Decision tree:**
1. Read PL-D04 findings → domains matching bad patterns
2. Find or create shared exclusion list "PPCOS — Bad Domains"
3. Add each domain as `shared_criterion` with `placement.url`
4. Link list to all active Display/Video/DG campaigns

---

## PL-E05: Configure Brand Safety Settings

**Triggered by:** PL-D06 WARN

**Two mutation types:**

**A. Inventory type (per-campaign):**
```json
{
  "type": "update",
  "resource": "campaign",
  "resource_name": "customers/{id}/campaigns/{id}",
  "fields": { "video_brand_safety_suitability": "STANDARD_INVENTORY" },
  "meta": {
    "action_id": "PL-E05",
    "category": "brand_safety_setting",
    "target": "Campaign: {name}",
    "previous_value": "EXPANDED_INVENTORY",
    "new_value": "STANDARD_INVENTORY",
    "rationale": "Expanded inventory allows brand-unsafe content"
  }
}
```

**B. Content label exclusions (account-level):**

Recommended exclusions: `SEXUALLY_SUGGESTIVE`, `JUVENILE`, `PROFANITY`, `TRAGEDY`, `BELOW_THE_FOLD`, `EMBEDDED_VIDEO`, `LIVE_STREAMING_VIDEO`

```json
{
  "type": "create",
  "resource": "customer_negative_criterion",
  "fields": { "content_label": { "type": "SEXUALLY_SUGGESTIVE" } },
  "meta": {
    "action_id": "PL-E05",
    "category": "content_label_exclusion",
    "target": "SEXUALLY_SUGGESTIVE",
    "rationale": "Recommended content label exclusion not applied"
  }
}
```

---

## PL-E06: Update and Consolidate Exclusion Lists

**Triggered by:** PL-D05 FAIL, PL-D09 WARN

**Decision tree:**
1. Read current shared sets and linkages
2. Identify gaps:
   - Lists not linked to active campaigns → create `campaign_shared_set`
   - Unused lists (reference_count = 0) → advisory note
   - Overlapping lists → advise consolidation
3. For campaigns missing exclusion list coverage:
   - Create `campaign_shared_set` linkages
   - **Skip PMax campaigns** — they don't support campaign_shared_set

**Operations.json (link list to campaign):**
```json
{
  "type": "create",
  "resource": "campaign_shared_set",
  "fields": {
    "campaign": "customers/{id}/campaigns/{id}",
    "shared_set": "customers/{id}/sharedSets/{id}"
  },
  "meta": {
    "action_id": "PL-E06",
    "category": "list_linkage",
    "target": "Link '{list_name}' to '{campaign_name}'",
    "rationale": "Campaign not covered by placement exclusion list"
  }
}
```

---

## PL-E07: Automated Exclusion Scripts (Advisory)

**Triggered by:** PL-D02, PL-D04 findings

**No API mutation.** Advisory guidance + optional Google Ads Scripts template:
- Template at `created/placement-scripts/auto-exclude-template.js`
- Monitors for zero-click and high-CTR placements
- Auto-adds to exclusion list + email alerts

---

## Exclusion List Management Pattern

### Creating a New Shared Set
```json
{
  "type": "create",
  "resource": "shared_set",
  "fields": { "name": "PPCOS — Performance Exclusions", "type": "NEGATIVE_PLACEMENTS" },
  "meta": { "action_id": "PL-E02", "category": "exclusion_list_create", "target": "New shared exclusion list" },
  "output_ref": "perf_list"
}
```

The `output_ref` field stores the created resource_name for use by subsequent operations via `{perf_list.resource_name}`.

### Operation Ordering (handled by mutate.js)
1. shared_set creates → must exist before adding items
2. customer_negative_criterion creates → account-level (no dependencies)
3. shared_criterion creates → add items to lists (depends on 1)
4. campaign_criterion creates �� campaign-level exclusions
5. campaign_shared_set creates → link lists to campaigns (depends on 1)
6. campaign updates → brand safety settings
7. removes → only with --allow-remove

### Batching
- Max 200 operations per API call (safety cap)
- Default --max-ops=200; override with `--max-ops=N`
- Sequential entity types with brief pauses between
- Progress reporting for runs >50 operations
