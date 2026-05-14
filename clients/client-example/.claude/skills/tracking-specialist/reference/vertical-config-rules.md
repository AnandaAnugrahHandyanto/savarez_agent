# Vertical Configuration Rules

Agent-readable lookup tables for Phase 1 diagnostics. Cross-reference the account's vertical against these tables to determine correct configuration.

---

## 1. Expected Conversion Actions by Vertical

### Ecommerce

| Role | Event | Typical Source | Notes |
|------|-------|----------------|-------|
| Macro | Purchase / booking confirmation | GACT pixel | Always required |
| Micro | Add to cart | GACT pixel | Secondary — funnel signal |
| Micro | Begin checkout | GACT pixel | Secondary — funnel signal |
| Micro | Add shipping info | GACT pixel | Secondary — funnel signal |
| Micro | Add payment info | GACT pixel | Secondary — funnel signal |
| Micro | Product page view | GACT pixel | Secondary — funnel signal |
| Enhancement | Conversion Adjustments (returns) | Upload / API | Restates purchase value for refunds |

### Lead Gen

| Role | Event | Typical Source | Notes |
|------|-------|----------------|-------|
| Macro | Form submission | GACT pixel | Switch to secondary once OCT is stable (30+ days) |
| Macro | Phone call | GACT / call tracking | One per click |
| Macro | Appointment booking | GACT pixel | One per click |
| OCT stage | MQL (marketing qualified lead) | CRM import | Secondary — reporting only |
| OCT stage | SQL (sales qualified lead) | CRM import | Secondary — reporting only |
| OCT stage | Proposal sent | CRM import | Secondary — reporting only |
| OCT stage | Closed Won | CRM import | Primary once stable — real business outcome |
| Micro | Lead magnet download | GACT pixel | Secondary |
| Micro | Calculator / tool usage | GACT pixel | Secondary |
| Micro | High-value page view | GACT pixel | Secondary |

### SaaS

| Role | Event | Typical Source | Notes |
|------|-------|----------------|-------|
| Macro | Signup / registration | GACT pixel | Switch to secondary once OCT is stable (30+ days) |
| OCT stage | Trial start | CRM import | Secondary — reporting only |
| OCT stage | Feature activation | CRM import | Secondary — reporting only |
| OCT stage | Trial-to-paid (payment success) | CRM import | Primary once stable — real business outcome |
| Macro | Subscription purchase / renewal | CRM import or GACT | Every count if revenue-bearing |
| Macro | Upgrade (plan change) | CRM import | Via Conversion Adjustments |
| Micro | Onboarding step completion | GACT pixel | Secondary |
| Micro | Documentation visit | GACT pixel | Secondary |

---

## 2. Goal Category Rules

Map each event type to its expected `conversion_action.category` value.

| Event Type | Expected Category |
|---|---|
| Purchase / transaction | PURCHASE |
| Booking confirmation | PURCHASE |
| Form submission (lead) | SUBMIT_LEAD_FORM |
| Phone call | PHONE_CALL_LEAD |
| Appointment booking | BOOK_APPOINTMENT |
| Signup / registration | SIGNUP |
| Trial start | SIGNUP |
| Trial-to-paid | PURCHASE |
| Subscription purchase | PURCHASE |
| MQL (imported) | QUALIFIED_LEAD |
| SQL (imported) | QUALIFIED_LEAD |
| Closed Won (imported) | CONVERTED_LEAD |
| Add to cart | ADD_TO_CART |
| Begin checkout | BEGIN_CHECKOUT |
| Page view (high-value) | PAGE_VIEW |
| Lead magnet download | DOWNLOAD |

---

## 3. Counting Method Rules

| Event Type | Expected Counting | API Value | Rationale |
|---|---|---|---|
| Purchase / transaction | Every | MANY_PER_CLICK | Each purchase generates revenue |
| Subscription purchase / renewal | Every | MANY_PER_CLICK | Each renewal is revenue |
| Add to cart | Every | MANY_PER_CLICK | Each cart action is a signal |
| Form submission / lead | One | ONE_PER_CLICK | Multiple submissions = one lead |
| Phone call | One | ONE_PER_CLICK | Multiple calls = one prospect |
| Signup / registration | One | ONE_PER_CLICK | User registers once |
| MQL (imported) | One | ONE_PER_CLICK | Lead qualifies once per stage |
| SQL (imported) | One | ONE_PER_CLICK | Lead qualifies once per stage |
| Closed Won (imported) | One | ONE_PER_CLICK | Deal closes once |
| Trial start | One | ONE_PER_CLICK | User starts trial once |
| Trial-to-paid | One | ONE_PER_CLICK | One conversion per trial |
| Appointment booking | One | ONE_PER_CLICK | One booking per lead |

**Vertical shortcut:**
- Ecommerce: default to `MANY_PER_CLICK` (revenue events)
- Lead Gen: default to `ONE_PER_CLICK` (lead events)
- SaaS: default to `ONE_PER_CLICK` (signup/trial events)

---

## 4. Primary / Secondary Classification Rules

### By Vertical

| Vertical | Primary Action(s) | Secondary Actions |
|---|---|---|
| Ecommerce | Purchase | Add to cart, begin checkout, page view, all micro conversions |
| Lead Gen (no OCT) | Form submission, phone call | Lead magnet, page views, micro conversions |
| Lead Gen (with OCT) | Closed Won (OCT import) | Form submission (demoted after 30-day OCT stability), MQL, SQL, micro conversions |
| SaaS (no OCT) | Signup | Onboarding steps, docs visits, micro conversions |
| SaaS (with OCT) | Trial-to-paid (OCT import) | Signup (demoted after 30-day OCT stability), trial start, activation, micro conversions |

### Classification Decision Rules

| Condition | Classification | Rationale |
|---|---|---|
| Macro conversion tied to revenue | Primary | Direct business outcome for Smart Bidding |
| Micro conversion (funnel step) | Secondary | Reporting and funnel analysis only |
| Backup/redundant tracking (e.g., GA4 import alongside GACT) | Secondary | Prevents double-counting in bidding |
| OCT import (qualified lead, closed deal) | Primary | Higher-quality signal than form submission |
| Profit-based conversion (ProfitMetrics, custom profit import) | Primary | Enables value-based bidding on margins |
| OCT intermediate stages (MQL, SQL) | Secondary | Reporting only — do not make multiple OCT stages primary |

### When Micro Becomes Primary (exceptions)

| Condition | Example | Action |
|---|---|---|
| Campaign goal is not revenue-tied | Upper funnel campaign for whitepaper downloads | Set micro as campaign-specific primary |
| Insufficient macro conversion volume (<30/month) | Low-traffic campaign | Exhaust consolidation tactics first, micro second |
| Conversion cycle exceeds 90-day window | B2B enterprise 6-month sales cycle | Optimize for mid-funnel step (SQL instead of closed deal) |
| Experimental testing | Testing higher-volume signal | Run 50/50 experiment before full switch |

### OCT Transition Timeline

| Timeframe | Primary | Secondary |
|---|---|---|
| Day 0 (OCT goes live) | Web form submission + OCT import (both primary) | Micro conversions |
| Day 30+ (OCT stable) | OCT import only | Web form submission (demoted), micro conversions |

---

## 5. Account-Default vs. Campaign-Specific Goal Rules

### Default Rule

All primary conversion actions are account-default goals unless an override condition applies.

### When to Use Campaign-Specific Goals

| Scenario | Account Default | Campaign Override |
|---|---|---|
| Standard bottom-funnel campaigns | Primary macro conversion | None needed |
| Upper funnel (YouTube, Display) optimizing for different objective | Purchase / Lead | Whitepaper download or micro conversion as campaign-specific primary |
| A/B testing conversion actions | Revenue-based primary | Profit-based primary on test campaigns |
| OCT vs. GACT split by funnel position | OCT import (bottom funnel) | GACT form submit (upper funnel with low OCT volume) |
| Low-volume campaign needing micro conversion | Purchase | Add to cart as campaign-specific primary |

### Guard Rails

| Rule | Detail |
|---|---|
| One primary macro per goal category per campaign | Multiple primaries in same category = double-counting for Smart Bidding |
| All micro conversions default to secondary | Only override with campaign-specific goal when justified |
| Verify after every change | Check: (1) account-default goal categories, (2) primary actions within each category, (3) campaign-level overrides |
| Do not make multiple OCT stages primary | Only the stage closest to revenue should be primary |

---

## 6. Conversion Window Rules by Vertical

| Vertical | Typical Sales Cycle | Recommended Click-Through Window | View-Through | Engaged-View |
|---|---|---|---|---|
| Ecommerce (impulse) | Same day - 3 days | 7-14 days | 1 day | 3 days |
| Ecommerce (considered) | 1-2 weeks | 14-30 days | 1 day | 3 days |
| Lead Gen (B2C) | 1-2 weeks | 14-30 days | 1 day | 3 days |
| Lead Gen (B2B services) | 2-4 weeks | 30-60 days | 1 day | 3 days |
| Lead Gen (B2B enterprise) | 1-3 months | 60-90 days | 1 day | 3 days |
| SaaS (self-serve trial) | 1-2 weeks | 30-60 days (match trial length) | 1 day | 3 days |
| SaaS (enterprise) | 1-3 months | 60-90 days | 1 day | 3 days |

**Calibration rule:** Window = 2x average conversion lag (from Path Metrics).

---

## 7. Value Type Rules by Vertical

| Vertical | Value Type | Source | Notes |
|---|---|---|---|
| Ecommerce | Dynamic (actual revenue) | Transaction value from data layer | Pass real order value |
| Lead Gen (no OCT) | Dynamic (estimated deal value) | Calculated: avg deal value x stage-to-close rate | Proxy until OCT available |
| Lead Gen (with OCT) | Dynamic (actual deal value) | CRM deal value at close | Import real value for Closed Won |
| SaaS (no OCT) | Dynamic (estimated LTV) | Calculated: avg LTV x trial-to-paid rate | Proxy until OCT available |
| SaaS (with OCT) | Dynamic (actual payment / LTV) | Payment processor or CRM | Import actual subscription value |

---

## 8. Attribution Rules (all verticals)

| Setting | Rule | Exceptions |
|---|---|---|
| Attribution model | Data-Driven Attribution (DDA) | None — always DDA |
| GA4 cross-channel | Enable "paid and organic channels" if significant organic traffic | Default (Google paid only) if Google Ads is sole channel |
| Over-attribution | Calibrate targets using formula: (Google ROAS / Backend ROAS) x Target ROAS | Requires backend data comparison |

---

## 9. Foundation Feature Requirements by Vertical

| Feature | Ecommerce | Lead Gen | SaaS | Min Spend |
|---|---|---|---|---|
| GACT pixel | Required | Required | Required | Any |
| Transaction ID | Required | Required | Required | Any |
| Enhanced Conversions | Required | Required | Required | Any |
| Server-Side Tagging (SST) | Recommended | Recommended | Recommended | EUR 5,000+/mo |
| OCT | Not typical | Required | Required | Any |
| Cart Data | Required | N/A | N/A | Any |
| COGS in product feed | Recommended | N/A | N/A | Any |
| Conversion Adjustments | Recommended (returns) | Recommended (deal value updates) | Recommended (upgrades/churn) | Any |
| New Customer Data | When running NCA campaigns | When acquisition vs retention matters | When acquisition campaigns are distinct | Any |

---

## 10. Vanity Metrics — Never Track as Conversions

- Quality visits / engaged sessions
- Time on site thresholds
- Bounce rate improvements
- Generic page views without business value
- Scroll depth events

**Test:** Does this metric directly or indirectly drive revenue? If not, it is vanity.
