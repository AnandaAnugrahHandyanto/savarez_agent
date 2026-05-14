#!/usr/bin/env node

/**
 * Quality Score Auditor - Batch Data Pull
 *
 * Runs all 5 QS auditor GAQL queries in a single process,
 * delegating to gads-context/scripts/query.js.
 *
 * Usage:
 *   node scripts/pull-all.js --period=30 --lag=8 --history=180
 *
 * Reads config from: config/ads-context.config.json
 * Outputs CSVs to:   context/google-ads/data/
 */

import { execFileSync } from 'child_process';
import { existsSync, mkdirSync, readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

let projectRoot = __dirname;
while (projectRoot !== '/' && !existsSync(resolve(projectRoot, 'config'))) {
    projectRoot = resolve(projectRoot, '..');
}

const cliArgs = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const eqIndex = arg.indexOf('=');
        acc[arg.slice(0, eqIndex).replace('--', '')] = arg.slice(eqIndex + 1);
    } else if (arg.startsWith('--')) {
        acc[arg.replace('--', '')] = true;
    }
    return acc;
}, {});

const configPath = resolve(projectRoot, 'config/ads-context.config.json');
if (!existsSync(configPath)) {
    console.error('Error: config/ads-context.config.json not found');
    process.exit(1);
}
const config = JSON.parse(readFileSync(configPath, 'utf8'));
const gads = config.googleAds;

if (!gads || !gads.customerId) {
    console.error('Error: googleAds.customerId missing from config');
    process.exit(1);
}

const customerId = gads.customerId;
const loginCustomerId = gads.loginCustomerId || customerId;
const period = parseInt(cliArgs['period'] || config.qualityScoreAudit?.evaluationPeriod || 30);
const lag = parseInt(cliArgs['lag'] || config.searchTermAnalysis?.conversionLagDays || 8);
const history = parseInt(cliArgs['history'] || config.qualityScoreAudit?.historicalPeriod || 180);

const gaqlDir = resolve(__dirname, '..', 'reference', 'gaql');
const queryScript = resolve(projectRoot, '.claude/skills/gads-context/scripts/query.js');
const outputDir = resolve(projectRoot, 'context/google-ads/data');

mkdirSync(outputDir, { recursive: true });

const results = [];

function runQuery(label, gaqlFile, outputFile, opts = {}) {
    const args = [
        queryScript,
        `--customer-id=${customerId}`,
        `--login-customer-id=${loginCustomerId}`,
        `--query-file=${resolve(gaqlDir, gaqlFile)}`,
        `--output=${resolve(outputDir, outputFile)}`,
    ];

    if (opts.noDateRange) {
        args.push('--no-date-range');
    } else {
        args.push(`--days=${opts.days ?? period}`);
        if (opts.lagOffset !== undefined) {
            args.push(`--lag-offset=${opts.lagOffset}`);
        }
    }

    if (opts.allowEmpty) {
        args.push('--allow-empty');
    }

    try {
        const output = execFileSync('node', args, {
            cwd: projectRoot,
            encoding: 'utf8',
            timeout: 180000,
        });

        const rowsMatch = output.match(/Rows:\s*(\d+)/);
        const rows = rowsMatch ? parseInt(rowsMatch[1]) : '?';
        results.push({ label, file: outputFile, rows, status: 'OK' });
        console.log(`  ${label}: ${outputFile} (${rows} rows)`);
    } catch (error) {
        const stderr = error.stderr || error.message;
        results.push({ label, file: outputFile, rows: 0, status: 'ERROR' });
        console.error(`  ${label}: ERROR - ${stderr.trim().split('\n')[0]}`);
    }
}

console.log(`\nQuality Score Auditor — Batch Pull`);
console.log(`Account: ${gads.clientName || customerId}`);
console.log(`Customer ID: ${customerId}`);
console.log(`Period: ${period} days | Lag: ${lag} days | History: ${history} days\n`);
console.log(`Running queries...\n`);

// Current-state QS + Lost IS + top impression share (period A with lag offset)
runQuery('Keywords QS Period', 'keywords-qs-period.gaql', 'keywords-qs-period.csv', { lagOffset: lag });

// Historical QS timeseries (weekly) — skips gracefully if <history-period data exists
runQuery('Keywords QS Timeseries', 'keywords-qs-timeseries.gaql', 'keywords-qs-timeseries.csv', { days: history, lagOffset: lag, allowEmpty: true });

// Ads for keyword-to-ad relevance gap (D07 evidence)
runQuery('RSAs', 'ads.gaql', 'qs-ads.csv', { noDateRange: true, allowEmpty: true });

// Campaign settings — bid strategy, targets
runQuery('Campaigns Settings', 'campaigns-settings.gaql', 'campaigns-settings.csv', { noDateRange: true });

// Campaign-level Impression Share metrics (authoritative source for D15)
runQuery('Campaigns IS', 'campaigns-is.gaql', 'campaigns-is.csv', { lagOffset: lag, allowEmpty: true });

// Portfolio bid strategies
runQuery('Bidding Strategies', 'bidding-strategies.gaql', 'bidding-strategies.csv', { noDateRange: true, allowEmpty: true });

// Customizers — feed Headline Test + QS-D17 Customizer Integrity (INFO-only)
runQuery('Customizer Attributes', 'customizer-attributes.gaql', 'customizer-attributes.csv', { noDateRange: true, allowEmpty: true });
runQuery('Ad Group Customizers', 'ad-group-customizers.gaql', 'ad-group-customizers.csv', { noDateRange: true, allowEmpty: true });
runQuery('Keyword Customizers', 'keyword-customizers.gaql', 'keyword-customizers.csv', { noDateRange: true, allowEmpty: true });
runQuery('Campaign Customizers', 'campaign-customizers.gaql', 'campaign-customizers.csv', { noDateRange: true, allowEmpty: true });
runQuery('Customer Customizers', 'customer-customizers.gaql', 'customer-customizers.csv', { noDateRange: true, allowEmpty: true });

const okCount = results.filter(r => r.status === 'OK').length;
const errCount = results.filter(r => r.status === 'ERROR').length;
const totalRows = results.reduce((sum, r) => sum + (typeof r.rows === 'number' ? r.rows : 0), 0);

console.log(`\n--- Done ---`);
console.log(`Queries: ${okCount} OK, ${errCount} errors`);
console.log(`Total rows: ${totalRows}`);
console.log(`Output: ${outputDir}`);

console.log('\n__RESULTS_JSON__');
console.log(JSON.stringify(results));

if (errCount > 0) {
    process.exit(1);
}
