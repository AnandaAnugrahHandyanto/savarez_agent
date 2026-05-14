#!/usr/bin/env node

/**
 * GS-D08: Weekly Schedule Pattern Consistency Validation
 *
 * Pulls hourly performance with segments.date for N days, groups by ISO week,
 * and computes per-slot consistency across weeks.
 *
 * Usage:
 *   node analyze-schedule-consistency.js \
 *     --customer-id=XXX \
 *     --login-customer-id=YYY \
 *     --days=30 \
 *     --output=context/google-ads/data/schedule-consistency.csv
 *
 * Output columns:
 *   campaign_name, day_of_week, hour, weeks_observed, weeks_high, weeks_low,
 *   weeks_dead, consistency (confirmed/unconfirmed/insufficient), avg_cpa,
 *   avg_cpa_deviation_pct
 */

import { GoogleAdsApi, enums } from 'google-ads-api';
import { writeFileSync, existsSync, mkdirSync } from 'fs';
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
    console.error('Usage: node analyze-schedule-consistency.js --customer-id=XXX --output=path.csv [--days=30]');
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

function getISOWeek(dateStr) {
    // dateStr = "YYYY-MM-DD" or "YYYYMMDD"
    const d = dateStr.includes('-') ? new Date(dateStr) : new Date(`${dateStr.slice(0,4)}-${dateStr.slice(4,6)}-${dateStr.slice(6,8)}`);
    d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() + 3 - ((d.getDay() + 6) % 7));
    const week1 = new Date(d.getFullYear(), 0, 4);
    return Math.round(((d - week1) / 86400000 - 3 + ((week1.getDay() + 6) % 7)) / 7) + 1;
}

const DOW_MAP = {
    2: 'MONDAY', 3: 'TUESDAY', 4: 'WEDNESDAY', 5: 'THURSDAY',
    6: 'FRIDAY', 7: 'SATURDAY', 8: 'SUNDAY',
    MONDAY: 'MONDAY', TUESDAY: 'TUESDAY', WEDNESDAY: 'WEDNESDAY',
    THURSDAY: 'THURSDAY', FRIDAY: 'FRIDAY', SATURDAY: 'SATURDAY', SUNDAY: 'SUNDAY'
};

function resolveDow(val) {
    return DOW_MAP[val] || enums.DayOfWeek[val] || String(val);
}

async function run() {
    const now = new Date();
    const endDate = new Date(now);
    endDate.setDate(endDate.getDate() - 1);
    const startDate = new Date(endDate);
    startDate.setDate(startDate.getDate() - days + 1);

    const query = `
        SELECT
          campaign.id, campaign.name,
          segments.date, segments.hour, segments.day_of_week,
          metrics.clicks, metrics.impressions, metrics.cost_micros,
          metrics.conversions
        FROM campaign
        WHERE segments.date BETWEEN '${formatDate(startDate)}' AND '${formatDate(endDate)}'
          AND campaign.status = 'ENABLED'
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
        writeEmpty();
        return;
    }

    // Aggregate by campaign > day_of_week > hour > week
    // Structure: { campaignName: { "DOW_HOUR": { weekN: { clicks, conv, cost } } } }
    const data = {};
    const allWeeks = new Set();

    for (const row of results) {
        const campaign = row.campaign?.name || 'Unknown';
        const date = row.segments?.date;
        const hour = row.segments?.hour;
        const dow = resolveDow(row.segments?.day_of_week);
        const week = getISOWeek(date);
        allWeeks.add(week);

        const slotKey = `${dow}_${hour}`;
        if (!data[campaign]) data[campaign] = {};
        if (!data[campaign][slotKey]) data[campaign][slotKey] = { dow, hour, weeks: {} };
        if (!data[campaign][slotKey].weeks[week]) {
            data[campaign][slotKey].weeks[week] = { clicks: 0, conversions: 0, cost: 0 };
        }

        const w = data[campaign][slotKey].weeks[week];
        w.clicks += Number(row.metrics?.clicks || 0);
        w.conversions += Number(row.metrics?.conversions || 0);
        w.cost += Number(row.metrics?.cost_micros || 0) / 1_000_000;
    }

    const totalWeeks = allWeeks.size;

    // Compute campaign-level avg CPA for deviation calc
    const campaignAvgCPA = {};
    for (const [campaign, slots] of Object.entries(data)) {
        let totalCost = 0, totalConv = 0;
        for (const slot of Object.values(slots)) {
            for (const w of Object.values(slot.weeks)) {
                totalCost += w.cost;
                totalConv += w.conversions;
            }
        }
        campaignAvgCPA[campaign] = totalConv > 0 ? totalCost / totalConv : null;
    }

    // Build output rows
    const header = 'campaign_name,day_of_week,hour,weeks_observed,weeks_high,weeks_low,weeks_dead,consistency,avg_cpa,avg_cpa_deviation_pct';
    const rows = [header];

    for (const [campaign, slots] of Object.entries(data)) {
        const avgCPA = campaignAvgCPA[campaign];

        for (const [, slot] of Object.entries(slots)) {
            const weekEntries = Object.values(slot.weeks);
            const weeksObserved = weekEntries.length;

            // Compute slot-level metrics
            let totalCost = 0, totalConv = 0, totalClicks = 0;
            let weeksHigh = 0, weeksLow = 0, weeksDead = 0;

            for (const w of weekEntries) {
                totalCost += w.cost;
                totalConv += w.conversions;
                totalClicks += w.clicks;

                if (w.clicks === 0 && w.conversions === 0) {
                    weeksDead++;
                } else if (avgCPA && w.conversions > 0) {
                    const weekCPA = w.cost / w.conversions;
                    if (weekCPA > avgCPA * 1.6) weeksHigh++;
                    if (weekCPA < avgCPA * 0.7) weeksLow++;
                } else if (w.clicks > 0 && w.conversions === 0) {
                    weeksHigh++; // Clicks but no conversions = bad week
                }
            }

            const slotCPA = totalConv > 0 ? totalCost / totalConv : null;
            let deviation = null;
            if (slotCPA !== null && avgCPA !== null && avgCPA > 0) {
                deviation = ((slotCPA - avgCPA) / avgCPA) * 100;
            }

            // Determine consistency
            let consistency;
            if (weeksObserved < 4) {
                consistency = 'insufficient';
            } else if (weeksDead >= weeksObserved * 0.75) {
                consistency = 'confirmed'; // Consistently dead
            } else if (weeksHigh >= weeksObserved * 0.75 || weeksLow >= weeksObserved * 0.75) {
                consistency = 'confirmed'; // Consistently high or low
            } else {
                consistency = 'unconfirmed';
            }

            rows.push([
                `"${campaign}"`, slot.dow, slot.hour, weeksObserved,
                weeksHigh, weeksLow, weeksDead, consistency,
                slotCPA !== null ? slotCPA.toFixed(2) : '',
                deviation !== null ? deviation.toFixed(1) : ''
            ].join(','));
        }
    }

    const outPath = resolve(_projectRoot, outputPath);
    const outDir = dirname(outPath);
    if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true });
    writeFileSync(outPath, rows.join('\n') + '\n', 'utf8');

    const confirmedCount = rows.filter(r => r.includes(',confirmed,')).length;
    console.log(`File: ${outputPath}`);
    console.log(`Rows: ${rows.length - 1}`);
    console.log(`Weeks covered: ${totalWeeks}`);
    console.log(`Confirmed patterns: ${confirmedCount}`);

    function writeEmpty() {
        const outPath = resolve(_projectRoot, outputPath);
        const outDir = dirname(outPath);
        if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true });
        writeFileSync(outPath, `${header}\n`, 'utf8');
        console.log(`File: ${outputPath}`);
        console.log('Rows: 0');
    }
}

run().catch(e => {
    console.error(`Fatal error: ${e.message}`);
    process.exit(1);
});
