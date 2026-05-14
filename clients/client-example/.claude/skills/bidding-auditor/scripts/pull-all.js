#!/usr/bin/env node

/**
 * Bidding Auditor - Batch Data Pull
 *
 * Runs the bidding-auditor GAQL queries needed for the requested module(s).
 * Module flag selects which queries to run; default is "all".
 *
 * Usage:
 *   node scripts/pull-all.js --period=30 --module=all
 *   node scripts/pull-all.js --module=portfolio
 *
 * Reads config from: config/ads-context.config.json
 * Outputs CSVs to:   context/google-ads/data/
 */

import { execFileSync } from 'child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
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
const period = parseInt(cliArgs['period'] || gads.dateRange || 30);
const lag = parseInt(cliArgs['lag'] || config.searchTermAnalysis?.conversionLagDays || 8);
const moduleFlag = (cliArgs['module'] || 'all').toLowerCase();

// Experiment campaigns: default = excluded (only ENABLED base campaigns).
// Pre-filtering at pull time keeps removed/ended-experiment campaigns out of every downstream analysis.
const cfgIncludeExperiments = config.biddingAudit?.includeExperiments === true;
const cliIncludeExperiments = cliArgs['include-experiments'] === true || cliArgs['include-experiments'] === 'true';
const includeExperiments = cliIncludeExperiments || cfgIncludeExperiments;
const experimentFilter = includeExperiments ? '' : `AND campaign.experiment_type = 'BASE'`;

const gaqlDir = resolve(__dirname, '..', 'reference', 'gaql');
const queryScript = resolve(projectRoot, '.claude/skills/gads-context/scripts/query.js');
const outputDir = resolve(projectRoot, 'context/google-ads/data');
const tmpDir = resolve(__dirname, '..', 'tmp', 'gaql');

mkdirSync(outputDir, { recursive: true });
mkdirSync(tmpDir, { recursive: true });

function resolveQueryFile(gaqlFile) {
    const srcPath = resolve(gaqlDir, gaqlFile);
    const raw = readFileSync(srcPath, 'utf8');
    if (!raw.includes('{EXPERIMENT_FILTER}')) return srcPath;
    const rendered = raw.replace(/\{EXPERIMENT_FILTER\}/g, experimentFilter);
    const outPath = resolve(tmpDir, gaqlFile);
    writeFileSync(outPath, rendered, 'utf8');
    return outPath;
}

const results = [];

function runQuery(label, gaqlFile, outputFile, opts = {}) {
    const args = [
        queryScript,
        `--customer-id=${customerId}`,
        `--login-customer-id=${loginCustomerId}`,
        `--query-file=${resolveQueryFile(gaqlFile)}`,
        `--output=${resolve(outputDir, outputFile)}`,
    ];

    if (opts.noDateRange) {
        args.push('--no-date-range');
    } else {
        args.push(`--days=${opts.days || period}`);
        if (opts.lagOffset !== undefined) args.push(`--lag-offset=${opts.lagOffset}`);
    }
    if (opts.allowEmpty) args.push('--allow-empty');

    try {
        const output = execFileSync('node', args, { cwd: projectRoot, encoding: 'utf8', timeout: 180000 });
        const rowsMatch = output.match(/Rows:\s*(\d+)/);
        const rows = rowsMatch ? parseInt(rowsMatch[1]) : '?';
        results.push({ label, file: outputFile, rows, status: 'OK' });
        console.log(`  ${label}: ${outputFile} (${rows} rows)`);
    } catch (error) {
        const stderr = error.stderr || error.message;
        results.push({ label, file: outputFile, rows: 0, status: 'ERROR' });
        console.error(`  ${label}: ERROR - ${String(stderr).trim().split('\n')[0]}`);
    }
}

const QUERY_MAP = {
    'campaigns-bidding-perf': () => runQuery(
        'Campaigns Bidding Perf', 'campaigns-bidding-perf.gaql', 'campaigns-bidding-perf.csv',
        { lagOffset: lag, allowEmpty: true }
    ),
    'campaigns-bidding-daily': () => runQuery(
        'Campaigns Bidding Daily', 'campaigns-bidding-daily.gaql', 'campaigns-bidding-daily.csv',
        { lagOffset: lag, allowEmpty: true }
    ),
    'bidding-strategies': () => runQuery(
        'Bidding Strategies', 'bidding-strategies.gaql', 'bidding-strategies.csv',
        { noDateRange: true, allowEmpty: true }
    ),
    'campaigns-criteria': () => runQuery(
        'Campaigns Criteria', 'campaigns-criteria.gaql', 'campaigns-criteria-bidding.csv',
        { noDateRange: true, allowEmpty: true }
    ),
    'conversion-value-rules': () => runQuery(
        'Conversion Value Rules', 'conversion-value-rules.gaql', 'conversion-value-rules.csv',
        { noDateRange: true, allowEmpty: true }
    ),
    'data-exclusions': () => runQuery(
        'Data Exclusions', 'data-exclusions.gaql', 'bidding-data-exclusions.csv',
        { noDateRange: true, allowEmpty: true }
    ),
};

const MODULE_QUERIES = {
    all:          Object.keys(QUERY_MAP),
    strategy:     ['bidding-strategies', 'campaigns-bidding-perf'],
    targets:      ['campaigns-bidding-perf', 'campaigns-bidding-daily'],
    learning:     ['bidding-strategies', 'data-exclusions', 'campaigns-bidding-perf'],
    portfolio:    ['bidding-strategies', 'campaigns-bidding-perf'],
    adjustments:  ['campaigns-criteria'],
    cpc:          ['campaigns-bidding-daily'],
    'value-rules':['conversion-value-rules'],
};

const queriesToRun = MODULE_QUERIES[moduleFlag] || MODULE_QUERIES.all;

console.log(`\nBidding Auditor — Batch Pull`);
console.log(`Account: ${gads.clientName || customerId}`);
console.log(`Customer ID: ${customerId}`);
console.log(`Period: ${period} days | Lag: ${lag} days | Module: ${moduleFlag}`);
console.log(`Experiments: ${includeExperiments ? 'INCLUDED' : 'excluded'}\n`);
console.log(`Running ${queriesToRun.length} queries...\n`);

for (const q of queriesToRun) {
    const fn = QUERY_MAP[q];
    if (fn) fn();
}

const okCount = results.filter(r => r.status === 'OK').length;
const errCount = results.filter(r => r.status === 'ERROR').length;
const totalRows = results.reduce((sum, r) => sum + (typeof r.rows === 'number' ? r.rows : 0), 0);

console.log(`\n--- Done ---`);
console.log(`Queries: ${okCount} OK, ${errCount} errors`);
console.log(`Total rows: ${totalRows}`);
console.log(`Output: ${outputDir}`);

console.log('\n__RESULTS_JSON__');
console.log(JSON.stringify(results));

if (errCount > 0) process.exit(1);
