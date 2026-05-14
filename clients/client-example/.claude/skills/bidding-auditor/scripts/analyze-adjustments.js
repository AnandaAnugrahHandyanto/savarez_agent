#!/usr/bin/env node

/**
 * Bidding Auditor — Bid Adjustments engine
 *
 * Module covered:
 *   Module 5 — Bid Adjustments (BID-D18–D21)
 *
 * Reads:
 *   campaigns-criteria-bidding.csv   (criteria with bid_modifier != 1.0)
 *   campaigns-bidding-perf.csv       (so we can identify which campaigns are smart-bid)
 *
 * Note: ~99% of bid modifiers on smart-bidding campaigns are noise. We surface
 * them as INFO and only WARN when modifier == -100% (effective exclusion) or
 * when the campaign is on Manual CPC.
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import {
    PROJECT_ROOT, readCsv, num, isSmartBidding, isManualBidding, makeFinding,
} from './lib.js';

const __dirname = dirname(fileURLToPath(import.meta.url));

const args = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const i = arg.indexOf('=');
        acc[arg.slice(0, i).replace('--', '')] = arg.slice(i + 1);
    }
    return acc;
}, {});

const criteriaPath = args['criteria-csv'] || resolve(PROJECT_ROOT, 'context/google-ads/data/campaigns-criteria-bidding.csv');
const perfPath = args['perf-csv'] || resolve(PROJECT_ROOT, 'context/google-ads/data/campaigns-bidding-perf.csv');
const findingsOut = args['findings-output'] || resolve(PROJECT_ROOT, 'context/analysis/bidding/findings-adjustments.json');

const criteriaRows = readCsv(criteriaPath);
const perfRows = readCsv(perfPath).filter(r => r['campaign.serving_status'] !== 'ENDED');

// Build a lookup: campaign id → bidding strategy type
const strategyByCampaign = new Map();
for (const r of perfRows) {
    strategyByCampaign.set(r['campaign.id'], r['campaign.bidding_strategy_type']);
}

const findings = [];

// Categorize criteria
const adjustmentsByType = {
    device: [],
    location: [],
    schedule: [],
    audience: [],
    other: [],
};

for (const r of criteriaRows) {
    const type = (r['campaign_criterion.type'] || '').toUpperCase();
    const modifier = num(r['campaign_criterion.bid_modifier']);
    if (modifier === 1) continue; // 1.0 = no-op; 0 = -100% exclusion (real signal — keep)
    const enriched = {
        ...r,
        modifier,
        modifier_pct: ((modifier - 1) * 100).toFixed(0) + '%',
        strategy: strategyByCampaign.get(r['campaign.id']) || '',
    };
    if (type === 'DEVICE') adjustmentsByType.device.push(enriched);
    else if (type === 'LOCATION') adjustmentsByType.location.push(enriched);
    else if (type === 'AD_SCHEDULE') adjustmentsByType.schedule.push(enriched);
    else if (type === 'USER_LIST' || type === 'USER_INTEREST'
          || type === 'AGE_RANGE' || type === 'GENDER'
          || type === 'INCOME_RANGE' || type === 'PARENTAL_STATUS') adjustmentsByType.audience.push(enriched);
    else adjustmentsByType.other.push(enriched);
}

// BID-D18: Adjustments on smart bidding (ignored unless == -100%)
{
    const ignoredOnSmart = [];
    const exclusionsOnSmart = [];
    for (const r of [...adjustmentsByType.device, ...adjustmentsByType.location,
                     ...adjustmentsByType.schedule, ...adjustmentsByType.audience]) {
        if (isSmartBidding(r.strategy)) {
            if (r.modifier === 0) exclusionsOnSmart.push(r);
            else ignoredOnSmart.push(r);
        }
    }
    if (ignoredOnSmart.length) {
        findings.push(makeFinding('BID-D18', 'INFO', 'low',
            `${ignoredOnSmart.length} bid modifiers active on smart-bidding campaigns; smart bidding ignores values other than -100%. Informational only.`,
            { count: ignoredOnSmart.length, sample: ignoredOnSmart.slice(0, 10) }));
    } else {
        findings.push(makeFinding('BID-D18', 'PASS', 'low', 'No ignored modifiers on smart bidding.', {}));
    }
    if (exclusionsOnSmart.length) {
        findings.push(makeFinding('BID-D18', 'INFO', 'low',
            `${exclusionsOnSmart.length} -100% (exclusion) modifiers on smart bidding — these still apply as exclusions. Confirm intent.`,
            { count: exclusionsOnSmart.length, sample: exclusionsOnSmart.slice(0, 10) }));
    }
}

// BID-D19: Device adjustments — appropriateness on manual
{
    const onManual = adjustmentsByType.device.filter(r => isManualBidding(r.strategy));
    if (onManual.length) {
        findings.push(makeFinding('BID-D19', 'INFO', 'low',
            `${onManual.length} device modifiers on manual-CPC campaigns. Validate they reflect device-specific CPC efficiency, not stale assumptions.`,
            { count: onManual.length, sample: onManual.slice(0, 10) }));
    } else {
        findings.push(makeFinding('BID-D19', 'PASS', 'low', 'No device modifiers on manual CPC.', {}));
    }
}

// BID-D20: Location/schedule adjustments
{
    const onManual = [...adjustmentsByType.location, ...adjustmentsByType.schedule]
        .filter(r => isManualBidding(r.strategy));
    if (onManual.length) {
        findings.push(makeFinding('BID-D20', 'INFO', 'low',
            `${onManual.length} location/schedule modifiers on manual CPC. Review effectiveness vs current data.`,
            { count: onManual.length, sample: onManual.slice(0, 10) }));
    } else {
        findings.push(makeFinding('BID-D20', 'PASS', 'low', 'No location/schedule modifiers on manual CPC.', {}));
    }
}

// BID-D21: Audience adjustments
{
    const onManual = adjustmentsByType.audience.filter(r => isManualBidding(r.strategy));
    if (onManual.length) {
        findings.push(makeFinding('BID-D21', 'INFO', 'low',
            `${onManual.length} audience modifiers on manual CPC. Review for accuracy.`,
            { count: onManual.length, sample: onManual.slice(0, 10) }));
    } else {
        findings.push(makeFinding('BID-D21', 'PASS', 'low', 'No audience modifiers on manual CPC.', {}));
    }
}

function writeJson(path, data) {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, JSON.stringify(data, null, 2));
}
writeJson(findingsOut, findings);

const counts = findings.reduce((acc, f) => { acc[f.verdict] = (acc[f.verdict] || 0) + 1; return acc; }, {});
console.log(`analyze-adjustments: ${findings.length} findings`);
console.log(`  ${JSON.stringify(counts)}`);
console.log(`  output: ${findingsOut}`);
