#!/usr/bin/env node

/**
 * Search Term Auditor — Batch Data Pull
 *
 * Runs all search-term-auditor GAQL queries in one process,
 * eliminating per-query permission prompts.
 *
 * Usage:
 *   node scripts/pull-all.js --period=60 --ngram-period=120 --lag=14
 *   node scripts/pull-all.js --period=60 --ngram-period=120 --lag=14 --catalog-period=365
 *
 * Reads config from: config/ads-context.config.json
 * Outputs CSVs to:   context/google-ads/data/
 *
 * Delegates each query to gads-context/scripts/query.js.
 */

import { execFileSync } from 'child_process';
import { existsSync, mkdirSync, readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Walk up to project root
let projectRoot = __dirname;
while (projectRoot !== '/' && !existsSync(resolve(projectRoot, 'config'))) {
    projectRoot = resolve(projectRoot, '..');
}

const cliArgs = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const eq = arg.indexOf('=');
        acc[arg.slice(0, eq).replace('--', '')] = arg.slice(eq + 1);
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
const appConfig = JSON.parse(readFileSync(configPath, 'utf8'));
const gads = appConfig.googleAds;

if (!gads || !gads.customerId) {
    console.error('Error: googleAds.customerId missing from config');
    process.exit(1);
}

const customerId = gads.customerId;
const loginCustomerId = gads.loginCustomerId || customerId;
const mainPeriod = parseInt(cliArgs['period'] || 60);
const ngramPeriod = parseInt(cliArgs['ngram-period'] || 120);
const catalogPeriod = parseInt(cliArgs['catalog-period'] || 365);
const lag = parseInt(cliArgs['lag'] || appConfig.searchTermAnalysis?.conversionLagDays || 14);
const pullCatalog = cliArgs['pull-catalog'] === true || cliArgs['pull-catalog'] === 'true';
const includeExperiments = cliArgs['include-experiments'] === true
    || cliArgs['include-experiments'] === 'true'
    || appConfig.searchTermAnalysis?.includeExperiments === true;

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
        args.push(`--days=${opts.days ?? mainPeriod}`);
        if (opts.lagOffset !== undefined) {
            args.push(`--lag-offset=${opts.lagOffset}`);
        }
    }

    if (opts.allowEmpty) args.push('--allow-empty');
    if (includeExperiments) args.push('--include-experiments');

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

console.log(`\nSearch Term Auditor — Batch Pull`);
console.log(`Account: ${gads.clientName || customerId}`);
console.log(`Customer ID: ${customerId}`);
console.log(`Main period: ${mainPeriod}d | N-gram period: ${ngramPeriod}d | Lag: ${lag}d\n`);
console.log(`Running queries...\n`);

// Period A (current): lag offset = lag
const lagA = lag;
// Period B (prior window, for trend/drift comparison): lag + main period
const lagB = lag + mainPeriod;

// Q1: search-terms Period A (main period)
runQuery('Search Terms Period A', 'search-terms.gaql', 'search-terms-periodA.csv',
    { days: mainPeriod, lagOffset: lagA });

// Q2: search-terms Period B (prior window, trend detection)
runQuery('Search Terms Period B', 'search-terms.gaql', 'search-terms-periodB.csv',
    { days: mainPeriod, lagOffset: lagB });

// Q3: search-terms Period N (n-gram window)
runQuery('Search Terms N-gram', 'search-terms.gaql', 'search-terms-ngram.csv',
    { days: ngramPeriod, lagOffset: lagA });

// Q4: pmax-search-terms Period A
runQuery('PMax Search Terms', 'pmax-search-terms.gaql', 'pmax-search-terms.csv',
    { days: mainPeriod, lagOffset: lagA, allowEmpty: true });

// Q5: search-terms catalog (365d by default) — only if requested
if (pullCatalog) {
    runQuery('Search Terms Catalog', 'search-terms.gaql', 'search-terms-catalog.csv',
        { days: catalogPeriod, lagOffset: lagA });
}

// Q6: campaign-level negatives
runQuery('Negatives Campaign', 'negatives-campaign.gaql', 'negative-keywords-campaign.csv',
    { noDateRange: true, allowEmpty: true });

// Q7: shared-list negatives
runQuery('Negatives Shared', 'negatives-shared.gaql', 'negative-keywords-shared.csv',
    { noDateRange: true, allowEmpty: true });

// Q8: ad-group negatives
runQuery('Negatives Ad Group', 'negatives-adgroup.gaql', 'negative-keywords-adgroup.csv',
    { noDateRange: true, allowEmpty: true });

// Q9: shared-list ↔ campaign attachments
runQuery('Negatives Shared Links', 'negatives-shared-campaigns.gaql', 'negative-keywords-shared-links.csv',
    { noDateRange: true, allowEmpty: true });

// Q10: campaigns-settings (must include campaign.bidding_strategy for portfolio resolution)
runQuery('Campaigns Settings', 'campaigns-settings.gaql', 'campaigns-settings.csv',
    { noDateRange: true });

// Q11: portfolio bid strategies
runQuery('Bidding Strategies', 'bidding-strategies.gaql', 'bidding-strategies.csv',
    { noDateRange: true, allowEmpty: true });

// Q12: active positive keywords (used for routing detection on repeated negatives)
runQuery('Keywords Active', 'keywords-active.gaql', 'keywords-active.csv',
    { noDateRange: true, allowEmpty: true });

// --- Summary ---
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
