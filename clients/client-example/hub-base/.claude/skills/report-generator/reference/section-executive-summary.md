# Section Template: Executive Summary

HTML section template for a combined report across all available audits. Insert into `{report_body_sections}` in the base template.

## Purpose

The executive summary provides a high-level overview of all audit results for a client, combining scores and critical issues across all available audit types into one document.

## HTML Section

```html
<!-- Executive Summary Header -->
<div class="overall-score" style="background: var(--color-primary); color: #ffffff; border: none;">
    <div style="font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; opacity: 0.8;">
        Executive summary
    </div>
    <div class="score-value" style="color: #ffffff;">{average_score}%</div>
    <div class="score-grade" style="color: rgba(255,255,255,0.8);">
        Average across {audit_count} audits — {average_grade}
    </div>
</div>

<!-- All Audit Scores Grid -->
<h2>Audit overview</h2>
<div class="scores-grid">
    <!-- Repeat for each available audit -->
    <div class="score-card">
        <div class="module-name">{audit_display_name}</div>
        <div class="module-score" style="color: var(--color-{grade_color});">{audit_score}%</div>
        <div class="module-grade">{audit_grade}</div>
        <div style="margin-top: 8px;">
            <div class="progress-bar">
                <div class="fill {grade_class}" style="width: {audit_score}%"></div>
            </div>
        </div>
        <div style="font-size: 0.8rem; color: var(--color-text-light); margin-top: 8px;">
            {audit_date}
        </div>
    </div>
    <!-- /Repeat -->
</div>

<!-- Strengths & Weaknesses -->
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin: 24px 0;">
    <!-- Strengths Column -->
    <div style="padding: 20px; background: #f0fdf4; border-radius: var(--border-radius); border: 1px solid #bbf7d0;">
        <h3 style="color: #166534; margin: 0 0 12px;">Strengths</h3>
        <ul style="padding-left: 20px; margin: 0;">
            <!-- List modules/audits scoring >= 80% -->
            <li style="padding: 4px 0; color: #166534;">{strength_item} — {score}%</li>
        </ul>
    </div>
    <!-- Weaknesses Column -->
    <div style="padding: 20px; background: #fef2f2; border-radius: var(--border-radius); border: 1px solid #fecaca;">
        <h3 style="color: #991b1b; margin: 0 0 12px;">Areas for improvement</h3>
        <ul style="padding-left: 20px; margin: 0;">
            <!-- List modules/audits scoring < 70% -->
            <li style="padding: 4px 0; color: #991b1b;">{weakness_item} — {score}%</li>
        </ul>
    </div>
</div>

<!-- Strategy Viability (only if strategy audit is available) -->
<!-- Include this block only if strategy-audit.md was parsed -->
<div class="verdict-banner {verdict_class}" style="margin: 24px 0;">
    Strategy viability: {verdict}
</div>

<!-- All Critical Issues (aggregated) -->
<h2>Critical issues across all audits</h2>
<p style="color: var(--color-text-light); margin-bottom: 16px;">
    {total_critical_count} critical issues found across all audits, sorted by priority.
</p>

<!-- If no critical issues across all audits: -->
<p style="color: var(--color-success); font-weight: 600;">No critical issues found across any audit.</p>

<!-- Repeat for each critical issue, grouped by audit type: -->
<h3 style="font-size: 0.95rem; color: var(--color-text-light); margin-top: 20px;">{audit_display_name}</h3>
<div class="issue-card">
    <div class="issue-id">{diagnostic_id}</div>
    <div class="issue-title">{issue_description}</div>
    <div class="issue-impact">{impact}</div>
</div>
<!-- /Repeat -->

<!-- Per-Audit Module Breakdown -->
<h2>Detailed scores by audit</h2>

<!-- Repeat for each audit type -->
<div class="module-section">
    <div class="module-header">
        <h3>{audit_display_name}</h3>
        <span class="score-badge {grade_class}">{audit_score}% — {audit_grade}</span>
    </div>
    <p style="font-size: 0.85rem; color: var(--color-text-light); margin-bottom: 12px;">
        Audited: {audit_date}
    </p>
    <table>
        <thead>
            <tr>
                <th>Module</th>
                <th style="width: 80px;">Score</th>
                <th style="width: 100px;">Grade</th>
                <th>Key finding</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each module in the audit -->
            <tr>
                <td><strong>{module_name}</strong></td>
                <td>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        {module_score}%
                        <div class="progress-bar" style="width: 60px;">
                            <div class="fill {module_grade_class}" style="width: {module_score}%"></div>
                        </div>
                    </div>
                </td>
                <td><span class="score-badge {module_grade_class}" style="font-size: 0.8rem; padding: 2px 8px;">{module_grade}</span></td>
                <td style="font-size: 0.85rem;">{key_finding_summary}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>
<!-- /Repeat for each audit -->

<!-- Priority Recommendations -->
<h2>Priority recommendations</h2>
<div class="recommendations">
    <p style="color: var(--color-text-light); margin-bottom: 16px;">
        Top actions to improve overall account health, prioritized by impact:
    </p>
    <ol>
        <!-- Aggregate and prioritize recommendations across all audits -->
        <!-- List the top 5-10 highest-impact recommendations -->
        <li>
            <strong>{recommendation_title}</strong><br>
            <span style="font-size: 0.9rem; color: var(--color-text-light);">{recommendation_detail} (Source: {audit_name})</span>
        </li>
    </ol>
</div>

<!-- Data Freshness Summary -->
<h2>Data freshness</h2>
<table>
    <thead>
        <tr>
            <th>Audit</th>
            <th>Date</th>
            <th>Age</th>
            <th>Status</th>
        </tr>
    </thead>
    <tbody>
        <!-- Repeat for each audit -->
        <tr>
            <td>{audit_display_name}</td>
            <td>{audit_date}</td>
            <td>{days_old} days</td>
            <td><span class="status-pill {freshness_class}">{freshness_status}</span></td>
        </tr>
        <!-- /Repeat -->
    </tbody>
</table>
<p style="font-size: 0.85rem; color: var(--color-text-light); margin-top: 8px;">
    Audits older than 14 days may not reflect current account state. Consider re-running stale audits.
</p>
```

## Data Extraction Guide

For the executive summary, parse ALL available `*-audit.md` files:

1. **For each audit file**: Extract header (date, score, grade) and module scores table
2. **Average score**: Calculate mean of all audit overall scores
3. **Strengths**: Modules scoring >= 80% across all audits
4. **Weaknesses**: Modules scoring < 70% across all audits
5. **Critical issues**: Aggregate all FAIL items from all audits
6. **Recommendations**: Merge and deduplicate routing recommendations, sort by priority
7. **Strategy verdict**: Include only if strategy-audit.md exists
8. **Data freshness**: Calculate days since each audit date

## Freshness Status

| Days Old | Status | CSS Class |
|----------|--------|-----------|
| 0-7 | Fresh | `pass` |
| 8-14 | Recent | `warn` |
| 15+ | Stale | `fail` |

## Strengths/Weaknesses Logic

- **Strengths**: Any audit or module scoring >= 80% (Good or Excellent)
- **Weaknesses**: Any audit or module scoring < 70% (Needs attention or Critical)
- Middle ground (70-79%): Include in neither list
- Sort strengths highest-first, weaknesses lowest-first

## Print Considerations

The executive summary should fit well in a printed PDF:
- The scores grid should not break across pages
- Issue cards should not break across pages
- The per-audit module breakdown tables may span pages — this is acceptable
