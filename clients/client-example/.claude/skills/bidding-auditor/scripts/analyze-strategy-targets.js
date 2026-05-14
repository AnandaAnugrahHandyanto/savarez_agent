#!/usr/bin/env node

/**
 * Bidding Auditor — Strategy Selection + Target Validation engine
 *
 * Modules covered:
 *   Module 1 — Strategy Selection (BID-D01–D04)
 *   Module 2 — Target Validation  (BID-D05–D09)
 *
 * Reads:
 *   campaigns-bidding-perf.csv     (aggregate per-campaign metrics)
 *   campaigns-bidding-daily.csv    (daily rows for D08 deviation tracking)
 *   bidding-strategies.csv         (portfolio target lookup)
 *
 * Writes:
 *   findings.json (merged with other engines downstream)
 *   opportunities.json (BID-D09 starvation recovery)
 *   target-deviation.csv (per-campaign actual vs target over the window)
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import {
    PROJECT_ROOT, readCsv, num, microsToDollars, getChannelType,
    isSmartBidding, isManualBidding, isValueBased,
    resolveCampaignTarget, indexPortfoliosByResource,
    getConvVolumeThreshold, computeBreakEvenMargin, computePAR,
    computeTargetDeviation, detectStarvationZone, getOpportunityValue,
    groupDailyByCampaign, makeFinding,
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
const findingsOut = args['findings-output'] || resolve(PROJECT_ROOT, 'context/analysis/bidding/findings-strategy-targets.json');
const oppsOut = args['opps-output'] || resolve(PROJECT_ROOT, 'context/analysis/bidding/opportunities-strategy-targets.json');
const deviationOut = args['deviation-output'] || resolve(PROJECT_ROOT, 'context/google-ads/data/target-deviation.csv');

const configPath = resolve(PROJECT_ROOT, 'config/ads-context.config.json');
const config = JSON.parse(readFileSync(configPath, 'utf8'));
const ba = config.biddingAudit || {};
const periodDays = parseInt(args['period'] || '30');

// ── Load data ──────────────────────────────────────────────────────────
const perfRows = readCsv(perfPath).filter(r => r['campaign.serving_status'] !== 'ENDED');
const dailyRows = readCsv(dailyPath);
const portfolioRows = readCsv(portfoliosPath);
const portfoliosById = indexPortfoliosByResource(portfolioRows);
const dailyByCampaign = groupDailyByCampaign(dailyRows);

const findings = [];
const opportunities = [];
const deviationLog = [];

// ── Iterate per campaign ──────────────────────────────────────────────
for (const c of perfRows) {
    const id = c['campaign.id'];
    const name = c['campaign.name'];
    const channel = getChannelType(c);
    const target = resolveCampaignTarget(c, portfoliosById);
    const cost = microsToDollars(c['metrics.cost_micros']);
    const conv = num(c['metrics.conversions']);
    const value = num(c['metrics.conversions_value']);
    const monthlyConv = (conv / Math.max(periodDays, 1)) * 30;
    const actualCpa = conv > 0 ? cost / conv : null;
    const actualRoas = cost > 0 ? value / cost : null;

    const meta = { campaign_id: id, campaign: name, channel, strategy: target.type, target_source: target.source, portfolio_name: target.portfolioName };

    // ── Module 1: Strategy Selection ─────────────────────────────────

    // BID-D01: Appropriateness — strategy matches maturity & goals
    {
        const threshold = getConvVolumeThreshold(channel, target.type);
        let verdict = 'PASS', severity = 'low', message = `Strategy ${target.type} on ${channel}; ${monthlyConv.toFixed(0)} conv/30d`;

        if (target.type === 'MANUAL_CPC' && monthlyConv >= ba.manualBiddingMaxConv) {
            verdict = 'WARN'; severity = 'medium';
            message = `Manual CPC on a campaign producing ${monthlyConv.toFixed(0)} conv/30d — consider smart bidding (≥ ${ba.manualBiddingMaxConv}/30d threshold).`;
        }
        if (isSmartBidding(target.type) && threshold && monthlyConv < threshold.absolute) {
            verdict = 'FAIL'; severity = 'high';
            message = `Smart bidding (${target.type}) on ${channel} below absolute minimum (${threshold.absolute}/30d, current ${monthlyConv.toFixed(0)}).`;
        }
        findings.push(makeFinding('BID-D01', verdict, severity, message, meta));
    }

    // BID-D02: Manual on high-volume
    if (isManualBidding(target.type) && monthlyConv >= ba.manualBiddingMaxConv) {
        findings.push(makeFinding('BID-D02', 'FAIL', 'high',
            `Manual bidding on ${monthlyConv.toFixed(0)} monthly conversions; smart bidding likely outperforms.`, meta));
    } else {
        findings.push(makeFinding('BID-D02', 'PASS', 'low', `Manual bidding not flagged.`, meta));
    }

    // BID-D03: Smart bidding without data
    if (isSmartBidding(target.type)) {
        const threshold = getConvVolumeThreshold(channel, target.type);
        const minimum = threshold?.absolute ?? ba.smartBiddingMinConv;
        if (monthlyConv < minimum) {
            findings.push(makeFinding('BID-D03', 'FAIL', 'high',
                `Smart bidding (${target.type}) with ${monthlyConv.toFixed(0)} conv/30d, below ${minimum} minimum for ${channel}.`,
                { ...meta, monthlyConv, threshold: minimum }));
        } else {
            findings.push(makeFinding('BID-D03', 'PASS', 'low',
                `Conversion volume meets smart-bidding minimum (${monthlyConv.toFixed(0)} ≥ ${minimum}).`, meta));
        }
    } else {
        findings.push(makeFinding('BID-D03', 'SKIP', 'low', 'Not smart bidding.', meta));
    }

    // BID-D04: Conversion action alignment — informational only
    findings.push(makeFinding('BID-D04', 'INFO', 'low',
        `Confirm strategy is optimizing for the right action. Account primary action: ${ba.primaryConversionAction || 'unset'}.`, meta));

    // ── Module 2: Target Validation ──────────────────────────────────

    // BID-D05: target CPA vs break-even
    if (target.type === 'TARGET_CPA' && target.targetCpa && ba.breakEvenCPA) {
        const margin = computeBreakEvenMargin(target.targetCpa, ba.breakEvenCPA, 'cpa');
        if (target.targetCpa > ba.breakEvenCPA) {
            findings.push(makeFinding('BID-D05', 'FAIL', 'high',
                `tCPA $${target.targetCpa.toFixed(2)} exceeds break-even $${ba.breakEvenCPA.toFixed(2)}; campaign cannot be profitable at this target.`,
                { ...meta, target_cpa: target.targetCpa, break_even_cpa: ba.breakEvenCPA, margin }));
        } else if (margin != null && margin < (ba.tCpaSafetyMargin || 0.7) - 0.5) {
            findings.push(makeFinding('BID-D05', 'WARN', 'medium',
                `tCPA $${target.targetCpa.toFixed(2)} is too close to break-even $${ba.breakEvenCPA.toFixed(2)} (margin ${(margin * 100).toFixed(0)}%).`,
                { ...meta, target_cpa: target.targetCpa, break_even_cpa: ba.breakEvenCPA, margin }));
        } else {
            findings.push(makeFinding('BID-D05', 'PASS', 'low',
                `tCPA within profitable range (margin ${(margin * 100).toFixed(0)}%).`, meta));
        }
    } else {
        findings.push(makeFinding('BID-D05', 'SKIP', 'low', 'Not a tCPA campaign or break-even unset.', meta));
    }

    // BID-D06: target ROAS vs break-even
    if (target.type === 'TARGET_ROAS' && target.targetRoas && ba.breakEvenROAS) {
        if (target.targetRoas < ba.breakEvenROAS) {
            findings.push(makeFinding('BID-D06', 'FAIL', 'high',
                `tROAS ${(target.targetRoas * 100).toFixed(0)}% below break-even ${(ba.breakEvenROAS * 100).toFixed(0)}%; cannot be profitable.`,
                { ...meta, target_roas: target.targetRoas, break_even_roas: ba.breakEvenROAS }));
        } else {
            findings.push(makeFinding('BID-D06', 'PASS', 'low',
                `tROAS at or above break-even.`, meta));
        }
    } else {
        findings.push(makeFinding('BID-D06', 'SKIP', 'low', 'Not a tROAS campaign or break-even unset.', meta));
    }

    // BID-D07: PAR ratio
    if (target.type === 'TARGET_CPA' && target.targetCpa && actualCpa) {
        const par = computePAR(actualCpa, target.targetCpa);
        const parTarget = ba.parTarget || 1.5;
        let verdict = 'PASS', severity = 'low';
        let message = `PAR ${par.toFixed(2)} (target ${parTarget.toFixed(2)}).`;
        if (par < 1.0) { verdict = 'FAIL'; severity = 'high'; message = `PAR ${par.toFixed(2)} below 1.0 — campaign overshooting target CPA.`; }
        else if (par < parTarget * 0.8) { verdict = 'WARN'; severity = 'medium'; message = `PAR ${par.toFixed(2)} below posture target ${parTarget.toFixed(2)}.`; }
        findings.push(makeFinding('BID-D07', verdict, severity, message, { ...meta, par, par_target: parTarget }));
    } else {
        findings.push(makeFinding('BID-D07', 'SKIP', 'low', 'PAR not applicable.', meta));
    }

    // BID-D08: target deviation over window
    if (target.hasTarget) {
        const days = dailyByCampaign.get(id) || [];
        const tail = days.slice(-Math.min(ba.tcpaDeviationDays || 14, days.length));
        const tailCost = tail.reduce((s, r) => s + microsToDollars(r['metrics.cost_micros']), 0);
        const tailConv = tail.reduce((s, r) => s + num(r['metrics.conversions']), 0);
        const tailValue = tail.reduce((s, r) => s + num(r['metrics.conversions_value']), 0);
        const tailCpa = tailConv > 0 ? tailCost / tailConv : null;
        const tailRoas = tailCost > 0 ? tailValue / tailCost : null;

        let dev = null;
        if (target.type === 'TARGET_CPA' && target.targetCpa && tailCpa) {
            dev = computeTargetDeviation(tailCpa, target.targetCpa);
        } else if (target.type === 'TARGET_ROAS' && target.targetRoas && tailRoas) {
            dev = -computeTargetDeviation(tailRoas, target.targetRoas);
        }
        deviationLog.push({
            campaign_id: id, campaign: name, strategy: target.type,
            target_cpa: target.targetCpa ?? '', target_roas: target.targetRoas ?? '',
            actual_cpa: tailCpa ?? '', actual_roas: tailRoas ?? '',
            deviation_pct: dev != null ? dev.toFixed(1) : '',
        });

        if (dev != null && Math.abs(dev) >= (ba.tcpaDeviationPp || 20)) {
            findings.push(makeFinding('BID-D08', 'WARN', 'medium',
                `Actual deviates ${dev.toFixed(0)}% from target over last ${tail.length} days.`,
                { ...meta, deviation_pct: dev }));
        } else {
            findings.push(makeFinding('BID-D08', 'PASS', 'low',
                dev != null ? `Within ±${ba.tcpaDeviationPp || 20}% of target.` : 'Insufficient daily data.', meta));
        }
    } else {
        findings.push(makeFinding('BID-D08', 'SKIP', 'low', 'No target to compare against.', meta));
    }

    // BID-D09: starvation zone
    if (target.hasTarget) {
        const sv = detectStarvationZone(c, target);
        if (sv.isStarvation) {
            findings.push(makeFinding('BID-D09', 'WARN', 'medium',
                `Possible starvation: ${sv.reason}.`, meta));

            // Also emit an opportunity entry — recovery if target is loosened by ~20%.
            opportunities.push({
                type: 'starvation_recovery',
                campaign_id: id, campaign: name,
                strategy: target.type,
                current_target: target.targetCpa ?? target.targetRoas,
                suggested_step_pct: 20,
                rationale: sv.reason,
            });
        } else {
            findings.push(makeFinding('BID-D09', 'PASS', 'low', 'No starvation pattern detected.', meta));
        }
    } else {
        findings.push(makeFinding('BID-D09', 'SKIP', 'low', 'No target.', meta));
    }

    // ── Cross-cutting opportunity: budget-lost recovery ──────────────
    const opp = getOpportunityValue(c, target, ba.breakEvenCPA);
    if (opp) {
        opportunities.push({
            ...opp,
            campaign_id: id, campaign: name, strategy: target.type,
        });
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
writeCsv(deviationOut, deviationLog);

const counts = findings.reduce((acc, f) => { acc[f.verdict] = (acc[f.verdict] || 0) + 1; return acc; }, {});
console.log(`analyze-strategy-targets: ${findings.length} findings`);
console.log(`  ${JSON.stringify(counts)}`);
console.log(`  opportunities: ${opportunities.length}`);
console.log(`  outputs: ${findingsOut}, ${oppsOut}, ${deviationOut}`);
