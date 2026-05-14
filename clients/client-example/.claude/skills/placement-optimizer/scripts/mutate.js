#!/usr/bin/env node

/**
 * Google Ads Mutation Script — Placement Optimizer
 *
 * Applies placement exclusions, brand safety settings, and exclusion list
 * management operations via the Google Ads API.
 *
 * Handles multi-entity operations with dependency chains:
 *   1. shared_set creates (must exist before adding items)
 *   2. customer_negative_criterion creates (account-level exclusions)
 *   3. shared_criterion creates (add items to lists — depends on step 1)
 *   4. campaign_criterion creates (campaign-level exclusions)
 *   5. campaign_shared_set creates (link lists to campaigns — depends on step 1)
 *   6. campaign updates (brand safety settings)
 *   7. removes (only with --allow-remove)
 *
 * Usage:
 *   node mutate.js \
 *     --customer-id=XXXX \
 *     --login-customer-id=YYYY \
 *     --operations-file=path/to/operations.json \
 *     --mode=dry-run|live \
 *     --max-ops=200 \
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
const maxOps = parseInt(args['max-ops'] || '200');
const allowRemove = args['allow-remove'] === true;
const BATCH_SIZE = 200;

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
    console.error('    --max-ops=200 \\');
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

if (operations.length > maxOps) {
    console.error(`Error: ${operations.length} operations exceeds max-ops limit of ${maxOps}`);
    console.error(`Use --max-ops=${operations.length} to override`);
    process.exit(1);
}

const removeOps = operations.filter(op => op.type === 'remove');
if (removeOps.length > 0 && !allowRemove) {
    console.error(`Error: ${removeOps.length} remove operations found but --allow-remove not set`);
    process.exit(1);
}

// Entity count guard
const entityTypes = new Set(operations.map(op => op.resource).filter(Boolean));
if (entityTypes.size > 3) {
    console.log(`WARNING: Operations span ${entityTypes.size} entity types (>3).`);
}

// Shared set protection: never remove a shared_set with reference_count > 0
for (const op of removeOps) {
    if (op.resource === 'shared_set' && op.meta?.reference_count > 0) {
        console.error(`Error: Cannot remove shared_set "${op.meta?.target}" with reference_count ${op.meta.reference_count}`);
        console.error('Unlink from all campaigns first, then retry.');
        process.exit(1);
    }
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

// ── Operation ordering ──────────────────────────────────────────────

const ENTITY_ORDER = [
    'shared_set',                  // 1. Create lists first
    'customer_negative_criterion', // 2. Account-level exclusions
    'shared_criterion',            // 3. Add items to lists
    'campaign_criterion',          // 4. Campaign-level exclusions
    'campaign_shared_set',         // 5. Link lists to campaigns
    'campaign',                    // 6. Brand safety settings
];

// Maps entity types to their Google Ads API resource path segments
// Used for generating temporary resource names in validate_only calls
const ENTITY_PATH_MAP = {
    'shared_set': 'sharedSets',
    'campaign': 'campaigns',
    'campaign_criterion': 'campaignCriteria',
    'customer_negative_criterion': 'customerNegativeCriteria',
    'shared_criterion': 'sharedCriteria',
    'campaign_shared_set': 'campaignSharedSets',
};

// Maps entity type → field name in MutateOperationResponse (from gRPC proto)
// mutateResources returns results[j].{result_key}.resource_name
const ENTITY_RESULT_KEY = {
    'shared_set': 'shared_set_result',
    'campaign': 'campaign_result',
    'campaign_criterion': 'campaign_criterion_result',
    'customer_negative_criterion': 'customer_negative_criterion_result',
    'shared_criterion': 'shared_criterion_result',
    'campaign_shared_set': 'campaign_shared_set_result',
};

function extractResourceName(response, j, entity) {
    const resultKey = ENTITY_RESULT_KEY[entity];
    return response?.results?.[j]?.[resultKey]?.resource_name
        ?? response?.results?.[j]?.resource_name;  // fallback for older lib versions
}

// Entities that depend on output_ref from a prior create (must validate together)
const DEPENDENT_ENTITIES = new Set(['shared_criterion', 'campaign_shared_set']);

function sortOperations(ops) {
    // Non-remove operations first (in entity order), then removes (reverse order)
    const creates = ops.filter(op => op.type !== 'remove');
    const removes = ops.filter(op => op.type === 'remove');

    creates.sort((a, b) => {
        const aIdx = ENTITY_ORDER.indexOf(a.resource);
        const bIdx = ENTITY_ORDER.indexOf(b.resource);
        return (aIdx === -1 ? 99 : aIdx) - (bIdx === -1 ? 99 : bIdx);
    });

    removes.sort((a, b) => {
        const aIdx = ENTITY_ORDER.indexOf(a.resource);
        const bIdx = ENTITY_ORDER.indexOf(b.resource);
        return (bIdx === -1 ? 99 : bIdx) - (aIdx === -1 ? 99 : aIdx);
    });

    return [...creates, ...removes];
}

// ── Group by entity type ────────────────────────────────────────────

function groupByEntity(ops) {
    const groups = {};
    for (const op of ops) {
        const entity = op.resource || 'unknown';
        if (!groups[entity]) groups[entity] = [];
        groups[entity].push(op);
    }
    return groups;
}

// ── Mobile app detection ───────────────────────────────────────────

/**
 * Detect if a placement URL is actually a mobile app identifier.
 * The Google Ads API `placement` criterion type only accepts website URLs.
 * Mobile apps must use the `mobile_application` criterion type instead.
 *
 * App ID format in placement CSVs:
 *   - Google Play: "2-{package_name}" (e.g. "2-com.example.app")
 *   - iOS App Store: "1-{numeric_id}" (e.g. "1-6754315344")
 *   - Raw package name: "com.example.app" (no prefix)
 */
function isAppPlacement(url) {
    if (!url) return false;
    return /^[12]-/.test(url) || /^[a-z]+\.[a-z]+\.[a-z]/i.test(url);
}

function toAppId(url) {
    // Already has platform prefix → use as-is
    if (/^[12]-/.test(url)) return url;
    // Raw package name → assume Google Play
    return `2-${url}`;
}

/**
 * If op.fields contains a placement.url that is actually a mobile app,
 * convert it to mobile_application.app_id so the API accepts it.
 */
function rewriteAppPlacement(fields) {
    if (!fields?.placement?.url) return fields;
    const url = fields.placement.url;
    if (!isAppPlacement(url)) return fields;

    const rewritten = { ...fields };
    delete rewritten.placement;
    rewritten.mobile_application = { app_id: toAppId(url) };
    // Preserve name if present in meta (optional, for readability)
    if (fields.placement.name) {
        rewritten.mobile_application.name = fields.placement.name;
    }
    return rewritten;
}

// ── Build mutation operations ───────────────────────────────────────

function buildMutateOperation(op) {
    const entity = op.resource;

    if (op.type === 'create') {
        return {
            entity,
            operation: 'create',
            resource: rewriteAppPlacement(op.fields),
        };
    }

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

// ── Resolve output_ref references ───────────────────────────────────

function resolveOutputRefs(ops, refMap) {
    for (const op of ops) {
        if (!op.fields) continue;
        for (const [key, value] of Object.entries(op.fields)) {
            if (typeof value === 'string' && value.startsWith('{') && value.endsWith('}')) {
                const refKey = value.slice(1, -1);
                const [refName, field] = refKey.split('.');
                if (refMap[refName] && refMap[refName][field]) {
                    op.fields[key] = refMap[refName][field];
                }
            } else if (typeof value === 'object' && value !== null) {
                for (const [subKey, subVal] of Object.entries(value)) {
                    if (typeof subVal === 'string' && subVal.startsWith('{') && subVal.endsWith('}')) {
                        const refKey = subVal.slice(1, -1);
                        const [refName, field] = refKey.split('.');
                        if (refMap[refName] && refMap[refName][field]) {
                            value[subKey] = refMap[refName][field];
                        }
                    }
                }
            }
        }
    }
}

// ── Format dry-run table ────────────────────────────────────────────

function formatDryRunTable(ops) {
    const groups = groupByEntity(ops);
    const lines = [];
    lines.push('## Proposed Changes (DRY RUN)');
    lines.push('');

    let idx = 0;
    for (const entity of ENTITY_ORDER) {
        const entityOps = groups[entity];
        if (!entityOps || entityOps.length === 0) continue;

        const entityLabel = entity.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        lines.push(`### ${entityLabel} (${entityOps.length} operations)`);
        lines.push('');

        if (entity === 'campaign') {
            lines.push('| # | Action | Campaign | Setting | Current | Proposed | Rationale |');
            lines.push('|---|--------|----------|---------|---------|----------|-----------|');
            for (const op of entityOps) {
                idx++;
                const m = op.meta || {};
                lines.push(`| ${idx} | Update | ${m.target || '—'} | ${m.category || '—'} | ${m.previous_value || '—'} | ${m.new_value || '—'} | ${m.rationale || '—'} |`);
            }
        } else if (entity === 'campaign_shared_set') {
            lines.push('| # | Action | Campaign | List | Rationale |');
            lines.push('|---|--------|----------|------|-----------|');
            for (const op of entityOps) {
                idx++;
                const m = op.meta || {};
                lines.push(`| ${idx} | ${op.type === 'remove' ? 'Unlink' : 'Link'} | ${m.campaign || '—'} | ${m.target || '—'} | ${m.rationale || '—'} |`);
            }
        } else {
            lines.push('| # | Action | Type | Target | Rationale |');
            lines.push('|---|--------|------|--------|-----------|');
            for (const op of entityOps) {
                idx++;
                const m = op.meta || {};
                const action = op.type === 'create' ? 'Create' : op.type === 'remove' ? 'Remove' : 'Update';
                lines.push(`| ${idx} | ${action} | ${m.category || entity} | ${m.target || '—'} | ${m.rationale || '—'} |`);
            }
        }
        lines.push('');
    }

    lines.push(`Total operations: ${ops.length}`);
    lines.push(`Entity types: ${entityTypes.size} (${Array.from(entityTypes).join(', ')})`);
    lines.push('');
    lines.push('These changes have NOT been applied.');
    lines.push('');
    lines.push('Ready to apply? (yes / no)');

    return lines.join('\n');
}

// ── Execute ─────────────────────────────────────────────────────────

async function run() {
    const sorted = sortOperations(operations);

    if (mode === 'dry-run') {
        // Assign temporary resource names for output_ref operations so the API
        // can validate dependency chains (e.g. shared_set → shared_criterion)
        const tempRefMap = {};
        let tempId = -1;

        for (const op of sorted) {
            if (op.output_ref && op.type === 'create') {
                const pathSegment = ENTITY_PATH_MAP[op.resource];
                if (pathSegment) {
                    const tempResourceName = `customers/${customerId}/${pathSegment}/${tempId}`;
                    tempRefMap[op.output_ref] = { resource_name: tempResourceName };
                    op.fields.resource_name = tempResourceName;
                    tempId--;
                }
            }
        }

        // Resolve {ref.field} placeholders to temp resource names
        resolveOutputRefs(sorted, tempRefMap);

        // Split into two validation groups for better error isolation:
        //   - dependentOps: shared_set + entities that reference it (must validate together)
        //   - independentOps: everything else (customer_negative_criterion, etc.)
        const dependentOps = [];
        const independentOps = [];

        for (const op of sorted) {
            if (op.resource === 'shared_set' || DEPENDENT_ENTITIES.has(op.resource)) {
                dependentOps.push(op);
            } else {
                independentOps.push(op);
            }
        }

        // Build mutation operations for each group
        function buildOpsArray(ops) {
            const mutateOps = [];
            for (const op of ops) {
                try {
                    mutateOps.push(buildMutateOperation(op));
                } catch (e) {
                    console.error(`Error building operation: ${e.message}`);
                    console.error(`Operation: ${JSON.stringify(op.meta)}`);
                    process.exit(1);
                }
            }
            return mutateOps;
        }

        // Server-side validation via validate_only — catches API errors without applying
        let allPassed = true;

        if (independentOps.length > 0) {
            const indepMutateOps = buildOpsArray(independentOps);
            try {
                await customer.mutateResources(indepMutateOps, { validate_only: true });
                console.log(`API validation (${independentOps.length} independent ops): PASSED`);
            } catch (e) {
                allPassed = false;
                const errMsg = e.errors?.[0]?.message || e.message || String(e);
                console.error(`API validation (independent ops): FAILED — ${errMsg}`);
            }
        }

        if (dependentOps.length > 0) {
            const depMutateOps = buildOpsArray(dependentOps);
            try {
                await customer.mutateResources(depMutateOps, { validate_only: true });
                console.log(`API validation (${dependentOps.length} dependent ops): PASSED`);
            } catch (e) {
                allPassed = false;
                const errMsg = e.errors?.[0]?.message || e.message || String(e);
                console.error(`API validation (dependent ops): FAILED — ${errMsg}`);
            }
        }

        console.log(allPassed ? '\nAll API validation: PASSED\n' : '\n');
        console.log(formatDryRunTable(sorted));
        return;
    }

    // ── Live mode ───────────────────────────────────────────────────

    const results = { applied: 0, failed: 0, errors: [] };
    const refMap = {}; // output_ref → { resource_name: ... }

    const groups = groupByEntity(sorted);

    for (const entity of [...ENTITY_ORDER, ...Object.keys(groups).filter(e => !ENTITY_ORDER.includes(e))]) {
        const entityOps = groups[entity];
        if (!entityOps || entityOps.length === 0) continue;

        // Resolve any output_ref references before building mutations
        resolveOutputRefs(entityOps, refMap);

        // Batch operations
        for (let i = 0; i < entityOps.length; i += BATCH_SIZE) {
            const batch = entityOps.slice(i, i + BATCH_SIZE);
            const mutateOps = batch.map(buildMutateOperation);

            try {
                const response = await customer.mutateResources(mutateOps);
                results.applied += batch.length;

                // Store output_refs from response
                for (let j = 0; j < batch.length; j++) {
                    if (batch[j].output_ref) {
                        const rn = extractResourceName(response, j, entity);
                        if (rn) {
                            refMap[batch[j].output_ref] = { resource_name: rn };
                        }
                    }
                }

                const batchLabel = entityOps.length > BATCH_SIZE
                    ? ` (batch ${Math.floor(i / BATCH_SIZE) + 1}/${Math.ceil(entityOps.length / BATCH_SIZE)})`
                    : '';
                console.log(`OK: ${batch.length} ${entity} operations applied${batchLabel}`);
            } catch (e) {
                results.failed += batch.length;
                const errMsg = e.errors?.[0]?.message || e.message || String(e);
                results.errors.push({ entity, count: batch.length, error: errMsg });
                console.error(`FAILED: ${batch.length} ${entity} operations: ${errMsg}`);
            }
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
            console.log(`  - ${err.entity} (${err.count} ops): ${err.error}`);
        }
    }

    // ── Write changelog ─────────────────────────────────────────────

    const changelogPath = resolve(_projectRoot, 'context/analysis/placement-changelog.md');
    const date = new Date().toISOString().split('T')[0];
    const changelogDir = dirname(changelogPath);
    if (!existsSync(changelogDir)) mkdirSync(changelogDir, { recursive: true });

    const entry = [];
    entry.push(`## ${date} — Placement Optimizer`);
    entry.push('');
    entry.push(`**Mode:** live | **Account:** ${customerId}`);
    entry.push(`**Result:** ${results.applied}/${operations.length} applied`);
    entry.push(`**Source:** ${opsData.generated_from || 'placement-audit.md'}`);
    entry.push('');
    entry.push('| # | Entity | Action | Category | Target | Status |');
    entry.push('|---|--------|--------|----------|--------|--------|');

    let idx = 0;
    const failedEntities = new Set(results.errors.map(e => e.entity));
    for (const op of sorted) {
        idx++;
        const m = op.meta || {};
        const status = failedEntities.has(op.resource) ? 'FAILED' : 'OK';
        entry.push(`| ${idx} | ${op.resource} | ${op.type} | ${m.category || '—'} | ${m.target || '—'} | ${status} |`);
    }
    entry.push('');

    let existing = '';
    if (existsSync(changelogPath)) {
        existing = readFileSync(changelogPath, 'utf8');
    } else {
        existing = '# Placement Optimizer Changelog\n\n';
    }
    writeFileSync(changelogPath, existing + entry.join('\n') + '\n', 'utf8');
    console.log(`\nChanges logged to context/analysis/placement-changelog.md`);
}

run().catch(e => {
    console.error(`Fatal error: ${e.message}`);
    process.exit(1);
});
