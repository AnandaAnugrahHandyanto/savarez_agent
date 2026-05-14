# Placement Auditor — Hygiene & Monitoring Rules (PL-D08 to PL-D10)

## PL-D08: Demand Gen Channel Performance

**Data source:** `placement-flags.csv` filtered to `campaign_channel_type = DEMAND_GEN`

**Logic:**

1. Filter placement-flags.csv to DEMAND_GEN campaigns
2. Also read raw placement-performance.csv for DEMAND_GEN to get channel distribution
3. Group by placement (channel-level) for DEMAND_GEN campaigns
4. Calculate per-channel CPA, spend share, and conversion share
5. Evaluate:

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| All channels within 1.5x of campaign average CPA | PASS | — | 10/10 |
| One channel CPA 2x+ above avg, <50% spend share | WARN | Medium | 5/10 |
| One channel >50% of spend with below-avg CPA + high CPA on remaining | FAIL | High | 0/10 |
| No Demand Gen campaigns in account | SKIP | — | —/— |

**Details to include:**
- Channel-level breakdown: placement name, impressions, clicks, cost, conversions, CPA
- Spend distribution across channels
- Channels with disproportionate spend vs. performance
- Note: Demand Gen serves across YouTube, Discover, and Gmail — allocation varies by Google's optimization

**Routing:** Advisory only — no optimizer action. Recommend reviewing channel allocation and consider separate ad groups per channel for better control.

---

## PL-D09: Placement Exclusion List Hygiene

**Data source:** `exclusion-coverage.json` → `list_hygiene` section

**Logic:**

1. Read list hygiene data
2. Check each list for:
   - Capacity: member_count vs 65,000 limit
   - Usage: reference_count = 0 means unused
   - Cross-list overlaps
3. Evaluate:

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| All lists <50% capacity, all linked, no overlaps | PASS | — | 5/5 |
| Any list >80% capacity | WARN | Medium | 2/5 |
| Unused lists (reference_count = 0) | WARN | Low | 3/5 |
| Significant cross-list overlaps (>10% of items) | WARN | Low | 3/5 |
| No exclusion lists exist (already caught by PL-D05) | SKIP | — | —/— |

**Note:** The API does not expose when items were added to exclusion lists. "Not updated in 90+ days" tracking must use `placement-changelog.md`. On first run, assume "unknown" and start tracking from this audit.

**Details to include:**
- Per-list: name, member count, capacity %, linked campaign count, status
- Unused lists (recommend removal or linking)
- Cross-list overlap count
- Lists approaching capacity

**Routing:** `/placement-optimizer lists` (PL-E06)

---

## PL-D10: Top Placement Brand Safety Spot-Check

**Data source:** `placements-for-review.csv` + `placement-content-flags.csv` (sub-agent output)

**Logic:**

1. The sub-agent reviews the top placements by spend/impressions during Phase 0.7
2. Any flagged items from the sub-agent serve as the spot-check output
3. Additionally, present the top 10 placements by impressions to the user for manual review
4. Evaluate:

| Condition | Verdict | Severity | Points |
|-----------|---------|----------|--------|
| Sub-agent found no issues in top placements | PASS (INFO) | — | 3/3 |
| Sub-agent flagged 1-3 items, none Critical | INFO | Low | 2/3 |
| Sub-agent flagged Critical items (kids content, brand-unsafe) | WARN | Low | 0/3 |

**This is always an advisory check.** Even when PASS, present the top 10 placements to the user with:
- Placement name/URL
- Placement type
- Impressions
- Campaign name

The user may spot issues that automated checks missed.

**Details to include:**
- Sub-agent flagged items (if any) with flag type and detail
- Top 10 placements by impressions for manual review
- Note that this is a spot-check, not comprehensive

**Routing:** Manual review — no optimizer action
