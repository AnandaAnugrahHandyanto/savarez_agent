#!/usr/bin/env node

/**
 * Search Term Auditor — quality + promotion + close-variant + PMax analysis.
 *
 * Produces tmp/search-term-flags.json keyed by diagnostic module (not by SOP bucket).
 * Covers ST-D01 to D05 (quality), ST-D17 to D19 (close variants), ST-D20 to D22 (promotion),
 * ST-D25, D26 (PMax). Coverage + n-gram diagnostics live in analyze-negatives.js.
 *
 * Portfolio bid strategies are resolved per campaign via lib.resolveBiddingStrategy()
 * before any threshold calc, so every flagged record carries target_source and
 * portfolio_name where applicable.
 */

import { writeFileSync, existsSync, statSync, mkdirSync, readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { config as dotenv } from 'dotenv';

import {
    findProjectRoot,
    loadCSV, loadConfig, f, num, norm, key3,
    parseCliArgs, parseBusinessContext, getCurrencySymbol,
    CHANNEL_TYPE_CODES, SKIP_TYPES, PMAX_TYPES, SHOPPING_TYPES,
    getCampaignType,
    loadPortfolioTargets, resolveBiddingStrategy,
    loadNegativeStatus, isTermExcluded
} from './lib.js';

// ── Bootstrap ──────────────────────────────────────────────────────

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = findProjectRoot(__dirname);
dotenv({ path: resolve(projectRoot, 'config/.env') });

const args = parseCliArgs(process.argv);
const campaignFilter = args['campaign'] || null;
const defaultOutput = resolve(projectRoot, '.claude/skills/search-term-auditor/tmp/search-term-flags.json');
const outputPath = args['output'] || defaultOutput;

const appConfig = loadConfig(projectRoot);
const sta = appConfig.searchTermAnalysis || {};

const includeExperiments = (args['include-experiments'] === true || args['include-experiments'] === 'true')
    || sta.includeExperiments === true;

const minCostForNeg = parseFloat(sta.minSpendToFlag ?? 20);
const conversionLagDays = parseInt(sta.conversionLagDays ?? 14, 10);
const excludeBranded = sta.excludeBrandedCampaigns ?? true;
const brandedCampaignNames = new Set(
    (sta.brandedCampaigns || []).map(n => n.toLowerCase().trim())
);
const biddingStrategyType = (sta.biddingStrategy || 'cpa').toLowerCase();
const inefficientCPAMult = parseFloat(sta.inefficientCPAMultiplier ?? 1.5);
const inefficientROASMult = parseFloat(sta.inefficientROASMultiplier ?? 0.7);
const minCostForInefficient = parseFloat(sta.minSpendForInefficient ?? 50);
const minClicksForInefficient = parseInt(sta.minClicksForInefficient ?? 3, 10);
const neverExcludeTerms = new Set((sta.protectedTerms?.neverExclude || []).map(t => norm(t)));

const { currency, currencySymbol } = getCurrencySymbol(appConfig);
const business = parseBusinessContext(projectRoot);
const { targetCPA, maxCPA, targetROAS } = business;

// ── Load CSVs ──────────────────────────────────────────────────────

const dataDir = resolve(projectRoot, 'context/google-ads/data');
const periodA = loadCSV(resolve(dataDir, 'search-terms-periodA.csv'));
const periodB = loadCSV(resolve(dataDir, 'search-terms-periodB.csv'));
const pmaxTerms = loadCSV(resolve(dataDir, 'pmax-search-terms.csv'));

// Try per-auditor files first, fall back to legacy names from /gads-context
let campaigns = loadCSV(resolve(dataDir, 'campaigns-settings.csv'));
if (campaigns.length === 0) campaigns = loadCSV(resolve(dataDir, 'campaigns.csv'));
const keywords = loadCSV(resolve(dataDir, 'keywords.csv'));

const portfolioTargets = loadPortfolioTargets(projectRoot);
const negatives = loadNegativeStatus(projectRoot);

// Self-learning decisions
const decisionsPath = resolve(projectRoot, 'context/analysis/search-term-decisions.json');
let decisions = { relevantTerms: [], rejectedNgrams: [] };
if (existsSync(decisionsPath)) {
    try { decisions = JSON.parse(readFileSync(decisionsPath, 'utf8')); } catch {}
}
const knownRelevant = new Set((decisions.relevantTerms || []).map(t => t.toLowerCase().trim()));

if (periodA.length === 0) {
    console.error('ERROR: search-terms-periodA.csv is empty or missing. Run pull-all.js first.');
    process.exit(1);
}

// Data age (mtime)
let dataAgeDays = 0;
const periodAPath = resolve(dataDir, 'search-terms-periodA.csv');
if (existsSync(periodAPath)) {
    dataAgeDays = Math.round((Date.now() - statSync(periodAPath).mtimeMs) / (1000 * 60 * 60 * 24));
}

// ── Campaign lookup with resolved bidding strategy ─────────────────

const campaignTypeMap = {};
const campaignBidding = {}; // campaign_name → resolved strategy object

for (const c of campaigns) {
    const name = f(c, 'campaign.name', 'campaign_name', 'name');
    if (!name) continue;
    const status = f(c, 'campaign.status', 'campaign_status');
    if (status === 'REMOVED') continue;
    if (!includeExperiments) {
        const expType = f(c, 'campaign.experiment_type', 'campaign_experiment_type');
        if (expType && expType !== 'BASE') continue;
    }
    const rawType = f(c, 'campaign.advertising_channel_type', 'campaign_advertising_channel_type', 'advertising_channel_type');
    campaignTypeMap[name] = CHANNEL_TYPE_CODES[String(rawType).trim()] || rawType || 'SEARCH';

    const resolved = resolveBiddingStrategy(
        c, portfolioTargets,
        { targetCPA: targetCPA || maxCPA, targetROAS },
        biddingStrategyType
    );
    campaignBidding[name] = resolved;
}

function biddingFor(name) {
    return campaignBidding[name] || {
        targetCpa: null, targetRoas: null,
        biddingMode: biddingStrategyType,
        strategyType: 'UNKNOWN',
        targetSource: 'none',
        portfolioName: '', portfolioResource: ''
    };
}

// ── Keyword set for duplicate/promotion checks ─────────────────────

const existingKeywords = new Set();
const existingKeywordsByAdGroup = new Set();
for (const kw of keywords) {
    const campaign = f(kw, 'campaign.name', 'campaign_name');
    const adGroup = f(kw, 'ad_group.name', 'ad_group_name');
    const text = norm(f(kw, 'ad_group_criterion.keyword.text', 'keyword.text', 'keyword_text', 'criteria', 'keyword'));
    if (!text) continue;
    existingKeywords.add(text);
    if (campaign && adGroup) existingKeywordsByAdGroup.add(key3(campaign, adGroup, text));
}

// ── Helpers ────────────────────────────────────────────────────────

function isBrandedCampaign(name) {
    const normalized = norm(name);
    if (brandedCampaignNames.size > 0) return brandedCampaignNames.has(normalized);
    return /branded/i.test(name) && !/non.?branded/i.test(name);
}

function aggregateTerms(rows) {
    const agg = new Map();
    for (const row of rows) {
        const campName = f(row, 'campaign.name', 'campaign_name');
        // Drop ended/removed campaigns. By default also drop experiments —
        // historical waste from experimental campaigns is not actionable. The
        // user can opt-in via --include-experiments / config.includeExperiments.
        const campStatus = f(row, 'campaign.status', 'campaign_status');
        if (campStatus === 'REMOVED') continue;
        if (!includeExperiments) {
            const expType = f(row, 'campaign.experiment_type', 'campaign_experiment_type');
            if (expType && expType !== 'BASE') continue;
        }
        if (campaignFilter && !campName.toLowerCase().includes(campaignFilter.toLowerCase())) continue;
        if (excludeBranded && isBrandedCampaign(campName)) continue;
        const campType = getCampaignType(row, campaignTypeMap);
        if (SKIP_TYPES.has(campType)) continue;

        const term = f(row, 'campaign_search_term_view.search_term', 'search_term');
        if (!term) continue;
        const adGroup = f(row, 'ad_group.name', 'ad_group_name');
        const networkType = f(row, 'segments.ad_network_type', 'ad_network_type') || 'SEARCH';

        const k = key3(campName, adGroup, term);
        const clicks = num(f(row, 'clicks', 'metrics.clicks'));
        const impressions = num(f(row, 'impressions', 'metrics.impressions'));
        const cost = num(f(row, 'cost', 'metrics.cost'));
        const conversions = num(f(row, 'conversions', 'metrics.conversions'));
        const convValue = num(f(row, 'conversions_value', 'metrics.conversions_value'));
        const searchMatchType = f(row, 'segments.search_term_match_type', 'search_term_match_type');

        if (agg.has(k)) {
            const a = agg.get(k);
            a.clicks += clicks; a.impressions += impressions; a.cost += cost;
            a.conversions += conversions; a.convValue += convValue;
            if (searchMatchType) a.matchTypes.add(String(searchMatchType).toUpperCase());
        } else {
            agg.set(k, {
                term, campaign: campName, adGroup, campaignType: campType, networkType,
                clicks, impressions, cost, conversions, convValue,
                matchTypes: new Set(searchMatchType ? [String(searchMatchType).toUpperCase()] : [])
            });
        }
    }
    // Convert matchTypes Set → Array, round cost
    for (const a of agg.values()) {
        a.matchTypes = Array.from(a.matchTypes);
    }
    return agg;
}

const termsA = aggregateTerms(periodA);
const termsB = aggregateTerms(periodB);
const pmaxAgg = aggregateTerms(pmaxTerms);

// ── Totals + classifications ───────────────────────────────────────

let totalSpend = 0;
let irrelevantSpend = 0;
let nonConvertingSpend = 0;
let convertingTermsCount = 0;
let convertingTermsAsKeyword = 0;

const nonConvertingTerms = [];
const underperformingTerms = [];
const irrelevantTerms = [];
const promotionCandidates = [];
const monitorTerms = [];

for (const [k, a] of termsA.entries()) {
    const { term, campaign, adGroup, campaignType, clicks, impressions, cost, conversions, convValue } = a;
    const cpa = conversions > 0 ? cost / conversions : null;
    const roas = cost > 0 && convValue > 0 ? convValue / cost : null;
    const bidding = biddingFor(campaign);
    const excluded = negatives.available ? isTermExcluded(negatives, campaign, adGroup, term) : false;
    const alreadyKeyword = existingKeywordsByAdGroup.has(key3(campaign, adGroup, term));
    const campType = campaignType;

    totalSpend += cost;

    // Base record with resolved targets
    const base = {
        term, campaign, adGroup, campaign_type: campType,
        clicks, impressions,
        cost: Math.round(cost * 100) / 100,
        conversions: Math.round(conversions * 100) / 100,
        conversion_value: Math.round(convValue * 100) / 100,
        cpa: cpa !== null ? Math.round(cpa * 100) / 100 : null,
        roas: roas !== null ? Math.round(roas * 100) / 100 : null,
        match_types: a.matchTypes,
        bidding_mode: bidding.biddingMode,
        strategy_type: bidding.strategyType,
        target_cpa: bidding.targetCpa,
        target_roas: bidding.targetRoas,
        target_source: bidding.targetSource,
        portfolio_name: bidding.portfolioName,
        excluded,
        already_keyword: alreadyKeyword
    };

    if (conversions > 0) {
        convertingTermsCount++;
        if (alreadyKeyword) convertingTermsAsKeyword++;

        // ST-D03: underperforming check — uses resolved target
        let isUnderperforming = false;
        const meetsMinimums = cost >= minCostForInefficient && clicks >= minClicksForInefficient;
        if (bidding.biddingMode === 'roas' && bidding.targetRoas) {
            const cutoff = bidding.targetRoas * inefficientROASMult;
            isUnderperforming = meetsMinimums && roas !== null && roas < cutoff;
            if (isUnderperforming) base.note = `roas_${(roas ?? 0).toFixed(2)}_below_${cutoff.toFixed(2)}`;
        } else if (bidding.biddingMode === 'cpa' && bidding.targetCpa) {
            const cutoff = bidding.targetCpa * inefficientCPAMult;
            isUnderperforming = meetsMinimums && cpa !== null && cpa > cutoff;
            if (isUnderperforming) base.note = `cpa_${(cpa ?? 0).toFixed(2)}_above_${cutoff.toFixed(2)}`;
        }

        if (isUnderperforming) underperformingTerms.push(base);

        // ST-D20: promotion candidate
        const withinTarget = bidding.biddingMode === 'roas'
            ? (bidding.targetRoas === null || (roas !== null && roas >= bidding.targetRoas))
            : (bidding.targetCpa === null || cpa <= bidding.targetCpa);

        if (!alreadyKeyword && !excluded && !isUnderperforming && withinTarget) {
            promotionCandidates.push(base);
        }
    } else if (cost >= minCostForNeg && !excluded) {
        // ST-D02: non-converting terms
        nonConvertingSpend += cost;
        if (!neverExcludeTerms.has(norm(term))) {
            nonConvertingTerms.push(base);
            // Classification as irrelevant is a Claude judgment (ST-D01); we mark high-cost non-converters for review
            if (!knownRelevant.has(norm(term))) {
                irrelevantSpend += cost;
                irrelevantTerms.push(base);
            }
        }
    } else if (impressions >= 50) {
        monitorTerms.push(base);
    }
}

// Sort + cap
nonConvertingTerms.sort((a, b) => b.cost - a.cost);
underperformingTerms.sort((a, b) => b.cost - a.cost);
irrelevantTerms.sort((a, b) => b.cost - a.cost);
promotionCandidates.sort((a, b) => b.conversions - a.conversions);
monitorTerms.sort((a, b) => b.impressions - a.impressions);

// ── ST-D05: trending terms (Period A vs Period B delta) ─────────────

const trendingTerms = [];
for (const [k, a] of termsA.entries()) {
    const b = termsB.get(k);
    const costA = a.cost;
    const costB = b?.cost || 0;
    if (costA < minCostForNeg) continue;
    // Flag term that went from near-zero spend in Period B to meaningful spend in Period A
    if (costB < 1 && costA >= minCostForNeg) {
        trendingTerms.push({
            term: a.term, campaign: a.campaign, adGroup: a.adGroup,
            campaign_type: a.campaignType,
            cost_period_a: Math.round(costA * 100) / 100,
            cost_period_b: Math.round(costB * 100) / 100,
            conversions_period_a: Math.round(a.conversions * 100) / 100,
            conversions_period_b: Math.round((b?.conversions || 0) * 100) / 100,
            direction: 'new'
        });
    }
}
trendingTerms.sort((a, b) => b.cost_period_a - a.cost_period_a);

// ── ST-D17 / D18 / D19: close variants ─────────────────────────────

// Build a map of keyword text → existing match types
const kwByText = new Map();
for (const kw of keywords) {
    const text = norm(f(kw, 'ad_group_criterion.keyword.text', 'keyword.text'));
    const mt = String(f(kw, 'ad_group_criterion.keyword.match_type', 'keyword_match_type', 'match_type') || '').toUpperCase();
    const adGroup = f(kw, 'ad_group.name', 'ad_group_name');
    const campaign = f(kw, 'campaign.name', 'campaign_name');
    if (!text) continue;
    if (!kwByText.has(text)) kwByText.set(text, []);
    kwByText.get(text).push({ campaign, adGroup, matchType: mt });
}

const driftCandidates = [];
const highSpendVariants = [];
for (const a of termsA.values()) {
    const mt = a.matchTypes[0] || '';
    const isVariant = mt.includes('CLOSE_VARIANT') || mt === 'NEAR_EXACT' || mt === 'CLOSE_VARIANT_EXACT' || mt === 'CLOSE_VARIANT_PHRASE';
    if (!isVariant) continue;

    const parentMatches = kwByText.get(norm(a.term)) || [];
    const parent = parentMatches.find(p => p.adGroup === a.adGroup) || parentMatches[0];
    if (!parent) continue;

    const cpa = a.conversions > 0 ? a.cost / a.conversions : null;
    const roas = a.cost > 0 && a.convValue > 0 ? a.convValue / a.cost : null;

    if (cpa === null && a.cost >= minCostForNeg) {
        driftCandidates.push({
            term: a.term, campaign: a.campaign, adGroup: a.adGroup,
            match_type: mt, parent_match_type: parent.matchType,
            cost: Math.round(a.cost * 100) / 100,
            conversions: Math.round(a.conversions * 100) / 100,
            cpa, roas
        });
    }
    if (a.cost >= minCostForInefficient) {
        highSpendVariants.push({
            term: a.term, campaign: a.campaign, adGroup: a.adGroup,
            match_type: mt,
            cost: Math.round(a.cost * 100) / 100,
            share_of_term_spend: null
        });
    }
}
driftCandidates.sort((a, b) => b.cost - a.cost);
highSpendVariants.sort((a, b) => b.cost - a.cost);

// ── Module 5: PMax ─────────────────────────────────────────────────

const pmaxNonConverting = [];
const pmaxUnderperforming = [];
const pmaxCategoriesByCampaign = new Map();
let pmaxBrandMatches = 0;
let pmaxTotalTerms = 0;
const searchOverlapCandidates = [];

// Build set of search-campaign terms for overlap check
const searchCampaignTerms = new Set();
for (const a of termsA.values()) {
    if (a.campaignType === 'SEARCH') searchCampaignTerms.add(norm(a.term));
}

const brandCheck = (appConfig?.googleAds?.brandName || business?.brandName || '').toLowerCase().trim();
const brandedCampListLower = Array.from(brandedCampaignNames);

for (const a of pmaxAgg.values()) {
    pmaxTotalTerms++;
    const bidding = biddingFor(a.campaign);
    const cpa = a.conversions > 0 ? a.cost / a.conversions : null;
    const roas = a.cost > 0 && a.convValue > 0 ? a.convValue / a.cost : null;

    const record = {
        term: a.term, campaign: a.campaign,
        cost: Math.round(a.cost * 100) / 100,
        conversions: Math.round(a.conversions * 100) / 100,
        cpa: cpa !== null ? Math.round(cpa * 100) / 100 : null,
        roas: roas !== null ? Math.round(roas * 100) / 100 : null,
        target_cpa: bidding.targetCpa, target_roas: bidding.targetRoas,
        target_source: bidding.targetSource, portfolio_name: bidding.portfolioName
    };

    if (a.conversions === 0 && a.cost >= minCostForNeg) {
        pmaxNonConverting.push(record);
    }
    if (a.conversions > 0) {
        if (bidding.biddingMode === 'roas' && bidding.targetRoas && roas !== null && roas < bidding.targetRoas * inefficientROASMult) {
            pmaxUnderperforming.push(record);
        } else if (bidding.biddingMode === 'cpa' && bidding.targetCpa && cpa !== null && cpa > bidding.targetCpa * inefficientCPAMult) {
            pmaxUnderperforming.push(record);
        }
    }

    // Brand query check
    if (brandCheck && norm(a.term).includes(brandCheck)) pmaxBrandMatches++;
    for (const branded of brandedCampListLower) {
        // Compare term tokens against branded campaign name tokens
        if (branded && branded.split(' ').some(tok => tok.length > 3 && norm(a.term).includes(tok))) {
            pmaxBrandMatches++;
            break;
        }
    }

    // Search overlap
    if (searchCampaignTerms.has(norm(a.term))) {
        searchOverlapCandidates.push({
            term: a.term, pmax_campaign: a.campaign,
            pmax_cost: Math.round(a.cost * 100) / 100,
            pmax_conversions: Math.round(a.conversions * 100) / 100
        });
    }
}

pmaxNonConverting.sort((a, b) => b.cost - a.cost);
pmaxUnderperforming.sort((a, b) => b.cost - a.cost);
searchOverlapCandidates.sort((a, b) => b.cost - a.cost);
const pmaxBrandQueryPct = pmaxTotalTerms > 0 ? Math.round((pmaxBrandMatches / pmaxTotalTerms) * 1000) / 10 : 0;

// ── ST-D22: coverage ratio ──────────────────────────────────────────

const coverageRatio = convertingTermsCount > 0
    ? Math.round((convertingTermsAsKeyword / convertingTermsCount) * 1000) / 10
    : null;

const irrelevantSpendPct = totalSpend > 0
    ? Math.round((irrelevantSpend / totalSpend) * 1000) / 10
    : 0;

// ── Build output (diagnostic-shaped) ───────────────────────────────

const summary = {
    meta: {
        generatedAt: new Date().toISOString(),
        dataAgeDays,
        currency, currencySymbol,
        conversionLagDays,
        periods: {
            main_days: null, // pull-all.js is the authority here; periodA CSV has the actual dates
        },
        thresholds: {
            minCostForNeg, minCostForInefficient, minClicksForInefficient,
            inefficientCPAMultiplier: inefficientCPAMult,
            inefficientROASMultiplier: inefficientROASMult,
            excludeBranded, biddingStrategyDefault: biddingStrategyType
        },
        business: {
            targetCPA: targetCPA || maxCPA || null,
            targetROAS: targetROAS || null,
            currencySymbol
        },
        negativeStatus: {
            available: negatives.available,
            source: negatives.source,
            linkAwareShared: negatives.linkAwareShared,
            warnings: negatives.warnings
        },
        counts: {
            totalTermsPeriodA: termsA.size,
            totalTermsPeriodB: termsB.size,
            pmaxTerms: pmaxTotalTerms,
            nonConverting: nonConvertingTerms.length,
            underperforming: underperformingTerms.length,
            irrelevant: irrelevantTerms.length,
            promotionCandidates: promotionCandidates.length,
            monitor: monitorTerms.length,
            trending: trendingTerms.length,
            driftVariants: driftCandidates.length,
            highSpendVariants: highSpendVariants.length,
            pmaxNonConverting: pmaxNonConverting.length,
            pmaxUnderperforming: pmaxUnderperforming.length,
            searchOverlap: searchOverlapCandidates.length
        }
    },
    quality: {
        irrelevantSpendPct,
        nonConvertingSpend: Math.round(nonConvertingSpend * 100) / 100,
        totalSpend: Math.round(totalSpend * 100) / 100,
        nonConvertingTerms,
        underperformingTerms,
        irrelevantTerms,
        trendingTerms,
        monitor: monitorTerms
    },
    promotion: {
        candidates: promotionCandidates,
        coverageRatio,
        convertingTermsTotal: convertingTermsCount,
        convertingTermsAsKeyword
    },
    closeVariants: {
        driftCandidates,
        highSpendVariants
    },
    pmaxAnalysis: {
        nonConvertingCategories: pmaxNonConverting,
        underperformingCategories: pmaxUnderperforming,
        brandQueryPct: pmaxBrandQueryPct,
        brandMatchCount: pmaxBrandMatches,
        searchOverlap: searchOverlapCandidates
    }
};

// Ensure output dir
mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(outputPath, JSON.stringify(summary, null, 2), 'utf8');

console.log(`✓ Search term flags written to: ${outputPath}`);
console.log(`  Terms (Period A / B): ${termsA.size} / ${termsB.size}`);
console.log(`  Non-converting: ${nonConvertingTerms.length}`);
console.log(`  Underperforming: ${underperformingTerms.length}`);
console.log(`  Promotion candidates: ${promotionCandidates.length}`);
console.log(`  Trending terms: ${trendingTerms.length}`);
console.log(`  PMax terms: ${pmaxTotalTerms} (non-conv ${pmaxNonConverting.length}, underperf ${pmaxUnderperforming.length})`);
console.log(`  Brand query % (PMax): ${pmaxBrandQueryPct}%`);
console.log(`  Irrelevant spend: ${currencySymbol}${irrelevantSpend.toFixed(2)} (${irrelevantSpendPct}% of ${currencySymbol}${totalSpend.toFixed(2)})`);

// Surface portfolio-resolved campaigns for auditor visibility
const portfolioCampaigns = Object.entries(campaignBidding)
    .filter(([, b]) => b.targetSource === 'portfolio')
    .map(([name, b]) => `  - ${name} → ${b.portfolioName} (tCPA=${b.targetCpa || '-'}, tROAS=${b.targetRoas || '-'})`);
if (portfolioCampaigns.length > 0) {
    console.log(`  Portfolio-resolved campaigns: ${portfolioCampaigns.length}`);
    for (const line of portfolioCampaigns.slice(0, 5)) console.log(line);
}
