#!/usr/bin/env node

/**
 * Google Ads Mutation Script — Search Term Optimizer
 *
 * Applies search-term mutations via 5 primitives:
 *   - create_keyword     (ST-E03)  ad_group_criterion (positive)
 *   - create_negative    (E01, E02, E05, E06, E07, E10)  shared_criterion / campaign_criterion / ad_group_criterion (negative)
 *   - remove_negative    (E04, E05, E06)
 *   - create_shared_set  (E02 bootstrap, E07, auto-create in pre-flight)
 *                        includes campaign_shared_set attachments
 *   - brand_exclusion    (E09)  campaign_criterion (brand_list)
 *
 * Operation ordering (PRD §4.6):
 *   1. Shared set creates + campaign attachments
 *   2. Negative creates at shared list level
 *   3. Negative creates at campaign level
 *   4. Negative creates at ad-group level
 *   5. Negative removes (E04, E05, E06)
 *   6. Brand exclusions (E09)
 *   7. Keyword creates (E03)
 *
 * Usage:
 *   node mutate.js --customer-id=XXXX --login-customer-id=YYYY \
 *     --operations-file=path/to/operations.json --mode=dry-run|live --max-ops=100
 */

import { GoogleAdsApi, enums } from 'google-ads-api';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { config } from 'dotenv';

const __dirname = dirname(fileURLToPath(import.meta.url));
let _projectRoot = __dirname;
while (_projectRoot !== '/' && !existsSync(resolve(_projectRoot, 'config'))) {
    _projectRoot = resolve(_projectRoot, '..');
}
config({ path: resolve(_projectRoot, 'config/.env') });

// ── CLI args ────────────────────────────────────────────────────────

const args = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const eq = arg.indexOf('=');
        const k = arg.slice(0, eq).replace('--', '');
        const v = arg.slice(eq + 1);
        if (k && v) acc[k] = v;
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
const BATCH_SIZE = 200;

if (!customerId || !operationsFile || !mode) {
    console.error('Error: Missing required arguments');
    console.error('Usage: node mutate.js --customer-id=X --login-customer-id=Y --operations-file=ops.json --mode=dry-run|live');
    process.exit(1);
}
if (mode !== 'dry-run' && mode !== 'live') {
    console.error(`Error: --mode must be "dry-run" or "live" (got "${mode}")`);
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

if (operations.length > maxOps) {
    console.error(`Error: ${operations.length} operations exceeds max-ops limit of ${maxOps}`);
    console.error(`Use --max-ops=${operations.length} to override`);
    process.exit(1);
}

// ── API client ──────────────────────────────────────────────────────

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

function sortKey(op) {
    // 1. shared_set creates
    if (op.resource === 'shared_set' && op.type === 'create') return 1;
    // 2. campaign_shared_set attachments
    if (op.resource === 'campaign_shared_set' && op.type === 'create') return 2;
    // 3. shared_criterion creates (negatives at shared list level)
    if (op.resource === 'shared_criterion' && op.type === 'create') return 3;
    // 4. campaign_criterion creates (campaign-level negatives OR brand exclusions)
    if (op.resource === 'campaign_criterion' && op.type === 'create') {
        // Brand exclusions go last among creates
        if (op.meta?.action_id === 'ST-E09') return 6;
        return 4;
    }
    // 5. ad_group_criterion negative creates
    if (op.resource === 'ad_group_criterion' && op.type === 'create' && op.fields?.negative === true) return 5;
    // 6. removes — always after creates
    if (op.type === 'remove') return 7;
    // 7. positive keyword creates (ST-E03) — LAST
    if (op.resource === 'ad_group_criterion' && op.type === 'create' && op.fields?.negative !== true) return 8;
    return 9;
}

function sortOperations(ops) {
    return [...ops].sort((a, b) => sortKey(a) - sortKey(b));
}

// ── Build mutation operation for google-ads-api ─────────────────────

function buildMutateOperation(op) {
    const entity = op.resource;
    if (op.type === 'create') {
        return { entity, operation: 'create', resource: op.fields };
    }
    if (op.type === 'update') {
        return {
            entity, operation: 'update',
            resource: { resource_name: op.resource_name, ...op.fields },
            update_mask: { paths: Object.keys(op.fields || {}) }
        };
    }
    if (op.type === 'remove') {
        return { entity, operation: 'remove', resource: op.resource_name };
    }
    throw new Error(`Unknown operation type: ${op.type}`);
}

// ── CSV export (shared by dry-run preview and live-applied) ────────

function csvCell(v) {
    if (v === null || v === undefined) return '';
    const s = String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function csvRow(fields) {
    return fields.map(csvCell).join(',');
}

function matchTypeLabel(mt) {
    if (!mt) return '';
    return mt.charAt(0) + mt.slice(1).toLowerCase();
}

function bucketForOp(op) {
    const cat = op.meta?.category;
    if (cat === 'bootstrap' || cat === 'attach') return 'preflight';
    if (cat === 'ngram') return 'ngrams';
    if (cat === 'negate') return 'negate';
    if (cat === 'foreign') return 'foreign';
    if (cat === 'promote') return 'promote';
    if (cat === 'conflict' || op.type === 'remove') return 'removals';
    if (op.meta?.action_id === 'ST-E09') return 'brand';
    return 'other';
}

function numCell(v) {
    const n = Number(v);
    return Number.isFinite(n) && n !== 0 ? n : '';
}

function rowFor(op, bucket) {
    const m = op.meta || {};
    const kw = op.fields?.keyword || {};
    switch (bucket) {
        case 'preflight':
            return [
                op.resource === 'shared_set' ? 'Create list' : 'Attach list',
                m.list_name || m.target || op.fields?.name || '',
                m.category === 'attach' ? (m.target || '') : '',
                m.rationale || ''
            ];
        case 'ngrams':
        case 'negate':
        case 'foreign':
            if (op.resource === 'shared_criterion') {
                const listName = (m.scope || '').replace(/^shared_list:/, '') || m.list_name || '';
                return [listName, kw.text || m.term || '', matchTypeLabel(kw.match_type || m.match_type), numCell(m.cost), numCell(m.conversions), m.rationale || '', m.source_diagnostic || ''];
            }
            return [m.campaign || m.scope || '', kw.text || m.term || '', matchTypeLabel(kw.match_type || m.match_type), numCell(m.cost), numCell(m.conversions), m.rationale || '', m.source_diagnostic || ''];
        case 'promote':
            return [m.campaign || '', m.ad_group || '', kw.text || m.term || '', matchTypeLabel(kw.match_type || m.match_type), op.fields?.status || 'Enabled', numCell(m.conversions), numCell(m.cost), numCell(m.cpa), m.rationale || ''];
        case 'removals':
            return [m.scope || '', m.target || '', m.term || '', matchTypeLabel(m.match_type), numCell(m.cost), m.rationale || ''];
        case 'brand':
            return [m.campaign || m.scope || '', m.target || 'brand list', numCell(m.cost), m.rationale || ''];
        default:
            return [op.resource, op.type, m.target || m.term || '', m.rationale || ''];
    }
}

function headerFor(bucket) {
    switch (bucket) {
        case 'preflight': return ['Action', 'List Name', 'Campaign', 'Rationale'];
        case 'ngrams':
        case 'negate':
        case 'foreign': return ['Scope', 'Keyword', 'Match Type', 'Cost', 'Conversions', 'Rationale', 'Source Diagnostic'];
        case 'promote': return ['Campaign', 'Ad Group', 'Keyword', 'Match Type', 'Status', 'Conversions', 'Cost', 'CPA', 'Rationale'];
        case 'removals': return ['Scope', 'Target', 'Term', 'Match Type', 'Cost', 'Rationale'];
        case 'brand': return ['Campaign', 'Target', 'Cost', 'Rationale'];
        default: return ['Resource', 'Type', 'Target', 'Rationale'];
    }
}

function sortKeyForBucket(bucket, op) {
    const m = op.meta || {};
    const cost = Number(m.cost) || 0;
    const conversions = Number(m.conversions) || 0;
    switch (bucket) {
        case 'promote':       return -conversions;
        case 'ngrams':
        case 'negate':
        case 'foreign':
        case 'removals':
        case 'brand':         return -cost;
        default:              return 0;
    }
}

function writeOperationsCSVs(sortedOps, prefix) {
    const date = new Date().toISOString().split('T')[0];
    const outDir = resolve(_projectRoot, 'created/search-terms');
    if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true });

    const byBucket = new Map();
    for (const op of sortedOps) {
        const b = bucketForOp(op);
        if (!byBucket.has(b)) byBucket.set(b, []);
        byBucket.get(b).push(op);
    }

    const written = [];
    for (const [bucket, ops] of byBucket) {
        const bucketSorted = [...ops].sort((a, b) => sortKeyForBucket(bucket, a) - sortKeyForBucket(bucket, b));
        const header = headerFor(bucket);
        const rows = bucketSorted.map(op => csvRow(rowFor(op, bucket)));
        const content = [csvRow(header), ...rows].join('\n') + '\n';
        const filename = `${date}_${prefix}_${bucket}.csv`;
        const filepath = resolve(outDir, filename);
        writeFileSync(filepath, content, 'utf8');
        written.push({ bucket, filename, count: bucketSorted.length });
    }
    return written;
}

// ── Format dry-run table ────────────────────────────────────────────

function formatDryRun(sorted) {
    const lines = [];
    lines.push('## Search Term Optimizer — Dry Run Results');
    lines.push('');
    lines.push(`**Operations:** ${sorted.length} total`);
    lines.push('');

    // Group by action_id
    const groups = new Map();
    for (const op of sorted) {
        const id = op.meta?.action_id || 'OTHER';
        if (!groups.has(id)) groups.set(id, []);
        groups.get(id).push(op);
    }

    const ACTION_LABELS = {
        'ST-E01': 'Negate Irrelevant (shared list)',
        'ST-E02': 'N-gram Exclusions',
        'ST-E03': 'Promote Keywords',
        'ST-E04': 'Resolve Negative Conflicts',
        'ST-E05': 'Consolidate Ad-Group → Shared',
        'ST-E06': 'Consolidate Campaign → Shared',
        'ST-E07': 'Catalog-Validated Negatives',
        'ST-E09': 'PMax Brand Exclusion',
        'ST-E10': 'Foreign Language Negatives',
        'PREFLIGHT': 'Pre-Flight Shared-List Setup'
    };

    let idx = 0;
    for (const [id, ops] of groups.entries()) {
        const label = ACTION_LABELS[id] || id;
        lines.push(`### ${label} (${ops.length} ops)`);
        lines.push('| # | Type | Target | Scope | Match | Rationale |');
        lines.push('|---|------|--------|-------|-------|-----------|');
        for (const op of ops) {
            idx++;
            const m = op.meta || {};
            const action = op.type === 'create' ? 'Create' : op.type === 'remove' ? 'Remove' : 'Update';
            const target = m.target || m.term || m.keyword || m.list_name || '—';
            const scope = m.scope || op.resource || '—';
            const match = m.match_type || '—';
            const rationale = m.rationale || '—';
            lines.push(`| ${idx} | ${action} | ${target} | ${scope} | ${match} | ${rationale} |`);
        }
        lines.push('');
    }

    lines.push(`Total operations: ${sorted.length}`);
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

        const written = writeOperationsCSVs(sorted, 'preview');
        console.log('');
        console.log('Preview CSVs written to created/search-terms/:');
        for (const w of written) console.log(`  - ${w.filename} (${w.count} rows)`);

        console.log('');
        console.log(formatDryRun(sorted));
        return;
    }

    // Live mode — apply in order, BATCH_SIZE at a time
    const results = { applied: 0, failed: 0, errors: [] };
    for (let i = 0; i < sorted.length; i += BATCH_SIZE) {
        const batch = sorted.slice(i, i + BATCH_SIZE);
        const mutateOps = batch.map(buildMutateOperation);
        try {
            await customer.mutateResources(mutateOps);
            results.applied += batch.length;
            const label = sorted.length > BATCH_SIZE
                ? ` (batch ${Math.floor(i / BATCH_SIZE) + 1}/${Math.ceil(sorted.length / BATCH_SIZE)})`
                : '';
            console.log(`OK: ${batch.length} operations applied${label}`);
        } catch (e) {
            results.failed += batch.length;
            const errMsg = e.errors?.[0]?.message || e.message || String(e);
            results.errors.push({ count: batch.length, error: errMsg });
            console.error(`FAILED: ${batch.length} operations: ${errMsg}`);
        }
    }

    console.log('');
    console.log('## Results');
    console.log('');
    console.log(`${results.applied}/${operations.length} operations applied successfully.`);
    if (results.failed > 0) {
        console.log('');
        console.log(`${results.failed} operations failed:`);
        for (const err of results.errors) console.log(`  - ${err.count} ops: ${err.error}`);
    }

    // Write changelog
    const changelogPath = resolve(_projectRoot, 'context/analysis/search-term-changelog.md');
    const date = new Date().toISOString().split('T')[0];
    const changelogDir = dirname(changelogPath);
    if (!existsSync(changelogDir)) mkdirSync(changelogDir, { recursive: true });

    const entry = [];
    entry.push(`## ${date} — Search Term Optimizer`);
    entry.push('');
    entry.push(`**Mode:** live | **Account:** ${customerId}`);
    entry.push(`**Result:** ${results.applied}/${operations.length} applied`);
    entry.push(`**Source:** ${opsData.generated_from || 'search-term-audit.md'}`);
    entry.push('');

    const byAction = new Map();
    for (const op of sorted) {
        const id = op.meta?.action_id || 'OTHER';
        byAction.set(id, (byAction.get(id) || 0) + 1);
    }
    const actionSummary = Array.from(byAction.entries())
        .map(([id, n]) => `${n} × ${id}`)
        .join(', ');
    entry.push(`**Summary:** ${actionSummary}`);
    entry.push('');
    entry.push('| # | Action | Type | Target | Status |');
    entry.push('|---|--------|------|--------|--------|');
    let idx = 0;
    for (const op of sorted) {
        idx++;
        const m = op.meta || {};
        const status = results.failed > 0 ? '?' : 'OK';
        entry.push(`| ${idx} | ${m.action_id || '—'} | ${op.type} | ${m.target || m.term || '—'} | ${status} |`);
    }
    entry.push('');

    let existing = existsSync(changelogPath)
        ? readFileSync(changelogPath, 'utf8')
        : '# Search Term Optimizer Changelog\n\n';
    writeFileSync(changelogPath, existing + entry.join('\n') + '\n', 'utf8');
    console.log(`\nChanges logged to context/analysis/search-term-changelog.md`);

    const applied = writeOperationsCSVs(sorted, 'applied');
    console.log('Applied CSVs written to created/search-terms/:');
    for (const w of applied) console.log(`  - ${w.filename} (${w.count} rows)`);
}

run().catch(e => {
    console.error(`Fatal error: ${e.message}`);
    process.exit(1);
});
