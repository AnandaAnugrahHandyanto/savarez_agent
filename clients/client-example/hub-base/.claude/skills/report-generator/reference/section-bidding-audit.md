# Section Template: Bidding Audit

HTML section template for rendering bidding-audit.md data. Insert into `{report_body_sections}` in the base template.

## Source File

`clients/<name>/context/analysis/bidding-audit.md`

## Modules

7 modules: Target Validation (BID-D05–D09, /25), Strategy Selection (BID-D01–D04, /20), Learning Phase (BID-D10–D13, /15), Portfolio Health (BID-D14–D17, /15), CPC & Cost Health (BID-D22–D24, /10), Conversion Value Rules (BID-D25–D26, /10), Bid Adjustments (BID-D18–D21, /5)

## HTML Section

```html
<!-- Overall Score -->
<div class="overall-score">
    <div class="score-value">{overall_score}/100</div>
    <div class="score-grade">{overall_grade}</div>
    <div style="max-width: 300px; margin: 12px auto 0;">
        <div class="progress-bar">
            <div class="fill {grade_class}" style="width: {overall_score}%"></div>
        </div>
    </div>
    <div style="font-size: 0.85rem; color: var(--color-text-light); margin-top: 8px;">
        Window: {period}d · Module scope: {module_scope} · Posture: {posture}
    </div>
</div>

<!-- Executive Read -->
<h2>Executive read</h2>
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 24px; margin: 16px 0;">
    <!-- Repeat for each paragraph (2-4 paragraphs) -->
    <p style="font-size: 1rem; line-height: 1.7; margin: 0 0 12px;">{executive_paragraph}</p>
    <!-- /Repeat -->
</div>

<!-- Diagnosis (technical) -->
<h2>Diagnosis</h2>
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 24px; margin: 16px 0;">
    <p style="font-size: 1rem; line-height: 1.7; margin: 0;">{diagnosis_narrative}</p>
</div>

<!-- Top Hypothesis -->
<h2>Top hypothesis</h2>
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 20px; margin: 16px 0;">
    <div style="display: flex; gap: 24px; flex-wrap: wrap; margin-bottom: 12px;">
        <div style="padding: 12px 16px; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
            <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase; letter-spacing: 0.5px;">Layer</div>
            <div style="font-weight: 700; margin-top: 4px;">{hypothesis_layer}</div>
        </div>
        <div style="padding: 12px 16px; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
            <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase; letter-spacing: 0.5px;">Name</div>
            <div style="font-weight: 700; margin-top: 4px;">{hypothesis_name}</div>
        </div>
        <div style="padding: 12px 16px; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
            <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase; letter-spacing: 0.5px;">Confidence</div>
            <div style="font-weight: 700; margin-top: 4px;">{confidence}</div>
        </div>
    </div>
    <p style="font-size: 0.95rem; line-height: 1.7; margin: 0;">{hypothesis_evidence}</p>
</div>

<!-- Module Scores Grid -->
<h2>Module scores</h2>
<div class="scores-grid">
    <!-- Repeat for each module: Target Validation (/25), Strategy Selection (/20), Learning Phase (/15), Portfolio Health (/15), CPC & Cost Health (/10), Conversion Value Rules (/10), Bid Adjustments (/5) -->
    <div class="score-card">
        <div class="module-name">{module_name}</div>
        <div class="module-score" style="color: var(--color-{grade_color});">{module_score}/{module_max}</div>
        <div class="module-grade">{module_grade}</div>
        <div style="margin-top: 8px;">
            <div class="progress-bar">
                <div class="fill {module_grade_class}" style="width: {module_score_pct}%"></div>
            </div>
        </div>
    </div>
    <!-- /Repeat -->
</div>

<!-- Risks — segmented by cascade state -->
<h2>Risks</h2>

<!-- Section 1: Investigate first (blocking handoffs — Measurement/Business active) -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#128269;</span>
        <h3 style="margin: 0; color: var(--color-danger);">Investigate first</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— blocking, do not mutate bids yet</span>
    </div>
    <table>
        <thead>
            <tr>
                <th>Finding</th>
                <th style="width: 220px;">Handoff</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each blocking finding -->
            <tr>
                <td>{finding_description}</td>
                <td><code>{handoff_skill}</code></td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 2: Structural fix needed (BID-D14, BID-D17, mixed portfolio, etc.) -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#128295;</span>
        <h3 style="margin: 0; color: var(--color-warning);">Structural fix needed</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— resolve before adjusting targets</span>
    </div>
    <table>
        <thead>
            <tr>
                <th>Issue</th>
                <th>Affected</th>
                <th style="width: 220px;">Fix</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each structural issue -->
            <tr>
                <td>{issue_description}</td>
                <td>{affected_scope}</td>
                <td><code>{fix_command}</code></td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 3: Recover efficiency first (Eff/Conv hypotheses active) -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#128260;</span>
        <h3 style="margin: 0; color: var(--color-info);">Recover efficiency first</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— before changing strategy or targets</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 50px;">Step</th>
                <th style="width: 220px;">Skill</th>
                <th>What it addresses</th>
                <th>Expected impact</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each recovery step (search-term → keyword → quality-score → rsa → lp → offer) -->
            <tr>
                <td>{step_number}</td>
                <td><code>{skill_command}</code></td>
                <td>{addresses}</td>
                <td>{expected_impact}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 4: Act now (safe — survived all cascade layers) -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#9989;</span>
        <h3 style="margin: 0; color: var(--color-success);">Act now</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— safe regardless of cascade state</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 40px;">#</th>
                <th>Action</th>
                <th>Scope</th>
                <th style="width: 100px;">Est. impact</th>
                <th style="width: 240px;">Optimizer command</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each safe action -->
            <tr>
                <td>{step_number}</td>
                <td>{action_description}</td>
                <td>{scope}</td>
                <td>{estimated_impact}</td>
                <td><code>{optimizer_command}</code></td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 5: Hold (in learning — BID-D11, BID-D13) -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#9888;&#65039;</span>
        <h3 style="margin: 0; color: var(--color-warning);">Hold (in learning)</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— do not touch until window clears</span>
    </div>
    <table>
        <thead>
            <tr>
                <th>Campaign</th>
                <th>Reason</th>
                <th style="width: 140px;">Window clears</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each in-learning campaign -->
            <tr>
                <td>{campaign_name}</td>
                <td>{learning_reason}</td>
                <td>{window_clear_date}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Opportunities -->
<h2>Opportunities</h2>
<table>
    <thead>
        <tr>
            <th style="width: 40px;">#</th>
            <th style="width: 180px;">Type</th>
            <th>Campaign</th>
            <th>Projected impact</th>
            <th style="width: 240px;">Action</th>
        </tr>
    </thead>
    <tbody>
        <!-- Repeat for each opportunity -->
        <tr>
            <td>{opportunity_number}</td>
            <td>{opportunity_type}</td>
            <td>{campaign_name}</td>
            <td>{projected_impact}</td>
            <td><code>{action_command}</code></td>
        </tr>
        <!-- /Repeat -->
    </tbody>
</table>

<!-- Learning State -->
<h2>Learning state</h2>
<table>
    <thead>
        <tr>
            <th>Campaign</th>
            <th>Strategy</th>
            <th>Last strategy change</th>
            <th>Last target change</th>
            <th>Days since</th>
            <th>In learning</th>
        </tr>
    </thead>
    <tbody>
        <!-- Repeat for each campaign -->
        <tr>
            <td>{campaign_name}</td>
            <td>{strategy}</td>
            <td>{last_strategy_change}</td>
            <td>{last_target_change}</td>
            <td>{days_since}</td>
            <td><span class="status-pill {learning_status_class}">{in_learning}</span></td>
        </tr>
        <!-- /Repeat -->
    </tbody>
</table>

<!-- Module Detail Sections -->
<!-- Repeat for each module -->
<div class="module-section">
    <div class="module-header">
        <h3>{module_name}</h3>
        <span class="score-badge {module_grade_class}">{module_score}/{module_max} — {module_grade}</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 80px;">ID</th>
                <th>Diagnostic</th>
                <th style="width: 80px;">Verdict</th>
                <th>Evidence / next step</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each diagnostic in the module — INFO-only diagnostics flagged in evidence -->
            <tr>
                <td><strong>{diagnostic_id}</strong></td>
                <td>{diagnostic_name}</td>
                <td><span class="status-pill {status_class}">{verdict}</span></td>
                <td>{evidence}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>
<!-- /Repeat for each module -->

<!-- Configuration Snapshot -->
<h2>Configuration snapshot</h2>
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 16px; margin: 16px 0; font-size: 0.9rem;">
    <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
        <li><strong>Primary KPI:</strong> {primary_kpi}</li>
        <li><strong>Break-even:</strong> {break_even}</li>
        <li><strong>Posture:</strong> {posture} (PAR target {par_target})</li>
        <li><strong>Last confirmed:</strong> {last_confirmed}</li>
    </ul>
</div>
```

## Data Extraction Guide

Parse the bidding-audit.md file for:

1. **Header block**: `**Score:**`, `**Window:**` (period days), `**Module scope:**` (full / strategy / targets / learning / portfolio / adjustments / cpc / value-rules), `**Run by:**` line
2. **Executive read**: Section under `## Executive read` — 2-4 prose paragraphs (no bullets). Split by paragraph break, render each as a separate `<p>`
3. **Diagnosis (technical)**: Section under `## Diagnosis (technical)` — single paragraph stating root-cause hypothesis, cascade layer, and what to do first
4. **Top hypothesis**: Section under `## Top hypothesis` — extract Layer (M / B / Vol / Eff / Conv / Bud / Comp / Struct / T), Name, Confidence (low/medium/high), Evidence narrative
5. **Module Scores table**: Table under `## Module scores` — 7 modules with non-uniform max scores (Target Validation /25, Strategy Selection /20, Learning Phase /15, Portfolio Health /15, CPC & Cost Health /10, Conversion Value Rules /10, Bid Adjustments /5) plus a Total row
6. **Risks**: Section under `## Risks (segmented by cascade state)` with 5 sub-sections:
   - `### 🔍 Investigate first (blocking handoffs)` — finding → `/skill` (only when M/B hypotheses active)
   - `### 🔧 Structural fix needed` — BID-D14, BID-D17, mixed-portfolio, etc.
   - `### 🔄 Recover efficiency first` — search-term → keyword → quality-score → rsa → lp → offer sequence (when Eff/Conv active)
   - `### ✅ Act now (safe)` — items that survived cascade. Each names an `/bidding-optimizer {subcommand}`
   - `### ⚠️ Hold (in learning)` — BID-D11, BID-D13 in-learning campaigns with window-clear date
7. **Opportunities**: Table under `## Opportunities` — # | Type | Campaign | Projected impact | Action. Always rendered (even with zero risks)
8. **Learning state**: Table under `## Learning state (permanent fixture)` — Campaign | Strategy | Last strategy change | Last target change | Days since | In learning. Always rendered
9. **Module details**: Section under `## Module details` — per-diagnostic verdict + evidence + suggested next step. INFO-only diagnostics flagged in evidence text
10. **Configuration snapshot**: Section under `## Configuration snapshot` — Primary KPI, Break-even, Posture (with PAR target), Last confirmed

## Special Fields

- **Score format**: Total is rendered as `{x}/100` not `{x}%`. Module scores are `{x}/{module_max}` with non-uniform maximums — display both raw score and percentage-based progress bar
- **Module scope**: Header indicates whether full audit or single-module run (strategy / targets / learning / portfolio / adjustments / cpc / value-rules). Display under the overall score
- **Executive read**: Flowing prose paragraphs (~250 words total). Render each paragraph as `<p>`, no bullet conversion
- **Top hypothesis layer codes**: M=Measurement, B=Business, Vol=Volume, Eff=Efficiency, Conv=Conversion, Bud=Budget, Comp=Competitive, Struct=Structural, T=Traffic. Render layer code verbatim — readers familiar with the cascade recognize the abbreviation
- **Risks — 5 segments**: Only render populated segments. Investigate-first and Structural-fix point to other skills; Act-now points to `/bidding-optimizer` subcommands; Hold lists campaigns in learning windows. Recover-efficiency lists upstream skills in cascade order
- **Opportunities**: Cross-cutting list, populated even when there are zero risks — render the section unconditionally
- **Learning state**: Permanent fixture — render even when empty (with a "No campaigns in learning" message)
- **Configuration snapshot**: Footer-style summary of business posture used as the audit yardstick

## Status-to-Class Mapping

| Verdict | CSS Class |
|---------|-----------|
| PASS    | `pass`    |
| WARN    | `warn`    |
| FAIL    | `fail`    |
| INFO    | `skip`    |
| N/A     | `skip`    |
| SKIP    | `skip`    |

## Learning Status Mapping

| In learning | CSS Class |
|-------------|-----------|
| Yes / true  | `warn`    |
| No / false  | `pass`    |

## Grade Color Mapping

Map score percentages to color variables:
- 90-100%: `--color-success` (green)
- 70-89%: `--color-info` (blue)
- 50-69%: `--color-warning` (amber)
- <50%: `--color-danger` (red)
