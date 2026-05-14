#!/usr/bin/env node

/**
 * Google Ads Context - Batch Query Runner
 *
 * Runs all GAQL queries from the gads-context skill in a single process,
 * eliminating the need for ~20 separate shell invocations.
 *
 * Usage:
 *   node scripts/run-all.js [--days=30]
 *
 * Reads config from: config/ads-context.config.json
 * Outputs CSVs to:   context/google-ads/data/
 *
 * Delegates each query to query.js via child_process to reuse all existing
 * logic (date handling, enum resolution, micros conversion, CSV output).
 */

import { execFileSync } from 'child_process';
import { existsSync, mkdirSync, readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Find project root
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
const days = cliArgs['days'] || gads.dateRange || 30;
const conversionActions = gads.conversionActions || [];
const refsDir = resolve(__dirname, '..', 'references');
const queryScript = resolve(__dirname, 'query.js');
const mergeScript = resolve(__dirname, 'merge-csv.js');
const outputDir = resolve(projectRoot, 'context/google-ads/data');

// Ensure output directory exists
mkdirSync(outputDir, { recursive: true });

// Results tracker
const results = [];

function runQuery(label, gaqlFile, outputFile, opts = {}) {
    const args = [
        queryScript,
        `--customer-id=${customerId}`,
        `--login-customer-id=${loginCustomerId}`,
        `--query-file=${resolve(refsDir, gaqlFile)}`,
        `--output=${resolve(outputDir, outputFile)}`,
    ];

    if (opts.noDateRange) {
        args.push('--no-date-range');
    } else {
        args.push(`--days=${days}`);
    }

    if (opts.allowEmpty) {
        args.push('--allow-empty');
    }

    if (opts.conversionAction) {
        // For conversion queries, read the GAQL and replace placeholder before passing
        // We use --query instead of --query-file for this case
        const gaqlContent = readFileSync(resolve(refsDir, gaqlFile), 'utf8')
            .trim()
            .replace(/\{CONVERSION_ACTION_NAME\}/g, opts.conversionAction);
        // Remove --query-file and add --query
        const queryFileIdx = args.findIndex(a => a.startsWith('--query-file='));
        args[queryFileIdx] = `--query=${gaqlContent}`;
    }

    try {
        const output = execFileSync('node', args, {
            cwd: projectRoot,
            encoding: 'utf8',
            timeout: 120000,
        });

        // Parse rows from output
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

console.log(`\nGoogle Ads Context — Batch Pull`);
console.log(`Account: ${gads.clientName || customerId}`);
console.log(`Customer ID: ${customerId}`);
console.log(`Days: ${days}\n`);
console.log(`Running queries...\n`);

// --- Core queries (with date range) ---
runQuery('Campaigns', 'campaigns.gaql', 'campaigns.csv');
runQuery('Bidding Strategies', 'bidding-strategies.gaql', 'bidding-strategies.csv', { noDateRange: true, allowEmpty: true });
runQuery('Ad Groups', 'adgroups.gaql', 'adgroups.csv');
runQuery('Keywords', 'keywords.gaql', 'keywords.csv');
runQuery('Ads', 'ads.gaql', 'ads.csv');
runQuery('Search Terms', 'search-terms.gaql', 'search-terms.csv');
runQuery('Device Performance', 'device-performance.gaql', 'device-performance.csv');

// --- Negative keywords (no date range, current state) ---
runQuery('Neg KW (Campaign)', 'negative-keywords-campaign.gaql', 'negative-keywords-campaign.csv', { noDateRange: true });
runQuery('Neg KW (Ad Group)', 'negative-keywords-adgroup.gaql', 'negative-keywords-adgroup.csv', { noDateRange: true });
runQuery('Neg KW (Shared)', 'negative-keywords-shared.gaql', 'negative-keywords-shared.csv', { noDateRange: true });
runQuery('Neg KW (Shared Links)', 'negative-keywords-shared-links.gaql', 'negative-keywords-shared-links.csv', { noDateRange: true });

// --- Conversion actions (loop + merge) ---
if (conversionActions.length > 0) {
    console.log(`\n  Conversion actions (${conversionActions.length})...`);
    const convFiles = [];
    for (const action of conversionActions) {
        const safeAction = action.replace(/[^a-zA-Z0-9-_]/g, '_');
        const convFile = `conv_${safeAction}.csv`;
        runQuery(`Conv: ${action}`, 'conversions.gaql', convFile, {
            noDateRange: true,
            conversionAction: action,
        });
        convFiles.push(resolve(outputDir, convFile));
    }

    // Merge conversion files
    const existingConvFiles = convFiles.filter(f => existsSync(f) && readFileSync(f, 'utf8').trim().length > 0);
    if (existingConvFiles.length > 0) {
        try {
            const mergeOutput = execFileSync('node', [
                mergeScript,
                `--input=${existingConvFiles.join(',')}`,
                `--output=${resolve(outputDir, 'conversions.csv')}`,
            ], { cwd: projectRoot, encoding: 'utf8', timeout: 30000 });

            const rowsMatch = mergeOutput.match(/Rows:\s*(\d+)/);
            const rows = rowsMatch ? parseInt(rowsMatch[1]) : '?';
            results.push({ label: 'Conversions (merged)', file: 'conversions.csv', rows, status: 'OK' });
            console.log(`  Conversions (merged): conversions.csv (${rows} rows)`);
        } catch (error) {
            results.push({ label: 'Conversions (merged)', file: 'conversions.csv', rows: 0, status: 'ERROR' });
            console.error(`  Conversions (merged): ERROR - ${(error.stderr || error.message).trim().split('\n')[0]}`);
        }
    }
} else {
    console.log('\n  No conversion actions configured, skipping conversions');
}

// --- Optional queries (--allow-empty) ---
console.log('');
runQuery('Assets', 'assets.gaql', 'assets.csv', { noDateRange: true, allowEmpty: true });
runQuery('Assets (Campaign)', 'assets-campaign-performance.gaql', 'assets-campaign-performance.csv', { allowEmpty: true });
runQuery('Assets (Ad Group)', 'assets-adgroup-performance.gaql', 'assets-adgroup-performance.csv', { allowEmpty: true });
runQuery('Audiences (Campaign)', 'audiences-campaign.gaql', 'audiences-campaign.csv', { allowEmpty: true });
runQuery('Audiences (Ad Group)', 'audiences-adgroup.gaql', 'audiences-adgroup.csv', { allowEmpty: true });
runQuery('Geo (Targeted)', 'geo-targeted.gaql', 'geo-targeted.csv', { allowEmpty: true });
runQuery('Geo (User Location)', 'geo-user-location.gaql', 'geo-user-location.csv', { allowEmpty: true });
runQuery('Shopping Performance', 'shopping-performance.gaql', 'shopping-performance.csv', { allowEmpty: true });
runQuery('Shopping Products', 'shopping-products.gaql', 'shopping-products.csv', { noDateRange: true, allowEmpty: true });
runQuery('Product Groups', 'product-groups.gaql', 'product-groups.csv', { allowEmpty: true });

// --- Summary ---
const okCount = results.filter(r => r.status === 'OK').length;
const errCount = results.filter(r => r.status === 'ERROR').length;
const totalRows = results.reduce((sum, r) => sum + (typeof r.rows === 'number' ? r.rows : 0), 0);

console.log(`\n--- Done ---`);
console.log(`Queries: ${okCount} OK, ${errCount} errors`);
console.log(`Total rows: ${totalRows}`);
console.log(`Output: ${outputDir}`);

// Output JSON summary for Claude to parse
console.log('\n__RESULTS_JSON__');
console.log(JSON.stringify(results));

if (errCount > 0) {
    process.exit(1);
}
