# Section Template: Search Term Audit

HTML section template for rendering search-term-audit.md data. Insert into `{report_body_sections}` in the base template.

## Source File

`clients/<name>/context/analysis/search-term-audit.md`

## Modules

5 modules: Search Term Quality (ST-D01–D05), Negative Coverage (ST-D06–D12), N-grams (ST-D13–D16), Close Variants (ST-D17–D19), Promotion & PMax (ST-D20–D26)

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
        Period: {main_period}d main · {ngram_period}d n-grams · Lag: {lag}d · Terms: {terms_analyzed}
    </div>
</div>

<!-- Portfolio context (only render if any record has target_source=portfolio) -->
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 16px; margin: 16px 0; font-size: 0.9rem;">
    <strong>Portfolio bid strategies in scope:</strong>
    <ul style="margin: 8px 0 0; padding-left: 20px;">
        <!-- Repeat for each portfolio -->
        <li>{portfolio_name} ({target_type}={target_value}, applies to: {campaigns})</li>
        <!-- /Repeat -->
    </ul>
</div>

<!-- Executive Read -->
<h2>Executive read</h2>
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 24px; margin: 16px 0;">
    <!-- Repeat for each paragraph (≤300 words total, prose only — no bullets). Quoted peer-report findings stay inline -->
    <p style="font-size: 1rem; line-height: 1.7; margin: 0 0 12px;">{executive_paragraph}</p>
    <!-- /Repeat -->
</div>

<!-- Diagnosis -->
<h2>Diagnosis</h2>
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 24px; margin: 16px 0;">
    <p style="font-size: 1rem; line-height: 1.7; margin-bottom: 0;">{diagnosis_narrative}</p>
</div>

<!-- Evidence Ladder -->
<h2>Evidence ladder</h2>
<div style="margin: 16px 0;">
    <!-- Repeat for each active cascade layer (Measurement, Business, Traffic) -->
    <div style="margin-bottom: 20px;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
            <h3 style="margin: 0; font-size: 1rem;">{layer_name} layer</h3>
            <!-- If layer is clear: -->
            <span class="status-pill pass" style="font-size: 0.75rem;">CLEAR</span>
            <!-- If layer is active: -->
            <span class="status-pill warn" style="font-size: 0.75rem;">ACTIVE</span>
        </div>
        <!-- Repeat for each evidence bullet in this layer -->
        <div style="border-left: 3px solid var(--color-border); padding: 8px 16px; margin: 8px 0; font-size: 0.9rem; line-height: 1.6;">
            {evidence_detail}
            <!-- If links to hypothesis: -->
            <span style="display: inline-block; padding: 1px 8px; background: var(--color-primary); color: #fff; border-radius: 10px; font-size: 0.75rem; font-weight: 600; margin-left: 6px;">&rarr; H{n}</span>
            <!-- If blocking: -->
            <span style="display: inline-block; padding: 1px 8px; background: var(--color-danger); color: #fff; border-radius: 10px; font-size: 0.75rem; font-weight: 600; margin-left: 4px;">BLOCKING</span>
        </div>
        <!-- /Repeat -->
    </div>
    <!-- /Repeat for each layer -->
</div>

<!-- Module Scores Grid -->
<h2>Module scores</h2>
<div class="scores-grid">
    <!-- Repeat for each module: Search Term Quality (25), Negative Coverage (25), N-grams (20), Close Variants (15), Promotion & PMax (15) -->
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

<!-- Actions — segmented by cascade state -->
<h2>Actions</h2>

<!-- Section 1: Investigate first (Measurement/Business active) -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#128269;</span>
        <h3 style="margin: 0; color: var(--color-danger);">Investigate first</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— blocking, do not negate terms yet</span>
    </div>
    <table>
        <thead>
            <tr>
                <th>Hypothesis</th>
                <th style="width: 200px;">Skill</th>
                <th>What this unblocks</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each blocking hypothesis -->
            <tr>
                <td>{hypothesis_name}</td>
                <td><code>{skill_command}</code></td>
                <td>{unblocks_description}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 2: Structural fix needed (relevant-but-underperforming terms) -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#128295;</span>
        <h3 style="margin: 0; color: var(--color-warning);">Structural fix needed</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— route upstream, never negate</span>
    </div>
    <table>
        <thead>
            <tr>
                <th>Issue</th>
                <th style="width: 80px;">Terms</th>
                <th style="width: 100px;">Waste</th>
                <th>Routes</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each structural issue -->
            <tr>
                <td>{issue_description}</td>
                <td>{term_count}</td>
                <td>{waste_amount}</td>
                <td>{routing_skills}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 3: Act now (safe) -->
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
                <th style="width: 80px;">Terms</th>
                <th style="width: 100px;">Est. impact</th>
                <th style="width: 220px;">Optimizer command</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each safe action -->
            <tr>
                <td>{step_number}</td>
                <td>{action_description}</td>
                <td>{term_count}</td>
                <td>{estimated_impact}</td>
                <td><code>{optimizer_command}</code></td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 4: Do NOT negate -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#9888;&#65039;</span>
        <h3 style="margin: 0; color: var(--color-warning);">Do NOT negate</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— relevant / profitable, must stay</span>
    </div>
    <ul style="margin: 0; padding-left: 20px; font-size: 0.9rem; line-height: 1.7;">
        <!-- Repeat for each "do not negate" category -->
        <li>{category_description}</li>
        <!-- /Repeat -->
    </ul>
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
                <th>Diagnostic</th>
                <th style="width: 80px;">Verdict</th>
                <th>Evidence</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each diagnostic in the module -->
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

<!-- Self-Learning Notes -->
<!-- Only render if the audit has a Self-Learning Notes section -->
<h2>Self-learning notes</h2>
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 16px; margin: 16px 0; font-size: 0.9rem; line-height: 1.7;">
    {self_learning_notes}
</div>

<!-- Next Recommended Action -->
<h2>Next recommended action</h2>
<div style="background: var(--color-bg-alt); border-left: 4px solid var(--color-primary); padding: 16px 20px; margin: 16px 0; font-size: 0.95rem; line-height: 1.6;">
    {next_action}
</div>
```

## Data Extraction Guide

Parse the search-term-audit.md file for:

1. **Header block**: `**Score:**`, `**Period:**` (main / n-gram periods, lag, currency), `**Terms analyzed:**` counts (Period A, Period B, PMax), optional portfolio context lines
2. **Executive read**: Section under `## Executive read` — prose paragraphs (≤300 words, no bullets). Split by paragraph break, render each as a separate `<p>`. Quoted peer-report findings stay inline. Covers six slots in order: score meaning, this-week priorities, what is NOT a problem, fresh peer findings, how to read the rest, score trend
3. **Diagnosis**: Section under `## Diagnosis` — single natural-language paragraph stating the root-cause hypothesis
4. **Evidence Ladder**: Section under `## Evidence Ladder` — grouped by cascade layer (Measurement, Business, Traffic). Each layer has bullets with evidence and optional `→ H{n}` / `BLOCKING` tags
5. **Module Scores table**: Table under `## Module Scores` — Module | Score | Grade. Five modules: Search Term Quality (/25), Negative Coverage (/25), N-grams (/20), Close Variants (/15), Promotion & PMax (/15)
6. **Actions**: Section under `## Actions` with 4 sub-sections:
   - `### 🔍 Investigate first` — hypothesis → skill
   - `### 🔧 Structural fix needed` — relevant-but-underperforming terms routed upstream
   - `### ✅ Act now (safe)` — bullet list mapping actions to `/search-term-optimizer {subcommand}`
   - `### ⚠️ Do NOT negate` — protected categories (core-relevant underperformers, OVER_TARGET converters)
7. **Module Details**: Sections named `### Module 1 — Search Term Quality`, `### Module 2 — Negative Keyword Coverage`, etc. — each has a 3-column diagnostic table (Diagnostic | Verdict | Evidence)
8. **Self-Learning Notes**: Optional section under `## Self-Learning Notes` — free-form list of relevance overrides and rejected n-grams persisted to `search-term-decisions.json`
9. **Next Recommended Action**: Section under `## Next Recommended Action` — single sentence pointing to the top handoff

## Special Fields

- **Period display**: Show main period, n-gram period, conversion lag, and terms analyzed below the overall score
- **Portfolio context**: Only render if the audit mentions portfolio bid strategies in the header. List each unique portfolio with target type/value and campaigns in scope
- **Diagnosis**: Single paragraph, not a card — the auditor writes prose here, not structured hypothesis metadata like keyword-audit does
- **Evidence Ladder**: Three layers only (Measurement, Business, Traffic). Only populated layers render
- **Actions — 4 segments**: Investigate / Structural fix / Act now / Do NOT negate. Only populated segments render
- **Optimizer commands**: Actions in "Act now" map to `/search-term-optimizer` subcommands (`negate`, `ngrams`, `promote`, `conflicts`, `consolidate`, `catalog`, `brand`, `foreign`). Render as inline code
- **Module max scores**: Not equal across modules — Quality and Coverage are /25, N-grams is /20, Close Variants and Promotion are /15. Display both the raw score and the percentage-based progress bar

## Status-to-Class Mapping

| Verdict | CSS Class |
|---------|-----------|
| PASS    | `pass`    |
| WARN    | `warn`    |
| FAIL    | `fail`    |
| INFO    | `skip`    |
| SKIP    | `skip`    |

## Cascade Layer Status Mapping

| Status | CSS Class | Label |
|--------|-----------|-------|
| Clear  | `pass`    | CLEAR |
| Active | `warn`    | ACTIVE |

## Grade Color Mapping

Map score percentages to color variables:
- 90-100%: `--color-success` (green)
- 70-89%: `--color-info` (blue)
- 50-69%: `--color-warning` (amber)
- <50%: `--color-danger` (red)
