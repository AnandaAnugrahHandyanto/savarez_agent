---
name: report-generator
description: Generate professional branded HTML audit reports (and exec summaries) for clients from audit markdown, using my-brand/ agency branding. Use for client reports, PDF export, or branded reports.
argument-hint: "[client-name] [--all | --summary]"
---

# Report Generator

Generates professional, branded HTML reports from client audit data. Reports use the freelancer's agency branding from `my-brand/` and can be exported to PDF via browser print.

## Command Format

```
/report-generator                          # Interactive — select client and reports
/report-generator <client-name>            # Reports for specific client
/report-generator <client-name> --all      # All available audit reports for client
/report-generator <client-name> --summary  # Executive summary combining all audits
```

**Examples:**
- `/report-generator` — List clients, pick one, choose which audits to include
- `/report-generator client-acme` — Show available audits for client-acme, pick reports
- `/report-generator client-acme --all` — Generate individual reports for all available audits
- `/report-generator client-acme --summary` — Generate combined executive summary

## Path Resolution

**Always resolve paths relative to the hub root.**

To find the hub root:
1. Check current directory for `main-config.json` or `clients/` directory
2. If not found, walk up parent directories until found
3. The hub root is where `main-config.json` lives

**Key paths (relative to hub root):**
- Branding: `my-brand/brand.json`, `my-brand/brand.md`
- Logo: `my-brand/logo.png` (or `.svg`, `.jpg`)
- Client audits: `clients/<name>/context/analysis/*-audit.md`
- Client business context: `clients/<name>/context/business.md`
- Report output: `reports/<client-name>/`

## Data Sources

| File | Required | Purpose |
|------|----------|---------|
| `my-brand/brand.json` | Yes | Freelancer branding (colors, fonts, company info) |
| `my-brand/logo.*` | No | Logo for report header (embedded as base64) |
| `clients/<name>/context/analysis/*-audit.md` | Yes | Audit data to render |
| `clients/<name>/context/business.md` | No | Client company name, vertical |
| `reference/report-registry.json` | Yes | Maps audit files to display names and templates |
| `reference/html-base-template.md` | Yes | HTML shell with CSS variable system |
| `reference/section-*.md` | Yes | Per-audit-type HTML section templates |

## Process

### Phase 0: Prerequisites

1. **Find hub root** — walk up from cwd looking for `main-config.json`. Try reading it from the current directory, then parent, then grandparent:
   - Read `main-config.json` from cwd — if found, cwd is the hub root
   - If not found, Read `../main-config.json` — if found, parent is the hub root
   - If not found, Read `../../main-config.json` — if found, grandparent is the hub root
   - Store the directory containing `main-config.json` as `{hub_root}` (absolute path)

2. **Check branding** — use the Read tool to read `{hub_root}/my-brand/brand.json` (absolute path).
   - If the Read tool returns an error (file not found): "Run `/branding-generator` first to set up your agency branding."
   - If exists: parse the JSON content and load all branding values

3. **Check logo** — use the Glob tool to search for `logo.*` in `{hub_root}/my-brand/`:
   ```
   Glob pattern: "logo.*" path: "{hub_root}/my-brand"
   ```
   - If found: read the image file for base64 embedding later
   - If not found: skip logo in report header (use text-only header)

4. **Read registry** — use the Read tool to load `reference/report-registry.json` (relative to this skill's directory)

**Important:** All `my-brand/` paths must use the absolute hub root path. If you're inside a client subfolder like `{hub_root}/clients/client-a/`, you must still read from `{hub_root}/my-brand/brand.json`, not from a relative path.

### Phase 1: Client Selection

**If client name provided in command:** use it directly.

**If currently inside `clients/<name>/`:** auto-detect the client name from the directory path.

**If at hub root or elsewhere:**
1. Scan `clients/` for directories that contain `context/analysis/` with at least one `*-audit.md` file
2. List available clients via AskUserQuestion
3. User selects one

### Phase 2: Report Discovery

1. Scan `clients/<selected>/context/analysis/` for files matching `*-audit.md`
2. For each file, check against `reference/report-registry.json`:
   - Match `sourceFile` to the filename
   - Get `displayName` and `templateFile`
   - Unknown audit files (not in registry) are listed but noted as "no template available"
3. Parse each audit file's header to extract:
   - **Date:** from the `**Date:**` line
   - **Overall Score:** from the `**Overall Score:**` line (format: `{x}% — {grade}`)
4. Present discovery table:

```
Available audit reports for {client-name}:

| # | Report | Date | Score | Grade |
|---|--------|------|-------|-------|
| 1 | Account structure | 2026-03-20 | 74% | Good |
| 2 | Landing page | 2026-03-18 | 68% | Needs attention |
| 3 | Offer quality | 2026-03-15 | 82% | Good |
| 4 | Tracking | 2026-03-12 | 91% | Excellent |
| 5 | Strategy | 2026-03-10 | 65% | Needs attention |
```

5. Ask via AskUserQuestion: "Which reports do you want to generate?"
   - Options: individual reports (list each), "All available", "Executive Summary (combined)"
   - multiSelect: true (user can pick multiple individual reports)

**If `--all` flag:** skip question, generate all individual reports.
**If `--summary` flag:** skip question, generate executive summary.

### Phase 3: Parse Audit Data

For each selected audit report, read the full `*-audit.md` file and extract structured data:

#### Common Fields (all audits)
- Date
- Account ID (if present)
- Vertical (if present)
- Mode (if present)
- Overall Score (percentage)
- Overall Grade

#### Module Scores Table
Parse the `## Module Scores` section. Extract for each row:
- Module name
- Score (percentage)
- Grade
- Checks passed/failed/skipped (if present)

#### Critical Issues
Parse the `## Critical Issues` or `## Priority Fixes` section. Extract for each row:
- Priority number
- Diagnostic ID
- Issue description
- Impact
- Routing/Fix command (if present)

#### Per-Module Results
For each `## {Module Name} Results` section, extract the diagnostic table:
- Diagnostic ID
- Diagnostic name
- Status (PASS/WARN/FAIL/SKIP)
- Points (x/y)
- Details

#### Routing Recommendations
Parse the `## Routing Recommendations` section if present.

#### Special Fields Per Audit Type
- **Strategy:** Viability Verdict (Go / Conditional Go / No-Go)
- **Tracking:** Tier column (API/DevTools/Manual), Manual Checks Required section
- **LP:** Conditional Ecommerce module, Fix Command column
- **Offer:** Next Steps with `/offer-maker` commands
- **Keyword:** Hypothesis-driven structure — parse Diagnosis (top hypothesis, confidence, secondary hypotheses), Evidence Ladder (grouped by cascade layer with hypothesis tags), Actions segmented by cascade state (5 sections: Investigate/Structural/Recover/Act/Do-NOT-Pause), KW-D07 sub-sections (core-term do-not-pause, non-core UNPROFITABLE, PAUSE_CANDIDATE, OVER_TARGET, business context box), and Data Sufficiency Notes. See `section-keyword-audit.md` for full extraction guide.

Also read `clients/<selected>/context/business.md` (if exists) for:
- Client company name
- Vertical
- Primary KPI

### Phase 4: Generate HTML

**Text casing rule:** Use sentence case for all headings, labels, and display text in the generated HTML. Only capitalize the first word and proper nouns/acronyms (e.g. "Module scores", "Critical issues", "URL health", "Goals & KPIs"). Do not use title case.

1. **Read base template** — `reference/html-base-template.md` for the HTML shell
2. **Populate CSS variables** from `my-brand/brand.json`:
   - `--color-primary` ← `colors.primary`
   - `--color-secondary` ← `colors.secondary`
   - `--color-accent` ← `colors.accent`
   - `--color-bg` ← `colors.background`
   - `--color-bg-alt` ← `colors.backgroundAlt`
   - `--color-text` ← `colors.text`
   - `--color-text-light` ← `colors.textLight`
   - `--font-heading` ← `fonts.heading`
   - `--font-body` ← `fonts.body`
3. **Logo** — if logo exists, reference it with an absolute `file://` path in the `<img>` tag:
   ```html
   <img src="file://{hub_root}/my-brand/logo.png" class="report-logo" alt="{company_name} logo">
   ```
   Use the actual absolute path from Phase 0 (e.g., `file:///Users/john/ppcos-hub/my-brand/logo.png` on Mac/Linux, `file:///C:/Users/john/ppcos-hub/my-brand/logo.png` on Windows).
   The browser loads the logo when the user opens the HTML, and Print > Save as PDF captures it in the rendered output.
   Do NOT base64-encode the logo — it bloats the HTML file.
4. **Populate header** — company name, tagline, logo from brand.json
5. **Populate report metadata** — client name (from business.md or directory name), report date, report type
6. **For individual reports:**
   - Read the matching `reference/section-{type}.md` template
   - Populate with parsed audit data from Phase 3
   - Generate one HTML file per selected audit
7. **For executive summary:**
   - Read `reference/section-executive-summary.md`
   - Include overview scores for ALL available audits
   - Highlight critical issues across all audits
   - Generate one combined HTML file
8. **Populate footer** — company name, email, website from brand.json

### Phase 5: Output Location

Ask the user where to save the report(s) via AskUserQuestion.

**If triggered from a client subfolder** (`clients/<name>/`):
- Ask: "Where should the report be saved?"
  - Option 1: "Client folder" — save to `clients/<name>/created/reports/` (Recommended)
  - Option 2: "Hub root" — save to `{hub_root}/reports/<client-name>/`

**If triggered from the hub root:**
- Ask: "Where should the report be saved?"
  - Option 1: "Client folder" — save to `clients/<name>/created/reports/`
  - Option 2: "Hub root" — save to `{hub_root}/reports/<client-name>/` (Recommended)

**File naming (same for both locations):**

Individual reports: `{YYYYMMDD}_{client}_{report-type}.html`
- Example: `20260326_client-acme_account-audit.html`

Executive summary: `{YYYYMMDD}_{client}_executive-summary.html`

Create the target directory if it doesn't exist.

Present summary:

```
Reports generated:

| Report | File |
|--------|------|
| Account Audit | reports/client-acme/20260326_client-acme_account-audit.html |
| Executive Summary | reports/client-acme/20260326_client-acme_executive-summary.html |

Open in your browser and use Print → Save as PDF for a polished PDF export.
The logo and all branding are embedded — no external dependencies needed.
```

## Error Handling

| Error | Message |
|-------|---------|
| Hub root not found | "Could not find hub root (no main-config.json). Run this from your PPCOS hub directory." |
| No branding configured | "No branding found. Run `/branding-generator` to set up your agency branding first." |
| Client not found | "Client '{name}' not found in clients/. Check the name and try again." |
| No audit reports found | "No audit reports found for {client}. Run audit skills first (e.g., `/account-audit`)." |
| Audit file not in registry | "Report template not available for {filename}. Skipping." |
| Logo file unreadable | (silent — generate report without logo) |

## Integration Points

### Reads From
- `my-brand/brand.json` — Freelancer branding
- `my-brand/logo.*` — Logo for header
- `clients/<name>/context/analysis/*-audit.md` — Audit reports
- `clients/<name>/context/business.md` — Client info

### Produces
- `reports/<client-name>/{YYYYMMDD}_{client}_{type}.html` — Branded HTML reports

### Upstream Skills (produce data this skill reads)
- `/account-audit` → `context/analysis/account-audit.md`
- `/lp-auditor` → `context/analysis/lp-audit.md`
- `/offer-auditor` → `context/analysis/offer-audit.md`
- `/tracking-audit` → `context/analysis/tracking-audit.md`
- `/strategy-audit` → `context/analysis/strategy-audit.md`
- `/geo-schedule-audit` → `context/analysis/geo-schedule-audit.md`
- `/placement-audit` → `context/analysis/placement-audit.md`
- `/keyword-auditor` → `context/analysis/keyword-audit.md`
- `/competitive-analyst` → `context/analysis/competitive-audit.md`
- `/search-term-auditor` → `context/analysis/search-term-audit.md`
- `/quality-score-auditor` → `context/analysis/quality-score-audit.md`
- `/bidding-auditor` → `context/analysis/bidding-audit.md`
- `/budget-auditor` → `context/analysis/budget-audit.md`

## Adding New Report Types

To add support for a new audit type:
1. Create a `reference/section-{new-type}.md` HTML section template
2. Add an entry to `reference/report-registry.json`
3. No changes to this SKILL.md are needed
