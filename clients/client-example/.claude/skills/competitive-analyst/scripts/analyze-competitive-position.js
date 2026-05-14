#!/usr/bin/env node

/**
 * Competitive Position Analysis — competitive-analyst
 *
 * Reads campaign IS timeseries, keyword IS, and (optionally) shopping ad group
 * IS timeseries. Produces competitive-flags.csv with flagged issues across
 * 7 diagnostics: CA-D01, CA-D02, CA-D05, CA-D08, CA-D09, CA-D11, CA-D13.
 *
 * Usage:
 *   node analyze-competitive-position.js \
 *     --timeseries-csv=context/google-ads/data/campaign-is-timeseries.csv \
 *     --keyword-csv=context/google-ads/data/keyword-is.csv \
 *     [--shopping-adgroup-csv=context/google-ads/data/shopping-adgroup-is-timeseries.csv] \
 *     --output=context/google-ads/data/competitive-flags.csv
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

const timeseriesCsvPath = resolve(_projectRoot, args['timeseries-csv'] || '');
const keywordCsvPath = resolve(_projectRoot, args['keyword-csv'] || '');
const shoppingAgCsvPath = args['shopping-adgroup-csv'] ? resolve(_projectRoot, args['shopping-adgroup-csv']) : null;
const outputPath = resolve(_projectRoot, args['output'] || 'context/google-ads/data/competitive-flags.csv');

// ── Helpers ─────────────────────────────────────────────────────────
function loadCsv(path) {
    if (!existsSync(path)) return [];
    const content = readFileSync(path, 'utf8');
    if (!content.trim()) return [];
    return parse(content, { columns: true, skip_empty_lines: true, relax_column_count: true });
}

function num(v) {
    if (v === undefined || v === null || v === '' || v === '--' || v === ' --') return null;
    const n = parseFloat(String(v).replace(/[,%]/g, ''));
    return isNaN(n) ? null : n;
}

function pct(v) {
    // Handle percentage values — may come as "0.45" (ratio) or "45%" or "45"
    const n = num(v);
    if (n === null) return null;
    // If the value contains '%', it's already a percentage
    if (String(v).includes('%')) return n;
    // If between 0 and 1 (exclusive), treat as ratio → convert to percentage
    if (n > 0 && n < 1) return n * 100;
    // Otherwise treat as percentage already
    return n;
}

function costFromMicros(v) {
    const n = num(v);
    return n !== null ? n / 1_000_000 : 0;
}

function cpcFromMicros(v) {
    const n = num(v);
    return n !== null ? n / 1_000_000 : null;
}

// ── Load data ───────────────────────────────────────────────────────
console.log('\nCompetitive Position Analysis');
console.log('─'.repeat(40));

const timeseriesRows = loadCsv(timeseriesCsvPath);
const keywordRows = loadCsv(keywordCsvPath);
const shoppingAgRows = shoppingAgCsvPath ? loadCsv(shoppingAgCsvPath) : [];

console.log(`Campaign timeseries rows: ${timeseriesRows.length}`);
console.log(`Keyword IS rows: ${keywordRows.length}`);
console.log(`Shopping AG timeseries rows: ${shoppingAgRows.length}`);

if (timeseriesRows.length === 0) {
    console.error('Error: No campaign timeseries data. Cannot analyze.');
    process.exit(1);
}

const flags = [];

function addFlag(flagType, checkId, data) {
    flags.push({
        flag_type: flagType,
        check_id: checkId,
        campaign_id: data.campaign_id || '',
        campaign_name: data.campaign_name || '',
        ad_group_id: data.ad_group_id || '',
        ad_group_name: data.ad_group_name || '',
        keyword_text: data.keyword_text || '',
        metric_name: data.metric_name || '',
        metric_value: data.metric_value ?? '',
        threshold: data.threshold ?? '',
        delta: data.delta ?? '',
        severity: data.severity || '',
        detail: data.detail || '',
    });
}

// ── Organize timeseries by campaign ─────────────────────────────────
const campaignDays = {};  // campaign_id → [{date, IS, budget_lost, rank_lost, ...}]
const campaignMeta = {};  // campaign_id → {name, channel_type, bidding_strategy}

for (const row of timeseriesRows) {
    const cid = row.campaign_id || row['campaign.id'];
    if (!cid) continue;

    if (!campaignMeta[cid]) {
        campaignMeta[cid] = {
            name: row.campaign_name || row['campaign.name'] || '',
            channel_type: row.advertising_channel_type || row['campaign.advertising_channel_type'] || '',
            bidding_strategy: row.bidding_strategy_type || row['campaign.bidding_strategy_type'] || '',
        };
    }

    if (!campaignDays[cid]) campaignDays[cid] = [];

    campaignDays[cid].push({
        date: row.date || row['segments.date'] || '',
        impressions: num(row.impressions || row['metrics.impressions']) || 0,
        clicks: num(row.clicks || row['metrics.clicks']) || 0,
        cost: costFromMicros(row.cost_micros || row['metrics.cost_micros']),
        conversions: num(row.conversions || row['metrics.conversions']) || 0,
        conversions_value: num(row.conversions_value || row['metrics.conversions_value']) || 0,
        average_cpc: cpcFromMicros(row.average_cpc || row['metrics.average_cpc']),
        is: pct(row.search_impression_share || row['metrics.search_impression_share']),
        budget_lost_is: pct(row.search_budget_lost_impression_share || row['metrics.search_budget_lost_impression_share']),
        rank_lost_is: pct(row.search_rank_lost_impression_share || row['metrics.search_rank_lost_impression_share']),
        top_is: pct(row.search_top_impression_share || row['metrics.search_top_impression_share']),
        abs_top_is: pct(row.search_absolute_top_impression_share || row['metrics.search_absolute_top_impression_share']),
    });
}

// Sort each campaign's days chronologically
for (const cid of Object.keys(campaignDays)) {
    campaignDays[cid].sort((a, b) => a.date.localeCompare(b.date));
}

// ── Helper: compute windowed average of a metric ────────────────────
function windowAvg(days, metric, startIdx, windowSize) {
    let sum = 0;
    let count = 0;
    for (let i = startIdx; i < Math.min(startIdx + windowSize, days.length); i++) {
        const v = days[i][metric];
        if (v !== null && v !== undefined) {
            sum += v;
            count++;
        }
    }
    return count > 0 ? sum / count : null;
}

// ── CA-D01: IS Trajectory per campaign ──────────────────────────────
console.log('\nRunning CA-D01: IS trajectory...');

for (const [cid, days] of Object.entries(campaignDays)) {
    const meta = campaignMeta[cid];
    const validDays = days.filter(d => d.is !== null);
    if (validDays.length < 14) continue;  // need minimum data

    const totalDays = validDays.length;

    // 30-day windows: recent 30 vs prior 30
    const recent30Start = Math.max(0, totalDays - 30);
    const prior30Start = Math.max(0, recent30Start - 30);

    const recentIS = windowAvg(validDays, 'is', recent30Start, 30);
    const priorIS = windowAvg(validDays, 'is', prior30Start, 30);

    if (recentIS === null || priorIS === null) continue;

    const delta30 = recentIS - priorIS;

    // 90-day trajectory: last 30 vs first 30 of the window
    const first30IS = windowAvg(validDays, 'is', 0, 30);
    const delta90 = first30IS !== null ? recentIS - first30IS : null;

    // Classify
    let trajectory = 'STABLE';
    if (delta30 > 3) trajectory = 'RISING';
    else if (delta30 < -3) trajectory = 'DECLINING';

    // Flag per thresholds
    if (delta90 !== null && delta90 < -10) {
        addFlag('IS_DECLINING', 'CA-D01', {
            campaign_id: cid,
            campaign_name: meta.name,
            metric_name: 'search_impression_share_90d_delta',
            metric_value: delta90.toFixed(1),
            threshold: '-10pp/90d',
            delta: delta90.toFixed(1),
            severity: 'High',
            detail: `IS trajectory: ${trajectory}. Recent 30d avg: ${recentIS.toFixed(1)}%, first 30d avg: ${first30IS.toFixed(1)}%. 90-day decline: ${Math.abs(delta90).toFixed(1)}pp.`,
        });
    } else if (delta30 < -5) {
        addFlag('IS_DECLINING', 'CA-D01', {
            campaign_id: cid,
            campaign_name: meta.name,
            metric_name: 'search_impression_share_30d_delta',
            metric_value: delta30.toFixed(1),
            threshold: '-5pp/30d',
            delta: delta30.toFixed(1),
            severity: 'Medium',
            detail: `IS trajectory: ${trajectory}. Recent 30d avg: ${recentIS.toFixed(1)}%, prior 30d avg: ${priorIS.toFixed(1)}%. 30-day decline: ${Math.abs(delta30).toFixed(1)}pp.`,
        });
    }
}

// ── CA-D02: IS Loss Decomposition ───────────────────────────────────
console.log('Running CA-D02: IS loss decomposition...');

for (const [cid, days] of Object.entries(campaignDays)) {
    const meta = campaignMeta[cid];
    const validDays = days.filter(d => d.budget_lost_is !== null || d.rank_lost_is !== null);
    if (validDays.length === 0) continue;

    // Average over evaluation period
    let budgetLostSum = 0, budgetLostCount = 0;
    let rankLostSum = 0, rankLostCount = 0;

    for (const d of validDays) {
        if (d.budget_lost_is !== null) { budgetLostSum += d.budget_lost_is; budgetLostCount++; }
        if (d.rank_lost_is !== null) { rankLostSum += d.rank_lost_is; rankLostCount++; }
    }

    const avgBudgetLost = budgetLostCount > 0 ? budgetLostSum / budgetLostCount : 0;
    const avgRankLost = rankLostCount > 0 ? rankLostSum / rankLostCount : 0;
    const combinedLoss = avgBudgetLost + avgRankLost;

    // Classify dominant loss type
    const dominant = avgBudgetLost > avgRankLost ? 'BUDGET' : 'RANK';

    if (combinedLoss > 20) {
        addFlag('IS_LOSS_HIGH', 'CA-D02', {
            campaign_id: cid,
            campaign_name: meta.name,
            metric_name: 'combined_is_loss',
            metric_value: combinedLoss.toFixed(1),
            threshold: '20%',
            severity: 'High',
            detail: `Combined IS loss: ${combinedLoss.toFixed(1)}%. Budget-lost: ${avgBudgetLost.toFixed(1)}%, Rank-lost: ${avgRankLost.toFixed(1)}%. Dominant: ${dominant}.`,
        });
    }

    // Always flag the dominant loss type for the report
    if (avgBudgetLost > 5) {
        addFlag('IS_LOSS_BUDGET', 'CA-D02', {
            campaign_id: cid,
            campaign_name: meta.name,
            metric_name: 'search_budget_lost_impression_share',
            metric_value: avgBudgetLost.toFixed(1),
            severity: avgBudgetLost > 15 ? 'High' : 'Medium',
            detail: `Budget-lost IS avg: ${avgBudgetLost.toFixed(1)}% over ${validDays.length} days.`,
        });
    }

    if (avgRankLost > 5) {
        addFlag('IS_LOSS_RANK', 'CA-D02', {
            campaign_id: cid,
            campaign_name: meta.name,
            metric_name: 'search_rank_lost_impression_share',
            metric_value: avgRankLost.toFixed(1),
            severity: avgRankLost > 15 ? 'High' : 'Medium',
            detail: `Rank-lost IS avg: ${avgRankLost.toFixed(1)}% over ${validDays.length} days.`,
        });
    }
}

// ── CA-D05: Top-of-page Rate Trends ─────────────────────────────────
console.log('Running CA-D05: Top-of-page rate trends...');

for (const [cid, days] of Object.entries(campaignDays)) {
    const meta = campaignMeta[cid];
    if (meta.channel_type === 'SHOPPING') continue;  // top-of-page is Search only

    const validDays = days.filter(d => d.abs_top_is !== null || d.top_is !== null);
    if (validDays.length < 14) continue;

    const totalDays = validDays.length;
    const recent30Start = Math.max(0, totalDays - 30);
    const prior30Start = Math.max(0, recent30Start - 30);

    // Absolute top IS trend
    const recentAbsTop = windowAvg(validDays, 'abs_top_is', recent30Start, 30);
    const priorAbsTop = windowAvg(validDays, 'abs_top_is', prior30Start, 30);

    if (recentAbsTop !== null && priorAbsTop !== null) {
        const deltaAbsTop = recentAbsTop - priorAbsTop;

        if (deltaAbsTop < -10) {
            addFlag('TOP_IS_DECLINING', 'CA-D05', {
                campaign_id: cid,
                campaign_name: meta.name,
                metric_name: 'search_absolute_top_impression_share_30d_delta',
                metric_value: deltaAbsTop.toFixed(1),
                threshold: '-10pp/30d',
                delta: deltaAbsTop.toFixed(1),
                severity: 'High',
                detail: `Abs top IS declining ${Math.abs(deltaAbsTop).toFixed(1)}pp. Recent: ${recentAbsTop.toFixed(1)}%, prior: ${priorAbsTop.toFixed(1)}%.`,
            });
        } else if (deltaAbsTop < -5) {
            addFlag('TOP_IS_DECLINING', 'CA-D05', {
                campaign_id: cid,
                campaign_name: meta.name,
                metric_name: 'search_absolute_top_impression_share_30d_delta',
                metric_value: deltaAbsTop.toFixed(1),
                threshold: '-5pp/30d',
                delta: deltaAbsTop.toFixed(1),
                severity: 'Medium',
                detail: `Abs top IS declining ${Math.abs(deltaAbsTop).toFixed(1)}pp. Recent: ${recentAbsTop.toFixed(1)}%, prior: ${priorAbsTop.toFixed(1)}%.`,
            });
        }
    }

    // Top IS trend
    const recentTop = windowAvg(validDays, 'top_is', recent30Start, 30);
    const priorTop = windowAvg(validDays, 'top_is', prior30Start, 30);

    if (recentTop !== null && priorTop !== null) {
        const deltaTop = recentTop - priorTop;

        if (deltaTop < -5) {
            addFlag('TOP_IS_DECLINING', 'CA-D05', {
                campaign_id: cid,
                campaign_name: meta.name,
                metric_name: 'search_top_impression_share_30d_delta',
                metric_value: deltaTop.toFixed(1),
                threshold: '-5pp/30d',
                delta: deltaTop.toFixed(1),
                severity: 'Medium',
                detail: `Top IS declining ${Math.abs(deltaTop).toFixed(1)}pp. Recent: ${recentTop.toFixed(1)}%, prior: ${priorTop.toFixed(1)}%.`,
            });
        }
    }
}

// ── CA-D08: Keyword Competitive Position ────────────────────────────
console.log('Running CA-D08: Keyword competitive position...');

if (keywordRows.length > 0) {
    // Sort by cost descending, take top 20
    const kwSorted = [...keywordRows].sort((a, b) => {
        const costA = num(a.cost_micros || a['metrics.cost_micros']) || 0;
        const costB = num(b.cost_micros || b['metrics.cost_micros']) || 0;
        return costB - costA;
    });

    const top20 = kwSorted.slice(0, 20);

    for (const kw of top20) {
        const kwText = kw.keyword_text || kw['ad_group_criterion.keyword.text'] || '';
        const cid = kw.campaign_id || kw['campaign.id'] || '';
        const cname = kw.campaign_name || kw['campaign.name'] || '';
        const agId = kw.ad_group_id || kw['ad_group.id'] || '';
        const agName = kw.ad_group_name || kw['ad_group.name'] || '';
        const kwIS = pct(kw.search_impression_share || kw['metrics.search_impression_share']);
        const kwRankLost = pct(kw.search_rank_lost_impression_share || kw['metrics.search_rank_lost_impression_share']);
        const kwTopIS = pct(kw.search_top_impression_share || kw['metrics.search_top_impression_share']);
        const kwAbsTopIS = pct(kw.search_absolute_top_impression_share || kw['metrics.search_absolute_top_impression_share']);
        const kwCost = costFromMicros(kw.cost_micros || kw['metrics.cost_micros']);

        // Flag: IS < 30% with rank-lost > 40%
        if (kwIS !== null && kwIS < 30 && kwRankLost !== null && kwRankLost > 40) {
            addFlag('KEYWORD_IS_PRESSURE', 'CA-D08', {
                campaign_id: cid,
                campaign_name: cname,
                ad_group_id: agId,
                ad_group_name: agName,
                keyword_text: kwText,
                metric_name: 'keyword_is_with_rank_lost',
                metric_value: kwIS.toFixed(1),
                threshold: 'IS<30% AND rank-lost>40%',
                severity: 'High',
                detail: `Keyword IS: ${kwIS.toFixed(1)}%, Rank-lost: ${kwRankLost.toFixed(1)}%. Under heavy competitive pressure. Spend: $${kwCost.toFixed(2)}.`,
            });
        }

        // Flag: top-IS < 20% on high-spend keyword
        if (kwTopIS !== null && kwTopIS < 20) {
            addFlag('KEYWORD_POSITION_LOSS', 'CA-D08', {
                campaign_id: cid,
                campaign_name: cname,
                ad_group_id: agId,
                ad_group_name: agName,
                keyword_text: kwText,
                metric_name: 'keyword_top_impression_share',
                metric_value: kwTopIS.toFixed(1),
                threshold: 'top-IS<20%',
                severity: 'Medium',
                detail: `Top IS: ${kwTopIS.toFixed(1)}%, Abs top IS: ${kwAbsTopIS !== null ? kwAbsTopIS.toFixed(1) : 'N/A'}%. Losing page position. Spend: $${kwCost.toFixed(2)}.`,
            });
        }
    }
}

// ── CA-D09: Shopping Ad Group IS Analysis ───────────────────────────
console.log('Running CA-D09: Shopping ad group IS...');

if (shoppingAgRows.length > 0) {
    // Organize by campaign → ad_group → days
    const shoppingCampaignAgs = {};

    for (const row of shoppingAgRows) {
        const cid = row.campaign_id || row['campaign.id'] || '';
        const agId = row.ad_group_id || row['ad_group.id'] || '';
        if (!cid || !agId) continue;

        if (!shoppingCampaignAgs[cid]) shoppingCampaignAgs[cid] = {};
        if (!shoppingCampaignAgs[cid][agId]) {
            shoppingCampaignAgs[cid][agId] = {
                name: row.ad_group_name || row['ad_group.name'] || '',
                campaign_name: row.campaign_name || row['campaign.name'] || '',
                days: [],
            };
        }

        shoppingCampaignAgs[cid][agId].days.push({
            date: row.date || row['segments.date'] || '',
            is: pct(row.search_impression_share || row['metrics.search_impression_share']),
            budget_lost_is: pct(row.search_budget_lost_impression_share || row['metrics.search_budget_lost_impression_share']),
            rank_lost_is: pct(row.search_rank_lost_impression_share || row['metrics.search_rank_lost_impression_share']),
        });
    }

    for (const [cid, adGroups] of Object.entries(shoppingCampaignAgs)) {
        const agIds = Object.keys(adGroups);
        if (agIds.length < 2) continue;  // need 2+ ad groups

        // Get campaign-level IS delta from Q1 data
        const campaignData = campaignDays[cid];
        let campaignDelta = 0;
        if (campaignData) {
            const validCampaignDays = campaignData.filter(d => d.is !== null);
            if (validCampaignDays.length >= 14) {
                const total = validCampaignDays.length;
                const recentCamp = windowAvg(validCampaignDays, 'is', Math.max(0, total - 30), 30);
                const priorCamp = windowAvg(validCampaignDays, 'is', Math.max(0, total - 60), 30);
                if (recentCamp !== null && priorCamp !== null) {
                    campaignDelta = recentCamp - priorCamp;
                }
            }
        }

        // Compute per-ad-group IS delta
        for (const [agId, ag] of Object.entries(adGroups)) {
            ag.days.sort((a, b) => a.date.localeCompare(b.date));
            const validAgDays = ag.days.filter(d => d.is !== null);
            if (validAgDays.length < 14) continue;

            const total = validAgDays.length;
            const recentAg = windowAvg(validAgDays, 'is', Math.max(0, total - 30), 30);
            const priorAg = windowAvg(validAgDays, 'is', Math.max(0, total - 60), 30);

            if (recentAg === null || priorAg === null) continue;

            const agDelta = recentAg - priorAg;

            // Isolated decline: ag declining more than campaign
            const isolatedDecline = agDelta - campaignDelta;

            if (isolatedDecline < -10) {
                addFlag('SHOPPING_AG_IS_SEVERE_DECLINE', 'CA-D09', {
                    campaign_id: cid,
                    campaign_name: ag.campaign_name,
                    ad_group_id: agId,
                    ad_group_name: ag.name,
                    metric_name: 'ad_group_is_isolated_decline',
                    metric_value: agDelta.toFixed(1),
                    threshold: '-10pp isolated decline',
                    delta: isolatedDecline.toFixed(1),
                    severity: 'High',
                    detail: `Ad group IS dropped ${Math.abs(agDelta).toFixed(1)}pp (${priorAg.toFixed(1)}% → ${recentAg.toFixed(1)}%) while campaign moved ${campaignDelta.toFixed(1)}pp. Isolated decline: ${Math.abs(isolatedDecline).toFixed(1)}pp — suggests category-specific competition.`,
                });
            } else if (isolatedDecline < -5) {
                addFlag('SHOPPING_AG_IS_ISOLATED_DECLINE', 'CA-D09', {
                    campaign_id: cid,
                    campaign_name: ag.campaign_name,
                    ad_group_id: agId,
                    ad_group_name: ag.name,
                    metric_name: 'ad_group_is_isolated_decline',
                    metric_value: agDelta.toFixed(1),
                    threshold: '-5pp isolated decline',
                    delta: isolatedDecline.toFixed(1),
                    severity: 'Medium',
                    detail: `Ad group IS dropped ${Math.abs(agDelta).toFixed(1)}pp (${priorAg.toFixed(1)}% → ${recentAg.toFixed(1)}%) while campaign moved ${campaignDelta.toFixed(1)}pp. Isolated decline: ${Math.abs(isolatedDecline).toFixed(1)}pp.`,
                });
            }
        }
    }
} else {
    console.log('  No Shopping ad group data — CA-D09 will SKIP');
}

// ── CA-D11: CPC-IS Correlation ──────────────────────────────────────
console.log('Running CA-D11: CPC-competitive pressure...');

for (const [cid, days] of Object.entries(campaignDays)) {
    const meta = campaignMeta[cid];

    // Build weekly aggregates for CPC and IS
    const weeklyData = {};
    for (const d of days) {
        if (!d.date || d.is === null || d.average_cpc === null) continue;
        // Week key = ISO week (YYYY-Www)
        const dt = new Date(d.date);
        const yearStart = new Date(dt.getFullYear(), 0, 1);
        const weekNum = Math.ceil(((dt - yearStart) / 86400000 + yearStart.getDay() + 1) / 7);
        const weekKey = `${dt.getFullYear()}-W${String(weekNum).padStart(2, '0')}`;

        if (!weeklyData[weekKey]) weeklyData[weekKey] = { cpcSum: 0, cpcCount: 0, isSum: 0, isCount: 0 };
        weeklyData[weekKey].cpcSum += d.average_cpc;
        weeklyData[weekKey].cpcCount++;
        weeklyData[weekKey].isSum += d.is;
        weeklyData[weekKey].isCount++;
    }

    const weeks = Object.keys(weeklyData).sort();
    if (weeks.length < 4) continue;  // need at least 4 weeks

    const weeklyCpc = weeks.map(w => weeklyData[w].cpcSum / weeklyData[w].cpcCount);
    const weeklyIs = weeks.map(w => weeklyData[w].isSum / weeklyData[w].isCount);

    // Pearson correlation coefficient
    const n = weeklyCpc.length;
    const meanCpc = weeklyCpc.reduce((s, v) => s + v, 0) / n;
    const meanIs = weeklyIs.reduce((s, v) => s + v, 0) / n;

    let sumXY = 0, sumX2 = 0, sumY2 = 0;
    for (let i = 0; i < n; i++) {
        const dx = weeklyCpc[i] - meanCpc;
        const dy = weeklyIs[i] - meanIs;
        sumXY += dx * dy;
        sumX2 += dx * dx;
        sumY2 += dy * dy;
    }

    const denom = Math.sqrt(sumX2 * sumY2);
    const r = denom > 0 ? sumXY / denom : 0;

    // CPC change over period
    const firstWeekCpc = weeklyCpc[0];
    const lastWeekCpc = weeklyCpc[weeklyCpc.length - 1];
    const cpcChangePct = firstWeekCpc > 0 ? ((lastWeekCpc - firstWeekCpc) / firstWeekCpc) * 100 : 0;

    // Negative correlation (IS down, CPC up) = competitive pressure
    if (r < -0.7) {
        addFlag('CPC_COMPETITIVE_PRESSURE', 'CA-D11', {
            campaign_id: cid,
            campaign_name: meta.name,
            metric_name: 'cpc_is_correlation',
            metric_value: r.toFixed(3),
            threshold: 'r < -0.7',
            severity: 'High',
            detail: `Strong negative CPC-IS correlation (r=${r.toFixed(3)}). CPC changed ${cpcChangePct.toFixed(1)}% ($${firstWeekCpc.toFixed(2)} → $${lastWeekCpc.toFixed(2)}) over ${n} weeks. IS declining as CPC rises — strong competitive pressure signal.`,
        });
    } else if (r < -0.5) {
        addFlag('CPC_COMPETITIVE_PRESSURE', 'CA-D11', {
            campaign_id: cid,
            campaign_name: meta.name,
            metric_name: 'cpc_is_correlation',
            metric_value: r.toFixed(3),
            threshold: 'r < -0.5',
            severity: 'Medium',
            detail: `Moderate negative CPC-IS correlation (r=${r.toFixed(3)}). CPC changed ${cpcChangePct.toFixed(1)}% ($${firstWeekCpc.toFixed(2)} → $${lastWeekCpc.toFixed(2)}) over ${n} weeks. Possible competitive pressure.`,
        });
    }
}

// ── CA-D13: KPI Impact Estimation ───────────────────────────────────
console.log('Running CA-D13: KPI impact estimation...');

for (const [cid, days] of Object.entries(campaignDays)) {
    const meta = campaignMeta[cid];
    const validDays = days.filter(d => d.is !== null);
    if (validDays.length < 30) continue;

    const totalDays = validDays.length;

    // Current IS (last 30d avg)
    const currentIS = windowAvg(validDays, 'is', Math.max(0, totalDays - 30), 30);
    // Historical IS (first 30d avg)
    const historicalIS = windowAvg(validDays, 'is', 0, 30);

    if (currentIS === null || historicalIS === null || currentIS >= historicalIS) continue;

    // Total metrics over evaluation period
    let totalImpressions = 0, totalClicks = 0, totalConversions = 0, totalValue = 0;
    for (const d of days) {
        totalImpressions += d.impressions;
        totalClicks += d.clicks;
        totalConversions += d.conversions;
        totalValue += d.conversions_value;
    }

    if (totalImpressions === 0 || currentIS === 0) continue;

    const isGap = historicalIS - currentIS;  // positive = IS declined

    // Estimated lost metrics
    const estLostImpressions = totalImpressions * (isGap / currentIS);
    const ctr = totalClicks / totalImpressions;
    const estLostClicks = estLostImpressions * ctr;
    const cvr = totalClicks > 0 ? totalConversions / totalClicks : 0;
    const estLostConversions = estLostClicks * cvr;
    const avgConvValue = totalConversions > 0 ? totalValue / totalConversions : 0;
    const estLostValue = estLostConversions * avgConvValue;

    // As percentage of total
    const convLossPct = totalConversions > 0 ? (estLostConversions / totalConversions) * 100 : 0;

    if (convLossPct > 5) {
        addFlag('KPI_IMPACT', 'CA-D13', {
            campaign_id: cid,
            campaign_name: meta.name,
            metric_name: 'estimated_conversion_loss_pct',
            metric_value: convLossPct.toFixed(1),
            threshold: convLossPct > 10 ? '10%' : '5%',
            severity: convLossPct > 10 ? 'High' : 'Medium',
            detail: `IS declined ${isGap.toFixed(1)}pp (${historicalIS.toFixed(1)}% → ${currentIS.toFixed(1)}%). Est. lost: ${Math.round(estLostImpressions)} impressions, ${Math.round(estLostClicks)} clicks, ${estLostConversions.toFixed(1)} conversions ($${estLostValue.toFixed(2)} value). Conv loss: ${convLossPct.toFixed(1)}% of campaign total.`,
        });
    }
}

// ── Write output ────────────────────────────────────────────────────
const outputDir = dirname(outputPath);
mkdirSync(outputDir, { recursive: true });

const columns = ['flag_type', 'check_id', 'campaign_id', 'campaign_name', 'ad_group_id', 'ad_group_name', 'keyword_text', 'metric_name', 'metric_value', 'threshold', 'delta', 'severity', 'detail'];

const csvLines = [columns.join(',')];
for (const f of flags) {
    const row = columns.map(col => {
        const val = String(f[col] ?? '');
        // Escape commas and quotes in CSV
        if (val.includes(',') || val.includes('"') || val.includes('\n')) {
            return `"${val.replace(/"/g, '""')}"`;
        }
        return val;
    });
    csvLines.push(row.join(','));
}

writeFileSync(outputPath, csvLines.join('\n') + '\n');

// ── Summary ─────────────────────────────────────────────────────────
const flagCounts = {};
for (const f of flags) {
    flagCounts[f.check_id] = (flagCounts[f.check_id] || 0) + 1;
}

console.log(`\n--- Results ---`);
console.log(`Total flags: ${flags.length}`);
for (const [check, count] of Object.entries(flagCounts).sort()) {
    console.log(`  ${check}: ${count} flags`);
}
console.log(`Output: ${outputPath}`);

console.log('\n__RESULTS_JSON__');
console.log(JSON.stringify({ total_flags: flags.length, by_check: flagCounts }));
