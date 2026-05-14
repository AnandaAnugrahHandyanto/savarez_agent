#!/usr/bin/env node

/**
 * GS-D12: Year-over-Year Geographic Performance Comparison
 *
 * Pulls geo performance for the current period and the same period last year,
 * computes per-location YoY CPA deviation, and outputs a summary CSV.
 *
 * Usage:
 *   node analyze-geo-seasonal.js \
 *     --customer-id=XXX \
 *     --login-customer-id=YYY \
 *     --days=30 \
 *     --output=context/google-ads/data/geo-seasonal-comparison.csv
 *
 * Output columns:
 *   location, current_clicks, current_conversions, current_cpa,
 *   prior_year_clicks, prior_year_conversions, prior_year_cpa,
 *   yoy_deviation_pct, verdict (WARN/PASS/SKIP)
 *
 * If the account has <12 months of data, outputs header + "insufficient_data" flag.
 */

import { GoogleAdsApi, enums } from 'google-ads-api';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { config } from 'dotenv';

// Find project root by walking up from script location
const __dirname = dirname(fileURLToPath(import.meta.url));
let _projectRoot = __dirname;
while (_projectRoot !== '/' && !existsSync(resolve(_projectRoot, 'config'))) {
    _projectRoot = resolve(_projectRoot, '..');
}

config({ path: resolve(_projectRoot, 'config/.env') });

// Parse args
const args = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const eqIndex = arg.indexOf('=');
        const key = arg.slice(0, eqIndex).replace('--', '');
        const value = arg.slice(eqIndex + 1);
        if (key && value) acc[key] = value;
    }
    return acc;
}, {});

const customerId = args['customer-id'];
const loginCustomerId = args['login-customer-id'];
const days = parseInt(args['days'] || '30');
const outputPath = args['output'];

if (!customerId || !outputPath) {
    console.error('Usage: node analyze-geo-seasonal.js --customer-id=XXX --output=path.csv [--days=30]');
    process.exit(1);
}

const clientId = process.env.GOOGLE_ADS_CLIENT_ID;
const clientSecret = process.env.GOOGLE_ADS_CLIENT_SECRET;
const developerToken = process.env.GOOGLE_ADS_DEVELOPER_TOKEN;
const refreshToken = process.env.GOOGLE_ADS_REFRESH_TOKEN;

if (!clientId || !clientSecret || !developerToken || !refreshToken) {
    console.error('Error: Missing Google Ads credentials in config/.env');
    process.exit(1);
}

const client = new GoogleAdsApi({
    client_id: clientId,
    client_secret: clientSecret,
    developer_token: developerToken,
});

const customer = client.Customer({
    customer_id: customerId,
    login_customer_id: loginCustomerId || customerId,
    refresh_token: refreshToken,
});

function formatDate(d) {
    return d.toISOString().split('T')[0].replace(/-/g, '');
}

function escapeCSV(val) {
    const s = String(val ?? '');
    if (s.includes(',') || s.includes('"') || s.includes('\n')) {
        return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
}

async function run() {
    // Calculate date ranges
    const now = new Date();
    const endDate = new Date(now);
    endDate.setDate(endDate.getDate() - 1); // yesterday

    const startDate = new Date(endDate);
    startDate.setDate(startDate.getDate() - days + 1);

    // Same period last year
    const priorEndDate = new Date(endDate);
    priorEndDate.setFullYear(priorEndDate.getFullYear() - 1);
    const priorStartDate = new Date(startDate);
    priorStartDate.setFullYear(priorStartDate.getFullYear() - 1);

    const query = `
        SELECT
          geographic_view.country_criterion_id,
          geographic_view.location_type,
          segments.date,
          metrics.clicks, metrics.impressions, metrics.cost_micros,
          metrics.conversions, metrics.conversions_value
        FROM geographic_view
        WHERE segments.date BETWEEN '${formatDate(priorStartDate)}' AND '${formatDate(endDate)}'
          AND campaign.experiment_type != 'EXPERIMENT'
          AND metrics.impressions > 0
    `;

    let results;
    try {
        results = await customer.query(query);
    } catch (e) {
        console.error(`API error: ${e.message}`);
        process.exit(1);
    }

    if (!results || results.length === 0) {
        writeInsufficientData();
        return;
    }

    // Split results into current period and prior year
    const currentStart = formatDate(startDate);
    const currentEnd = formatDate(endDate);
    const priorStart = formatDate(priorStartDate);
    const priorEnd = formatDate(priorEndDate);

    const currentData = {};
    const priorData = {};
    let hasPriorData = false;

    for (const row of results) {
        const date = row.segments?.date?.replace(/-/g, '');
        const locationId = row.geographic_view?.country_criterion_id;
        const locationType = enums.GeoTargetingType[row.geographic_view?.location_type] || row.geographic_view?.location_type;
        const key = `${locationId}_${locationType}`;

        const metrics = {
            clicks: Number(row.metrics?.clicks || 0),
            conversions: Number(row.metrics?.conversions || 0),
            cost: Number(row.metrics?.cost_micros || 0) / 1_000_000,
        };

        if (date >= currentStart && date <= currentEnd) {
            if (!currentData[key]) currentData[key] = { locationId, locationType, clicks: 0, conversions: 0, cost: 0 };
            currentData[key].clicks += metrics.clicks;
            currentData[key].conversions += metrics.conversions;
            currentData[key].cost += metrics.cost;
        } else if (date >= priorStart && date <= priorEnd) {
            hasPriorData = true;
            if (!priorData[key]) priorData[key] = { clicks: 0, conversions: 0, cost: 0 };
            priorData[key].clicks += metrics.clicks;
            priorData[key].conversions += metrics.conversions;
            priorData[key].cost += metrics.cost;
        }
    }

    if (!hasPriorData) {
        writeInsufficientData();
        return;
    }

    // Build comparison rows
    const header = 'location,location_type,current_clicks,current_conversions,current_cpa,prior_year_clicks,prior_year_conversions,prior_year_cpa,yoy_deviation_pct,verdict';
    const rows = [header];

    for (const [key, cur] of Object.entries(currentData)) {
        const prior = priorData[key];
        const curCPA = cur.conversions > 0 ? cur.cost / cur.conversions : null;

        if (!prior || prior.conversions === 0) {
            // No prior year data for this location
            rows.push([
                escapeCSV(cur.locationId), escapeCSV(cur.locationType),
                cur.clicks, cur.conversions, curCPA !== null ? curCPA.toFixed(2) : '',
                prior?.clicks || 0, 0, '',
                '', 'SKIP'
            ].join(','));
            continue;
        }

        const priorCPA = prior.cost / prior.conversions;
        let deviation = null;
        let verdict = 'PASS';

        if (curCPA !== null && priorCPA > 0) {
            deviation = ((curCPA - priorCPA) / priorCPA) * 100;
            if (Math.abs(deviation) > 30) verdict = 'WARN';
        } else if (curCPA === null && prior.conversions > 0) {
            verdict = 'WARN'; // Lost all conversions YoY
            deviation = 100;
        }

        rows.push([
            escapeCSV(cur.locationId), escapeCSV(cur.locationType),
            cur.clicks, cur.conversions, curCPA !== null ? curCPA.toFixed(2) : '',
            prior.clicks, prior.conversions, priorCPA.toFixed(2),
            deviation !== null ? deviation.toFixed(1) : '', verdict
        ].join(','));
    }

    const outPath = resolve(_projectRoot, outputPath);
    const outDir = dirname(outPath);
    if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true });
    writeFileSync(outPath, rows.join('\n') + '\n', 'utf8');

    const warnCount = rows.filter(r => r.endsWith('WARN')).length;
    console.log(`File: ${outputPath}`);
    console.log(`Rows: ${rows.length - 1}`);
    console.log(`WARN locations: ${warnCount}`);

    function writeInsufficientData() {
        const outPath = resolve(_projectRoot, outputPath);
        const outDir = dirname(outPath);
        if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true });
        writeFileSync(outPath, `${header}\n# insufficient_data — account has <12 months of geo data\n`, 'utf8');
        console.log(`File: ${outputPath}`);
        console.log('Rows: 0');
        console.log('Status: insufficient_data');
    }
}

run().catch(e => {
    console.error(`Fatal error: ${e.message}`);
    process.exit(1);
});
