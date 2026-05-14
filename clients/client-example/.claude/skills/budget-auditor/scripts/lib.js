/**
 * Shared utilities for the budget-auditor analysis engines.
 * All helpers are pure (no I/O unless explicit) and account-agnostic.
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

// ── Money accessors ────────────────────────────────────────────────────
//
// query.js strips every `_micros` suffix and divides by 1,000,000, so
// CSV columns are already in dollars (string form like "18673.37").
// Helpers below centralise the lookup so analyzers can't accidentally
// reach for the `_micros` form (which doesn't exist post-query.js).

export function getCost(row)        { return num(row?.['metrics.cost']); }
export function getConvValue(row)   { return num(row?.['metrics.conversions_value']); }
export function getDailyBudget(row) { return num(row?.['campaign_budget.amount']); }

export function getTargetCpa(row) {
    return num(row?.['campaign.target_cpa.target_cpa'])
        || num(row?.['campaign.maximize_conversions.target_cpa']);
}

// ── Currency formatting (uses top-level accountCurrency from config) ──

export function formatCurrency(amount, currency = 'USD') {
    const n = num(amount);
    return new Intl.NumberFormat('en-US', {
        style: 'currency', currency, maximumFractionDigits: 0,
    }).format(n);
}

export function formatCurrencyPrecise(amount, currency = 'USD') {
    const n = num(amount);
    return new Intl.NumberFormat('en-US', {
        style: 'currency', currency, maximumFractionDigits: 2,
    }).format(n);
}

// ── Channel detection ──────────────────────────────────────────────────

export function getChannelType(row) {
    return (row['campaign.advertising_channel_type'] || '').toUpperCase();
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

export function isSmartBidding(strategyType) {
    return SMART_BIDDING_TYPES.has((strategyType || '').toUpperCase());
}

// Channel-aware minimum monthly conv volume for smart bidding.
// Mirrors /sops/Conversion Volume Thresholds Reference.md.
const VOLUME_THRESHOLDS = {
    SEARCH:          { TARGET_CPA: 30, TARGET_ROAS: 50, MAXIMIZE_CONVERSIONS: 30, MAXIMIZE_CONVERSION_VALUE: 50 },
    SHOPPING:        { TARGET_ROAS: 50, MAXIMIZE_CONVERSION_VALUE: 50 },
    PERFORMANCE_MAX: { TARGET_CPA: 30, TARGET_ROAS: 50, MAXIMIZE_CONVERSIONS: 30, MAXIMIZE_CONVERSION_VALUE: 50 },
    DISPLAY:         { TARGET_CPA: 30, MAXIMIZE_CONVERSIONS: 30 },
    VIDEO:           { TARGET_CPA: 30, MAXIMIZE_CONVERSIONS: 30 },
    DEMAND_GEN:      { TARGET_CPA: 30, TARGET_ROAS: 50, MAXIMIZE_CONVERSIONS: 30 },
};

export function getMinConvVolumeForSmartBidding(channelType, strategyType, fallback = 30) {
    const ch = (channelType || '').toUpperCase();
    const st = (strategyType || '').toUpperCase();
    return VOLUME_THRESHOLDS[ch]?.[st] || fallback;
}

// ── Profitability ──────────────────────────────────────────────────────

/**
 * Decide if a campaign is profitable, unprofitable, or unclassified.
 * KPI-aware. Returns { state: 'profitable' | 'unprofitable' | 'unclassified', margin?, reason? }.
 *
 * Inputs:
 *   campaignAggRow — perf CSV row (cost, conversions, conv value)
 *   primaryKPI     — 'cpa' | 'roas' | null
 *   breakEven      — number | null (CPA $ if cpa, ROAS ratio if roas)
 *   minConv        — minimum conversions to make a profitability call (default 5)
 */
export function classifyProfitability(campaignAggRow, primaryKPI, breakEven, minConv = 5) {
    const cost = getCost(campaignAggRow);
    const conv = num(campaignAggRow['metrics.conversions']);
    const value = getConvValue(campaignAggRow);

    if (!primaryKPI || breakEven == null || !Number.isFinite(breakEven)) {
        return { state: 'unclassified', reason: 'no_break_even' };
    }
    if (conv < minConv) {
        return { state: 'unclassified', reason: 'insufficient_conversions' };
    }
    if (primaryKPI === 'cpa') {
        if (cost <= 0 || conv <= 0) return { state: 'unclassified', reason: 'no_spend_or_conv' };
        const actualCpa = cost / conv;
        const margin = (breakEven - actualCpa) / breakEven;
        return {
            state: actualCpa <= breakEven ? 'profitable' : 'unprofitable',
            actualCpa,
            margin,
        };
    }
    if (primaryKPI === 'roas') {
        if (cost <= 0) return { state: 'unclassified', reason: 'no_spend' };
        const actualRoas = value / cost;
        const margin = (actualRoas - breakEven) / breakEven;
        return {
            state: actualRoas >= breakEven ? 'profitable' : 'unprofitable',
            actualRoas,
            margin,
        };
    }
    return { state: 'unclassified', reason: 'unknown_kpi' };
}

// ── Seasonality ────────────────────────────────────────────────────────

const MONTH_NAMES = [
    'january','february','march','april','may','june',
    'july','august','september','october','november','december'
];

/**
 * Returns a multiplier (0.8..1.5 typical) describing whether the current
 * month is a designated highlight month in the seasonalityProfile.
 * v1 logic: highlight months get 1.0 (kept neutral), non-highlight in a
 * highlight-month account also stays 1.0. The flag signals when the user
 * SHOULD be ramping — interpretation belongs to the analyzer.
 *
 * Returns { isHighlight: bool, mode, currentMonth } so the analyzer can
 * adjust messaging without committing to a hardcoded multiplier.
 */
export function getSeasonalityState(currentDate, seasonalityProfile) {
    const profile = seasonalityProfile || { mode: 'flat', months: [] };
    const monthIdx = currentDate.getMonth();
    const currentMonth = MONTH_NAMES[monthIdx];
    const months = (profile.months || []).map(m => String(m).toLowerCase());
    const isHighlight = profile.mode === 'highlight_months' && months.includes(currentMonth);

    // Approaching = next month is in the highlight list (gives the auditor
    // a chance to flag "ramp up before season starts").
    const nextMonth = MONTH_NAMES[(monthIdx + 1) % 12];
    const approachingHighlight = profile.mode === 'highlight_months' && months.includes(nextMonth);

    return {
        mode: profile.mode || 'flat',
        currentMonth,
        nextMonth,
        isHighlight,
        approachingHighlight,
    };
}

// ── Account changelog parsing ──────────────────────────────────────────

/**
 * Parse `context/account-changelog.md` and return per-campaign
 * budget-related last-change timestamps.
 * Returns Map(campaignNameLower → { lastBudgetChange: ISO, lastSharedBudgetChange: ISO }).
 */
export function readAccountChangelog(path, daysBack = 30) {
    if (!existsSync(path)) return { entries: new Map(), text: '', mtimeMs: 0, fresh: false };
    const text = readFileSync(path, 'utf8');
    const stat = (existsSync(path)) ? readFileSync(path, 'utf8') : '';
    const map = new Map();
    const cutoff = new Date(Date.now() - daysBack * 24 * 60 * 60 * 1000);

    for (const line of text.split('\n')) {
        if (!line.trim() || line.startsWith('#')) continue;
        const dateMatch = line.match(/(\d{4}-\d{2}-\d{2})/);
        if (!dateMatch) continue;
        const date = dateMatch[1];
        if (new Date(date) < cutoff) continue;
        const isBudget = /budget|daily.amount|spending.limit/i.test(line);
        if (!isBudget) continue;
        const isShared = /shared/i.test(line);
        const campMatch = line.match(/campaign[:\s"]+([^"|\n]+?)(?:["|]|$)/i)
            || line.match(/"([^"]+)"/);
        if (!campMatch) continue;
        const campName = campMatch[1].trim().toLowerCase();
        const cur = map.get(campName) || { lastBudgetChange: null, lastSharedBudgetChange: null };
        if (!cur.lastBudgetChange || cur.lastBudgetChange < date) cur.lastBudgetChange = date;
        if (isShared && (!cur.lastSharedBudgetChange || cur.lastSharedBudgetChange < date)) {
            cur.lastSharedBudgetChange = date;
        }
        map.set(campName, cur);
    }
    return { entries: map, text };
}

// ── Pacing math ───────────────────────────────────────────────────────

/**
 * From a list of {date, cost} entries (a single campaign or aggregated
 * account total), compute MTD spend and project the full-month total
 * based on average daily run-rate so far.
 *
 * Returns { mtdSpend, daysElapsed, daysInMonth, avgDaily, projectedMonth }.
 * `today` is an optional Date override for testing.
 */
export function computeMtdProjection(dailySeries, today = new Date()) {
    const yyyy = today.getFullYear();
    const mm = today.getMonth();
    const daysElapsed = today.getDate();
    const daysInMonth = new Date(yyyy, mm + 1, 0).getDate();

    const monthPrefix = `${yyyy}-${String(mm + 1).padStart(2, '0')}`;
    const monthRows = dailySeries.filter(r => (r.date || '').startsWith(monthPrefix));
    const mtdSpend = monthRows.reduce((s, r) => s + num(r.cost), 0);

    // Use elapsed minus today (today partial) for run-rate when we have a
    // reasonable number of full days.
    const fullDays = Math.max(daysElapsed - 1, 1);
    const avgDaily = fullDays > 0 ? mtdSpend / Math.max(monthRows.length, 1) : 0;
    const projectedMonth = avgDaily * daysInMonth;

    return {
        mtdSpend,
        daysElapsed,
        daysInMonth,
        avgDaily,
        projectedMonth,
        daysObserved: monthRows.length,
    };
}

/**
 * Group daily rows by campaign id (string). Returns Map<id, [{date, cost, ...}]>.
 */
export function groupDailyByCampaign(dailyRows) {
    const map = new Map();
    for (const r of dailyRows) {
        const id = r['campaign.id'];
        if (!id) continue;
        if (!map.has(id)) map.set(id, []);
        map.get(id).push({
            date: r['segments.date'],
            cost: getCost(r),
            clicks: num(r['metrics.clicks']),
            conversions: num(r['metrics.conversions']),
            row: r,
        });
    }
    for (const arr of map.values()) {
        arr.sort((a, b) => (a.date || '').localeCompare(b.date || ''));
    }
    return map;
}

// ── Budget exhaustion detection ───────────────────────────────────────

/**
 * Heuristic: BUD-D06 — daily-budget exhaustion before EOD.
 * Without hourly data we estimate via:
 *   - days where actual_spend / daily_budget > 0.95 → "spent the budget"
 *   - paired with high search_budget_lost_impression_share on the aggregate row
 * Return ratio of "exhausted" days vs observed days.
 */
export function detectExhaustionPattern(dailyEntries, dailyBudget) {
    if (!dailyBudget || dailyEntries.length === 0) return null;
    let exhaustedDays = 0;
    for (const e of dailyEntries) {
        if (e.cost >= dailyBudget * 0.95) exhaustedDays += 1;
    }
    return {
        exhaustedDays,
        observedDays: dailyEntries.length,
        ratio: exhaustedDays / dailyEntries.length,
    };
}

// ── Opportunity computation ───────────────────────────────────────────

/**
 * BUD opportunity-mode: estimate incremental conversions if budget is raised
 * enough to recover IS Lost (Budget). Mirrors bidding-auditor's
 * is_lost_budget heuristic — replaceable by Performance Planner in v1.1.
 *
 * Returns null if not enough signal; otherwise a structured opportunity.
 */
export function computeOpportunityValue(campaignRow, primaryKPI, breakEven) {
    const cost = getCost(campaignRow);
    const clicks = num(campaignRow['metrics.clicks']);
    const conv = num(campaignRow['metrics.conversions']);
    const value = getConvValue(campaignRow);
    const isLostBudget = num(campaignRow['metrics.search_budget_lost_impression_share']);
    if (!conv || !clicks || !cost) return null;

    const cvr = conv / clicks;
    const cpc = cost / clicks;
    if (cvr <= 0 || cpc <= 0 || isLostBudget <= 0.05) return null;

    // IS-lost is 0..1 already
    const recoveryFactor = isLostBudget / Math.max(1 - isLostBudget, 0.01);
    const incrementalClicks = clicks * recoveryFactor;
    const incrementalConv = incrementalClicks * cvr;
    const incrementalCost = incrementalClicks * cpc;
    const incrementalValue = incrementalConv * (conv > 0 ? value / conv : 0);

    let projected = null;
    let profitable = null;
    if (primaryKPI === 'cpa' && incrementalConv > 0) {
        projected = incrementalCost / incrementalConv;
        if (breakEven != null) profitable = projected <= breakEven;
    } else if (primaryKPI === 'roas' && incrementalCost > 0) {
        projected = incrementalValue / incrementalCost;
        if (breakEven != null) profitable = projected >= breakEven;
    }

    return {
        type: 'is_lost_budget_recovery',
        isLostBudget,
        incrementalClicks: Math.round(incrementalClicks),
        incrementalConv: Math.round(incrementalConv * 10) / 10,
        incrementalCost: Math.round(incrementalCost),
        incrementalValue: Math.round(incrementalValue),
        projected: projected != null ? Math.round(projected * 100) / 100 : null,
        profitable,
    };
}

// ── Findings helper ────────────────────────────────────────────────────

export function makeFinding(id, verdict, severity, message, extras = {}) {
    return {
        id,
        verdict,
        severity,
        message,
        blocking: extras.blocking || [],
        ...extras,
    };
}

// ── Experiment grouping ───────────────────────────────────────────────

/**
 * For Allocation math, group rows by base-campaign budget consumer.
 * If campaign.experiment is set, that campaign rolls up into its base.
 * Returns Map<groupKey, { base, members: [rows] }> where groupKey is the
 * base campaign id (or the campaign's own id if no experiment link).
 *
 * `campaign.base_campaign` is the resource_name of the base campaign
 * (equals the row's own resource_name when the row IS a base). For an
 * experiment-type row, base_campaign points back to the parent — but in
 * practice the safer grouping signal is the shared campaign_budget id.
 * v1 behavior: group experiment rows by their `campaign_budget.id`; if
 * no sibling base exists in the data, the row stands alone.
 */
export function groupExperimentsWithBases(rows) {
    const groups = new Map();
    for (const r of rows) {
        const isExperiment = (r['campaign.experiment_type'] || '').toUpperCase() === 'EXPERIMENT';
        // Heuristic: experiments share the budget id with the base; group by that.
        // Fall back to the campaign id if no budget id is present.
        const groupKey = isExperiment
            ? (r['campaign_budget.id'] || r['campaign.id'])
            : r['campaign.id'];
        if (!groups.has(groupKey)) groups.set(groupKey, { base: null, members: [] });
        const g = groups.get(groupKey);
        g.members.push(r);
        if (!isExperiment && !g.base) g.base = r;
    }
    return groups;
}

export function isExperimentRow(row) {
    return (row['campaign.experiment_type'] || '').toUpperCase() === 'EXPERIMENT';
}
