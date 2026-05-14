#!/usr/bin/env node

/**
 * Competitive Analyst - Batch Data Pull
 *
 * Runs all competitive-analyst GAQL queries in a single process.
 * Q3 (shopping ad group IS) is conditional — only runs when Q1 results
 * contain SHOPPING campaigns with 2+ ad groups.
 *
 * Usage:
 *   node scripts/pull-all.js --period=90 --lag=8
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
const period = parseInt(cliArgs['period'] || 90);
const lag = parseInt(cliArgs['lag'] || config.searchTermAnalysis?.conversionLagDays || 8);

const gaqlDir = resolve(__dirname, 'gaql');
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

console.log(`\nCompetitive Analyst — Batch Pull`);
console.log(`Account: ${gads.clientName || customerId}`);
console.log(`Customer ID: ${customerId}`);
console.log(`Period: ${period} days | Lag: ${lag} days\n`);
console.log(`Running queries...\n`);

const lagOffset = lag;

// Q1: Campaign IS timeseries (Search + Shopping, segmented by date)
runQuery('Campaign IS Timeseries', 'campaign-is-timeseries.gaql', 'campaign-is-timeseries.csv', { lagOffset });

// Q2: Keyword IS (period aggregate, all enabled keywords with impressions)
runQuery('Keyword IS', 'keyword-is.gaql', 'keyword-is.csv', { lagOffset });

// Q3 gate: check Q1 output for Shopping campaigns with 2+ ad groups
let runQ3 = false;
const q1Path = resolve(outputDir, 'campaign-is-timeseries.csv');
if (existsSync(q1Path)) {
    try {
        const q1Content = readFileSync(q1Path, 'utf8');
        const lines = q1Content.split('\n').filter(l => l.trim());
        if (lines.length > 1) {
            const headers = lines[0].split(',').map(h => h.trim());
            const channelIdx = headers.indexOf('advertising_channel_type');
            const campaignIdIdx = headers.indexOf('campaign_id');
            const adGroupIdIdx = headers.indexOf('ad_group_id');

            if (channelIdx >= 0) {
                // Collect Shopping campaign IDs
                const shoppingCampaigns = new Set();
                // Q1 is campaign-level (no ad_group_id), so we only know campaign IDs here.
                // We'll check if any Shopping rows exist; Q3 pulls ad group detail.
                for (let i = 1; i < lines.length; i++) {
                    const cols = lines[i].split(',').map(c => c.trim());
                    if (cols[channelIdx] === 'SHOPPING') {
                        shoppingCampaigns.add(cols[campaignIdIdx]);
                    }
                }

                if (shoppingCampaigns.size > 0) {
                    // Shopping campaigns exist — run Q3 to get ad group breakdown.
                    // The analyze script will determine if any campaign has 2+ ad groups.
                    runQ3 = true;
                    console.log(`  Found ${shoppingCampaigns.size} Shopping campaign(s) — running Q3 for ad group breakdown\n`);
                } else {
                    console.log(`  No Shopping campaigns found — skipping Q3\n`);
                }
            }
        }
    } catch (e) {
        console.log(`  Could not parse Q1 output for Shopping gate — skipping Q3\n`);
    }
}

if (runQ3) {
    runQuery('Shopping AdGroup IS Timeseries', 'shopping-adgroup-is-timeseries.gaql', 'shopping-adgroup-is-timeseries.csv', { lagOffset, allowEmpty: true });
}

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
