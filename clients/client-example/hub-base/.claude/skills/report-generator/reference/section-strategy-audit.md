# Section Template: Strategy & Unit Economics Audit

HTML section template for rendering strategy-audit.md data. Insert into `{report_body_sections}` in the base template.

## Source File

`clients/<name>/context/analysis/strategy-audit.md`

## Modules

2 modules: Unit Economics, Goals & KPIs

## Unique Features

- **Viability Verdict**: Go / Conditional Go / No-Go — prominently displayed
- **ASK items**: Unresolved questions that need user input

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

<!-- Viability Verdict Banner -->
<div class="verdict-banner {verdict_class}">
    Viability verdict: {verdict}
</div>

<!-- Executive Read -->
<h2>Executive read</h2>
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 24px; margin: 16px 0;">
    <!-- Repeat for each paragraph (≤300 words total, prose only — no bullets). Quoted peer-report findings stay inline — strategy is the B-layer; tracking-audit is the upstream validation, bidding/budget are downstream-blocked -->
    <p style="font-size: 1rem; line-height: 1.7; margin: 0 0 12px;">{executive_paragraph}</p>
    <!-- /Repeat -->
</div>

<!-- Module Scores Grid -->
<h2>Module scores</h2>
<div class="scores-grid">
    <!-- Repeat for: Unit Economics, Goals & KPIs -->
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

<!-- Unit Economics Results -->
<div class="module-section">
    <div class="module-header">
        <h3>Unit economics</h3>
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
            <!-- Repeat for each diagnostic -->
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

<!-- Goals & KPIs Results -->
<div class="module-section">
    <div class="module-header">
        <h3>Goals & KPIs</h3>
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
            <!-- Repeat for each diagnostic -->
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

<!-- Unresolved Questions (ASK items, if any) -->
<!-- Only include if there are ASK items -->
<h2>Unresolved questions</h2>
<div class="recommendations" style="border-left: 4px solid var(--color-warning);">
    <p style="color: var(--color-text-light); margin-bottom: 12px;">
        The following items need clarification before a full assessment can be made:
    </p>
    <ul style="padding-left: 20px;">
        <!-- Repeat for each ASK item -->
        <li style="padding: 4px 0;">{ask_description}</li>
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

Parse the strategy-audit.md file for:

1. **Header block**: `**Date:**`, `**Account:**`, `**Vertical:**`, `**Mode:**`, `**Overall Score:**`
2. **Executive read**: Section under `## Executive read` — prose paragraphs (≤300 words, no bullets). Split by paragraph break, render each as a separate `<p>`. Quoted peer-report findings stay inline — strategy is the B-layer; tracking-audit is the upstream validation, bidding/budget are downstream-blocked. Covers six slots in order: score meaning, this-week priorities, what is NOT a problem, fresh peer findings, how to read the rest, score trend
3. **Overall Score table**: Module | Score | Grade
4. **Viability Verdict**: Look for `Go`, `Conditional Go`, or `No-Go` — often in a prominent section or as part of the summary
5. **Unit Economics Results table**: ID | Diagnostic | Status | Pts | Details
6. **Goals & KPIs Results table**: Same structure
7. **Critical Issues**: Only FAIL items — What | Impact | Fix
8. **ASK items**: Items with ASK status that need user input
9. **Recommendations**: Numbered list

## Verdict Class Mapping

| Verdict | CSS Class |
|---------|-----------|
| Go | `go` |
| Conditional Go | `conditional` |
| No-Go | `no-go` |
