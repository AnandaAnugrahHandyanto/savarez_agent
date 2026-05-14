#!/usr/bin/env node

/**
 * Google Ads Change Event Fetcher
 *
 * Queries the change_event resource to fetch all account changes
 * within a date range and outputs clean CSV.
 *
 * Usage:
 *   node fetch-changes.js \
 *     --customer-id=YOUR_CUSTOMER_ID \
 *     --login-customer-id=YOUR_LOGIN_CUSTOMER_ID \
 *     --days=30 \
 *     --output=context/account-changelog.csv
 *
 * Returns: File path and row count only (keeps context window small)
 */

import { GoogleAdsApi, enums } from 'google-ads-api';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { config } from 'dotenv';

// Find project root by walking up from script location
const __dirname = dirname(fileURLToPath(import.meta.url));
let _projectRoot = __dirname;
while (_projectRoot !== '/' && !existsSync(resolve(_projectRoot, 'config'))) {
    _projectRoot = resolve(_projectRoot, '..');
}

// Load environment variables from config/.env
config({ path: resolve(_projectRoot, 'config/.env') });

// Parse command line arguments
const args = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const eqIndex = arg.indexOf('=');
        const key = arg.slice(0, eqIndex).replace('--', '');
        const value = arg.slice(eqIndex + 1);
        if (key && value) {
            acc[key] = value;
        }
    } else if (arg.startsWith('--')) {
        acc[arg.replace('--', '')] = true;
    }
    return acc;
}, {});

const customerId = args['customer-id'];
const loginCustomerId = args['login-customer-id'];
const days = args['days'] ? parseInt(args['days']) : 30;
const outputPath = args['output'];

// Validate arguments
if (!customerId || !outputPath) {
    console.error('Error: Missing required arguments');
    console.error('');
    console.error('Usage:');
    console.error('  node fetch-changes.js \\');
    console.error('    --customer-id=YOUR_CUSTOMER_ID \\');
    console.error('    --login-customer-id=YOUR_LOGIN_CUSTOMER_ID \\');
    console.error('    --days=30 \\');
    console.error('    --output=context/account-changelog.csv');
    process.exit(1);
}

if (days > 30) {
    console.error('Warning: Google Ads change_event supports max 30-day lookback. Capping to 30 days.');
}

// Validate credentials
const clientId = process.env.GOOGLE_ADS_CLIENT_ID;
const clientSecret = process.env.GOOGLE_ADS_CLIENT_SECRET;
const developerToken = process.env.GOOGLE_ADS_DEVELOPER_TOKEN;
const refreshToken = process.env.GOOGLE_ADS_REFRESH_TOKEN;

if (!clientId || !clientSecret || !developerToken || !refreshToken) {
    console.error('Error: Missing Google Ads credentials');
    console.error('Please set the following in config/.env:');
    console.error('  GOOGLE_ADS_CLIENT_ID');
    console.error('  GOOGLE_ADS_CLIENT_SECRET');
    console.error('  GOOGLE_ADS_DEVELOPER_TOKEN');
    console.error('  GOOGLE_ADS_REFRESH_TOKEN');
    process.exit(1);
}

// Initialize Google Ads API client
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

async function getAccountTimezone() {
    const timezoneQuery = 'SELECT customer.time_zone FROM customer LIMIT 1';
    const results = await customer.query(timezoneQuery);
    return results[0]?.customer?.time_zone || 'America/Los_Angeles';
}

function calculateDateRange(numDays, timezone) {
    // Use Intl.DateTimeFormat.formatToParts for reliable timezone handling
    // (avoids the toLocaleString → new Date() roundtrip that can shift dates)
    const now = new Date();
    const parts = new Intl.DateTimeFormat('en-US', {
        timeZone: timezone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
    }).formatToParts(now);

    const year = parseInt(parts.find(p => p.type === 'year').value);
    const month = parseInt(parts.find(p => p.type === 'month').value) - 1;
    const day = parseInt(parts.find(p => p.type === 'day').value);

    // End date is today in account timezone
    const endDate = new Date(year, month, day);

    // Start date: go back (numDays - 1) days from today
    // With days=30: start = today - 29 = safely within the 30-day API limit
    const startDate = new Date(year, month, day - (numDays - 1));

    const formatDate = (date) => {
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, '0');
        const d = String(date.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
    };

    return {
        start: formatDate(startDate),
        end: formatDate(endDate)
    };
}

async function fetchChanges() {
    try {
        const timezone = await getAccountTimezone();
        const effectiveDays = Math.min(days, 30);
        const dateRange = calculateDateRange(effectiveDays, timezone);

        // Read GAQL template
        const gaqlPath = resolve(
            __dirname,
            '../references/change-event.gaql'
        );
        let query = readFileSync(gaqlPath, 'utf8').trim();

        // Replace date placeholders
        query = query.replace('{CHANGE_START}', dateRange.start);
        query = query.replace('{CHANGE_END}', dateRange.end);

        // Execute query
        const results = await customer.query(query);

        if (!results || results.length === 0) {
            console.log(`File: ${outputPath}`);
            console.log('Rows: 0');
            console.log('Note: No changes found in the specified date range.');
            writeFileSync(outputPath, '', 'utf8');
            return;
        }

        // Flatten nested objects
        function flattenRow(obj, prefix = '') {
            const flattened = {};
            for (const [key, value] of Object.entries(obj)) {
                const newKey = prefix ? `${prefix}.${key}` : key;
                if (Array.isArray(value)) {
                    if (value.length > 0 && typeof value[0] === 'object' && value[0].text !== undefined) {
                        flattened[newKey] = value.map(item => item.text).join(' | ');
                    } else if (value.every(item => typeof item === 'string')) {
                        flattened[newKey] = value.join(' | ');
                    } else {
                        flattened[newKey] = JSON.stringify(value);
                    }
                } else if (value && typeof value === 'object') {
                    Object.assign(flattened, flattenRow(value, newKey));
                } else {
                    flattened[newKey] = value;
                }
            }
            return flattened;
        }

        const flattenedResults = results.map(row => {
            // Extract old_resource and new_resource before flattening
            // (stored as JSON strings to avoid sparse column explosion)
            const oldResource = row.change_event?.old_resource;
            const newResource = row.change_event?.new_resource;

            // Deep copy and remove old/new resource to prevent recursive flattening
            const rowCopy = JSON.parse(JSON.stringify(row));
            if (rowCopy.change_event) {
                delete rowCopy.change_event.old_resource;
                delete rowCopy.change_event.new_resource;
            }

            const flattened = flattenRow(rowCopy);

            // Add old/new resource as JSON strings
            flattened['change_event.old_resource'] = oldResource && Object.keys(oldResource).length > 0
                ? JSON.stringify(oldResource) : '';
            flattened['change_event.new_resource'] = newResource && Object.keys(newResource).length > 0
                ? JSON.stringify(newResource) : '';

            return flattened;
        });

        // Resolve numeric enum values to human-readable strings
        const enumFieldMap = {
            'change_event.change_resource_type': enums.ChangeEventResourceType,
            'change_event.resource_change_operation': enums.ResourceChangeOperation,
            'change_event.client_type': enums.ChangeClientType,
        };

        for (const row of flattenedResults) {
            for (const [key, value] of Object.entries(row)) {
                if (value !== null && value !== undefined && enumFieldMap[key]) {
                    const label = enumFieldMap[key][value];
                    if (typeof label === 'string') {
                        row[key] = label;
                    }
                }
            }
        }

        // Define desired column order for readability
        const columnOrder = [
            'change_event.change_date_time',
            'change_event.user_email',
            'change_event.change_resource_type',
            'change_event.resource_change_operation',
            'change_event.client_type',
            'campaign.name',
            'ad_group.name',
            'change_event.change_resource_name',
            'change_event.changed_fields',
            'change_event.old_resource',
            'change_event.new_resource'
        ];

        // Collect all headers from results
        const headersSet = new Set();
        flattenedResults.forEach(row => {
            Object.keys(row).forEach(key => headersSet.add(key));
        });

        // Use ordered columns first, then any remaining
        const headers = [
            ...columnOrder.filter(h => headersSet.has(h)),
            ...Array.from(headersSet).filter(h => !columnOrder.includes(h)).sort()
        ];

        // Build CSV
        const csvRows = [];
        csvRows.push(headers.join(','));

        for (const row of flattenedResults) {
            const values = headers.map(header => {
                let value = row[header];
                if (value !== null && value !== undefined) {
                    value = String(value);
                    if (value.includes(',') || value.includes('"') || value.includes('\n')) {
                        value = `"${value.replace(/"/g, '""')}"`;
                    }
                } else {
                    value = '';
                }
                return value;
            });
            csvRows.push(values.join(','));
        }

        const csvContent = csvRows.join('\n');
        writeFileSync(outputPath, csvContent, 'utf8');

        console.log(`File: ${outputPath}`);
        console.log(`Rows: ${results.length}`);
        console.log(`Date range: ${dateRange.start} to ${dateRange.end}`);

    } catch (error) {
        console.error('Error fetching change events:', error.message);
        if (error.errors) {
            error.errors.forEach(err => {
                console.error(`  - ${err.error_code?.request_error || 'Unknown error'}: ${err.message}`);
            });
        }
        process.exit(1);
    }
}

fetchChanges();
