# Placement Auditor — Brand Safety & Coverage Rules (PL-D05 to PL-D07)

## PL-D05: Placement Exclusion List Coverage

**Data source:** `exclusion-coverage.json` → `campaign_coverage` section

**Logic:**

1. Read `campaign_coverage.uncovered_campaigns` and `campaign_coverage.coverage_matrix`
2. Evaluate:

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| All eligible campaigns linked to at least one exclusion list | PASS | — | 10/10 |
| Some campaigns uncovered but exclusion lists exist | WARN | Medium | 5/10 |
| No placement exclusion lists exist at all | FAIL | High | 0/10 |
| No Display/Video/DG/PMax campaigns in account | SKIP | — | —/— |

**Details to include:**
- Total eligible campaigns vs covered
- Names of uncovered campaigns with channel type
- Coverage matrix summary (which lists linked to which campaigns)
- Note: PMax campaigns only support account-level exclusions, not campaign-level shared sets

**Routing:** `/placement-optimizer lists` (PL-E06)

---

## PL-D06: Brand Safety Configuration

**Data source:** `campaign-brand-safety.csv` + `account-exclusions-labels.csv`

**Logic:**

1. Read campaign brand safety settings
2. Check inventory type per Video campaign:
   - `EXPANDED_INVENTORY` or empty → WARN
   - `STANDARD_INVENTORY` or `LIMITED_INVENTORY` → OK
3. Check account-level content label exclusions against recommended set:
   - Recommended: `SEXUALLY_SUGGESTIVE`, `JUVENILE`, `PROFANITY`, `TRAGEDY`, `BELOW_THE_FOLD`, `EMBEDDED_VIDEO`, `LIVE_STREAMING_VIDEO`
   - Optional (context-dependent): `SOCIAL_ISSUES`, `BRAND_SUITABILITY_*` labels
4. Evaluate:

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| All campaigns on Standard/Limited inventory + all recommended labels excluded | PASS | — | 5/5 |
| Some campaigns on Expanded inventory OR missing 1-3 recommended labels | WARN | Medium | 2/5 |
| Multiple Expanded campaigns AND missing 4+ recommended labels | WARN | Medium | 0/5 |
| No Video/Display campaigns | SKIP | — | —/— |

**Note:** `video_brand_safety_suitability` returns empty for non-video campaigns — expected behavior. Only flag Video campaigns.

**Details to include:**
- Campaigns with Expanded inventory (names)
- Missing content label exclusions (list)
- Current exclusion label count vs recommended

**Routing:** `/placement-optimizer safety` (PL-E05)

---

## PL-D07: PMax Placement Review (Brand Safety)

**Data source:** `placement-flags.csv` (flag_type: `PMAX_BAD_DOMAIN`) + `placement-content-flags.csv` (PMax placements) + `pmax-placements.csv`

**Logic:**

1. Read PMax-specific flags from performance script
2. Read any PMax content flags from sub-agent
3. Note: PMax only exposes impressions — no clicks, cost, or conversions
4. Evaluate:

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| No brand-unsafe PMax placements found | PASS | — | 5/5 |
| 1-3 suspicious PMax placements, low impressions | WARN | Medium | 2/5 |
| 4+ suspicious PMax placements OR high impression volume on bad domains | WARN | Medium | 0/5 |
| No PMax campaigns in account | SKIP | — | —/— |

**Critical limitation:** PMax placement decisions MUST be made on brand safety/relevance, NOT performance. Only impressions data is available.

**PMax exclusion constraint:** PMax campaigns only support account-level exclusions via `customer_negative_criterion`. Cannot use campaign-level exclusions or shared sets.

**Details to include:**
- Flagged PMax placements with impression count
- Domain pattern matches
- Content safety flags from sub-agent
- Note about PMax's impressions-only limitation

**Routing:** `/placement-optimizer safety` (PL-E03, PL-E04 at account level)
