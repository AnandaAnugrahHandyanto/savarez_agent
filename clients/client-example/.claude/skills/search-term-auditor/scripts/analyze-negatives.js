#!/usr/bin/env node

/**
 * Search Term Auditor — negative coverage + n-gram analysis.
 *
 * Produces tmp/negative-flags.json keyed by module:
 *   - coverage (ST-D06 to D12)  — negative keyword hygiene
 *   - ngrams   (ST-D13 to D16)  — waste at the n-gram level
 *
 * N-gram thresholds use targets resolved via lib.resolveBiddingStrategy()
 * so portfolio-attached campaigns classify against real targets rather than
 * computed averages. Every flagged n-gram carries target_source + portfolio_name.
 */

import { writeFileSync, existsSync, statSync, mkdirSync, readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { config as dotenv } from 'dotenv';

import {
    findProjectRoot,
    loadCSV, loadConfig, f, num, norm,
    parseCliArgs, parseBusinessContext, getCurrencySymbol,
    CHANNEL_TYPE_CODES, SKIP_TYPES, PMAX_TYPES,
    getCampaignType,
    loadPortfolioTargets, resolveBiddingStrategy,
    loadNegativeStatus
} from './lib.js';

// ── Bootstrap ──────────────────────────────────────────────────────

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = findProjectRoot(__dirname);
dotenv({ path: resolve(projectRoot, 'config/.env') });

const args = parseCliArgs(process.argv);
const campaignFilter = args['campaign'] || null;
const defaultOutput = resolve(projectRoot, '.claude/skills/search-term-auditor/tmp/negative-flags.json');
const outputPath = args['output'] || defaultOutput;

const appConfig = loadConfig(projectRoot);
const sta = appConfig.searchTermAnalysis || {};
const ngCfg = appConfig.ngramAnalysis || {};

const minImpressions = parseInt(ngCfg.minImpressions ?? 100, 10);
const minClicks = parseInt(ngCfg.minClicks ?? 25, 10);
const minDistinctTerms = parseInt(ngCfg.minDistinctTerms ?? 3, 10);
const nonConvertingMult = parseFloat(ngCfg.nonConvertingSpendMultiplier ?? 2.0);
const inefficientCPAMult = parseFloat(ngCfg.inefficientCPAMultiplier ?? 1.75);
const inefficientROASMult = parseFloat(ngCfg.inefficientROASMultiplier ?? 0.7);
const defaultAOV = parseFloat(ngCfg.defaultAOV ?? 0);
const extraStopwords = (ngCfg.stopwords || []).map(s => s.toLowerCase());
const biddingStrategyType = (String(ngCfg.biddingStrategy || sta.biddingStrategy || 'cpa').toLowerCase() === 'roas') ? 'roas' : 'cpa';

const excludeBranded = sta.excludeBrandedCampaigns ?? true;
const brandedCampaignNames = new Set((sta.brandedCampaigns || []).map(n => n.toLowerCase().trim()));

const includeExperiments = (args['include-experiments'] === true || args['include-experiments'] === 'true')
    || sta.includeExperiments === true;

// Manually-flagged routing terms — bypass the heuristic and force likely_routing=true.
const manualRoutingTerms = new Set(
    (sta.routingNegatives || []).map(t => String(t).toLowerCase().trim()).filter(Boolean)
);

const { currency, currencySymbol } = getCurrencySymbol(appConfig);
const business = parseBusinessContext(projectRoot);
const { targetCPA, maxCPA, targetROAS } = business;
const effectiveCPA = maxCPA || targetCPA;

// ── Load CSVs ──────────────────────────────────────────────────────

const dataDir = resolve(projectRoot, 'context/google-ads/data');
let ngramRows = loadCSV(resolve(dataDir, 'search-terms-ngram.csv'));
if (ngramRows.length === 0) {
    // Fallback to period A if dedicated n-gram file absent (e.g. legacy layout)
    ngramRows = loadCSV(resolve(dataDir, 'search-terms-periodA.csv'));
}
let campaigns = loadCSV(resolve(dataDir, 'campaigns-settings.csv'));
if (campaigns.length === 0) campaigns = loadCSV(resolve(dataDir, 'campaigns.csv'));

const portfolioTargets = loadPortfolioTargets(projectRoot);
const negatives = loadNegativeStatus(projectRoot);

const decisionsPath = resolve(projectRoot, 'context/analysis/search-term-decisions.json');
let decisions = { relevantTerms: [], rejectedNgrams: [] };
if (existsSync(decisionsPath)) {
    try { decisions = JSON.parse(readFileSync(decisionsPath, 'utf8')); } catch {}
}
const rejectedNgrams = new Set((decisions.rejectedNgrams || []).map(t => t.toLowerCase().trim()));

if (ngramRows.length === 0) {
    console.error('ERROR: search-terms-ngram.csv is empty or missing. Run pull-all.js first.');
    process.exit(1);
}

// Data age
let dataAgeDays = 0;
const srcPath = resolve(dataDir, 'search-terms-ngram.csv');
if (existsSync(srcPath)) {
    dataAgeDays = Math.round((Date.now() - statSync(srcPath).mtimeMs) / (1000 * 60 * 60 * 24));
}

// ── Campaign bidding resolution ─────────────────────────────────────

const campaignTypeMap = {};
const campaignBidding = {};

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
        { targetCPA: effectiveCPA, targetROAS },
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

function isBrandedCampaign(name) {
    const normalized = norm(name);
    if (brandedCampaignNames.size > 0) return brandedCampaignNames.has(normalized);
    return /branded/i.test(name) && !/non.?branded/i.test(name);
}

// ── Stop words ─────────────────────────────────────────────────────

const DEFAULT_STOPWORDS = new Set([
    'a', 'an', 'the', 'and', 'or', 'for', 'to', 'in', 'on', 'with',
    'of', 'is', 'it', 'as', 'at', 'be', 'by', 'from', 'this', 'that',
    'was', 'are', 'i', 'my', 'me', 'we', 'our', 'you', 'your', 'its',
    'do', 'does', 'can', 'get', 'use', 'using', 'used', 'how', 'what',
    'where', 'when', 'which', 'who', 'will', 'so', 'if', 'than', 'more',
    ...extraStopwords
]);

function tokenize(text) {
    return text.toLowerCase()
        .replace(/[^a-z0-9\s'-]/g, ' ')
        .split(/\s+/)
        .filter(t => t.length >= 2 && !DEFAULT_STOPWORDS.has(t));
}

function extractNgrams(text) {
    const tokens = tokenize(text);
    const out = [];
    for (const token of tokens) out.push({ ngram: token, type: '1-gram' });
    for (let i = 0; i < tokens.length - 1; i++) {
        out.push({ ngram: `${tokens[i]} ${tokens[i + 1]}`, type: '2-gram' });
    }
    return out;
}

// ── Module 3: N-gram analysis (ST-D13 to D16) ──────────────────────

const ngramMap = new Map();
let totalAccountCost = 0;
let totalConversions = 0;
let totalConvValue = 0;
let eligibleRowCount = 0;
const warnings = [];

const termsByCost = []; // for volume concentration

for (const row of ngramRows) {
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

    const clicks = num(f(row, 'clicks', 'metrics.clicks'));
    const impressions = num(f(row, 'impressions', 'metrics.impressions'));
    const cost = num(f(row, 'cost', 'metrics.cost'));
    const conversions = num(f(row, 'conversions', 'metrics.conversions'));
    const convValue = num(f(row, 'conversions_value', 'metrics.conversions_value'));

    totalAccountCost += cost;
    totalConversions += conversions;
    totalConvValue += convValue;
    eligibleRowCount++;
    termsByCost.push({ term, campaign: campName, cost, conversions });

    for (const { ngram, type } of extractNgrams(term)) {
        if (!ngramMap.has(ngram)) {
            ngramMap.set(ngram, {
                ngram, type,
                impressions: 0, clicks: 0, cost: 0, conversions: 0, convValue: 0,
                distinctTerms: new Set(),
                exampleTerms: [],
                campaignCost: new Map(),
                campaignType: new Set()
            });
        }
        const e = ngramMap.get(ngram);
        e.impressions += impressions;
        e.clicks += clicks;
        e.cost += cost;
        e.conversions += conversions;
        e.convValue += convValue;
        e.distinctTerms.add(term);
        e.campaignType.add(campType);
        if (e.exampleTerms.length < 5 && !e.exampleTerms.includes(term)) e.exampleTerms.push(term);
        if (campName) {
            e.campaignCost.set(campName, (e.campaignCost.get(campName) || 0) + cost);
        }
    }
}

const inferredAOV = totalConversions > 0 ? totalConvValue / totalConversions : null;
const activeAOV = (inferredAOV && inferredAOV > 0) ? inferredAOV : (defaultAOV > 0 ? defaultAOV : null);

if (biddingStrategyType === 'roas' && !targetROAS) warnings.push('targetROAS not set; inefficient ROAS bucket empty.');
if (biddingStrategyType === 'roas' && !activeAOV) warnings.push('AOV unavailable (no conv value, no defaultAOV); non-converting ROAS threshold cannot be computed.');
if (biddingStrategyType === 'cpa' && !effectiveCPA) warnings.push('targetCPA not set; non-converting classification falls back to cost > 0, inefficient CPA bucket empty.');

// Build set of high-performing n-grams (appear in terms meeting their campaign's target)
const highPerformingNgrams = new Set();
for (const row of termsByCost) {
    if (row.conversions <= 0) continue;
    const bidding = biddingFor(row.campaign);
    let passes = true;
    if (bidding.biddingMode === 'roas' && bidding.targetRoas) {
        const roas = row.cost > 0 ? (row.conversions > 0 ? 0 : 0) : 0;
        // we don't have convValue at this granularity; skip soft flag
        passes = row.conversions > 0;
    } else if (bidding.biddingMode === 'cpa' && bidding.targetCpa) {
        const cpa = row.conversions > 0 ? row.cost / row.conversions : null;
        passes = cpa !== null && cpa <= bidding.targetCpa;
    }
    if (passes) {
        for (const { ngram } of extractNgrams(row.term)) highPerformingNgrams.add(ngram);
    }
}

function resolveDominantCampaign(entry) {
    let dominant = null;
    let maxCost = -1;
    for (const [camp, cost] of entry.campaignCost.entries()) {
        if (cost > maxCost) { maxCost = cost; dominant = camp; }
    }
    return dominant;
}

const nonConvertingNgrams = [];
const inefficientNgrams = [];
const safeListConflicts = [];

for (const entry of ngramMap.values()) {
    if (entry.impressions < minImpressions) continue;
    if (entry.clicks < minClicks) continue;
    if (entry.distinctTerms.size < minDistinctTerms) continue;
    if (rejectedNgrams.has(entry.ngram.toLowerCase())) continue;

    const cpa = entry.conversions > 0 ? entry.cost / entry.conversions : null;
    const roas = entry.cost > 0 && entry.convValue > 0 ? entry.convValue / entry.cost : null;

    const dominantCamp = resolveDominantCampaign(entry);
    const bidding = biddingFor(dominantCamp);

    const record = {
        ngram: entry.ngram,
        type: entry.type,
        impressions: Math.round(entry.impressions),
        clicks: Math.round(entry.clicks),
        cost: Math.round(entry.cost * 100) / 100,
        conversions: Math.round(entry.conversions * 100) / 100,
        conversion_value: Math.round(entry.convValue * 100) / 100,
        cpa: cpa !== null ? Math.round(cpa * 100) / 100 : null,
        roas: roas !== null ? Math.round(roas * 100) / 100 : null,
        distinct_terms: entry.distinctTerms.size,
        example_terms: entry.exampleTerms,
        campaign_types: Array.from(entry.campaignType),
        dominant_campaign: dominantCamp,
        bidding_mode: bidding.biddingMode,
        target_cpa: bidding.targetCpa,
        target_roas: bidding.targetRoas,
        target_source: bidding.targetSource,
        portfolio_name: bidding.portfolioName
    };

    if (highPerformingNgrams.has(entry.ngram)) {
        safeListConflicts.push({ ...record, reason: 'appears_in_high_performing_terms' });
        continue;
    }

    // Classification — dominant campaign's resolved strategy + target
    if (bidding.biddingMode === 'roas') {
        if (entry.conversions === 0 && activeAOV !== null && entry.cost > activeAOV * nonConvertingMult) {
            nonConvertingNgrams.push(record);
        } else if (entry.conversions > 0 && bidding.targetRoas !== null && roas !== null && roas < bidding.targetRoas * inefficientROASMult) {
            inefficientNgrams.push(record);
        }
    } else {
        if (entry.conversions === 0 && bidding.targetCpa !== null && entry.cost > bidding.targetCpa * nonConvertingMult) {
            nonConvertingNgrams.push(record);
        } else if (entry.conversions === 0 && bidding.targetCpa === null && entry.cost > 0) {
            nonConvertingNgrams.push(record);
        } else if (entry.conversions > 0 && bidding.targetCpa !== null && cpa !== null && cpa > bidding.targetCpa * inefficientCPAMult) {
            inefficientNgrams.push(record);
        }
    }
}

nonConvertingNgrams.sort((a, b) => b.cost - a.cost);
inefficientNgrams.sort((a, b) => b.cost - a.cost);
safeListConflicts.sort((a, b) => b.cost - a.cost);

// Volume concentration — top 5 n-grams share of waste
const allFlaggedCost = [...nonConvertingNgrams, ...inefficientNgrams].reduce((s, r) => s + r.cost, 0);
const topN = [...nonConvertingNgrams, ...inefficientNgrams].slice(0, 5);
const topNCost = topN.reduce((s, r) => s + r.cost, 0);
const volumeConcentrationPct = allFlaggedCost > 0
    ? Math.round((topNCost / allFlaggedCost) * 1000) / 10
    : 0;

// ── Module 2: Negative Keyword Coverage (ST-D06 to D12) ────────────

const coverageFlags = {
    campaignsWithoutNegatives: [],
    campaignsWithoutSharedLists: [],
    negativeConflicts: [],
    repeatedAdGroupNegatives: [],
    repeatedCampaignNegatives: [],
    legacyModifiedBroad: [],
    catalogGaps: [] // Claude-computed downstream
};

// Build campaign → has-negatives map
const campaignsWithCampaignNegs = new Set();
for (const r of negatives.coverage.campaignLevel) {
    if (r.campaign) campaignsWithCampaignNegs.add(r.campaign);
}
const campaignsWithAdGroupNegs = new Set();
for (const r of negatives.coverage.adGroupLevel) {
    if (r.campaign) campaignsWithAdGroupNegs.add(r.campaign);
}
const campaignsWithSharedLinks = new Set(negatives.campaignSharedLinks ? negatives.campaignSharedLinks.keys() : []);

// Only consider search + pmax campaigns
const activeCampaigns = [];
for (const c of campaigns) {
    const name = f(c, 'campaign.name', 'campaign_name');
    const rawType = f(c, 'campaign.advertising_channel_type', 'campaign_advertising_channel_type');
    const type = (CHANNEL_TYPE_CODES[String(rawType).trim()] || rawType || 'SEARCH').toUpperCase();
    if (type === 'SEARCH' || PMAX_TYPES.has(type)) {
        activeCampaigns.push({ name: norm(name), display: name, type });
    }
}

for (const c of activeCampaigns) {
    const hasAny = campaignsWithCampaignNegs.has(c.name)
        || campaignsWithAdGroupNegs.has(c.name)
        || campaignsWithSharedLinks.has(c.name);
    if (!hasAny) {
        coverageFlags.campaignsWithoutNegatives.push({ campaign: c.display, campaign_type: c.type });
    }
    if (!campaignsWithSharedLinks.has(c.name)) {
        coverageFlags.campaignsWithoutSharedLists.push({ campaign: c.display, campaign_type: c.type });
    }
}

// Repeated ad-group negatives (same term across multiple AGs in same campaign)
const adGroupTermCounts = new Map();
for (const r of negatives.coverage.adGroupLevel) {
    if (!r.campaign || !r.adGroup || !r.term) continue;
    const key = `${r.campaign}|||${r.term}|||${r.matchType}`;
    if (!adGroupTermCounts.has(key)) {
        adGroupTermCounts.set(key, {
            campaign: r.campaign, term: r.term, match_type: r.matchType, ad_groups: new Set()
        });
    }
    adGroupTermCounts.get(key).ad_groups.add(r.adGroup);
}
for (const v of adGroupTermCounts.values()) {
    if (v.ad_groups.size >= 3) {
        coverageFlags.repeatedAdGroupNegatives.push({
            campaign: v.campaign, term: v.term, match_type: v.match_type,
            ad_group_count: v.ad_groups.size,
            ad_groups: Array.from(v.ad_groups).slice(0, 10)
        });
    }
}

// Repeated campaign negatives (same term across multiple campaigns)
const campaignTermCounts = new Map();
for (const r of negatives.coverage.campaignLevel) {
    if (!r.term) continue;
    const key = `${r.term}|||${r.matchType}`;
    if (!campaignTermCounts.has(key)) {
        campaignTermCounts.set(key, { term: r.term, match_type: r.matchType, campaigns: new Set() });
    }
    campaignTermCounts.get(key).campaigns.add(r.campaign || '(account)');
}
for (const v of campaignTermCounts.values()) {
    if (v.campaigns.size >= 3) {
        coverageFlags.repeatedCampaignNegatives.push({
            term: v.term, match_type: v.match_type,
            campaign_count: v.campaigns.size,
            campaigns: Array.from(v.campaigns).slice(0, 10)
        });
    }
}

// Legacy modified broad (+word +word pattern)
const isLegacyModifiedBroad = t => /\+\w+/.test(t);
const seenLegacy = new Set();
for (const src of [negatives.coverage.campaignLevel, negatives.coverage.adGroupLevel]) {
    for (const r of src) {
        if (isLegacyModifiedBroad(r.term) && !seenLegacy.has(r.term)) {
            seenLegacy.add(r.term);
            coverageFlags.legacyModifiedBroad.push({
                term: r.term, campaign: r.campaign, match_type: r.matchType
            });
        }
    }
}
for (const rows of negatives.coverage.sharedListRows || []) {
    if (isLegacyModifiedBroad(rows.term) && !seenLegacy.has(rows.term)) {
        seenLegacy.add(rows.term);
        coverageFlags.legacyModifiedBroad.push({
            term: rows.term, shared_set: rows.setName, match_type: rows.matchType
        });
    }
}

// ── Routing detection (ST-D09 / D10 false-positive guard) ──────────
//
// A negative repeated across multiple campaigns (or ad groups) often LOOKS like
// a consolidation candidate but is actually intentional traffic routing — e.g.
// excluding "beslag" from door campaigns to push hardware queries into a
// hardware campaign. Promoting such negatives to a shared list breaks the
// routing in every linked campaign.
//
// Heuristic: for each candidate, check whether the negative-term tokens appear
// as positive keywords or converting search terms in OTHER (non-flagged)
// campaigns or ad groups. If yes → likely intentional routing. We annotate
// the entry with `likely_routing` + evidence so downstream scoring and the
// optimizer can skip these rather than mass-consolidate them.

const activeKeywordRows = loadCSV(resolve(dataDir, 'keywords-active.csv'));

// Per-campaign positive-keyword tokens
//   campaignKeywordTokens: Map<campaign_norm, Array<{text, tokens:Set, campaign, adGroup, adGroupNorm}>>
const campaignKeywordTokens = new Map();
for (const kw of activeKeywordRows) {
    const camp = f(kw, 'campaign.name', 'campaign_name');
    const adGroup = f(kw, 'ad_group.name', 'ad_group_name');
    const text = f(kw, 'ad_group_criterion.keyword.text', 'keyword.text', 'keyword_text');
    if (!camp || !text) continue;
    const status = f(kw, 'ad_group_criterion.status', 'status');
    if (status === 'PAUSED' || status === 'REMOVED') continue;
    const campNorm = norm(camp);
    if (!campaignKeywordTokens.has(campNorm)) campaignKeywordTokens.set(campNorm, []);
    campaignKeywordTokens.get(campNorm).push({
        text: String(text).toLowerCase(),
        tokens: new Set(tokenize(text)),
        campaign: camp,
        adGroup: adGroup || '',
        adGroupNorm: norm(adGroup || '')
    });
}

// Per-campaign converting search terms (from n-gram window)
//   campaignConvertingTerms: Map<campaign_norm, Array<{text, tokens, campaign, adGroup, adGroupNorm, conversions}>>
const campaignConvertingTerms = new Map();
for (const row of ngramRows) {
    const conv = num(f(row, 'conversions', 'metrics.conversions'));
    if (conv <= 0) continue;
    const camp = f(row, 'campaign.name', 'campaign_name');
    const adGroup = f(row, 'ad_group.name', 'ad_group_name');
    const text = f(row, 'campaign_search_term_view.search_term', 'search_term');
    if (!camp || !text) continue;
    const campNorm = norm(camp);
    if (!campaignConvertingTerms.has(campNorm)) campaignConvertingTerms.set(campNorm, []);
    campaignConvertingTerms.get(campNorm).push({
        text: String(text).toLowerCase(),
        tokens: new Set(tokenize(text)),
        campaign: camp,
        adGroup: adGroup || '',
        adGroupNorm: norm(adGroup || ''),
        conversions: conv
    });
}

// Token overlap test — exact token match OR negative token is a substring of a
// keyword/ST text (catches compound words like "schuifdeurbeslag" containing "beslag").
function termMatchesTokens(termTokens, candidateText, candidateTokens) {
    for (const t of termTokens) {
        if (candidateTokens.has(t)) return t;
        if (t.length >= 3 && candidateText.includes(t)) return t;
    }
    return null;
}

// scope: 'campaign'  → flaggedCampaigns is a Set<campaign_norm>; check OTHER campaigns.
// scope: 'ad_group'  → within a single campaign, flaggedAdGroups is Set<adGroup_norm>;
//                       check OTHER ad groups in the SAME campaign.
function detectRouting(term, scope, opts) {
    const termLower = String(term).toLowerCase();
    if (manualRoutingTerms.has(termLower)) {
        return { likely_routing: true, evidence: { reason: 'manual_config' } };
    }
    const negTokens = tokenize(term).filter(t => t.length >= 3);
    if (negTokens.length === 0) return { likely_routing: false };

    if (scope === 'campaign') {
        const flagged = opts.flaggedCampaigns;
        // Active keywords in non-flagged campaigns
        for (const [campNorm, kwList] of campaignKeywordTokens.entries()) {
            if (flagged.has(campNorm)) continue;
            for (const kw of kwList) {
                const matchedToken = termMatchesTokens(negTokens, kw.text, kw.tokens);
                if (matchedToken) {
                    return {
                        likely_routing: true,
                        evidence: {
                            reason: 'positive_keyword_in_other_campaign',
                            other_campaign: kw.campaign,
                            ad_group: kw.adGroup,
                            keyword: kw.text,
                            matched_token: matchedToken
                        }
                    };
                }
            }
        }
        // Converting search terms in non-flagged campaigns
        for (const [campNorm, stList] of campaignConvertingTerms.entries()) {
            if (flagged.has(campNorm)) continue;
            for (const st of stList) {
                const matchedToken = termMatchesTokens(negTokens, st.text, st.tokens);
                if (matchedToken) {
                    return {
                        likely_routing: true,
                        evidence: {
                            reason: 'converting_search_term_in_other_campaign',
                            other_campaign: st.campaign,
                            ad_group: st.adGroup,
                            search_term: st.text,
                            conversions: Math.round(st.conversions * 100) / 100,
                            matched_token: matchedToken
                        }
                    };
                }
            }
        }
        return { likely_routing: false };
    }

    if (scope === 'ad_group') {
        const campNorm = opts.campaignNorm;
        const flaggedAGs = opts.flaggedAdGroups;
        // Active keywords in non-flagged ad groups within the same campaign
        const kwList = campaignKeywordTokens.get(campNorm) || [];
        for (const kw of kwList) {
            if (flaggedAGs.has(kw.adGroupNorm)) continue;
            const matchedToken = termMatchesTokens(negTokens, kw.text, kw.tokens);
            if (matchedToken) {
                return {
                    likely_routing: true,
                    evidence: {
                        reason: 'positive_keyword_in_other_ad_group',
                        ad_group: kw.adGroup,
                        keyword: kw.text,
                        matched_token: matchedToken
                    }
                };
            }
        }
        const stList = campaignConvertingTerms.get(campNorm) || [];
        for (const st of stList) {
            if (flaggedAGs.has(st.adGroupNorm)) continue;
            const matchedToken = termMatchesTokens(negTokens, st.text, st.tokens);
            if (matchedToken) {
                return {
                    likely_routing: true,
                    evidence: {
                        reason: 'converting_search_term_in_other_ad_group',
                        ad_group: st.adGroup,
                        search_term: st.text,
                        conversions: Math.round(st.conversions * 100) / 100,
                        matched_token: matchedToken
                    }
                };
            }
        }
        return { likely_routing: false };
    }

    return { likely_routing: false };
}

// Annotate ST-D10 candidates (campaign-level repeats)
for (const entry of coverageFlags.repeatedCampaignNegatives) {
    const flagged = new Set(entry.campaigns.map(c => norm(c)));
    const result = detectRouting(entry.term, 'campaign', { flaggedCampaigns: flagged });
    entry.likely_routing = result.likely_routing;
    if (result.evidence) entry.routing_evidence = result.evidence;
}

// Annotate ST-D09 candidates (ad-group-level repeats inside a campaign)
for (const entry of coverageFlags.repeatedAdGroupNegatives) {
    const flaggedAGs = new Set((entry.ad_groups || []).map(g => norm(g)));
    const result = detectRouting(entry.term, 'ad_group', {
        campaignNorm: norm(entry.campaign),
        flaggedAdGroups: flaggedAGs
    });
    entry.likely_routing = result.likely_routing;
    if (result.evidence) entry.routing_evidence = result.evidence;
}

if (activeKeywordRows.length === 0) {
    warnings.push('keywords-active.csv missing or empty; ST-D09/D10 routing detection ran without positive-keyword evidence (false positives may pass through). Run pull-all.js to refresh.');
}

// Negative conflicts: negative blocks an active keyword
// Check if any negative term matches a keyword text in the same scope
const keywords = loadCSV(resolve(dataDir, 'keywords.csv'));
const keywordByAdGroupTerm = new Map();
const keywordByCampaignTerm = new Map();
for (const kw of keywords) {
    const text = norm(f(kw, 'ad_group_criterion.keyword.text', 'keyword.text'));
    const campaign = norm(f(kw, 'campaign.name', 'campaign_name'));
    const adGroup = norm(f(kw, 'ad_group.name', 'ad_group_name'));
    const status = f(kw, 'ad_group_criterion.status', 'status');
    if (!text || status === 'PAUSED' || status === 'REMOVED') continue;
    if (campaign && adGroup) {
        keywordByAdGroupTerm.set(`${campaign}|||${adGroup}|||${text}`, { text, campaign: f(kw, 'campaign.name'), adGroup: f(kw, 'ad_group.name') });
    }
    if (campaign) {
        if (!keywordByCampaignTerm.has(`${campaign}|||${text}`)) keywordByCampaignTerm.set(`${campaign}|||${text}`, []);
        keywordByCampaignTerm.get(`${campaign}|||${text}`).push({ text, campaign: f(kw, 'campaign.name'), adGroup: f(kw, 'ad_group.name') });
    }
}

// Simple exact-text match check (phrase/broad matching is fuzzy — we flag exact overlaps only)
for (const r of negatives.coverage.adGroupLevel) {
    const k = `${r.campaign}|||${r.adGroup}|||${r.term}`;
    if (keywordByAdGroupTerm.has(k)) {
        const kw = keywordByAdGroupTerm.get(k);
        coverageFlags.negativeConflicts.push({
            scope: 'ad_group', negative_term: r.term, negative_match_type: r.matchType,
            blocks_keyword: kw.text, campaign: kw.campaign, ad_group: kw.adGroup
        });
    }
}
for (const r of negatives.coverage.campaignLevel) {
    const matches = keywordByCampaignTerm.get(`${r.campaign}|||${r.term}`) || [];
    for (const kw of matches) {
        coverageFlags.negativeConflicts.push({
            scope: 'campaign', negative_term: r.term, negative_match_type: r.matchType,
            blocks_keyword: kw.text, campaign: kw.campaign, ad_group: kw.adGroup
        });
    }
}

// List staleness — shared lists not updated recently
const listStaleness = {}; // we don't have modified timestamps in the current GAQL; leave empty with warning
if (negatives.sharedSets.size === 0) {
    warnings.push('No shared negative lists found; ST-D15 staleness check cannot be evaluated.');
}

// ── Build output ───────────────────────────────────────────────────

const summary = {
    meta: {
        generatedAt: new Date().toISOString(),
        dataAgeDays,
        currency, currencySymbol,
        totalAccountCost: Math.round(totalAccountCost * 100) / 100,
        activeBiddingStrategy: biddingStrategyType,
        activeAOV: activeAOV ? Math.round(activeAOV * 100) / 100 : null,
        thresholds: {
            minImpressions, minClicks, minDistinctTerms,
            nonConvertingSpendMultiplier: nonConvertingMult,
            inefficientCPAMultiplier: inefficientCPAMult,
            inefficientROASMultiplier: inefficientROASMult
        },
        negativeStatus: {
            available: negatives.available,
            source: negatives.source,
            linkAwareShared: negatives.linkAwareShared,
            warnings: negatives.warnings
        },
        counts: {
            eligibleNgramRows: eligibleRowCount,
            ngramCandidatesTotal: ngramMap.size,
            nonConverting: nonConvertingNgrams.length,
            inefficient: inefficientNgrams.length,
            safeListConflicts: safeListConflicts.length,
            coverageCampaignsMissing: coverageFlags.campaignsWithoutNegatives.length,
            coverageSharedListMissing: coverageFlags.campaignsWithoutSharedLists.length,
            negativeConflicts: coverageFlags.negativeConflicts.length,
            repeatedAdGroup: coverageFlags.repeatedAdGroupNegatives.length,
            repeatedAdGroupRouting: coverageFlags.repeatedAdGroupNegatives.filter(e => e.likely_routing).length,
            repeatedAdGroupConsolidatable: coverageFlags.repeatedAdGroupNegatives.filter(e => !e.likely_routing).length,
            repeatedCampaign: coverageFlags.repeatedCampaignNegatives.length,
            repeatedCampaignRouting: coverageFlags.repeatedCampaignNegatives.filter(e => e.likely_routing).length,
            repeatedCampaignConsolidatable: coverageFlags.repeatedCampaignNegatives.filter(e => !e.likely_routing).length,
            legacyModifiedBroad: coverageFlags.legacyModifiedBroad.length
        },
        warnings
    },
    coverage: coverageFlags,
    ngrams: {
        nonConverting: nonConvertingNgrams,
        inefficient: inefficientNgrams,
        safeListConflicts,
        listStaleness,
        volumeConcentration: {
            topShareOfFlaggedSpendPct: volumeConcentrationPct,
            topItems: topN.map(r => ({
                ngram: r.ngram, cost: r.cost,
                distinct_terms: r.distinct_terms
            }))
        }
    }
};

mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(outputPath, JSON.stringify(summary, null, 2), 'utf8');

console.log(`✓ Negative flags written to: ${outputPath}`);
console.log(`  Eligible n-gram rows: ${eligibleRowCount}`);
console.log(`  N-gram candidates: ${ngramMap.size} (non-conv ${nonConvertingNgrams.length}, inefficient ${inefficientNgrams.length}, safe-list conflicts ${safeListConflicts.length})`);
console.log(`  Coverage gaps: ${coverageFlags.campaignsWithoutNegatives.length} without negatives, ${coverageFlags.campaignsWithoutSharedLists.length} without shared lists`);
{
    const agRouting = coverageFlags.repeatedAdGroupNegatives.filter(e => e.likely_routing).length;
    const campRouting = coverageFlags.repeatedCampaignNegatives.filter(e => e.likely_routing).length;
    console.log(`  Repeated: ${coverageFlags.repeatedAdGroupNegatives.length} AG (${agRouting} routing) / ${coverageFlags.repeatedCampaignNegatives.length} campaign (${campRouting} routing) / ${coverageFlags.legacyModifiedBroad.length} legacy +modified`);
}
console.log(`  Negative conflicts (exact text): ${coverageFlags.negativeConflicts.length}`);
if (warnings.length) {
    console.log('  Warnings:');
    for (const w of warnings) console.log(`    - ${w}`);
}
