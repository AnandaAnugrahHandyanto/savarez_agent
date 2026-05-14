#!/usr/bin/env node

/**
 * Keyword Performance Analysis — keyword-auditor
 *
 * Classifies every keyword into performance tiers against true business economics
 * (break-even CPA, per-action conversion values, product relevance), not just
 * campaign target CPA. All business inputs come from config — Claude's Phase 0
 * interview populates them. This script never parses business.md.
 *
 * Tiers: HERO, ACTIVE, OVER_TARGET, UNPROFITABLE, PAUSE_CANDIDATE, INSUFFICIENT_DATA,
 *        LOW_PERFORMER, ZOMBIE
 *
 * Usage:
 *   node analyze-keyword-performance.js \
 *     --period-a-csv=context/google-ads/data/keywords-periodA.csv \
 *     --period-b-csv=context/google-ads/data/keywords-periodB.csv \
 *     --conv-by-action-a-csv=context/google-ads/data/keywords-conv-by-action-periodA.csv \
 *     --conv-by-action-b-csv=context/google-ads/data/keywords-conv-by-action-periodB.csv \
 *     --campaigns-csv=context/google-ads/data/campaigns-settings.csv \
 *     --portfolios-csv=context/google-ads/data/bidding-strategies.csv \
 *     --tiers-output=context/google-ads/data/keyword-tiers.csv \
 *     --flags-output=context/google-ads/data/keyword-flags.csv
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { parse } from 'csv-parse/sync';

// ── Project root discovery ──────────────────────────────────────────
const __dirname = dirname(fileURLToPath(import.meta.url));
let _projectRoot = __dirname;
while (_projectRoot !== '/' && !existsSync(resolve(_projectRoot, 'config'))) {
    _projectRoot = resolve(_projectRoot, '..');
}

// ── Parse CLI args ──────────────────────────────────────────────────
const args = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const eqIndex = arg.indexOf('=');
        const key = arg.slice(0, eqIndex).replace(/^--/, '');
        const value = arg.slice(eqIndex + 1);
        if (key && value) acc[key] = value;
    }
    return acc;
}, {});

const periodACsvPath = resolve(_projectRoot, args['period-a-csv'] || '');
const periodBCsvPath = resolve(_projectRoot, args['period-b-csv'] || '');
const convByActionACsvPath = args['conv-by-action-a-csv'] ? resolve(_projectRoot, args['conv-by-action-a-csv']) : '';
const convByActionBCsvPath = args['conv-by-action-b-csv'] ? resolve(_projectRoot, args['conv-by-action-b-csv']) : '';
const campaignsCsvPath = resolve(_projectRoot, args['campaigns-csv'] || '');
const portfoliosCsvPath = args['portfolios-csv']
    ? resolve(_projectRoot, args['portfolios-csv'])
    : resolve(_projectRoot, 'context/google-ads/data/bidding-strategies.csv');
const tiersOutputPath = resolve(_projectRoot, args['tiers-output'] || 'context/google-ads/data/keyword-tiers.csv');
const flagsOutputPath = resolve(_projectRoot, args['flags-output'] || 'context/google-ads/data/keyword-flags.csv');

// ── Load config ─────────────────────────────────────────────────────
let kwConfig = {};
let searchConfig = {};
let googleAdsConfig = {};
try {
    const configPath = resolve(_projectRoot, 'config/ads-context.config.json');
    if (existsSync(configPath)) {
        const fullConfig = JSON.parse(readFileSync(configPath, 'utf8'));
        kwConfig = fullConfig.keywordAudit || {};
        searchConfig = fullConfig.searchTermAnalysis || {};
        googleAdsConfig = fullConfig.googleAds || {};
    }
} catch (e) { /* use defaults */ }

// Normalize break-even ROAS to the canonical ratio form (e.g. 5.3 = 530%).
// The Google Ads API and all computed metrics in this script (effectiveRoas,
// campaign.target_roas) use the ratio form. Users, however, often enter 530
// (percentage) instead of 5.3. Any ROAS value above 10 is extremely unlikely
// to be a real ratio — a 1000% ROAS is believable, a 10x ratio is already the
// upper end of what serious accounts sustain — so we coerce anything > 10 by
// dividing by 100. The coercion is logged so misconfigurations are visible.
function normalizeRoasRatio(raw) {
    if (raw === null || raw === undefined) return null;
    const v = Number(raw);
    if (!isFinite(v) || v <= 0) return null;
    if (v > 10) {
        console.warn(`⚠ breakEvenROAS=${raw} looks like a percentage (>10) — normalizing to ratio ${(v / 100).toFixed(2)}. Enter as a ratio (e.g. 5.3 for 530%) to silence this warning.`);
        return v / 100;
    }
    return v;
}

const CFG = {
    // Analyst-cached (written by Phase 0 interview)
    // primaryKPI determines which profitability gate drives tier classification:
    //   "cpa"  → breakEvenCPA (lower is better)
    //   "roas" → breakEvenROAS (higher is better, stored as a ratio)
    // Falls back to biddingStrategy from searchTermAnalysis config, then defaults to "cpa".
    primaryKPI: kwConfig.primaryKPI ?? searchConfig.biddingStrategy ?? 'cpa',
    breakEvenCPA: kwConfig.breakEvenCPA ?? null,
    breakEvenROAS: normalizeRoasRatio(kwConfig.breakEvenROAS ?? null),
    conversionActionValues: kwConfig.conversionActionValues ?? null,
    primaryConversionAction: kwConfig.primaryConversionAction ?? null,
    coreProductTokens: Array.isArray(kwConfig.coreProductTokens) ? kwConfig.coreProductTokens : null,
    // Backward compat: accept both old cpaFallbackMode and new targetFallbackMode
    targetFallbackMode: kwConfig.targetFallbackMode ?? kwConfig.cpaFallbackMode ?? null,

    // Static defaults
    pauseStatisticalMultiplier: kwConfig.pauseStatisticalMultiplier ?? 2.0,
    coreTermsPatienceMultiplier: kwConfig.coreTermsPatienceMultiplier ?? 1.5,
    // Absolute floor for pause-candidate spend. Prevents tiny-budget accounts
    // from getting aggressive pauses when the derived threshold is a trivial sum.
    // CPA mode: final threshold = max(breakEvenCPA × multiplier × patience, absolutePauseFloor).
    // ROAS mode: final threshold = max(absolutePauseFloor × multiplier × patience, absolutePauseFloor).
    absolutePauseFloor: kwConfig.absolutePauseFloor ?? 100,
    heroShareThreshold: kwConfig.heroShareThreshold ?? 0.30,
    villainSpendGapPp: kwConfig.villainSpendGapPp ?? 20,
    villainCpaMultiplier: kwConfig.villainCpaMultiplier ?? 1.5,
    villainRoasMultiplier: kwConfig.villainRoasMultiplier ?? 0.7,
    zombieDays: kwConfig.zombieDays ?? 30,
    minClicksForEval: kwConfig.minClicksForEval ?? 100,
    minConversionsForEfficiency: kwConfig.minConversionsForEfficiency ?? 10,
    nonConvertingSpendMultiplier: kwConfig.nonConvertingSpendMultiplier ?? 2.0,
    tierShiftEnabled: kwConfig.tierShiftEnabled ?? true,
};

// ── Hard-fail validation of analyst-cached config ──────────────────
// The script is dumb by design. If Claude has not run the Phase 0 interview
// to populate business context, stop here — do not silently fall back.
const isFallbackMode = CFG.targetFallbackMode === 'campaign_target_only' || CFG.targetFallbackMode === 'tcpa_only';

function failConfig(missing) {
    console.error('');
    console.error('╭─ Keyword Auditor — Missing Business Context ─────────────────╮');
    console.error('│                                                              │');
    console.error('│  Required config values are missing or null:                 │');
    for (const m of missing) {
        console.error(`│    • keywordAudit.${m}`.padEnd(63) + '│');
    }
    console.error('│                                                              │');
    console.error('│  These are populated by Claude during the keyword-auditor    │');
    console.error('│  Phase 0 business-context interview. Run:                    │');
    console.error('│                                                              │');
    console.error('│    /keyword-audit --reconfirm                                │');
    console.error('│                                                              │');
    console.error('│  to re-run the interview, or manually edit                   │');
    console.error('│  config/ads-context.config.json → keywordAudit.              │');
    console.error('│                                                              │');
    console.error('│  If you want to proceed without true business targets        │');
    console.error('│  (limited analysis), set keywordAudit.targetFallbackMode =   │');
    console.error('│  "campaign_target_only" and re-run.                          │');
    console.error('│                                                              │');
    console.error('╰──────────────────────────────────────────────────────────────╯');
    process.exit(2);
}

if (!isFallbackMode) {
    const missing = [];
    // Validate the profitability threshold matching the configured KPI
    if (CFG.primaryKPI === 'roas') {
        if (CFG.breakEvenROAS === null || CFG.breakEvenROAS === undefined) missing.push('breakEvenROAS');
    } else {
        if (CFG.breakEvenCPA === null || CFG.breakEvenCPA === undefined) missing.push('breakEvenCPA');
    }
    if (!CFG.conversionActionValues || Object.keys(CFG.conversionActionValues).length === 0) missing.push('conversionActionValues');
    if (!CFG.primaryConversionAction) missing.push('primaryConversionAction');
    if (!CFG.coreProductTokens) missing.push('coreProductTokens');
    if (missing.length > 0) failConfig(missing);
}

console.log(`Primary KPI: ${CFG.primaryKPI.toUpperCase()}`);
if (CFG.primaryKPI === 'roas') {
    console.log(`Min profitable ROAS: ${CFG.breakEvenROAS}`);
} else {
    console.log(`Max profitable CPA: $${CFG.breakEvenCPA}`);
}

if (isFallbackMode) {
    console.warn(`⚠ Running in targetFallbackMode=${CFG.targetFallbackMode} — pause/unprofitable tier math disabled.`);
    console.warn(`  Analysis is limited to campaign targets. Every report section that uses`);
    console.warn(`  profitability thresholds will carry a caveat that true business targets are not set.`);
}

const BROAD_WITHOUT_SMART_BIDDING_STRATEGIES = new Set(['MANUAL_CPC', 'MAXIMIZE_CLICKS']);
const brandedCampaignNames = new Set(
    (searchConfig.brandedCampaigns || []).map(name => normalizeText(name))
);
const exactBrandTerms = loadExactBrandTerms();

// ── Validation ──────────────────────────────────────────────────────
if (!args['period-a-csv']) {
    console.error('Error: --period-a-csv is required');
    process.exit(1);
}

// ── Helpers ─────────────────────────────────────────────────────────
function loadCsv(path) {
    if (!path || !existsSync(path)) return [];
    const raw = readFileSync(path, 'utf8');
    const rows = parse(raw, { columns: true, skip_empty_lines: true, relax_column_count: true });
    // Normalize column names: dots → underscores (query.js outputs dot-separated GAQL paths)
    return rows.map(row => {
        const norm = {};
        for (const [key, val] of Object.entries(row)) {
            norm[key.replace(/\./g, '_')] = val;
        }
        return norm;
    });
}

function normalizeText(text) {
    return String(text || '')
        .toLowerCase()
        .replace(/[^\p{L}\p{N}]+/gu, ' ')
        .trim();
}

function num(val) {
    const n = parseFloat(val);
    return isNaN(n) ? 0 : n;
}

function numOrNull(val) {
    const n = parseFloat(val);
    return isNaN(n) ? null : n;
}

function escapeCsv(val) {
    if (val == null) return '';
    const s = String(val);
    if (s.includes(',') || s.includes('"') || s.includes('\n')) {
        return '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
}

function writeCsv(path, headers, rows) {
    const dir = dirname(path);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    const lines = [headers.join(',')];
    for (const row of rows) {
        lines.push(headers.map(h => escapeCsv(row[h])).join(','));
    }
    writeFileSync(path, lines.join('\n') + '\n', 'utf8');
}

function escapeRegex(text) {
    return String(text).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function addBrandCandidates(target, rawValue) {
    if (!rawValue) return;
    const parts = String(rawValue)
        .split(/[()]/)
        .map(part => normalizeText(part))
        .filter(Boolean);

    for (const part of parts) {
        const words = part.split(/\s+/).filter(Boolean);
        if (words.length >= 2) {
            target.add(part);
        }
    }

    if (target.size === 0) {
        for (const part of parts) {
            if (part) target.add(part);
        }
    }
}

function extractMarkdownValue(markdown, label) {
    const fieldRegex = new RegExp(`\\*\\*${escapeRegex(label)}:\\*\\*\\s*([^\\n]+)`, 'i');
    const fieldMatch = markdown.match(fieldRegex);
    if (fieldMatch) return fieldMatch[1].trim();

    const tableRegex = new RegExp(`\\|\\s*${escapeRegex(label)}\\s*\\|\\s*([^|\\n]+)\\|`, 'i');
    const tableMatch = markdown.match(tableRegex);
    return tableMatch ? tableMatch[1].trim() : '';
}

function loadExactBrandTerms() {
    const terms = new Set();
    const businessPath = resolve(_projectRoot, 'context/business.md');
    const brandPath = resolve(_projectRoot, 'context/brand.md');

    if (existsSync(businessPath)) {
        const businessMd = readFileSync(businessPath, 'utf8');
        addBrandCandidates(terms, extractMarkdownValue(businessMd, 'Client Name'));
    }

    if (existsSync(brandPath)) {
        const brandMd = readFileSync(brandPath, 'utf8');
        addBrandCandidates(terms, extractMarkdownValue(brandMd, 'Name'));
        const headingMatch = brandMd.match(/^#\s+Brand Context\s*-\s*(.+)$/mi);
        if (headingMatch) addBrandCandidates(terms, headingMatch[1]);
    }

    addBrandCandidates(terms, googleAdsConfig.clientName);
    return terms;
}

function isBrandedCampaign(campaignName) {
    const normalizedName = normalizeText(campaignName);
    if (!normalizedName) return false;
    if (brandedCampaignNames.size > 0) {
        return brandedCampaignNames.has(normalizedName);
    }
    return /branded/i.test(campaignName) && !/non.?branded/i.test(campaignName);
}

/**
 * Determine bidding mode from campaign bidding strategy type.
 * SMART = strategies with machine-learning optimization.
 * MANUAL = everything else.
 */
function biddingMode(strategyType) {
    const smart = ['TARGET_CPA', 'TARGET_ROAS', 'MAXIMIZE_CONVERSIONS', 'MAXIMIZE_CONVERSION_VALUE'];
    if (smart.includes(strategyType)) return 'SMART';
    return 'MANUAL';
}

/**
 * Normalize conversion action names so `trial-converted`, `trial_converted`,
 * `Trial Converted` all match. The authoritative key is config.googleAds.conversionActions,
 * but we match loosely to survive gatherer/business.md typos.
 */
function normalizeActionName(name) {
    return String(name || '').toLowerCase().replace(/[\s\-_]+/g, '');
}

/**
 * Build a fast lookup: normalized action name → value (dollars).
 */
function buildActionValueMap(conversionActionValues) {
    const map = new Map();
    if (!conversionActionValues) return map;
    for (const [name, value] of Object.entries(conversionActionValues)) {
        map.set(normalizeActionName(name), num(value));
    }
    return map;
}

const actionValueMap = buildActionValueMap(CFG.conversionActionValues);
const primaryActionNormalized = CFG.primaryConversionAction
    ? normalizeActionName(CFG.primaryConversionAction)
    : null;

// Composite keyword key — criterion_id is only unique within an ad group,
// so every lookup must be keyed by (ad_group_id, criterion_id) to avoid
// cross-ad-group collisions.
const kwKey = (adGroupId, criterionId) => `${adGroupId}:${criterionId}`;

/**
 * Build a lookup from (ad_group_id, criterion_id) → { normalizedActionName: conversions }.
 * Only keeps actions that appear in the configured conversionActionValues —
 * everything else is ignored (e.g. secondary tracking actions we don't bid toward).
 */
function buildConvByActionLookup(rows) {
    const lookup = new Map();
    for (const row of rows) {
        const critId = row.ad_group_criterion_criterion_id;
        const agId = row.ad_group_id;
        if (!critId || !agId) continue;
        const key = kwKey(agId, critId);

        const actionName = row.segments_conversion_action_name || '';
        const normalized = normalizeActionName(actionName);
        if (!normalized) continue;

        // Only keep actions we care about (configured by the user)
        if (actionValueMap.size > 0 && !actionValueMap.has(normalized)) continue;

        const convs = num(row.metrics_conversions);
        if (!lookup.has(key)) lookup.set(key, {});
        const entry = lookup.get(key);
        entry[normalized] = (entry[normalized] || 0) + convs;
    }
    return lookup;
}

/**
 * Resolve per-keyword primary/effective conversions from the lookup.
 * Returns {primaryConversions, effectiveConversions, effectiveConvValue}.
 * In fallback mode, returns blended values from the raw row.
 */
function resolveConvByAction(adGroupId, criterionId, blendedConv, blendedValue, convByActionLookup) {
    if (isFallbackMode) {
        return {
            primaryConversions: blendedConv,
            effectiveConversions: blendedConv,
            effectiveConvValue: blendedValue,
        };
    }

    const convByAction = convByActionLookup.get(kwKey(adGroupId, criterionId)) || {};
    let primaryConversions = 0;
    let effectiveConversions = 0;
    let effectiveConvValue = 0;

    for (const [normalizedAction, value] of actionValueMap) {
        const actionConv = num(convByAction[normalizedAction] || 0);
        effectiveConversions += actionConv;
        effectiveConvValue += actionConv * value;
        if (normalizedAction === primaryActionNormalized) {
            primaryConversions = actionConv;
        }
    }

    return { primaryConversions, effectiveConversions, effectiveConvValue };
}

/**
 * True if the keyword text contains any configured core product token.
 * Used to apply the patience multiplier before pausing a strategically
 * relevant keyword that has not yet hit the statistical gate.
 */
function isCoreProductTerm(keywordText) {
    if (!CFG.coreProductTokens || CFG.coreProductTokens.length === 0) return false;
    const normalized = normalizeText(keywordText);
    if (!normalized) return false;
    for (const token of CFG.coreProductTokens) {
        const t = normalizeText(token);
        if (t && normalized.includes(t)) return true;
    }
    return false;
}

// ── Step 0: Load data ───────────────────────────────────────────────
console.log('Loading data...');
const periodARows = loadCsv(periodACsvPath);
const periodBRows = loadCsv(periodBCsvPath);
const campaignRows = loadCsv(campaignsCsvPath);
const portfolioRows = loadCsv(portfoliosCsvPath);
const convByActionARows = convByActionACsvPath ? loadCsv(convByActionACsvPath) : [];
const convByActionBRows = convByActionBCsvPath ? loadCsv(convByActionBCsvPath) : [];

console.log(`Period A: ${periodARows.length} rows`);
console.log(`Period B: ${periodBRows.length} rows`);
console.log(`Campaigns: ${campaignRows.length} rows`);
console.log(`Portfolios: ${portfolioRows.length} rows`);
console.log(`Conv-by-action Period A: ${convByActionARows.length} rows`);
console.log(`Conv-by-action Period B: ${convByActionBRows.length} rows`);

if (!isFallbackMode && convByActionARows.length === 0) {
    console.warn('⚠ No conv-by-action Period A data — primary conversion counts will be 0 for all keywords.');
    console.warn('  Check that keywords-conv-by-action-periodA.csv was pulled correctly.');
}

// Build per-period lookups
const convByActionLookupA = buildConvByActionLookup(convByActionARows);
const convByActionLookupB = buildConvByActionLookup(convByActionBRows);
console.log(`Conv-by-action lookup A: ${convByActionLookupA.size} keywords with tracked conversions`);
console.log(`Conv-by-action lookup B: ${convByActionLookupB.size} keywords with tracked conversions`);

// Filter out experiments
const periodA = periodARows.filter(r => !r.campaign_experiment_type || r.campaign_experiment_type === 'BASE' || r.campaign_experiment_type === '');
const periodB = periodBRows.filter(r => !r.campaign_experiment_type || r.campaign_experiment_type === 'BASE' || r.campaign_experiment_type === '');

console.log(`After experiment filter: Period A=${periodA.length}, Period B=${periodB.length}`);

// ── Step 1: Load campaign targets ───────────────────────────────────
console.log('Loading campaign targets...');

// Build portfolio bid strategy lookup, keyed by resource_name.
// Portfolio targets are authoritative when a campaign attaches to a portfolio —
// the inline `campaign.target_roas.target_roas` field is null in that case.
const portfolioTargets = new Map();
for (const p of portfolioRows) {
    const resourceName = p.bidding_strategy_resource_name || '';
    if (!resourceName) continue;

    let targetCpa = numOrNull(p.bidding_strategy_target_cpa_target_cpa);
    if (targetCpa === null) targetCpa = numOrNull(p.bidding_strategy_maximize_conversions_target_cpa);

    let targetRoas = numOrNull(p.bidding_strategy_target_roas_target_roas);
    if (targetRoas === null) targetRoas = numOrNull(p.bidding_strategy_maximize_conversion_value_target_roas);

    portfolioTargets.set(resourceName, {
        id: p.bidding_strategy_id || '',
        name: p.bidding_strategy_name || '',
        type: p.bidding_strategy_type || '',
        targetCpa,
        targetRoas,
    });
}
if (portfolioTargets.size > 0) {
    console.log(`Portfolio targets loaded: ${portfolioTargets.size}`);
}

const campaignTargets = new Map();

// First, build from campaigns-settings.csv
for (const c of campaignRows) {
    const cid = c.campaign_id;
    if (!cid) continue;

    const stratType = c.campaign_bidding_strategy_type || '';
    let mode = biddingMode(stratType);

    // Extract target CPA (query.js auto-converts micros → dollars)
    let targetCpa = numOrNull(c.campaign_target_cpa_target_cpa);
    if (targetCpa === null) targetCpa = numOrNull(c.campaign_maximize_conversions_target_cpa);

    // Extract target ROAS
    let targetRoas = numOrNull(c.campaign_target_roas_target_roas);
    if (targetRoas === null) targetRoas = numOrNull(c.campaign_maximize_conversion_value_target_roas);

    // Source precedence: inline campaign target > portfolio target > computed fallback.
    // Portfolio lookup runs only when the inline target is null AND the campaign is
    // linked to a portfolio (non-empty `campaign.bidding_strategy` resource name).
    let targetSource = (targetCpa !== null || targetRoas !== null) ? 'campaign_inline' : 'none';
    let portfolioName = '';
    let portfolioResource = '';

    if (targetSource === 'none') {
        const portfolioRef = c.campaign_bidding_strategy || '';
        if (portfolioRef && portfolioTargets.has(portfolioRef)) {
            const pt = portfolioTargets.get(portfolioRef);
            if (pt.targetCpa !== null || pt.targetRoas !== null) {
                targetCpa = pt.targetCpa;
                targetRoas = pt.targetRoas;
                targetSource = 'portfolio';
                portfolioName = pt.name;
                portfolioResource = portfolioRef;
            }
        }
    }

    campaignTargets.set(cid, {
        targetCpa,
        targetRoas,
        biddingMode: mode,
        strategyType: stratType,
        targetSource,
        portfolioName,
        portfolioResource,
    });
}

// ── Step 2: Aggregate campaign-level totals from Period A ───────────
console.log('Computing campaign totals...');

function buildCampaignTotals(rows, convLookup) {
    const totals = new Map();
    for (const row of rows) {
        const cid = row.campaign_id;
        if (!totals.has(cid)) {
            totals.set(cid, {
                totalCost: 0,
                totalBlendedConversions: 0,
                totalPrimaryConversions: 0,
                totalEffectiveConversions: 0,
                totalEffectiveConvValue: 0,
                kwCount: 0,
            });
        }
        const t = totals.get(cid);
        const cost = num(row.metrics_cost);
        const blendedConv = num(row.metrics_conversions);
        const blendedVal = num(row.metrics_conversions_value);
        const { primaryConversions, effectiveConversions, effectiveConvValue } =
            resolveConvByAction(row.ad_group_id, row.ad_group_criterion_criterion_id, blendedConv, blendedVal, convLookup);

        t.totalCost += cost;
        t.totalBlendedConversions += blendedConv;
        t.totalPrimaryConversions += primaryConversions;
        t.totalEffectiveConversions += effectiveConversions;
        t.totalEffectiveConvValue += effectiveConvValue;
        t.kwCount++;
    }
    return totals;
}

const campaignTotals = buildCampaignTotals(periodA, convByActionLookupA);

// Compute campaign-level fallback targets (average CPA/ROAS based on primary conversions).
// Fallback is only used when neither the campaign nor an attached portfolio supplied a
// real target. When fallback is the source, synthesis must treat the campaign as
// "unconstrained" — tagged via target.targetSource === 'fallback'.
for (const [cid, t] of campaignTotals) {
    const target = campaignTargets.get(cid);
    if (target) {
        if (target.targetCpa === null && t.totalPrimaryConversions > 0) {
            target.fallbackCpa = t.totalCost / t.totalPrimaryConversions;
            if (target.targetSource === 'none') target.targetSource = 'fallback';
        }
        if (target.targetRoas === null && t.totalCost > 0) {
            target.fallbackRoas = t.totalEffectiveConvValue / t.totalCost;
            if (target.targetSource === 'none') target.targetSource = 'fallback';
        }
        target.avgConversions = t.kwCount > 0 ? t.totalPrimaryConversions / t.kwCount : 0;
    }
}

// ── Step 3-4: Classify each keyword ─────────────────────────────────
console.log('Classifying keywords...');

function classifyKeywords(rows, convLookup, totalsForPeriod) {
    const results = [];

    for (const row of rows) {
        const cid = row.campaign_id;
        const target = campaignTargets.get(cid);
        const totals = totalsForPeriod.get(cid);
        const criterionId = row.ad_group_criterion_criterion_id || '';
        const adGroupId = row.ad_group_id || '';

        const impressions = num(row.metrics_impressions);
        const clicks = num(row.metrics_clicks);
        const cost = num(row.metrics_cost);
        const blendedConv = num(row.metrics_conversions);
        const blendedConvValue = num(row.metrics_conversions_value);

        // Business-grounded per-action metrics (or blended in fallback mode)
        const { primaryConversions, effectiveConversions, effectiveConvValue } =
            resolveConvByAction(adGroupId, criterionId, blendedConv, blendedConvValue, convLookup);

        const primaryCpa = primaryConversions > 0 ? cost / primaryConversions : null;
        const effectiveCpa = effectiveConversions > 0 ? cost / effectiveConversions : null;
        const effectiveRoas = cost > 0 ? effectiveConvValue / cost : null;
        const ctr = impressions > 0 ? clicks / impressions : null;

        const spendShare = (totals && totals.totalCost > 0) ? cost / totals.totalCost : 0;
        const convShare = (totals && totals.totalPrimaryConversions > 0)
            ? primaryConversions / totals.totalPrimaryConversions
            : 0;

        const effectiveTargetCpa = target?.targetCpa ?? target?.fallbackCpa ?? null;
        const effectiveTargetRoas = target?.targetRoas ?? target?.fallbackRoas ?? null;
        const mode = target?.biddingMode ?? 'MANUAL';

        // Relevance guard — core product terms get extra patience before pause
        const keywordText = row.ad_group_criterion_keyword_text || '';
        const isCoreTerm = isCoreProductTerm(keywordText);
        const patienceMultiplier = isCoreTerm ? CFG.coreTermsPatienceMultiplier : 1.0;

        // Pause statistical gate: required zero-conv spend before pause is defensible.
        // Floors at absolutePauseFloor so small accounts don't get aggressive pauses.
        // CPA mode:  max(breakEvenCPA × multiplier × patience, absolutePauseFloor)
        // ROAS mode: max(absolutePauseFloor × multiplier × patience, absolutePauseFloor)
        let pauseSpendThreshold = null;
        if (CFG.primaryKPI === 'roas') {
            // ROAS mode: no CPA to derive from, so use the absolute floor scaled by patience
            pauseSpendThreshold = Math.max(
                CFG.absolutePauseFloor * CFG.pauseStatisticalMultiplier * patienceMultiplier,
                CFG.absolutePauseFloor
            );
        } else if (CFG.breakEvenCPA !== null) {
            pauseSpendThreshold = Math.max(
                CFG.breakEvenCPA * CFG.pauseStatisticalMultiplier * patienceMultiplier,
                CFG.absolutePauseFloor
            );
        }

        // ── Tier decision tree ──────────────────────────────────────
        let tier = 'ACTIVE';
        let isHeroSpender = false;

        // KPI-aware profitability check:
        //   CPA mode:  unprofitable when primaryCpa > breakEvenCPA
        //   ROAS mode: unprofitable when effectiveRoas < breakEvenROAS
        let isUnprofitable = false;
        if (CFG.primaryKPI === 'roas') {
            isUnprofitable = CFG.breakEvenROAS !== null
                && effectiveRoas !== null
                && effectiveRoas < CFG.breakEvenROAS;
        } else {
            isUnprofitable = CFG.breakEvenCPA !== null
                && primaryCpa !== null
                && primaryCpa > CFG.breakEvenCPA;
        }

        // KPI-aware over-target check:
        //   CPA mode:  primaryCpa > villainCpaMultiplier × tCPA (above target, but still profitable)
        //   ROAS mode: effectiveRoas < villainRoasMultiplier × tROAS (below target, but still profitable)
        const isOverTarget = CFG.primaryKPI === 'roas'
            ? (effectiveTargetRoas !== null && effectiveRoas !== null &&
               effectiveRoas < CFG.villainRoasMultiplier * effectiveTargetRoas &&
               !isUnprofitable)
            : (effectiveTargetCpa !== null && primaryCpa !== null &&
               primaryCpa > CFG.villainCpaMultiplier * effectiveTargetCpa);

        const approvalStatus = row.ad_group_criterion_approval_status || '';

        if (approvalStatus === 'DISAPPROVED') {
            // Disapproved keywords can't serve → would otherwise land in ZOMBIE (0 impressions)
            // and get mislabeled as "cleanup waste" by KW-D08. The real fix is resolving the
            // disapproval (policy, landing page, trademark), not pausing.
            tier = 'DISAPPROVED';
        } else if (impressions === 0) {
            tier = 'ZOMBIE';
        } else if (convShare > CFG.heroShareThreshold ||
                   (spendShare > CFG.heroShareThreshold && primaryConversions > 0)) {
            // HERO gate requires merit: top converter, or top spender that is actually
            // converting. A top-spend keyword with zero primary conversions falls
            // through to the zero-conv branch where the pause gate decides its fate —
            // otherwise a small ad group's biggest waster gets mislabeled HERO.
            //
            // HERO is also profitability-aware: a top-spend/top-conv keyword that is
            // losing money per acquisition is the single most important finding in the
            // audit, so it must NOT be hidden behind the HERO label. Demote to
            // UNPROFITABLE and flag `is_hero_spender=true` so D07 can surface it first.
            if (isUnprofitable) {
                tier = 'UNPROFITABLE';
                isHeroSpender = true;
            } else {
                tier = 'HERO';
            }
        } else if (clicks === 0) {
            tier = 'LOW_PERFORMER';
        } else if (primaryConversions > 0) {
            // Converting keyword — profitability check first (business), then bid target
            if (isUnprofitable) {
                tier = 'UNPROFITABLE';
            } else if (isOverTarget) {
                tier = 'OVER_TARGET';
            } else {
                tier = 'ACTIVE';
            }
        } else {
            // Zero primary conversions — pause gate or insufficient data
            if (clicks < CFG.minClicksForEval) {
                tier = 'INSUFFICIENT_DATA';
            } else if (pauseSpendThreshold !== null && cost >= pauseSpendThreshold) {
                tier = 'PAUSE_CANDIDATE';
            } else {
                // Has clicks but not enough zero-conv spend to justify pause — still learning
                tier = 'INSUFFICIENT_DATA';
            }
        }

        results.push({
            keyword_text: keywordText,
            match_type: row.ad_group_criterion_keyword_match_type || '',
            campaign_name: row.campaign_name || '',
            ad_group_name: row.ad_group_name || '',
            campaign_id: cid || '',
            ad_group_id: row.ad_group_id || '',
            criterion_id: criterionId,
            status: row.ad_group_criterion_status || '',
            approval_status: approvalStatus,
            impressions,
            clicks,
            cost: cost.toFixed(2),
            blended_conversions: blendedConv.toFixed(2),
            primary_conversions: primaryConversions.toFixed(2),
            effective_conversions: effectiveConversions.toFixed(2),
            effective_conv_value: effectiveConvValue.toFixed(2),
            primary_cpa: primaryCpa !== null ? primaryCpa.toFixed(2) : '',
            effective_cpa: effectiveCpa !== null ? effectiveCpa.toFixed(2) : '',
            effective_roas: effectiveRoas !== null ? effectiveRoas.toFixed(2) : '',
            ctr: ctr !== null ? (ctr * 100).toFixed(2) : '',
            spend_share: (spendShare * 100).toFixed(2),
            conversion_share: (convShare * 100).toFixed(2),
            quality_score: row.ad_group_criterion_quality_info_quality_score || '',
            expected_ctr: row.ad_group_criterion_quality_info_search_predicted_ctr || '',
            ad_relevance: row.ad_group_criterion_quality_info_creative_quality_score || '',
            landing_page_exp: row.ad_group_criterion_quality_info_post_click_quality_score || '',
            tier,
            is_hero_spender: isHeroSpender ? 'true' : 'false',
            prior_tier: '',
            tier_shifted: 'false',
            bidding_mode: mode,
            campaign_target_cpa: effectiveTargetCpa !== null ? effectiveTargetCpa.toFixed(2) : '',
            campaign_target_roas: effectiveTargetRoas !== null ? effectiveTargetRoas.toFixed(2) : '',
            target_source: target?.targetSource ?? 'none',
            portfolio_name: target?.portfolioName ?? '',
            break_even_cpa: CFG.breakEvenCPA !== null ? Number(CFG.breakEvenCPA).toFixed(2) : '',
            break_even_roas: CFG.breakEvenROAS !== null ? Number(CFG.breakEvenROAS).toFixed(2) : '',
            primary_kpi: CFG.primaryKPI,
            is_core_term: isCoreTerm ? 'true' : 'false',
            patience_multiplier: patienceMultiplier.toFixed(1),
            pause_spend_threshold: pauseSpendThreshold !== null ? pauseSpendThreshold.toFixed(2) : '',
        });
    }

    return results;
}

const tiersA = classifyKeywords(periodA, convByActionLookupA, campaignTotals);

// ── Step 5: Period-over-period tier shift (D09) ─────────────────────
if (CFG.tierShiftEnabled && periodB.length > 0) {
    console.log('Computing tier shifts...');

    // Build Period B campaign totals (using Period B conv-by-action lookup)
    const campaignTotalsB = buildCampaignTotals(periodB, convByActionLookupB);

    const tiersB = classifyKeywords(periodB, convByActionLookupB, campaignTotalsB);

    // Build lookup: (ad_group_id, criterion_id) → tier from Period B
    const priorTierMap = new Map();
    for (const b of tiersB) {
        priorTierMap.set(kwKey(b.ad_group_id, b.criterion_id), b.tier);
    }

    // Compare and annotate tier shifts (higher rank = better)
    const tierRank = {
        HERO: 7,
        ACTIVE: 6,
        OVER_TARGET: 5,
        INSUFFICIENT_DATA: 4,
        LOW_PERFORMER: 3,
        UNPROFITABLE: 2,
        PAUSE_CANDIDATE: 1,
        ZOMBIE: 0,
        DISAPPROVED: 0,
    };

    for (const a of tiersA) {
        const priorTier = priorTierMap.get(kwKey(a.ad_group_id, a.criterion_id));
        if (priorTier) {
            a.prior_tier = priorTier;
            const currentRank = tierRank[a.tier] ?? 3;
            const priorRank = tierRank[priorTier] ?? 3;
            if (currentRank < priorRank) {
                a.tier_shifted = 'DEGRADED';
            } else if (currentRank > priorRank) {
                a.tier_shifted = 'IMPROVED';
            } else {
                a.tier_shifted = 'STABLE';
            }
        }
    }
} else if (periodB.length === 0) {
    console.log('No Period B data — skipping tier shift analysis.');
}

// ── Step 6-7: Generate flags ────────────────────────────────────────
console.log('Generating flags...');

const flags = [];

for (const kw of tiersA) {
    const matchType = kw.match_type;
    const cid = kw.campaign_id;
    const target = campaignTargets.get(cid);

    // HERO flag (INFO only)
    if (kw.tier === 'HERO') {
        flags.push({
            ...flagBase(kw),
            flag_type: 'HERO',
            flag_severity: 'Info',
            flag_detail: `${kw.keyword_text} accounts for ${kw.spend_share}% spend, ${kw.conversion_share}% primary conversions`,
        });
    }

    // PAUSE_CANDIDATE — zero primary conv AND spend exceeds statistical gate
    if (kw.tier === 'PAUSE_CANDIDATE') {
        const coreNote = kw.is_core_term === 'true' ? ` [core term, patience ×${kw.patience_multiplier}]` : '';
        const gateDetail = CFG.primaryKPI === 'roas'
            ? `(${CFG.pauseStatisticalMultiplier}× pause floor $${CFG.absolutePauseFloor})`
            : `(${CFG.pauseStatisticalMultiplier}× break-even CPA $${kw.break_even_cpa})`;
        flags.push({
            ...flagBase(kw),
            flag_type: 'PAUSE_CANDIDATE',
            flag_severity: 'High',
            flag_detail: `${kw.clicks} clicks, 0 primary conv, $${kw.cost} spend ≥ pause gate $${kw.pause_spend_threshold} ${gateDetail}${coreNote}`,
        });
    }

    // UNPROFITABLE — converting but beyond profitability threshold
    if (kw.tier === 'UNPROFITABLE') {
        const heroNote = kw.is_hero_spender === 'true'
            ? ` [HERO_SPENDER — ${kw.spend_share}% spend share, top money-loser in the campaign]`
            : '';
        const profDetail = CFG.primaryKPI === 'roas'
            ? `ROAS ${kw.effective_roas} < break-even ${kw.break_even_roas}. Converting (${kw.primary_conversions}) but below profitability threshold.`
            : `Primary CPA $${kw.primary_cpa} > break-even $${kw.break_even_cpa}. Converting (${kw.primary_conversions}) but loses money per acquisition.`;
        flags.push({
            ...flagBase(kw),
            flag_type: 'UNPROFITABLE',
            flag_severity: kw.is_hero_spender === 'true' ? 'Critical' : 'High',
            flag_detail: `${profDetail}${heroNote}`,
        });
    }

    // OVER_TARGET — converting profitably but beyond campaign target (bidding issue, not waste)
    if (kw.tier === 'OVER_TARGET') {
        const targetDetail = CFG.primaryKPI === 'roas'
            ? `ROAS ${kw.effective_roas} < ${CFG.villainRoasMultiplier}× tROAS ${kw.campaign_target_roas}, but above break-even ${kw.break_even_roas}. Review bids / target ROAS segmentation — do not pause.`
            : `Primary CPA $${kw.primary_cpa} > ${CFG.villainCpaMultiplier}× tCPA $${kw.campaign_target_cpa}, but under break-even $${kw.break_even_cpa}. Review bids / target CPA segmentation — do not pause.`;
        flags.push({
            ...flagBase(kw),
            flag_type: 'OVER_TARGET',
            flag_severity: 'Medium',
            flag_detail: targetDetail,
        });
    }

    // ZOMBIE flag
    if (kw.tier === 'ZOMBIE') {
        flags.push({
            ...flagBase(kw),
            flag_type: 'ZOMBIE',
            flag_severity: 'Medium',
            flag_detail: `0 impressions in evaluation period`,
        });
    }

    // DISAPPROVED flag — distinct from ZOMBIE so D08 doesn't misread it as cleanup waste.
    // Root cause is a policy/content disapproval that must be resolved, not a pause candidate.
    if (kw.tier === 'DISAPPROVED') {
        flags.push({
            ...flagBase(kw),
            flag_type: 'DISAPPROVED',
            flag_severity: 'High',
            flag_detail: `Keyword disapproved — ineligible to serve. Fix the disapproval (policy/landing page/trademark) rather than pause.`,
        });
    }

    // LOW_PERFORMER flag
    if (kw.tier === 'LOW_PERFORMER') {
        flags.push({
            ...flagBase(kw),
            flag_type: 'LOW_PERFORMER',
            flag_severity: 'Medium',
            flag_detail: `${kw.impressions} impressions, 0 clicks in evaluation period`,
        });
    }

    // TIER_DEGRADED flag (D09)
    if (kw.tier_shifted === 'DEGRADED') {
        flags.push({
            ...flagBase(kw),
            flag_type: 'TIER_DEGRADED',
            flag_severity: 'Medium',
            flag_detail: `${kw.keyword_text} shifted from ${kw.prior_tier} to ${kw.tier}`,
        });
    }

    // BROAD_WITHOUT_SMART_BIDDING flag (D02)
    if (matchType === 'BROAD' && BROAD_WITHOUT_SMART_BIDDING_STRATEGIES.has(target?.strategyType || '')) {
        const stratType = target?.strategyType || '';
        flags.push({
            ...flagBase(kw),
            flag_type: 'BROAD_WITHOUT_SMART_BIDDING',
            flag_severity: 'Medium',
            flag_detail: `Broad match keyword on ${stratType} campaign — no smart bidding safety net`,
        });
    }

    // BELOW_FIRST_PAGE_BID (D14) is emitted in a second pass below — it needs
    // bid data enriched from the raw Period A rows, which is not on `kw` yet.

    // BRAND_IN_NON_BRAND flag (D18 pre-flag for exact brand matches)
    const normalizedKeyword = normalizeText(kw.keyword_text);
    if (
        exactBrandTerms.size > 0 &&
        normalizedKeyword &&
        exactBrandTerms.has(normalizedKeyword) &&
        !isBrandedCampaign(kw.campaign_name)
    ) {
        flags.push({
            ...flagBase(kw),
            flag_type: 'BRAND_IN_NON_BRAND',
            flag_severity: 'Medium',
            flag_detail: `Exact brand keyword "${kw.keyword_text}" found in non-brand campaign "${kw.campaign_name}"`,
        });
    }
}

function flagBase(kw) {
    return {
        keyword_text: kw.keyword_text,
        match_type: kw.match_type,
        campaign_name: kw.campaign_name,
        ad_group_name: kw.ad_group_name,
        campaign_id: kw.campaign_id,
        ad_group_id: kw.ad_group_id,
        criterion_id: kw.criterion_id,
        impressions: kw.impressions,
        clicks: kw.clicks,
        cost: kw.cost,
        primary_conversions: kw.primary_conversions,
        primary_cpa: kw.primary_cpa,
        effective_conversions: kw.effective_conversions,
        effective_cpa: kw.effective_cpa,
        effective_roas: kw.effective_roas,
        break_even_cpa: kw.break_even_cpa,
        break_even_roas: kw.break_even_roas,
        primary_kpi: kw.primary_kpi,
        is_core_term: kw.is_core_term,
        quality_score: kw.quality_score,
        campaign_bidding_strategy_type: campaignTargets.get(kw.campaign_id)?.strategyType || '',
        campaign_target_cpa: kw.campaign_target_cpa,
        campaign_target_roas: kw.campaign_target_roas,
        is_hero_spender: kw.is_hero_spender || 'false',
    };
}

// ── Step 8: Write outputs ───────────────────────────────────────────

// Preserve bid data from raw rows for D14 (before writing, enrich tiersA with bid info)
// We need to re-read raw data to get bid fields that weren't in the classifyKeywords output
const bidLookup = new Map();
for (const row of periodA) {
    const crid = row.ad_group_criterion_criterion_id;
    const agId = row.ad_group_id;
    if (crid && agId) {
        bidLookup.set(kwKey(agId, crid), {
            effectiveBid: row.ad_group_criterion_effective_cpc_bid || '',
            firstPageBid: row.ad_group_criterion_position_estimates_first_page_cpc || '',
        });
    }
}

// Enrich flags for D14 with bid data
for (const kw of tiersA) {
    const bid = bidLookup.get(kwKey(kw.ad_group_id, kw.criterion_id));
    if (bid) {
        kw._effectiveBid = bid.effectiveBid;
        kw._firstPageBid = bid.firstPageBid;
    }
}

// D14 BELOW_FIRST_PAGE_BID: needs bid data enriched above
for (const kw of tiersA) {
    const target = campaignTargets.get(kw.campaign_id);
    if (target?.strategyType !== 'MANUAL_CPC') continue;
    const effectiveBid = numOrNull(kw._effectiveBid);
    const firstPageBid = numOrNull(kw._firstPageBid);
    if (effectiveBid !== null && firstPageBid !== null && effectiveBid < firstPageBid) {
        flags.push({
            ...flagBase(kw),
            flag_type: 'BELOW_FIRST_PAGE_BID',
            flag_severity: 'Low',
            flag_detail: `Bid $${Number(effectiveBid).toFixed(2)} < first page estimate $${Number(firstPageBid).toFixed(2)}`,
        });
    }
}

// Clean internal fields before writing
for (const kw of tiersA) {
    delete kw._effectiveBid;
    delete kw._firstPageBid;
}

// Tiers CSV
const tiersHeaders = [
    'keyword_text', 'match_type', 'campaign_name', 'ad_group_name', 'campaign_id', 'ad_group_id',
    'criterion_id', 'status', 'approval_status', 'impressions', 'clicks', 'cost',
    'blended_conversions', 'primary_conversions', 'effective_conversions', 'effective_conv_value',
    'primary_cpa', 'effective_cpa', 'effective_roas',
    'ctr', 'spend_share', 'conversion_share',
    'quality_score', 'expected_ctr', 'ad_relevance', 'landing_page_exp',
    'tier', 'prior_tier', 'tier_shifted', 'is_hero_spender',
    'bidding_mode', 'campaign_target_cpa', 'campaign_target_roas',
    'target_source', 'portfolio_name',
    'break_even_cpa', 'break_even_roas', 'primary_kpi',
    'is_core_term', 'patience_multiplier', 'pause_spend_threshold',
];

writeCsv(tiersOutputPath, tiersHeaders, tiersA);
console.log(`File: ${tiersOutputPath}`);
console.log(`Rows: ${tiersA.length}`);

// Flags CSV
const flagsHeaders = [
    'keyword_text', 'match_type', 'campaign_name', 'ad_group_name', 'campaign_id', 'ad_group_id',
    'criterion_id', 'flag_type', 'flag_severity', 'flag_detail',
    'impressions', 'clicks', 'cost',
    'primary_conversions', 'primary_cpa', 'effective_conversions', 'effective_cpa', 'effective_roas',
    'break_even_cpa', 'break_even_roas', 'primary_kpi', 'is_core_term',
    'quality_score', 'campaign_bidding_strategy_type',
    'campaign_target_cpa', 'campaign_target_roas',
];

writeCsv(flagsOutputPath, flagsHeaders, flags);
console.log(`File: ${flagsOutputPath}`);
console.log(`Rows: ${flags.length}`);

// ── Data sufficiency check ──────────────────────────────────────────
let totalPrimaryConversions = 0;
for (const [, t] of campaignTotals) {
    totalPrimaryConversions += t.totalPrimaryConversions;
}

if (totalPrimaryConversions < 15) {
    console.warn(`\n⚠ Only ${totalPrimaryConversions.toFixed(0)} primary conversions in evaluation window. Tier classification may be unreliable.`);
    console.warn(`  Re-run with a longer window: /keyword-audit 60 or /keyword-audit 90`);
}

// Summary stats
const tierCounts = {};
for (const kw of tiersA) {
    tierCounts[kw.tier] = (tierCounts[kw.tier] || 0) + 1;
}
console.log(`\nTier distribution: ${JSON.stringify(tierCounts)}`);
console.log(`Flags generated: ${flags.length}`);
console.log('Done.');
