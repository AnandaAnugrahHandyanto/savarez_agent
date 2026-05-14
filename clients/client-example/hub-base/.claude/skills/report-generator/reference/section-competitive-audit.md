# Section Template: Competitive Audit

HTML section template for rendering competitive-audit.md data. Insert into `{report_body_sections}` in the base template.

## Source File

`clients/<name>/context/analysis/competitive-audit.md`

## Modules

3 modules: IS Health & Trends (CA-D01, CA-D02), Competitive Position (CA-D05, CA-D08, CA-D09), Competitive Impact (CA-D11, CA-D13)

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
        Period: {evaluation_period} days · Conversion lag: {conversion_lag}d
    </div>
</div>

<!-- Executive Read -->
<h2>Executive read</h2>
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 24px; margin: 16px 0;">
    <!-- Repeat for each paragraph (≤300 words total, prose only — no bullets). Quoted peer-report findings stay inline — competitive findings often get rewritten by a fresh QS / bidding / budget peer -->
    <p style="font-size: 1rem; line-height: 1.7; margin: 0 0 12px;">{executive_paragraph}</p>
    <!-- /Repeat -->
</div>

<!-- Strategic Verdict -->
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 24px; margin: 24px 0;">
    <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px; color: var(--color-text-light); margin-bottom: 8px;">Strategic verdict</div>
    <div style="font-size: 1.2rem; font-weight: 700; margin-bottom: 12px; color: var(--color-{verdict_color});">{strategic_verdict}</div>
    <p style="font-size: 1rem; line-height: 1.7; margin: 0;">{diagnosis_narrative}</p>
</div>

<!-- Business Economics Context -->
<h2>Business economics context</h2>
<div style="margin: 16px 0;">
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px 24px; font-size: 0.9rem; margin-bottom: 16px;">
        <div><strong>Primary KPI:</strong> {primary_kpi}</div>
        <div><strong>Target:</strong> {target_value}</div>
        <div><strong>Break-even:</strong> {break_even_value}</div>
        <div><strong>Bidding strategy:</strong> {bidding_strategy}</div>
    </div>

    <!-- Campaign economics table -->
    <h3 style="font-size: 0.95rem; margin: 16px 0 8px;">Campaign-level economics</h3>
    <table>
        <thead>
            <tr>
                <th>Campaign</th>
                <th style="width: 60px;">Type</th>
                <th style="width: 80px;">{primary_kpi_label}</th>
                <th style="width: 80px;">Target</th>
                <th style="width: 100px;">Headroom</th>
                <th style="width: 60px;">CVR</th>
                <th style="width: 80px;">Avg CPC</th>
                <th style="width: 120px;">Can afford more IS?</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each campaign -->
            <tr>
                <td>{campaign_name}</td>
                <td>{campaign_type}</td>
                <td>{primary_kpi_value}</td>
                <td>{target}</td>
                <td style="color: var(--color-{headroom_color});">{headroom}</td>
                <td>{cvr}</td>
                <td>{avg_cpc}</td>
                <td>{can_afford_more_is}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>

    <!-- Keyword economics table (top 20) -->
    <h3 style="font-size: 0.95rem; margin: 16px 0 8px;">Keyword-level economics (top 20)</h3>
    <table>
        <thead>
            <tr>
                <th>Keyword</th>
                <th style="width: 60px;">{primary_kpi_label}</th>
                <th style="width: 60px;">CVR</th>
                <th style="width: 60px;">CTR</th>
                <th style="width: 80px;">IS</th>
                <th style="width: 100px;">Economic status</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each keyword -->
            <tr>
                <td>{keyword_text}</td>
                <td>{primary_kpi_value}</td>
                <td>{cvr}</td>
                <td>{ctr}</td>
                <td>{impression_share}</td>
                <td style="color: var(--color-{economic_color});">{economic_status}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Evidence Ladder -->
<h2>Evidence ladder</h2>
<div style="margin: 16px 0;">
    <!-- Repeat for each active cascade layer (Data Validation, Business Economics, QS & Rank Diagnosis, Strategic Assessment, Tactical Routing) -->
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
    <!-- Repeat for each module: IS Health & Trends, Competitive Position, Competitive Impact -->
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

<!-- IS Trend Dashboard -->
<h2>IS trend dashboard</h2>
<table>
    <thead>
        <tr>
            <th>Campaign</th>
            <th style="width: 60px;">Type</th>
            <th style="width: 80px;">IS start</th>
            <th style="width: 80px;">IS end</th>
            <th style="width: 80px;">Change</th>
            <th style="width: 80px;">Trajectory</th>
            <th style="width: 80px;">Status</th>
        </tr>
    </thead>
    <tbody>
        <!-- Repeat for each campaign -->
        <tr>
            <td>{campaign_name}</td>
            <td>{campaign_type}</td>
            <td>{is_start}%</td>
            <td>{is_end}%</td>
            <td style="color: var(--color-{change_color});">{is_change}</td>
            <td>{trajectory}</td>
            <td><span class="status-pill {status_class}">{status}</span></td>
        </tr>
        <!-- /Repeat -->
    </tbody>
</table>

<!-- IS Loss Decomposition -->
<h2>IS loss decomposition</h2>
<table>
    <thead>
        <tr>
            <th>Campaign</th>
            <th style="width: 100px;">Total IS loss</th>
            <th style="width: 100px;">Lost to budget</th>
            <th style="width: 100px;">Lost to rank</th>
            <th style="width: 80px;">Primary cause</th>
            <th style="width: 120px;">Can afford more IS?</th>
            <th style="width: 80px;">Status</th>
        </tr>
    </thead>
    <tbody>
        <!-- Repeat for each campaign -->
        <tr>
            <td>{campaign_name}</td>
            <td>{total_is_loss}%</td>
            <td>{lost_budget}%</td>
            <td>{lost_rank}%</td>
            <td>{primary_cause}</td>
            <td style="color: var(--color-{afford_color});">{can_afford}</td>
            <td><span class="status-pill {status_class}">{status}</span></td>
        </tr>
        <!-- /Repeat -->
    </tbody>
</table>

<!-- Top-of-Page Position Analysis (Search campaigns only) -->
<h2>Top-of-page position analysis</h2>
<table>
    <thead>
        <tr>
            <th>Campaign</th>
            <th style="width: 80px;">Abs top IS</th>
            <th style="width: 80px;">Top IS</th>
            <th style="width: 80px;">Abs top trend</th>
            <th style="width: 80px;">Top trend</th>
            <th style="width: 80px;">Status</th>
        </tr>
    </thead>
    <tbody>
        <!-- Repeat for each Search campaign -->
        <tr>
            <td>{campaign_name}</td>
            <td>{abs_top_is}%</td>
            <td>{top_is}%</td>
            <td style="color: var(--color-{abs_trend_color});">{abs_top_trend}</td>
            <td style="color: var(--color-{top_trend_color});">{top_trend}</td>
            <td><span class="status-pill {status_class}">{status}</span></td>
        </tr>
        <!-- /Repeat -->
    </tbody>
</table>

<!-- Keyword Competitive Pressure (Top 20) -->
<h2>Keyword competitive pressure</h2>
<table>
    <thead>
        <tr>
            <th>Keyword</th>
            <th style="width: 60px;">IS</th>
            <th style="width: 70px;">IS lost rank</th>
            <th style="width: 70px;">IS lost budget</th>
            <th style="width: 40px;">QS</th>
            <th style="width: 80px;">QS driver</th>
            <th style="width: 80px;">{primary_kpi_label}</th>
            <th style="width: 100px;">Economic status</th>
            <th style="width: 80px;">Flags</th>
        </tr>
    </thead>
    <tbody>
        <!-- Repeat for each keyword -->
        <tr>
            <td>{keyword_text}</td>
            <td>{impression_share}%</td>
            <td>{is_lost_rank}%</td>
            <td>{is_lost_budget}%</td>
            <td>{quality_score}</td>
            <td>{qs_driver}</td>
            <td>{primary_kpi_value}</td>
            <td style="color: var(--color-{economic_color});">{economic_status}</td>
            <td>{flags}</td>
        </tr>
        <!-- /Repeat -->
    </tbody>
</table>

<!-- Shopping Ad Group Breakdown (conditional) -->
<!-- Only render if Shopping campaigns with 2+ ad groups exist -->
<h2>Shopping ad group breakdown</h2>
<table>
    <thead>
        <tr>
            <th>Campaign</th>
            <th>Ad group</th>
            <th style="width: 60px;">IS</th>
            <th style="width: 80px;">IS trend</th>
            <th style="width: 80px;">IS change</th>
            <th style="width: 80px;">Status</th>
        </tr>
    </thead>
    <tbody>
        <!-- Repeat for each Shopping ad group -->
        <tr>
            <td>{campaign_name}</td>
            <td>{ad_group_name}</td>
            <td>{impression_share}%</td>
            <td>{is_trend}</td>
            <td style="color: var(--color-{change_color});">{is_change}</td>
            <td><span class="status-pill {status_class}">{status}</span></td>
        </tr>
        <!-- /Repeat -->
    </tbody>
</table>

<!-- CPC-Competition Correlation -->
<h2>CPC-competition correlation</h2>
<table>
    <thead>
        <tr>
            <th>Campaign</th>
            <th style="width: 80px;">CPC trend</th>
            <th style="width: 80px;">IS trend</th>
            <th style="width: 80px;">Correlation</th>
            <th style="width: 80px;">Status</th>
            <th>Analysis</th>
        </tr>
    </thead>
    <tbody>
        <!-- Repeat for each campaign -->
        <tr>
            <td>{campaign_name}</td>
            <td style="color: var(--color-{cpc_color});">{cpc_trend}</td>
            <td style="color: var(--color-{is_color});">{is_trend}</td>
            <td>{correlation}</td>
            <td><span class="status-pill {status_class}">{status}</span></td>
            <td>{analysis}</td>
        </tr>
        <!-- /Repeat -->
    </tbody>
</table>
<!-- If branded CPC pressure detected (SA2): -->
<div class="issue-card warning" style="margin-top: 12px;">
    <div class="issue-id" style="color: var(--color-warning);">Branded competitive entry</div>
    <div class="issue-title">{branded_entry_analysis}</div>
</div>

<!-- KPI Impact Estimate -->
<h2>KPI impact estimate</h2>
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 20px; margin: 16px 0;">
    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin-bottom: 16px;">
        <div style="padding: 12px 16px; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
            <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase; letter-spacing: 0.5px;">Estimated lost conversions</div>
            <div style="font-weight: 700; font-size: 1.2rem; margin-top: 4px;">{lost_conversions}</div>
        </div>
        <div style="padding: 12px 16px; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
            <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase; letter-spacing: 0.5px;">Estimated lost value</div>
            <div style="font-weight: 700; font-size: 1.2rem; margin-top: 4px;">{lost_value}</div>
        </div>
        <div style="padding: 12px 16px; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
            <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase; letter-spacing: 0.5px;">Recovery {primary_kpi_label}</div>
            <div style="font-weight: 700; font-size: 1.2rem; margin-top: 4px; color: var(--color-{recovery_color});">{recovery_kpi_value}</div>
            <div style="font-size: 0.8rem; color: var(--color-text-light);">vs target {target_value}</div>
        </div>
    </div>
    <p style="font-size: 0.9rem; color: var(--color-text-light); margin: 0; line-height: 1.6;">
        {kpi_impact_narrative}
    </p>
</div>

<!-- Skipped Diagnostics -->
<h2>Skipped diagnostics</h2>
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 16px; margin: 16px 0; font-size: 0.9rem;">
    <ul style="margin: 0; padding-left: 20px; line-height: 1.7;">
        <!-- Always includes CA-D03, CA-D04, CA-D06, CA-D07, CA-D10, CA-D12 -->
        <!-- Repeat for each skipped diagnostic -->
        <li><strong>{diagnostic_id}</strong> — {diagnostic_name}: {skip_reason}</li>
        <!-- /Repeat -->
    </ul>
</div>

<!-- Competitor Ad Copy Insights (conditional) -->
<!-- Only render if /competitor-ads data exists -->
<h2>Competitor ad copy insights</h2>
<div style="margin: 16px 0;">
    {competitor_insights_content}
</div>

<!-- Actions — segmented by cascade state -->
<h2>Actions</h2>

<!-- Section 1: Investigate first -->
<!-- Only render if Data Validation or Business Economics hypotheses are blocking -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#128269;</span>
        <h3 style="margin: 0; color: var(--color-danger);">Investigate first</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— blocking, resolve before tactical changes</span>
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
            <!-- Repeat for each investigation -->
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

<!-- Section 2: Fix economics first -->
<!-- Only render if efficiency exceeds target or conversion path needs improvement -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#128295;</span>
        <h3 style="margin: 0; color: var(--color-warning);">Fix economics first</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— improve conversion path before competing for more traffic</span>
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
            <!-- Repeat for each economics fix -->
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

<!-- Section 3: Compete where viable -->
<!-- Only render if some campaigns have economic headroom for IS recovery -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#9989;</span>
        <h3 style="margin: 0; color: var(--color-success);">Compete where viable</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— economics support IS recovery in these areas</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 40px;">#</th>
                <th>Action</th>
                <th style="width: 140px;">Skill</th>
                <th>Campaign(s)</th>
                <th>Est. impact</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each viable competitive action -->
            <tr>
                <td>{step_number}</td>
                <td>{action_description}</td>
                <td><code>{skill_command}</code></td>
                <td>{campaigns}</td>
                <td>{estimated_impact}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 4: Strategic discussion -->
<!-- Only render if structural challenges or market viability issues detected -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#128172;</span>
        <h3 style="margin: 0; color: var(--color-info);">Strategic discussion</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— needs business-level decision, not tactical optimization</span>
    </div>
    <div style="border-left: 3px solid var(--color-info); padding: 12px 16px; font-size: 0.9rem; line-height: 1.6;">
        {strategic_discussion_content}
    </div>
</div>

<!-- Section 5: Monitor -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#128065;</span>
        <h3 style="margin: 0; color: var(--color-text-light);">Monitor</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— no action needed, track for changes</span>
    </div>
    <table>
        <thead>
            <tr>
                <th>What to watch</th>
                <th style="width: 120px;">Current value</th>
                <th style="width: 120px;">Alert threshold</th>
                <th style="width: 120px;">Re-audit trigger</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each monitor item -->
            <tr>
                <td>{watch_item}</td>
                <td>{current_value}</td>
                <td>{alert_threshold}</td>
                <td>{reaudit_trigger}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Module Detail Sections -->
<!-- Repeat for each module: IS Health & Trends, Competitive Position, Competitive Impact -->
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
```

## Data Extraction Guide

Parse the competitive-audit.md file for:

1. **Header block**: Lines starting with `**Score:**`, `**Grade:**`, `**Period:**`, `**Campaigns:**`, `**Keywords:**`, `**Strategic verdict:**`
2. **Executive read**: Section under `## Executive read` — prose paragraphs (≤300 words, no bullets). Split by paragraph break, render each as a separate `<p>`. Quoted peer-report findings stay inline — competitive findings are typically *explainers*, so a fresh QS / bidding / budget peer often rewrites the diagnosis. Covers six slots in order: score meaning, this-week priorities, what is NOT a problem, fresh peer findings, how to read the rest, score trend
3. **Diagnosis**: Section under `## Diagnosis` — strategic verdict (one of: Compete aggressively, Fix economics first, Selective competition, Structural challenge), followed by 1-2 paragraph narrative connecting IS data to business economics
4. **Business Economics Context**: Section under `## Business Economics Context` — two tables: campaign-level economics (campaign, type, CPA/ROAS, target, headroom, CVR, avg CPC, can-afford-more-IS) and keyword-level economics (keyword, CPA/ROAS, CVR, CTR, IS, economic status)
5. **Evidence Ladder**: Section under `## Evidence Ladder` — grouped by cascade layer (Data Validation, Business Economics, QS & Rank Diagnosis, Strategic Assessment). Each layer has a status and evidence bullets with IDs (DV1-DV3, BE1-BE4, QS/RD items, SA1-SA3), details, and hypothesis tags
6. **Module Scores table**: Table under `## Module Scores` — each row has Module | Score | Grade | Key Finding
7. **IS Trend Dashboard**: Section under `## IS Trend Dashboard` — campaign-level trajectory table with IS start, IS end, change, trajectory, status
8. **IS Loss Decomposition**: Section under `## IS Loss Decomposition` — per-campaign breakdown of budget vs rank loss with "Can Afford More IS?" column
9. **Top-of-Page Position Analysis**: Section under `## Top-of-Page Position Analysis` — Search campaigns only, abs-top IS and top IS with trends
10. **Keyword Competitive Pressure**: Section under `## Keyword Competitive Pressure` — top 20 keywords with IS metrics, QS, QS driver, economic status, and flags
11. **Shopping Ad Group Breakdown**: Conditional section — only present if Shopping campaigns with 2+ ad groups exist. Per-ad-group IS and trends
12. **CPC-Competition Correlation**: Section under `## CPC-Competition Correlation` — per-campaign CPC vs IS correlation analysis, plus SA2 branded entry response if applicable
13. **KPI Impact Estimate**: Section under `## KPI Impact Estimate` — metric tree with lost conversions, lost value, recovery CPA/ROAS vs target
14. **Skipped Diagnostics**: Section under `## Skipped Diagnostics` — list of CA-D03, CA-D04, CA-D06, CA-D07, CA-D10, CA-D12 plus conditionally skipped checks
15. **Competitor Ad Copy Insights**: Conditional section — only present if `/competitor-ads` data exists
16. **Actions — segmented by cascade state**: Section under `## Actions` with 5 sub-sections:
    - `### Investigate first` — blocking upstream hypotheses
    - `### Fix economics first` — efficiency/conversion path improvements
    - `### Compete where viable` — IS recovery where economics support it
    - `### Strategic discussion` — business-level decisions needed
    - `### Monitor` — watch items with thresholds

## Special Fields

- **Strategic Verdict**: One of 4 values — "Compete aggressively", "Fix economics first", "Selective competition", "Structural challenge". This is the lead of the report and drives the action segmentation. Color mapping: Compete aggressively → `--color-success`, Selective competition → `--color-info`, Fix economics first → `--color-warning`, Structural challenge → `--color-danger`.
- **Can Afford More IS?**: Per-campaign economic assessment in IS Loss Decomposition and Campaign Economics tables. Values: "Yes — headroom available", "No — efficiency exceeds target", "Marginal — near break-even".
- **QS Driver**: In the Keyword Competitive Pressure table, indicates whether rank loss is QS-driven or bid-driven. Values: "QS-driven (ad relevance)", "QS-driven (LP experience)", "QS-driven (expected CTR)", "Bid-driven", "Unknown (null QS)".
- **Recovery KPI**: In the KPI Impact Estimate, shows the implied CPA/ROAS to recover lost IS — contrasts with the target to show whether recovery is economically viable.
- **Actions — 5 segments**: Actions are segmented by cascade state matching the synthesis playbook: (1) Investigate first (blocking), (2) Fix economics first (conversion path), (3) Compete where viable (IS recovery), (4) Strategic discussion (business decisions), (5) Monitor (watch items). Only populated segments should render.
- **Conditional sections**: Shopping Ad Group Breakdown only renders if Shopping campaigns with 2+ ad groups exist. Competitor Ad Copy Insights only renders if `/competitor-ads` data was available. Branded competitive entry card only renders if SA2 detected branded CPC pressure.
- **CA-D09 point redistribution**: When CA-D09 is SKIP, note in module detail that its 8 points redistributed to CA-D05 (+4) and CA-D08 (+4).

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
