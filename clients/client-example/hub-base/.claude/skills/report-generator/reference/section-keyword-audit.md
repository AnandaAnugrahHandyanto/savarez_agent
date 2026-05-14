# Section Template: Keyword Audit

HTML section template for rendering keyword-audit.md data. Insert into `{report_body_sections}` in the base template.

## Source File

`clients/<name>/context/analysis/keyword-audit.md`

## Modules

5 modules: Match Type Health (KW-D01–D04), Performance Segmentation (KW-D05–D09), Cannibalization & Duplicates (KW-D10–D13), Keyword Hygiene (KW-D14–D15), Intent Alignment (KW-D17–D18)

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
        Mode: {audit_mode} · Period: {evaluation_period}
    </div>
</div>

<!-- Business Context Yardstick -->
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 20px; margin: 24px 0;">
    <h3 style="margin: 0 0 12px; font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.5px; color: var(--color-text-light);">Business context (yardstick)</h3>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px 24px; font-size: 0.9rem;">
        <div><strong>Profitability threshold:</strong> {profitability_threshold}</div>
        <div><strong>Primary KPI:</strong> {primary_kpi} @ {primary_kpi_value}/event</div>
        <div><strong>Core product tokens:</strong> {core_product_tokens}</div>
        <div><strong>Target fallback mode:</strong> {target_fallback_mode}</div>
        <!-- If secondary KPI present: -->
        <div><strong>Secondary KPI:</strong> {secondary_kpi} @ {secondary_kpi_value}/event</div>
    </div>
    <!-- If target_fallback_mode is campaign_target_only: -->
    <div style="margin-top: 12px; padding: 8px 12px; background: #fef3c7; border-left: 3px solid var(--color-warning); border-radius: 0 4px 4px 0; font-size: 0.85rem; color: #92400e;">
        Campaign target fallback active — keywords without explicit targets inherit campaign-level tCPA/tROAS. Verify campaign targets before acting on efficiency findings.
    </div>
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
    <p style="font-size: 1rem; line-height: 1.7; margin-bottom: 16px;">{diagnosis_narrative}</p>
    <div style="display: flex; gap: 24px; flex-wrap: wrap; margin-bottom: 16px;">
        <div style="padding: 12px 16px; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
            <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase; letter-spacing: 0.5px;">Top hypothesis</div>
            <div style="font-weight: 700; margin-top: 4px;">{top_hypothesis_name}</div>
            <div style="font-size: 0.85rem; color: var(--color-text-light);">{top_hypothesis_layer} layer</div>
        </div>
        <div style="padding: 12px 16px; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
            <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase; letter-spacing: 0.5px;">Confidence</div>
            <div style="font-weight: 700; margin-top: 4px;">{confidence}</div>
        </div>
        <div style="padding: 12px 16px; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
            <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase; letter-spacing: 0.5px;">Explains</div>
            <div style="font-weight: 700; margin-top: 4px;">~{explained_waste_pct}% of flagged waste</div>
        </div>
    </div>
    <p style="font-size: 0.95rem; line-height: 1.7; margin-bottom: 12px;">{connecting_narrative}</p>
    <!-- If secondary hypotheses exist: -->
    <div style="margin-top: 12px;">
        <div style="font-size: 0.85rem; font-weight: 600; color: var(--color-text-light); margin-bottom: 6px;">Secondary hypotheses:</div>
        <ul style="margin: 0; padding-left: 20px; font-size: 0.9rem;">
            <!-- Repeat for each secondary hypothesis -->
            <li style="padding: 2px 0;">{hypothesis_name} — {explained_waste_pct}% of flagged waste</li>
            <!-- /Repeat -->
        </ul>
    </div>
    <div style="margin-top: 12px; font-size: 0.85rem; color: var(--color-text-light); font-style: italic;">
        If all hypotheses above are wrong: run the Act Now list below and re-audit in 14 days.
    </div>
</div>

<!-- Evidence Ladder -->
<h2>Evidence ladder</h2>
<div style="margin: 16px 0;">
    <!-- Repeat for each active cascade layer (only layers with active hypotheses appear) -->
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
            <strong>{evidence_id} — {evidence_label}:</strong> {evidence_detail}
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
    <!-- Repeat for each module: Match Type Health, Performance Segmentation, Cannibalization & Duplicates, Keyword Hygiene, Intent Alignment -->
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
            {key_finding}
        </div>
    </div>
    <!-- /Repeat -->
</div>

<!-- Actions — segmented by cascade state -->
<h2>Actions</h2>

<!-- Section 1: Investigate first -->
<!-- Only render if Measurement, Business, or Conversion hypotheses are active -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#128269;</span>
        <h3 style="margin: 0; color: var(--color-danger);">Investigate first</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— blocking, do not touch keywords yet</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 40px;">#</th>
                <th>Action</th>
                <th style="width: 140px;">Skill</th>
                <th>Resolves hypothesis</th>
                <th>What this unblocks</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each blocking investigation -->
            <tr>
                <td>{step_number}</td>
                <td>{action_description}</td>
                <td><code>{skill_command}</code></td>
                <td>H{n} — {hypothesis_name}</td>
                <td>{unblocks_description}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 2: Structural fix needed -->
<!-- Only render if core-term concentration, bid strategy, or LP/offer issues detected -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#128295;</span>
        <h3 style="margin: 0; color: var(--color-warning);">Structural fix needed</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— requires another skill, not keyword changes</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 40px;">#</th>
                <th>Action</th>
                <th style="width: 140px;">Skill</th>
                <th>Affected</th>
                <th>Est. impact</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each structural fix -->
            <tr>
                <td>{step_number}</td>
                <td>{action_description}</td>
                <td><code>{skill_command}</code></td>
                <td>{affected_scope}</td>
                <td>{estimated_impact}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 3: Recover efficiency first -->
<!-- Render whenever UNPROFITABLE keywords exist that passed Layers 1-3 -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#128260;</span>
        <h3 style="margin: 0; color: var(--color-info);">Recover efficiency first</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— before pausing, try to make these keywords profitable</span>
    </div>
    <div style="font-size: 0.9rem; color: var(--color-text-light); margin-bottom: 12px;">
        {recovery_keyword_count} keywords totaling {recovery_spend}/mo recommended for efficiency recovery before any pause action.
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 50px;">Step</th>
                <th style="width: 180px;">Skill</th>
                <th>What it addresses</th>
                <th>Expected impact</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each recovery step (ordered ER1-ER5) -->
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

<!-- Section 4: Act now (safe) -->
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
                <th>Keywords</th>
                <th>Est. impact</th>
                <th style="width: 180px;">Optimizer command</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each safe action -->
            <tr>
                <td>{step_number}</td>
                <td>{action_description}</td>
                <td>{keyword_count_or_sample}</td>
                <td>{estimated_impact}</td>
                <td><code>{optimizer_command}</code></td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 5: Do NOT pause -->
<!-- Render whenever OVER_TARGET keywords exist -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#9888;&#65039;</span>
        <h3 style="margin: 0; color: var(--color-warning);">Do NOT pause</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— profitable, above campaign target</span>
    </div>
    <div style="font-size: 0.9rem; color: var(--color-text-light); margin-bottom: 12px;">
        OVER_TARGET keywords — profitable by profitability threshold but above campaign target (tCPA/tROAS). Recommendation: adjust target or accept above-target performance.
    </div>
    <table>
        <thead>
            <tr>
                <th>Keyword</th>
                <th>Campaign</th>
                <th style="width: 80px;">Spend</th>
                <th style="width: 120px;">{primary_kpi_label}</th>
                <th style="width: 80px;">Max</th>
                <th style="width: 160px;">Action</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each OVER_TARGET keyword -->
            <tr>
                <td>{keyword_text}</td>
                <td>{campaign_name}</td>
                <td>{spend}</td>
                <td>{primary_kpi_value}</td>
                <td>{profitability_max}</td>
                <td>{recommended_action}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Module Detail Sections -->
<!-- Repeat for each module -->
<div class="module-section">
    <div class="module-header">
        <h3>{module_name}</h3>
        <span class="score-badge {module_grade_class}">{module_score}% — {module_grade}</span>
    </div>

    <!-- Module 2: Performance Segmentation — Target source banner (only render inside Module 2 when any campaign uses a portfolio bid strategy) -->
    <div style="background: var(--color-bg-alt); border-left: 3px solid var(--color-info); border-radius: 0 4px 4px 0; padding: 10px 14px; margin: 12px 0; font-size: 0.9rem;">
        <!-- Repeat for each portfolio in use -->
        <div>{portfolio_campaign_count} campaigns run on portfolio bid strategy <strong>'{portfolio_name}'</strong> at {target_type} {target_value}.</div>
        <!-- /Repeat -->
        <!-- If any campaigns fall back to a computed target (target_source=fallback), banner separately as unconstrained -->
        <div style="margin-top: 6px; color: #92400e;"><strong>Unconstrained:</strong> {fallback_campaigns} — no portfolio target supplied; computed efficiency floor in use. Effective Maximize Conversion Value applies only here.</div>
    </div>

    <!-- Standard diagnostic table (all modules except Performance Segmentation KW-D07) -->
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

    <!-- KW-D07 expanded sub-sections (Performance Segmentation module only) -->
    <!-- Only render these sub-sections inside the Performance Segmentation module, after the diagnostic table -->

    <!-- KW-D07 sub-section 1: Hypothesis-framed summary -->
    <!-- If core-term hypothesis is active: -->
    <div class="issue-card warning" style="margin-top: 16px;">
        <div class="issue-id" style="color: var(--color-warning);">Core-term hypothesis active</div>
        <div class="issue-title">{core_term_pct}% of UNPROFITABLE spend sits on core product terms — flagged as a structural hypothesis, not a pause candidate. See Diagnosis above.</div>
    </div>
    <!-- Core-term "do not pause" table -->
    <h4 style="font-size: 0.95rem; margin: 16px 0 8px; color: var(--color-text);">Core-term keywords (do not pause)</h4>
    <table>
        <thead>
            <tr>
                <th>Keyword</th>
                <th>Campaign</th>
                <th style="width: 80px;">Spend</th>
                <th style="width: 120px;">{primary_kpi_label}</th>
                <th style="width: 120px;">Threshold</th>
                <th>Reasoning</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each core-term UNPROFITABLE keyword -->
            <tr>
                <td>{keyword_text}</td>
                <td>{campaign_name}</td>
                <td>{spend}</td>
                <td>{primary_kpi_value}</td>
                <td>{profitability_threshold}</td>
                <td>{reasoning}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>

    <!-- KW-D07 sub-section 2: Non-core UNPROFITABLE (genuine pause candidates) -->
    <h4 style="font-size: 0.95rem; margin: 16px 0 8px; color: var(--color-text);">Non-core UNPROFITABLE (pause candidates)</h4>
    <table>
        <thead>
            <tr>
                <th>Keyword</th>
                <th>Campaign</th>
                <th style="width: 80px;">Spend</th>
                <th style="width: 120px;">{primary_kpi_label}</th>
                <th style="width: 120px;">Threshold</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat -->
            <tr>
                <td>{keyword_text}</td>
                <td>{campaign_name}</td>
                <td>{spend}</td>
                <td>{primary_kpi_value}</td>
                <td>{profitability_threshold}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>

    <!-- KW-D07 sub-section 3: PAUSE_CANDIDATE (zero primary conversions) -->
    <h4 style="font-size: 0.95rem; margin: 16px 0 8px; color: var(--color-text);">Zero-conversion pause candidates</h4>
    <table>
        <thead>
            <tr>
                <th>Keyword</th>
                <th>Campaign</th>
                <th style="width: 80px;">Spend</th>
                <th style="width: 100px;">Gate</th>
                <th>Note</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat — note core-term patience: "Core product term — x1.5 patience applied" -->
            <tr>
                <td>{keyword_text}</td>
                <td>{campaign_name}</td>
                <td>{spend}</td>
                <td>{pause_spend_threshold}</td>
                <td>{note}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>

    <!-- KW-D07 sub-section 4: OVER_TARGET (info, no pause) -->
    <h4 style="font-size: 0.95rem; margin: 16px 0 8px; color: var(--color-text);">OVER_TARGET (profitable, no pause)</h4>
    <table>
        <thead>
            <tr>
                <th>Keyword</th>
                <th>Campaign</th>
                <th style="width: 80px;">Spend</th>
                <th style="width: 120px;">{primary_kpi_label}</th>
                <th style="width: 80px;">Max</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat -->
            <tr>
                <td>{keyword_text}</td>
                <td>{campaign_name}</td>
                <td>{spend}</td>
                <td>{primary_kpi_value}</td>
                <td>{profitability_max}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>

    <!-- KW-D07 sub-section 5: Business context box -->
    <div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 16px; margin-top: 16px; font-size: 0.85rem;">
        <strong>Business context:</strong> Profitability threshold: {profitability_threshold} · Primary conversion: <code>{primary_conversion_action}</code> · Core tokens: {core_product_tokens}
        <!-- If targetFallbackMode is campaign_target_only: -->
        <div style="margin-top: 8px; padding: 6px 10px; background: #fef3c7; border-left: 3px solid var(--color-warning); border-radius: 0 4px 4px 0; color: #92400e;">
            Target fallback: campaign_target_only — keywords inherit campaign tCPA/tROAS. Verify before acting.
        </div>
    </div>

    <!-- /End KW-D07 sub-sections -->
</div>
<!-- /Repeat for each module -->

<!-- Data sufficiency notes -->
<h2>Data sufficiency notes</h2>
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 20px; margin: 16px 0;">
    <ul style="margin: 0; padding-left: 20px; font-size: 0.9rem; line-height: 1.7;">
        <!-- Repeat for each caveat (conversion lag, window length, low-conv warnings, attribution anomalies, portfolio bid strategy) -->
        <li>{caveat}</li>
        <!-- /Repeat -->
    </ul>
</div>
```

## Data Extraction Guide

Parse the keyword-audit.md file for:

1. **Header block**: Lines starting with `**Score:**`, `**Evaluation period:**`, `**Period A:**`, `**Campaigns audited:**`, `**Keywords analyzed:**`
2. **Business Context block**: Section under `## Business Context (yardstick)` — extract profitability threshold, primary/secondary KPI, core product tokens, target fallback mode
3. **Executive read**: Section under `## Executive read` — prose paragraphs (≤300 words, no bullets). Split by paragraph break, render each as a separate `<p>`. Quoted peer-report findings stay inline. Covers six slots in order: score meaning, this-week priorities, what is NOT a problem, fresh peer findings, how to read the rest, score trend
4. **Diagnosis**: Section under `## Diagnosis` — narrative paragraph, top hypothesis (name, layer, confidence, explained waste %), connecting narrative, secondary hypotheses list, fallback guidance
5. **Evidence Ladder**: Section under `## Evidence Ladder` — grouped by cascade layer (Measurement, Business, Conversion, Traffic/Creative). Each layer has a status (clear/active) and evidence bullets with IDs (M1–M4, B1–B4, C1–C2), details, and hypothesis tags (`→ H{n}`, `→ H{n} blocking`)
6. **Module Scores table**: Table under `## Module Scores` — each row has Module | Score | Grade | Key Findings
7. **Actions — segmented by cascade state**: Section under `## Actions — segmented by cascade state` with 5 sub-sections:
   - `### 🔍 Investigate first` — table: # | Action | Skill | Resolves hypothesis | What this unblocks
   - `### 🔧 Structural fix needed` — table: # | Action | Skill | Affected | Est. impact
   - `### 🔄 Recover efficiency first` — table: Step | Skill | What it addresses | Expected impact (plus summary line with keyword count and spend). The first row routes to `/search-term-auditor ngrams`
   - `### ✅ Act now (safe)` — table: # | Action | Keywords | Est. impact | Optimizer command
   - `### ⚠️ Do NOT pause` — table: Keyword | Campaign | Spend | Primary CPA / Eff. ROAS | Max | Action
8. **Module Details**: Sections named `### Module 1: Match Type Health`, `### Module 2: Performance Segmentation`, etc. — each has a diagnostic table. **Performance Segmentation** opens with a one-line **target source banner** (only when any campaign uses a portfolio bid strategy) listing each portfolio name + target (using `target_source` + `portfolio_name` from `keyword-tiers.csv`); campaigns with `target_source=fallback` are bannered separately as **unconstrained**. The module then has 5 KW-D07 sub-sections: hypothesis summary, non-core UNPROFITABLE, PAUSE_CANDIDATE, OVER_TARGET, business context box
9. **Data Sufficiency Notes**: Section under `## Data Sufficiency Notes` — free-form list of caveats (conversion lag, window length, low-conv warnings, attribution anomalies, portfolio bid strategy)

## Special Fields

- **Mode**: The audit supports partial modes (`full`, `match-type`, `performance`, `duplicates`, `hygiene`, `intent`). Display the mode below the overall score.
- **Period**: Evaluation period in days (30, 60, or 90), plus conversion lag exclusion. Display alongside mode.
- **Business Context yardstick**: Rendered at the top — profitability threshold, KPIs, core tokens, fallback mode. If `targetFallbackMode=campaign_target_only`, show a warning banner.
- **Diagnosis**: Multi-part — narrative paragraph, top hypothesis card (name, layer, confidence, explained waste %), connecting narrative, secondary hypotheses, fallback. This is the reader's biggest takeaway.
- **Evidence Ladder**: Grouped by cascade layer. Only layers with active hypotheses appear. Each bullet has an evidence ID, factual observation, and hypothesis tag. Blocking evidence gets a red badge.
- **Actions — 5 segments**: Actions are segmented by cascade state, NOT by priority. The segments are: (1) Investigate first (blocking upstream hypotheses), (2) Structural fix needed (routes to other skills), (3) Recover efficiency first (ER1–ER5 sequence before pause), (4) Act now (safe post-cascade), (5) Do NOT pause (OVER_TARGET). Only populated segments should render.
- **KW-D07 sub-sections**: Performance Segmentation module has 5 mandatory sub-sections for KW-D07: hypothesis summary, core-term do-not-pause table, non-core UNPROFITABLE table, PAUSE_CANDIDATE table, OVER_TARGET info table, and business context box. Never mix these buckets.
- **Routing column**: Investigate and Structural fix actions route to upstream skills (`/tracking-specialist`, `/strategy-specialist`, `/lp-auditor`, `/offer-auditor`) *before* `/keyword-optimizer`. Render as inline code.
- **Data sufficiency notes**: Free-form caveats about conversion lag, evaluation window, low-conversion warnings, attribution anomalies, and portfolio bid strategy limitations.

## Status-to-Class Mapping

| Status | CSS Class |
|--------|-----------|
| PASS | `pass` |
| WARN | `warn` |
| FAIL | `fail` |
| SKIP | `skip` |

## Cascade Layer Status Mapping

| Status | CSS Class | Label |
|--------|-----------|-------|
| Clear | `pass` | CLEAR |
| Active | `warn` | ACTIVE |

## Grade Color Mapping

Map score percentages to color variables:
- 90-100%: `--color-success` (green)
- 70-89%: `--color-info` (blue)
- 50-69%: `--color-warning` (amber)
- <50%: `--color-danger` (red)
