#!/usr/bin/env node

/**
 * Google Ads Mutation Script — Keyword Optimizer
 *
 * Applies keyword mutations: pause, match type swaps (remove + create),
 * cross-negatives, and duplicate resolution.
 *
 * Operation ordering:
 *   1. Creates (negatives) — cross-negatives must exist before pauses
 *   2. Removes — old match type keywords (part of E03 swap)
 *   3. Creates (positive) — new match type keywords (part of E03 swap)
 *   4. Updates (pause) — pause zombies, villains, duplicates last
 *
 * Usage:
 *   node mutate.js \
 *     --customer-id=XXXX \
 *     --login-customer-id=YYYY \
 *     --operations-file=path/to/operations.json \
 *     --mode=dry-run|live \
 *     --max-ops=100 \
 *     --allow-remove
 */

import { GoogleAdsApi, enums } from 'google-ads-api';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { config } from 'dotenv';

// Find project root
const __dirname = dirname(fileURLToPath(import.meta.url));
let _projectRoot = __dirname;
while (_projectRoot !== '/' && !existsSync(resolve(_projectRoot, 'config'))) {
    _projectRoot = resolve(_projectRoot, '..');
}

config({ path: resolve(_projectRoot, 'config/.env') });

// Parse CLI args
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
const maxOps = parseInt(args['max-ops'] || '100');
const allowRemove = args['allow-remove'] === true;
const confirmPortfolio = args['confirm-portfolio'] === true;
const BATCH_SIZE = 200;

// Bid strategy types supported by KW-E08 (campaign-level target updates)
const SUPPORTED_BID_STRATEGY_TYPES = new Set([
    'TARGET_CPA',
    'TARGET_ROAS',
    'MAXIMIZE_CONVERSIONS',
    'MAXIMIZE_CONVERSION_VALUE',
]);

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
    console.error('    --max-ops=100 \\');
    console.error('    --allow-remove \\');
    console.error('    --confirm-portfolio');
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

if (operations.length > maxOps) {
    console.error(`Error: ${operations.length} operations exceeds max-ops limit of ${maxOps}`);
    console.error(`Use --max-ops=${operations.length} to override`);
    process.exit(1);
}

const removeOps = operations.filter(op => op.type === 'remove');
if (removeOps.length > 0 && !allowRemove) {
    console.error(`Error: ${removeOps.length} remove operations found but --allow-remove not set`);
    console.error('Match type swaps require --allow-remove because they remove the old keyword.');
    process.exit(1);
}

// Status change guard: only allow PAUSED, never REMOVED
for (const op of operations) {
    if (op.type === 'update' && op.resource === 'ad_group_criterion' && op.fields?.status && op.fields.status !== 'PAUSED') {
        console.error(`Error: Status change to "${op.fields.status}" not allowed. Only PAUSED is permitted.`);
        console.error(`Keyword: ${op.meta?.target || 'unknown'}`);
        process.exit(1);
    }
}

// KW-E08 campaign update guards
const campaignOps = operations.filter(op => op.resource === 'campaign');
for (const op of campaignOps) {
    // Only updates allowed — never create/remove a campaign via this skill
    if (op.type !== 'update') {
        console.error(`Error: campaign resource only supports 'update' (got '${op.type}'). Campaign creation/removal is out of scope.`);
        console.error(`Target: ${op.meta?.target || 'unknown'}`);
        process.exit(1);
    }

    // Bid strategy type must be supported
    const bidType = op.meta?.bid_strategy_type;
    if (!bidType || !SUPPORTED_BID_STRATEGY_TYPES.has(bidType)) {
        console.error(`Error: campaign '${op.meta?.target || 'unknown'}' has unsupported bid strategy type '${bidType || 'missing'}'.`);
        console.error(`Supported: ${Array.from(SUPPORTED_BID_STRATEGY_TYPES).join(', ')}`);
        console.error('Route to /strategy-specialist for manual review.');
        process.exit(1);
    }

    // Only target fields may be mutated — never the bid strategy type itself
    const allowedFieldPaths = new Set([
        'target_cpa.target_cpa_micros',
        'target_roas.target_roas',
        'maximize_conversions.target_cpa_micros',
        'maximize_conversion_value.target_roas',
    ]);
    const fieldPaths = flattenKeys(op.fields || {});
    for (const path of fieldPaths) {
        if (!allowedFieldPaths.has(path)) {
            console.error(`Error: campaign field '${path}' is not allowed. KW-E08 only mutates bid strategy targets.`);
            console.error(`Target: ${op.meta?.target || 'unknown'}`);
            process.exit(1);
        }
    }

    // Portfolio block: if meta.is_portfolio true, require --confirm-portfolio
    if (op.meta?.is_portfolio === true && !confirmPortfolio) {
        const shared = op.meta?.portfolio_shared_campaigns || [];
        console.error(`Error: campaign '${op.meta?.target}' uses a portfolio bid strategy shared across ${shared.length} campaign(s):`);
        for (const c of shared) console.error(`  - ${c}`);
        console.error('Portfolio mutations affect every campaign in the portfolio.');
        console.error('Re-run with --confirm-portfolio after reviewing the shared-scope warning.');
        process.exit(1);
    }
}

function flattenKeys(obj, prefix = '') {
    const paths = [];
    for (const [key, val] of Object.entries(obj)) {
        const path = prefix ? `${prefix}.${key}` : key;
        if (val && typeof val === 'object' && !Array.isArray(val)) {
            paths.push(...flattenKeys(val, path));
        } else {
            paths.push(path);
        }
    }
    return paths;
}

const entityTypes = new Set(operations.map(op => op.resource).filter(Boolean));

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

// ── Operation ordering ──────────────────────────────────────────────
// Keyword optimizer ordering per §9 of the plan:
//   1. Creates (negatives) — cross-negatives before pauses
//   2. Removes — old match type keywords (E03 swap step 1)
//   3. Creates (positive) — new match type keywords (E03 swap step 2)
//   4. Updates (pause) — pause zombies, villains, duplicates

const ENTITY_ORDER = [
    'ad_group_criterion',    // Keywords (positive + negative)
    'campaign_criterion',    // Campaign-level negatives
    'shared_criterion',      // Shared negative list items
    'campaign',              // Campaign-level bid strategy target updates (KW-E08)
];

const ENTITY_PATH_MAP = {
    'ad_group_criterion': 'adGroupCriteria',
    'campaign_criterion': 'campaignCriteria',
    'shared_criterion': 'sharedCriteria',
    'campaign': 'campaigns',
};

const ENTITY_RESULT_KEY = {
    'ad_group_criterion': 'ad_group_criterion_result',
    'campaign_criterion': 'campaign_criterion_result',
    'shared_criterion': 'shared_criterion_result',
    'campaign': 'campaign_result',
};

function extractResourceName(response, j, entity) {
    const resultKey = ENTITY_RESULT_KEY[entity];
    return response?.results?.[j]?.[resultKey]?.resource_name
        ?? response?.results?.[j]?.resource_name;
}

function sortOperations(ops) {
    // Custom sort order:
    //   0. Campaign bid raises (E08) — raise ceiling before touching any keywords
    //   1. Cross-negatives (E05)    — traffic routing before pauses
    //   2. Removes (E03)            — old match-type keyword removed
    //   3. Positive creates (E03)   — new match-type keyword created
    //   4. Pauses                   — last, so routing changes are in place first
    const order = (op) => {
        if (op.resource === 'campaign' && op.type === 'update') return 0;
        if (op.type === 'create' && op.fields?.negative === true) return 1;
        if (op.type === 'remove') return 2;
        if (op.type === 'create' && !op.fields?.negative) return 3;
        if (op.type === 'update') return 4;
        return 5;
    };

    return [...ops].sort((a, b) => order(a) - order(b));
}

// ── Build mutation operations ───────────────────────────────────────

function buildMutateOperation(op) {
    const entity = op.resource;

    if (op.type === 'create') {
        return {
            entity,
            operation: 'create',
            resource: op.fields,
        };
    }

    if (op.type === 'update') {
        // Campaign updates use nested fields (e.g. target_cpa.target_cpa_micros) so the
        // update_mask must hold the dotted leaf paths, not the top-level keys.
        const updateMask = entity === 'campaign'
            ? flattenKeys(op.fields || {})
            : Object.keys(op.fields || {});
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

    if (op.type === 'remove') {
        // google-ads-api reads mutation.resource and wraps it as { remove: resource }.
        // For remove ops the protobuf expects a resource_name string, so we must put
        // the resource_name under the `resource` key — not a separate `resource_name` key.
        return {
            entity,
            operation: 'remove',
            resource: op.resource_name,
        };
    }

    throw new Error(`Unknown operation type: ${op.type}`);
}

// ── Format dry-run table ────────────────────────────────────────────

function formatBidValue(field, value) {
    if (value == null) return '—';
    if (field && field.includes('cpa_micros')) return `$${(value / 1_000_000).toFixed(2)}`;
    if (field && field.includes('target_roas')) return `${(value * 100).toFixed(0)}%`;
    return String(value);
}

function formatDryRunTable(ops) {
    const lines = [];
    lines.push('## Keyword Optimizer — Dry Run Results');
    lines.push('');
    lines.push(`**Operations:** ${ops.length} total`);
    lines.push('');

    // Group by action category
    const bidStrategyUpdates = ops.filter(op => op.resource === 'campaign' && op.meta?.action_id === 'KW-E08');
    const pauses = ops.filter(op => op.resource === 'ad_group_criterion' && op.type === 'update' && op.fields?.status === 'PAUSED');
    const matchTypeFixes = ops.filter(op => op.meta?.action_id === 'KW-E03');
    const crossNegatives = ops.filter(op => op.type === 'create' && op.fields?.negative === true && op.meta?.action_id === 'KW-E05');
    const other = ops.filter(op =>
        !bidStrategyUpdates.includes(op) && !pauses.includes(op) && !matchTypeFixes.includes(op) && !crossNegatives.includes(op)
    );

    let idx = 0;

    if (bidStrategyUpdates.length > 0) {
        lines.push(`### Bid Strategy Target Updates (${bidStrategyUpdates.length} operations)`);
        lines.push('| # | Campaign | Strategy | Current | New | Change | Portfolio | Conv 30d | Rationale |');
        lines.push('|---|----------|----------|---------|-----|--------|-----------|----------|-----------|');
        for (const op of bidStrategyUpdates) {
            idx++;
            const m = op.meta || {};
            const portfolioFlag = m.is_portfolio ? `YES (shared ${m.portfolio_shared_campaigns?.length || 0})` : 'no';
            const current = formatBidValue(m.bid_strategy_field, m.old_value);
            const next = formatBidValue(m.bid_strategy_field, m.new_value);
            const pct = (m.old_value && m.new_value)
                ? `${(((m.new_value - m.old_value) / m.old_value) * 100).toFixed(1)}%`
                : '—';
            lines.push(`| ${idx} | ${m.campaign || '—'} | ${m.bid_strategy_type || '—'} | ${current} | ${next} | ${pct} | ${portfolioFlag} | ${m.conversions_last_30d ?? '—'} | ${m.rationale || '—'} |`);
        }
        lines.push('');
        lines.push('> Bid strategy changes trigger a ~7–14 day re-learning period. Smart bidding will adjust pacing while it re-learns — expect temporary volatility.');
        if (bidStrategyUpdates.some(op => op.meta?.is_portfolio)) {
            lines.push('');
            lines.push('> **PORTFOLIO WARNING:** One or more updates affect a portfolio bid strategy. Changes cascade to every campaign sharing the portfolio. Re-run with `--confirm-portfolio` to apply.');
        }
        lines.push('');
    }

    if (pauses.length > 0) {
        lines.push(`### Pauses (${pauses.length} operations)`);
        lines.push('| # | Keyword | Match Type | Campaign | Ad Group | Action | Rationale |');
        lines.push('|---|---------|-----------|----------|----------|--------|-----------|');
        for (const op of pauses) {
            idx++;
            const m = op.meta || {};
            lines.push(`| ${idx} | ${m.target || '—'} | ${m.match_type || '—'} | ${m.campaign || '—'} | ${m.ad_group || '—'} | PAUSE | ${m.rationale || '—'} |`);
        }
        lines.push('');
    }

    if (matchTypeFixes.length > 0) {
        lines.push(`### Match Type Fixes (${matchTypeFixes.length} operations — remove + create pairs)`);
        lines.push('| # | Keyword | From | To | Campaign | Ad Group | Rationale |');
        lines.push('|---|---------|------|-----|----------|----------|-----------|');
        // Group by keyword for display
        const seen = new Set();
        for (const op of matchTypeFixes) {
            idx++;
            const m = op.meta || {};
            const key = `${m.target}|${m.campaign}|${m.ad_group}`;
            if (seen.has(key)) continue;
            seen.add(key);
            lines.push(`| ${idx} | ${m.target || '—'} | ${m.from_match_type || '—'} | ${m.to_match_type || '—'} | ${m.campaign || '—'} | ${m.ad_group || '—'} | ${m.rationale || '—'} |`);
        }
        lines.push('');
        lines.push('> Match type changes will lose keyword history. The new keyword starts fresh.');
        lines.push('');
    }

    if (crossNegatives.length > 0) {
        lines.push(`### Cross-Negatives (${crossNegatives.length} operations)`);
        lines.push('| # | Keyword | Match Type | Campaign | Ad Group | Type | Rationale |');
        lines.push('|---|---------|-----------|----------|----------|------|-----------|');
        for (const op of crossNegatives) {
            idx++;
            const m = op.meta || {};
            lines.push(`| ${idx} | ${m.target || '—'} | ${m.match_type || 'EXACT'} | ${m.campaign || '—'} | ${m.ad_group || '—'} | NEGATIVE | ${m.rationale || '—'} |`);
        }
        lines.push('');
    }

    if (other.length > 0) {
        lines.push(`### Other Operations (${other.length})`);
        lines.push('| # | Action | Type | Target | Rationale |');
        lines.push('|---|--------|------|--------|-----------|');
        for (const op of other) {
            idx++;
            const m = op.meta || {};
            const action = op.type === 'create' ? 'Create' : op.type === 'remove' ? 'Remove' : 'Update';
            lines.push(`| ${idx} | ${action} | ${m.category || op.resource} | ${m.target || '—'} | ${m.rationale || '—'} |`);
        }
        lines.push('');
    }

    lines.push(`Total operations: ${ops.length}`);
    lines.push(`Entity types: ${entityTypes.size} (${Array.from(entityTypes).join(', ')})`);
    lines.push('');
    lines.push('These changes have NOT been applied.');
    lines.push('**Ready to apply? (yes / no)**');

    return lines.join('\n');
}

// ── Execute ─────────────────────────────────────────────────────────

async function run() {
    const sorted = sortOperations(operations);

    if (mode === 'dry-run') {
        const mutateOps = sorted.map(buildMutateOperation);

        try {
            await customer.mutateResources(mutateOps, { validate_only: true });
            console.log(`API validation (${sorted.length} ops): PASSED`);
        } catch (e) {
            const errMsg = e.errors?.[0]?.message || e.message || String(e);
            console.error(`API validation: FAILED — ${errMsg}`);
        }

        console.log('');
        console.log(formatDryRunTable(sorted));
        return;
    }

    // ── Live mode ───────────────────────────────────────────────────

    const results = { applied: 0, failed: 0, errors: [] };

    // Execute in order: negatives → removes → creates → pauses
    for (let i = 0; i < sorted.length; i += BATCH_SIZE) {
        const batch = sorted.slice(i, i + BATCH_SIZE);
        const mutateOps = batch.map(buildMutateOperation);

        try {
            await customer.mutateResources(mutateOps);
            results.applied += batch.length;

            const batchLabel = sorted.length > BATCH_SIZE
                ? ` (batch ${Math.floor(i / BATCH_SIZE) + 1}/${Math.ceil(sorted.length / BATCH_SIZE)})`
                : '';
            console.log(`OK: ${batch.length} operations applied${batchLabel}`);
        } catch (e) {
            results.failed += batch.length;
            const errMsg = e.errors?.[0]?.message || e.message || String(e);
            results.errors.push({ count: batch.length, error: errMsg });
            console.error(`FAILED: ${batch.length} operations: ${errMsg}`);
        }
    }

    // ── Summary ─────────────────────────────────────────────────────

    console.log('');
    console.log('## Results');
    console.log('');
    console.log(`${results.applied}/${operations.length} operations applied successfully.`);

    if (results.failed > 0) {
        console.log('');
        console.log(`${results.failed} operations failed:`);
        for (const err of results.errors) {
            console.log(`  - ${err.count} ops: ${err.error}`);
        }
    }

    // ── Write changelog ─────────────────────────────────────────────

    const changelogPath = resolve(_projectRoot, 'context/analysis/keyword-changelog.md');
    const date = new Date().toISOString().split('T')[0];
    const changelogDir = dirname(changelogPath);
    if (!existsSync(changelogDir)) mkdirSync(changelogDir, { recursive: true });

    const entry = [];
    entry.push(`## ${date} — Keyword Optimizer`);
    entry.push('');
    entry.push(`**Mode:** live | **Account:** ${customerId}`);
    entry.push(`**Result:** ${results.applied}/${operations.length} applied`);
    entry.push(`**Source:** ${opsData.generated_from || 'keyword-audit.md'}`);
    entry.push('');

    const pauseCount = sorted.filter(op => op.resource === 'ad_group_criterion' && op.type === 'update' && op.fields?.status === 'PAUSED').length;
    const negCount = sorted.filter(op => op.type === 'create' && op.fields?.negative === true).length;
    const matchFixCount = sorted.filter(op => op.meta?.action_id === 'KW-E03').length;
    const removeCount = sorted.filter(op => op.type === 'remove').length;
    const bidCount = sorted.filter(op => op.resource === 'campaign' && op.meta?.action_id === 'KW-E08').length;

    entry.push(`**Summary:** ${pauseCount} keywords paused, ${negCount} cross-negatives added, ${matchFixCount / 2 || 0} match types fixed, ${removeCount} removed, ${bidCount} bid strategy targets updated`);
    entry.push('');
    entry.push('| # | Action | Category | Target | Status |');
    entry.push('|---|--------|----------|--------|--------|');

    let idx = 0;
    for (const op of sorted) {
        idx++;
        const m = op.meta || {};
        const status = results.failed > 0 ? '?' : 'OK';
        entry.push(`| ${idx} | ${op.type} | ${m.category || '—'} | ${m.target || '—'} | ${status} |`);
    }
    entry.push('');

    let existing = '';
    if (existsSync(changelogPath)) {
        existing = readFileSync(changelogPath, 'utf8');
    } else {
        existing = '# Keyword Optimizer Changelog\n\n';
    }
    writeFileSync(changelogPath, existing + entry.join('\n') + '\n', 'utf8');
    console.log(`\nChanges logged to context/analysis/keyword-changelog.md`);
}

run().catch(e => {
    console.error(`Fatal error: ${e.message}`);
    process.exit(1);
});
