# Section Template: Placement Audit

HTML section template for rendering placement-audit.md data. Insert into `{report_body_sections}` in the base template.

## Source File

`clients/<name>/context/analysis/placement-audit.md`

## Modules

3 modules: Performance & App Audit (PL-D01–D04), Brand Safety & Coverage (PL-D05–D07), Hygiene & Monitoring (PL-D08–D10)

## HTML Section

```html
<!-- Overall Score -->
<div class="overall-score">
    <div class="score-value">{overall_score}%</div>
    <div class="score-grade">{overall_grade}</div>
    <div style="max-width: 300px; margin: 12px auto 0;">
        <div class="progress-bar">
            <div class="fill {grade_class}" style="width: {overall_score}%"></div>
        </div>
    </div>
    <div style="font-size: 0.85rem; color: var(--color-text-light); margin-top: 8px;">
        Mode: {audit_mode}
    </div>
</div>

<!-- Executive Read -->
<h2>Executive read</h2>
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 24px; margin: 16px 0;">
    <!-- Repeat for each paragraph (≤300 words total, prose only — no bullets). Quoted peer-report findings stay inline -->
    <p style="font-size: 1rem; line-height: 1.7; margin: 0 0 12px;">{executive_paragraph}</p>
    <!-- /Repeat -->
</div>

<!-- Module Scores Grid -->
<h2>Module scores</h2>
<div class="scores-grid">
    <!-- Repeat for each module: Performance & App Audit, Brand Safety & Coverage, Hygiene & Monitoring -->
    <div class="score-card">
        <div class="module-name">{module_name}</div>
        <div class="module-score" style="color: var(--color-{grade_color});">{module_score}%</div>
        <div class="module-grade">{module_grade}</div>
        <div style="margin-top: 8px;">
            <div class="progress-bar">
                <div class="fill {module_grade_class}" style="width: {module_score}%"></div>
            </div>
        </div>
        <div style="font-size: 0.8rem; color: var(--color-text-light); margin-top: 8px;">
            {checks_passed} passed · {checks_warned} warned · {checks_failed} failed · {checks_skipped} skipped
        </div>
    </div>
    <!-- /Repeat -->
</div>

<!-- Critical Issues -->
<h2>Critical issues</h2>
<!-- If no critical issues: -->
<p style="color: var(--color-success); font-weight: 600;">No critical issues found.</p>
<!-- If critical issues exist, repeat for each: -->
<div class="issue-card">
    <div class="issue-id">{diagnostic_id}</div>
    <div class="issue-title">{issue_description}</div>
    <div class="issue-impact">{impact}</div>
    <div class="issue-routing" style="font-size: 0.85rem; color: var(--color-text-light); margin-top: 4px;">
        Fix: <code>{routing_command}</code>
    </div>
</div>
<!-- /Repeat -->

<!-- Placement Type Breakdown -->
<!-- Render only if the audit produced a `## Placement Type Breakdown` section (sourced from summary JSON `placement_type_breakdown`) -->
<h2>Placement type breakdown</h2>
<table>
    <thead>
        <tr>
            <th>Type</th>
            <th style="width: 90px;">Placements</th>
            <th style="width: 90px;">Spend</th>
            <th style="width: 90px;">Conversions</th>
            <th style="width: 80px;">CPA</th>
            <th style="width: 100px;">Conv. value</th>
            <th style="width: 70px;">ROAS</th>
            <th style="width: 70px;">CTR</th>
        </tr>
    </thead>
    <tbody>
        <!-- Repeat for each placement type -->
        <tr>
            <td>{placement_type}</td>
            <td>{placement_count}</td>
            <td>{spend}</td>
            <td>{conversions}</td>
            <td>{cpa}</td>
            <td>{conversion_value}</td>
            <td>{roas}</td>
            <td>{ctr}%</td>
        </tr>
        <!-- /Repeat -->
    </tbody>
</table>

<!-- Top Wasters (0 Conversions) -->
<!-- Render only if the audit produced a `## Top Wasters (0 Conversions)` section (sourced from summary JSON `top_wasters`). Up to 20 placements ranked by spend, all with 0 click-through conversions -->
<h2>Top wasters (0 conversions)</h2>
<table>
    <thead>
        <tr>
            <th style="width: 40px;">#</th>
            <th>Placement</th>
            <th style="width: 100px;">Type</th>
            <th>Campaign</th>
            <th style="width: 90px;">Spend</th>
            <th style="width: 80px;">Clicks</th>
            <th style="width: 60px;">VTC</th>
        </tr>
    </thead>
    <tbody>
        <!-- Repeat for each waster (sorted by spend desc, max 20) -->
        <tr>
            <td>{rank}</td>
            <td>{placement}</td>
            <td>{placement_type}</td>
            <td>{campaign_name}</td>
            <td>{spend}</td>
            <td>{clicks}</td>
            <td>{view_through_conversions}</td>
        </tr>
        <!-- /Repeat -->
    </tbody>
</table>

<!-- Module Detail Sections -->
<!-- Repeat for each module -->
<div class="module-section">
    <div class="module-header">
        <h3>{module_name}</h3>
        <span class="score-badge {module_grade_class}">{module_score}% — {module_grade}</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 80px;">ID</th>
                <th>Diagnostic</th>
                <th style="width: 80px;">Status</th>
                <th style="width: 80px;">Points</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each diagnostic in the module -->
            <tr>
                <td><strong>{diagnostic_id}</strong></td>
                <td>{diagnostic_name}</td>
                <td><span class="status-pill {status_class}">{status}</span></td>
                <td>{points_earned}/{points_possible}</td>
                <td>{details}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>
<!-- /Repeat for each module -->

<!-- Recommended Next Steps -->
<h2>Recommended next steps</h2>
<div class="recommendations">
    <table>
        <thead>
            <tr>
                <th>Action</th>
                <th>Command</th>
                <th style="width: 100px;">Priority</th>
                <th>Addresses</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each recommendation -->
            <tr>
                <td>{action_description}</td>
                <td><code>{optimizer_command}</code></td>
                <td><span class="status-pill {priority_class}">{priority}</span></td>
                <td>{diagnostic_ids}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Data Freshness -->
<h2>Data freshness</h2>
<div class="data-freshness">
    <table>
        <thead>
            <tr>
                <th>Data source</th>
                <th style="width: 80px;">Rows</th>
                <th style="width: 120px;">Last updated</th>
                <th style="width: 80px;">Status</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each data source -->
            <tr>
                <td>{source_name}</td>
                <td>{row_count}</td>
                <td>{last_updated}</td>
                <td><span class="status-pill {freshness_class}">{freshness_status}</span></td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>
```

## Data Extraction Guide

Parse the placement-audit.md file for:

1. **Header block**: Lines starting with `**Date:**`, `**Account:**`, `**Vertical:**`, `**Mode:**`, `**Overall Score:**`
2. **Executive read**: Section under `## Executive read` — prose paragraphs (≤300 words, no bullets). Split by paragraph break, render each as a separate `<p>`. Quoted peer-report findings stay inline. Covers six slots in order: score meaning, this-week priorities, what is NOT a problem, fresh peer findings, how to read the rest, score trend
3. **Module Scores table**: Table under `## Module Scores` — each row has Module | Score | Grade | Passed | Warned | Failed | Skipped
4. **Critical Issues**: Table under `## Critical Issues` — each row has Priority | ID | Issue | Impact | Routing (`/placement-optimize` subcommands)
5. **Placement Type Breakdown**: Table under `## Placement Type Breakdown` — Type | Placements | Spend | Conversions | CPA | Conv. Value | ROAS | CTR
6. **Top Wasters (0 Conversions)**: Table under `## Top Wasters (0 Conversions)` — up to 20 placements ranked by spend, all with 0 click-through conversions: # | Placement | Type | Campaign | Spend | Clicks | VTC
7. **Module Results**: Sections named `## Performance & App Audit Results`, `## Brand Safety & Coverage Results`, `## Hygiene & Monitoring Results` — each has a diagnostic table with ID | Diagnostic | Status | Points | Details
8. **Recommended Next Steps**: Table under `## Recommended Next Steps` — each row has Action | Command (`/placement-optimize` subcommands) | Priority | Addresses
9. **Data Freshness**: Table under `## Data Freshness` — each row has Data Source | Rows | Last Updated | Status

## Special Fields

- **Mode**: The audit supports partial modes (`full`, `performance`, `safety`, `hygiene`). Display the mode below the overall score.
- **Routing column**: Critical issues include a routing command pointing to `/placement-optimize` subcommands. Render as inline code.
- **Next steps table**: Maps directly to optimizer commands (`/placement-optimize apps`, `/placement-optimize performance`, `/placement-optimize safety`, `/placement-optimize lists`).
- **Data freshness table**: Shows source data age and row counts. Use `pass`/`warn` status classes for OK/Stale.
- **Sub-agent output**: The audit uses a `placement-content-reviewer` sub-agent. Its output (`placement-content-flags.csv`) feeds into diagnostics but is not rendered separately in the report.

## Status-to-Class Mapping

| Status | CSS Class |
|--------|-----------|
| PASS | `pass` |
| WARN | `warn` |
| FAIL | `fail` |
| SKIP | `skip` |

## Freshness Status Mapping

| Status | CSS Class |
|--------|-----------|
| OK | `pass` |
| Stale | `warn` |

## Grade Color Mapping

Map score percentages to color variables:
- 90-100%: `--color-success` (green)
- 70-89%: `--color-info` (blue)
- 50-69%: `--color-warning` (amber)
- <50%: `--color-danger` (red)
