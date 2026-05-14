#!/usr/bin/env node

/**
 * Quality Score — Trend Analysis
 *
 * Reads keywords-qs-timeseries.csv (weekly segmented historical QS + components)
 * and writes qs-trends.csv with per-keyword trajectory, slope, and component
 * trends. Optionally correlates with context/account-changelog.md for post-
 * optimization QS deltas (D13).
 *
 * Usage:
 *   node analyze-qs-trends.js \
 *     --timeseries-csv=context/google-ads/data/keywords-qs-timeseries.csv \
 *     --output=context/google-ads/data/qs-trends.csv
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { parse } from 'csv-parse/sync';

const __dirname = dirname(fileURLToPath(import.meta.url));
let _projectRoot = __dirname;
while (_projectRoot !== '/' && !existsSync(resolve(_projectRoot, 'config'))) {
    _projectRoot = resolve(_projectRoot, '..');
}

const args = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const eqIndex = arg.indexOf('=');
        const key = arg.slice(0, eqIndex).replace(/^--/, '');
        const value = arg.slice(eqIndex + 1);
        if (key && value) acc[key] = value;
    }
    return acc;
}, {});

const timeseriesCsvPath = resolve(_projectRoot, args['timeseries-csv'] || 'context/google-ads/data/keywords-qs-timeseries.csv');
const outputPath = resolve(_projectRoot, args['output'] || 'context/google-ads/data/qs-trends.csv');
const changelogPath = resolve(_projectRoot, 'context/account-changelog.md');

// ── Config thresholds ───────────────────────────────────────────────
let qsConfig = {};
try {
    const configPath = resolve(_projectRoot, 'config/ads-context.config.json');
    if (existsSync(configPath)) {
        const full = JSON.parse(readFileSync(configPath, 'utf8'));
        qsConfig = full.qualityScoreAudit || {};
    }
} catch (e) { /* defaults */ }

const T = qsConfig.thresholds || {};
const CFG = {
    qsTrendWarnPoints: T.qsTrendWarnPoints ?? 1,
    qsTrendFailPoints: T.qsTrendFailPoints ?? 2,
    minWeeksForTrend: T.minWeeksForTrend ?? 4,
    minImpressionsPerWeek: T.minImpressionsPerWeek ?? 25,
};

// ── Helpers ─────────────────────────────────────────────────────────
function loadCsv(path) {
    if (!path || !existsSync(path)) return [];
    const raw = readFileSync(path, 'utf8');
    const rows = parse(raw, { columns: true, skip_empty_lines: true, relax_column_count: true });
    return rows.map(row => {
        const norm = {};
        for (const [k, v] of Object.entries(row)) {
            norm[k.replace(/\./g, '_')] = v;
        }
        return norm;
    });
}

function num(val) {
    const n = parseFloat(val);
    return isNaN(n) ? 0 : n;
}

function numOrNull(val) {
    if (val === '' || val === null || val === undefined) return null;
    const n = parseFloat(val);
    return isNaN(n) ? null : n;
}

function escapeCsv(val) {
    if (val == null) return '';
    const s = String(val);
    if (s.includes(',') || s.includes('"') || s.includes('\n')) {
        return '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
}

function writeCsv(path, headers, rows) {
    const dir = dirname(path);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    const lines = [headers.join(',')];
    for (const row of rows) {
        lines.push(headers.map(h => escapeCsv(row[h])).join(','));
    }
    writeFileSync(path, lines.join('\n') + '\n', 'utf8');
}

// Simple least-squares slope for equally-spaced series
function linearSlope(values) {
    const n = values.length;
    if (n < 2) return 0;
    const xs = values.map((_, i) => i);
    const xMean = xs.reduce((a, b) => a + b, 0) / n;
    const yMean = values.reduce((a, b) => a + b, 0) / n;
    let num = 0, denom = 0;
    for (let i = 0; i < n; i++) {
        num += (xs[i] - xMean) * (values[i] - yMean);
        denom += (xs[i] - xMean) ** 2;
    }
    return denom === 0 ? 0 : num / denom;
}

function componentNumeric(raw) {
    if (raw === '' || raw === null || raw === undefined) return null;
    const s = String(raw).toUpperCase().trim();
    if (s === 'BELOW_AVERAGE' || s === '1') return 1;
    if (s === 'AVERAGE' || s === '2') return 2;
    if (s === 'ABOVE_AVERAGE' || s === '3') return 3;
    const n = parseFloat(s);
    if (!isNaN(n) && n >= 1 && n <= 3) return n;
    return null;
}

function classifyTrajectory(change, warnPts, failPts) {
    if (change <= -failPts) return 'DECLINING_SHARP';
    if (change <= -warnPts) return 'DECLINING';
    if (change >= warnPts) return 'IMPROVING';
    return 'STABLE';
}

// ── Load data ───────────────────────────────────────────────────────
console.log('Loading timeseries data...');
const rows = loadCsv(timeseriesCsvPath);
console.log(`Timeseries rows: ${rows.length}`);

if (rows.length === 0) {
    console.warn('⚠ No timeseries data. Writing empty output.');
    writeCsv(outputPath, [
        'keyword_text', 'match_type', 'campaign_name', 'ad_group_name',
        'campaign_id', 'ad_group_id', 'criterion_id',
        'weeks_of_data', 'first_qs', 'last_qs', 'qs_change',
        'qs_slope_per_week', 'qs_trajectory',
        'ar_first', 'ar_last', 'ar_trajectory',
        'ectr_first', 'ectr_last', 'ectr_trajectory',
        'lp_first', 'lp_last', 'lp_trajectory',
        'total_impressions', 'changelog_events_near',
    ], []);
    process.exit(0);
}

// ── Load changelog (optional) for D13 correlation ───────────────────
const changelogEvents = [];
if (existsSync(changelogPath)) {
    const changelog = readFileSync(changelogPath, 'utf8');
    // Extract dated change events (ISO dates like 2026-03-15 or YYYY-MM-DD)
    const dateRegex = /(\d{4}-\d{2}-\d{2})/g;
    const lines = changelog.split('\n');
    for (const line of lines) {
        const match = line.match(dateRegex);
        if (match && line.trim()) {
            for (const d of match) {
                changelogEvents.push({ date: d, line: line.trim().slice(0, 140) });
            }
        }
    }
    console.log(`Changelog events loaded: ${changelogEvents.length}`);
} else {
    console.log('No changelog found — D13 post-optimization correlation skipped.');
}

// ── Group rows by keyword (ad_group_id, criterion_id) ───────────────
console.log('Aggregating by keyword...');

const keywordSeries = new Map();
for (const row of rows) {
    const agId = row.ad_group_id;
    const crId = row.ad_group_criterion_criterion_id;
    if (!agId || !crId) continue;
    const key = `${agId}:${crId}`;

    if (!keywordSeries.has(key)) {
        keywordSeries.set(key, {
            keyword_text: row.ad_group_criterion_keyword_text || '',
            match_type: row.ad_group_criterion_keyword_match_type || '',
            campaign_name: row.campaign_name || '',
            ad_group_name: row.ad_group_name || '',
            campaign_id: row.campaign_id || '',
            ad_group_id: agId,
            criterion_id: crId,
            weeks: [],
        });
    }
    const ks = keywordSeries.get(key);
    ks.weeks.push({
        week: row.segments_week || '',
        qs: numOrNull(row.metrics_historical_quality_score),
        ar: componentNumeric(row.metrics_historical_creative_quality_score),
        ectr: componentNumeric(row.metrics_historical_search_predicted_ctr),
        lp: componentNumeric(row.metrics_historical_landing_page_quality_score),
        impressions: num(row.metrics_impressions),
    });
}

console.log(`Unique keywords in timeseries: ${keywordSeries.size}`);

// ── Compute trajectory per keyword ──────────────────────────────────
const trends = [];
for (const [, ks] of keywordSeries) {
    // Sort by week ascending
    ks.weeks.sort((a, b) => (a.week < b.week ? -1 : a.week > b.week ? 1 : 0));

    // Filter to weeks with valid QS + minimum impressions (noise gate)
    const validWeeks = ks.weeks.filter(w =>
        w.qs !== null && w.qs >= 1 && w.qs <= 10 && w.impressions >= CFG.minImpressionsPerWeek
    );

    if (validWeeks.length < CFG.minWeeksForTrend) {
        // Not enough history to trend — still emit the row with SKIP trajectory
        // so downstream can see which keywords were skipped and why.
        trends.push(baseRow(ks, ks.weeks, {
            weeksOfData: validWeeks.length,
            firstQs: validWeeks[0]?.qs ?? '',
            lastQs: validWeeks[validWeeks.length - 1]?.qs ?? '',
            qsChange: '',
            qsSlope: '',
            qsTrajectory: 'INSUFFICIENT_DATA',
            arFirst: '', arLast: '', arTraj: 'INSUFFICIENT_DATA',
            ectrFirst: '', ectrLast: '', ectrTraj: 'INSUFFICIENT_DATA',
            lpFirst: '', lpLast: '', lpTraj: 'INSUFFICIENT_DATA',
            changelogEventsNear: '',
        }));
        continue;
    }

    const qsValues = validWeeks.map(w => w.qs);
    const firstQs = qsValues[0];
    const lastQs = qsValues[qsValues.length - 1];
    const qsChange = lastQs - firstQs;
    const qsSlope = linearSlope(qsValues);

    // Component trajectories — use first/last non-null values
    function componentTraj(key) {
        const vals = validWeeks.map(w => w[key]).filter(v => v !== null);
        if (vals.length < 2) return { first: '', last: '', traj: 'INSUFFICIENT_DATA' };
        const first = vals[0];
        const last = vals[vals.length - 1];
        const change = last - first;
        // Components are on 1-3 scale: any +1 = improving, -1 = declining
        let traj;
        if (change <= -1) traj = 'DECLINING';
        else if (change >= 1) traj = 'IMPROVING';
        else traj = 'STABLE';
        return { first, last, traj };
    }

    const ar = componentTraj('ar');
    const ectr = componentTraj('ectr');
    const lp = componentTraj('lp');

    const qsTrajectory = classifyTrajectory(qsChange, CFG.qsTrendWarnPoints, CFG.qsTrendFailPoints);

    // Correlate with changelog — count events in the window of this keyword's data
    let changelogEventsNear = 0;
    if (changelogEvents.length > 0 && validWeeks.length > 0) {
        const firstWeek = validWeeks[0].week;
        const lastWeek = validWeeks[validWeeks.length - 1].week;
        for (const ev of changelogEvents) {
            if (ev.date >= firstWeek && ev.date <= lastWeek) {
                changelogEventsNear++;
            }
        }
    }

    trends.push(baseRow(ks, validWeeks, {
        weeksOfData: validWeeks.length,
        firstQs,
        lastQs,
        qsChange: qsChange.toFixed(2),
        qsSlope: qsSlope.toFixed(3),
        qsTrajectory,
        arFirst: ar.first, arLast: ar.last, arTraj: ar.traj,
        ectrFirst: ectr.first, ectrLast: ectr.last, ectrTraj: ectr.traj,
        lpFirst: lp.first, lpLast: lp.last, lpTraj: lp.traj,
        changelogEventsNear: changelogEventsNear || '',
    }));
}

function baseRow(ks, weeks, m) {
    const totalImpressions = weeks.reduce((s, w) => s + (w.impressions || 0), 0);
    return {
        keyword_text: ks.keyword_text,
        match_type: ks.match_type,
        campaign_name: ks.campaign_name,
        ad_group_name: ks.ad_group_name,
        campaign_id: ks.campaign_id,
        ad_group_id: ks.ad_group_id,
        criterion_id: ks.criterion_id,
        weeks_of_data: m.weeksOfData,
        first_qs: m.firstQs,
        last_qs: m.lastQs,
        qs_change: m.qsChange,
        qs_slope_per_week: m.qsSlope,
        qs_trajectory: m.qsTrajectory,
        ar_first: m.arFirst,
        ar_last: m.arLast,
        ar_trajectory: m.arTraj,
        ectr_first: m.ectrFirst,
        ectr_last: m.ectrLast,
        ectr_trajectory: m.ectrTraj,
        lp_first: m.lpFirst,
        lp_last: m.lpLast,
        lp_trajectory: m.lpTraj,
        total_impressions: totalImpressions,
        changelog_events_near: m.changelogEventsNear,
    };
}

// ── Write output ────────────────────────────────────────────────────
const headers = [
    'keyword_text', 'match_type', 'campaign_name', 'ad_group_name',
    'campaign_id', 'ad_group_id', 'criterion_id',
    'weeks_of_data', 'first_qs', 'last_qs', 'qs_change',
    'qs_slope_per_week', 'qs_trajectory',
    'ar_first', 'ar_last', 'ar_trajectory',
    'ectr_first', 'ectr_last', 'ectr_trajectory',
    'lp_first', 'lp_last', 'lp_trajectory',
    'total_impressions', 'changelog_events_near',
];
writeCsv(outputPath, headers, trends);
console.log(`File: ${outputPath}`);
console.log(`Rows: ${trends.length}`);

// Summary
const trajCounts = {};
for (const t of trends) {
    trajCounts[t.qs_trajectory] = (trajCounts[t.qs_trajectory] || 0) + 1;
}
console.log(`\nTrajectory distribution: ${JSON.stringify(trajCounts)}`);
console.log('Done.');
