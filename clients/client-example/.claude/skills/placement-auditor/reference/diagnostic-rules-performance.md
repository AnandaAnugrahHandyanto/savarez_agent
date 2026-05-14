# Placement Auditor — Performance & App Audit Rules (PL-D01 to PL-D04)

## PL-D01: Mobile App Placement Audit

**Data source:** `exclusion-coverage.json` → `app_audit` section

**Logic:**

1. Read `app_audit.missing_categories` — list of app categories NOT excluded at account level
2. Read `app_audit.app_placement_spend_dollars` and `app_audit.app_placement_conversions`
3. Evaluate:

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| All categories excluded AND app spend <2% of total | PASS | — | 5/5 |
| Missing categories but app spend <2% with some conversions | WARN | Medium | 3/5 |
| Missing categories AND app spend >5% of total with 0 conversions | FAIL | High | 0/10 |
| Missing categories AND app spend >2% with 0 conversions | WARN | Medium | 3/5 |
| No app placement data (no Display/Video campaigns) | SKIP | — | —/— |

**Details to include:**
- Count of missing categories (with names if <10)
- App placement spend as % of total
- App conversion count
- `adsenseformobileapps.com` exclusion status

**Routing:** `/placement-optimizer apps` (PL-E01)

---

## PL-D02: Display Placement Performance

**Data source:** `placement-flags.csv` filtered to flag_types: `ZERO_CLICK`, `HIGH_CTR_ACCIDENTAL`, `HIGH_CTR_NO_CONV`, `HIGH_CPA`, `ZERO_CONV_WASTE`, `LOW_ROAS`

**Logic:**

1. Read flags CSV, filter to performance flag types
2. Group by flag_type, count items, sum flagged spend
3. Evaluate:

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| 0 performance flags | PASS | — | 10/10 |
| 1-3 flags, flagged spend <5% of total campaign spend | WARN | Medium | 5/10 |
| 4+ flags OR flagged spend >5% of campaign spend | FAIL | High | 0/10 |
| No Display/Video/DG campaigns in account | SKIP | — | —/— |

**Details to include:**
- Count per flag type (zero-click, accidental, invalid, high-CPA, zero-conv-waste, low-ROAS)
- Top 5 offending placements with spend and flag detail
- Total flagged spend in dollars

**Routing:** `/placement-optimizer performance` (PL-E02)

---

## PL-D03: Video Placement Quality

**Data source:** `placement-flags.csv` (flag_types: `VIDEO_NO_CONV`, `VIDEO_CTR_ANOMALY`) + `placement-content-flags.csv` (flag_types: `KIDS_CONTENT`, `MUSIC_PASSIVE`, `SPAM_CONTENT`)

**Logic:**

1. Read performance flags filtered to video types
2. Read content flags from sub-agent
3. Merge — kids content and brand-unsafe are Critical severity
4. Evaluate:

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| No video quality flags from either source | PASS | — | 15/15 |
| Music/passive channels only (no brand safety issues) | WARN | Medium | 10/15 |
| Spam content detected | FAIL | High | 5/15 |
| Kids content OR brand-unsafe content detected | FAIL | Critical | 0/15 |
| No Video/DG campaigns in account | SKIP | — | —/— |

**Important:** YouTube Data API metadata (subscriber count, channel age, video-to-subscriber ratio) is NOT available via Google Ads API. Content classification relies on display_name analysis by the sub-agent + performance signals from the script.

**Details to include:**
- Kids content channels found (with names — Critical)
- Spam channels found (with names)
- Music/passive channels with zero conversions
- Video placements with high spend and zero conversions

**Routing:** `/placement-optimizer safety` (PL-E03)

---

## PL-D04: Known-Bad Domain Detection

**Data source:** `placement-flags.csv` (flag_types: `PARKED_DOMAIN`, `MFA_SITE`, `RANDOM_DOMAIN`, `HIGH_RISK_TLD`) + `placement-content-flags.csv` (flag_type: `LOW_QUALITY_DOMAIN`)

**Logic:**

1. Read domain-related flags from both sources
2. Merge and deduplicate by normalized placement URL
3. Evaluate:

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| 0 known-bad domains | PASS | — | 10/10 |
| 1-5 domains, low spend | WARN | Medium | 5/10 |
| 6+ domains OR significant spend on bad domains | FAIL | High | 0/10 |
| No Display/DG campaigns (no website placements) | SKIP | — | —/— |

**Details to include:**
- Count per domain pattern type
- Top offending domains with spend
- High-risk TLD placements (only those with combined signals)

**Routing:** `/placement-optimizer safety` (PL-E04)
