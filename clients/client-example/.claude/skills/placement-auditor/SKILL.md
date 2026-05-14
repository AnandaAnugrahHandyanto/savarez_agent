---
name: placement-auditor
description: |
  Audit placement quality, brand safety, and exclusion list health. Scores 0-100 per module.
  AUTO-ACTIVATE for: "placement audit", "check placements", "placement health",
  "brand safety audit", "exclusion list audit", "placement performance check",
  "app placement audit", "video placement audit", "PMax placement review".
  Also triggered by /placement-audit command.
---

# Placement Auditor Skill

Audits placement performance, brand safety, and exclusion list health across 3 modules (10 diagnostics). DIAGNOSE-ONLY — findings route to `placement-optimizer` for execution.

| Module | IDs | Checks |
|--------|-----|--------|
| **Performance & App Audit** | PL-D01–D04 | Mobile app audit, display performance, video quality, known-bad domains |
| **Brand Safety & Coverage** | PL-D05–D07 | Exclusion list coverage, brand safety config, PMax placement review |
| **Hygiene & Monitoring** | PL-D08–D10 | Demand Gen channels, list hygiene, top placement spot-check |

**Not checked by this skill (per de-duplication log):**
- Applying exclusions/changes → `placement-optimizer` (`/placement-optimize`)
- Content targeting setup → content-targeting-specialist (future)
- Campaign structure → account-auditor
- Waste calculation (WD-D02, WD-D09) → waste-detective (shared data, different scope)

## Command Format

```
/placement-audit                     # Full audit (all 10 checks)
/placement-audit performance         # PL-D01 to PL-D04 only
/placement-audit safety              # PL-D05 to PL-D07 only
/placement-audit hygiene             # PL-D08 to PL-D10 only
```

---

## Data Sources

| File | Required | Purpose |
|------|----------|---------|
| `context/google-ads/data/placement-performance.csv` | Yes (pulled fresh) | Group placement performance |
| `context/google-ads/data/placement-detail.csv` | Yes (pulled fresh) | Video granularity |
| `context/google-ads/data/pmax-placements.csv` | Yes (pulled fresh) | PMax placements |
| `context/google-ads/data/exclusion-lists.csv` | Yes (pulled fresh) | Shared exclusion lists |
| `context/google-ads/data/exclusion-list-items.csv` | Yes (pulled fresh) | List contents |
| `context/google-ads/data/exclusion-list-links.csv` | Yes (pulled fresh) | List-to-campaign linkage |
| `context/google-ads/data/account-exclusions-apps.csv` | Yes (pulled fresh) | Mobile app category exclusions |
| `context/google-ads/data/account-exclusions-labels.csv` | Yes (pulled fresh) | Content label exclusions |
| `context/google-ads/data/account-exclusions-placements.csv` | Yes (pulled fresh) | Placement exclusions |
| `context/google-ads/data/campaign-brand-safety.csv` | Yes (pulled fresh) | Campaign inventory type settings |
| `context/google-ads/data/mobile-app-categories.csv` | Yes (pulled fresh) | Reference: all app categories |
| `context/google-ads/data/campaigns.csv` | Yes (from gads-context) | Campaign types, bid strategies |
| `context/google-ads/data/placement-vtc-by-action.csv` | Yes (pulled fresh) | VTCs segmented by conversion action |
| `context/google-ads/data/conversions-audit.csv` | Yes (from tracking pull) | Conversion action names + primary_for_goal |
| `context/business.md` | Recommended | Vertical, brand sensitivity level |
| `config/ads-context.config.json` | Yes | Customer IDs + conversionActions |

### Script Outputs (generated during Phase 0.6)

| File | Produced by | Purpose |
|------|-------------|---------|
| `context/google-ads/data/placement-vtc-primary.csv` | `resolve-primary-vtc.js` | VTCs filtered to primary actions only |
| `context/google-ads/data/placement-flags.csv` | `analyze-placement-performance.js` | Performance flags |
| `context/google-ads/data/placement-flags-summary.json` | `analyze-placement-performance.js` | Summary stats |
| `context/google-ads/data/placements-for-review.csv` | `analyze-placement-performance.js` | Top 1000 for sub-agent |
| `context/google-ads/data/exclusion-coverage.json` | `analyze-exclusion-coverage.js` | App gaps, coverage, hygiene |

### Sub-Agent Output (generated during Phase 0.7)

| File | Produced by | Purpose |
|------|-------------|---------|
| `context/google-ads/data/placement-content-flags.csv` | `placement-content-reviewer` sub-agent | Content/brand safety flags |

---

## Process

---

### Phase 0: Prerequisites & Route

1. **Parse subcommand:**
   - `performance` → PL-D01–D04 only
   - `safety` → PL-D05–D07 only
   - `hygiene` → PL-D08–D10 only
   - No subcommand (default) → run all modules sequentially

2. **Load config** — read `config/ads-context.config.json`, extract:
   - `googleAds.customerId` and `googleAds.loginCustomerId`

3. **Load business.md** — extract:
   - Vertical (ecommerce / lead gen / SaaS / etc.)
   - Brand sensitivity level if mentioned
   - Target CPA or target ROAS (needed for performance thresholds)
   - If business.md is missing: WARN but continue

4. **Display configuration:**
   ```
   Placement Audit Configuration:
     Account: {customerId}
     Vertical: {vertical}
     Target CPA: ${target_cpa} (or Target ROAS: {target_roas})
     Mode: {performance / safety / hygiene / full}
   ```

---

### Phase 0.1: Config Interview

**Ensure `placementAudit` section in `config/ads-context.config.json` is set up correctly before running.**

1. **Read inputs:**
   - `config/ads-context.config.json` → `placementAudit` section (may be missing)
   - `context/business.md` → target CPA, vertical, bidding strategy, monthly budget

2. **Evaluate each setting** — compare current value against what makes sense for this account. Use the decision logic below to determine the right value, then flag any mismatches.

   **Decision logic per setting:**

   | Setting | How to determine the right value |
   |---------|--------------------------------|
   | `extremeCpaMultiplier` | Default 3.0. If business.md shows tight margins (LTV:CAC < 2:1) or low target CPA, suggest 2.0 for stricter control. If high-margin/growth mode, 3.0 is fine. |
   | `highRoasMultiplier` | Default 0.5. Only relevant for ROAS-mode campaigns. If business.md shows tROAS, keep 0.5. If pure CPA account, note it won't be used. |
   | `minClicks` | Default 50. If monthly budget is low (<$2k/mo on Display/DG), suggest 20-30 to catch issues faster. High budget accounts can afford 50+. |
   | `minWasteSpend` | Default 50. Should roughly equal 0.25-0.5x the target CPA — if tCPA is $200, then $50-100 is appropriate as a fallback floor. |
   | `vtcDiscountFactor` | Default 0.3. Standard for Display/DG. Lower (0.1-0.2) if the account has short conversion windows or mostly direct-response. Higher (0.4-0.5) if long consideration cycle. |
   | `useVtcInWasteCheck` | Default true. Set false only if VTC data is unreliable or the account is pure Search (no Display/DG/Video). |

3. **Present assessment** — show current vs recommended in a single table, with a verdict per row:

   ```
   Placement Audit Config Check:

   Setting                Current    Recommended  Status
   ─────────────────────  ─────────  ───────────  ──────
   extremeCpaMultiplier   3.0        2.0          ⚠ Adjust — tight margins (LTV:CAC 1.17:1)
   highRoasMultiplier     0.5        0.5          ✓ OK
   minClicks              50         50           ✓ OK
   minWasteSpend          50         50           ✓ OK — 0.25x target CPA ($200)
   vtcDiscountFactor      0.3        0.3          ✓ OK — SaaS, 7-day trial cycle
   useVtcInWasteCheck     true       true         ✓ OK — account runs Demand Gen

   Context: Target CPA $200 | SaaS | CPA bidding | Demand Gen active
   ```

   Use ✓ for values that are fine, ⚠ for values that should change (with reason).

4. **If all ✓** — say "Config looks good, proceeding." and move to Phase 0.5.

5. **If any ⚠** — present the recommended changes and ask: "I'd suggest these adjustments — want me to apply them?"
   - If yes → update `config/ads-context.config.json` → `placementAudit`
   - If no → proceed with current values

6. **If section is missing entirely** — generate full section with recommended values, present to user, apply after confirmation.

---

### Phase 0.5: Data Collection

**Pull all fresh placement data. Run queries in parallel where possible.**

```bash
# 1. Placement performance (group view) — 90 days
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query-file=.claude/skills/placement-auditor/reference/placement-performance.gaql \
  --days=90 \
  --output=context/google-ads/data/placement-performance.csv

# 2. Placement detail (detail view) — 90 days
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query-file=.claude/skills/placement-auditor/reference/placement-detail.gaql \
  --days=90 \
  --output=context/google-ads/data/placement-detail.csv

# 3. PMax placements — 90 days
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query-file=.claude/skills/placement-auditor/reference/pmax-placements.gaql \
  --days=90 \
  --output=context/google-ads/data/pmax-placements.csv

# 4. VTC segmented by conversion action — 90 days
# Needed by resolve-primary-vtc.js to filter VTCs to primary actions only
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query-file=.claude/skills/placement-auditor/reference/placement-vtc-by-action.gaql \
  --days=90 \
  --allow-empty \
  --output=context/google-ads/data/placement-vtc-by-action.csv

# 5. Conversions audit (if not already present or >7 days old)
# Provides conversion action names and primary_for_goal flag
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query-file=.claude/skills/tracking-specialist/reference/conversions-all.gaql \
  --no-date-range \
  --output=context/google-ads/data/conversions-audit.csv

# 5a. Shared exclusion lists (no date range — structural)
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query="SELECT shared_set.resource_name, shared_set.id, shared_set.name, shared_set.type, shared_set.status, shared_set.member_count, shared_set.reference_count FROM shared_set WHERE shared_set.type = 'NEGATIVE_PLACEMENTS' AND shared_set.status = 'ENABLED'" \
  --no-date-range \
  --allow-empty \
  --output=context/google-ads/data/exclusion-lists.csv

# 5b. List-to-campaign linkage
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query="SELECT campaign.id, campaign.name, shared_set.id, shared_set.name, shared_set.type, shared_set.member_count, campaign_shared_set.status FROM campaign_shared_set WHERE shared_set.type = 'NEGATIVE_PLACEMENTS' AND shared_set.status = 'ENABLED'" \
  --no-date-range \
  --allow-empty \
  --output=context/google-ads/data/exclusion-list-links.csv

# 5c. List contents
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query="SELECT shared_set.id, shared_set.name, shared_criterion.criterion_id, shared_criterion.type, shared_criterion.placement.url, shared_criterion.youtube_channel.channel_id, shared_criterion.youtube_video.video_id, shared_criterion.mobile_app_category.mobile_app_category_constant FROM shared_criterion WHERE shared_set.type = 'NEGATIVE_PLACEMENTS'" \
  --no-date-range \
  --allow-empty \
  --output=context/google-ads/data/exclusion-list-items.csv

# 6a. Account exclusions — app categories
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query="SELECT customer_negative_criterion.resource_name, customer_negative_criterion.id, customer_negative_criterion.type, customer_negative_criterion.mobile_app_category.mobile_app_category_constant FROM customer_negative_criterion WHERE customer_negative_criterion.type = 'MOBILE_APP_CATEGORY'" \
  --no-date-range \
  --allow-empty \
  --output=context/google-ads/data/account-exclusions-apps.csv

# 6b. Account exclusions — content labels
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query="SELECT customer_negative_criterion.resource_name, customer_negative_criterion.id, customer_negative_criterion.type, customer_negative_criterion.content_label.type FROM customer_negative_criterion WHERE customer_negative_criterion.type = 'CONTENT_LABEL'" \
  --no-date-range \
  --allow-empty \
  --output=context/google-ads/data/account-exclusions-labels.csv

# 6c. Account exclusions — placements
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query="SELECT customer_negative_criterion.resource_name, customer_negative_criterion.id, customer_negative_criterion.type, customer_negative_criterion.placement.url, customer_negative_criterion.youtube_video.video_id, customer_negative_criterion.youtube_channel.channel_id FROM customer_negative_criterion WHERE customer_negative_criterion.type IN ('PLACEMENT', 'YOUTUBE_VIDEO', 'YOUTUBE_CHANNEL', 'PLACEMENT_LIST')" \
  --no-date-range \
  --allow-empty \
  --output=context/google-ads/data/account-exclusions-placements.csv

# 7. Campaign brand safety settings
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query="SELECT campaign.id, campaign.name, campaign.advertising_channel_type, campaign.video_brand_safety_suitability FROM campaign WHERE campaign.status = 'ENABLED' AND campaign.advertising_channel_type IN ('VIDEO', 'DISPLAY', 'DEMAND_GEN', 'PERFORMANCE_MAX')" \
  --no-date-range \
  --output=context/google-ads/data/campaign-brand-safety.csv

# 8. Mobile app categories (reference data — only if not already cached)
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query="SELECT mobile_app_category_constant.resource_name, mobile_app_category_constant.id, mobile_app_category_constant.name FROM mobile_app_category_constant" \
  --no-date-range \
  --output=context/google-ads/data/mobile-app-categories.csv
```

**Check campaigns.csv** — if >3 days old, re-pull via gads-context.

---

### Phase 0.6: Run Analysis Scripts

**Run analysis scripts to pre-process raw CSVs into condensed outputs.**

```bash
cd .claude/skills/placement-auditor/scripts && npm install --silent && cd -

# Step 1: Resolve VTCs to primary conversion actions only
# Uses config.googleAds.conversionActions, falls back to primary_for_goal from conversions-audit.csv
node .claude/skills/placement-auditor/scripts/resolve-primary-vtc.js \
  --vtc-csv=context/google-ads/data/placement-vtc-by-action.csv \
  --conversions-audit-csv=context/google-ads/data/conversions-audit.csv \
  --output=context/google-ads/data/placement-vtc-primary.csv

# Step 2: Performance analysis — flags zero-click, high-CTR, high-CPA, bad domains
# Consumes primary VTC lookup from Step 1 for accurate adjusted_conversions
node .claude/skills/placement-auditor/scripts/analyze-placement-performance.js \
  --performance-csv=context/google-ads/data/placement-performance.csv \
  --detail-csv=context/google-ads/data/placement-detail.csv \
  --pmax-csv=context/google-ads/data/pmax-placements.csv \
  --domain-patterns=.claude/skills/placement-auditor/reference/domain-patterns.json \
  --campaigns-csv=context/google-ads/data/campaigns.csv \
  --portfolios-csv=context/google-ads/data/bidding-strategies.csv \
  --vtc-primary-csv=context/google-ads/data/placement-vtc-primary.csv \
  --output=context/google-ads/data/placement-flags.csv

# Exclusion coverage analysis — app gaps, campaign coverage, list hygiene
node .claude/skills/placement-auditor/scripts/analyze-exclusion-coverage.js \
  --app-exclusions-csv=context/google-ads/data/account-exclusions-apps.csv \
  --app-categories-csv=context/google-ads/data/mobile-app-categories.csv \
  --exclusion-lists-csv=context/google-ads/data/exclusion-lists.csv \
  --list-items-csv=context/google-ads/data/exclusion-list-items.csv \
  --list-links-csv=context/google-ads/data/exclusion-list-links.csv \
  --campaigns-csv=context/google-ads/data/campaigns.csv \
  --placement-performance-csv=context/google-ads/data/placement-performance.csv \
  --output=context/google-ads/data/exclusion-coverage.json
```

---

### Phase 0.7: Content Review Sub-Agent

**Spawn the `placement-content-reviewer` sub-agent to review top placements for multilingual content/brand safety issues.**

1. Spawn the sub-agent with:
   - Path to `context/google-ads/data/placements-for-review.csv`
   - Target market language from `business.md` (default: English)
   - Output path: `context/google-ads/data/placement-content-flags.csv`
2. The sub-agent reads placements, classifies content, writes flags
3. Continue to Phase 1 after sub-agent completes

**Sub-agent prompt template:**
```
Review the placements in context/google-ads/data/placements-for-review.csv for content quality and brand safety issues. The target market is {language/market from business.md}. Write flagged placements to context/google-ads/data/placement-content-flags.csv.
```

---

### Phase 1: Run Diagnostics

**Read `reference/diagnostic-rules-shared.md`** for scoring model and data sources.

**Read the condensed script outputs** (NOT raw CSVs):
1. `context/google-ads/data/placement-flags.csv` — performance flags
2. `context/google-ads/data/placement-flags-summary.json` — summary stats
3. `context/google-ads/data/placement-content-flags.csv` — content flags from sub-agent
4. `context/google-ads/data/exclusion-coverage.json` — exclusion analysis

**For each module in scope:**

**Performance & App Audit (PL-D01–D04):**
- Read `reference/diagnostic-rules-performance.md`
- Run PL-D01 using `exclusion-coverage.json` → `app_audit`
- Run PL-D02 using `placement-flags.csv` (performance flags)
- Run PL-D03 using `placement-flags.csv` (video flags) + `placement-content-flags.csv`
- Run PL-D04 using `placement-flags.csv` (domain flags) + `placement-content-flags.csv`

**Brand Safety & Coverage (PL-D05–D07):**
- Read `reference/diagnostic-rules-safety.md`
- Run PL-D05 using `exclusion-coverage.json` → `campaign_coverage`
- Run PL-D06 using `campaign-brand-safety.csv` + `account-exclusions-labels.csv`
- Run PL-D07 using `placement-flags.csv` (PMAX_BAD_DOMAIN) + content flags

**Hygiene & Monitoring (PL-D08–D10):**
- Read `reference/diagnostic-rules-hygiene.md`
- Run PL-D08 using `placement-flags.csv` (filtered to DEMAND_GEN)
- Run PL-D09 using `exclusion-coverage.json` → `list_hygiene`
- Run PL-D10 using content flags + `placements-for-review.csv`

---

### Phase 2: Score & Log

1. **Read `reference/report-template.md`** for scoring model and log entry format.
2. Calculate module scores and overall score per the scoring model.
3. Assign grade:
   - 90-100%: Excellent
   - 70-89%: Good
   - 50-69%: Needs Attention
   - < 50%: Critical
4. **Append to log:** `context/analysis/placement-audit-log.md`. If file doesn't exist, create it with `# Placement Audit Log` header. Use the log entry template from `reference/report-template.md`.

---

### Phase 2.5: Peer Report Lookup (MANDATORY before writing the report)

**Don't send the user from one door to the other.** Before recommending any peer-skill handoff in Phase 3, check whether that peer has already produced a fresh report — and if so, **read it and integrate its findings into THIS report** instead of asking the user to re-run.

The whole point of cross-skill awareness is that a user who runs `/budget-auditor` last week and then runs `/placement-audit` this week sees the budget findings *quoted inside the placement report*, not a redundant "go run budget" instruction. Re-running an auditor that already produced a fresh answer wastes time and obscures the placement-side action.

#### Freshness windows

| Peer skill | Report file | Fresh window |
|---|---|---|
| `/quality-score-auditor` | `context/analysis/quality-score-audit.md` | ≤ 7 days |
| `/search-term-auditor` | `context/analysis/search-term-audit.md` | ≤ 7 days |
| `/keyword-auditor` | `context/analysis/keyword-audit.md` | ≤ 7 days |
| `/budget-auditor` | `context/analysis/budget-audit.md` | ≤ 7 days |
| `/bidding-auditor` | `context/analysis/bidding-audit.md` | ≤ 7 days |
| `/competitive-analyst` | `context/analysis/competitive-audit.md` | ≤ 14 days |
| `/lp-auditor` | `context/analysis/lp-audit.md` | ≤ 14 days |
| `/offer-auditor` | `context/analysis/offer-audit.md` | ≤ 30 days |
| `/tracking-specialist` | `context/analysis/tracking-audit.md` | ≤ 30 days |
| `/account-auditor` | `context/analysis/account-audit.md` | ≤ 30 days |

#### Procedure for each peer that the routing would otherwise hand off to

1. **Check if the file exists.** If not → keep the handoff as a plain "run `/peer-skill`" line.
2. **If it exists, check the date in the report header against the freshness window.** The report header date is canonical. mtime is a sanity check — if mtime is *older* than the header date, warn the user that something is off.
3. **If fresh:** open the report and read its **executive read / top findings / module scores**. Pull out the 1–3 findings that overlap with this audit's flagged placements, campaigns, or ad groups. Use them to:
   - **Enrich the Executive read at the top of `placement-audit.md`** — quote the peer's score, the headline finding, and the date inline.
   - **Replace** the routing line "run `/peer-skill`" with: **"Review the existing {date} {peer} report at {path} — top finding: '{one-liner}'. Re-run only if you want fresher data."**
   - In Recommended Actions / Routing, when a peer handoff is the recommended action, quote the peer's specific finding so the user can act without leaving this report.
4. **If stale:** mention "a previous {peer} report exists from {date} but is {N} days old — recommend re-running before relying on it" and keep the handoff as a re-run.
5. **If missing:** standard "run `/peer-skill`" handoff.

#### When a fresh peer report contradicts a placement hypothesis

Say so explicitly in the Executive read. Example: placement-auditor flags a Demand Gen campaign for mobile-game waste — but the fresh tracking-audit shows the conversion event for that campaign is misfiring. The waste finding is then unreliable; placement exclusions won't help if the conversion isn't being recorded. Conversely, a fresh budget-audit may show the campaign in question is budget-capped, which means low click volume on flagged placements is expected, not a true waste signal. **The placement report must surface these contradictions, not silently propose exclusions.**

That cross-skill validation is the entire reason this phase exists. A placement audit that ignores a fresh tracking, budget, or bidding audit produces a confidently-wrong recommendation.

---

### Phase 3: Write Report

Write `context/analysis/placement-audit.md` using `reference/report-template.md`.

This report is regenerated on each run (overwrites previous). The log (Phase 2) preserves history.

**Lead with the Executive read** — the 6-slot prose contract defined in `reference/report-template.md`. Apply Phase 2.5 lookup results to slot 4 (inline-quoted fresh peer findings) and to every line in Recommended Actions / Routing that points to a peer skill.

Fill in all sections in this order:
1. **Executive read** (prose, ≤300 words, no bullets) — score meaning, 1–3 priorities w/ why, what's NOT a problem, fresh peer findings inline, how-to-read, score trend.
2. Overall score + grade
3. Module scores breakdown
4. Critical Issues (sorted by impact) — with peer findings integrated when fresh
5. Placement Type Breakdown, Top Wasters
6. All diagnostic results per module
7. Recommended Actions / Routing — apply Phase 2.5 results: every line says either "run /peer" (missing/stale) or "review existing {date} report at {path}" (fresh, with the one-liner finding)
8. Data Summary

---

### Phase 4: Present Results & Offer Optimizer

Already written in Phase 3; Phase 4 is the user-facing presentation. The reader should be able to act from the **Executive read alone** — that's the bar. Everything else is reference material.

Print to user in this order:

1. **Executive read** (the prose section from the report — quote it verbatim, don't re-summarize). It already covers score-meaning, this-week priorities w/ why, what's-NOT-a-problem, fresh peer findings inline, how-to-read, score trend.
2. Score, grade, mode, run timestamp.
3. Module score table.
4. Top issues — sorted by severity, with specific fix actions.
5. **Routing recommendations** — apply Phase 2.5 lookup results to every line. Each peer handoff says either "review existing {date} report at {path} (top finding: ...)" or "run `/peer-skill`".
6. Note location of full report: `context/analysis/placement-audit.md`.
7. **If any WARN or FAIL finding has an optimizer action:**
   - List the specific optimizer commands that would fix each issue
   - Ask: "Would you like me to start the placement optimizer to fix these issues? It will show you a dry-run preview of all changes before applying anything."
8. If user agrees → hand off to `placement-optimizer` with the appropriate subcommand

### DIAGNOSE → Optimizer Routing Table

| DIAGNOSE Result | Optimizer Command |
|---|---|
| PL-D01 WARN/FAIL (app categories) | `/placement-optimize apps` |
| PL-D02 FAIL (performance-failing) | `/placement-optimize performance` |
| PL-D03 FAIL (brand-unsafe video) | `/placement-optimize safety` |
| PL-D04 FAIL (known-bad domains) | `/placement-optimize safety` |
| PL-D05 FAIL (no exclusion lists) | `/placement-optimize lists` |
| PL-D06 WARN (brand safety config) | `/placement-optimize safety` |
| PL-D07 WARN (PMax brand-unsafe) | `/placement-optimize safety` |
| PL-D08 WARN/FAIL (DG channels) | Advisory only — no optimizer action |
| PL-D09 WARN (list hygiene) | `/placement-optimize lists` |
| PL-D10 INFO (spot-check) | Manual review — no optimizer action |
| Multiple FAILs | `/placement-optimize` (full) |
| All PASS | No action — re-audit in 30 days |
