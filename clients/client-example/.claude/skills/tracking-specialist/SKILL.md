---
name: tracking-specialist
description: Audit conversion tracking across 50 diagnostics in 7 modules (completeness, tag health, consent, attribution, OCT, hygiene, advanced). Scores 0-100 per module. Use for tracking and conversion setup audits.
argument-hint: "[module] [--url URL]"
---

# Tracking Specialist Skill

Audits conversion tracking configuration across 7 modules (50 diagnostics):

| Module | IDs | Method |
|--------|-----|--------|
| **Completeness** | D01-D07 | API |
| **Tag Health** | D08-D17 | API + Chrome DevTools + interactive |
| **Consent Mode** | D25-D29 | Chrome DevTools + API + interactive |
| **Attribution** | D30-D35 | API + interactive |
| **OCT** | D36-D41 | API + interactive |
| **Data Hygiene** | D42-D45 | API |
| **Advanced** | D46-D50 | Chrome DevTools + API + interactive |

**Not built (blocked — needs GTM API):** Enhanced Conversions (D18-D21), Server-Side Tagging (D22-D24).

## Command Format

```
/tracking-audit                          # Default: runs all available modules sequentially
/tracking-audit completeness             # D01-D07 only (API)
/tracking-audit tag-health               # D08-D17 (API + Chrome DevTools)
/tracking-audit consent                  # D25-D29 (Chrome DevTools + API)
/tracking-audit attribution              # D30-D35 (API)
/tracking-audit oct                      # D36-D41 (API + interactive)
/tracking-audit hygiene                  # D42-D45 (API)
/tracking-audit advanced                 # D46-D50 (mixed)
/tracking-audit --url=https://...        # Preload URL for Chrome DevTools checks
```

**Examples:**
- `/tracking-audit` — Full audit across all modules
- `/tracking-audit completeness` — Quick completeness check
- `/tracking-audit tag-health --url=https://example.com/thank-you` — Tag health with on-page checks
- `/tracking-audit attribution` — Attribution settings audit
- `/tracking-audit --url=https://example.com` — Full audit with Chrome DevTools pre-loaded

---

## Data Sources

| File | Required | Purpose |
|------|----------|---------|
| `context/google-ads/data/conversions-audit.csv` | Yes (pulled fresh) | All conversion actions, unfiltered |
| `context/google-ads/data/conversions-daily.csv` | Yes for D09/D10 (pulled fresh) | Daily conversion volumes, 14 days |
| `context/google-ads/data/conversion-goal-config.csv` | Yes (pulled fresh) | Which campaigns use account-default vs custom goals |
| `context/google-ads/data/custom-conversion-goals.csv` | Yes (pulled fresh) | Custom goal sets — which conversion actions each contains |
| `context/google-ads/data/campaign-goals.csv` | Already exists | Campaign goal categories with biddable flags (from gads-context) |
| `context/google-ads/data/conversions-attribution.csv` | For attribution module | Attribution model, windows per action |
| `context/business.md` | Yes | Vertical, conversion events, targets |
| `config/ads-context.config.json` | Yes | Customer IDs |
| `context/account-changelog.md` | Recommended | Recent tracking changes |

---

## Process

---

### Phase 0: Prerequisites & Route

1. **Parse subcommand and flags:**
   - `completeness` → D01-D07 only
   - `tag-health` → D08-D17
   - `consent` → D25-D29
   - `attribution` → D30-D35
   - `oct` → D36-D41
   - `hygiene` → D42-D45
   - `advanced` → D46-D50
   - No subcommand (default) → run all available modules sequentially
   - `--url=` → store for Chrome DevTools phases

2. **Load config** — read `config/ads-context.config.json`, extract:
   - `googleAds.customerId` and `googleAds.loginCustomerId`
   - `trackingAudit` section if it exists (optional overrides)

3. **Load business.md** — extract and display:
   - Vertical (ecommerce / lead gen / SaaS)
   - Expected conversion events
   - Target CPA / ROAS
   - If business.md is missing or has no conversion events listed, ask the user before proceeding

4. **Check account-changelog.md** — scan for recent conversion tracking changes (last 7 days). If found, display them.

Display configuration:
```
Tracking Audit Configuration:
  Account: {customerId}
  Vertical: {vertical}
  Mode: {completeness / tag-health / full}
  Expected conversions: {list from business.md}
  Target CPA: ${X} | Target ROAS: {X}x
```

---

### Phase 0.5: Data Pull

**Always pull fresh conversion data for audit — do NOT rely on existing conversions.csv from gads-context.**

```bash
# Pull ALL conversion actions (unfiltered, no date range)
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query-file=.claude/skills/tracking-specialist/reference/conversions-all.gaql \
  --no-date-range \
  --allow-empty \
  --output=context/google-ads/data/conversions-audit.csv
```

**Always pull campaign goal configuration (which campaigns override defaults):**

```bash
# Pull goal config level per campaign (CUSTOMER = account-default, CAMPAIGN = custom goals)
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query-file=.claude/skills/tracking-specialist/reference/conversion-goal-config.gaql \
  --no-date-range \
  --allow-empty \
  --output=context/google-ads/data/conversion-goal-config.csv

# Pull custom conversion goal definitions (which conversion actions each custom goal contains)
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query-file=.claude/skills/tracking-specialist/reference/custom-conversion-goals.gaql \
  --no-date-range \
  --allow-empty \
  --output=context/google-ads/data/custom-conversion-goals.csv
```

**If attribution module in scope:**

```bash
# Pull attribution settings per conversion action
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query-file=.claude/skills/tracking-specialist/reference/conversions-attribution.gaql \
  --no-date-range \
  --allow-empty \
  --output=context/google-ads/data/conversions-attribution.csv
```

**If D09/D10 in scope (default mode or tag-health mode):**

```bash
# Pull daily conversion data for anomaly detection (14 days)
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query-file=.claude/skills/tracking-specialist/reference/conversions-daily.gaql \
  --days=14 \
  --allow-empty \
  --output=context/google-ads/data/conversions-daily.csv
```

Display data pull summary:
```
Data Pulled:
| File                         | Rows | Status |
|------------------------------|------|--------|
| conversions-audit.csv        | {n}  | OK     |
| conversion-goal-config.csv   | {n}  | OK     |
| custom-conversion-goals.csv  | {n}  | OK / No custom goals |
| conversions-daily.csv        | {n}  | OK     |
```

If conversions-audit.csv has zero rows, STOP and tell user: "No conversion actions found in this account. Set up conversion tracking first."

---

### Phase 1: API Diagnostics

**Read `reference/diagnostic-rules-shared.md` first (CSV columns, origin filtering, scoring).**

**Then read ONLY the module-specific rules for the requested subcommand:**

| Subcommand | Read these reference files |
|---|---|
| `completeness` | `diagnostic-rules-completeness.md` + `vertical-config-rules.md` + `naming-conventions.md` |
| `tag-health` | `diagnostic-rules-tag-health.md` + `tag-verification-patterns.md` (Phase 2 only) |
| `consent` | `diagnostic-rules-consent.md` + `tag-verification-patterns.md` (for D25, D28) |
| `attribution` | `diagnostic-rules-attribution.md` + `vertical-config-rules.md` |
| `oct` | `diagnostic-rules-oct.md` |
| `hygiene` | `diagnostic-rules-hygiene.md` |
| `advanced` | `diagnostic-rules-advanced.md` + `tag-verification-patterns.md` (for D46) |
| Default (all) | Run modules sequentially. Load and release each module's references before loading the next. |

**Important:** When running all modules (default), do NOT load all reference files at once. Run completeness first, then tag-health, then attribution, etc. — loading each module's references fresh for that phase.

Read `conversions-audit.csv`, `conversion-goal-config.csv`, `custom-conversion-goals.csv`, and `conversions-daily.csv` into working memory.

**Campaign-level goal detection:** Before running D02 and D07, check `conversion-goal-config.csv`:
1. Identify campaigns with `goal_config_level = CAMPAIGN` (these use custom goals, not account defaults)
2. For those campaigns, look up their `custom_conversion_goal` resource name in `custom-conversion-goals.csv` to find which specific conversion actions they bid on
3. Build a lookup: `{campaign_name → [conversion_action_resource_names]}`

**How this affects diagnostics:**
- D02: Do not flag an account-level secondary action as wrong if it appears in a custom goal for specific campaigns. Report as INFO with context: "Action X is secondary at account level but used as a custom goal in campaigns: Y, Z"
- D07: Report two layers — account defaults AND campaign overrides. A campaign using `goal_config_level = CAMPAIGN` is intentionally overriding, not misconfigured
- If ALL campaigns use `goal_config_level = CUSTOMER`, campaign-level goals are not a factor — evaluate purely on account defaults

Run each diagnostic in order. For each, produce a structured result:

```
ID: TRK-DXX
Name: {diagnostic name}
Status: PASS | WARN | FAIL | SKIP
Severity: Critical | High | Medium
Points: {earned} / {possible}
Details: {what was found}
Recommendation: {if WARN or FAIL, what to do}
```

**Completeness diagnostics (D01-D07):**

| ID | Check | Key columns |
|----|-------|------------|
| D01 | Coverage: business.md events vs actual actions | name, status, category, all_conversions |
| D02 | Primary/secondary: correct classification | primary_for_goal, category, name |
| D03 | Duplicates: same event tracked multiple times | category, primary_for_goal, type, name |
| D04 | Naming: consistent, descriptive names | name |
| D05 | Goal category: correct category per vertical | category, name |
| D06 | Counting: ONE vs EVERY per vertical | counting_type, category |
| D07 | Account defaults: intentional primary set | primary_for_goal, category, name |

**Tag health diagnostics (D08-D10) — API tier:**

| ID | Check | Key columns |
|----|-------|------------|
| D08 | Status: all primary actions ENABLED | status, primary_for_goal |
| D09 | Zero-check: 0 conversions in 7+ days | all_conversions (daily) |
| D10 | Volume anomaly: >50% drop vs prior period | all_conversions (daily, 7d vs 7d) |

After running all API diagnostics, display results table:

```
API Diagnostic Results:
| ID   | Diagnostic            | Status | Pts     | Detail                    |
|------|-----------------------|--------|---------|---------------------------|
| D01  | Coverage              | PASS   | 15/15   | All 2 business events covered |
| D02  | Primary/Secondary     | PASS   | 15/15   | ...                       |
| ...  | ...                   | ...    | ...     | ...                       |
```

---

### Phase 1.5: Chrome DevTools Gate

**Skip this phase if mode is `completeness`.**

After displaying API results, present Chrome DevTools option. Ask:

**Question:** "API diagnostics complete. Want to run on-page tag health checks (D11-D16)?"

| Option | Description |
|--------|-------------|
| Passive check only | I'll visit a URL and check what's already loaded (D11-D12 reliable, D13-D16 only if post-conversion page) |
| Full conversion test | I'll perform a test conversion on your site (fill a form / add to cart) to verify tags fire correctly (D11-D16 all reliable) |
| Skip on-page checks | D11-D16 will be marked as SKIP in the report |

**If D10 was FAIL:** Tell the user Chrome DevTools checks are strongly recommended to diagnose the tracking issue.

**If passive check:** Ask for URL (landing page or thank-you page). D13-D16 will be best-effort — mark as SKIP if no conversion data visible on the page.

**If full conversion test:** Ask for:
1. **URL** — the page where the conversion happens (contact form, product page, checkout)
2. **Vertical confirmation** to determine test action:

| Vertical | Test action |
|----------|-------------|
| Lead Gen | Fill and submit a form (name, email, phone) |
| SaaS | Fill signup/trial form |
| Ecommerce | Add product to cart → begin checkout (do NOT complete payment) |

3. **Explicit consent** — before performing ANY action on the site, confirm:

```
I'm about to perform the following actions on your site:
- Navigate to: {url}
- {describe exact action: "Fill the contact form with test data and submit" / "Add the first product to cart and proceed to checkout"}

This will create a real form submission / trigger a real add-to-cart event.
Proceed? (Yes / No)
```

**CRITICAL:** Do NOT click, fill, or submit anything without the user confirming "Yes" to the specific action described. If the user says no or hesitates, fall back to passive check.

---

### Phase 2: Chrome DevTools Diagnostics (D11-D16)

**Read `reference/tag-verification-patterns.md` for JS patterns and network request signatures.**

#### Step 1: Passive checks (D11-D12) — always run first

Navigate to URL via `mcp__chrome-devtools__navigate_page`. Wait for page to fully load.

| ID | Check | Method |
|----|-------|--------|
| D11 | Google Tag presence | `evaluate_script`: check `typeof gtag`, `typeof google_tag_manager`, `window.dataLayer`. Also check network requests for `googletagmanager.com`. |
| D12 | Conversion Linker | Check network requests for `googleads.g.doubleclick.net`. Check cookies for `_gcl_aw`, `_gcl_dc` via `evaluate_script`. |

#### Step 2: Conversion test (D13-D16) — only if user approved full test

**Before acting:** Clear network requests by navigating, then perform the agreed action:

| Vertical | Actions |
|----------|---------|
| Lead Gen / SaaS | Use `mcp__chrome-devtools__fill` to populate form fields with test data (e.g., "Test User", "test@example.com", "0000000000"). Use `mcp__chrome-devtools__click` to submit. |
| Ecommerce | Use `mcp__chrome-devtools__click` to add a product to cart. Navigate to cart/checkout if needed. Do NOT enter payment details or complete purchase. |

**After the action:** Wait 2-3 seconds for tags to fire, then capture:

| ID | Check | Method |
|----|-------|--------|
| D13 | Tag firing | `list_network_requests`: look for requests to `pagead/conversion/` with label, value, oid params. |
| D14 | Transaction ID | `evaluate_script`: inspect `window.dataLayer` for events with `transaction_id`. Check `oid=` in conversion requests. |
| D15 | Dynamic value | `evaluate_script`: check dataLayer for `value` parameter. Check if numeric, non-zero, non-static. |
| D16 | Currency | `evaluate_script`: check dataLayer for `currency` parameter. Compare to API `default_currency_code`. |

**D17 (Backend Cross-Check):** Always SKIP. Display manual verification instructions from `reference/diagnostic-rules.md`.

Display Chrome DevTools results:
```
On-Page Diagnostic Results ({url}):
| ID   | Diagnostic            | Status | Detail                           |
|------|-----------------------|--------|----------------------------------|
| D11  | Google Tag Presence   | PASS   | GTM container GTM-XXXXXXX loaded |
| D12  | Conversion Linker     | PASS   | _gcl_aw cookie set               |
| ...  | ...                   | ...    | ...                              |
```

---

### Phase 3: Score & Log

**Calculate scores:**

1. Tally points earned vs points possible (exclude SKIP diagnostics from denominator)
2. Calculate module scores:
   - Completeness: D01-D07 (max 80 pts)
   - Tag Health: D08-D17 (max 70 pts, minus SKIPs)
   - Overall: total earned / total possible as percentage

3. Assign grade:
   - 90-100%: Excellent
   - 70-89%: Good
   - 50-69%: Needs Attention
   - < 50%: Critical

**Append to log:** `context/analysis/tracking-audit-log.md`

If file doesn't exist, create it with header `# Tracking Audit Log`.

Append a timestamped entry using the log template from `reference/report-template.md`.

---

### Phase 3.5: Peer Report Lookup (MANDATORY before writing the report)

**Don't send the user from one door to the other.** Before recommending any peer-skill handoff in Phase 4, check whether that peer has already produced a fresh report — and if so, **read it and integrate its findings into THIS report** instead of asking the user to re-run.

The whole point of cross-skill awareness is that a user who runs `/quality-score-auditor` last week and then runs `/tracking-audit` this week sees the QS findings *quoted inside the tracking report*, not a redundant "go run QS" instruction. Re-running an auditor that already produced a fresh answer wastes time and obscures the tracking-side action.

**Tracking is the M (Measurement) layer** — the *first* hard-block in every other skill's constraint cascade. Most peer findings (CVR, CPA, ROAS, search-term performance, bid-strategy learning, QS Landing Page Experience, etc.) are *invalid* if conversion tracking is broken. That makes peer-lookup integration especially load-bearing here: if this audit finds a misfiring conversion, a duplicate tag, a stale OCT mapping, a Consent Mode v2 gap, or an enhanced-conversions attribution issue, the Executive read MUST flag every fresh peer report whose conclusions depend on the broken signal.

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
| `/strategy-specialist` | `context/analysis/strategy-audit.md` | ≤ 30 days |
| `/account-auditor` | `context/analysis/account-audit.md` | ≤ 30 days |

#### Procedure for each peer that the routing would otherwise hand off to

1. **Check if the file exists.** If not → keep the handoff as a plain "run `/peer-skill`" line.
2. **If it exists, check the date in the report header against the freshness window.** The report header date is canonical. mtime is a sanity check — if mtime is *older* than the header date, warn the user that something is off.
3. **If fresh:** open the report and read its **executive read / top findings / module scores**. Pull out the 1–3 findings that overlap with this audit's flagged conversion actions, campaigns, or tag/consent issues. Use them to:
   - **Enrich the Executive read at the top of `tracking-audit.md`** — quote the peer's score, the headline finding, and the date inline.
   - **Replace** the routing line "run `/peer-skill`" with: **"Review the existing {date} {peer} report at {path} — top finding: '{one-liner}'. Re-run only if you want fresher data."**
   - In Recommendations / Routing, when a peer handoff is the recommended action, quote the peer's specific finding so the user can act without leaving this report.
4. **If stale:** mention "a previous {peer} report exists from {date} but is {N} days old — recommend re-running before relying on it" and keep the handoff as a re-run.
5. **If missing:** standard "run `/peer-skill`" handoff.

#### When a fresh peer report contradicts a tracking finding (or vice versa)

Surface contradictions explicitly in the Executive read. Never auto-defer to the peer and never silently override it. Tracking sits beneath every other skill's findings, so contradictions almost always mean the *peer's* conclusion is unsafe to act on until the tracking issue is fixed. Examples:

- Tracking flags Purchase as misfiring on Campaign X, but a fresh `/bidding-auditor` report calls Campaign X's tROAS "healthy and learned." → Say so: the bid-strategy verdict is built on a broken signal and should not be trusted until D13/D14/D15 are resolved.
- Tracking flags a duplicate Lead tag double-counting on the thank-you page, but a fresh `/search-term-auditor` report celebrates a "high-converting" n-gram. → Say so: the n-gram win is likely inflated by the duplicate; re-evaluate after dedup.
- Tracking finds a stale OCT mapping (offline conversions importing against the wrong action), but `/strategy-specialist` recently re-set targets using that data. → Say so: the targets were set against contaminated data and need a re-baseline once OCT is fixed.
- Tracking finds a Consent Mode v2 gap suppressing conversions, but `/quality-score-auditor` flags Landing Page Experience based on the resulting CVR drop. → Say so: the LPX signal is partly an artefact of consent loss, not page quality alone.
- Tracking finds an enhanced-conversions attribution issue, but `/lp-auditor` Module 4 (Performance) flags low CVR on the affected campaigns. → Say so: the LP CVR finding is unreliable until enhanced conversions are repaired.

That cross-skill validation is the entire reason this phase exists. A tracking audit that ignores fresh peer reports — or a peer audit that ignored a fresh tracking report — produces a confidently-wrong recommendation.

---

### Phase 4: Write Report

Write `context/analysis/tracking-audit.md` using `reference/report-template.md`.

This report is regenerated on each run (overwrites previous). The log (Phase 3) preserves history.

**Lead with the Executive read** — the 6-slot prose contract defined in `reference/report-template.md`. Apply Phase 3.5 lookup results to slot 4 (inline-quoted fresh peer findings) and to every line in Recommendations / Routing that points to a peer skill.

Fill in all sections in this order:
1. **Executive read** (prose, ≤300 words, no bullets) — score meaning, 1–3 priorities w/ why, what's NOT a problem, fresh peer findings inline (with explicit contradictions surfaced), how-to-read, score trend.
2. Overall score + grade
3. Module score breakdown
4. Critical issues (FAIL diagnostics, sorted by severity) — with peer findings integrated when fresh
5. Completeness results table (D01-D07)
6. Tag Health results table (D08-D17)
7. Recommendations (tied to business.md targets) — apply Phase 3.5 results: every line says either "run /peer" (missing/stale) or "review existing {date} report at {path}" (fresh, with the one-liner finding)
8. Manual checks required
9. Data freshness

---

### Phase 5: Summary & Next Steps

Already written in Phase 4; Phase 5 is the user-facing presentation. The reader should be able to act from the **Executive read alone** — that's the bar. Everything else is reference material.

Print to user in this order:

1. **Executive read** (the prose section from the report — quote it verbatim, don't re-summarize). It already covers score-meaning, this-week priorities w/ why, what's-NOT-a-problem, fresh peer findings inline (including contradictions), how-to-read, score trend.
2. Score, grade, mode, run timestamp.
3. Module score table.
4. Top 3 issues — sorted by severity, with specific fix actions.
5. **Recommendations / Routing** — apply Phase 3.5 lookup results to every line. Each peer handoff says either "review existing {date} report at {path} (top finding: ...)" or "run `/peer-skill`".
   - If D01 FAIL: "Missing conversion actions. Set them up in Google Ads following your tracking SOP."
   - If D06 FAIL: "Counting method wrong on {action}. Change from MANY_PER_CLICK to ONE_PER_CLICK in Google Ads > Goals > Conversions."
   - If D09/D10 FAIL: "Tracking may be broken. Run `/tracking-audit tag-health --url={site}` immediately."
   - If a fresh peer report depends on a broken tracking signal: name the contradiction and tell the user to refresh the peer report after the tracking fix lands.
   - If all PASS: "Tracking looks solid. Consider running enhanced conversions checks when available."
6. Note location of full report: `context/analysis/tracking-audit.md`.

**Log to memory:** Write entry to `context/memory/YYYY-MM-DD.md` per memory-logging rules:

```markdown
## Tracking Audit Completed
- Mode: {mode}
- Score: {score}% ({grade})
- Key findings: {list of FAIL/WARN items}
- Fresh peer reports integrated: {list or "none"}
- Report: context/analysis/tracking-audit.md
```
