#!/usr/bin/env node

/**
 * Google Ads Mutation Script — Budget Optimizer
 *
 * Applies campaign_budget updates: raise (BUD-E01, BUD-E07), reduce
 * (BUD-E04 reduce side), reallocate (BUD-E02 / BUD-E04 portfolio rebalance),
 * fix-shared (BUD-E05), pacing-adjust (BUD-E06).
 *
 * Operation file format mirrors keyword-optimizer / bidding-optimizer.
 * Each op carries a `meta` block with the auditor-derived gate clearances:
 *   - cascade_clear: { measurement, business, efficiency, conversion, bidding }
 *   - step_cap: { from_micros, to_micros, multiplier, max_allowed }
 *   - mutation_type: "raise" | "reduce" | "reallocate" | "fix-shared" | "pacing-adjust"
 *   - confirmed: bool — set by SKILL.md after the user types "confirm" on a soft-block
 *   - rationale: human-readable explanation
 *
 * mutate.js re-validates these gates before either dry-run or live apply.
 * Override flags must be explicitly passed at the CLI to take effect.
 */

import { GoogleAdsApi } from 'google-ads-api';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { config as loadEnv } from 'dotenv';

const __dirname = dirname(fileURLToPath(import.meta.url));
let _projectRoot = __dirname;
while (_projectRoot !== '/' && !existsSync(resolve(_projectRoot, 'config'))) {
    _projectRoot = resolve(_projectRoot, '..');
}
loadEnv({ path: resolve(_projectRoot, 'config/.env') });

// ── CLI parsing ─────────────────────────────────────────────────────────

const args = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const i = arg.indexOf('=');
        acc[arg.slice(0, i).replace('--', '')] = arg.slice(i + 1);
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
const aggressive = args['aggressive'] === true;
const overrideMeasurement = args['override-measurement'] === true;
const overrideBusiness = args['override-business'] === true;
const overrideReason = args['override-reason'] || null;

if (!customerId || !operationsFile || !mode) {
    console.error('Usage: node mutate.js --customer-id=X --login-customer-id=Y --operations-file=PATH --mode=dry-run|live [--aggressive] [--override-measurement --override-business --override-reason="..."]');
    process.exit(1);
}
if (mode !== 'dry-run' && mode !== 'live') {
    console.error(`--mode must be dry-run or live (got "${mode}")`);
    process.exit(1);
}

const clientId = process.env.GOOGLE_ADS_CLIENT_ID;
const clientSecret = process.env.GOOGLE_ADS_CLIENT_SECRET;
const developerToken = process.env.GOOGLE_ADS_DEVELOPER_TOKEN;
const refreshToken = process.env.GOOGLE_ADS_REFRESH_TOKEN;
if (!clientId || !clientSecret || !developerToken || !refreshToken) {
    console.error('Missing Google Ads credentials in config/.env');
    process.exit(1);
}

// ── Config ──────────────────────────────────────────────────────────────

const configPath = resolve(_projectRoot, 'config/ads-context.config.json');
const ppCfg = JSON.parse(readFileSync(configPath, 'utf8'));
const ba = ppCfg.budgetAudit || {};
const accountCurrency = ppCfg.accountCurrency || 'USD';
const baseMaxMultiplier = ba.maxSingleMutationMultiplier ?? 1.3;
const maxMultiplier = aggressive ? Math.max(baseMaxMultiplier, 1.5) : baseMaxMultiplier;
const dailyToCpaRatio = ba.dailyBudgetToCpaRatio ?? 2.0;

// ── Operations ──────────────────────────────────────────────────────────

const opsPath = resolve(_projectRoot, operationsFile);
if (!existsSync(opsPath)) {
    console.error(`Operations file not found: ${opsPath}`);
    process.exit(1);
}
const opsData = JSON.parse(readFileSync(opsPath, 'utf8'));
const operations = opsData.operations || [];
if (operations.length === 0) {
    console.log('No operations to apply.');
    process.exit(0);
}
if (operations.length > maxOps) {
    console.error(`${operations.length} operations exceeds --max-ops=${maxOps}.`);
    process.exit(1);
}

// ── Pre-flight gate validation ─────────────────────────────────────────

const violations = [];

for (const op of operations) {
    const meta = op.meta || {};
    const cc = meta.cascade_clear || {};

    // Hard blocks
    if (cc.measurement === 'blocking' && !overrideMeasurement) {
        violations.push({ op: meta.target, why: 'Measurement cascade is blocking — route to /tracking-specialist before any mutation. Use --override-measurement --override-reason="..." to override.' });
    }
    if (cc.business === 'blocking' && !overrideBusiness) {
        violations.push({ op: meta.target, why: 'Business cascade is blocking — break-even / unit economics missing. Route to /strategy-specialist. Use --override-business --override-reason="..." to override.' });
    }

    // Soft blocks (efficiency / conversion / bidding) require meta.confirmed=true
    // set by the SKILL after the user types "confirm" on the explicit prompt.
    const softLayers = ['efficiency', 'conversion', 'bidding'];
    for (const layer of softLayers) {
        if ((cc[layer] === 'soft-block' || cc[layer] === 'recommended') && !meta.confirmed) {
            violations.push({
                op: meta.target,
                why: `${layer} layer flagged as soft-block; operation must carry meta.confirmed=true after the user types "confirm" + an override reason.`,
            });
        }
    }

    // Channel sanity (raise only)
    if (meta.mutation_type === 'raise') {
        const ch = (meta.channel_type || '').toUpperCase();
        const newDaily = (op.fields?.amount_micros ?? 0) / 1_000_000;
        if ((ch === 'SEARCH' || ch === 'SHOPPING') && meta.tcpa && newDaily < meta.tcpa * dailyToCpaRatio) {
            violations.push({
                op: meta.target,
                why: `New daily budget $${newDaily.toFixed(2)} is below ${dailyToCpaRatio}x tCPA ($${(meta.tcpa * dailyToCpaRatio).toFixed(2)}). Raise the budget or adjust tCPA via /bidding-specialist first.`,
            });
        }
        if (ch === 'PERFORMANCE_MAX') {
            if (meta.pmax_volume_floor == null) {
                violations.push({
                    op: meta.target,
                    why: 'meta.pmax_volume_floor is required for PMax raise ops. The SKILL must hydrate it from budgetAudit.pmaxVolumeFloor (with a $50/day fallback) per execute-rules.md before generating the op.',
                });
            } else if (newDaily < meta.pmax_volume_floor) {
                violations.push({
                    op: meta.target,
                    why: `New daily budget $${newDaily.toFixed(2)} is below the configured PMax volume floor $${meta.pmax_volume_floor}.`,
                });
            }
        }
    }

    // Step cap (1.3x default; can be raised to 1.5x with --aggressive).
    // Only enforced for raises.
    if (meta.mutation_type === 'raise') {
        const sc = meta.step_cap || {};
        const mult = sc.multiplier ?? (sc.to_micros && sc.from_micros ? sc.to_micros / sc.from_micros : 1);
        if (mult > maxMultiplier + 1e-9) {
            violations.push({
                op: meta.target,
                why: `Raise multiplier ${mult.toFixed(2)}x exceeds cap ${maxMultiplier.toFixed(2)}x${aggressive ? ' (aggressive)' : ''}. Split into smaller increments or pass --aggressive (max 1.5x).`,
            });
        }
    }
}

if (violations.length > 0) {
    console.error('Pre-flight gates failed:');
    for (const v of violations) console.error(`  - [${v.op}] ${v.why}`);
    process.exit(1);
}

// ── API client ──────────────────────────────────────────────────────────

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

// ── Build mutate operations ─────────────────────────────────────────────

function flattenKeys(obj, prefix = '') {
    const paths = [];
    for (const [k, v] of Object.entries(obj)) {
        const path = prefix ? `${prefix}.${k}` : k;
        if (v && typeof v === 'object' && !Array.isArray(v)) paths.push(...flattenKeys(v, path));
        else paths.push(path);
    }
    return paths;
}

function buildMutateOperation(op) {
    const entity = op.resource || 'campaign_budget';
    if (op.type === 'update') {
        const updateMask = flattenKeys(op.fields || {});
        return {
            entity,
            operation: 'update',
            resource: { resource_name: op.resource_name, ...op.fields },
            update_mask: { paths: updateMask },
        };
    }
    if (op.type === 'create') {
        return { entity, operation: 'create', resource: op.fields };
    }
    if (op.type === 'remove') {
        return { entity, operation: 'remove', resource: op.resource_name };
    }
    throw new Error(`Unknown op type: ${op.type}`);
}

// Order: reduces → reallocations (mixed) → raises. Reduces first frees
// account-level pool when allocate-then-raise is the pattern.
function sortOps(ops) {
    const order = (op) => {
        const t = op.meta?.mutation_type;
        if (t === 'reduce') return 0;
        if (t === 'reallocate') return 1;
        if (t === 'fix-shared') return 2;
        if (t === 'pacing-adjust') return 3;
        if (t === 'raise') return 4;
        return 5;
    };
    return [...ops].sort((a, b) => order(a) - order(b));
}

// ── Dry-run table ──────────────────────────────────────────────────────

function fmt(amount) {
    if (amount == null) return '—';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: accountCurrency, maximumFractionDigits: 0 }).format(amount);
}

function mdEscape(value) {
    if (value === null || value === undefined) return '—';
    return String(value).replaceAll('|', '\\|');
}

function formatDryRunTable(ops) {
    const lines = [];
    lines.push('## Budget Optimizer — Dry Run Results');
    lines.push('');
    lines.push(`**Operations:** ${ops.length} total`);
    lines.push('');

    const byType = {
        raise: ops.filter(o => o.meta?.mutation_type === 'raise'),
        reduce: ops.filter(o => o.meta?.mutation_type === 'reduce'),
        reallocate: ops.filter(o => o.meta?.mutation_type === 'reallocate'),
        'fix-shared': ops.filter(o => o.meta?.mutation_type === 'fix-shared'),
        'pacing-adjust': ops.filter(o => o.meta?.mutation_type === 'pacing-adjust'),
    };

    let idx = 0;
    let totalIncrementalDaily = 0;

    for (const [section, list] of Object.entries(byType)) {
        if (!list.length) continue;
        lines.push(`### ${section.charAt(0).toUpperCase() + section.slice(1)} (${list.length})`);
        lines.push('| # | Campaign / Pool | Old/day | New/day | Δ/day | Δ/mo (~) | Cascade | Rationale |');
        lines.push('|---|-----------------|---------|---------|-------|----------|---------|-----------|');
        for (const op of list) {
            idx++;
            const m = op.meta || {};
            const sc = m.step_cap || {};
            const oldDaily = (sc.from_micros ?? 0) / 1_000_000;
            const newDaily = (sc.to_micros ?? (op.fields?.amount_micros ?? 0)) / 1_000_000;
            const deltaDaily = newDaily - oldDaily;
            const deltaMonthly = Math.round(deltaDaily * 30.4);
            totalIncrementalDaily += deltaDaily;
            const cc = m.cascade_clear || {};
            const cascadeFlags = Object.entries(cc)
                .map(([k, v]) => `${k}:${v}`)
                .join(' ');
            lines.push(`| ${idx} | \`${mdEscape(m.target)}\` | ${fmt(oldDaily)} | ${fmt(newDaily)} | ${deltaDaily >= 0 ? '+' : ''}${fmt(deltaDaily)} | ${deltaMonthly >= 0 ? '+' : ''}${fmt(deltaMonthly)} | ${mdEscape(cascadeFlags)} | ${mdEscape(m.rationale)} |`);
        }
        lines.push('');
    }

    lines.push(`**Net monthly impact:** ${totalIncrementalDaily >= 0 ? '+' : ''}${fmt(Math.round(totalIncrementalDaily * 30.4))}`);
    lines.push('');

    const allClear = ops.every(o => {
        const cc = o.meta?.cascade_clear || {};
        return cc.measurement !== 'blocking' && cc.business !== 'blocking';
    });
    lines.push('Gate clearances:');
    lines.push(`- Cascade: ${allClear ? '✅' : '⚠'} measurement+business${overrideMeasurement || overrideBusiness ? ` (override active: ${overrideReason || '—'})` : ''}`);
    lines.push(`- Step cap: ✅ within ${maxMultiplier.toFixed(2)}x${aggressive ? ' (aggressive)' : ''}`);
    lines.push('');
    lines.push('These changes have NOT been applied.');
    lines.push('**Ready to apply? (yes / no)**');
    return lines.join('\n');
}

// ── Run ─────────────────────────────────────────────────────────────────

async function run() {
    const sorted = sortOps(operations);

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

    // Live
    const results = { applied: 0, failed: 0, errors: [] };
    const BATCH = 50;
    for (let i = 0; i < sorted.length; i += BATCH) {
        const batch = sorted.slice(i, i + BATCH);
        const mutateOps = batch.map(buildMutateOperation);
        try {
            await customer.mutateResources(mutateOps);
            results.applied += batch.length;
            console.log(`OK: applied ${batch.length} (batch ${Math.floor(i / BATCH) + 1})`);
        } catch (e) {
            results.failed += batch.length;
            const errMsg = e.errors?.[0]?.message || e.message || String(e);
            results.errors.push({ count: batch.length, error: errMsg });
            console.error(`FAILED: ${batch.length} ops — ${errMsg}`);
        }
    }

    // Mutation history (kept indefinitely — small files, valuable for rollback inspection)
    const tmpDir = resolve(_projectRoot, 'tmp/budget-optimizer');
    mkdirSync(tmpDir, { recursive: true });
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    const historyPath = resolve(tmpDir, `mutations-${stamp}.json`);
    writeFileSync(historyPath, JSON.stringify({
        timestamp: new Date().toISOString(),
        mode,
        customerId,
        accountCurrency,
        operations: sorted,
        results,
        override_flags: { aggressive, overrideMeasurement, overrideBusiness, overrideReason },
    }, null, 2));

    // Append to changelog
    const changelogPath = resolve(_projectRoot, 'context/analysis/budget-changelog.md');
    mkdirSync(dirname(changelogPath), { recursive: true });
    const date = new Date().toISOString().slice(0, 10);
    const summary = [];
    summary.push(`## ${date} — Budget Optimizer`);
    summary.push('');
    summary.push(`**Mode:** live | **Customer:** ${customerId} | **Currency:** ${accountCurrency}`);
    summary.push(`**Result:** ${results.applied}/${operations.length} applied`);
    if (overrideReason) summary.push(`**Override:** ${overrideReason}`);
    summary.push('');
    summary.push('| # | Type | Target | Old/day | New/day | Rationale |');
    summary.push('|---|------|--------|---------|---------|-----------|');
    let idx = 0;
    for (const op of sorted) {
        idx++;
        const m = op.meta || {};
        const sc = m.step_cap || {};
        const oldD = (sc.from_micros ?? 0) / 1_000_000;
        const newD = (sc.to_micros ?? (op.fields?.amount_micros ?? 0)) / 1_000_000;
        summary.push(`| ${idx} | ${mdEscape(m.mutation_type)} | \`${mdEscape(m.target)}\` | ${fmt(oldD)} | ${fmt(newD)} | ${mdEscape(m.rationale)} |`);
    }
    summary.push('');
    const existing = existsSync(changelogPath) ? readFileSync(changelogPath, 'utf8') : '# Budget Optimizer Changelog\n\n';
    writeFileSync(changelogPath, existing + summary.join('\n') + '\n', 'utf8');

    console.log('');
    console.log(`${results.applied}/${operations.length} operations applied.`);
    console.log(`History: ${historyPath}`);
    console.log(`Changelog: ${changelogPath}`);
}

run().catch(e => {
    console.error(`Fatal: ${e.message}`);
    process.exit(1);
});
