#!/usr/bin/env node

/**
 * Keyword Auditor - Batch Data Pull
 *
 * Runs all 9 keyword-auditor GAQL queries in a single process,
 * eliminating per-query permission prompts.
 *
 * Usage:
 *   node scripts/pull-all.js --period=30 --lag=8
 *
 * Reads config from: config/ads-context.config.json
 * Outputs CSVs to:   context/google-ads/data/
 *
 * Delegates each query to gads-context/scripts/query.js to reuse all
 * existing logic (date handling, enum resolution, lag offset, CSV output).
 */

import { execFileSync } from 'child_process';
import { existsSync, mkdirSync, readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Find project root by walking up from script location
let projectRoot = __dirname;
while (projectRoot !== '/' && !existsSync(resolve(projectRoot, 'config'))) {
    projectRoot = resolve(projectRoot, '..');
}

// Parse CLI args
const cliArgs = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const eqIndex = arg.indexOf('=');
        acc[arg.slice(0, eqIndex).replace('--', '')] = arg.slice(eqIndex + 1);
    } else if (arg.startsWith('--')) {
        acc[arg.replace('--', '')] = true;
    }
    return acc;
}, {});

// Load config
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
        args.push(`--days=${period}`);
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
            timeout: 120000,
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

console.log(`\nKeyword Auditor — Batch Pull`);
console.log(`Account: ${gads.clientName || customerId}`);
console.log(`Customer ID: ${customerId}`);
console.log(`Period: ${period} days | Lag: ${lag} days\n`);
console.log(`Running queries...\n`);

// Period A: current window, shifted back by conversion lag
const lagA = lag;
// Period B: prior window, shifted back by lag + period
const lagB = lag + period;

// Q1: Keywords Period A (performance with metrics)
runQuery('Keywords Period A', 'keywords-period.gaql', 'keywords-periodA.csv', { lagOffset: lagA });

// Q2: Keywords Period B (prior period for tier shift)
runQuery('Keywords Period B', 'keywords-period.gaql', 'keywords-periodB.csv', { lagOffset: lagB });

// Q2a: Keywords conversions by action — Period A
runQuery('Conv by Action A', 'keywords-conversions-by-action.gaql', 'keywords-conv-by-action-periodA.csv', { lagOffset: lagA, allowEmpty: true });

// Q2b: Keywords conversions by action — Period B
runQuery('Conv by Action B', 'keywords-conversions-by-action.gaql', 'keywords-conv-by-action-periodB.csv', { lagOffset: lagB, allowEmpty: true });

// Q3: Keywords structural (no date filter)
runQuery('Keywords Structural', 'keywords-structural.gaql', 'keywords-structural.csv', { noDateRange: true });

// Q4: Campaign settings
runQuery('Campaigns Settings', 'campaigns-settings.gaql', 'campaigns-settings.csv', { noDateRange: true });

// Q4b: Portfolio bid strategies (targets when campaigns use a portfolio, not inline)
runQuery('Bidding Strategies', 'bidding-strategies.gaql', 'bidding-strategies.csv', { noDateRange: true, allowEmpty: true });

// Q5: PMax search terms
runQuery('PMax Search Terms', 'pmax-search-terms.gaql', 'pmax-search-terms.csv', { lagOffset: lagA, allowEmpty: true });

// Q6: Campaign-level negative keywords
runQuery('Negatives Campaign', 'negatives-campaign.gaql', 'negatives-campaign-kw.csv', { noDateRange: true, allowEmpty: true });

// Q7: Shared negative keyword list members
runQuery('Negatives Shared', 'negatives-shared.gaql', 'negatives-shared-kw.csv', { noDateRange: true, allowEmpty: true });

// Q8: Campaign ↔ shared negative list attachments
runQuery('Negatives Shared Links', 'negatives-shared-campaigns.gaql', 'negatives-shared-campaigns.csv', { noDateRange: true, allowEmpty: true });

// Q9: Ad group-level negative keywords
runQuery('Negatives Ad Group', 'negatives-adgroup.gaql', 'negatives-adgroup-kw.csv', { noDateRange: true, allowEmpty: true });

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

if (errCount > 0) {
    process.exit(1);
}
