# Account Auditor — Defaults Diagnostics (AUD-D24)

## AUD-D24: Account-Level Setting Defaults
**Severity:** Medium (5 pts) | **Data:** `conversion-goal-config.csv` (if available), `campaigns-settings.csv`, `business.md`

**Rule:** Account-level settings (conversion goals, audience defaults, auto-applied recommendations) should be intentionally configured, not left at Google's defaults.

**How to check:**

### Conversion goal configuration
1. If `conversion-goal-config.csv` exists (from tracking-specialist or gads-context):
   - Check if campaigns use `goal_config_level = CUSTOMER` (account default) vs `CAMPAIGN` (custom)
   - If all campaigns use account defaults: verify the account-default conversion goals make sense for the business
   - Cross-reference with `business.md` primary conversion events
2. If data not available: SKIP this sub-check with note

### Account-level auto-apply
1. This data is not available via GAQL — requires Change History review
2. Flag as manual review item: "Check Settings > Account settings > Auto-apply recommendations"
3. Recommendation: Most auto-apply settings should be OFF unless intentionally enabled

### Account-level audience settings
1. Not available via GAQL
2. Flag as manual review item: "Check account-level audience settings (observation vs targeting defaults)"

**Pass/Fail:**
- PASS: Conversion goals intentionally configured (custom goals per campaign or verified account defaults)
- WARN: All campaigns on account defaults — may be fine, but should be verified as intentional
- SKIP: Insufficient data to evaluate (no conversion-goal-config.csv available)

**Note:** This is the lightest check — more of an awareness prompt. The key question: "Has someone intentionally configured these account-level settings, or are they still at Google's defaults?"

**Routing on issues:** tracking-specialist (conversion goal config), automation-specialist (auto-apply settings)
