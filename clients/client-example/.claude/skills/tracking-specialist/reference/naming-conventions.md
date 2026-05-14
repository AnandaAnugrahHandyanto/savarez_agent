# Naming Conventions

Reference file for Phase 1 D04 (Naming Consistency) check.
Used to evaluate whether conversion action names follow clear, identifiable patterns and flag vague or default names.

---

## GACT (Google Ads Conversion Tag) Actions

### Expected format

From SOP_21 (Set Up Google Ads Conversion Tracking):

```
[Initials] – GACT – [Event Name]
```

### Examples

| Good | Why |
|------|-----|
| `BM – GACT – Purchase` | Identifies owner, source (GACT), and event |
| `BM – GACT – Form Submit` | Clear event type |
| `BM – GACT – Book Appointment` | Specific event |
| `BM – GACT – Phone Call` | Identifies the conversion type |

| Bad | Why |
|-----|-----|
| `Purchase` | No source identifier -- could be GACT, GA4 import, or OCT |
| `Conversion 1` | No information about what it tracks |
| `Website Lead` | Missing source prefix, vague event name |
| `test conversion` | Placeholder left in production |

### Key rules

- Prefix with owner initials so you know who created it
- Include `GACT` to distinguish from GA4 imports and OCT imports
- Event name should match the actual trigger event (Purchase, Form Submit, Phone Call, Signup)

---

## OCT (Offline Conversion Tracking) Import Actions

### Expected format

From SOP_24 (Set Up Offline Conversion Tracking):

```
[Initials] – OCT – [Stage Name]
```

### Examples

| Good | Why |
|------|-----|
| `BM – OCT – MQL` | Identifies source (OCT) and funnel stage |
| `BM – OCT – SQL` | Clear stage distinction |
| `BM – OCT – Closed Won` | Revenue stage, clearly named |
| `BM – OCT – Trial Start` | SaaS funnel stage |
| `BM – OCT – Payment Success` | SaaS conversion to paid |
| `BM – OCT – Proposal` | Intermediate lead gen stage |

| Bad | Why |
|-----|-----|
| `Offline Lead` | No stage distinction, no source prefix |
| `CRM Import` | Describes the method, not the event |
| `Qualified Lead` | Missing OCT prefix -- could be confused with a GACT action |
| `Import Conversion` | Generic, no stage info |

### Key rules

- Include `OCT` to distinguish from web-based GACT tracking
- Stage name must reflect the actual CRM/funnel stage
- The conversion name in Google Ads must match EXACTLY what is used in the upload template (column: `Conversion Name`) -- mismatches cause import failures
- Use consistent stage terminology across Google Ads and CRM

---

## GA4 Import Actions

### Common naming patterns

GA4 imported conversion actions typically appear with their GA4 event name. These are created when GA4 goals are imported into Google Ads.

| Pattern | Example | Notes |
|---------|---------|-------|
| GA4 event name as-is | `purchase`, `generate_lead` | Google Ads imports the event name directly |
| Prefixed by GA4 property | `GA4 – Purchase` | Sometimes manually renamed |
| With "(GA4)" suffix | `Purchase (GA4)` | Common way to distinguish from GACT |

### How to distinguish from native GACT

| Indicator | GACT | GA4 Import |
|-----------|------|------------|
| Source column (in Conversions summary) | Website | Google Analytics 4 |
| Naming convention | `[Initials] – GACT – [Event]` | Usually the raw GA4 event name |
| Tag setup available | Yes (shows Conversion ID + Label) | No (managed via GA4 link) |

### Key rules

- GA4 imports should NOT be set as primary for the same event that GACT already tracks (causes double-counting)
- If both exist, flag the duplicate and note which is primary
- GA4 import names are often less structured since they inherit from GA4 event names

---

## General Naming Rules

### What makes a name "vague" or "inconsistent"

A name is vague when it does not tell you:
1. **What source tracks it** (GACT, OCT, GA4)
2. **What event it represents** (purchase, form submit, MQL, closed deal)

A name is inconsistent when:
1. It uses a different format than other actions in the same account
2. It mixes naming styles (some with initials, some without; some with source prefix, some without)
3. It uses abbreviations that are not standard in the account

### Minimum information a name should convey

| Element | Required | Purpose |
|---------|----------|---------|
| Source identifier | Yes | Distinguishes GACT vs OCT vs GA4 import |
| Event type / stage | Yes | Tells you what the conversion actually is |
| Owner initials | Recommended | Identifies who created/manages the action |

### Name quality tiers

| Tier | Format | Example |
|------|--------|---------|
| Best | `[Initials] – [Source] – [Event]` | `BM – GACT – Purchase` |
| Acceptable | `[Source] – [Event]` | `GACT – Purchase` |
| Weak | `[Event] ([Source])` | `Purchase (GACT)` |
| Bad | `[Event]` only | `Purchase` |
| Worst | Default/placeholder | `Conversion 1`, `Untitled` |

---

## Patterns for D04 Check

### Regex patterns to flag bad names

Use these patterns to identify problematic conversion action names:

```javascript
// Default/placeholder names -- always flag
const defaultNamePatterns = [
  /^conversion\s*\d*$/i,           // "Conversion", "Conversion 1", "Conversion 2"
  /^untitled/i,                     // "Untitled", "Untitled conversion"
  /^test/i,                         // "test", "test conversion", "Test 123"
  /^new\s+conversion/i,            // "New conversion", "New Conversion Action"
  /^default/i,                      // "Default conversion"
  /^sample/i,                       // "Sample conversion"
  /^copy\s+of/i,                    // "Copy of Purchase"
  /^unnamed/i,                      // "Unnamed"
];

// Vague names -- flag as warning
const vagueNamePatterns = [
  /^(lead|sale|signup|click|submit|call|download)$/i,  // Single generic word
  /^website\s+(lead|conversion|goal)/i,                 // "Website Lead", "Website Conversion"
  /^online\s+(lead|conversion|sale)/i,                  // "Online Lead"
  /^offline\s+(lead|conversion|import)/i,               // "Offline Lead" without stage
  /^crm\s+import/i,                                      // "CRM Import" (method, not event)
  /^import\s+conversion/i,                               // "Import Conversion"
  /^goal\s+\d+/i,                                        // "Goal 1", "Goal 2" (legacy GA import)
];
```

### Known default/placeholder names to flag

These are names that Google Ads auto-generates or that indicate no intentional naming:

| Name | Flag as |
|------|---------|
| `Conversion` | Default |
| `Conversion 1`, `Conversion 2`, etc. | Default |
| `Untitled` | Default |
| `Untitled conversion action` | Default |
| `New conversion action` | Default |
| `Website conversions` | Default (auto-created) |
| `Calls from ads` | Auto-created (may be intentional -- check if call tracking is set up) |
| `Imported from Google Analytics` | GA4 import placeholder |
| `Page view` | Too vague -- which page? |
| `Copy of [anything]` | Duplicate left unnamed |

### What to output for D04

When checking naming consistency, evaluate and report:

1. **Format consistency**: Do all actions follow the same naming pattern? (e.g., all use `[Initials] – [Source] – [Event]`)
2. **Default names found**: List any names matching default/placeholder patterns
3. **Vague names found**: List any names that lack source or event specificity
4. **Duplicate indicators**: Names containing "Copy of" or numbered suffixes
5. **Source distinguishability**: Can you tell GACT from OCT from GA4 import by name alone?
6. **Recommendation**: If names are inconsistent, suggest a rename scheme following the `[Initials] – [Source] – [Event]` pattern
