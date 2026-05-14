#!/usr/bin/env node

/**
 * Google Ads Mutation Script — Geo-Schedule Optimizer
 *
 * Applies geo/schedule/demographic bid modifier changes to Google Ads
 * via the API. Always run in dry-run mode first, then live after approval.
 *
 * Usage:
 *   node mutate.js \
 *     --customer-id=XXXX \
 *     --login-customer-id=YYYY \
 *     --operations-file=path/to/operations.json \
 *     --mode=dry-run|live \
 *     --max-ops=50 \
 *     --allow-remove
 *
 * Flags:
 *   --customer-id          Google Ads customer ID (required)
 *   --login-customer-id    MCC login customer ID (optional)
 *   --operations-file      Path to operations.json (required)
 *   --mode                 dry-run or live (required, no default)
 *   --max-ops=N            Max operations per run (default: 50)
 *   --allow-remove         Enable remove operations (off by default)
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

// Load environment variables from config/.env
config({ path: resolve(_projectRoot, 'config/.env') });

// Parse command line arguments
const args = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const eqIndex = arg.indexOf('=');
        const key = arg.slice(0, eqIndex).replace('--', '');
        const value = arg.slice(eqIndex + 1);
        if (key && value) acc[key] = value;
    } else if (arg.startsWith('--')) {
        acc[arg.replace('--', '')] = true;
    }
    return acc;
}, {});

const customerId = args['customer-id'];
const loginCustomerId = args['login-customer-id'];
const operationsFile = args['operations-file'];
const mode = args['mode'];
const maxOps = parseInt(args['max-ops'] || '50');
const allowRemove = args['allow-remove'] === true;

// ── Validation ──────────────────────────────────────────────────────

if (!customerId || !operationsFile || !mode) {
    console.error('Error: Missing required arguments');
    console.error('');
    console.error('Usage:');
    console.error('  node mutate.js \\');
    console.error('    --customer-id=YOUR_CUSTOMER_ID \\');
    console.error('    --login-customer-id=YOUR_LOGIN_CUSTOMER_ID \\');
    console.error('    --operations-file=path/to/operations.json \\');
    console.error('    --mode=dry-run|live \\');
    console.error('    --max-ops=50 \\');
    console.error('    --allow-remove');
    process.exit(1);
}

if (mode !== 'dry-run' && mode !== 'live') {
    console.error(`Error: --mode must be "dry-run" or "live" (got "${mode}")`);
    process.exit(1);
}

// Validate credentials
const clientId = process.env.GOOGLE_ADS_CLIENT_ID;
const clientSecret = process.env.GOOGLE_ADS_CLIENT_SECRET;
const developerToken = process.env.GOOGLE_ADS_DEVELOPER_TOKEN;
const refreshToken = process.env.GOOGLE_ADS_REFRESH_TOKEN;

if (!clientId || !clientSecret || !developerToken || !refreshToken) {
    console.error('Error: Missing Google Ads credentials in config/.env');
    process.exit(1);
}

// ── Load operations ─────────────────────────────────────────────────

const opsPath = resolve(_projectRoot, operationsFile);
if (!existsSync(opsPath)) {
    console.error(`Error: Operations file not found: ${opsPath}`);
    process.exit(1);
}

let opsData;
try {
    opsData = JSON.parse(readFileSync(opsPath, 'utf8'));
} catch (e) {
    console.error(`Error: Invalid JSON in operations file: ${e.message}`);
    process.exit(1);
}

const operations = opsData.operations || [];
if (operations.length === 0) {
    console.log('No operations to apply.');
    process.exit(0);
}

// ── Safety rails ────────────────────────────────────────────────────

// Max operations cap
if (operations.length > maxOps) {
    console.error(`Error: ${operations.length} operations exceeds max-ops limit of ${maxOps}`);
    console.error(`Use --max-ops=${operations.length} to override`);
    process.exit(1);
}

// Check for remove operations
const removeOps = operations.filter(op => op.type === 'remove');
if (removeOps.length > 0 && !allowRemove) {
    console.error(`Error: ${removeOps.length} remove operations found but --allow-remove not set`);
    console.error('Add --allow-remove to enable remove operations');
    process.exit(1);
}

// Bid modifier bounds check (-90% to +900%, with dimension-aware -100% support)
// Only device and demographic criteria support bid_modifier=0.0 (-100%).
// Ad schedule and location criteria minimum is 0.1 (-90%).
const ALLOWS_ZERO = new Set(['device', 'age_range', 'gender', 'income_range']);
for (const op of operations) {
    if (op.fields?.bid_modifier !== undefined) {
        const mod = op.fields.bid_modifier;
        const dim = op.meta?.dimension || '';
        if (mod === 0.0 && !ALLOWS_ZERO.has(dim)) {
            console.error(`Error: bid_modifier 0.0 (-100%) is not allowed for ${dim} criteria`);
            console.error(`  Ad schedule minimum is 0.1 (-90%). Location exclusions use negative=true.`);
            console.error(`Operation: ${JSON.stringify(op.meta)}`);
            process.exit(1);
        }
        if (mod < 0.1 && mod !== 0.0) {
            console.error(`Error: bid_modifier ${mod} is below -90% (0.1) minimum`);
            console.error(`Operation: ${JSON.stringify(op.meta)}`);
            process.exit(1);
        }
        if (mod > 10.0) {
            console.error(`Error: bid_modifier ${mod} exceeds +900% (10.0) maximum`);
            console.error(`Operation: ${JSON.stringify(op.meta)}`);
            process.exit(1);
        }
    }
}

// Campaign count guard
const campaignsAffected = new Set(operations.map(op => op.meta?.campaign).filter(Boolean));
if (campaignsAffected.size > 5) {
    console.log(`WARNING: Operations touch ${campaignsAffected.size} campaigns (>5). Proceeding anyway.`);
}

// ── Initialize API client ───────────────────────────────────────────

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

// ── Build mutation resources ────────────────────────────────────────

function buildMutateOperation(op) {
    const entity = op.resource || 'campaign_criterion';

    if (op.type === 'update') {
        const updateMask = Object.keys(op.fields || {});
        return {
            entity,
            operation: 'update',
            resource: {
                resource_name: op.resource_name,
                ...op.fields,
            },
            update_mask: { paths: updateMask },
        };
    }

    if (op.type === 'create') {
        return {
            entity,
            operation: 'create',
            resource: op.fields,
        };
    }

    if (op.type === 'remove') {
        // google-ads-api reads mutation.resource and wraps it as { remove: resource }.
        // For remove ops the protobuf expects a resource_name string under `resource`.
        return {
            entity,
            operation: 'remove',
            resource: op.resource_name,
        };
    }

    throw new Error(`Unknown operation type: ${op.type}`);
}

// ── Group operations by campaign ────────────────────────────────────

function groupByCampaign(ops) {
    const groups = {};
    for (const op of ops) {
        const campaign = op.meta?.campaign || 'Unknown';
        if (!groups[campaign]) groups[campaign] = [];
        groups[campaign].push(op);
    }
    return groups;
}

// ── Format dry-run table ────────────────────────────────────────────

function formatModifier(value) {
    if (value === undefined || value === null) return '—';
    if (value === 0.0) return '-100%';
    const pct = Math.round((value - 1) * 100);
    if (pct === 0) return '+0%';
    return pct > 0 ? `+${pct}%` : `${pct}%`;
}

function formatDryRunTable(ops) {
    const groups = groupByCampaign(ops);
    const lines = [];
    lines.push(`## Proposed Changes (DRY RUN)`);
    lines.push('');

    let idx = 0;
    for (const [campaign, campaignOps] of Object.entries(groups)) {
        lines.push(`### Campaign: ${campaign}`);
        lines.push('');
        lines.push('| # | Action | Dimension | Target | Current | Proposed | Rationale |');
        lines.push('|---|--------|-----------|--------|---------|----------|-----------|');

        for (const op of campaignOps) {
            idx++;
            const m = op.meta || {};
            let action = op.type === 'create' ? 'Create' : op.type === 'remove' ? 'Remove' : 'Update';
            if (m.dimension === 'location_exclusion') action = 'Exclude location';
            if (op.fields?.bid_modifier === 0.0 && op.type !== 'remove') action = 'Pause (-100%)';
            if (op.type === 'update' && op.fields?.bid_modifier !== undefined) action = 'Update modifier';

            const dimension = m.dimension || '—';
            const target = m.target || '—';
            const current = formatModifier(m.previous_value);
            const proposed = op.type === 'remove' ? 'Removed' : formatModifier(op.fields?.bid_modifier ?? m.new_value);
            const rationale = m.rationale || '—';

            lines.push(`| ${idx} | ${action} | ${dimension} | ${target} | ${current} | ${proposed} | ${rationale} |`);
        }
        lines.push('');
    }

    lines.push(`Total operations: ${ops.length}`);
    lines.push(`Campaigns affected: ${Object.keys(groups).length}`);
    lines.push('');
    lines.push('These changes have NOT been applied.');
    lines.push('');
    lines.push('Ready to apply? (yes / no)');

    return lines.join('\n');
}

// ── Execute ─────────────────────────────────────────────────────────

async function run() {
    if (mode === 'dry-run') {
        // Build and validate all operations locally first
        const mutateOps = [];
        for (const op of operations) {
            try {
                mutateOps.push(buildMutateOperation(op));
            } catch (e) {
                console.error(`Error building operation: ${e.message}`);
                console.error(`Operation: ${JSON.stringify(op.meta)}`);
                process.exit(1);
            }
        }

        // Server-side validation via validate_only — catches API errors without applying
        try {
            await customer.mutateResources(mutateOps, { validate_only: true });
            console.log('API validation: PASSED (all operations are valid)\n');
        } catch (e) {
            const errMsg = e.errors?.[0]?.message || e.message || String(e);
            console.error(`API validation: FAILED — ${errMsg}\n`);
        }

        console.log(formatDryRunTable(operations));
        return;
    }

    // ── Live mode ───────────────────────────────────────────────────
    const groups = groupByCampaign(operations);
    const results = { applied: 0, failed: 0, errors: [] };

    for (const [campaign, campaignOps] of Object.entries(groups)) {
        const mutateOps = campaignOps.map(buildMutateOperation);

        try {
            await customer.mutateResources(mutateOps);
            results.applied += campaignOps.length;
            console.log(`OK: ${campaignOps.length} operations applied for "${campaign}"`);
        } catch (e) {
            results.failed += campaignOps.length;
            const errMsg = e.errors?.[0]?.message || e.message || String(e);
            results.errors.push({ campaign, count: campaignOps.length, error: errMsg });
            console.error(`FAILED: ${campaignOps.length} operations for "${campaign}": ${errMsg}`);
        }
    }

    // ── Summary ─────────────────────────────────────────────────────
    console.log('');
    console.log(`## Results`);
    console.log('');
    console.log(`${results.applied}/${operations.length} operations applied successfully.`);

    if (results.failed > 0) {
        console.log('');
        console.log(`${results.failed} operations failed:`);
        for (const err of results.errors) {
            console.log(`  - ${err.campaign} (${err.count} ops): ${err.error}`);
        }
    }

    // ── Write changelog ─────────────────────────────────────────────
    const changelogPath = resolve(_projectRoot, 'context/analysis/geo-schedule-changelog.md');
    const date = new Date().toISOString().split('T')[0];
    const changelogDir = dirname(changelogPath);
    if (!existsSync(changelogDir)) mkdirSync(changelogDir, { recursive: true });

    const entry = [];
    entry.push(`## ${date} — Geo-Schedule Optimizer`);
    entry.push('');
    entry.push(`**Mode:** live | **Account:** ${customerId}`);
    entry.push(`**Result:** ${results.applied}/${operations.length} applied`);
    entry.push('');
    entry.push('| Campaign | Action | Dimension | Target | Before | After | Status |');
    entry.push('|----------|--------|-----------|--------|--------|-------|--------|');

    const failedCampaigns = new Set(results.errors.map(e => e.campaign));
    for (const op of operations) {
        const m = op.meta || {};
        const status = failedCampaigns.has(m.campaign) ? 'FAILED' : 'OK';
        const before = formatModifier(m.previous_value);
        const after = op.type === 'remove' ? 'Removed' : formatModifier(op.fields?.bid_modifier ?? m.new_value);
        entry.push(`| ${m.campaign || '—'} | ${op.type} | ${m.dimension || '—'} | ${m.target || '—'} | ${before} | ${after} | ${status} |`);
    }
    entry.push('');

    // Append to changelog
    let existing = '';
    if (existsSync(changelogPath)) {
        existing = readFileSync(changelogPath, 'utf8');
    } else {
        existing = '# Geo-Schedule Optimizer Changelog\n\n';
    }
    writeFileSync(changelogPath, existing + entry.join('\n') + '\n', 'utf8');
    console.log(`\nChanges logged to context/analysis/geo-schedule-changelog.md`);
}

run().catch(e => {
    console.error(`Fatal error: ${e.message}`);
    process.exit(1);
});
