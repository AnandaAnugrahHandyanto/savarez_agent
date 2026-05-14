# Section Template: Account Structure Audit

HTML section template for rendering account-audit.md data. Insert into `{report_body_sections}` in the base template.

## Source File

`clients/<name>/context/analysis/account-audit.md`

## Modules

5 modules: Structure (AUD-D01–D08), Naming (AUD-D09–D10), Settings (AUD-D11–D19), Ad Groups (AUD-D20–D23), Defaults (AUD-D24)

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
    <!-- Repeat for each module: Structure, Naming, Settings, Ad Groups, Defaults -->
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
            {checks_passed} passed · {checks_failed} failed · {checks_skipped} skipped
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
</div>
<!-- /Repeat -->

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

<!-- Routing Recommendations -->
<h2>Recommendations</h2>
<div class="recommendations">
    <table>
        <thead>
            <tr>
                <th>Specialist</th>
                <th>Why</th>
                <th style="width: 80px;">Priority</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each recommendation -->
            <tr>
                <td><strong>{skill_name}</strong></td>
                <td>{reason}</td>
                <td><span class="status-pill {priority_class}">{priority}</span></td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>
```

## Data Extraction Guide

Parse the account-audit.md file for:

1. **Header block**: Lines starting with `**Date:**`, `**Account:**`, `**Overall Score:**`
2. **Executive read**: Section under `## Executive read` — prose paragraphs (≤300 words, no bullets). Split by paragraph break, render each as a separate `<p>`. Quoted peer-report findings stay inline. Covers six slots in order: score meaning, this-week priorities, what is NOT a problem, fresh peer findings, how to read the rest, score trend
3. **Module Scores table**: Table under `## Module Scores` — each row has Module | Score | Grade | Checks Passed | Checks Failed | Checks Skipped
4. **Critical Issues**: Table under `## Critical Issues` — each row has Priority | ID | Issue | Impact | Routing
5. **Module Results**: Sections named `## Structure Results`, `## Naming Results`, `## Settings Results`, `## Ad Group Results`, `## Defaults Results` — each has a diagnostic table with ID | Diagnostic | Status | Points | Details
6. **Routing Recommendations**: Table under `## Routing Recommendations`

## Status-to-Class Mapping

| Status | CSS Class |
|--------|-----------|
| PASS | `pass` |
| WARN | `warn` |
| FAIL | `fail` |
| SKIP | `skip` |

## Grade Color Mapping

Map score percentages to color variables:
- 90-100%: `--color-success` (green)
- 70-89%: `--color-info` (blue)
- 50-69%: `--color-warning` (amber)
- <50%: `--color-danger` (red)
