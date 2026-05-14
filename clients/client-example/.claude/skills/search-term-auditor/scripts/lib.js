/**
 * Shared utilities for search-term-auditor scripts.
 *
 * Extracted from the previous analyze-terms.js and ngram-analysis.js. Adds
 * first-class portfolio bid strategy resolution per PRD §2 decision 14.
 */

import { readFileSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { parse } from 'csv-parse/sync';

// ── Path helpers ────────────────────────────────────────────────────

export function findProjectRoot(startDir) {
    let dir = startDir;
    while (dir !== '/' && !existsSync(resolve(dir, 'config'))) {
        dir = resolve(dir, '..');
    }
    return dir;
}

// ── CSV + field + numeric utilities ─────────────────────────────────

export function loadCSV(filePath) {
    if (!existsSync(filePath)) return [];
    try {
        const content = readFileSync(filePath, 'utf8');
        return parse(content, { columns: true, skip_empty_lines: true, trim: true });
    } catch (e) {
        console.error(`Warning: Could not parse ${filePath}: ${e.message}`);
        return [];
    }
}

export function f(row, ...names) {
    for (const name of names) {
        if (row[name] !== undefined && row[name] !== '') return row[name];
    }
    return '';
}

export function num(val) {
    if (val === null || val === undefined || val === '') return 0;
    const n = parseFloat(String(val).replace(/,/g, ''));
    return isNaN(n) ? 0 : n;
}

export function norm(val) {
    return String(val || '').trim().toLowerCase().replace(/\s+/g, ' ');
}

export function key2(a, b) {
    return `${norm(a)}|||${norm(b)}`;
}

export function key3(a, b, c) {
    return `${norm(a)}|||${norm(b)}|||${norm(c)}`;
}

// ── Config loader ───────────────────────────────────────────────────

export function loadConfig(projectRoot) {
    const configPath = resolve(projectRoot, 'config/ads-context.config.json');
    if (!existsSync(configPath)) return {};
    try {
        return JSON.parse(readFileSync(configPath, 'utf8'));
    } catch {
        return {};
    }
}

// ── Currency ────────────────────────────────────────────────────────

export const CURRENCY_SYMBOLS = {
    USD: '$', EUR: '€', GBP: '£', CAD: 'CA$', AUD: 'A$', JPY: '¥',
    CHF: 'CHF', NZD: 'NZ$', SEK: 'kr', NOK: 'kr', DKK: 'kr',
    PLN: 'zł', BRL: 'R$', MXN: 'MX$', INR: '₹', ZAR: 'R'
};

export function getCurrencySymbol(config) {
    const currency = (config?.googleAds?.currency || 'USD').toUpperCase();
    return { currency, currencySymbol: CURRENCY_SYMBOLS[currency] || currency };
}

// ── Business context (CPA/ROAS from business.md) ────────────────────

export function parseBusinessContext(projectRoot) {
    const businessPath = resolve(projectRoot, 'context/business.md');
    if (!existsSync(businessPath)) return { targetCPA: null, maxCPA: null, targetROAS: null };
    const content = readFileSync(businessPath, 'utf8');
    let targetCPA = null, maxCPA = null, targetROAS = null;

    for (const line of content.split('\n')) {
        const lower = line.toLowerCase();
        const dollarMatch = line.match(/\$\s*([\d,]+(?:\.\d+)?)/);
        const numMatch = line.match(/([\d,]+(?:\.\d+)?)/);
        const val = dollarMatch ? parseFloat(dollarMatch[1].replace(/,/g, ''))
                  : numMatch ? parseFloat(numMatch[1].replace(/,/g, ''))
                  : null;
        if (val === null) continue;

        if (lower.includes('max cpa') || lower.includes('maximum cpa') || lower.includes('cpa limit')) {
            maxCPA = val;
        } else if (lower.includes('target cpa') || lower.includes('cpa target') || lower.includes('goal cpa')) {
            targetCPA = val;
        } else if (lower.includes('target roas') || lower.includes('roas target') || lower.includes('goal roas')) {
            targetROAS = normalizeRoasRatio(val).value;
        }
    }
    return { targetCPA: targetCPA || maxCPA, maxCPA, targetROAS };
}

/**
 * Coerce ROAS inputs entered as percentages (e.g. 530) into ratio form (5.3).
 * Any value > 10 is treated as a percentage. Returns { value, normalized, original }.
 */
export function normalizeRoasRatio(raw) {
    if (raw === null || raw === undefined) return { value: null, normalized: false, original: raw };
    const v = Number(raw);
    if (!Number.isFinite(v)) return { value: null, normalized: false, original: raw };
    if (v > 10) {
        const fixed = v / 100;
        console.warn(`[lib] normalizeRoasRatio: ROAS ${v} looks like a percentage — normalizing to ${fixed}`);
        return { value: fixed, normalized: true, original: v };
    }
    return { value: v, normalized: false, original: v };
}

// ── Enum maps ───────────────────────────────────────────────────────

export const CHANNEL_TYPE_CODES = {
    '2': 'SEARCH',
    '3': 'DISPLAY',
    '4': 'SHOPPING',
    '6': 'VIDEO',
    '9': 'SMART',
    '10': 'MULTI_CHANNEL'
};
export const SKIP_TYPES = new Set(['DISPLAY', 'VIDEO', 'HOTEL', 'LOCAL', 'SMART']);
export const PMAX_TYPES = new Set(['MULTI_CHANNEL', 'PERFORMANCE_MAX']);
export const SHOPPING_TYPES = new Set(['SHOPPING']);

export const BIDDING_STRATEGY_CODES = {
    '2': 'MANUAL_CPC', '3': 'MANUAL_CPM', '6': 'TARGET_CPA', '7': 'PAGE_ONE_PROMOTED',
    '9': 'TARGET_SPEND', '10': 'TARGET_ROAS', '11': 'MAXIMIZE_CONVERSIONS',
    '12': 'MAXIMIZE_CONVERSION_VALUE', '13': 'TARGET_IMPRESSION_SHARE', '14': 'MANUAL_CPV'
};
export const CPA_STRATEGIES = new Set(['TARGET_CPA', 'MAXIMIZE_CONVERSIONS', 'MANUAL_CPC', 'TARGET_SPEND']);
export const ROAS_STRATEGIES = new Set(['TARGET_ROAS', 'MAXIMIZE_CONVERSION_VALUE']);

export function getCampaignType(row, campaignTypeMap) {
    const direct = f(row, 'campaign.advertising_channel_type', 'campaign_advertising_channel_type');
    if (direct) {
        const code = String(direct).trim();
        return (CHANNEL_TYPE_CODES[code] || direct).toUpperCase();
    }
    const campName = f(row, 'campaign.name', 'campaign_name');
    const fromMap = campaignTypeMap[campName] || 'SEARCH';
    return (CHANNEL_TYPE_CODES[String(fromMap).trim()] || fromMap).toUpperCase();
}

// ── Portfolio bid strategy resolution ────────────────────────────────

/**
 * Load portfolio bid strategies from bidding-strategies.csv.
 * Returns a Map keyed by bidding_strategy.resource_name.
 */
export function loadPortfolioTargets(projectRoot) {
    const map = new Map();
    const csvPath = resolve(projectRoot, 'context/google-ads/data/bidding-strategies.csv');
    const rows = loadCSV(csvPath);
    for (const row of rows) {
        const resourceName = f(row, 'bidding_strategy.resource_name', 'bidding_strategy_resource_name');
        if (!resourceName) continue;

        const id = f(row, 'bidding_strategy.id', 'bidding_strategy_id');
        const name = f(row, 'bidding_strategy.name', 'bidding_strategy_name');
        const rawType = f(row, 'bidding_strategy.type', 'bidding_strategy_type');
        const type = (BIDDING_STRATEGY_CODES[String(rawType).trim()] || String(rawType)).toUpperCase();

        // query.js strips _micros and divides by 1M, so these are already dollar values
        const pCpa = num(f(
            row,
            'bidding_strategy.target_cpa.target_cpa_micros',
            'bidding_strategy_target_cpa_target_cpa_micros',
            'bidding_strategy.target_cpa.target_cpa',
            'bidding_strategy_target_cpa_target_cpa',
            'bidding_strategy.maximize_conversions.target_cpa_micros',
            'bidding_strategy_maximize_conversions_target_cpa_micros',
            'bidding_strategy.maximize_conversions.target_cpa',
            'bidding_strategy_maximize_conversions_target_cpa'
        ));
        const pRoasRaw = num(f(
            row,
            'bidding_strategy.target_roas.target_roas',
            'bidding_strategy_target_roas_target_roas',
            'bidding_strategy.maximize_conversion_value.target_roas',
            'bidding_strategy_maximize_conversion_value_target_roas'
        ));
        const pRoas = pRoasRaw > 0 ? normalizeRoasRatio(pRoasRaw).value : 0;

        map.set(resourceName, {
            id,
            name,
            type,
            targetCpa: pCpa > 0 ? pCpa : null,
            targetRoas: pRoas > 0 ? pRoas : null
        });
    }
    return map;
}

/**
 * Resolve the effective bidding strategy + target for a campaign.
 *
 * Precedence per PRD: campaign_inline → portfolio → fallback → none.
 *
 * @param {object} campaignRow  row from campaigns-settings.csv
 * @param {Map} portfolioTargets  output of loadPortfolioTargets()
 * @param {object} fallbackTargets  { targetCPA, targetROAS } from business.md
 * @param {string} fallbackStrategy  'cpa' or 'roas' (account-level default)
 * @returns {object} { targetCpa, targetRoas, biddingMode, strategyType,
 *                     targetSource, portfolioName, portfolioResource }
 */
export function resolveBiddingStrategy(campaignRow, portfolioTargets, fallbackTargets, fallbackStrategy = 'cpa') {
    const rawStrategy = f(campaignRow, 'campaign.bidding_strategy_type', 'campaign_bidding_strategy_type', 'bidding_strategy_type');
    const strategyType = (BIDDING_STRATEGY_CODES[String(rawStrategy).trim()] || String(rawStrategy)).toUpperCase();

    // Inline targets (dollar values — query.js already converted from _micros)
    const inlineCpa = num(f(
        campaignRow,
        'campaign.target_cpa.target_cpa_micros', 'campaign_target_cpa_target_cpa_micros',
        'campaign.target_cpa.target_cpa', 'campaign_target_cpa_target_cpa',
        'campaign.maximize_conversions.target_cpa_micros', 'campaign_maximize_conversions_target_cpa_micros',
        'campaign.maximize_conversions.target_cpa', 'campaign_maximize_conversions_target_cpa'
    ));
    const inlineRoasRaw = num(f(
        campaignRow,
        'campaign.target_roas.target_roas', 'campaign_target_roas_target_roas',
        'campaign.maximize_conversion_value.target_roas', 'campaign_maximize_conversion_value_target_roas'
    ));
    const inlineRoas = inlineRoasRaw > 0 ? normalizeRoasRatio(inlineRoasRaw).value : 0;

    const portfolioResource = f(campaignRow, 'campaign.bidding_strategy', 'campaign_bidding_strategy');
    const portfolio = portfolioResource ? portfolioTargets.get(portfolioResource) : null;

    // Determine biddingMode based on strategyType
    let biddingMode;
    if (ROAS_STRATEGIES.has(strategyType)) biddingMode = 'roas';
    else if (CPA_STRATEGIES.has(strategyType)) biddingMode = 'cpa';
    else biddingMode = fallbackStrategy;

    // Try inline first
    if (inlineCpa > 0 && biddingMode === 'cpa') {
        return {
            targetCpa: inlineCpa, targetRoas: null,
            biddingMode: 'cpa', strategyType,
            targetSource: 'campaign_inline',
            portfolioName: '', portfolioResource: ''
        };
    }
    if (inlineRoas > 0 && biddingMode === 'roas') {
        return {
            targetCpa: null, targetRoas: inlineRoas,
            biddingMode: 'roas', strategyType,
            targetSource: 'campaign_inline',
            portfolioName: '', portfolioResource: ''
        };
    }

    // Portfolio attached → read portfolio target
    if (portfolio) {
        if (portfolio.targetCpa && biddingMode === 'cpa') {
            return {
                targetCpa: portfolio.targetCpa, targetRoas: null,
                biddingMode: 'cpa', strategyType,
                targetSource: 'portfolio',
                portfolioName: portfolio.name, portfolioResource
            };
        }
        if (portfolio.targetRoas && biddingMode === 'roas') {
            return {
                targetCpa: null, targetRoas: portfolio.targetRoas,
                biddingMode: 'roas', strategyType,
                targetSource: 'portfolio',
                portfolioName: portfolio.name, portfolioResource
            };
        }
        // Portfolio type might imply a different mode than strategyType suggests
        if (portfolio.targetRoas) {
            return {
                targetCpa: null, targetRoas: portfolio.targetRoas,
                biddingMode: 'roas', strategyType: portfolio.type || strategyType,
                targetSource: 'portfolio',
                portfolioName: portfolio.name, portfolioResource
            };
        }
        if (portfolio.targetCpa) {
            return {
                targetCpa: portfolio.targetCpa, targetRoas: null,
                biddingMode: 'cpa', strategyType: portfolio.type || strategyType,
                targetSource: 'portfolio',
                portfolioName: portfolio.name, portfolioResource
            };
        }
    }

    // Fallback to account-level target from business.md
    const fbCpa = fallbackTargets?.targetCPA || fallbackTargets?.maxCPA || null;
    const fbRoas = fallbackTargets?.targetROAS || null;

    if (biddingMode === 'roas' && fbRoas) {
        return {
            targetCpa: null, targetRoas: fbRoas,
            biddingMode: 'roas', strategyType,
            targetSource: 'fallback',
            portfolioName: '', portfolioResource: ''
        };
    }
    if (biddingMode === 'cpa' && fbCpa) {
        return {
            targetCpa: fbCpa, targetRoas: null,
            biddingMode: 'cpa', strategyType,
            targetSource: 'fallback',
            portfolioName: '', portfolioResource: ''
        };
    }

    // No target available anywhere
    return {
        targetCpa: null, targetRoas: null,
        biddingMode, strategyType,
        targetSource: 'none',
        portfolioName: '', portfolioResource: ''
    };
}

// ── Negative keyword state loader ───────────────────────────────────

export function loadNegativeStatus(projectRoot) {
    const empty = {
        available: false,
        source: null,
        accountTerms: new Set(),
        campaignTerms: new Set(),
        adGroupTerms: new Set(),
        sharedSets: new Map(),           // resource_name|name → { name, terms: Set, campaigns: Set }
        campaignSharedLinks: new Map(),  // campaign → Set of shared_set keys
        linkAwareShared: false,
        warnings: [],
        coverage: {
            campaignLevel: [],
            adGroupLevel: [],
            sharedListRows: [],
            sharedLinkRows: []
        }
    };

    const campaignNegPath = resolve(projectRoot, 'context/google-ads/data/negative-keywords-campaign.csv');
    const adGroupNegPath = resolve(projectRoot, 'context/google-ads/data/negative-keywords-adgroup.csv');
    const sharedNegPath = resolve(projectRoot, 'context/google-ads/data/negative-keywords-shared.csv');
    const sharedLinksPath = resolve(projectRoot, 'context/google-ads/data/negative-keywords-shared-links.csv');

    const hasCampaignNegs = existsSync(campaignNegPath);
    const hasAdGroupNegs = existsSync(adGroupNegPath);
    const hasSharedNegs = existsSync(sharedNegPath);
    const hasSharedLinks = existsSync(sharedLinksPath);

    if (!hasCampaignNegs && !hasAdGroupNegs && !hasSharedNegs) return empty;

    const accountTerms = new Set();
    const campaignTerms = new Set();
    const adGroupTerms = new Set();
    const warnings = [];
    const sources = [];

    const coverage = {
        campaignLevel: [],
        adGroupLevel: [],
        sharedListRows: [],
        sharedLinkRows: []
    };

    if (hasCampaignNegs) {
        sources.push(campaignNegPath);
        const rows = loadCSV(campaignNegPath);
        for (const row of rows) {
            const term = norm(f(row, 'campaign_criterion.keyword.text', 'Keyword', 'keyword', 'criteria'));
            const campaign = norm(f(row, 'campaign.name', 'Campaign', 'campaign'));
            const matchType = f(row, 'campaign_criterion.keyword.match_type', 'Match Type', 'match_type') || 'PHRASE';
            if (!term) continue;
            coverage.campaignLevel.push({ campaign, term, matchType: String(matchType).toUpperCase() });
            if (campaign) campaignTerms.add(`${campaign}|||${term}`);
            else accountTerms.add(term);
        }
    }

    if (hasAdGroupNegs) {
        sources.push(adGroupNegPath);
        const rows = loadCSV(adGroupNegPath);
        for (const row of rows) {
            const term = norm(f(row, 'ad_group_criterion.keyword.text', 'Keyword', 'keyword', 'criteria'));
            const campaign = norm(f(row, 'campaign.name', 'Campaign', 'campaign'));
            const adGroup = norm(f(row, 'ad_group.name', 'Ad Group', 'ad_group'));
            const matchType = f(row, 'ad_group_criterion.keyword.match_type', 'Match Type', 'match_type') || 'PHRASE';
            if (!term) continue;
            coverage.adGroupLevel.push({ campaign, adGroup, term, matchType: String(matchType).toUpperCase() });
            if (campaign && adGroup) adGroupTerms.add(`${campaign}|||${adGroup}|||${term}`);
            else if (campaign) campaignTerms.add(`${campaign}|||${term}`);
            else accountTerms.add(term);
        }
    }

    const sharedSets = new Map();
    const campaignSharedLinks = new Map();
    let linkAwareShared = false;

    if (hasSharedNegs) {
        sources.push(sharedNegPath);
        const sharedRows = loadCSV(sharedNegPath);
        const looseSharedTerms = new Set();

        for (const row of sharedRows) {
            const term = norm(f(row, 'shared_criterion.keyword.text', 'Keyword', 'keyword', 'criteria'));
            if (!term) continue;
            const setId = f(row, 'shared_set.id');
            const setName = f(row, 'shared_set.name', 'Shared Set', 'shared_set');
            const setKey = String(setId || setName || '').trim();
            const matchType = f(row, 'shared_criterion.keyword.match_type', 'Match Type', 'match_type') || 'PHRASE';
            coverage.sharedListRows.push({
                setKey, setName, term, matchType: String(matchType).toUpperCase()
            });
            if (!setKey) {
                looseSharedTerms.add(term);
                continue;
            }
            if (!sharedSets.has(setKey)) {
                sharedSets.set(setKey, { name: setName, terms: new Set(), campaigns: new Set() });
            }
            sharedSets.get(setKey).terms.add(term);
        }

        if (hasSharedLinks) {
            sources.push(sharedLinksPath);
            linkAwareShared = true;
            const linkRows = loadCSV(sharedLinksPath);
            for (const row of linkRows) {
                const campaign = norm(f(row, 'campaign.name', 'Campaign', 'campaign'));
                const setId = f(row, 'shared_set.id');
                const setName = f(row, 'shared_set.name', 'Shared Set', 'shared_set');
                const setKey = String(setId || setName || '').trim();
                if (!campaign || !setKey) continue;
                coverage.sharedLinkRows.push({ campaign, setKey, setName });
                if (!sharedSets.has(setKey)) {
                    sharedSets.set(setKey, { name: setName, terms: new Set(), campaigns: new Set() });
                }
                sharedSets.get(setKey).campaigns.add(campaign);
                if (!campaignSharedLinks.has(campaign)) campaignSharedLinks.set(campaign, new Set());
                campaignSharedLinks.get(campaign).add(setKey);
            }

            for (const [setKey, setData] of sharedSets.entries()) {
                if (setData.campaigns.size === 0) {
                    warnings.push(`Shared set has no campaign links: ${setData.name || setKey}`);
                    for (const term of setData.terms) accountTerms.add(term);
                    continue;
                }
                for (const campaign of setData.campaigns) {
                    for (const term of setData.terms) {
                        campaignTerms.add(`${campaign}|||${term}`);
                    }
                }
            }
        } else {
            warnings.push('Shared negative links file missing; shared terms treated as account-level.');
            for (const setData of sharedSets.values()) {
                for (const term of setData.terms) accountTerms.add(term);
            }
        }
        for (const term of looseSharedTerms) accountTerms.add(term);
    }

    return {
        available: true,
        source: sources.join(', '),
        accountTerms,
        campaignTerms,
        adGroupTerms,
        sharedSets,
        campaignSharedLinks,
        linkAwareShared,
        warnings,
        coverage
    };
}

export function isTermExcluded(negatives, campaign, adGroup, term) {
    const t = norm(term);
    const c = norm(campaign);
    const a = norm(adGroup);
    if (!t) return false;
    if (negatives.adGroupTerms.has(`${c}|||${a}|||${t}`)) return true;
    if (negatives.campaignTerms.has(`${c}|||${t}`)) return true;
    if (negatives.accountTerms.has(t)) return true;
    return false;
}

// ── CLI argument parsing ────────────────────────────────────────────

export function parseCliArgs(argv) {
    return argv.slice(2).reduce((acc, arg) => {
        if (arg.startsWith('--')) {
            const eq = arg.indexOf('=');
            if (eq > -1) acc[arg.slice(2, eq)] = arg.slice(eq + 1);
            else acc[arg.slice(2)] = true;
        }
        return acc;
    }, {});
}
