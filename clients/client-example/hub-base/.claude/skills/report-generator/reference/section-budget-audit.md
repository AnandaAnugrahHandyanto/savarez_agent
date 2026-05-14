# Section Template: Budget Audit

HTML section template for rendering budget-audit.md data. Insert into `{report_body_sections}` in the base template.

## Source File

`clients/<name>/context/analysis/budget-audit.md`

## Modules

5 modules: Allocation (BUD-D13–D16, /30), Limitation (BUD-D01–D04, /25), Pacing (BUD-D09–D12, /15 or N/A), Sufficiency (BUD-D05–D08, /15), Shared Budgets (BUD-D17–D19, /15 or N/A). When a module is fully SKIP'd it returns N/A and its weight redistributes proportionally to the remaining modules.

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
        Window: {period}d · Module scope: {module_scope} · Campaigns: {campaigns_audited} ({base_count} base + {experiment_count} experiment{experiment_scope_note})
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
    <!-- Repeat for each module: Allocation (/30), Limitation (/25), Pacing (/15 or N/A), Sufficiency (/15), Shared Budgets (/15 or N/A) -->
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
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— blocking, do not change budgets yet</span>
    </div>
    <table>
        <thead>
            <tr>
                <th>Campaign</th>
                <th>Finding</th>
                <th style="width: 220px;">Handoff</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each blocking finding. Quote fresh peer-report findings inline in the Finding cell. -->
            <tr>
                <td>{campaign_name}</td>
                <td>{finding_description}</td>
                <td><code>{handoff_skill}</code></td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 2: Bidding-side fix first (Bid layer — peer with budget) -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#9881;&#65039;</span>
        <h3 style="margin: 0; color: var(--color-warning);">Bidding-side fix first</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— budget side is downstream of a tCPA / portfolio decision</span>
    </div>
    <table>
        <thead>
            <tr>
                <th>Campaign</th>
                <th>Issue</th>
                <th style="width: 220px;">Fix</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each Bid-layer finding (BUD-D05 / BUD-D08 / BUD-D19) -->
            <tr>
                <td>{campaign_name}</td>
                <td>{issue_description}</td>
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
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— before raising spend</span>
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

<!-- Section 4: Allocation moves (after upstream layers clear) -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#9878;&#65039;</span>
        <h3 style="margin: 0; color: var(--color-info);">Allocation moves</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— paired reduce / raise legs (BUD-D13, BUD-D14, BUD-D15)</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 80px;">Leg</th>
                <th>Campaign</th>
                <th>Daily change</th>
                <th>Monthly impact</th>
                <th style="width: 240px;">Optimizer command</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each allocation leg (Reduce / Raise pairs, or single Reallocate rows) -->
            <tr>
                <td>{leg_label}</td>
                <td>{campaign_name}</td>
                <td>{daily_change}</td>
                <td>{monthly_impact}</td>
                <td><code>{optimizer_command}</code></td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 5: Act now (T layer — pure budget, cleared cascade) -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#9989;</span>
        <h3 style="margin: 0; color: var(--color-success);">Act now</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— every upstream layer has cleared</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 40px;">#</th>
                <th>Action</th>
                <th>Campaign</th>
                <th style="width: 100px;">Est. impact</th>
                <th style="width: 240px;">Optimizer command</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each safe action -->
            <tr>
                <td>{step_number}</td>
                <td>{action_description}</td>
                <td>{campaign_name}</td>
                <td>{estimated_impact}</td>
                <td><code>{optimizer_command}</code></td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 6: Hold (recently changed within 14 days) -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#9888;&#65039;</span>
        <h3 style="margin: 0; color: var(--color-warning);">Hold (recently changed)</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— budget changed in last 14 days; optimizer hard-refuses further mutation this session</span>
    </div>
    <table>
        <thead>
            <tr>
                <th>Campaign</th>
                <th>Change</th>
                <th style="width: 140px;">Verify after</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each recently-changed campaign -->
            <tr>
                <td>{campaign_name}</td>
                <td>{change_description}</td>
                <td>{verify_after_date}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 7: Confirm intent (INFO — review, not action) -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#8505;&#65039;</span>
        <h3 style="margin: 0; color: var(--color-text-light);">Confirm intent</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— looks red but usually deliberate</span>
    </div>
    <table>
        <thead>
            <tr>
                <th>Campaign / scope</th>
                <th>Apparent issue</th>
                <th>Likely intent</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each INFO-only finding (deliberate shared-budget skew, paused-but-enabled, small geo test, etc.) -->
            <tr>
                <td>{scope}</td>
                <td>{apparent_issue}</td>
                <td>{likely_intent}</td>
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
            <th style="width: 200px;">Type</th>
            <th>Campaign / scope</th>
            <th>Projected impact</th>
            <th style="width: 240px;">Action</th>
        </tr>
    </thead>
    <tbody>
        <!-- Repeat for each opportunity (profitable_limited_recovery, winner_underfunded, seasonality_ramp, underspend_redeploy, etc.) -->
        <tr>
            <td>{opportunity_number}</td>
            <td>{opportunity_type}</td>
            <td>{campaign_or_scope}</td>
            <td>{projected_impact}</td>
            <td><code>{action_command}</code></td>
        </tr>
        <!-- /Repeat -->
    </tbody>
</table>

<!-- Pacing snapshot — only when Module 3 (Pacing) ran -->
<!-- If pacing module SKIPped, omit this whole block -->
<h2>Pacing snapshot</h2>
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 16px; margin: 16px 0; font-size: 0.9rem;">
    <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
        <li><strong>MTD spend:</strong> {mtd_spend} {currency}</li>
        <li><strong>Days elapsed:</strong> {days_elapsed} of {days_in_month}</li>
        <li><strong>Avg daily so far:</strong> {avg_daily} {currency}</li>
        <li><strong>Projected month:</strong> {projected_month} {currency} ({pacing_delta_pct}% vs target {monthly_target})</li>
        <li><strong>Seasonality:</strong> {current_month} ({seasonality_label})</li>
    </ul>
</div>

<!-- Sequenced handoffs -->
<h2>Sequenced handoffs</h2>
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 20px; margin: 16px 0;">
    <p style="font-size: 0.95rem; line-height: 1.7; margin: 0 0 12px;"><strong>Top hypothesis:</strong> {hypothesis_layer} — {hypothesis_name}.</p>
    <p style="font-size: 0.95rem; line-height: 1.7; margin: 0 0 12px;">Before any budget change, here's what to do, in order:</p>
    <ol style="font-size: 0.95rem; line-height: 1.8; margin: 0; padding-left: 24px;">
        <!-- Repeat for each numbered step. When a fresh peer report exists, quote its top finding inline; otherwise say "run /skill". -->
        <li>{handoff_step}</li>
        <!-- /Repeat -->
    </ol>
</div>

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
                <th>Campaign / scope</th>
                <th style="width: 80px;">Verdict</th>
                <th>Note / next step</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each diagnostic in the module — INFO-only diagnostics flagged in note -->
            <tr>
                <td><strong>{diagnostic_id}</strong></td>
                <td>{campaign_or_scope}</td>
                <td><span class="status-pill {status_class}">{verdict}</span></td>
                <td>{note}</td>
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
        <li><strong>Monthly target:</strong> {monthly_target} {currency} ({target_mode})</li>
        <li><strong>Per-campaign overrides:</strong> {override_count}</li>
        <li><strong>Seasonality:</strong> {seasonality_mode}; highlight months: {highlight_months}</li>
        <li><strong>Daily : tCPA ratio threshold:</strong> {daily_tcpa_threshold} (default 2.0)</li>
        <li><strong>Max single-mutation multiplier:</strong> {max_step} (default 1.3×)</li>
        <li><strong>Last analyst confirmation:</strong> {last_confirmed}</li>
        <li><strong>Primary KPI / break-even:</strong> {primary_kpi} / {break_even}</li>
        <li><strong>Experiments scope:</strong> {experiments_scope}</li>
    </ul>
</div>
```

## Data Extraction Guide

Parse the budget-audit.md file for:

1. **Header block**: `**Score:**`, `**Window:**` (period days), `**Module scope:**` (full / limitation / sufficiency / pacing / allocation / shared / opportunities), `**Campaigns audited:**` (split into base + experiment counts; note `experiments excluded if base-only` if present), `**Currency:**`, `**Run by:**` line
2. **Executive read**: Section under `## Executive read` — 2-4 prose paragraphs (no bullets, ~300 words total). Split by paragraph break, render each as a separate `<p>`. Quoted peer-report findings stay inline with the surrounding prose
3. **Diagnosis (technical)**: Section under `## Diagnosis (technical)` — single paragraph stating root-cause hypothesis, cascade layer, and what to do first
4. **Top hypothesis**: Section under `## Top hypothesis` — extract Layer (M / B / Bid / Eff / Conv / Comp / Struct / T), Name, Confidence (low/medium/high), Evidence narrative
5. **Module Scores table**: Table under `## Module scores` — 5 modules with non-uniform max scores (Allocation /30, Limitation /25, Pacing /15 or N/A, Sufficiency /15, Shared Budgets /15 or N/A) plus a Total row. When a module shows `N/A` or "redistributed", render it with status text instead of a percentage bar
6. **Risks**: Section under `## Risks (segmented by cascade state)` with up to 7 sub-sections — render only those that have content:
   - `### 🔍 Investigate first (blocking handoffs)` — campaign → finding → `/skill` (only when M/B hypotheses active). Quote fresh peer-report one-liners inline in the finding cell
   - `### 🔧 Bidding-side fix first` — BUD-D05 / BUD-D08 / BUD-D19 (Bid layer peer findings) → `/bidding-specialist`
   - `### 🔄 Recover efficiency first` — search-term → keyword → quality-score → rsa → lp → offer sequence (when Eff/Conv active)
   - `### ⚖️ Allocation moves` — paired Reduce / Raise legs for BUD-D13 / BUD-D14 / BUD-D15 → `/budget-optimizer reduce | raise | reallocate`
   - `### ✅ Act now (T layer)` — items that survived the cascade. Each names a `/budget-optimizer {subcommand}`
   - `### ⚠️ Hold (recently changed)` — campaigns with budget changes in the last 14 days. Render `verify_after_date` (change date + 14 days)
   - `### ℹ️ Confirm intent` — INFO findings that look red but are usually deliberate (branded shared-budget skew, paused-but-enabled, deliberate small geo test)
7. **Opportunities**: Table under `## Opportunities` — # | Type | Campaign / scope | Projected impact | Action. Always rendered (even with zero risks). If `breakEven` was missing in the source audit, projections may show `investigate` instead of dollar amounts — render verbatim
8. **Pacing snapshot**: Block under `## Pacing snapshot (only when Module 3 ran)` — render only if the section exists in the source markdown. Pull MTD spend, days elapsed, avg daily, projected month + delta vs target, seasonality label
9. **Sequenced handoffs**: Section under `## Sequenced handoffs` — extract the top-hypothesis lead-in line and the numbered protocol that follows. Each numbered item is rendered as one `<li>`. When fresh peer reports exist, the protocol quotes their top findings inline (preserve the quotes verbatim — don't re-summarize)
10. **Module details**: Section under `## Module details` — per-diagnostic verdict + note + suggested next step. INFO-only and SKIP'd diagnostics flagged in the note
11. **Configuration snapshot**: Section under `## Configuration snapshot` — Monthly target (with `fallback mode active` or `configured` flag), per-campaign overrides count, seasonality mode + highlight months, daily:tCPA ratio threshold, max single-mutation multiplier, last analyst confirmation, primary KPI / break-even, experiments scope (`INCLUDED (active variants count)` or `excluded (base-only)`)

## Special Fields

- **Score format**: Total is rendered as `{x}/100` not `{x}%`. Module scores are `{x}/{module_max}` with non-uniform maximums — display both the raw score and a percentage-based progress bar. When a module is `N/A` due to full SKIP, show the `N/A` text and a "redistributed" status badge instead of a bar
- **Module scope**: Header indicates whether full audit or single-module run (limitation / sufficiency / pacing / allocation / shared / opportunities). Display under the overall score
- **Campaigns audited line**: Always split into `{base_count} base + {experiment_count} experiment`. If the audit ran with `base-only`, the note becomes `; experiments excluded` — render verbatim
- **Executive read**: Flowing prose paragraphs (~300 words total). Render each paragraph as `<p>`, no bullet conversion. Peer-report quotes stay inline
- **Top hypothesis layer codes**: M=Measurement, B=Business, Bid=Bidding, Eff=Efficiency, Conv=Conversion, Comp=Competitive, Struct=Structural, T=Traffic. Render layer code verbatim — readers familiar with the cascade recognize the abbreviation
- **Risks — 7 segments**: Only render populated segments. Investigate-first, Bidding-side, and Recover-efficiency point to upstream skills; Allocation-moves and Act-now point to `/budget-optimizer` subcommands; Hold lists recently-changed campaigns; Confirm-intent is INFO-only
- **Opportunities**: Cross-cutting list, populated even when there are zero risks — render the section unconditionally. Dollar projections may degrade to `investigate` when break-even is unresolved
- **Pacing snapshot**: Conditional — only render the entire block if Module 3 ran (i.e., the section exists in the source markdown). When Pacing is N/A account-wide, omit this section
- **Configuration snapshot**: Footer-style summary of business posture used as the audit yardstick. Note the experiments scope explicitly because budget-auditor includes experiments by default (inverse of bidding-auditor)

## Status-to-Class Mapping

| Verdict | CSS Class |
|---------|-----------|
| PASS    | `pass`    |
| WARN    | `warn`    |
| FAIL    | `fail`    |
| INFO    | `skip`    |
| N/A     | `skip`    |
| SKIP    | `skip`    |

## Grade Color Mapping

Map score percentages to color variables:
- 90-100%: `--color-success` (green)
- 70-89%: `--color-info` (blue)
- 50-69%: `--color-warning` (amber)
- <50%: `--color-danger` (red)
