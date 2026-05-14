# Geo-Schedule Optimizer — Execute Rules (GS-E01–E10)

## Bid Strategy Decision Gate

**This is step 1 for every execute action.** Before generating any mutation:

1. Read `campaigns.csv` → get `campaign.bidding_strategy_type` for each affected campaign
   - **Exclude experiment campaigns** (`campaign.experiment_type = EXPERIMENT`) — never generate mutations for experiments
2. Classify:
   - **Smart Bidding:** `TARGET_CPA`, `TARGET_ROAS`, `MAXIMIZE_CONVERSIONS`, `MAXIMIZE_CONVERSION_VALUE`
   - **Manual/Semi-auto:** `MANUAL_CPC`, `ENHANCED_CPC`, `MAXIMIZE_CLICKS`, `TARGET_IMPRESSION_SHARE`

3. Apply gate:

| Action | Smart Bidding | Manual/Semi-auto |
|--------|--------------|-----------------|
| GS-E01 Location bid modifiers | SKIP (ignored by algorithm) | APPLY |
| GS-E02 Location exclusions | APPLY (-100% / negative criterion) | APPLY |
| GS-E03 Targeting method fix | APPLY | APPLY |
| GS-E04 Schedule bid adjustments | SKIP (ignored) | APPLY |
| GS-E05 Pause dead windows | APPLY (schedule coverage) | APPLY (schedule coverage) |
| GS-E06 Device bid adjustments | APPLY -100% exclusion only | APPLY |
| GS-E07 Demographic exclusions | APPLY (-100% only) | APPLY |

When skipping an action for Smart Bidding, include a note in the dry-run output:
> "Skipped bid modifier adjustments for [Campaign] — Smart Bidding ignores non-exclusion modifiers. Only -100% (pause/exclusion) actions included."

---

## Modifier Formulas

### CPA-Based Accounts
```
modifier = (avg_CPA / segment_CPA) - 1
```

Example: avg CPA = $25, segment CPA = $20 → modifier = (25/20) - 1 = +25%
Example: avg CPA = $25, segment CPA = $35 → modifier = (25/35) - 1 = -29%

### ROAS-Based Accounts
```
modifier = (segment_ROAS / avg_ROAS) - 1
```

Example: avg ROAS = 4.0, segment ROAS = 5.2 → modifier = (5.2/4.0) - 1 = +30%
Example: avg ROAS = 4.0, segment ROAS = 2.8 → modifier = (2.8/4.0) - 1 = -30%

### Modifier Caps

| Scenario | Cap | Override |
|----------|-----|---------|
| First-time change (no existing modifier) | +/-30% | User says "uncap" during approval |
| Existing modifier from prior run | +/-50% | User says "uncap" during approval |
| Exclusion (-100%) | No cap | Always applied at exactly 0.0 |

When capping, show both values in the dry-run table:
> "Proposed: +42% → Capped to: +30% (first-time cap). Say 'uncap' to override."

### Bid Modifier API Values

The API uses a multiplier where 1.0 = no change:
- +25% modifier → `bid_modifier: 1.25`
- -30% modifier → `bid_modifier: 0.70`
- -100% (exclusion) → `bid_modifier: 0.0`
- No change → `bid_modifier: 1.0` (or omit)

---

## Execute Action: GS-E01 — Location Bid Modifiers

**Triggered by:** GS-D02 WARN/FAIL (geographic CPA/ROAS variance)

**Gate:** Manual/Semi-auto only. Skip for Smart Bidding.

**Decision tree:**
1. Read GS-D02 findings from audit report → get list of high-CPA/low-ROAS locations
2. Read `geo-user-location.csv` → get current performance per location
3. Read `campaign-criteria.csv` → get current location bid modifiers
4. For each flagged location:
   a. Calculate modifier using CPA or ROAS formula
   b. Apply cap (+/-30% first-time, +/-50% existing)
   c. Compute delta from current modifier value
5. Generate `update` operation per location

**Operations.json structure:**
```json
{
  "type": "update",
  "resource": "campaign_criterion",
  "resource_name": "{from campaign-criteria.csv}",
  "fields": { "bid_modifier": {calculated_value} },
  "meta": {
    "campaign": "{name}",
    "dimension": "location",
    "target": "{location name}",
    "previous_value": {current_modifier},
    "new_value": {calculated_value},
    "rationale": "CPA XX% above/below avg — Tier 1/2"
  }
}
```

---

## Execute Action: GS-E02 — Exclude Zero-Conversion Locations

**Triggered by:** GS-D03 FAIL (zero-conversion locations)

**Gate:** All bid strategies. Exclusions always work.

**Decision tree:**
1. Read GS-D03 findings → get list of zero-conversion locations with spend >2x target CPA
2. Read `campaign-criteria.csv` → check if location is already excluded (negative=true)
3. For each non-excluded zero-conv location:
   - Create a negative location criterion

**Operations.json structure:**
```json
{
  "type": "create",
  "resource": "campaign_criterion",
  "fields": {
    "campaign": "customers/{id}/campaigns/{id}",
    "negative": true,
    "location": { "geo_target_constant": "geoTargetConstants/{geo_id}" }
  },
  "meta": {
    "campaign": "{name}",
    "dimension": "location_exclusion",
    "target": "{location name}",
    "rationale": "Zero conversions, spend ${X} (>2x target CPA) — exclusion"
  }
}
```

---

## Execute Action: GS-E03 — Fix Location Targeting Method

**Triggered by:** GS-D01 WARN (presence or interest without justification)

**Gate:** All bid strategies.

**Note:** This is a campaign-level setting change, NOT a campaign_criterion mutation. It requires a different API call pattern — updating `campaign.geo_target_type_setting.positive_geo_target_type` via campaign update.

**Decision tree:**
1. Read GS-D01 findings → get list of campaigns using `PRESENCE_OR_INTEREST`
2. Confirm vertical is NOT tourism/travel/relocation/pure-ecommerce
3. Generate campaign update operation (not campaign_criterion)

**Operations.json structure:**
```json
{
  "type": "update",
  "resource": "campaign",
  "resource_name": "customers/{id}/campaigns/{id}",
  "fields": {
    "geo_target_type_setting": { "positive_geo_target_type": "PRESENCE" }
  },
  "meta": {
    "campaign": "{name}",
    "dimension": "targeting_method",
    "target": "Location targeting method",
    "previous_value": "PRESENCE_OR_INTEREST",
    "new_value": "PRESENCE",
    "rationale": "Non-exempt vertical — restrict to physical presence"
  }
}
```

---

## Execute Action: GS-E04 — Ad Schedule Bid Adjustments

**Triggered by:** GS-D07 FAIL (ad schedule waste) for high-CPA time slots

**Gate:** Manual/Semi-auto only. Skip for Smart Bidding.

**Decision tree:**
1. Read GS-D07 findings → get list of high-CPA time slots (CPA 60%+ above avg)
2. Read `schedule-performance.csv` → get current performance per slot
3. Read `campaign-criteria.csv` → check for existing ad_schedule modifiers
4. For each flagged slot:
   a. Calculate modifier using CPA/ROAS formula
   b. Apply cap
   c. If ad_schedule criterion already exists → update
   d. If no existing criterion → create new

**Operations.json structure (create):**
```json
{
  "type": "create",
  "resource": "campaign_criterion",
  "fields": {
    "campaign": "customers/{id}/campaigns/{id}",
    "ad_schedule": {
      "day_of_week": "MONDAY",
      "start_hour": 0,
      "start_minute": "ZERO",
      "end_hour": 4,
      "end_minute": "ZERO"
    },
    "bid_modifier": 0.65
  },
  "meta": {
    "campaign": "{name}",
    "dimension": "ad_schedule",
    "target": "Mon 00:00-04:00",
    "previous_value": null,
    "new_value": 0.65,
    "rationale": "CPA 65% above avg — reduce bids during low-performing window"
  }
}
```

---

## Execute Action: GS-E05 — Pause Dead Time Windows

**Triggered by:** GS-D07 FAIL (dead time windows with zero conversions over 4+ weeks)

**Gate:** All bid strategies. Dead windows are removed via custom schedule coverage — bid strategy doesn't matter.

**API constraint:** `bid_modifier = 0.0` (-100%) is **NOT supported** for ad_schedule criteria. The correct approach is **custom schedule coverage**: create ad_schedule entries covering only the active hours, leaving dead windows as gaps. When a campaign has any ad_schedule criteria, it only serves during scheduled hours.

**Decision tree:**
1. Read GS-D07 findings → get dead time windows (0 conversions, 4+ weeks)
2. Read `campaign-criteria.csv` → check for existing ad_schedule criteria
3. **If campaign has NO existing ad_schedule criteria** (running 24/7):
   - Generate `create` operations for schedule entries covering all **active** hours, leaving dead windows as gaps
   - Example: to block Mon 20:00-23:00, create `Mon 00:00-20:00` + `Mon 23:00-24:00`
   - Repeat for each affected day of the week (2 entries per day with one dead window)
   - Once any schedule entries exist, the campaign only serves during scheduled hours — gaps are implicitly paused
4. **If campaign has existing ad_schedule criteria:**
   - Remove entries that overlap with dead windows (requires `--allow-remove`)
   - Create new entries covering active hours only
   - Example: existing `Mon 00:00-24:00` + dead window 20:00-23:00 → remove old, create `Mon 00:00-20:00` + `Mon 23:00-24:00`

**Note on partial adjustments:** For Manual CPC / eCPC campaigns where a time window has poor (but not zero) performance, consider a bid modifier reduction instead of full removal. Use `bid_modifier = 0.5` (-50%) or similar via GS-E04 for high-CPA windows that still convert.

**Note:** Custom schedule coverage creates more operations (up to 2 per day per dead window × 7 days = 14 ops). Show the full schedule in the dry-run table for user review.

**Operations.json structure (custom schedule coverage):**
```json
[
  {
    "type": "create",
    "resource": "campaign_criterion",
    "fields": {
      "campaign": "customers/{id}/campaigns/{id}",
      "ad_schedule": {
        "day_of_week": "MONDAY",
        "start_hour": 0,
        "start_minute": "ZERO",
        "end_hour": 20,
        "end_minute": "ZERO"
      },
      "bid_modifier": 1.0
    },
    "meta": {
      "campaign": "{name}",
      "dimension": "ad_schedule",
      "target": "Mon 00:00-20:00",
      "previous_value": null,
      "new_value": 1.0,
      "rationale": "Schedule coverage — active hours (dead window: 20:00-23:00)"
    }
  },
  {
    "type": "create",
    "resource": "campaign_criterion",
    "fields": {
      "campaign": "customers/{id}/campaigns/{id}",
      "ad_schedule": {
        "day_of_week": "MONDAY",
        "start_hour": 23,
        "start_minute": "ZERO",
        "end_hour": 24,
        "end_minute": "ZERO"
      },
      "bid_modifier": 1.0
    },
    "meta": {
      "campaign": "{name}",
      "dimension": "ad_schedule",
      "target": "Mon 23:00-24:00",
      "previous_value": null,
      "new_value": 1.0,
      "rationale": "Schedule coverage — active hours (dead window: 20:00-23:00)"
    }
  }
]
```

---

## Execute Action: GS-E06 — Device Bid Adjustments

**Triggered by:** GS-D06 FAIL (device CPA 50%+ above average)

**Gate:**
- **Manual/Semi-auto:** Full modifier adjustments (any value).
- **Smart Bidding:** Only -100% exclusion (`bid_modifier: 0.0`). Skip partial modifiers — Smart Bidding ignores them. When a device CPA is 80%+ above average on 200+ clicks, propose exclusion. Below that threshold on Smart Bidding, note in dry-run output: "Device underperforming but below exclusion threshold for Smart Bidding — monitor only."

**Decision tree:**
1. Read GS-D06 findings → get underperforming device types
2. Read `campaigns.csv` → classify bid strategy (Smart Bidding vs Manual/Semi-auto)
3. Read `device-performance.csv` → get current CPA per device
4. Read `campaign-criteria.csv` → get current device bid modifiers
5. For each flagged device:
   - **Manual/Semi-auto campaigns:**
     a. Calculate modifier using CPA/ROAS formula
     b. Apply cap
     c. Device criteria always exist (one per campaign per device type), so always `update`
   - **Smart Bidding campaigns:**
     a. Check if device CPA is 80%+ above average AND has 200+ clicks
     b. If yes → propose `bid_modifier: 0.0` (-100% exclusion)
     c. If no → skip with monitoring note (no operation generated)

**Operations.json structure (partial modifier — Manual/Semi-auto only):**
```json
{
  "type": "update",
  "resource": "campaign_criterion",
  "resource_name": "{from campaign-criteria.csv where type=DEVICE}",
  "fields": { "bid_modifier": 0.55 },
  "meta": {
    "campaign": "{name}",
    "dimension": "device",
    "target": "TABLET",
    "previous_value": 1.0,
    "new_value": 0.55,
    "rationale": "Tablet CPA 68% above avg ($43 vs $26)"
  }
}
```

**Operations.json structure (exclusion — all bid strategies):**
```json
{
  "type": "update",
  "resource": "campaign_criterion",
  "resource_name": "{from campaign-criteria.csv where type=DEVICE}",
  "fields": { "bid_modifier": 0.0 },
  "meta": {
    "campaign": "{name}",
    "dimension": "device",
    "target": "TABLET",
    "previous_value": 1.0,
    "new_value": 0.0,
    "rationale": "Tablet CPA 92% above avg ($50 vs $26) on 340 clicks — exclusion (-100%)"
  }
}
```

---

## Execute Action: GS-E07 — Demographic Exclusions

**Triggered by:** GS-D13 FAIL (demographic exclusion opportunity — sustained 60+ days, 100+ clicks)

**Gate:** All bid strategies. -100% is respected.

**Decision tree:**
1. Read GS-D13 findings → get demographic segments with sustained high CPA
2. Read `campaign-criteria.csv` → find existing demographic criteria
3. For each flagged segment:
   - Update existing criterion to `bid_modifier: 0.0` (-100%)
   - Note: demographic criteria are at campaign level (age_range, gender, income_range)

**Operations.json structure:**
```json
{
  "type": "update",
  "resource": "campaign_criterion",
  "resource_name": "{from campaign-criteria.csv}",
  "fields": { "bid_modifier": 0.0 },
  "meta": {
    "campaign": "{name}",
    "dimension": "age_range",
    "target": "AGE_RANGE_65_UP",
    "previous_value": 1.0,
    "new_value": 0.0,
    "rationale": "CPA 72% above avg sustained 90+ days — exclusion (-100%)"
  }
}
```

---

## Execute Action: GS-E08 — Geographic Targeting Optimization (Advisory)

**Triggered by:** GS-D04 WARN, GS-D14 WARN (high-performing locations with IS loss)

**No API mutation.** This is advisory guidance only.

**Output:** Include in the dry-run table as an advisory row:

```
| — | Advisory | Location | New York, US | — | — | CPA 28% below avg, IS lost 15% — consider dedicated campaign |
```

**Guidance to present:**
- "Consider creating a dedicated campaign for [location] with its own budget"
- "Current IS lost to budget: X% — dedicated campaign could capture ~Y additional conversions/month"
- This is a strategic recommendation, not an automated change

---

## Execute Action: GS-E09 — Document All Changes (Auto)

**No user action.** `mutate.js` automatically writes to `context/analysis/geo-schedule-changelog.md` after live apply. The optimizer also logs to `context/memory/YYYY-MM-DD.md` per memory-logging rules.

---

## Execute Action: GS-E10 — Schedule Next Review (Advisory)

**No API mutation.** Present at the end of Phase 5:

- If significant changes applied (>5 operations or any exclusions): "Re-audit in 14 days to measure impact"
- If minor adjustments only: "Re-audit in 30 days"
- If only advisories (GS-E08): "Re-audit in 30 days"
