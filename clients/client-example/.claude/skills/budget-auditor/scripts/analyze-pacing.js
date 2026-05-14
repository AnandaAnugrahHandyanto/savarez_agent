#!/usr/bin/env node

/**
 * Budget Auditor — Module 3 (Pacing)
 *
 * Reads campaigns-pacing-daily.csv + campaign-budgets.csv + campaigns-budget-perf.csv,
 * computes MTD spend vs target, projects month-end, detects exhaustion patterns,
 * and writes findings + a pacing-projection.csv.
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

import {
    readCsv, num, makeFinding,
    groupDailyByCampaign, computeMtdProjection, detectExhaustionPattern,
    getSeasonalityState, getCost, getDailyBudget,
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

const config = JSON.parse(readFileSync(resolve(projectRoot, 'config/ads-context.config.json'), 'utf8'));
const ba = config.budgetAudit || {};
const accountCurrency = config.accountCurrency || 'USD';
const monthlyTarget = ba.monthlyBudgetTotal;
const overspendPp = num(ba.overspendAlertPp, 10);
const underspendPp = num(ba.underspendAlertPp, 10);
const fallbackMode = ba.targetFallbackMode === 'no_monthly_target';
const seasonality = ba.seasonalityProfile || { mode: 'flat', months: [] };

const dataDir = resolve(projectRoot, 'context/google-ads/data');
const outDir = resolve(projectRoot, 'context/analysis/budget');
mkdirSync(outDir, { recursive: true });

const findings = [];
const opportunities = [];

const today = new Date();
const seasonState = getSeasonalityState(today, seasonality);

if (fallbackMode || monthlyTarget == null) {
    const note = fallbackMode
        ? 'Pacing skipped — config has targetFallbackMode = "no_monthly_target".'
        : 'Pacing skipped — no monthlyBudgetTotal configured. Run /budget-auditor reconfirm to set one, or accept fallback mode.';
    for (const id of ['BUD-D09','BUD-D10','BUD-D11','BUD-D12']) {
        findings.push(makeFinding(id, 'SKIP', 'info', note, { module: 'pacing' }));
    }
    writeFileSync(resolve(outDir, 'findings-pacing.json'), JSON.stringify({
        meta: { engine: 'analyze-pacing', generatedAt: new Date().toISOString(), skipped: true, reason: note, seasonalityState: seasonState },
        findings,
    }, null, 2));
    writeFileSync(resolve(outDir, 'opportunities-pacing.json'), JSON.stringify({ opportunities: [] }, null, 2));
    console.log(`Pacing module skipped: ${note}`);
    process.exit(0);
}

const daily = readCsv(resolve(dataDir, 'campaigns-pacing-daily.csv'));
const budgets = readCsv(resolve(dataDir, 'campaign-budgets.csv'));
const perf = readCsv(resolve(dataDir, 'campaigns-budget-perf.csv'));

const dailyByCampaign = groupDailyByCampaign(daily);

// Account-level series (sum of all campaigns, all dates)
const accountSeriesMap = new Map();
for (const r of daily) {
    const date = r['segments.date'];
    if (!date) continue;
    const cost = getCost(r);
    accountSeriesMap.set(date, (accountSeriesMap.get(date) || 0) + cost);
}
const accountSeries = Array.from(accountSeriesMap.entries())
    .map(([date, cost]) => ({ date, cost }))
    .sort((a, b) => a.date.localeCompare(b.date));

const acctProj = computeMtdProjection(accountSeries, today);
const target = num(monthlyTarget);
const projVsTargetPp = target > 0 ? ((acctProj.projectedMonth - target) / target) * 100 : 0;
const mtdVsTargetPp = target > 0 ? ((acctProj.mtdSpend - target * (acctProj.daysElapsed / acctProj.daysInMonth)) / target) * 100 : 0;

// BUD-D09 — MTD spend vs target
let d09Verdict = 'PASS';
let d09Severity = 'info';
let d09Msg = `MTD spend ${acctProj.mtdSpend.toFixed(0)} ${accountCurrency} vs proportional target ${(target * acctProj.daysElapsed / acctProj.daysInMonth).toFixed(0)} (${mtdVsTargetPp >= 0 ? '+' : ''}${mtdVsTargetPp.toFixed(1)}pp).`;
if (Math.abs(mtdVsTargetPp) > overspendPp) {
    d09Verdict = 'WARN'; d09Severity = 'medium';
}
findings.push(makeFinding('BUD-D09', d09Verdict, d09Severity, d09Msg, {
    mtdSpend: Math.round(acctProj.mtdSpend),
    proportionalTarget: Math.round(target * acctProj.daysElapsed / acctProj.daysInMonth),
    monthlyTarget: target,
    daysElapsed: acctProj.daysElapsed,
    daysInMonth: acctProj.daysInMonth,
    deviationPp: Math.round(mtdVsTargetPp * 10) / 10,
}));

// BUD-D10 — Overspend alert
let d10Verdict = 'PASS', d10Sev = 'info';
let d10Msg = `Projected month-end ${acctProj.projectedMonth.toFixed(0)} ${accountCurrency} vs target ${target} (${projVsTargetPp >= 0 ? '+' : ''}${projVsTargetPp.toFixed(1)}%).`;
if (projVsTargetPp > overspendPp) {
    d10Verdict = projVsTargetPp > overspendPp * 2 ? 'FAIL' : 'WARN';
    d10Sev = d10Verdict === 'FAIL' ? 'high' : 'medium';
    d10Msg = `Projected to overspend by ${projVsTargetPp.toFixed(1)}% (target ${target}, projected ${acctProj.projectedMonth.toFixed(0)}).`;
}
findings.push(makeFinding('BUD-D10', d10Verdict, d10Sev, d10Msg, {
    projectedMonth: Math.round(acctProj.projectedMonth),
    target,
    deviationPct: Math.round(projVsTargetPp * 10) / 10,
}));

// BUD-D11 — Underspend alert
let d11Verdict = 'PASS', d11Sev = 'info';
let d11Msg = `Pacing within ${underspendPp}% under-target band.`;
if (projVsTargetPp < -underspendPp) {
    d11Verdict = projVsTargetPp < -underspendPp * 2 ? 'FAIL' : 'WARN';
    d11Sev = d11Verdict === 'FAIL' ? 'high' : 'medium';
    d11Msg = `Projected to underspend by ${Math.abs(projVsTargetPp).toFixed(1)}% (target ${target}, projected ${acctProj.projectedMonth.toFixed(0)}).`;
    if (seasonState.isHighlight) {
        d11Sev = 'high';
        d11Msg += ` This is a designated highlight month (${seasonState.currentMonth}) — underspend is more costly than usual.`;
    }
    // Underspend = unspent budget for redeployment; surface as opportunity
    opportunities.push({
        type: 'underspend_redeploy',
        currentMonth: seasonState.currentMonth,
        unspentMonthly: Math.round(target - acctProj.projectedMonth),
        action: '/budget-optimizer reallocate',
        rationale: 'Projected underspend leaves headroom to scale winners or test new campaigns this month.',
    });
}
findings.push(makeFinding('BUD-D11', d11Verdict, d11Sev, d11Msg, {
    projectedMonth: Math.round(acctProj.projectedMonth),
    target,
    deviationPct: Math.round(projVsTargetPp * 10) / 10,
    isHighlightMonth: seasonState.isHighlight,
}));

// BUD-D12 — Seasonal adjustment awareness
let d12Verdict = 'INFO', d12Sev = 'info';
let d12Msg = `Seasonality mode: ${seasonState.mode}. Current month: ${seasonState.currentMonth}.`;
if (seasonState.mode === 'highlight_months') {
    if (seasonState.approachingHighlight) {
        d12Verdict = 'WARN'; d12Sev = 'medium';
        d12Msg = `Approaching highlight month (${seasonState.nextMonth}). Confirm budgets are sized for the seasonal lift.`;
        opportunities.push({
            type: 'seasonality_ramp',
            month: seasonState.nextMonth,
            action: '/budget-optimizer raise',
            rationale: `Highlight month "${seasonState.nextMonth}" begins next month — consider preemptive scale on profitable campaigns.`,
        });
    } else if (seasonState.isHighlight) {
        d12Msg = `In a highlight month (${seasonState.currentMonth}). Pacing thresholds may need temporary widening.`;
    }
}
findings.push(makeFinding('BUD-D12', d12Verdict, d12Sev, d12Msg, {
    seasonalityState: seasonState,
}));

// BUD-D06 — Exhaustion timing (daily-level pattern)
const budgetsById = new Map();
for (const b of budgets) {
    const id = b['campaign_budget.id'];
    if (id) budgetsById.set(id, b);
}
const exhaustionFlags = [];
for (const [campaignId, entries] of dailyByCampaign) {
    if (entries.length === 0) continue;
    const budgetId = entries[0].row['campaign_budget.id'];
    if (!budgetId) continue;
    const b = budgetsById.get(budgetId);
    if (!b) continue;
    const dailyBudget = getDailyBudget(b);
    const recent = entries.slice(-14); // last 14 days
    const ex = detectExhaustionPattern(recent, dailyBudget);
    if (ex && ex.ratio >= 0.5 && recent.length >= 7) {
        const name = entries[0].row['campaign.name'] || campaignId;
        exhaustionFlags.push({
            campaign: name,
            campaignId,
            exhaustedDays: ex.exhaustedDays,
            observedDays: ex.observedDays,
            ratio: Math.round(ex.ratio * 100) / 100,
            dailyBudget: Math.round(dailyBudget * 100) / 100,
        });
    }
}
findings.push(makeFinding(
    'BUD-D06',
    exhaustionFlags.length === 0 ? 'PASS' : 'WARN',
    exhaustionFlags.length === 0 ? 'info' : 'medium',
    exhaustionFlags.length === 0
        ? 'No campaigns showing chronic daily-budget exhaustion in the last 14 days.'
        : `${exhaustionFlags.length} campaign(s) hit daily budget on >=50% of recent days — possible mid-day exhaustion.`,
    { campaigns: exhaustionFlags, note: 'Hourly segmentation deferred to v1.1; daily 95% threshold used as v1 heuristic.' }
));

// Write pacing-projection.csv (account level + per-campaign daily series)
const csvLines = ['scope,date,cost,daily_budget,monthly_target_share'];
for (const r of accountSeries) {
    csvLines.push(`account,${r.date},${r.cost.toFixed(2)},,${(target / acctProj.daysInMonth).toFixed(2)}`);
}
// Forecast tail to end of month based on avgDaily
const avgDaily = acctProj.avgDaily;
const monthPrefix = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;
for (let day = acctProj.daysElapsed + 1; day <= acctProj.daysInMonth; day++) {
    const dateStr = `${monthPrefix}-${String(day).padStart(2, '0')}`;
    csvLines.push(`account_projection,${dateStr},${avgDaily.toFixed(2)},,${(target / acctProj.daysInMonth).toFixed(2)}`);
}
writeFileSync(resolve(outDir, 'pacing-projection.csv'), csvLines.join('\n'));

writeFileSync(resolve(outDir, 'findings-pacing.json'), JSON.stringify({
    meta: {
        engine: 'analyze-pacing',
        generatedAt: new Date().toISOString(),
        accountCurrency,
        monthlyTarget: target,
        seasonalityState: seasonState,
        projection: {
            mtdSpend: Math.round(acctProj.mtdSpend),
            projectedMonth: Math.round(acctProj.projectedMonth),
            daysElapsed: acctProj.daysElapsed,
            daysInMonth: acctProj.daysInMonth,
            avgDaily: Math.round(avgDaily * 100) / 100,
        },
    },
    findings,
}, null, 2));

writeFileSync(resolve(outDir, 'opportunities-pacing.json'), JSON.stringify({
    meta: { engine: 'analyze-pacing', generatedAt: new Date().toISOString() },
    opportunities,
}, null, 2));

console.log(`\nPacing — ${findings.length} findings, ${opportunities.length} opportunities.`);
console.log(`MTD: ${acctProj.mtdSpend.toFixed(0)} ${accountCurrency} | Projected month-end: ${acctProj.projectedMonth.toFixed(0)} | Target: ${target} (${projVsTargetPp >= 0 ? '+' : ''}${projVsTargetPp.toFixed(1)}%)`);
console.log(`Wrote: ${resolve(outDir, 'findings-pacing.json')}`);
console.log(`Wrote: ${resolve(outDir, 'pacing-projection.csv')}`);
