#!/usr/bin/env node

/**
 * Quality Score — Point-in-time Analysis
 *
 * Reads keywords-qs-period.csv + campaigns-settings.csv + bidding-strategies.csv.
 * Outputs qs-tiers.csv (one row per keyword with tier/class/component scoring)
 * and qs-flags.csv (one row per flag — high-spend-low-QS, per-component Below
 * Avg, lost-IS-rank, CPC premium, branded low-QS escalation).
 *
 * Classification runs against config.qualityScoreAudit.competitorCampaigns and
 * config.searchTermAnalysis.brandedCampaigns. INFORMATIONAL class is a Claude
 * semantic overlay applied in the SKILL.md phases — not assigned here.
 *
 * Usage:
 *   node analyze-quality-score.js \
 *     --period-csv=context/google-ads/data/keywords-qs-period.csv \
 *     --campaigns-csv=context/google-ads/data/campaigns-settings.csv \
 *     --portfolios-csv=context/google-ads/data/bidding-strategies.csv \
 *     --tiers-output=context/google-ads/data/qs-tiers.csv \
 *     --flags-output=context/google-ads/data/qs-flags.csv
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { parse } from 'csv-parse/sync';
import { formatCurrencyPrecise, resolveAccountCurrency } from './lib.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
let _projectRoot = __dirname;
while (_projectRoot !== '/' && !existsSync(resolve(_projectRoot, 'config'))) {
    _projectRoot = resolve(_projectRoot, '..');
}

const args = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const eqIndex = arg.indexOf('=');
        const key = arg.slice(0, eqIndex).replace(/^--/, '');
        const value = arg.slice(eqIndex + 1);
        if (key && value) acc[key] = value;
    }
    return acc;
}, {});

const periodCsvPath = resolve(_projectRoot, args['period-csv'] || 'context/google-ads/data/keywords-qs-period.csv');
const campaignsCsvPath = resolve(_projectRoot, args['campaigns-csv'] || 'context/google-ads/data/campaigns-settings.csv');
const portfoliosCsvPath = args['portfolios-csv']
    ? resolve(_projectRoot, args['portfolios-csv'])
    : resolve(_projectRoot, 'context/google-ads/data/bidding-strategies.csv');
const campaignsIsCsvPath = args['campaigns-is-csv']
    ? resolve(_projectRoot, args['campaigns-is-csv'])
    : resolve(_projectRoot, 'context/google-ads/data/campaigns-is.csv');
const tiersOutputPath = resolve(_projectRoot, args['tiers-output'] || 'context/google-ads/data/qs-tiers.csv');
const flagsOutputPath = resolve(_projectRoot, args['flags-output'] || 'context/google-ads/data/qs-flags.csv');

// ── Load config ─────────────────────────────────────────────────────
let qsConfig = {};
let searchConfig = {};
let accountCurrency = 'USD';
try {
    const configPath = resolve(_projectRoot, 'config/ads-context.config.json');
    if (existsSync(configPath)) {
        const fullConfig = JSON.parse(readFileSync(configPath, 'utf8'));
        qsConfig = fullConfig.qualityScoreAudit || {};
        searchConfig = fullConfig.searchTermAnalysis || {};
        accountCurrency = resolveAccountCurrency(fullConfig);
    }
} catch (e) { /* defaults */ }

const T = qsConfig.thresholds || {};
const CFG = {
    impressionWeightedQsFail: T.impressionWeightedQsFail ?? 5.0,
    impressionWeightedQsWarn: T.impressionWeightedQsWarn ?? 6.9,
    lowQsKeywordPct: T.lowQsKeywordPct ?? 10,
    highSpendPercentile: T.highSpendPercentile ?? 80,
    nullQsWarnPct: T.nullQsWarnPct ?? 30,
    dominantComponentPct: T.dominantComponentPct ?? 50,
    lostIsRankThresholdPct: T.lostIsRankThresholdPct ?? 15,
    lostIsRankQsCeiling: T.lostIsRankQsCeiling ?? 6,
    cpcPremiumPct: T.cpcPremiumPct ?? 30,
    minImpressionsForStableQs: T.minImpressionsForStableQs ?? 1000,
    brandLowQsCeiling: T.brandLowQsCeiling ?? 8,
};

const brandedCampaignNames = new Set(
    (searchConfig.brandedCampaigns || []).map(n => normalizeText(n))
);
const competitorCampaignNames = new Set(
    (qsConfig.competitorCampaigns || []).map(n => normalizeText(n))
);

// ── Helpers ─────────────────────────────────────────────────────────
function loadCsv(path) {
    if (!path || !existsSync(path)) return [];
    const raw = readFileSync(path, 'utf8');
    const rows = parse(raw, { columns: true, skip_empty_lines: true, relax_column_count: true });
    return rows.map(row => {
        const norm = {};
        for (const [k, v] of Object.entries(row)) {
            norm[k.replace(/\./g, '_')] = v;
        }
        return norm;
    });
}

function normalizeText(text) {
    return String(text || '').toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
}

function num(val) {
    const n = parseFloat(val);
    return isNaN(n) ? 0 : n;
}

function numOrNull(val) {
    if (val === '' || val === null || val === undefined) return null;
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

function biddingMode(strategyType) {
    const smart = ['TARGET_CPA', 'TARGET_ROAS', 'MAXIMIZE_CONVERSIONS', 'MAXIMIZE_CONVERSION_VALUE'];
    if (smart.includes(strategyType)) return 'SMART';
    return 'MANUAL';
}

// QS component statuses can arrive as enum strings (ABOVE_AVERAGE / AVERAGE /
// BELOW_AVERAGE / UNKNOWN / UNSPECIFIED) or as raw integers (1/2/3) in some
// GAQL outputs. Normalize to BELOW_AVG / AVG / ABOVE_AVG / NULL.
function normalizeComponent(raw) {
    if (raw === '' || raw === null || raw === undefined) return 'NULL';
    const s = String(raw).toUpperCase().trim();
    if (s === 'BELOW_AVERAGE' || s === '1') return 'BELOW_AVG';
    if (s === 'AVERAGE' || s === '2') return 'AVG';
    if (s === 'ABOVE_AVERAGE' || s === '3') return 'ABOVE_AVG';
    return 'NULL'; // UNKNOWN, UNSPECIFIED, or unrecognized
}

function classifyCampaign(campaignName) {
    const n = normalizeText(campaignName);
    if (!n) return 'GENERIC';
    if (competitorCampaignNames.has(n)) return 'COMPETITOR';
    if (brandedCampaignNames.has(n)) return 'BRANDED';
    return 'GENERIC';
}

// ── Load data ───────────────────────────────────────────────────────
console.log('Loading data...');
const periodRows = loadCsv(periodCsvPath).filter(r =>
    !r.campaign_experiment_type || r.campaign_experiment_type === 'BASE' || r.campaign_experiment_type === ''
);
const campaignRows = loadCsv(campaignsCsvPath);
const portfolioRows = loadCsv(portfoliosCsvPath);
const campaignsIsRows = loadCsv(campaignsIsCsvPath);

console.log(`Period: ${periodRows.length} keyword rows`);
console.log(`Campaigns: ${campaignRows.length}`);
console.log(`Portfolios: ${portfolioRows.length}`);
console.log(`Campaign IS rows: ${campaignsIsRows.length}`);

// ── Campaign-level Impression Share (authoritative D15 source) ──────
// Google Ads API returns IS metrics as fractions (0..1) on keyword_view but
// as fractions on `campaign` too. Multiply by 100 for percent.
const campaignIs = new Map();
for (const r of campaignsIsRows) {
    const cid = r.campaign_id;
    if (!cid) continue;
    const lostRank = numOrNull(r.metrics_search_rank_lost_impression_share);
    const lostBudget = numOrNull(r.metrics_search_budget_lost_impression_share);
    const is = numOrNull(r.metrics_search_impression_share);
    const topIs = numOrNull(r.metrics_search_top_impression_share);
    const absTopIs = numOrNull(r.metrics_search_absolute_top_impression_share);
    campaignIs.set(cid, {
        lostIsRankPct: lostRank !== null ? lostRank * 100 : null,
        lostIsBudgetPct: lostBudget !== null ? lostBudget * 100 : null,
        searchIsPct: is !== null ? is * 100 : null,
        topIsPct: topIs !== null ? topIs * 100 : null,
        absTopIsPct: absTopIs !== null ? absTopIs * 100 : null,
    });
}

if (periodRows.length === 0) {
    console.error('Error: no keyword rows in period CSV. Run pull-all.js first.');
    process.exit(1);
}

// ── Resolve campaign targets / portfolios / bidding mode ────────────
const portfolioTargets = new Map();
for (const p of portfolioRows) {
    const rn = p.bidding_strategy_resource_name;
    if (!rn) continue;
    portfolioTargets.set(rn, {
        name: p.bidding_strategy_name || '',
        type: p.bidding_strategy_type || '',
    });
}

const campaignMeta = new Map();
for (const c of campaignRows) {
    const cid = c.campaign_id;
    if (!cid) continue;
    const stratType = c.campaign_bidding_strategy_type || '';
    const mode = biddingMode(stratType);

    let targetSource = 'none';
    let portfolioName = '';
    let portfolioType = '';

    const hasInline = numOrNull(c.campaign_target_cpa_target_cpa) !== null ||
                      numOrNull(c.campaign_maximize_conversions_target_cpa) !== null ||
                      numOrNull(c.campaign_target_roas_target_roas) !== null ||
                      numOrNull(c.campaign_maximize_conversion_value_target_roas) !== null;
    if (hasInline) {
        targetSource = 'campaign_inline';
    } else {
        const portfolioRef = c.campaign_bidding_strategy || '';
        if (portfolioRef && portfolioTargets.has(portfolioRef)) {
            const pt = portfolioTargets.get(portfolioRef);
            targetSource = 'portfolio';
            portfolioName = pt.name;
            portfolioType = pt.type;
        }
    }

    campaignMeta.set(cid, {
        name: c.campaign_name || '',
        strategyType: stratType,
        biddingMode: mode,
        targetSource,
        portfolioName,
        portfolioType,
    });
}

// ── Compute ad-group-level avg CPC (for D16 CPC premium) ────────────
const agCpcTotals = new Map(); // ad_group_id → { totalCost, totalClicks }
for (const row of periodRows) {
    const agId = row.ad_group_id;
    if (!agId) continue;
    if (!agCpcTotals.has(agId)) {
        agCpcTotals.set(agId, { totalCost: 0, totalClicks: 0 });
    }
    const t = agCpcTotals.get(agId);
    t.totalCost += num(row.metrics_cost);
    t.totalClicks += num(row.metrics_clicks);
}
const agAvgCpc = new Map();
for (const [agId, t] of agCpcTotals) {
    agAvgCpc.set(agId, t.totalClicks > 0 ? t.totalCost / t.totalClicks : null);
}

// ── High-spend percentile cutoff (top N% by spend, spending rows only) ──
// Computing the percentile over all rows including zero-cost ones collapses
// the cutoff to 0 when non-spenders dominate (common on broad-match-heavy
// accounts), flagging every spending keyword. Restrict to rows with cost > 0.
const spends = periodRows
    .map(r => num(r.metrics_cost))
    .filter(c => c > 0)
    .sort((a, b) => a - b);
let highSpendCutoff = 0;
if (spends.length > 0) {
    const idx = Math.min(spends.length - 1, Math.floor(spends.length * (CFG.highSpendPercentile / 100)));
    highSpendCutoff = spends[idx];
}

// ── Classify each keyword ───────────────────────────────────────────
console.log('Classifying keywords...');

const tiers = [];
for (const row of periodRows) {
    const cid = row.campaign_id;
    const meta = campaignMeta.get(cid) || {};

    const keywordText = row.ad_group_criterion_keyword_text || '';
    const matchType = row.ad_group_criterion_keyword_match_type || '';
    const campaignName = row.campaign_name || meta.name || '';
    const adGroupName = row.ad_group_name || '';
    const adGroupId = row.ad_group_id || '';
    const criterionId = row.ad_group_criterion_criterion_id || '';

    const impressions = num(row.metrics_impressions);
    const clicks = num(row.metrics_clicks);
    const cost = num(row.metrics_cost);
    const avgCpc = numOrNull(row.metrics_average_cpc);
    const conversions = num(row.metrics_conversions);
    const convValue = num(row.metrics_conversions_value);

    const qsRaw = numOrNull(row.ad_group_criterion_quality_info_quality_score);
    const qs = qsRaw !== null && qsRaw >= 1 && qsRaw <= 10 ? qsRaw : null;
    const ar = normalizeComponent(row.ad_group_criterion_quality_info_creative_quality_score);
    const ectr = normalizeComponent(row.ad_group_criterion_quality_info_search_predicted_ctr);
    const lp = normalizeComponent(row.ad_group_criterion_quality_info_post_click_quality_score);

    const lostIsRank = numOrNull(row.metrics_search_rank_lost_impression_share);
    const topIs = numOrNull(row.metrics_search_top_impression_share);
    const searchIs = numOrNull(row.metrics_search_impression_share);

    const klass = classifyCampaign(campaignName);

    // Tier classification (point-in-time QS health)
    // QS_NULL: no QS reported (too little data)
    // UNSTABLE_QS: <minImpressionsForStableQs impressions → QS unreliable
    // QS_CRITICAL: 1-4
    // QS_WATCH:    5-6
    // QS_OK:       7-10
    let tier;
    if (qs === null) {
        tier = 'QS_NULL';
    } else if (impressions < CFG.minImpressionsForStableQs) {
        tier = 'UNSTABLE_QS';
    } else if (qs <= 4) {
        tier = 'QS_CRITICAL';
    } else if (qs <= 6) {
        tier = 'QS_WATCH';
    } else {
        tier = 'QS_OK';
    }

    // Dominant limiting component on this keyword — the component(s) rated
    // Below Avg. Used by D10 (account-level dominant) and D07-D09 routing.
    const belowComponents = [];
    if (ar === 'BELOW_AVG') belowComponents.push('AR');
    if (ectr === 'BELOW_AVG') belowComponents.push('ECTR');
    if (lp === 'BELOW_AVG') belowComponents.push('LP');
    const dominantLimiting = belowComponents.length === 1 ? belowComponents[0] :
                             belowComponents.length > 1 ? 'MULTIPLE' : 'NONE';

    const isHighSpend = cost >= highSpendCutoff && cost > 0;
    const priorityScore = qs !== null ? (10 - qs) * impressions : 0;

    tiers.push({
        keyword_text: keywordText,
        match_type: matchType,
        campaign_name: campaignName,
        ad_group_name: adGroupName,
        campaign_id: cid || '',
        ad_group_id: adGroupId,
        criterion_id: criterionId,
        final_urls: row.ad_group_criterion_final_urls || '',
        impressions,
        clicks,
        cost: cost.toFixed(2),
        avg_cpc: avgCpc !== null ? avgCpc.toFixed(2) : '',
        conversions: conversions.toFixed(2),
        conversions_value: convValue.toFixed(2),
        quality_score: qs !== null ? qs : '',
        ad_relevance: ar,
        expected_ctr: ectr,
        landing_page_exp: lp,
        tier,
        class: klass,
        dominant_limiting_component: dominantLimiting,
        below_avg_components: belowComponents.join('|'),
        is_high_spend: isHighSpend ? 'true' : 'false',
        priority_score: priorityScore.toFixed(0),
        search_is: searchIs !== null ? (searchIs * 100).toFixed(2) : '',
        lost_is_rank: lostIsRank !== null ? (lostIsRank * 100).toFixed(2) : '',
        search_top_is: topIs !== null ? (topIs * 100).toFixed(2) : '',
        bidding_strategy_type: meta.strategyType || '',
        bidding_mode: meta.biddingMode || '',
        target_source: meta.targetSource || 'none',
        portfolio_name: meta.portfolioName || '',
    });
}

// ── Generate flags ──────────────────────────────────────────────────
console.log('Generating flags...');

const flags = [];

function flagBase(t) {
    return {
        keyword_text: t.keyword_text,
        match_type: t.match_type,
        campaign_name: t.campaign_name,
        ad_group_name: t.ad_group_name,
        campaign_id: t.campaign_id,
        ad_group_id: t.ad_group_id,
        criterion_id: t.criterion_id,
        impressions: t.impressions,
        clicks: t.clicks,
        cost: t.cost,
        quality_score: t.quality_score,
        ad_relevance: t.ad_relevance,
        expected_ctr: t.expected_ctr,
        landing_page_exp: t.landing_page_exp,
        class: t.class,
        bidding_mode: t.bidding_mode,
        bidding_strategy_type: t.bidding_strategy_type,
        target_source: t.target_source,
        portfolio_name: t.portfolio_name,
    };
}

for (const t of tiers) {
    const qs = t.quality_score === '' ? null : Number(t.quality_score);

    // QS-D03 HIGH_SPEND_LOW_QS: top 20% by spend AND QS < 5
    if (t.is_high_spend === 'true' && qs !== null && qs < 5) {
        flags.push({
            ...flagBase(t),
            flag_type: 'HIGH_SPEND_LOW_QS',
            flag_severity: 'Critical',
            flag_detail: `QS ${qs} on high-spend keyword (${formatCurrencyPrecise(t.cost, accountCurrency)}) — CPC premium is costing materially more per click than at QS 7+.`,
        });
    }

    // QS-D07 AR_BELOW_AVG: Ad Relevance Below Avg (suppressed for COMPETITOR class)
    if (t.ad_relevance === 'BELOW_AVG') {
        if (t.class === 'COMPETITOR') {
            flags.push({
                ...flagBase(t),
                flag_type: 'AR_BELOW_AVG_COMPETITOR',
                flag_severity: 'Info',
                flag_detail: `AR Below Avg on competitor-conquesting keyword — structurally expected. Do not recommend AR fixes.`,
            });
        } else {
            flags.push({
                ...flagBase(t),
                flag_type: 'AR_BELOW_AVG',
                flag_severity: t.class === 'BRANDED' ? 'High' : 'Medium',
                flag_detail: `Ad Relevance Below Avg. Route to /rsa-maker (copy); if Headline Test fails, surface pending keyword-restructurer brief (skill not yet built).`,
            });
        }
    }

    // QS-D08 ECTR_BELOW_AVG
    if (t.expected_ctr === 'BELOW_AVG') {
        flags.push({
            ...flagBase(t),
            flag_type: 'ECTR_BELOW_AVG',
            flag_severity: 'Medium',
            flag_detail: `Expected CTR Below Avg. Route to /offer-maker + /rsa-maker once AR is Average+.`,
        });
    }

    // QS-D09 LP_BELOW_AVG
    if (t.landing_page_exp === 'BELOW_AVG') {
        flags.push({
            ...flagBase(t),
            flag_type: 'LP_BELOW_AVG',
            flag_severity: t.class === 'BRANDED' ? 'High' : 'Medium',
            flag_detail: `Landing Page Experience Below Avg. Route to /lp-auditor → /lp-optimizer.`,
        });
    }

    // Branded low-QS escalation: QS < brandLowQsCeiling on branded campaign
    if (t.class === 'BRANDED' && qs !== null && qs < CFG.brandLowQsCeiling) {
        flags.push({
            ...flagBase(t),
            flag_type: 'BRAND_LOW_QS',
            flag_severity: 'Critical',
            flag_detail: `Branded keyword with QS ${qs} < ${CFG.brandLowQsCeiling}. Usually tracking, wrong URL, or LP message-match — escalate to /lp-auditor first.`,
        });
    }

    // QS-D16 CPC_PREMIUM_LOW_QS: avg_cpc >30% above AG avg AND QS<5
    if (qs !== null && qs < 5) {
        const agCpc = agAvgCpc.get(t.ad_group_id);
        const kwCpc = t.avg_cpc === '' ? null : Number(t.avg_cpc);
        if (agCpc !== null && agCpc > 0 && kwCpc !== null && kwCpc > 0) {
            const premiumPct = ((kwCpc - agCpc) / agCpc) * 100;
            if (premiumPct >= CFG.cpcPremiumPct) {
                flags.push({
                    ...flagBase(t),
                    flag_type: 'CPC_PREMIUM_LOW_QS',
                    flag_severity: 'Medium',
                    flag_detail: `Avg CPC ${formatCurrencyPrecise(kwCpc, accountCurrency)} is ${premiumPct.toFixed(0)}% above ad-group avg ${formatCurrencyPrecise(agCpc, accountCurrency)} on QS ${qs} keyword.`,
                });
            }
        }
    }
}

// ── Campaign-level flags: LOST_IS_RANK_QS (D15) ─────────────────────
// Campaign has >lostIsRankThresholdPct% Lost IS (rank) AND weighted QS
// <lostIsRankQsCeiling. Lost IS (rank) is read from campaigns-is.csv
// (authoritative campaign-level metric from Google Ads API). Weighted QS
// is reconstructed from keyword rows (there is no campaign-level QS field).
const campaignAgg = new Map();
for (const t of tiers) {
    const cid = t.campaign_id;
    if (!campaignAgg.has(cid)) {
        campaignAgg.set(cid, {
            campaign_name: t.campaign_name,
            totalImpressions: 0,
            qsWeightedSum: 0,
            bidding_mode: t.bidding_mode,
            strategyType: t.bidding_strategy_type,
        });
    }
    const c = campaignAgg.get(cid);
    const imp = t.impressions;
    c.totalImpressions += imp;
    if (t.quality_score !== '' && imp > 0) {
        c.qsWeightedSum += Number(t.quality_score) * imp;
    }
}

for (const [cid, c] of campaignAgg) {
    if (c.totalImpressions === 0) continue;
    const weightedQs = c.qsWeightedSum > 0 ? c.qsWeightedSum / c.totalImpressions : null;

    const is = campaignIs.get(cid);
    if (!is || is.lostIsRankPct === null) continue;

    const lostIsRankPct = is.lostIsRankPct;
    const lostIsBudgetPct = is.lostIsBudgetPct;

    const overThreshold = lostIsRankPct >= CFG.lostIsRankThresholdPct;
    const qsLow = weightedQs !== null && weightedQs < CFG.lostIsRankQsCeiling;
    const budgetNote = lostIsBudgetPct !== null && lostIsBudgetPct >= 5
        ? ` Note: also losing ${lostIsBudgetPct.toFixed(1)}% to budget — fix budget alongside QS.`
        : '';

    const flagCampaignBase = {
        keyword_text: '',
        match_type: '',
        campaign_name: c.campaign_name,
        ad_group_name: '',
        campaign_id: cid,
        ad_group_id: '',
        criterion_id: '',
        impressions: c.totalImpressions,
        clicks: '',
        cost: '',
        quality_score: weightedQs !== null ? weightedQs.toFixed(2) : '',
        ad_relevance: '',
        expected_ctr: '',
        landing_page_exp: '',
        class: '',
        bidding_mode: c.bidding_mode,
        bidding_strategy_type: c.strategyType,
        target_source: '',
        portfolio_name: '',
    };

    if (overThreshold && qsLow) {
        flags.push({
            ...flagCampaignBase,
            flag_type: 'LOST_IS_RANK_QS',
            flag_severity: 'High',
            flag_detail: `Campaign has ${lostIsRankPct.toFixed(1)}% Lost IS (rank) AND weighted QS ${weightedQs.toFixed(2)} < ${CFG.lostIsRankQsCeiling}. QS is dragging rank — fixing components likely recovers traffic.${budgetNote}`,
        });
    } else if (overThreshold && !qsLow) {
        // Rank loss high but QS healthy — not a QS-skill fix. Route elsewhere
        // (competitive, offer, budget, targeting). INFO severity.
        flags.push({
            ...flagCampaignBase,
            flag_type: 'LOST_IS_RANK_NON_QS',
            flag_severity: 'Info',
            flag_detail: `Campaign has ${lostIsRankPct.toFixed(1)}% Lost IS (rank) but weighted QS ${weightedQs !== null ? weightedQs.toFixed(2) : 'n/a'} is healthy — rank loss is NOT a QS issue. Investigate bid, ad strength, targeting, or competitive pressure. Route to /competitive-analyst or /offer-maker.${budgetNote}`,
        });
    }
}

// ── Write outputs ───────────────────────────────────────────────────
const tiersHeaders = [
    'keyword_text', 'match_type', 'campaign_name', 'ad_group_name',
    'campaign_id', 'ad_group_id', 'criterion_id', 'final_urls',
    'impressions', 'clicks', 'cost', 'avg_cpc', 'conversions', 'conversions_value',
    'quality_score', 'ad_relevance', 'expected_ctr', 'landing_page_exp',
    'tier', 'class', 'dominant_limiting_component', 'below_avg_components',
    'is_high_spend', 'priority_score',
    'search_is', 'lost_is_rank', 'search_top_is',
    'bidding_strategy_type', 'bidding_mode', 'target_source', 'portfolio_name',
];
writeCsv(tiersOutputPath, tiersHeaders, tiers);
console.log(`File: ${tiersOutputPath}`);
console.log(`Rows: ${tiers.length}`);

const flagsHeaders = [
    'keyword_text', 'match_type', 'campaign_name', 'ad_group_name',
    'campaign_id', 'ad_group_id', 'criterion_id',
    'flag_type', 'flag_severity', 'flag_detail',
    'impressions', 'clicks', 'cost',
    'quality_score', 'ad_relevance', 'expected_ctr', 'landing_page_exp',
    'class', 'bidding_mode', 'bidding_strategy_type', 'target_source', 'portfolio_name',
];
writeCsv(flagsOutputPath, flagsHeaders, flags);
console.log(`File: ${flagsOutputPath}`);
console.log(`Rows: ${flags.length}`);

// Summary stats
const tierCounts = {};
const classCounts = {};
for (const t of tiers) {
    tierCounts[t.tier] = (tierCounts[t.tier] || 0) + 1;
    classCounts[t.class] = (classCounts[t.class] || 0) + 1;
}
const flagCounts = {};
for (const f of flags) {
    flagCounts[f.flag_type] = (flagCounts[f.flag_type] || 0) + 1;
}

console.log(`\nTier distribution: ${JSON.stringify(tierCounts)}`);
console.log(`Class distribution: ${JSON.stringify(classCounts)}`);
console.log(`Flag distribution: ${JSON.stringify(flagCounts)}`);
console.log('Done.');
