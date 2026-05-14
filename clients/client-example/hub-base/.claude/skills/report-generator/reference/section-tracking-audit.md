# Section Template: Tracking Audit

HTML section template for rendering tracking-audit.md data. Insert into `{report_body_sections}` in the base template.

## Source File

`clients/<name>/context/analysis/tracking-audit.md`

## Modules

2 modules: Completeness (D01–D07), Tag Health (D08–D17)

## Unique Features

- **Tier column**: Diagnostics are classified as API / DevTools / Manual
- **Manual Checks Required section**: Lists checks that need human verification

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
    <!-- Repeat for each paragraph (≤300 words total, prose only — no bullets). Quoted peer-report findings stay inline — tracking is the Measurement layer / cascade root, so contradictions with downstream skills (bidding, QS, search-term, LP) are surfaced explicitly -->
    <p style="font-size: 1rem; line-height: 1.7; margin: 0 0 12px;">{executive_paragraph}</p>
    <!-- /Repeat -->
</div>

<!-- Module Scores Grid -->
<h2>Module scores</h2>
<div class="scores-grid">
    <!-- Repeat for: Completeness, Tag Health -->
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
<!-- Repeat for each critical issue: -->
<div class="issue-card">
    <div class="issue-id">{diagnostic_id}</div>
    <div class="issue-title">{finding}</div>
    <div class="issue-impact">{impact}</div>
    <div style="font-size: 0.85rem; color: var(--color-text-light); margin-top: 4px;">
        <strong>Fix:</strong> {fix_description}
    </div>
</div>
<!-- /Repeat -->

<!-- Completeness Results -->
<div class="module-section">
    <div class="module-header">
        <h3>Completeness</h3>
        <span class="score-badge {module_grade_class}">{module_score}% — {module_grade}</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 60px;">ID</th>
                <th>Diagnostic</th>
                <th style="width: 70px;">Tier</th>
                <th style="width: 70px;">Status</th>
                <th style="width: 70px;">Points</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for D01-D07 -->
            <tr>
                <td><strong>{id}</strong></td>
                <td>{diagnostic_name}</td>
                <td><span style="font-size: 0.8rem; color: var(--color-text-light);">{tier}</span></td>
                <td><span class="status-pill {status_class}">{status}</span></td>
                <td>{points}</td>
                <td>{details}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Tag Health Results -->
<div class="module-section">
    <div class="module-header">
        <h3>Tag health</h3>
        <span class="score-badge {module_grade_class}">{module_score}% — {module_grade}</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 60px;">ID</th>
                <th>Diagnostic</th>
                <th style="width: 70px;">Tier</th>
                <th style="width: 70px;">Status</th>
                <th style="width: 70px;">Points</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for D08-D17 -->
            <tr>
                <td><strong>{id}</strong></td>
                <td>{diagnostic_name}</td>
                <td><span style="font-size: 0.8rem; color: var(--color-text-light);">{tier}</span></td>
                <td><span class="status-pill {status_class}">{status}</span></td>
                <td>{points}</td>
                <td>{details}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Manual Checks Required (if any) -->
<h2>Manual checks required</h2>
<div class="recommendations">
    <p style="color: var(--color-text-light); margin-bottom: 12px;">
        The following checks require manual verification and could not be automated:
    </p>
    <ul style="padding-left: 20px;">
        <!-- Repeat for each manual check -->
        <li style="padding: 4px 0;">{manual_check_description}</li>
        <!-- /Repeat -->
    </ul>
</div>

<!-- Recommendations -->
<h2>Recommendations</h2>
<div class="recommendations">
    <ol>
        <!-- Repeat for each recommendation, in priority order -->
        <li>{recommendation}</li>
        <!-- /Repeat -->
    </ol>
</div>
```

## Data Extraction Guide

Parse the tracking-audit.md file for:

1. **Header block**: `**Date:**`, `**Account:**`, `**Mode:**` (one of: completeness / tag-health / consent / attribution / oct / hygiene / advanced / full), `**Vertical:**`, `**Overall Score:**`
2. **Executive read**: Section under `## Executive read` — prose paragraphs (≤300 words, no bullets). Split by paragraph break, render each as a separate `<p>`. Quoted peer-report findings stay inline — tracking is the Measurement layer / cascade root, so contradictions with downstream skills (bidding, QS, search-term, LP) are surfaced explicitly. Covers six slots in order: score meaning, this-week priorities, what is NOT a problem, fresh peer findings, how to read the rest, score trend
3. **Module Score table**: Under `## Module Scores` or similar — Module | Score | Grade
4. **Critical Issues**: Numbered list under `## Critical Issues` — each has Finding, Impact, Fix
5. **Completeness Results**: Table with ID | Diagnostic | Tier | Status | Points | Details
6. **Tag Health Results**: Same table structure as Completeness
7. **Manual Checks Required**: Listed under dedicated section
8. **Recommendations**: Numbered list

## Tier Display

| Tier | Meaning |
|------|---------|
| API | Checked via Google Ads API data |
| DevTools | Checked via Chrome DevTools |
| Manual | Requires human verification |
