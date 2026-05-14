#!/usr/bin/env node

/**
 * Budget Auditor — Batch Data Pull
 *
 * Runs the budget-auditor GAQL queries needed for the requested module(s).
 * Default scope INCLUDES active experiment-type campaigns (they consume
 * real budget). Pass --base-only to drop them.
 *
 * Usage:
 *   node scripts/pull-all.js --period=30 --module=all
 *   node scripts/pull-all.js --module=allocation --base-only
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

// Experiment scope — DEFAULT INCLUDES active experiment variants because
// they consume real budget. Inverse of bidding-auditor's default.
// Resolution order: --base-only flag → --include-experiments=false → config.budgetAudit.includeExperiments → true.
const cfgIncludeExperiments = config.budgetAudit?.includeExperiments !== false;
const cliBaseOnly = cliArgs['base-only'] === true || cliArgs['base-only'] === 'true';
const cliIncludeExperimentsFalse = cliArgs['include-experiments'] === 'false' || cliArgs['include-experiments'] === false;
const includeExperiments = cliBaseOnly || cliIncludeExperimentsFalse ? false : cfgIncludeExperiments;
const experimentFilter = includeExperiments
    ? `AND campaign.experiment_type IN ('BASE', 'EXPERIMENT')`
    : `AND campaign.experiment_type = 'BASE'`;

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
        const firstLine = String(stderr).trim().split('\n')[0];
        // Soft-fail account-budget — typical for non-invoicing accounts.
        if (gaqlFile === 'account-budget.gaql') {
            results.push({ label, file: outputFile, rows: 0, status: 'SKIP', reason: firstLine });
            console.log(`  ${label}: SKIP (${firstLine})`);
        } else {
            results.push({ label, file: outputFile, rows: 0, status: 'ERROR' });
            console.error(`  ${label}: ERROR - ${firstLine}`);
        }
    }
}

// Pacing query needs a long enough window to compute MTD + prior-month
// run-rate. We pull 60 days; the analyzer slices MTD vs prior 30d.
const pacingWindow = 60;

const QUERY_MAP = {
    'campaign-budgets': () => runQuery(
        'Campaign Budgets', 'campaign-budgets.gaql', 'campaign-budgets.csv',
        { noDateRange: true, allowEmpty: true }
    ),
    'campaigns-budget-perf': () => runQuery(
        'Campaigns Budget Perf', 'campaigns-budget-perf.gaql', 'campaigns-budget-perf.csv',
        { lagOffset: lag, allowEmpty: true }
    ),
    'campaigns-pacing-daily': () => runQuery(
        'Campaigns Pacing Daily', 'campaigns-pacing-daily.gaql', 'campaigns-pacing-daily.csv',
        { days: pacingWindow, allowEmpty: true }
    ),
    'bidding-strategies': () => runQuery(
        'Bidding Strategies', 'bidding-strategies.gaql', 'bidding-strategies.csv',
        { noDateRange: true, allowEmpty: true }
    ),
    'account-budget': () => runQuery(
        'Account Budget', 'account-budget.gaql', 'account-budget.csv',
        { noDateRange: true, allowEmpty: true }
    ),
};

const MODULE_QUERIES = {
    all:          Object.keys(QUERY_MAP),
    limitation:   ['campaign-budgets', 'campaigns-budget-perf'],
    sufficiency:  ['campaign-budgets', 'campaigns-budget-perf', 'campaigns-pacing-daily', 'bidding-strategies'],
    pacing:       ['campaign-budgets', 'campaigns-pacing-daily', 'campaigns-budget-perf', 'account-budget'],
    allocation:   ['campaign-budgets', 'campaigns-budget-perf'],
    shared:       ['campaign-budgets', 'campaigns-budget-perf', 'bidding-strategies'],
    opportunities:['campaign-budgets', 'campaigns-budget-perf', 'campaigns-pacing-daily'],
};

const queriesToRun = MODULE_QUERIES[moduleFlag] || MODULE_QUERIES.all;

console.log(`\nBudget Auditor — Batch Pull`);
console.log(`Account: ${gads.clientName || customerId}`);
console.log(`Customer ID: ${customerId}`);
console.log(`Period: ${period} days | Lag: ${lag} days | Module: ${moduleFlag}`);
console.log(`Experiments: ${includeExperiments ? 'INCLUDED (active variants count toward spend/IS/pacing)' : 'excluded (base-only)'}\n`);
console.log(`Running ${queriesToRun.length} queries...\n`);

for (const q of queriesToRun) {
    const fn = QUERY_MAP[q];
    if (fn) fn();
}

const okCount = results.filter(r => r.status === 'OK').length;
const errCount = results.filter(r => r.status === 'ERROR').length;
const skipCount = results.filter(r => r.status === 'SKIP').length;
const totalRows = results.reduce((sum, r) => sum + (typeof r.rows === 'number' ? r.rows : 0), 0);

console.log(`\n--- Done ---`);
console.log(`Queries: ${okCount} OK, ${skipCount} skipped, ${errCount} errors`);
console.log(`Total rows: ${totalRows}`);
console.log(`Output: ${outputDir}`);

console.log('\n__RESULTS_JSON__');
console.log(JSON.stringify({ results, includeExperiments, module: moduleFlag, period, lag }));

if (errCount > 0) process.exit(1);
