# Diagnostic Rules — Shared Reference

Read first, before any module-specific diagnostic rules file.

## CSV Column Reference (conversions-audit.csv)

| Column | Maps to |
|--------|---------|
| `conversion_action.name` | Action name |
| `conversion_action.status` | ENABLED / PAUSED / REMOVED / HIDDEN |
| `conversion_action.type` | WEBPAGE, UPLOAD_CLICKS, GOOGLE_PLAY, etc. |
| `conversion_action.origin` | WEBSITE, GOOGLE_HOSTED, CALL_FROM_ADS, YOUTUBE_HOSTED, APP, STORE, etc. |
| `conversion_action.category` | PURCHASE, CONVERTED_LEAD, SUBMIT_LEAD_FORM, SIGNUP, CONTACT, BOOK_APPOINTMENT, DEFAULT, etc. |
| `conversion_action.primary_for_goal` | true / false |
| `conversion_action.counting_type` | ONE_PER_CLICK / MANY_PER_CLICK |
| `conversion_action.value_settings.default_value` | Static default value (0 = dynamic) |
| `conversion_action.value_settings.default_currency_code` | Currency code (ISO 4217) |
| `metrics.all_conversions` | Total conversions (lifetime, incl. modeled) |
| `metrics.all_conversions_value` | Total conversion value (lifetime) |

Daily query (conversions-daily.gaql) adds `segments.date` for time-series checks.

## Status-Based Action Filtering

Filter actions by `conversion_action.status` before running diagnostics:

| Status | Treatment | Notes |
|---|---|---|
| `ENABLED` | **Audit normally** | Active, user-managed actions |
| `PAUSED` | **Include in completeness (D01-D07) only** | May indicate intentional pause — flag as INFO if it was recently primary |
| `HIDDEN` | **Exclude from all scoring** | Auto-imported ghost actions from linked GA4/UA properties. Not visible in Google Ads UI. Not user-created. Report in a separate "Hidden Actions" INFO section if any have `primary_for_goal = true` or `include_in_conversions_metric = true`. |
| `REMOVED` | **Exclude entirely** | Deleted actions — ignore |

**Why exclude HIDDEN actions:** Google auto-creates HIDDEN conversion actions when GA4 or Universal Analytics properties are linked to Google Ads. These are not added by the advertiser, cannot be managed in the standard UI, and should not affect audit scoring. They often have `primary_for_goal = true` as a Google default, which is misleading.

**The audit scope is: ENABLED actions only for scoring. PAUSED actions for completeness context. HIDDEN and REMOVED are excluded.**

---

## Origin-Based Action Filtering

Identify action source via `conversion_action.origin`:

| Origin | Treatment | Notes |
|---|---|---|
| `WEBSITE` | **Audit normally** | User-created GACT pixel |
| `APP` | **Audit normally** | User-created app conversion |
| `CALL_FROM_ADS` | **Audit normally** | User-configured call tracking |
| `STORE` | **Audit normally** | Store visit tracking |
| `YOUTUBE_HOSTED` | **Audit normally** | YouTube engagement |
| `GOOGLE_HOSTED` | **Skip from scoring** | Google auto-created, cannot be edited. Report separately as INFO. |
| `UNKNOWN` | **Flag for review** | Unexpected origin — WARN, ask user to verify |
| `UNSPECIFIED` | **Flag for review** | Unexpected origin — WARN, ask user to verify |

**Handling rules for `GOOGLE_HOSTED` actions:**
- Completeness checks (D02-D07): Exclude from pass/fail scoring. Report in a separate "Google-Hosted Actions" section.
- D07: If a GOOGLE_HOSTED action is primary AND has significant volume alongside the advertiser's real primary actions, note the potential signal dilution as INFO.
- Tag health checks (D08-D10): Include — volume anomalies on any active action are still worth flagging.

**Handling rules for `UNKNOWN` / `UNSPECIFIED` actions:**
- All diagnostics: Flag as WARN — "Action has unexpected origin, verify in Google Ads UI."

## Scoring

| Severity | Points | Meaning |
|----------|--------|---------|
| Critical | 15 | Blocks Smart Bidding or causes fundamentally wrong data |
| High | 10 | Degrades data quality or bidding signal significantly |
| Medium | 5 | Suboptimal config that limits features or clarity |

**SKIP handling:** Diagnostics marked SKIP (Chrome DevTools not run, or field unavailable) are excluded from the denominator. Score = earned / possible (excluding SKIPs).

| Score % | Health Rating |
|---------|--------------|
| 90-100% | Excellent — tracking is production-grade |
| 70-89% | Good — minor issues, no urgent action |
| 50-69% | Needs attention — multiple issues degrading data |
| < 50% | Critical — tracking is unreliable for Smart Bidding |
