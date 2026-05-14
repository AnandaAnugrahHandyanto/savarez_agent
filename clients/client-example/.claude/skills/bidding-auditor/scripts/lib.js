/**
 * Shared utilities for the bidding-auditor analysis engines.
 * All helpers are pure (no I/O) and account-agnostic — they read whatever
 * the engine passes in and never assume specific campaign/conv-action names.
 */

import { existsSync, readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

let _projectRoot = __dirname;
while (_projectRoot !== '/' && !existsSync(resolve(_projectRoot, 'config'))) {
    _projectRoot = resolve(_projectRoot, '..');
}
export const PROJECT_ROOT = _projectRoot;

// ── CSV reading ────────────────────────────────────────────────────────

export function readCsv(path) {
    if (!existsSync(path)) return [];
    const text = readFileSync(path, 'utf8').trim();
    if (!text) return [];
    const lines = text.split('\n');
    const headers = parseCsvLine(lines[0]);
    return lines.slice(1).map(line => {
        const cells = parseCsvLine(line);
        const row = {};
        headers.forEach((h, i) => { row[h] = cells[i] ?? ''; });
        return row;
    });
}

function parseCsvLine(line) {
    const out = [];
    let cur = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
        const c = line[i];
        if (inQuotes) {
            if (c === '"' && line[i + 1] === '"') { cur += '"'; i++; }
            else if (c === '"') inQuotes = false;
            else cur += c;
        } else {
            if (c === '"') inQuotes = true;
            else if (c === ',') { out.push(cur); cur = ''; }
            else cur += c;
        }
    }
    out.push(cur);
    return out;
}

// ── Number coercion ────────────────────────────────────────────────────

export function num(v, fallback = 0) {
    if (v === null || v === undefined || v === '') return fallback;
    const n = typeof v === 'number' ? v : Number(v);
    return Number.isFinite(n) ? n : fallback;
}

export function pct(part, whole) {
    if (!whole || !Number.isFinite(whole) || whole === 0) return 0;
    return (part / whole) * 100;
}

// ── Currency / target formatting ───────────────────────────────────────

export function microsToDollars(micros) {
    return num(micros) / 1_000_000;
}

export function formatTarget(value, kpi) {
    if (value == null || !Number.isFinite(value)) return '—';
    if (kpi === 'roas') return `${(value * 100).toFixed(0)}%`;
    return `$${value.toFixed(2)}`;
}

export function formatCurrency(amount, currency = 'USD') {
    const n = num(amount);
    return new Intl.NumberFormat('en-US', {
        style: 'currency', currency, maximumFractionDigits: 2,
    }).format(n);
}

// ── Channel detection ──────────────────────────────────────────────────

export function getChannelType(campaignRow) {
    return (campaignRow['campaign.advertising_channel_type'] || '').toUpperCase();
}

export function isSearch(row)   { return getChannelType(row) === 'SEARCH'; }
export function isShopping(row) { return getChannelType(row) === 'SHOPPING'; }
export function isPMax(row)     { return getChannelType(row) === 'PERFORMANCE_MAX'; }
export function isDisplay(row)  { return getChannelType(row) === 'DISPLAY'; }
export function isVideo(row)    { return getChannelType(row) === 'VIDEO'; }
export function isDemandGen(row){ return getChannelType(row) === 'DEMAND_GEN'; }

// ── Bid strategy classification ───────────────────────────────────────

export const SMART_BIDDING_TYPES = new Set([
    'TARGET_CPA', 'TARGET_ROAS',
    'MAXIMIZE_CONVERSIONS', 'MAXIMIZE_CONVERSION_VALUE',
]);

export const MANUAL_BIDDING_TYPES = new Set([
    'MANUAL_CPC', 'MANUAL_CPM', 'MANUAL_CPV', 'PERCENT_CPC',
]);

export const TARGET_CARRYING_TYPES = new Set([
    'TARGET_CPA', 'TARGET_ROAS',
]);

export const VALUE_BASED_TYPES = new Set([
    'TARGET_ROAS', 'MAXIMIZE_CONVERSION_VALUE',
]);

export function isSmartBidding(strategyType) {
    return SMART_BIDDING_TYPES.has((strategyType || '').toUpperCase());
}

export function isManualBidding(strategyType) {
    return MANUAL_BIDDING_TYPES.has((strategyType || '').toUpperCase());
}

export function isValueBased(strategyType) {
    return VALUE_BASED_TYPES.has((strategyType || '').toUpperCase());
}

// ── Campaign target resolution (inline OR portfolio) ───────────────────

/**
 * Resolve the effective bid target for a campaign row.
 * If the campaign has a portfolio (`campaign.bidding_strategy`), look up the
 * matching bidding_strategy row and use its target.
 */
export function resolveCampaignTarget(campaignRow, portfolioRowsById) {
    const type = (campaignRow['campaign.bidding_strategy_type'] || '').toUpperCase();
    const portfolioResource = campaignRow['campaign.bidding_strategy'];

    let targetCpaMicros = null;
    let targetRoas = null;
    let source = 'inline';
    let portfolioName = null;

    // Inline targets first
    targetCpaMicros = num(campaignRow['campaign.target_cpa.target_cpa_micros'], null)
        || num(campaignRow['campaign.maximize_conversions.target_cpa_micros'], null);
    targetRoas = num(campaignRow['campaign.target_roas.target_roas'], null)
        || num(campaignRow['campaign.maximize_conversion_value.target_roas'], null);

    if (portfolioResource && portfolioRowsById) {
        // Look up by resource_name
        const p = portfolioRowsById.get(portfolioResource);
        if (p) {
            source = 'portfolio';
            portfolioName = p['bidding_strategy.name'] || null;
            const pCpa = num(p['bidding_strategy.target_cpa.target_cpa_micros'], null)
                || num(p['bidding_strategy.maximize_conversions.target_cpa_micros'], null);
            const pRoas = num(p['bidding_strategy.target_roas.target_roas'], null)
                || num(p['bidding_strategy.maximize_conversion_value.target_roas'], null);
            if (pCpa) targetCpaMicros = pCpa;
            if (pRoas) targetRoas = pRoas;
        }
    }

    return {
        type,
        source,
        portfolioName,
        portfolioResource,
        targetCpa: targetCpaMicros ? microsToDollars(targetCpaMicros) : null,
        targetRoas: targetRoas || null,
        hasTarget: !!(targetCpaMicros || targetRoas),
    };
}

export function indexPortfoliosByResource(portfolioRows) {
    const m = new Map();
    for (const r of portfolioRows) {
        const key = r['bidding_strategy.resource_name'];
        if (key) m.set(key, r);
    }
    return m;
}

// ── Conversion volume thresholds (channel + strategy aware) ───────────
// Mirrors /sops/Conversion Volume Thresholds Reference.md.
// Returns minimums { absolute, functional, recommended } in monthly conversions.

const VOLUME_THRESHOLDS = {
    SEARCH: {
        TARGET_CPA: { absolute: 15, functional: 30, recommended: 50 },
        TARGET_ROAS: { absolute: 30, functional: 50, recommended: 50 },
        MAXIMIZE_CONVERSIONS: { absolute: 15, functional: 30, recommended: 50 },
        MAXIMIZE_CONVERSION_VALUE: { absolute: 30, functional: 50, recommended: 50 },
    },
    SHOPPING: {
        TARGET_ROAS: { absolute: 30, functional: 50, recommended: 50 },
    },
    PERFORMANCE_MAX: {
        TARGET_CPA: { absolute: 15, functional: 30, recommended: 50 },
        TARGET_ROAS: { absolute: 30, functional: 50, recommended: 50 },
    },
    DISPLAY: {
        TARGET_CPA: { absolute: 15, functional: 30, recommended: 50 },
        TARGET_ROAS: { absolute: 30, functional: 50, recommended: 50 },
        MAXIMIZE_CONVERSIONS: { absolute: 15, functional: 30, recommended: 50 },
    },
    VIDEO: {
        TARGET_CPA: { absolute: 15, functional: 30, recommended: 50 },
    },
    DEMAND_GEN: {
        TARGET_CPA: { absolute: 15, functional: 30, recommended: 50 },
        TARGET_ROAS: { absolute: 30, functional: 50, recommended: 50 },
    },
};

export function getConvVolumeThreshold(channelType, strategyType) {
    const ch = (channelType || '').toUpperCase();
    const st = (strategyType || '').toUpperCase();
    return VOLUME_THRESHOLDS[ch]?.[st] || null;
}

// ── Break-even margin & PAR ────────────────────────────────────────────

export function computeBreakEvenMargin(target, breakEven, kpi) {
    if (!target || !breakEven) return null;
    if (kpi === 'cpa') {
        // breakEven is the maximum profitable CPA → smaller target = safer.
        // margin = (breakEven - target) / breakEven
        return (breakEven - target) / breakEven;
    }
    if (kpi === 'roas') {
        // breakEven is the minimum profitable ROAS → larger target = safer.
        return (target - breakEven) / breakEven;
    }
    return null;
}

export function computePAR(actualCPA, targetCPA) {
    if (!actualCPA || !targetCPA) return null;
    return targetCPA / actualCPA;
}

// ── Target deviation ───────────────────────────────────────────────────

export function computeTargetDeviation(actualMetric, target) {
    if (!target || !Number.isFinite(target) || target === 0) return null;
    if (actualMetric == null || !Number.isFinite(actualMetric)) return null;
    return ((actualMetric - target) / target) * 100;
}

// ── Daily series helpers ───────────────────────────────────────────────

export function groupDailyByCampaign(dailyRows) {
    const map = new Map();
    for (const r of dailyRows) {
        const id = r['campaign.id'];
        if (!id) continue;
        if (!map.has(id)) map.set(id, []);
        map.get(id).push(r);
    }
    for (const arr of map.values()) {
        arr.sort((a, b) => (a['segments.date'] || '').localeCompare(b['segments.date'] || ''));
    }
    return map;
}

/**
 * Detect a CPC spike in the most recent ~14d window vs the prior ~14d window.
 * Returns { recent, prior, pctChange, isSpike } or null if insufficient data.
 */
export function detectCpcSpike(dailyRows, thresholdPct = 25) {
    if (!dailyRows || dailyRows.length < 14) return null;
    const halfIdx = Math.max(0, dailyRows.length - 14);
    const prior = dailyRows.slice(Math.max(0, halfIdx - 14), halfIdx);
    const recent = dailyRows.slice(halfIdx);
    const avgCpc = (rows) => {
        const cost = rows.reduce((s, r) => s + microsToDollars(r['metrics.cost_micros']), 0);
        const clicks = rows.reduce((s, r) => s + num(r['metrics.clicks']), 0);
        return clicks > 0 ? cost / clicks : null;
    };
    const recentCpc = avgCpc(recent);
    const priorCpc = avgCpc(prior);
    if (recentCpc == null || priorCpc == null || priorCpc === 0) return null;
    const pctChange = ((recentCpc - priorCpc) / priorCpc) * 100;
    return {
        recent: recentCpc,
        prior: priorCpc,
        pctChange,
        isSpike: pctChange >= thresholdPct,
    };
}

/**
 * Detect a rising-CPC trend across N consecutive periods of ~7d each.
 */
export function detectCpcRisingTrend(dailyRows, periods = 3, periodDays = 7) {
    if (!dailyRows || dailyRows.length < periods * periodDays) return null;
    const tail = dailyRows.slice(-periods * periodDays);
    const buckets = [];
    for (let i = 0; i < periods; i++) {
        const slice = tail.slice(i * periodDays, (i + 1) * periodDays);
        const cost = slice.reduce((s, r) => s + microsToDollars(r['metrics.cost_micros']), 0);
        const clicks = slice.reduce((s, r) => s + num(r['metrics.clicks']), 0);
        buckets.push(clicks > 0 ? cost / clicks : null);
    }
    if (buckets.some(b => b == null)) return null;
    let rising = true;
    for (let i = 1; i < buckets.length; i++) {
        if (buckets[i] <= buckets[i - 1]) { rising = false; break; }
    }
    return {
        buckets,
        rising,
    };
}

// ── Account changelog parsing ──────────────────────────────────────────

/**
 * Parse `context/account-changelog.md` and return per-campaign last-change
 * timestamps for bid-strategy / target changes. Account-changelog skill
 * writes one-line entries we can grep for.
 *
 * Returns Map(campaignNameLower → { lastStrategyChange: ISO, lastTargetChange: ISO }).
 */
export function parseAccountChangelog(text) {
    const map = new Map();
    if (!text) return map;
    const lines = text.split('\n');

    for (const line of lines) {
        // Skip blank + non-data lines
        if (!line.trim() || line.startsWith('#')) continue;

        // Try to extract a date (ISO) and a campaign name from any reasonable shape.
        const dateMatch = line.match(/(\d{4}-\d{2}-\d{2})/);
        if (!dateMatch) continue;
        const date = dateMatch[1];

        const lower = line.toLowerCase();
        const isBidChange = /bid[-_ ]?strateg|target_cpa|target_roas|tcpa|troas|maximize.conversion/i.test(line);
        if (!isBidChange) continue;

        const isStrategyChange = /strategy.*chang|swap|migrat|switch.*to|set.*to.*(target|maximize|manual)/i.test(line);
        const isTargetChange = /target.*(change|raise|lower|update|set)/i.test(line) || /\$\d/.test(line);

        // Best-effort campaign extraction: anything after "campaign:" or in quotes
        const campMatch = line.match(/campaign[:\s"]+([^"|\n]+?)(?:["|]|$)/i)
            || line.match(/"([^"]+)"/);
        if (!campMatch) continue;
        const campName = campMatch[1].trim().toLowerCase();

        const cur = map.get(campName) || { lastStrategyChange: null, lastTargetChange: null };
        if (isStrategyChange && (!cur.lastStrategyChange || cur.lastStrategyChange < date)) {
            cur.lastStrategyChange = date;
        }
        if (isTargetChange && (!cur.lastTargetChange || cur.lastTargetChange < date)) {
            cur.lastTargetChange = date;
        }
        map.set(campName, cur);
    }
    return map;
}

export function daysBetween(isoA, isoB) {
    if (!isoA || !isoB) return null;
    const a = new Date(isoA);
    const b = new Date(isoB);
    const diff = (b - a) / (1000 * 60 * 60 * 24);
    return Math.round(diff);
}

export function getLearningStatus(campaignName, changelog, learningWindow = 14, today = null) {
    const t = today || new Date().toISOString().slice(0, 10);
    const entry = changelog.get((campaignName || '').toLowerCase()) || {};
    const daysSinceStrategy = entry.lastStrategyChange
        ? daysBetween(entry.lastStrategyChange, t) : null;
    const daysSinceTarget = entry.lastTargetChange
        ? daysBetween(entry.lastTargetChange, t) : null;
    const inLearning =
        (daysSinceStrategy != null && daysSinceStrategy < learningWindow) ||
        (daysSinceTarget != null && daysSinceTarget < learningWindow);
    return {
        lastStrategyChange: entry.lastStrategyChange || null,
        lastTargetChange: entry.lastTargetChange || null,
        daysSinceStrategy,
        daysSinceTarget,
        inLearning,
    };
}

// ── Starvation detection (BID-D09) ─────────────────────────────────────

/**
 * Heuristic: aggressive target throttles delivery. Signals:
 * - high search_rank_lost_impression_share
 * - very low impression share
 * - actual_cpa well below target_cpa (or actual_roas well above target_roas)
 *   together with stagnant conversion volume
 */
export function detectStarvationZone(campaignRow, target) {
    const isLost = num(campaignRow['metrics.search_rank_lost_impression_share']);
    const is = num(campaignRow['metrics.search_impression_share']);
    const conv = num(campaignRow['metrics.conversions']);
    const cost = microsToDollars(campaignRow['metrics.cost_micros']);
    const actualCpa = conv > 0 ? cost / conv : null;
    const value = num(campaignRow['metrics.conversions_value']);
    const actualRoas = cost > 0 ? value / cost : null;

    if (target?.type === 'TARGET_CPA' && target.targetCpa && actualCpa) {
        const overlyTight = actualCpa < target.targetCpa * 0.7;
        if (overlyTight && isLost > 0.5 && is < 0.4) {
            return { isStarvation: true, reason: `actual CPA ${actualCpa.toFixed(2)} is well below target ${target.targetCpa}; rank-lost IS=${(isLost * 100).toFixed(0)}%` };
        }
    }
    if (target?.type === 'TARGET_ROAS' && target.targetRoas && actualRoas) {
        const overlyTight = actualRoas > target.targetRoas * 1.3;
        if (overlyTight && isLost > 0.5 && is < 0.4) {
            return { isStarvation: true, reason: `actual ROAS ${(actualRoas * 100).toFixed(0)}% well above target ${(target.targetRoas * 100).toFixed(0)}%; rank-lost IS=${(isLost * 100).toFixed(0)}%` };
        }
    }
    return { isStarvation: false };
}

// ── Opportunity heuristic (BID-D24 simulator gap) ──────────────────────

/**
 * Crude bid-simulator stand-in: estimate incremental conversions if budget
 * is loosened or target is relaxed. v1 heuristic — replaced in v1.1 by
 * CampaignBidSimulatorService.
 *
 * Inputs: campaign row, current target, breakEvenCPA (from config).
 * Returns an opportunity object or null.
 */
export function getOpportunityValue(campaignRow, target, breakEvenCpa) {
    const cost = microsToDollars(campaignRow['metrics.cost_micros']);
    const clicks = num(campaignRow['metrics.clicks']);
    const conv = num(campaignRow['metrics.conversions']);
    const isLostBudget = num(campaignRow['metrics.search_budget_lost_impression_share']);
    if (!conv || !clicks) return null;
    const cvr = conv / clicks;
    if (cvr <= 0) return null;

    if (isLostBudget > 0.1) {
        const incrementalClicks = clicks * (isLostBudget / Math.max(1 - isLostBudget, 0.01));
        const incrementalConv = incrementalClicks * cvr;
        const incrementalCost = incrementalClicks * (clicks > 0 ? cost / clicks : 0);
        const projectedCpa = incrementalConv > 0 ? incrementalCost / incrementalConv : null;
        const profitable = breakEvenCpa && projectedCpa ? projectedCpa <= breakEvenCpa : null;
        return {
            type: 'budget_lost_recovery',
            incrementalClicks: Math.round(incrementalClicks),
            incrementalConv: Math.round(incrementalConv * 10) / 10,
            incrementalCost: Math.round(incrementalCost * 100) / 100,
            projectedCpa: projectedCpa ? Math.round(projectedCpa * 100) / 100 : null,
            profitable,
        };
    }
    return null;
}

// ── Findings helper ────────────────────────────────────────────────────

export function makeFinding(id, verdict, severity, message, extras = {}) {
    return {
        id,
        verdict,
        severity,
        message,
        ...extras,
    };
}
