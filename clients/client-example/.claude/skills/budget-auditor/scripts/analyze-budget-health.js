#!/usr/bin/env node

/**
 * Budget Auditor — Modules 1, 2, 4, 5
 *
 * Limitation, Sufficiency, Allocation, Shared Budgets.
 * Reads CSVs from context/google-ads/data/ and writes:
 *   - context/analysis/budget/findings-health.json
 *   - context/analysis/budget/opportunities-health.json
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

import {
    readCsv, num, makeFinding, getChannelType,
    isSearch, isShopping, isPMax, isDisplay, isVideo,
    isSmartBidding, getMinConvVolumeForSmartBidding,
    classifyProfitability, computeOpportunityValue,
    isExperimentRow, groupExperimentsWithBases,
    getCost, getDailyBudget, getTargetCpa,
} from './lib.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
let projectRoot = __dirname;
while (projectRoot !== '/' && !existsSync(resolve(projectRoot, 'config'))) {
    projectRoot = resolve(projectRoot, '..');
}

const cliArgs = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const eq = arg.indexOf('=');
        acc[arg.slice(0, eq).replace('--', '')] = arg.slice(eq + 1);
    } else if (arg.startsWith('--')) {
        acc[arg.replace('--', '')] = true;
    }
    return acc;
}, {});

const period = parseInt(cliArgs['period'] || 30);

const config = JSON.parse(readFileSync(resolve(projectRoot, 'config/ads-context.config.json'), 'utf8'));
const ba = config.budgetAudit || {};
const accountCurrency = config.accountCurrency || 'USD';

// Try to derive primary KPI + break-even from sibling skills' configs.
const primaryKPI = config.biddingAudit?.primaryKPI
    || config.searchTermAnalysis?.biddingStrategy
    || null;
const breakEven = primaryKPI === 'cpa'
    ? (config.biddingAudit?.breakEvenCPA ?? config.competitiveAnalyst?.breakEvenCPA ?? null)
    : (config.biddingAudit?.breakEvenROAS ?? null);
const targetSourceFallback = (primaryKPI && breakEven != null) ? null : 'fallback';

const dataDir = resolve(projectRoot, 'context/google-ads/data');
const outDir = resolve(projectRoot, 'context/analysis/budget');
mkdirSync(outDir, { recursive: true });

const budgets = readCsv(resolve(dataDir, 'campaign-budgets.csv'));
const perf = readCsv(resolve(dataDir, 'campaigns-budget-perf.csv'));
const portfolios = readCsv(resolve(dataDir, 'bidding-strategies.csv'));

// Index budgets by id
const budgetsById = new Map();
for (const b of budgets) {
    const id = b['campaign_budget.id'];
    if (id) budgetsById.set(id, b);
}

// Aggregate perf rows per campaign (the perf CSV may have one row per
// campaign already; if segmented, sum metrics).
function aggregateCampaign(rows) {
    if (rows.length === 1) return rows[0];
    const out = { ...rows[0] };
    const sumKeys = ['metrics.impressions', 'metrics.clicks', 'metrics.cost',
        'metrics.conversions', 'metrics.conversions_value'];
    for (const k of sumKeys) out[k] = rows.reduce((s, r) => s + num(r[k]), 0);
    // Recompute weighted IS-style metrics as simple averages (best effort).
    const isKeys = ['metrics.search_impression_share',
        'metrics.search_budget_lost_impression_share',
        'metrics.search_rank_lost_impression_share'];
    for (const k of isKeys) {
        const valid = rows.map(r => num(r[k])).filter(v => v > 0);
        out[k] = valid.length ? valid.reduce((a, b) => a + b, 0) / valid.length : 0;
    }
    return out;
}

const perfByCampaign = new Map();
for (const r of perf) {
    const id = r['campaign.id'];
    if (!id) continue;
    if (!perfByCampaign.has(id)) perfByCampaign.set(id, []);
    perfByCampaign.get(id).push(r);
}
const campaigns = Array.from(perfByCampaign.entries()).map(([id, rows]) => ({
    id, agg: aggregateCampaign(rows),
}));

const totalSpend = campaigns.reduce((s, c) => s + getCost(c.agg), 0);
const findings = [];
const opportunities = [];

function pushFinding(f) { findings.push(f); }

// ─────────────────────────────────────────────────────────────────────
// MODULE 1 — Limitation
// ─────────────────────────────────────────────────────────────────────

const isLostBudgetThresholdPct = num(ba.isLostBudgetThreshold, 10);

// BUD-D01 — Limited status (budget-loss IS heuristic stand-in)
const limitedCampaigns = [];
for (const c of campaigns) {
    const isLostBudget = num(c.agg['metrics.search_budget_lost_impression_share']) * 100;
    if (isLostBudget >= isLostBudgetThresholdPct) {
        limitedCampaigns.push({
            campaign: c.agg['campaign.name'],
            campaignId: c.id,
            channel: getChannelType(c.agg),
            isLostBudgetPct: Math.round(isLostBudget * 10) / 10,
            cost: Math.round(getCost(c.agg)),
        });
    }
}
pushFinding(makeFinding(
    'BUD-D01',
    limitedCampaigns.length === 0 ? 'PASS' : 'WARN',
    limitedCampaigns.length > 0 ? 'medium' : 'info',
    limitedCampaigns.length === 0
        ? 'No campaigns flagged as limited by budget.'
        : `${limitedCampaigns.length} campaign(s) showing budget-limited signal (IS Lost (Budget) >= ${isLostBudgetThresholdPct}%).`,
    { campaigns: limitedCampaigns }
));

// BUD-D02 — IS lost budget (account-level distribution)
const heavyIsLost = limitedCampaigns.filter(c => c.isLostBudgetPct >= 25);
pushFinding(makeFinding(
    'BUD-D02',
    heavyIsLost.length === 0 ? 'PASS' : (heavyIsLost.length >= 3 ? 'FAIL' : 'WARN'),
    heavyIsLost.length === 0 ? 'info' : 'high',
    `${heavyIsLost.length} campaign(s) with IS Lost (Budget) >= 25%.`,
    { campaigns: heavyIsLost }
));

// BUD-D03 — Profitable + limited (high priority opportunity)
// BUD-D04 — Unprofitable + limited (reduce-first signal)
const profitableLimited = [];
const unprofitableLimited = [];
for (const c of limitedCampaigns) {
    const camp = campaigns.find(x => x.id === c.campaignId);
    if (!camp) continue;
    const cls = classifyProfitability(camp.agg, primaryKPI, breakEven);
    if (cls.state === 'profitable') {
        profitableLimited.push({ ...c, margin: cls.margin });
        // Surface as opportunity
        const opp = computeOpportunityValue(camp.agg, primaryKPI, breakEven);
        if (opp) {
            opportunities.push({
                type: 'profitable_limited_recovery',
                campaign: c.campaign,
                campaignId: c.campaignId,
                channel: c.channel,
                isLostBudget: c.isLostBudgetPct,
                projection: opp,
                action: '/budget-optimizer raise',
                rationale: 'Profitable + budget-limited — raising budget recovers lost IS at a profitable projected unit cost.',
            });
        }
    } else if (cls.state === 'unprofitable') {
        unprofitableLimited.push({ ...c, margin: cls.margin });
    }
}

pushFinding(makeFinding(
    'BUD-D03',
    profitableLimited.length === 0 ? 'PASS' : 'WARN',
    profitableLimited.length === 0 ? 'info' : 'high',
    profitableLimited.length === 0
        ? 'No profitable campaigns are budget-limited.'
        : `${profitableLimited.length} profitable campaign(s) constrained by budget.`,
    {
        campaigns: profitableLimited,
        blocking: targetSourceFallback ? ['business'] : [],
        targetSource: targetSourceFallback || 'configured',
    }
));

pushFinding(makeFinding(
    'BUD-D04',
    unprofitableLimited.length === 0 ? 'PASS' : 'FAIL',
    unprofitableLimited.length === 0 ? 'info' : 'critical',
    unprofitableLimited.length === 0
        ? 'No unprofitable campaigns are budget-limited.'
        : `${unprofitableLimited.length} unprofitable campaign(s) still budget-limited — reduce or pause before any raise.`,
    {
        campaigns: unprofitableLimited,
        blocking: targetSourceFallback ? ['business'] : [],
    }
));

// ─────────────────────────────────────────────────────────────────────
// MODULE 2 — Sufficiency
// ─────────────────────────────────────────────────────────────────────

const dailyToCpaRatio = num(ba.dailyBudgetToCpaRatio, 2.0);
const minSmartConv = num(ba.minConvVolumeForSmartBidding, 30);

// BUD-D05 — Daily budget : tCPA ratio (Search/Shopping)
const undersizedDaily = [];
for (const c of campaigns) {
    const channel = getChannelType(c.agg);
    if (!isSearch(c.agg) && !isShopping(c.agg)) continue;
    const tCpa = getTargetCpa(c.agg);
    if (!tCpa) continue;
    const dailyBudget = getDailyBudget(c.agg);
    if (!dailyBudget) continue;
    const ratio = dailyBudget / tCpa;
    if (ratio < dailyToCpaRatio) {
        undersizedDaily.push({
            campaign: c.agg['campaign.name'],
            campaignId: c.id,
            channel,
            dailyBudget: Math.round(dailyBudget * 100) / 100,
            tCpa: Math.round(tCpa * 100) / 100,
            ratio: Math.round(ratio * 100) / 100,
        });
    }
}
pushFinding(makeFinding(
    'BUD-D05',
    undersizedDaily.length === 0 ? 'PASS' : 'WARN',
    undersizedDaily.length === 0 ? 'info' : 'medium',
    undersizedDaily.length === 0
        ? 'All Search/Shopping campaigns have daily budget >= 2x tCPA.'
        : `${undersizedDaily.length} campaign(s) with daily budget below ${dailyToCpaRatio}x tCPA — smart bidding undersupplied.`,
    { campaigns: undersizedDaily, blocking: undersizedDaily.length === 0 ? [] : ['bidding'] }
));

// BUD-D06 — Exhaustion timing (handled in pacing engine via daily series)
pushFinding(makeFinding(
    'BUD-D06', 'INFO', 'info',
    'Exhaustion timing analyzed in pacing engine (analyze-pacing.js).',
    { deferTo: 'analyze-pacing' }
));

// BUD-D07 — 2x spending limit awareness (informational on STANDARD delivery)
const standardDelivery = budgets.filter(b => (b['campaign_budget.delivery_method'] || '').toUpperCase() === 'STANDARD');
pushFinding(makeFinding(
    'BUD-D07', 'INFO', 'info',
    `Reminder: Google may spend up to 2x daily budget on STANDARD delivery (${standardDelivery.length} of ${budgets.length} budgets).`,
    { standardCount: standardDelivery.length, totalBudgets: budgets.length }
));

// BUD-D08 — Budget vs conversion volume (smart-bidding floor)
const undervolumeSmart = [];
for (const c of campaigns) {
    const strategyType = (c.agg['campaign.bidding_strategy_type'] || '').toUpperCase();
    if (!isSmartBidding(strategyType)) continue;
    const channel = getChannelType(c.agg);
    const required = getMinConvVolumeForSmartBidding(channel, strategyType, minSmartConv);
    // Period is in days; normalize to monthly conv volume for the threshold check.
    const conv = num(c.agg['metrics.conversions']);
    const monthlyConv = period >= 30 ? conv * (30 / period) : conv;
    if (monthlyConv < required) {
        undervolumeSmart.push({
            campaign: c.agg['campaign.name'],
            campaignId: c.id,
            channel,
            strategyType,
            monthlyConv: Math.round(monthlyConv * 10) / 10,
            required,
        });
    }
}
pushFinding(makeFinding(
    'BUD-D08',
    undervolumeSmart.length === 0 ? 'PASS' : 'WARN',
    undervolumeSmart.length === 0 ? 'info' : 'medium',
    undervolumeSmart.length === 0
        ? 'All smart-bidding campaigns clear channel-specific monthly conversion floors.'
        : `${undervolumeSmart.length} smart-bidding campaign(s) below required monthly conversion floor.`,
    { campaigns: undervolumeSmart, blocking: undervolumeSmart.length === 0 ? [] : ['bidding'] }
));

// ─────────────────────────────────────────────────────────────────────
// MODULE 4 — Allocation
// ─────────────────────────────────────────────────────────────────────

// Group experiment rows under their base (by shared budget id) so a
// base+experiment pair counts as one budget consumer.
const groupedRows = groupExperimentsWithBases(campaigns.map(c => c.agg));
const consumers = [];
for (const [, group] of groupedRows) {
    const cost = group.members.reduce((s, r) => s + getCost(r), 0);
    const conv = group.members.reduce((s, r) => s + num(r['metrics.conversions']), 0);
    const value = group.members.reduce((s, r) => s + num(r['metrics.conversions_value']), 0);
    const base = group.base || group.members[0];
    consumers.push({
        name: base['campaign.name'],
        id: base['campaign.id'],
        channel: getChannelType(base),
        cost,
        conv,
        value,
        sharePct: totalSpend > 0 ? (cost / totalSpend) * 100 : 0,
        agg: base,
        members: group.members,
    });
}

// BUD-D13 — high performers underfunded
// BUD-D14 — low performers consuming disproportionate share
const underfunded = [];
const overfunded = [];
const sharePctThreshold = 5; // share-of-spend threshold to qualify as "material"
for (const cn of consumers) {
    if (cn.cost < 10) continue; // ignore noise
    const cls = classifyProfitability(cn.agg, primaryKPI, breakEven);
    if (cls.state === 'profitable' && cn.sharePct < sharePctThreshold) {
        underfunded.push({
            campaign: cn.name, channel: cn.channel,
            cost: Math.round(cn.cost), sharePct: Math.round(cn.sharePct * 10) / 10,
            margin: cls.margin,
        });
    } else if (cls.state === 'unprofitable' && cn.sharePct >= sharePctThreshold) {
        overfunded.push({
            campaign: cn.name, channel: cn.channel,
            cost: Math.round(cn.cost), sharePct: Math.round(cn.sharePct * 10) / 10,
            margin: cls.margin,
        });
    }
}
pushFinding(makeFinding(
    'BUD-D13',
    underfunded.length === 0 ? 'PASS' : 'WARN',
    underfunded.length === 0 ? 'info' : 'high',
    underfunded.length === 0
        ? 'No high-performing campaigns are starved of budget share.'
        : `${underfunded.length} profitable campaign(s) running below ${sharePctThreshold}% share of total spend.`,
    { campaigns: underfunded, blocking: targetSourceFallback ? ['business'] : [] }
));
pushFinding(makeFinding(
    'BUD-D14',
    overfunded.length === 0 ? 'PASS' : 'FAIL',
    overfunded.length === 0 ? 'info' : 'high',
    overfunded.length === 0
        ? 'No underperforming campaigns are over-allocated.'
        : `${overfunded.length} unprofitable campaign(s) consuming >= ${sharePctThreshold}% of spend.`,
    { campaigns: overfunded, blocking: targetSourceFallback ? ['business'] : [] }
));

// BUD-D15 — Cross-campaign efficiency: did spend tilt toward winners overall?
let crossEfficiencyVerdict = 'INFO';
let crossMessage = 'Cross-campaign efficiency check requires unit economics — set break-even via /strategy-specialist.';
if (primaryKPI && breakEven != null) {
    let profCost = 0, unpCost = 0;
    for (const cn of consumers) {
        const cls = classifyProfitability(cn.agg, primaryKPI, breakEven);
        if (cls.state === 'profitable') profCost += cn.cost;
        else if (cls.state === 'unprofitable') unpCost += cn.cost;
    }
    const denom = profCost + unpCost;
    const profShare = denom > 0 ? profCost / denom : null;
    if (profShare == null) {
        crossEfficiencyVerdict = 'INFO';
        crossMessage = 'Insufficient classified spend to evaluate cross-campaign efficiency.';
    } else if (profShare >= 0.7) {
        crossEfficiencyVerdict = 'PASS';
        crossMessage = `Profitable share of classified spend = ${(profShare * 100).toFixed(0)}%.`;
    } else if (profShare >= 0.5) {
        crossEfficiencyVerdict = 'WARN';
        crossMessage = `Profitable share of classified spend = ${(profShare * 100).toFixed(0)}% — reallocation upside.`;
    } else {
        crossEfficiencyVerdict = 'FAIL';
        crossMessage = `Profitable share of classified spend = ${(profShare * 100).toFixed(0)}% — major reallocation needed.`;
    }
}
pushFinding(makeFinding(
    'BUD-D15', crossEfficiencyVerdict,
    crossEfficiencyVerdict === 'FAIL' ? 'high' : 'medium',
    crossMessage,
    { blocking: targetSourceFallback ? ['business'] : [] }
));

// BUD-D16 — Zero-spend active campaigns
const zeroSpendDays = num(ba.zeroSpendDays, 7);
const zeroSpend = consumers.filter(cn => cn.cost === 0 && cn.members.some(m => (m['campaign.serving_status'] || '').toUpperCase() === 'SERVING'));
pushFinding(makeFinding(
    'BUD-D16',
    zeroSpend.length === 0 ? 'PASS' : 'WARN',
    zeroSpend.length === 0 ? 'info' : 'medium',
    zeroSpend.length === 0
        ? 'No active campaigns are running zero-spend.'
        : `${zeroSpend.length} active campaign(s) with zero spend over the audit window — likely policy/approval/targeting block.`,
    {
        campaigns: zeroSpend.map(c => ({ campaign: c.name, channel: c.channel })),
        windowDays: period,
        suspectedZeroSpendDaysThreshold: zeroSpendDays,
    }
));

// ─────────────────────────────────────────────────────────────────────
// MODULE 5 — Shared Budgets
// ─────────────────────────────────────────────────────────────────────

const sharedBudgets = budgets.filter(b => String(b['campaign_budget.explicitly_shared']).toLowerCase() === 'true');

if (sharedBudgets.length === 0) {
    pushFinding(makeFinding(
        'BUD-D17', 'SKIP', 'info',
        'No shared budgets in account — module N/A; weight redistributes.',
        { module: 'shared' }
    ));
    pushFinding(makeFinding('BUD-D18', 'SKIP', 'info', 'No shared budgets in account.', { module: 'shared' }));
    pushFinding(makeFinding('BUD-D19', 'SKIP', 'info', 'No shared budgets in account.', { module: 'shared' }));
} else {
    // Index portfolios by resource_name
    const portfoliosByResource = new Map();
    for (const p of portfolios) {
        const rn = p['bidding_strategy.resource_name'];
        if (rn) portfoliosByResource.set(rn, p);
    }

    // For each shared budget, find member campaigns
    const imbalances = [];
    const objectiveMixes = [];
    const portfolioConflicts = [];

    for (const b of sharedBudgets) {
        const budgetId = b['campaign_budget.id'];
        const members = campaigns.filter(c => c.agg['campaign_budget.id'] === budgetId);
        if (members.length < 2) continue;

        const costs = members.map(m => getCost(m.agg));
        const totalCost = costs.reduce((a, c) => a + c, 0);

        // Imbalance: max share / total > 0.7 = one campaign dominates
        const maxShare = totalCost > 0 ? Math.max(...costs) / totalCost : 0;
        if (maxShare > 0.7) {
            imbalances.push({
                budget: b['campaign_budget.name'],
                budgetId,
                members: members.map(m => ({
                    campaign: m.agg['campaign.name'],
                    cost: Math.round(getCost(m.agg)),
                    isExperiment: isExperimentRow(m.agg),
                })),
                dominanceShare: Math.round(maxShare * 100) / 100,
            });
        }

        // Different objectives: mixed channel types or mixed strategy categories
        const channelSet = new Set(members.map(m => getChannelType(m.agg)));
        const strategySet = new Set(members.map(m => (m.agg['campaign.bidding_strategy_type'] || '').toUpperCase()));
        if (channelSet.size > 1 || strategySet.size > 1) {
            objectiveMixes.push({
                budget: b['campaign_budget.name'],
                channels: Array.from(channelSet),
                strategies: Array.from(strategySet),
                memberCount: members.length,
            });
        }

        // Portfolio conflict: at least one member uses a portfolio strategy and the
        // budget is shared at the same time (operationally fragile combination).
        const portfolioMembers = members.filter(m => !!m.agg['campaign.bidding_strategy']);
        if (portfolioMembers.length > 0) {
            portfolioConflicts.push({
                budget: b['campaign_budget.name'],
                portfolioCampaigns: portfolioMembers.map(m => m.agg['campaign.name']),
                allMembers: members.map(m => m.agg['campaign.name']),
            });
        }
    }

    pushFinding(makeFinding(
        'BUD-D17',
        imbalances.length === 0 ? 'PASS' : 'WARN',
        imbalances.length === 0 ? 'info' : 'medium',
        imbalances.length === 0
            ? 'Shared budgets are reasonably balanced across members.'
            : `${imbalances.length} shared budget(s) where one campaign captures >70% of pool.`,
        { sharedBudgets: imbalances }
    ));
    pushFinding(makeFinding(
        'BUD-D18',
        objectiveMixes.length === 0 ? 'PASS' : 'WARN',
        objectiveMixes.length === 0 ? 'info' : 'medium',
        objectiveMixes.length === 0
            ? 'Shared budgets group campaigns with consistent objectives.'
            : `${objectiveMixes.length} shared budget(s) mixing channel types or strategy categories.`,
        { sharedBudgets: objectiveMixes }
    ));
    pushFinding(makeFinding(
        'BUD-D19',
        portfolioConflicts.length === 0 ? 'PASS' : 'WARN',
        portfolioConflicts.length === 0 ? 'info' : 'medium',
        portfolioConflicts.length === 0
            ? 'No shared budgets conflicting with portfolio bid strategies.'
            : `${portfolioConflicts.length} shared budget(s) coexist with portfolio strategies — verify intent.`,
        { sharedBudgets: portfolioConflicts, blocking: portfolioConflicts.length === 0 ? [] : ['bidding'] }
    ));
}

// ─────────────────────────────────────────────────────────────────────
// Cross-cutting opportunities for healthy + flagged accounts
// ─────────────────────────────────────────────────────────────────────

// (1) winners with low budget share that aren't marked profitable yet —
// surface as "investigate" opportunities (no profit projection without break-even).
if (!targetSourceFallback) {
    for (const cn of consumers) {
        if (cn.cost < 50) continue;
        const cls = classifyProfitability(cn.agg, primaryKPI, breakEven);
        if (cls.state !== 'profitable') continue;
        const isLost = num(cn.agg['metrics.search_budget_lost_impression_share']);
        if (isLost > (isLostBudgetThresholdPct / 100) && cn.sharePct < 15) {
            const opp = computeOpportunityValue(cn.agg, primaryKPI, breakEven);
            if (opp && opp.profitable) {
                opportunities.push({
                    type: 'winner_underfunded',
                    campaign: cn.name,
                    channel: cn.channel,
                    sharePct: Math.round(cn.sharePct * 10) / 10,
                    isLostBudget: Math.round(isLost * 1000) / 10,
                    projection: opp,
                    action: '/budget-optimizer raise',
                });
            }
        }
    }
}

// ─────────────────────────────────────────────────────────────────────
// Write outputs
// ─────────────────────────────────────────────────────────────────────

writeFileSync(
    resolve(outDir, 'findings-health.json'),
    JSON.stringify({
        meta: {
            engine: 'analyze-budget-health',
            generatedAt: new Date().toISOString(),
            period,
            primaryKPI,
            breakEven,
            targetSource: targetSourceFallback || 'configured',
            accountCurrency,
            campaignsAnalyzed: campaigns.length,
            consumersAfterExperimentGrouping: consumers.length,
            sharedBudgetsFound: sharedBudgets.length,
        },
        findings,
    }, null, 2)
);

writeFileSync(
    resolve(outDir, 'opportunities-health.json'),
    JSON.stringify({
        meta: {
            engine: 'analyze-budget-health',
            generatedAt: new Date().toISOString(),
            primaryKPI,
            breakEven,
        },
        opportunities,
    }, null, 2)
);

console.log(`\nBudget Health — ${findings.length} findings, ${opportunities.length} opportunities.`);
console.log(`Wrote: ${resolve(outDir, 'findings-health.json')}`);
console.log(`Wrote: ${resolve(outDir, 'opportunities-health.json')}`);
