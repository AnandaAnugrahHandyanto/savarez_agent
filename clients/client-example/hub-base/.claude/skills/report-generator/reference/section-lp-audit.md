# Section Template: Landing Page Audit

HTML section template for rendering lp-audit.md data. Insert into `{report_body_sections}` in the base template.

## Source File

`clients/<name>/context/analysis/lp-audit.md`

## Modules

6 modules: Structural (LP-D01–D12), Message Match (LP-D13–D16), Technical (LP-D17–D24), Performance (LP-D25–D31), URL Health (LP-D32–D37), Ecommerce (LP-D38–D40)

## Unique Features

- **Conditional Ecommerce module**: Only included for ecommerce verticals
- **Fix Command column**: Routes to specific `/lp-optimize` action modes
- **GA4 SKIP tracking**: Some performance diagnostics SKIP when GA4 data unavailable
- **URL(s) in header**: May audit multiple URLs

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
    <!-- Show audited URL(s) if available -->
    <div style="font-size: 0.85rem; color: var(--color-text-light); margin-top: 12px;">
        URL(s): {audited_urls}
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
    <!-- Repeat for: Structural, Message Match, Technical, Performance, URL Health -->
    <!-- Include Ecommerce only if present in the audit -->
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
            {passed} passed · {warned} warned · {failed} failed · {skipped} skipped
        </div>
    </div>
    <!-- /Repeat -->
</div>

<!-- Priority Fixes -->
<h2>Priority fixes</h2>
<!-- If no priority fixes: -->
<p style="color: var(--color-success); font-weight: 600;">No critical fixes needed.</p>
<!-- Repeat for each FAIL & WARN, sorted by severity then points: -->
<div class="issue-card {severity_class}">
    <div style="display: flex; justify-content: space-between; align-items: start;">
        <div>
            <div class="issue-id">{diagnostic_id}</div>
            <div class="issue-title">{issue_description}</div>
            <div class="issue-impact">{impact}</div>
        </div>
    </div>
</div>
<!-- /Repeat -->

<!-- Structural Results (LP-D01–D12) -->
<div class="module-section">
    <div class="module-header">
        <h3>Structural</h3>
        <span class="score-badge {module_grade_class}">{module_score}% — {module_grade}</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 70px;">ID</th>
                <th>Diagnostic</th>
                <th style="width: 70px;">Status</th>
                <th style="width: 70px;">Points</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for LP-D01 through LP-D12 -->
            <tr>
                <td><strong>{id}</strong></td>
                <td>{diagnostic_name}</td>
                <td><span class="status-pill {status_class}">{status}</span></td>
                <td>{points}</td>
                <td>{details}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Message Match Results (LP-D13–D16) -->
<div class="module-section">
    <div class="module-header">
        <h3>Message match</h3>
        <span class="score-badge {module_grade_class}">{module_score}% — {module_grade}</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 70px;">ID</th>
                <th>Diagnostic</th>
                <th style="width: 70px;">Status</th>
                <th style="width: 70px;">Points</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for LP-D13 through LP-D16 -->
            <tr>
                <td><strong>{id}</strong></td>
                <td>{diagnostic_name}</td>
                <td><span class="status-pill {status_class}">{status}</span></td>
                <td>{points}</td>
                <td>{details}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Technical Results (LP-D17–D24) -->
<div class="module-section">
    <div class="module-header">
        <h3>Technical</h3>
        <span class="score-badge {module_grade_class}">{module_score}% — {module_grade}</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 70px;">ID</th>
                <th>Diagnostic</th>
                <th style="width: 70px;">Status</th>
                <th style="width: 70px;">Points</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for LP-D17 through LP-D24 -->
            <tr>
                <td><strong>{id}</strong></td>
                <td>{diagnostic_name}</td>
                <td><span class="status-pill {status_class}">{status}</span></td>
                <td>{points}</td>
                <td>{details}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Performance Results (LP-D25–D31) -->
<div class="module-section">
    <div class="module-header">
        <h3>Performance</h3>
        <span class="score-badge {module_grade_class}">{module_score}% — {module_grade}</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 70px;">ID</th>
                <th>Diagnostic</th>
                <th style="width: 70px;">Status</th>
                <th style="width: 70px;">Points</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for LP-D25 through LP-D31 -->
            <!-- Note: some may be SKIP due to missing GA4 data -->
            <tr>
                <td><strong>{id}</strong></td>
                <td>{diagnostic_name}</td>
                <td><span class="status-pill {status_class}">{status}</span></td>
                <td>{points}</td>
                <td>{details}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- URL Health Results (LP-D32–D37) -->
<div class="module-section">
    <div class="module-header">
        <h3>URL health</h3>
        <span class="score-badge {module_grade_class}">{module_score}% — {module_grade}</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 70px;">ID</th>
                <th>Diagnostic</th>
                <th style="width: 70px;">Status</th>
                <th style="width: 70px;">Points</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for LP-D32 through LP-D37 -->
            <tr>
                <td><strong>{id}</strong></td>
                <td>{diagnostic_name}</td>
                <td><span class="status-pill {status_class}">{status}</span></td>
                <td>{points}</td>
                <td>{details}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Ecommerce Results (LP-D38–D40) — CONDITIONAL -->
<!-- Only include this section if Ecommerce module is present in the audit -->
<div class="module-section">
    <div class="module-header">
        <h3>Ecommerce</h3>
        <span class="score-badge {module_grade_class}">{module_score}% — {module_grade}</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 70px;">ID</th>
                <th>Diagnostic</th>
                <th style="width: 70px;">Status</th>
                <th style="width: 70px;">Points</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for LP-D38 through LP-D40 -->
            <tr>
                <td><strong>{id}</strong></td>
                <td>{diagnostic_name}</td>
                <td><span class="status-pill {status_class}">{status}</span></td>
                <td>{points}</td>
                <td>{details}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Routing Recommendations -->
<h2>Recommendations</h2>
<div class="recommendations">
    <table>
        <thead>
            <tr>
                <th>Action</th>
                <th>Why</th>
                <th style="width: 80px;">Priority</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each routing recommendation -->
            <tr>
                <td><strong>{action}</strong></td>
                <td>{reason}</td>
                <td><span class="status-pill {priority_class}">{priority}</span></td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>
```

## Data Extraction Guide

Parse the lp-audit.md file for:

1. **Header block**: `**Date:**`, `**URL(s):**`, `**Vertical:**`, `**Mode:**`, `**Overall Score:**`
2. **Executive read**: Section under `## Executive read` — prose paragraphs (≤300 words, no bullets). Split by paragraph break, render each as a separate `<p>`. Quoted peer-report findings stay inline with the surrounding prose. Covers six slots in order: score meaning, this-week priorities, what is NOT a problem, fresh peer findings, how to read the rest, score trend
3. **Module Scores table**: Module | Score | Grade | Passed | Warned | Failed | Skipped
4. **Priority Fixes**: Table under `## Priority Fixes` — Priority | ID | Issue | Impact | Fix Command (`/lp-optimize` subcommands)
5. **6 Module Result sections**: Each has diagnostic tables with ID | Diagnostic | Status | Points | Details
6. **Ecommerce module**: Only present for ecommerce verticals — check if section exists before including
7. **Routing Recommendations**: Table under `## Routing Recommendations`

## Conditional Ecommerce Module

Check the audit file for `## Ecommerce Results` section. If not present, omit the entire Ecommerce module section from the HTML output. This is normal for non-ecommerce verticals.
