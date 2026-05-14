---
name: placement-optimizer
description: Apply placement exclusions, brand safety settings, and exclusion list changes via Google Ads API with dry-run approval. Reads placement-auditor output. Use to fix or clean up placements.
argument-hint: "[action]"
---

# Placement Optimizer Skill

Applies placement exclusions, brand safety settings, and exclusion list management changes to Google Ads accounts. Reads findings from `placement-auditor`, generates mutation operations, and applies them via the API with mandatory dry-run approval.

**This skill writes to the Google Ads account. Always dry-run first.**

| Action | ID | API Service | Level |
|--------|------|-------------|-------|
| Exclude mobile app placements | PL-E01 | `CustomerNegativeCriterionService` | Account |
| Exclude performance-failing placements | PL-E02 | `SharedCriterionService` + `CampaignSharedSetService` | Shared list |
| Exclude brand-unsafe video placements | PL-E03 | `CustomerNegativeCriterionService` or `SharedCriterionService` | Account or list |
| Exclude known-bad domains | PL-E04 | `SharedCriterionService` | Shared list |
| Configure brand safety settings | PL-E05 | `CustomerNegativeCriterionService` + `CampaignService` | Account + campaign |
| Update/consolidate exclusion lists | PL-E06 | `SharedSetService` + `SharedCriterionService` + `CampaignSharedSetService` | List management |
| Automated exclusion scripts | PL-E07 | N/A (advisory) | Template output |

**Not built by this skill (per de-duplication log):**
- Diagnosing/scoring placement issues → `placement-auditor` (`/placement-auditor`)
- Bid strategy changes → bidding-specialist
- New campaign creation → campaign-builder
- Audience exclusions → audience-specialist (future)

## Command Format

```
/placement-optimizer                  # Apply all recommended changes (with dry-run first)
/placement-optimizer apps             # PL-E01 only (mobile app exclusions)
/placement-optimizer performance      # PL-E02 only (performance-failing placements)
/placement-optimizer safety           # PL-E03, PL-E04, PL-E05 (brand safety)
/placement-optimizer lists            # PL-E06 only (exclusion list management)
```

**Prerequisites:** Requires `context/analysis/placement-audit.md` from a recent `/placement-auditor` run. If missing or >24 hours old: "Run `/placement-auditor` first to generate fresh findings."

**Output:**
- Changes applied to Google Ads account (on approval)
- Changelog at `context/analysis/placement-changelog.md`
- Operations file at `created/placement-ops/operations-{YYYY-MM-DD}.json`

---

## Data Sources

| File | Required | Purpose |
|------|----------|---------|
| `context/analysis/placement-audit.md` | Yes | Audit findings to act on |
| `context/google-ads/data/placement-flags.csv` | Yes | Detailed placement flags |
| `context/google-ads/data/exclusion-coverage.json` | Yes | Exclusion state analysis |
| `context/google-ads/data/account-exclusions-apps.csv` | Yes (re-pulled fresh) | Current app exclusions |
| `context/google-ads/data/account-exclusions-labels.csv` | Yes (re-pulled fresh) | Current content label exclusions |
| `context/google-ads/data/account-exclusions-placements.csv` | Yes (re-pulled fresh) | Current placement exclusions |
| `context/google-ads/data/exclusion-lists.csv` | Yes (re-pulled fresh) | Current shared sets |
| `context/google-ads/data/exclusion-list-items.csv` | Yes (re-pulled fresh) | Current list contents |
| `context/google-ads/data/exclusion-list-links.csv` | Yes (re-pulled fresh) | Current list linkage |
| `context/google-ads/data/campaigns.csv` | Yes | Campaign types |
| `context/google-ads/data/mobile-app-categories.csv` | Yes | App category reference |
| `context/business.md` | Recommended | App install campaigns check |
| `config/ads-context.config.json` | Yes | Customer IDs |

---

## Process

---

### Phase 0: Prerequisites & Freshness Check

1. **Check audit report exists:**
   - Read `context/analysis/placement-audit.md`
   - If missing: STOP → "Run `/placement-auditor` first to generate findings."
   - If file modification time >24 hours ago: STOP → "Audit report is stale (>24h). Run `/placement-auditor` first for fresh findings."

2. **Parse subcommand:**
   - `apps` → PL-E01 only
   - `performance` → PL-E02 only
   - `safety` → PL-E03, PL-E04, PL-E05
   - `lists` → PL-E06 only
   - No subcommand → all applicable execute actions

3. **Load config** — read `config/ads-context.config.json`, extract customer IDs

4. **Re-pull current exclusion state** (always, to ensure we don't duplicate):
   ```bash
   # Account exclusions — apps
   node .claude/skills/gads-context/scripts/query.js \
     --customer-id={customer_id} \
     --login-customer-id={login_customer_id} \
     --query="SELECT customer_negative_criterion.resource_name, customer_negative_criterion.id, customer_negative_criterion.type, customer_negative_criterion.mobile_app_category.mobile_app_category_constant FROM customer_negative_criterion WHERE customer_negative_criterion.type = 'MOBILE_APP_CATEGORY'" \
     --no-date-range --allow-empty \
     --output=context/google-ads/data/account-exclusions-apps.csv

   # Account exclusions — labels
   node .claude/skills/gads-context/scripts/query.js \
     --customer-id={customer_id} \
     --login-customer-id={login_customer_id} \
     --query="SELECT customer_negative_criterion.resource_name, customer_negative_criterion.id, customer_negative_criterion.type, customer_negative_criterion.content_label.type FROM customer_negative_criterion WHERE customer_negative_criterion.type = 'CONTENT_LABEL'" \
     --no-date-range --allow-empty \
     --output=context/google-ads/data/account-exclusions-labels.csv

   # Account exclusions — placements
   node .claude/skills/gads-context/scripts/query.js \
     --customer-id={customer_id} \
     --login-customer-id={login_customer_id} \
     --query="SELECT customer_negative_criterion.resource_name, customer_negative_criterion.id, customer_negative_criterion.type, customer_negative_criterion.placement.url, customer_negative_criterion.youtube_video.video_id, customer_negative_criterion.youtube_channel.channel_id FROM customer_negative_criterion WHERE customer_negative_criterion.type IN ('PLACEMENT', 'YOUTUBE_VIDEO', 'YOUTUBE_CHANNEL', 'PLACEMENT_LIST')" \
     --no-date-range --allow-empty \
     --output=context/google-ads/data/account-exclusions-placements.csv

   # Shared sets + linkage + contents
   node .claude/skills/gads-context/scripts/query.js \
     --customer-id={customer_id} \
     --login-customer-id={login_customer_id} \
     --query="SELECT shared_set.resource_name, shared_set.id, shared_set.name, shared_set.type, shared_set.status, shared_set.member_count, shared_set.reference_count FROM shared_set WHERE shared_set.type = 'NEGATIVE_PLACEMENTS' AND shared_set.status = 'ENABLED'" \
     --no-date-range --allow-empty \
     --output=context/google-ads/data/exclusion-lists.csv

   node .claude/skills/gads-context/scripts/query.js \
     --customer-id={customer_id} \
     --login-customer-id={login_customer_id} \
     --query="SELECT campaign.id, campaign.name, shared_set.id, shared_set.name, shared_set.type, shared_set.member_count, campaign_shared_set.status FROM campaign_shared_set WHERE shared_set.type = 'NEGATIVE_PLACEMENTS' AND shared_set.status = 'ENABLED'" \
     --no-date-range --allow-empty \
     --output=context/google-ads/data/exclusion-list-links.csv

   node .claude/skills/gads-context/scripts/query.js \
     --customer-id={customer_id} \
     --login-customer-id={login_customer_id} \
     --query="SELECT shared_set.id, shared_set.name, shared_criterion.criterion_id, shared_criterion.type, shared_criterion.placement.url, shared_criterion.youtube_channel.channel_id, shared_criterion.youtube_video.video_id, shared_criterion.mobile_app_category.mobile_app_category_constant FROM shared_criterion WHERE shared_set.type = 'NEGATIVE_PLACEMENTS'" \
     --no-date-range --allow-empty \
     --output=context/google-ads/data/exclusion-list-items.csv
   ```

5. **Experiment exclusion:** All queries exclude experiment campaigns. Only base campaigns are optimized.

6. **Display configuration:**
   ```
   Placement Optimizer Configuration:
     Account: {customerId}
     Audit report: {date} ({age}h ago)
     Mode: {apps / performance / safety / lists / full}
     Exclusion state: re-pulled fresh ✓
   ```

---

### Phase 0.5: Peer Pre-flight (Cross-Skill Gate)

**Read `reference/handoff-matrix.md`** — it defines the Peer Audit Freshness Table and the Mutation Sensitivity Matrix consumed here.

This phase is the single point where stacked-mutation guards run. It produces an in-memory `peer_context` object (schema in `handoff-matrix.md → Output Contract`) consumed by Phase 1 (operations generation) and Phase 3 (dry-run rendering). It must complete before any operation is generated.

**Step 1 — Refresh the changelog.** The Mutation Sensitivity Matrix needs `context/account-changelog.md` ≤1h old. If stale or missing, auto-pull via `/account-changelog` before continuing. Abort if still stale.

**Step 2 — Walk the Peer Audit Freshness Table.** For each of the 10 peer reports:
1. Stat the file. If absent → record `"no fresh {peer}"` in `freshness_notes`.
2. Parse the report header date (canonical). Compare with file mtime — if mtime is older than the header date by >3 days, record the contradiction in `freshness_notes` (do **not** auto-defer to either; surface in dry-run).
3. If the header date is within the freshness window:
   - **`/tracking-specialist`** with fail/critical findings → push to `hard_blocks` (M layer).
   - **`/strategy-specialist`** (`context/analysis/strategy-audit.md`, ≤30d) with missing/placeholder unit economics → push to `hard_blocks` (B layer). Strategy-specialist is not in the 10-peer rotation table but the universal M/B cascade still applies.
   - Eff/Conv/Bud-layer peer flagging issues on a campaign in the operations plan → push to `soft_warns`.
   - Comp/Struct-layer peers → push to `informational`.

**Step 3 — Walk the Mutation Sensitivity Matrix.** For every campaign in the planned operations, scan `context/account-changelog.md` for entries within the windows defined in the matrix. Classify each match as `hard-warn` or `soft-warn` per the table.

**Step 4 — Hard-block gate.** If `hard_blocks` is non-empty:
- Print the failing finding(s) with the report path and the handoff command (e.g. "Run `/tracking-specialist` to clear M-layer findings").
- **Do not generate operations. Do not run Phase 1.** Stop the session here.

**Step 5 — Hold `peer_context` for Phase 3.** `soft_warns`, `hard_warns`, `informational`, and `freshness_notes` are surfaced in the dry-run output (Phase 3) as a "Cross-skill context" section above the mutation table. `hard_warns` will require an explicit "confirm" prompt before Phase 4 (live apply).

**Never auto-trigger a peer skill** to refresh a stale report — only the changelog (Step 1) is auto-refreshed. Missing peer reports are recorded as `freshness_notes` so the operator knows the picture is incomplete and can decide whether to refresh manually.

---

### Phase 1: Read Audit Findings & Apply Execute Rules

**Read `reference/execute-rules.md`** — contains decision trees for each execute action.

**Read the audit report** and extract all WARN/FAIL findings. For each finding in scope:

1. Look up the corresponding execute rule (PL-E01 through PL-E07)
2. Apply pre-flight checks (deduplication, PMax constraint, shared set limit)
3. Run the decision tree to determine:
   - Exclusion level (account, shared list, campaign)
   - Criterion type (placement, youtube_channel, youtube_video, mobile_app_category, content_label)
   - Target value
4. Generate operations.json entries

**Read current exclusion state** from re-pulled CSVs to deduplicate.

---

### Phase 2: Generate Operations File

1. Assemble all operations into `created/placement-ops/operations-{YYYY-MM-DD}.json`
2. Ensure output directory exists: `mkdir -p created/placement-ops`
3. Include metadata: description, generated_from, date, total operations count
4. Validate: no duplicate operations, all resource_names valid

**Build scripts allowed but temporary:** If writing a helper script (e.g. `build-operations.js`) speeds up generating the operations JSON, that's fine. But delete the script after the operations file is written — it contains hardcoded account-specific logic and is not reusable across accounts.

---

### Phase 3: Dry-Run

```bash
cd .claude/skills/placement-optimizer/scripts && npm install --silent && cd -
node .claude/skills/placement-optimizer/scripts/mutate.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --operations-file=created/placement-ops/operations-{YYYY-MM-DD}.json \
  --mode=dry-run
```

**Render the dry-run output with two sections:**

**1. Cross-skill context** (rendered first, above the mutation table). Use the `peer_context` object built in Phase 0.5. Format:

```
Cross-skill context
───────────────────
HARD-WARN (require "confirm"):
  - {campaign}: {peer} {mutation} {days_ago}d ago (window {window}d) — {rationale from matrix}

SOFT-WARN (informational):
  - {campaign}: {peer} {finding/mutation summary} — {rationale from matrix}

Informational:
  - {peer}: {score/headline finding}

Freshness notes:
  - no fresh /lp-auditor
  - /tracking-specialist mtime 5d older than header — suspicious
```

If the `peer_context` lists are empty, render `Cross-skill context: clean (all peers fresh, no recent overlapping mutations).`

**2. Mutation table** (existing dry-run output) — every proposed change grouped by entity type.

**Ask explicitly:**
- If `hard_warns` is empty → "Ready to apply these changes? (yes / no)"
- If `hard_warns` is non-empty → "Hard-warns above must be acknowledged. Type 'confirm' to proceed, or 'no' to abort." Capture the confirmation alongside the operations file for the audit trail.

---

### Phase 4: Live Apply (Only on User Approval)

Gate: do not start Phase 4 unless (a) the user said "yes"/"go ahead"/"apply" with no hard-warns, OR (b) the user typed "confirm" with hard-warns present. Any other response (including silence on a hard-warn) → STOP, preserve the operations file.

On user approval:

```bash
node .claude/skills/placement-optimizer/scripts/mutate.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --operations-file=created/placement-ops/operations-{YYYY-MM-DD}.json \
  --mode=live \
  --max-ops=200
```

If user says "no": STOP. Preserve the operations file for later review.

---

### Phase 5: Changelog & Memory

1. `mutate.js` automatically writes to `context/analysis/placement-changelog.md`
2. Log to `context/memory/YYYY-MM-DD.md` per the report template
3. Present results summary to the user

---

## Edge Cases

| Scenario | Handling |
|----------|---------|
| No Display/Video/DG/PMax campaigns | Nothing to optimize — report "No eligible campaigns" |
| Placement already excluded | Skip silently (deduplication in Phase 1) |
| Shared set limit reached | Add to existing lists instead of creating new ones |
| PMax placement bad but good in Display | Note conflict in dry-run; let user decide |
| App install business | Warn before excluding all app categories |
| >200 operations | Require explicit `--max-ops=N` override |
| Operations file from previous run exists | Overwrite with new file (timestamped) |
| M layer dirty (`/tracking-specialist` fresh fail/critical) | Phase 0.5 hard-block — refuse Phase 1; print finding + handoff to `/tracking-specialist` |
| B layer dirty (`/strategy-specialist` fresh, unit economics missing) | Phase 0.5 hard-block — refuse Phase 1; print finding + handoff to `/strategy-specialist --execute unit-economics` |
| Hard-warn in Mutation Sensitivity Matrix | Phase 3 dry-run lists in Cross-skill context with `WARN:` prefix; require "confirm" before Phase 4 |
| `account-changelog` >1h old | Auto-pull via `/account-changelog`; abort Phase 0.5 if still stale |
| Peer report mtime contradicts header date by >3d | Surface in dry-run `freshness_notes`; never auto-defer to either |
