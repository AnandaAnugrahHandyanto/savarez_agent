# Section Template: Offer Quality Audit

HTML section template for rendering offer-audit.md data. Insert into `{report_body_sections}` in the base template.

## Source File

`clients/<name>/context/analysis/offer-audit.md`

## Modules

4 modules: Value (D01–D06), Urgency (D07–D08), Trust (D09–D13), Positioning (D14–D16)

## Unique Features

- **Next Steps section**: Routes to specific `/offer-maker` commands
- **D15 is checklist-based**: Shows X/15 items passing

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
    <!-- Repeat for each paragraph (≤300 words total, prose only — no bullets). Quoted peer-report findings stay inline — `/lp-auditor` overlaps tightly with offer findings (the offer lives on the LP) -->
    <p style="font-size: 1rem; line-height: 1.7; margin: 0 0 12px;">{executive_paragraph}</p>
    <!-- /Repeat -->
</div>

<!-- Module Scores Grid -->
<h2>Module scores</h2>
<div class="scores-grid">
    <!-- Repeat for: Value, Urgency, Trust, Positioning -->
    <div class="score-card">
        <div class="module-name">{module_name}</div>
        <div class="module-score" style="color: var(--color-{grade_color});">{module_score}%</div>
        <div class="module-grade">{module_grade}</div>
        <div style="margin-top: 8px;">
            <div class="progress-bar">
                <div class="fill {module_grade_class}" style="width: {module_score}%"></div>
            </div>
        </div>
    </div>
    <!-- /Repeat -->
</div>

<!-- Critical Issues -->
<h2>Critical issues</h2>
<!-- If no critical issues: -->
<p style="color: var(--color-success); font-weight: 600;">No critical issues found.</p>
<!-- Repeat for each FAIL item: -->
<div class="issue-card">
    <div class="issue-id">{diagnostic_id}</div>
    <div class="issue-title">{what}</div>
    <div class="issue-impact">{impact}</div>
    <div style="font-size: 0.85rem; color: var(--color-text-light); margin-top: 4px;">
        <strong>Fix:</strong> {fix_description}
    </div>
</div>
<!-- /Repeat -->

<!-- All Diagnostics Table (single table for all 4 modules) -->
<h2>Diagnostic results</h2>

<!-- Value (D01-D06) -->
<div class="module-section">
    <div class="module-header">
        <h3>Value propositions</h3>
        <span class="score-badge {module_grade_class}">{module_score}% — {module_grade}</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 60px;">ID</th>
                <th>Diagnostic</th>
                <th style="width: 70px;">Status</th>
                <th style="width: 70px;">Points</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for D01-D06 -->
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

<!-- Urgency (D07-D08) -->
<div class="module-section">
    <div class="module-header">
        <h3>Urgency elements</h3>
        <span class="score-badge {module_grade_class}">{module_score}% — {module_grade}</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 60px;">ID</th>
                <th>Diagnostic</th>
                <th style="width: 70px;">Status</th>
                <th style="width: 70px;">Points</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for D07-D08 -->
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

<!-- Trust (D09-D13) -->
<div class="module-section">
    <div class="module-header">
        <h3>Trust & credibility</h3>
        <span class="score-badge {module_grade_class}">{module_score}% — {module_grade}</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 60px;">ID</th>
                <th>Diagnostic</th>
                <th style="width: 70px;">Status</th>
                <th style="width: 70px;">Points</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for D09-D13 -->
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

<!-- Positioning (D14-D16) -->
<div class="module-section">
    <div class="module-header">
        <h3>Positioning</h3>
        <span class="score-badge {module_grade_class}">{module_score}% — {module_grade}</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 60px;">ID</th>
                <th>Diagnostic</th>
                <th style="width: 70px;">Status</th>
                <th style="width: 70px;">Points</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for D14-D16 -->
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

<!-- Recommendations & Next Steps -->
<h2>Recommendations</h2>
<div class="recommendations">
    <ol>
        <!-- Repeat for each recommendation -->
        <li>{recommendation}</li>
        <!-- /Repeat -->
    </ol>
</div>
```

## Data Extraction Guide

Parse the offer-audit.md file for:

1. **Header block**: `**Date:**`, `**Account:**`, `**Vertical:**`, `**Module:**`, `**Overall Score:**`
2. **Executive read**: Section under `## Executive read` — prose paragraphs (≤300 words, no bullets). Split by paragraph break, render each as a separate `<p>`. Quoted peer-report findings stay inline — `/lp-auditor` overlaps tightly because the offer lives on the LP. Covers six slots in order: score meaning, this-week priorities, what is NOT a problem, fresh peer findings, how to read the rest, score trend
3. **Overall Score table**: Module | Score | Grade (for Value, Urgency, Trust, Positioning)
4. **Offer Quality Results table**: Single table with all D01-D16 diagnostics
5. **Critical Issues**: FAIL items with What | Impact | Fix
6. **Recommendations**: Numbered list
7. **Next Steps**: Specific `/offer-maker` command suggestions

Note: D15 is checklist-based (X/15 items pass). Display the points as-is — the template handles it like any other diagnostic.
