#!/usr/bin/env node

/**
 * Bidding Auditor — Learning Phase + CPC Health engine
 *
 * Modules covered:
 *   Module 3 — Learning Phase (BID-D10–D13)
 *   Module 6 — CPC & Cost Health (BID-D22–D24)
 *
 * Reads:
 *   campaigns-bidding-perf.csv
 *   campaigns-bidding-daily.csv
 *   bidding-strategies.csv (portfolio resolution)
 *   bidding-data-exclusions.csv
 *   context/account-changelog.md (parsed for last-change dates)
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import {
    PROJECT_ROOT, readCsv, num, microsToDollars,
    indexPortfoliosByResource, resolveCampaignTarget,
    groupDailyByCampaign, detectCpcSpike, detectCpcRisingTrend,
    parseAccountChangelog, getLearningStatus, getOpportunityValue,
    makeFinding,
} from './lib.js';

const __dirname = dirname(fileURLToPath(import.meta.url));

const args = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const i = arg.indexOf('=');
        acc[arg.slice(0, i).replace('--', '')] = arg.slice(i + 1);
    }
    return acc;
}, {});

const perfPath = args['perf-csv'] || resolve(PROJECT_ROOT, 'context/google-ads/data/campaigns-bidding-perf.csv');
const dailyPath = args['daily-csv'] || resolve(PROJECT_ROOT, 'context/google-ads/data/campaigns-bidding-daily.csv');
const portfoliosPath = args['portfolios-csv'] || resolve(PROJECT_ROOT, 'context/google-ads/data/bidding-strategies.csv');
const exclusionsPath = args['exclusions-csv'] || resolve(PROJECT_ROOT, 'context/google-ads/data/bidding-data-exclusions.csv');
const changelogPath = args['changelog'] || resolve(PROJECT_ROOT, 'context/account-changelog.md');
const findingsOut = args['findings-output'] || resolve(PROJECT_ROOT, 'context/analysis/bidding/findings-temporal.json');
const oppsOut = args['opps-output'] || resolve(PROJECT_ROOT, 'context/analysis/bidding/opportunities-temporal.json');
const learningStateOut = args['learning-state-output'] || resolve(PROJECT_ROOT, 'context/google-ads/data/learning-state.csv');

const configPath = resolve(PROJECT_ROOT, 'config/ads-context.config.json');
const config = JSON.parse(readFileSync(configPath, 'utf8'));
const ba = config.biddingAudit || {};

const perfRows = readCsv(perfPath).filter(r => r['campaign.serving_status'] !== 'ENDED');
const dailyRows = readCsv(dailyPath);
const portfolioRows = readCsv(portfoliosPath);
const exclusions = readCsv(exclusionsPath);
const portfoliosById = indexPortfoliosByResource(portfolioRows);
const dailyByCampaign = groupDailyByCampaign(dailyRows);

const changelogText = existsSync(changelogPath) ? readFileSync(changelogPath, 'utf8') : '';
const changelog = parseAccountChangelog(changelogText);

const findings = [];
const opportunities = [];
const learningState = [];

const today = new Date().toISOString().slice(0, 10);
const learningWindow = ba.learningWindowDays || 14;

for (const c of perfRows) {
    const id = c['campaign.id'];
    const name = c['campaign.name'];
    const target = resolveCampaignTarget(c, portfoliosById);
    const meta = { campaign_id: id, campaign: name, strategy: target.type };

    const status = getLearningStatus(name, changelog, learningWindow, today);

    learningState.push({
        campaign_id: id, campaign: name, strategy: target.type,
        last_strategy_change: status.lastStrategyChange ?? '',
        last_target_change: status.lastTargetChange ?? '',
        days_since_strategy: status.daysSinceStrategy ?? '',
        days_since_target: status.daysSinceTarget ?? '',
        in_learning: status.inLearning ? 'yes' : 'no',
    });

    // BID-D10: Extended learning (>14 days). True signal needs API status; here we
    // infer from a strategy change made >14d ago + still flagged in-learning.
    // Without a reliable "still in learning" signal we surface this as INFO.
    findings.push(makeFinding('BID-D10', 'INFO', 'low',
        'Extended-learning detection requires the bidding_strategy.learning_status field; surface manually if Google Ads UI flags this campaign as "still learning" >14 days.', meta));

    // BID-D11: Changes during learning
    if (status.inLearning && (status.daysSinceStrategy != null && status.daysSinceTarget != null)
        && status.daysSinceStrategy !== status.daysSinceTarget
        && status.daysSinceStrategy < learningWindow
        && status.daysSinceTarget < learningWindow) {
        findings.push(makeFinding('BID-D11', 'WARN', 'medium',
            `Strategy changed ${status.daysSinceStrategy}d ago AND target changed ${status.daysSinceTarget}d ago — overlapping learning resets.`,
            { ...meta, ...status }));
    } else {
        findings.push(makeFinding('BID-D11', 'PASS', 'low', 'No overlapping changes during learning.', meta));
    }

    // BID-D12: Data exclusion coverage during learning disruptions — informational
    findings.push(makeFinding('BID-D12', 'INFO', 'low',
        `Account has ${exclusions.length} data exclusion record(s). Verify any tracking outage in the last 60 days has a matching exclusion.`, meta));

    // BID-D13: Recent strategy change (<14 days) — counsel against new mutations
    if (status.daysSinceStrategy != null && status.daysSinceStrategy < learningWindow) {
        findings.push(makeFinding('BID-D13', 'WARN', 'medium',
            `Strategy changed ${status.daysSinceStrategy} days ago — still in learning. Avoid further bid mutations until ≥${learningWindow}d clears.`,
            { ...meta, days_since_strategy: status.daysSinceStrategy }));
    } else {
        findings.push(makeFinding('BID-D13', 'PASS', 'low',
            status.lastStrategyChange ? `Last strategy change ${status.daysSinceStrategy}d ago.` : 'No strategy change recorded.', meta));
    }

    // ── Module 6: CPC & Cost Health ──────────────────────────────────

    const days = dailyByCampaign.get(id) || [];

    // BID-D22: CPC spike
    const spike = detectCpcSpike(days, ba.cpcSpikeThresholdPct || 25);
    if (spike?.isSpike) {
        findings.push(makeFinding('BID-D22', 'WARN', 'medium',
            `CPC spike: $${spike.recent.toFixed(2)} vs $${spike.prior.toFixed(2)} prior 14d (+${spike.pctChange.toFixed(0)}%).`,
            { ...meta, ...spike }));
    } else if (spike) {
        findings.push(makeFinding('BID-D22', 'PASS', 'low',
            `CPC stable: ${spike.pctChange.toFixed(0)}% vs prior 14d.`, meta));
    } else {
        findings.push(makeFinding('BID-D22', 'SKIP', 'low', 'Insufficient daily data for CPC spike detection.', meta));
    }

    // BID-D23: Rising CPC trend
    const trend = detectCpcRisingTrend(days, ba.cpcRisingTrendPeriods || 3, 7);
    if (trend?.rising) {
        findings.push(makeFinding('BID-D23', 'WARN', 'medium',
            `CPC rising for ${trend.buckets.length} consecutive periods: ${trend.buckets.map(b => `$${b.toFixed(2)}`).join(' → ')}.`,
            { ...meta, buckets: trend.buckets }));
    } else if (trend) {
        findings.push(makeFinding('BID-D23', 'PASS', 'low', 'No rising CPC trend.', meta));
    } else {
        findings.push(makeFinding('BID-D23', 'SKIP', 'low', 'Insufficient daily data for trend detection.', meta));
    }

    // BID-D24: bid simulator gap (heuristic in v1) — emit as opportunity
    const opp = getOpportunityValue(c, target, ba.breakEvenCPA);
    if (opp) {
        findings.push(makeFinding('BID-D24', 'INFO', 'low',
            `Heuristic projects ${opp.incrementalConv} incremental conv at projected CPA $${opp.projectedCpa ?? '—'} if budget loosens.`,
            { ...meta, ...opp }));
        opportunities.push({
            type: 'simulator_gap_heuristic',
            campaign_id: id, campaign: name, strategy: target.type,
            ...opp,
        });
    } else {
        findings.push(makeFinding('BID-D24', 'PASS', 'low', 'No incremental opportunity from heuristic.', meta));
    }
}

// ── Write outputs ──────────────────────────────────────────────────────

function writeJson(path, data) {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, JSON.stringify(data, null, 2));
}
function writeCsv(path, rows) {
    mkdirSync(dirname(path), { recursive: true });
    if (!rows.length) { writeFileSync(path, '', 'utf8'); return; }
    const headers = Object.keys(rows[0]);
    const out = [headers.join(',')];
    for (const r of rows) {
        out.push(headers.map(h => {
            const v = r[h];
            if (v == null) return '';
            const s = String(v);
            return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
        }).join(','));
    }
    writeFileSync(path, out.join('\n'), 'utf8');
}

writeJson(findingsOut, findings);
writeJson(oppsOut, opportunities);
writeCsv(learningStateOut, learningState);

const counts = findings.reduce((acc, f) => { acc[f.verdict] = (acc[f.verdict] || 0) + 1; return acc; }, {});
console.log(`analyze-temporal: ${findings.length} findings`);
console.log(`  ${JSON.stringify(counts)}`);
console.log(`  opportunities: ${opportunities.length}`);
console.log(`  outputs: ${findingsOut}, ${oppsOut}, ${learningStateOut}`);
