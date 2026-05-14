#!/usr/bin/env node

/**
 * Google Ads Mutation Script — Bidding Optimizer
 *
 * Applies bid-strategy mutations: target adjustments (BID-E09), strategy
 * migrations (BID-E05 — driven by lib helpers, see migration playbook),
 * portfolio fixes (BID-D17 fix), CPC caps (BID-E08), data exclusions
 * (BID-E14), bid modifiers (BID-E12), and ad schedules (BID-E13).
 *
 * Operations file format mirrors keyword-optimizer's. Each operation carries
 * a `meta` block with the auditor-derived gate clearances:
 *   - cascade_clear: { measurement, business, efficiency, conversion, budget }
 *   - learning_gate: { last_strategy_change, last_target_change, days_since, in_window }
 *   - stacking: { mutation_type, prior_in_session }
 *   - step_cap: { from, to, pct, max_allowed_pct }
 *   - override_flags: ["force-learning", "aggressive", ...]
 *
 * The mutate.js engine re-validates these gates before either dry-run or live
 * apply. Override flags must be explicitly passed at the CLI to take effect.
 */

import { GoogleAdsApi } from 'google-ads-api';
import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync } from 'fs';
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
const forceLearning = args['force-learning'] === true;
const aggressive = args['aggressive'] === true;
const confirmPortfolio = args['confirm-portfolio'] === true;
const overrideReason = args['override-reason'] || null;

if (!customerId || !operationsFile || !mode) {
    console.error('Usage: node mutate.js --customer-id=X --login-customer-id=Y --operations-file=PATH --mode=dry-run|live [--force-learning --aggressive --confirm-portfolio --override-reason="..."]');
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
const ba = ppCfg.biddingAudit || {};

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

// 1. Cascade gates (blocking flags). Soft blocks require user confirmation
//    via the operation's meta.confirmed=true, set by the SKILL.md after the
//    user explicitly typed "confirm".
for (const op of operations) {
    const meta = op.meta || {};
    const cc = meta.cascade_clear || {};
    if (cc.measurement === 'blocking') violations.push({ op: meta.target, why: 'Measurement cascade is blocking — route to /tracking-specialist before any mutation.' });
    if (cc.business === 'blocking') violations.push({ op: meta.target, why: 'Business cascade is blocking — unit economics missing in business.md. Route to /strategy-audit --execute unit-economics.' });
    if ((cc.efficiency === 'soft-block' || cc.conversion === 'soft-block') && !meta.confirmed) {
        violations.push({ op: meta.target, why: 'Efficiency/conversion soft-block; operation must carry meta.confirmed=true after the user types "confirm".' });
    }
}

// 2. Learning window
for (const op of operations) {
    const meta = op.meta || {};
    if (meta.skip_learning_check) continue;
    const lg = meta.learning_gate || {};
    const dsStrat = lg.days_since_strategy;
    const dsTgt = lg.days_since_target;
    const learningDays = ba.learningWindowDays || 14;
    const tooFresh =
        (typeof dsStrat === 'number' && dsStrat < learningDays) ||
        (typeof dsTgt === 'number' && dsTgt < learningDays);
    if (tooFresh && !forceLearning) {
        violations.push({
            op: meta.target,
            why: `Learning gate: strategy=${dsStrat}d / target=${dsTgt}d (need ≥${learningDays}d). Pass --force-learning + --override-reason to override.`,
        });
    }
    if (forceLearning && !overrideReason) {
        violations.push({ op: meta.target, why: '--force-learning requires --override-reason="..."' });
    }
}

// 3. Stacking limit (per-session)
//    - ≤1 distinct strategy mutation per campaign (ops sharing meta.migration_id
//      count as one logical migration even if they emit multiple physical ops)
//    - ≤1 target mutation per campaign
//    - modifier / schedule / exclusion / rule ops are not capped (each affects
//      a distinct underlying resource)
//    Keys on meta.campaign_id (immutable identifier) — falls back to meta.target
//    for account-level ops with no campaign_id.
{
    const strategyByCampaign = new Map();   // campaignKey -> Set<migrationId>
    const targetByCampaign = new Map();     // campaignKey -> count
    const labelByCampaign = new Map();      // campaignKey -> meta.target for messages

    let opIdx = 0;
    for (const op of operations) {
        const meta = op.meta || {};
        const campaignKey = meta.campaign_id || meta.target || `__op_${opIdx}`;
        if (!labelByCampaign.has(campaignKey)) {
            labelByCampaign.set(campaignKey, meta.target || campaignKey);
        }
        const mt = meta.mutation_type;
        if (mt === 'strategy') {
            const set = strategyByCampaign.get(campaignKey) || new Set();
            set.add(meta.migration_id || `__solo_${opIdx}`);
            strategyByCampaign.set(campaignKey, set);
        } else if (mt === 'target') {
            targetByCampaign.set(campaignKey, (targetByCampaign.get(campaignKey) || 0) + 1);
        }
        opIdx++;
    }

    for (const [k, set] of strategyByCampaign) {
        if (set.size > 1) violations.push({
            op: labelByCampaign.get(k),
            why: `Stacking limit: ${set.size} distinct strategy mutations on this campaign in one session (max 1).`,
        });
    }
    for (const [k, n] of targetByCampaign) {
        if (n > 1) violations.push({
            op: labelByCampaign.get(k),
            why: `Stacking limit: ${n} target mutations on this campaign in one session (max 1).`,
        });
    }
}

// 4. Target step cap (BID-E09)
const maxStep = aggressive ? (ba.aggressiveMaxTargetStepPct || 30) : (ba.maxTargetStepPct || 20);
for (const op of operations) {
    const meta = op.meta || {};
    if (meta.mutation_type !== 'target') continue;
    const sc = meta.step_cap || {};
    const pct = Math.abs(sc.pct ?? 0);
    if (pct > maxStep) {
        violations.push({ op: meta.target, why: `Target step ${pct.toFixed(1)}% exceeds ${maxStep}% cap${aggressive ? ' (aggressive)' : ''}. Lower the step or split across runs.` });
    }
}

// 5. Portfolio confirmation
const portfolioOps = operations.filter(op => op.meta?.is_portfolio === true);
if (portfolioOps.length > 0 && !confirmPortfolio) {
    violations.push({ op: 'portfolio', why: `${portfolioOps.length} operation(s) target portfolio strategies. Pass --confirm-portfolio to apply.` });
}

// 6. Value rules guard
const valueRuleOps = operations.filter(op => op.resource === 'conversion_value_rule');
if (valueRuleOps.length > 0 && ba.valueRulesAllowed !== true) {
    violations.push({
        op: 'value-rules',
        why: `${valueRuleOps.length} conversion_value_rule operation(s) but biddingAudit.valueRulesAllowed !== true in config/ads-context.config.json.`,
    });
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
    const entity = op.resource;
    if (op.type === 'create') {
        return { entity, operation: 'create', resource: op.fields };
    }
    if (op.type === 'update') {
        const updateMask = entity === 'campaign' || entity === 'bidding_strategy'
            ? flattenKeys(op.fields || {})
            : Object.keys(op.fields || {});
        return {
            entity,
            operation: 'update',
            resource: { resource_name: op.resource_name, ...op.fields },
            update_mask: { paths: updateMask },
        };
    }
    if (op.type === 'remove') {
        return { entity, operation: 'remove', resource: op.resource_name };
    }
    throw new Error(`Unknown op type: ${op.type}`);
}

// Order: data-exclusions → portfolio adjustments → campaign target updates →
// criterion updates (modifiers / schedule). Reasoning: exclusions stabilise
// the model before any target moves; portfolio precedes campaign so portfolio
// fixes don't leave campaigns in inconsistent state mid-batch.
function sortOps(ops) {
    const order = (op) => {
        if (op.resource === 'bidding_data_exclusion') return 0;
        if (op.resource === 'bidding_strategy') return 1;
        if (op.resource === 'campaign') return 2;
        if (op.resource === 'campaign_criterion') return 3;
        if (op.resource === 'campaign_draft') return 4;
        if (op.resource === 'campaign_experiment') return 5;
        return 6;
    };
    return [...ops].sort((a, b) => order(a) - order(b));
}

// ── Dry-run table ──────────────────────────────────────────────────────

function fmtTarget(field, value) {
    if (value == null) return '—';
    if (typeof field === 'string' && field.includes('cpa_micros')) return `$${(value / 1_000_000).toFixed(2)}`;
    if (typeof field === 'string' && field.includes('target_roas')) return `${(value * 100).toFixed(0)}%`;
    return String(value);
}

function mdEscape(value) {
    if (value === null || value === undefined) return '—';
    return String(value).replaceAll('|', '\\|');
}

function formatDryRunTable(ops) {
    const lines = [];
    lines.push('## Bidding Optimizer — Dry Run Results');
    lines.push('');
    lines.push(`**Operations:** ${ops.length} total`);
    lines.push('');

    const targetUpdates = ops.filter(o => o.meta?.mutation_type === 'target');
    const strategyMigrations = ops.filter(o => o.meta?.mutation_type === 'strategy');
    const exclusions = ops.filter(o => o.resource === 'bidding_data_exclusion');
    const modifierOps = ops.filter(o => o.resource === 'campaign_criterion');
    const portfolioOps = ops.filter(o => o.resource === 'bidding_strategy');
    const otherOps = ops.filter(o =>
        !targetUpdates.includes(o) && !strategyMigrations.includes(o)
        && !exclusions.includes(o) && !modifierOps.includes(o) && !portfolioOps.includes(o)
    );

    let idx = 0;
    if (targetUpdates.length) {
        lines.push(`### Target Adjustments (${targetUpdates.length})`);
        lines.push('| # | Campaign | Strategy | Old | New | Δ% | Cascade | Learning | Stacking | Override |');
        lines.push('|---|----------|----------|-----|-----|-----|---------|----------|----------|---------|');
        for (const op of targetUpdates) {
            idx++;
            const m = op.meta || {};
            const sc = m.step_cap || {};
            const cc = m.cascade_clear || {};
            const lg = m.learning_gate || {};
            const cascadeFlags = Object.entries(cc).map(([k, v]) => `${k}:${v}`).join(' ');
            lines.push(`| ${idx} | \`${mdEscape(m.target)}\` | ${mdEscape(m.strategy)} | ${mdEscape(fmtTarget(m.field, sc.from))} | ${mdEscape(fmtTarget(m.field, sc.to))} | ${sc.pct?.toFixed(1) ?? '—'}% | ${mdEscape(cascadeFlags)} | s=${lg.days_since_strategy ?? '—'} t=${lg.days_since_target ?? '—'} | ${mdEscape(m.mutation_type)} | ${mdEscape((m.override_flags || []).join(',') || '—')} |`);
        }
        lines.push('');
    }
    if (strategyMigrations.length) {
        lines.push(`### Strategy Migrations / Switches (${strategyMigrations.length})`);
        lines.push('| # | Campaign | From | To | Mode | Rationale |');
        lines.push('|---|----------|------|-----|------|-----------|');
        for (const op of strategyMigrations) {
            idx++;
            const m = op.meta || {};
            lines.push(`| ${idx} | \`${mdEscape(m.target)}\` | ${mdEscape(m.from_strategy)} | ${mdEscape(m.to_strategy)} | ${mdEscape(m.migration_mode || 'direct')} | ${mdEscape(m.rationale)} |`);
        }
        lines.push('');
        lines.push('> Strategy changes trigger a 7–14 day re-learning period. Smart bidding will adjust pacing while it re-learns.');
        lines.push('');
    }
    if (portfolioOps.length) {
        lines.push(`### Portfolio Updates (${portfolioOps.length})`);
        lines.push('| # | Portfolio | Field | Old | New | Rationale |');
        lines.push('|---|-----------|-------|-----|-----|-----------|');
        for (const op of portfolioOps) {
            idx++;
            const m = op.meta || {};
            lines.push(`| ${idx} | \`${mdEscape(m.target)}\` | ${mdEscape(m.field)} | ${mdEscape(fmtTarget(m.field, m.old_value))} | ${mdEscape(fmtTarget(m.field, m.new_value))} | ${mdEscape(m.rationale)} |`);
        }
        lines.push('');
    }
    if (exclusions.length) {
        lines.push(`### Data Exclusions (${exclusions.length})`);
        lines.push('| # | Scope | Window | Devices | Channels | Rationale |');
        lines.push('|---|-------|--------|---------|----------|-----------|');
        for (const op of exclusions) {
            idx++;
            const m = op.meta || {};
            lines.push(`| ${idx} | ${mdEscape(m.scope)} | ${mdEscape(m.start)} → ${mdEscape(m.end)} | ${mdEscape((m.devices || []).join(',') || '—')} | ${mdEscape((m.channels || []).join(',') || '—')} | ${mdEscape(m.rationale)} |`);
        }
        lines.push('');
    }
    if (modifierOps.length) {
        lines.push(`### Bid Modifier / Schedule Updates (${modifierOps.length})`);
        lines.push('| # | Campaign | Type | Old | New | Rationale |');
        lines.push('|---|----------|------|-----|-----|-----------|');
        for (const op of modifierOps) {
            idx++;
            const m = op.meta || {};
            lines.push(`| ${idx} | \`${mdEscape(m.target)}\` | ${mdEscape(m.criterion_type)} | ${mdEscape(m.old_value)} | ${mdEscape(m.new_value)} | ${mdEscape(m.rationale)} |`);
        }
        lines.push('');
    }
    if (otherOps.length) {
        lines.push(`### Other (${otherOps.length})`);
        lines.push('| # | Resource | Type | Target | Rationale |');
        lines.push('|---|----------|------|--------|-----------|');
        for (const op of otherOps) {
            idx++;
            const m = op.meta || {};
            lines.push(`| ${idx} | ${mdEscape(op.resource)} | ${mdEscape(op.type)} | \`${mdEscape(m.target)}\` | ${mdEscape(m.rationale)} |`);
        }
        lines.push('');
    }
    lines.push('Gate clearances:');
    lines.push(`- Cascade: ${ops.every(o => !['blocking'].includes(o.meta?.cascade_clear?.measurement) && !['blocking'].includes(o.meta?.cascade_clear?.business)) ? '✅' : '❌'} measurement+business`);
    lines.push(`- Learning: ${forceLearning ? `⚠ override (${overrideReason})` : '✅ all >14d'}`);
    lines.push(`- Stacking: ✅ within session limits`);
    lines.push(`- Step cap: ✅ within ${maxStep}%${aggressive ? ' (aggressive)' : ''}`);
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

    // Mutation history
    const tmpDir = resolve(_projectRoot, 'tmp/bidding-optimizer');
    mkdirSync(tmpDir, { recursive: true });
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    const historyPath = resolve(tmpDir, `mutations-${stamp}.json`);
    writeFileSync(historyPath, JSON.stringify({
        timestamp: new Date().toISOString(),
        mode,
        customerId,
        operations: sorted,
        results,
        override_flags: { forceLearning, aggressive, confirmPortfolio, overrideReason },
    }, null, 2));

    // Append to changelog
    const changelogPath = resolve(_projectRoot, 'context/analysis/bidding-changelog.md');
    mkdirSync(dirname(changelogPath), { recursive: true });
    const date = new Date().toISOString().slice(0, 10);
    const summary = [];
    summary.push(`## ${date} — Bidding Optimizer`);
    summary.push('');
    summary.push(`**Mode:** live | **Customer:** ${customerId}`);
    summary.push(`**Result:** ${results.applied}/${operations.length} applied`);
    if (overrideReason) summary.push(`**Override:** ${overrideReason}`);
    summary.push('');
    summary.push('| # | Resource | Type | Target | Rationale |');
    summary.push('|---|----------|------|--------|-----------|');
    let idx = 0;
    for (const op of sorted) {
        idx++;
        const m = op.meta || {};
        summary.push(`| ${idx} | ${mdEscape(op.resource)} | ${mdEscape(op.type)} | \`${mdEscape(m.target)}\` | ${mdEscape(m.rationale)} |`);
    }
    summary.push('');
    const existing = existsSync(changelogPath) ? readFileSync(changelogPath, 'utf8') : '# Bidding Optimizer Changelog\n\n';
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
