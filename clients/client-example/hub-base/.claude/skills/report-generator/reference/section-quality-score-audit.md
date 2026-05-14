# Section Template: Quality Score Audit

HTML section template for rendering quality-score-audit.md data. Insert into `{report_body_sections}` in the base template.

## Source File

`clients/<name>/context/analysis/quality-score-audit.md`

## Modules

4 modules: QS Distribution (QS-D01–D06), Component Breakdown (QS-D07–D10), Historical Trends (QS-D11–D14), Competitive Context (QS-D15–D16)

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
        Period: {evaluation_period}d · History: {history_period}d · Keywords: {keywords_analyzed} (flagged {keywords_flagged})
    </div>
</div>

<!-- Executive Read -->
<h2>Executive read</h2>
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 24px; margin: 16px 0;">
    <!-- Repeat for each paragraph (≤300 words total, prose only — no bullets). Quoted peer-report findings stay inline -->
    <p style="font-size: 1rem; line-height: 1.7; margin: 0 0 12px;">{executive_paragraph}</p>
    <!-- /Repeat -->
</div>

<!-- Diagnosis — specialist-to-client narrative; render the four sub-sections verbatim from the source markdown -->
<h2>Diagnosis</h2>
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 24px; margin: 16px 0;">
    <div style="margin-bottom: 16px;">
        <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">In one line</div>
        <p style="font-size: 1.05rem; line-height: 1.6; margin: 0; font-weight: 600;">{diagnosis_in_one_line}</p>
    </div>
    <div style="margin-bottom: 16px;">
        <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">What's happening</div>
        <p style="font-size: 0.95rem; line-height: 1.7; margin: 0;">{diagnosis_whats_happening}</p>
    </div>
    <div style="margin-bottom: 16px;">
        <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Where it hurts most</div>
        <p style="font-size: 0.95rem; line-height: 1.7; margin: 0;">{diagnosis_where_it_hurts}</p>
    </div>
    <div>
        <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">What to do first</div>
        <p style="font-size: 0.95rem; line-height: 1.7; margin: 0;">{diagnosis_what_to_do_first}</p>
    </div>

    <!-- If Smart Bidding dampened: -->
    <div style="margin-top: 16px; padding: 8px 12px; background: #fef3c7; border-left: 3px solid var(--color-warning); border-radius: 0 4px 4px 0; font-size: 0.85rem; color: #92400e;">
        QS still feeds Ad Rank — CPC impact dampened by Smart Bidding, not eliminated.
    </div>
</div>

<!-- For the record (technical summary) — collapsed-style footer with machine-readable hypothesis data -->
<details style="margin: 8px 0 16px; padding: 12px 16px; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--border-radius); font-size: 0.85rem;">
    <summary style="cursor: pointer; font-weight: 600; color: var(--color-text-light); text-transform: uppercase; letter-spacing: 0.5px; font-size: 0.75rem;">For the record (technical summary)</summary>
    <ul style="margin: 12px 0 0; padding-left: 20px; line-height: 1.7;">
        <li><strong>Top hypothesis ({top_hypothesis_layer} layer):</strong> {top_hypothesis_name}</li>
        <li><strong>Confidence:</strong> {confidence}</li>
        <li><strong>Explains approximately:</strong> {explained_premium_pct}% of QS-related CPC premium</li>
        <li><strong>Blocking relationships:</strong> {blocking_relationships}</li>
        <li><strong>Secondary hypotheses:</strong>
            <ul style="margin: 4px 0 0; padding-left: 20px;">
                <!-- Repeat for each secondary hypothesis -->
                <li>{secondary_hypothesis}</li>
                <!-- /Repeat -->
            </ul>
        </li>
    </ul>
</details>

<!-- Classifier Results -->
<h2>Keyword classifier</h2>
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 16px; margin: 16px 0;">
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; font-size: 0.9rem;">
        <div><strong>BRANDED:</strong> {branded_count}</div>
        <div><strong>COMPETITOR:</strong> {competitor_count}</div>
        <div><strong>INFORMATIONAL:</strong> {informational_count}</div>
        <div><strong>GENERIC:</strong> {generic_count}</div>
    </div>
    <div style="margin-top: 10px; font-size: 0.85rem; color: var(--color-text-light); line-height: 1.6;">
        COMPETITOR AR Below Avg is structural (conquesting) — not treated as a fix candidate.
        INFORMATIONAL keywords route to <code>/keyword-auditor</code> instead of QS fixes.
    </div>
</div>

<!-- Evidence Ladder -->
<h2>Evidence ladder</h2>
<div style="margin: 16px 0;">
    <!-- Repeat for each active cascade layer (Outer: bidding-mode; Inner: AR, ECTR, LP) -->
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
    <!-- Repeat for each module: QS Distribution (20 pts), Component Breakdown (45 pts), Historical Trends (15 pts), Competitive Context (20 pts) -->
    <div class="score-card">
        <div class="module-name">{module_name}</div>
        <div class="module-score" style="color: var(--color-{grade_color});">{module_score}/{module_max}</div>
        <div class="module-grade">{module_grade}</div>
        <div style="margin-top: 8px;">
            <div class="progress-bar">
                <div class="fill {module_grade_class}" style="width: {module_pct}%"></div>
            </div>
        </div>
        <div style="font-size: 0.8rem; color: var(--color-text-light); margin-top: 8px;">
            {key_finding}
        </div>
    </div>
    <!-- /Repeat -->
</div>

<!-- QS Distribution Summary -->
<h2>QS distribution</h2>
<div style="margin: 16px 0;">
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px;">
        <div style="padding: 12px 16px; background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
            <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase;">Account-weighted QS</div>
            <div style="font-weight: 700; font-size: 1.4rem; margin-top: 4px;">{account_weighted_qs}</div>
        </div>
        <div style="padding: 12px 16px; background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
            <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase;">Low-QS spend share</div>
            <div style="font-weight: 700; font-size: 1.4rem; margin-top: 4px; color: var(--color-{low_qs_color});">{low_qs_spend_pct}%</div>
        </div>
        <div style="padding: 12px 16px; background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
            <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase;">High-spend / low-QS kw</div>
            <div style="font-weight: 700; font-size: 1.4rem; margin-top: 4px;">{high_spend_low_qs_count}</div>
        </div>
        <div style="padding: 12px 16px; background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
            <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase;">Null-QS keywords</div>
            <div style="font-weight: 700; font-size: 1.4rem; margin-top: 4px;">{null_qs_count} ({null_qs_pct}%)</div>
        </div>
    </div>

    <h3 style="font-size: 0.95rem; margin: 16px 0 8px;">QS by campaign</h3>
    <table>
        <thead>
            <tr>
                <th>Campaign</th>
                <th style="width: 70px;">Type</th>
                <th style="width: 70px;">Bidding</th>
                <th style="width: 80px;">Weighted QS</th>
                <th style="width: 80px;">Low-QS %</th>
                <th style="width: 80px;">Keywords</th>
                <th style="width: 80px;">Status</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each campaign -->
            <tr>
                <td>{campaign_name}</td>
                <td>{campaign_type}</td>
                <td>{bidding_mode}</td>
                <td>{weighted_qs}</td>
                <td style="color: var(--color-{low_qs_color});">{low_qs_pct}%</td>
                <td>{keyword_count}</td>
                <td><span class="status-pill {status_class}">{status}</span></td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Component Breakdown -->
<h2>Component breakdown</h2>
<div style="margin: 16px 0;">
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px;">
        <div style="padding: 12px 16px; background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
            <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase;">Ad Relevance Below Avg</div>
            <div style="font-weight: 700; font-size: 1.2rem; margin-top: 4px; color: var(--color-{ar_color});">{ar_below_avg_count} kw ({ar_below_avg_pct}%)</div>
        </div>
        <div style="padding: 12px 16px; background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
            <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase;">Expected CTR Below Avg</div>
            <div style="font-weight: 700; font-size: 1.2rem; margin-top: 4px; color: var(--color-{ectr_color});">{ectr_below_avg_count} kw ({ectr_below_avg_pct}%)</div>
        </div>
        <div style="padding: 12px 16px; background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
            <div style="font-size: 0.8rem; color: var(--color-text-light); text-transform: uppercase;">LP Experience Below Avg</div>
            <div style="font-weight: 700; font-size: 1.2rem; margin-top: 4px; color: var(--color-{lp_color});">{lp_below_avg_count} kw ({lp_below_avg_pct}%)</div>
        </div>
    </div>
    <div style="font-size: 0.9rem; color: var(--color-text-light); padding: 10px 14px; background: var(--color-bg-alt); border-left: 3px solid var(--color-primary); border-radius: 0 4px 4px 0;">
        <strong>Dominant limiting component:</strong> {dominant_component}. {dominant_explanation}
    </div>
</div>

<!-- QS-D17 Customizer Integrity (INFO-only — does not affect score) -->
<!-- Always render. PASS/INFO when no broken setups; WARN block(s) when present. -->
<h2>Customizer integrity <span style="font-size: 0.75rem; padding: 2px 8px; background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: 10px; color: var(--color-text-light); margin-left: 8px; vertical-align: middle;">QS-D17 · INFO-only</span></h2>
<div style="margin: 16px 0;">
    <p style="font-size: 0.9rem; color: var(--color-text-light); margin: 0 0 12px; line-height: 1.6;">
        Checks whether <code>{CUSTOMIZER.&lt;name&gt;}</code> references in RSAs actually resolve to a bound value. Broken or unbound customizers cause Google to render the inline <code>:default</code> every impression — a frequent root cause of AR Below Avg ratings. INFO-only: does not affect the QS score.
    </p>

    <!-- If integrity_status is OK / NO_CUSTOMIZERS for all AGs -->
    <div style="padding: 12px 16px; background: var(--color-bg-alt); border-left: 3px solid var(--color-success); border-radius: 0 4px 4px 0; font-size: 0.9rem;">
        <span class="status-pill pass" style="font-size: 0.75rem; margin-right: 8px;">PASS</span>
        No unresolved customizer references detected. {ok_keyword_count} AGs use keyword-level customizers, {ok_ag_count} use AG-level, {ok_campaign_count} use campaign- or customer-level, {no_customizer_count} use no customizers.
    </div>

    <!-- If any AG has integrity_status = BROKEN -->
    <h3 style="font-size: 0.95rem; margin: 20px 0 8px;">
        <span class="status-pill warn" style="font-size: 0.75rem; margin-right: 8px;">WARN</span>
        BROKEN — referenced attribute not defined on the account
    </h3>
    <table>
        <thead>
            <tr>
                <th>Ad group</th>
                <th>Campaign</th>
                <th>Missing attributes</th>
                <th style="width: 100px;">RSAs affected</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each BROKEN AG -->
            <tr>
                <td>{ad_group_name}</td>
                <td>{campaign_name}</td>
                <td><code>{missing_attributes}</code></td>
                <td>{rsas_affected}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>

    <!-- If any AG has integrity_status = EFFECTIVELY_STATIC -->
    <h3 style="font-size: 0.95rem; margin: 20px 0 8px;">
        <span class="status-pill warn" style="font-size: 0.75rem; margin-right: 8px;">WARN</span>
        EFFECTIVELY_STATIC — attribute defined but no binding (renders default every time)
    </h3>
    <table>
        <thead>
            <tr>
                <th>Ad group</th>
                <th>Campaign</th>
                <th>Static attributes</th>
                <th>Effective resolution</th>
                <th style="width: 100px;">RSAs affected</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each EFFECTIVELY_STATIC AG -->
            <tr>
                <td>{ad_group_name}</td>
                <td>{campaign_name}</td>
                <td><code>{static_attributes}</code></td>
                <td><code>{effective_resolution}</code></td>
                <td>{rsas_affected}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>

    <!-- How to fix block — render whenever any BROKEN or EFFECTIVELY_STATIC row is present -->
    <div style="margin-top: 16px; padding: 12px 16px; background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); font-size: 0.9rem; line-height: 1.7;">
        <strong>How to fix</strong>
        <ul style="margin: 8px 0 0; padding-left: 20px;">
            <li><strong>BROKEN</strong> — create the missing <code>customizer_attribute</code>, or remove the <code>{CUSTOMIZER.&lt;name&gt;}</code> reference from the RSA.</li>
            <li><strong>EFFECTIVELY_STATIC</strong> — add a binding at the appropriate hierarchy level (keyword / AG / campaign / customer), or remove the reference and bake the intended value into the headline.</li>
        </ul>
        <p style="margin: 10px 0 0; color: var(--color-text-light);">Re-audit after fixing to confirm AR recovery.</p>
    </div>
</div>

<!-- Historical Trends (conditional — skip if fresh account) -->
<!-- Only render if M3 ran (history ≥ 60d) -->
<h2>Historical trends</h2>
<table>
    <thead>
        <tr>
            <th style="width: 180px;">Metric</th>
            <th style="width: 80px;">Start</th>
            <th style="width: 80px;">End</th>
            <th style="width: 80px;">Slope</th>
            <th style="width: 100px;">Trajectory</th>
            <th>Notes</th>
        </tr>
    </thead>
    <tbody>
        <!-- Repeat for each tracked metric (account QS, AR, ECTR, LP) -->
        <tr>
            <td>{metric_name}</td>
            <td>{start_value}</td>
            <td>{end_value}</td>
            <td style="color: var(--color-{slope_color});">{slope}</td>
            <td>{trajectory}</td>
            <td>{notes}</td>
        </tr>
        <!-- /Repeat -->
    </tbody>
</table>

<!-- Competitive Context -->
<h2>Competitive context</h2>
<table>
    <thead>
        <tr>
            <th>Campaign</th>
            <th style="width: 80px;">Lost IS (rank)</th>
            <th style="width: 80px;">Weighted QS</th>
            <th style="width: 100px;">CPC premium vs QS≥7</th>
            <th style="width: 100px;">QS driver</th>
            <th style="width: 80px;">Status</th>
        </tr>
    </thead>
    <tbody>
        <!-- Repeat for each campaign with competitive pressure -->
        <tr>
            <td>{campaign_name}</td>
            <td>{lost_is_rank}%</td>
            <td>{weighted_qs}</td>
            <td style="color: var(--color-{premium_color});">{cpc_premium}</td>
            <td>{qs_driver}</td>
            <td><span class="status-pill {status_class}">{status}</span></td>
        </tr>
        <!-- /Repeat -->
    </tbody>
</table>

<!-- Actions — segmented by cascade state -->
<h2>Actions</h2>

<!-- Section 1: Investigate first (blocking) -->
<!-- Only render if outer-cascade or data-blocking hypotheses are active -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#128269;</span>
        <h3 style="margin: 0; color: var(--color-danger);">Investigate first</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— blocking, resolve before component fixes</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 40px;">#</th>
                <th>Action</th>
                <th style="width: 160px;">Skill</th>
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

<!-- Section 2: Branded-campaign escalation -->
<!-- Only render if any BRAND_LOW_QS flagged keywords exist -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#128681;</span>
        <h3 style="margin: 0; color: var(--color-warning);">Branded-campaign escalation</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— brand keywords with low QS usually indicate tracking or LP issues</span>
    </div>
    <table>
        <thead>
            <tr>
                <th>Ad group</th>
                <th style="width: 100px;">Keywords</th>
                <th style="width: 120px;">Impressions</th>
                <th style="width: 160px;">First skill to run</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each branded escalation row -->
            <tr>
                <td>{ad_group_name}</td>
                <td>{keyword_count}</td>
                <td>{impressions}</td>
                <td><code>{skill_command}</code></td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 3: Handoff Queue — Ad Relevance -->
<!-- Only render if AR queue is non-empty -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#128272;</span>
        <h3 style="margin: 0; color: var(--color-info);">Handoff queue — Ad Relevance</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— route to <code>/rsa-maker</code> (AR fixes block ECTR work)</span>
    </div>
    <table>
        <thead>
            <tr>
                <th>Ad group</th>
                <th>Campaign</th>
                <th style="width: 110px;">Keywords below avg</th>
                <th style="width: 110px;">Impressions</th>
                <th style="width: 100px;">Class</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each AR queue entry (sorted by impressions desc) -->
            <tr>
                <td>{ad_group_name}</td>
                <td>{campaign_name}</td>
                <td>{keywords_below_avg}</td>
                <td>{impressions}</td>
                <td>{keyword_class}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 3b: Pending handoff — keyword-restructurer (Headline Test failures) -->
<!-- Only render if any AGs failed the Headline Test (structural-split brief present) -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#128295;</span>
        <h3 style="margin: 0; color: var(--color-warning);">Pending handoff — Ad group restructure</h3>
        <span class="status-pill warn" style="font-size: 0.75rem;">PENDING — SKILL NOT YET BUILT</span>
    </div>
    <p style="font-size: 0.9rem; color: var(--color-text-light); margin: 0 0 10px;">
        These ad groups failed the Headline Test — the keywords inside them cover topics too different for any single ad to address well. New copy alone won't fix AR; the AGs need to be split first. The <code style="opacity: 0.7;">keyword-restructurer</code> skill is not built yet, so each row carries a structural-split brief instead of an active route.
    </p>
    <table>
        <thead>
            <tr>
                <th>Ad group</th>
                <th>Campaign</th>
                <th style="width: 110px;">Keywords</th>
                <th>Proposed theme split</th>
                <th>Keywords to move</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each Headline-Test-failed AG -->
            <tr>
                <td>{ad_group_name}</td>
                <td>{campaign_name}</td>
                <td>{keyword_count}</td>
                <td>{proposed_theme_split}</td>
                <td>{keywords_to_move}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 4: Handoff Queue — LP Experience (runs in parallel with AR) -->
<!-- Only render if LP queue is non-empty -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#127760;</span>
        <h3 style="margin: 0; color: var(--color-info);">Handoff queue — LP Experience</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— route to <code>/lp-auditor</code> &rarr; <code>/lp-optimize</code> (independent of AR/ECTR)</span>
    </div>
    <table>
        <thead>
            <tr>
                <th>Landing page URL</th>
                <th style="width: 110px;">Keywords</th>
                <th style="width: 110px;">Impressions</th>
                <th style="width: 110px;">Ad groups</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each LP queue entry (grouped by final_url) -->
            <tr>
                <td><code>{landing_page_url}</code></td>
                <td>{keyword_count}</td>
                <td>{impressions}</td>
                <td>{ad_group_count}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 5: Handoff Queue — Expected CTR (only after AR resolved) -->
<!-- Only render if ECTR queue is non-empty -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#128200;</span>
        <h3 style="margin: 0; color: var(--color-info);">Handoff queue — Expected CTR</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— route to <code>/offer-maker</code> + <code>/rsa-maker</code> after AR layer is clear</span>
    </div>
    <table>
        <thead>
            <tr>
                <th>Ad group</th>
                <th>Campaign</th>
                <th style="width: 110px;">Keywords below avg</th>
                <th style="width: 110px;">Impressions</th>
                <th style="width: 100px;">Class</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each ECTR queue entry -->
            <tr>
                <td>{ad_group_name}</td>
                <td>{campaign_name}</td>
                <td>{keywords_below_avg}</td>
                <td>{impressions}</td>
                <td>{keyword_class}</td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Section 6: Do NOT run QS fixes -->
<!-- Only render if COMPETITOR or INFORMATIONAL keywords exist -->
<div style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <span style="font-size: 1.2rem;">&#9888;&#65039;</span>
        <h3 style="margin: 0; color: var(--color-warning);">Do NOT run QS fixes on these</h3>
        <span style="font-size: 0.8rem; color: var(--color-text-light);">— structural, not a QS problem</span>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 140px;">Class</th>
                <th style="width: 100px;">Keywords</th>
                <th>Reason</th>
                <th style="width: 160px;">Where to route instead</th>
            </tr>
        </thead>
        <tbody>
            <!-- Repeat for each do-not-fix class -->
            <tr>
                <td>{keyword_class}</td>
                <td>{keyword_count}</td>
                <td>{do_not_fix_reason}</td>
                <td><code>{route_command}</code></td>
            </tr>
            <!-- /Repeat -->
        </tbody>
    </table>
</div>

<!-- Module Detail Sections -->
<!-- Repeat for each module: QS Distribution, Component Breakdown, Historical Trends, Competitive Context -->
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

<!-- Data Sufficiency Notes -->
<h2>Data sufficiency notes</h2>
<div style="background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 20px; margin: 16px 0;">
    <ul style="margin: 0; padding-left: 20px; font-size: 0.9rem; line-height: 1.7;">
        <!-- Repeat for each caveat (null-QS share, low-impression instability, fresh-account history, Smart Bidding dampening, missing changelog, competitor config) -->
        <li>{caveat}</li>
        <!-- /Repeat -->
    </ul>
</div>
```

## Data Extraction Guide

Parse the quality-score-audit.md file for:

1. **Header block**: Lines for `**Score:**`, `**Grade:**`, `**Period:**`, `**History:**`, `**Keywords:**`, `**Flagged:**`
2. **Executive read**: Section under `## Executive read` — prose paragraphs (≤300 words, no bullets). Split by paragraph break, render each as a separate `<p>`. Quoted peer-report findings stay inline. Covers six slots in order: score meaning, this-week priorities, what is NOT a problem, fresh peer findings, how to read the rest, score trend
3. **Diagnosis**: Section under `## Diagnosis`, written specialist-to-client. Four labeled sub-sections to render verbatim:
   - `**In one line:**` → `{diagnosis_in_one_line}`
   - `**What's happening.**` → `{diagnosis_whats_happening}`
   - `**Where it hurts most.**` → `{diagnosis_where_it_hurts}`
   - `**What to do first.**` → `{diagnosis_what_to_do_first}`
   Followed by a `**For the record (technical summary)**` block (after a `---` divider) with hypothesis layer/name, confidence, explained-% of QS CPC premium, **blocking_relationships**, and secondary hypotheses. Render that footer inside a collapsed `<details>`. Smart-Bidding dampening banner renders inside the diagnosis card when the source flags it.
4. **Classifier**: Section under `## Keyword Classifier` or inline line — counts of BRANDED, COMPETITOR, INFORMATIONAL, GENERIC
5. **Evidence Ladder**: Section under `## Evidence Ladder` — grouped by cascade layer (Outer: bidding-mode; Inner: AR, ECTR, LP). Each layer has a status and evidence bullets with hypothesis tags
6. **Module Scores table**: Table under `## Module Scores` — 4 rows: QS Distribution (/20), Component Breakdown (/45), Historical Trends (/15), Competitive Context (/20). D17 is INFO-only and is NOT a row in this table — render it in its own section (see #9).
7. **QS Distribution block**: Account-weighted QS, low-QS spend share, high-spend/low-QS count, null-QS count/%, per-campaign table (bidding mode, weighted QS, low-QS %, status)
8. **Component Breakdown block**: AR / ECTR / LP Below-Avg counts and %, dominant limiting component narrative
9. **Customizer Integrity (QS-D17, INFO-only)**: Section `### QS-D17 Customizer Integrity` — always rendered. PASS/INFO note when no broken setups; otherwise one or both of `BROKEN` and `EFFECTIVELY_STATIC` tables (ad_group, campaign, attributes, effective_resolution, RSAs_affected), plus the "How to fix" block.
10. **Historical Trends table**: Conditional on M3 running — per-metric start, end, slope, trajectory for account QS + each component
11. **Competitive Context table**: Per-campaign Lost-IS-Rank, weighted QS, CPC premium vs QS≥7 cohort, QS driver
12. **Actions — segmented by cascade state**: Section under `## Actions — segmented by cascade state`:
    - `### Investigate first` — blocking outer-cascade/data hypotheses
    - `### Branded-campaign escalation` — BRAND_LOW_QS flags
    - `## Handoff Queue — Ad Relevance` → `/rsa-maker` (ad_group, campaign, keywords_below_avg, impressions — impressions **mandatory**)
    - **Pending handoff — Ad group restructure** → `keyword-restructurer` is **not yet built**; render with a `PENDING — SKILL NOT YET BUILT` pill and the structural-split brief (ad_group, proposed theme split, keywords to move). No active route.
    - `## Handoff Queue — LP Experience` → `/lp-auditor` + `/lp-optimize` (grouped by *effective URL* — keyword-level `final_urls` override, else ad-level `final_urls`)
    - `## Handoff Queue — Expected CTR` → `/offer-maker` + `/rsa-maker` (only after AR resolved)
    - `### Do NOT run QS fixes on these` — COMPETITOR / INFORMATIONAL routing away
13. **Module Details**: Sections for each module with standard diagnostic tables
14. **Data Sufficiency Notes**: Free-form caveats (null-QS share, low-impression instability, fresh-account, Smart Bidding dampening, missing account-changelog, competitor config, **adaptive impression-threshold exclusion rate**)

## Special Fields

- **Diagnosis sub-sections**: Render the four labeled paragraphs (`In one line`, `What's happening`, `Where it hurts most`, `What to do first`) verbatim. Source markdown is written specialist-to-client — do not paraphrase, do not introduce cascade/layer/classifier terminology in the rendered prose. The source is currency-resolved upstream (uses the symbol from `config.googleAds.currency`); render strings as-is.
- **For-the-record footer**: The hypothesis layer/name, confidence, explained-%, blocking_relationships, and secondary hypotheses live below a `---` divider after the four sub-sections. Render inside a `<details>` element so it's collapsed by default — it's machine-readable context for downstream skills, not the headline.
- **Cascade layers**: Two-cascade system — outer (bidding-mode relevance) and inner (AR → ECTR → LP). AR layer blocks ECTR; LP runs in parallel. Only active layers render in the Evidence Ladder.
- **Smart Bidding dampening**: When the account runs Smart Bidding, severity annotations include `(dampened)`. Render the dampening banner in the Diagnosis card.
- **Keyword classes**: BRANDED, COMPETITOR, INFORMATIONAL, GENERIC — determined by classifier. COMPETITOR AR Below Avg is structural (do not fix). INFORMATIONAL routes to `/keyword-auditor`. BRAND_LOW_QS escalates to `/lp-auditor` before `/rsa-maker`.
- **Handoff queues — impressions mandatory**: AR, LP, and ECTR queue rows must carry impressions. Queues are sorted by impressions desc. Rows with zero impressions in window are excluded.
- **Pending handoff — keyword-restructurer**: Skill not yet built. Render with a `PENDING — SKILL NOT YET BUILT` warn pill and the structural-split brief (proposed theme split, keywords to move). Do NOT render `keyword-restructurer` as a runnable `<code>` slash command.
- **LP queue grouping**: Group by *effective URL* — keyword-level `final_urls` override when populated, else the ad's `final_urls`. The source markdown already resolves this; render the URL as-given.
- **Module point totals**: QS Distribution 20 pts, Component Breakdown 45 pts, Historical Trends 15 pts, Competitive Context 20 pts. Display as `{earned}/{max}` in module cards and detail headers. **D17 Customizer Integrity is INFO-only (0 pts)** — render in its own section, not as a Module Scores row.
- **Dominant limiting component**: Pick the component (AR / ECTR / LP) responsible for the largest share of below-avg weighted impressions. This drives the sequenced handoff order.
- **Historical Trends conditional**: Skip entire section if M3 SKIPed (fresh account <60d history).
- **Color mapping for counts**: Low-QS share and below-avg component % use warning/danger thresholds: ≥30% → `--color-danger`, ≥15% → `--color-warning`, otherwise `--color-success`.

## Status-to-Class Mapping

| Status | CSS Class |
|--------|-----------|
| PASS | `pass` |
| WARN | `warn` |
| FAIL | `fail` |
| SKIP | `skip` |
| INFO | `skip` |

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
