#!/usr/bin/env node

/**
 * Keyword Overlap Analysis — keyword-auditor
 *
 * Detects structural issues: duplicates, match type conflicts, and PMax overlap.
 * All detection is string-based (no semantic reasoning needed).
 *
 * Usage:
 *   node analyze-keyword-overlap.js \
 *     --structural-csv=context/google-ads/data/keywords-structural.csv \
 *     --period-a-csv=context/google-ads/data/keywords-periodA.csv \
 *     --pmax-csv=context/google-ads/data/pmax-search-terms.csv \
 *     --negatives-campaign-csv=context/google-ads/data/negatives-campaign-kw.csv \
 *     --negatives-shared-csv=context/google-ads/data/negatives-shared-kw.csv \
 *     --campaign-shared-sets-csv=context/google-ads/data/negatives-shared-campaigns.csv \
 *     --negatives-adgroup-csv=context/google-ads/data/negatives-adgroup-kw.csv \
 *     --output=context/google-ads/data/keyword-overlaps.csv
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

const structuralCsvPath = resolve(_projectRoot, args['structural-csv'] || '');
const periodACsvPath = resolve(_projectRoot, args['period-a-csv'] || '');
const pmaxCsvPath = resolve(_projectRoot, args['pmax-csv'] || '');
const negCampaignCsvPath = resolve(_projectRoot, args['negatives-campaign-csv'] || '');
const negSharedCsvPath = resolve(_projectRoot, args['negatives-shared-csv'] || '');
const campaignSharedSetsCsvPath = resolve(_projectRoot, args['campaign-shared-sets-csv'] || '');
const negAdGroupCsvPath = resolve(_projectRoot, args['negatives-adgroup-csv'] || '');
const outputPath = resolve(_projectRoot, args['output'] || 'context/google-ads/data/keyword-overlaps.csv');

// ── Validation ──────────────────────────────────────────────────────
if (!args['structural-csv']) {
    console.error('Error: --structural-csv is required');
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

function num(val) {
    const n = parseFloat(val);
    return isNaN(n) ? 0 : n;
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

function normalize(text) {
    return (text || '').toLowerCase().trim();
}

// Composite keyword key — criterion_id is only unique within an ad group,
// so every lookup must be keyed by (ad_group_id, criterion_id).
const kwKey = (adGroupId, criterionId) => `${adGroupId}:${criterionId}`;

// ── Step 0: Load data ───────────────────────────────────────────────
console.log('Loading data...');
const structuralRows = loadCsv(structuralCsvPath);
const periodARows = loadCsv(periodACsvPath);
const pmaxRows = loadCsv(pmaxCsvPath);

console.log(`Structural keywords: ${structuralRows.length}`);
console.log(`Period A keywords: ${periodARows.length}`);
console.log(`PMax search terms: ${pmaxRows.length}`);

// Filter out experiments
const structural = structuralRows.filter(r =>
    !r.campaign_experiment_type || r.campaign_experiment_type === 'BASE' || r.campaign_experiment_type === ''
);
const periodA = periodARows.filter(r =>
    !r.campaign_experiment_type || r.campaign_experiment_type === 'BASE' || r.campaign_experiment_type === ''
);
const pmax = pmaxRows.filter(r =>
    !r.campaign_experiment_type || r.campaign_experiment_type === 'BASE' || r.campaign_experiment_type === ''
);

console.log(`After experiment filter: Structural=${structural.length}, PMax=${pmax.length}`);
if (periodA.length > 0 && structural.length === 0) {
    console.warn('Warning: structural keyword dataset is empty while Period A has rows. Overlap and hygiene diagnostics may be incomplete.');
}

// Build performance lookup from Period A ((ad_group_id, criterion_id) → metrics).
// criterion_id is not globally unique, so we must key by the composite.
const perfLookup = new Map();
for (const row of periodA) {
    const crid = row.ad_group_criterion_criterion_id;
    const agid = row.ad_group_id;
    if (crid && agid) {
        perfLookup.set(kwKey(agid, crid), {
            impressions: num(row.metrics_impressions),
            clicks: num(row.metrics_clicks),
            cost: num(row.metrics_cost),
            conversions: num(row.metrics_conversions),
        });
    }
}

// ── Step 1b: Load negative keyword coverage ───────────────────────────
console.log('Loading negative keywords...');
const negCampaignRows = loadCsv(negCampaignCsvPath);
const negSharedRows = loadCsv(negSharedCsvPath);
const campaignSharedSetRows = loadCsv(campaignSharedSetsCsvPath);
const negAdGroupRows = loadCsv(negAdGroupCsvPath);
console.log(
    `Campaign negatives: ${negCampaignRows.length}, Shared negatives: ${negSharedRows.length}, ` +
    `Campaign/shared attachments: ${campaignSharedSetRows.length}, Ad group negatives: ${negAdGroupRows.length}`
);

// Build lookup: campaign_id → [{text, match_type}]
const campaignNegatives = new Map();
for (const row of negCampaignRows) {
    const cid = row.campaign_id;
    if (!campaignNegatives.has(cid)) campaignNegatives.set(cid, []);
    campaignNegatives.get(cid).push({
        text: normalize(row.campaign_criterion_keyword_text),
        matchType: row.campaign_criterion_keyword_match_type,
    });
}

const sharedNegativesBySet = new Map();
for (const row of negSharedRows) {
    const setId = row.shared_set_id;
    if (!setId) continue;
    if (!sharedNegativesBySet.has(setId)) sharedNegativesBySet.set(setId, []);
    sharedNegativesBySet.get(setId).push({
        text: normalize(row.shared_criterion_keyword_text),
        matchType: row.shared_criterion_keyword_match_type,
        sharedSetName: row.shared_set_name || '',
    });
}

const campaignSharedNegatives = new Map();
for (const row of campaignSharedSetRows) {
    const cid = row.campaign_id;
    const setId = row.shared_set_id;
    if (!cid || !setId) continue;
    if (!campaignSharedNegatives.has(cid)) campaignSharedNegatives.set(cid, []);
    const setMembers = sharedNegativesBySet.get(setId) || [];
    for (const member of setMembers) {
        campaignSharedNegatives.get(cid).push(member);
    }
}

// Build lookup: ad_group_id → [{text, match_type}]
const adGroupNegatives = new Map();
for (const row of negAdGroupRows) {
    const agid = row.ad_group_id;
    if (!adGroupNegatives.has(agid)) adGroupNegatives.set(agid, []);
    adGroupNegatives.get(agid).push({
        text: normalize(row.ad_group_criterion_keyword_text),
        matchType: row.ad_group_criterion_keyword_match_type,
    });
}

/**
 * Check if a keyword would be blocked by a negative.
 * Approximates Google's negative matching:
 *   EXACT  → keyword text must match exactly
 *   PHRASE → negative phrase must appear as contiguous word sequence in keyword
 *   BROAD  → all words in negative must appear anywhere in keyword
 */
function negativeCovers(negText, negMatchType, keywordText) {
    const kw = normalize(keywordText);
    const neg = negText; // already normalized
    if (kw === neg) return true; // exact match always covers

    if (negMatchType === 'EXACT') {
        return kw === neg;
    }
    if (negMatchType === 'PHRASE') {
        // Negative phrase must appear as a contiguous word-boundary match
        const kwWords = kw.split(/\s+/);
        const negWords = neg.split(/\s+/);
        for (let i = 0; i <= kwWords.length - negWords.length; i++) {
            if (negWords.every((w, j) => kwWords[i + j] === w)) return true;
        }
        return false;
    }
    // BROAD: all words in negative must appear in keyword (any order)
    const kwWords = new Set(kw.split(/\s+/));
    return neg.split(/\s+/).every(w => kwWords.has(w));
}

/**
 * Check if a keyword is covered by any negative at campaign or ad group level.
 * Returns the covering negative detail string, or null if not covered.
 */
function checkNegativeCoverage(keywordText, campaignId, adGroupId) {
    // Check campaign-level negatives
    const campNegs = campaignNegatives.get(campaignId) || [];
    for (const neg of campNegs) {
        if (negativeCovers(neg.text, neg.matchType, keywordText)) {
            return `campaign:${neg.text}[${neg.matchType}]`;
        }
    }
    // Check shared negative lists attached to the campaign
    const sharedNegs = campaignSharedNegatives.get(campaignId) || [];
    for (const neg of sharedNegs) {
        if (negativeCovers(neg.text, neg.matchType, keywordText)) {
            const listLabel = neg.sharedSetName ? `${neg.sharedSetName}:` : '';
            return `shared:${listLabel}${neg.text}[${neg.matchType}]`;
        }
    }
    // Check ad group-level negatives
    const agNegs = adGroupNegatives.get(adGroupId) || [];
    for (const neg of agNegs) {
        if (negativeCovers(neg.text, neg.matchType, keywordText)) {
            return `adgroup:${neg.text}[${neg.matchType}]`;
        }
    }
    return null;
}

const overlaps = [];

// ── Step 2: Match type redundancy within ad group (D03) ─────────────
console.log('Checking match type redundancy within ad groups...');

const agGroups = new Map(); // key: "ad_group_id|normalized_text"
for (const row of structural) {
    const key = `${row.ad_group_id}|${normalize(row.ad_group_criterion_keyword_text)}`;
    if (!agGroups.has(key)) agGroups.set(key, []);
    agGroups.get(key).push(row);
}

let redundancyCount = 0;
for (const [, group] of agGroups) {
    if (group.length <= 1) continue;

    const matchTypes = [...new Set(group.map(r => r.ad_group_criterion_keyword_match_type))];
    if (matchTypes.length <= 1) continue; // Same match type duplicates handled in D10

    redundancyCount++;
    const kwText = group[0].ad_group_criterion_keyword_text;
    const agName = group[0].ad_group_name;

    // Use first two entries as location A and B
    for (let i = 1; i < group.length; i++) {
        const a = group[0];
        const b = group[i];
        const perfA = perfLookup.get(kwKey(a.ad_group_id, a.ad_group_criterion_criterion_id)) || {};
        const perfB = perfLookup.get(kwKey(b.ad_group_id, b.ad_group_criterion_criterion_id)) || {};

        overlaps.push({
            keyword_text: kwText,
            match_type: `${a.ad_group_criterion_keyword_match_type} + ${b.ad_group_criterion_keyword_match_type}`,
            overlap_type: 'within_ad_group',
            flag_type: 'MATCH_TYPE_REDUNDANCY',
            flag_severity: 'Low',
            flag_detail: `"${kwText}" exists as ${matchTypes.join(', ')} in ad group "${agName}"`,
            location_a_campaign: a.campaign_name,
            location_a_adgroup: a.ad_group_name,
            location_a_criterion_id: a.ad_group_criterion_criterion_id,
            location_a_impressions: perfA.impressions ?? '',
            location_a_clicks: perfA.clicks ?? '',
            location_a_cost: perfA.cost !== undefined ? perfA.cost.toFixed(2) : '',
            location_a_conversions: perfA.conversions ?? '',
            location_b_campaign: b.campaign_name,
            location_b_adgroup: b.ad_group_name,
            location_b_criterion_id: b.ad_group_criterion_criterion_id,
            location_b_impressions: perfB.impressions ?? '',
            location_b_clicks: perfB.clicks ?? '',
            location_b_cost: perfB.cost !== undefined ? perfB.cost.toFixed(2) : '',
            location_b_conversions: perfB.conversions ?? '',
        });
    }
}

console.log(`Match type redundancy groups: ${redundancyCount}`);

// ── Step 3: Cross-campaign match type overlap (D04) ─────────────────
console.log('Checking cross-campaign match type overlap...');

const crossGroups = new Map(); // key: normalized_text
for (const row of structural) {
    const key = normalize(row.ad_group_criterion_keyword_text);
    if (!crossGroups.has(key)) crossGroups.set(key, []);
    crossGroups.get(key).push(row);
}

let crossConflictCount = 0;
for (const [, group] of crossGroups) {
    if (group.length <= 1) continue;

    // Get unique campaign IDs
    const campaignIds = [...new Set(group.map(r => r.campaign_id))];
    if (campaignIds.length <= 1) continue; // Same campaign — not a cross-campaign issue

    // Check for different match types across campaigns
    const byCampaign = new Map();
    for (const row of group) {
        if (!byCampaign.has(row.campaign_id)) byCampaign.set(row.campaign_id, []);
        byCampaign.get(row.campaign_id).push(row);
    }

    const campaignMatchTypes = new Map();
    for (const [cid, rows] of byCampaign) {
        campaignMatchTypes.set(cid, [...new Set(rows.map(r => r.ad_group_criterion_keyword_match_type))]);
    }

    // Find pairs with different match types
    const cidList = [...campaignMatchTypes.keys()];
    for (let i = 0; i < cidList.length; i++) {
        for (let j = i + 1; j < cidList.length; j++) {
            const typesA = campaignMatchTypes.get(cidList[i]);
            const typesB = campaignMatchTypes.get(cidList[j]);

            // Check if there's a match type in A not in B (or vice versa)
            const allTypes = new Set([...typesA, ...typesB]);
            if (allTypes.size > 1) {
                crossConflictCount++;
                const rowA = byCampaign.get(cidList[i])[0];
                const rowB = byCampaign.get(cidList[j])[0];
                const perfA = perfLookup.get(kwKey(rowA.ad_group_id, rowA.ad_group_criterion_criterion_id)) || {};
                const perfB = perfLookup.get(kwKey(rowB.ad_group_id, rowB.ad_group_criterion_criterion_id)) || {};
                const kwText = group[0].ad_group_criterion_keyword_text;

                // Check if either side has a negative covering this keyword
                const covA = checkNegativeCoverage(kwText, rowA.campaign_id, rowA.ad_group_id);
                const covB = checkNegativeCoverage(kwText, rowB.campaign_id, rowB.ad_group_id);
                const covered = covA || covB || '';

                overlaps.push({
                    keyword_text: kwText,
                    match_type: `${typesA.join('/')} vs ${typesB.join('/')}`,
                    overlap_type: 'cross_campaign',
                    flag_type: 'CROSS_CAMPAIGN_MATCH_CONFLICT',
                    flag_severity: 'Medium',
                    flag_detail: `"${kwText}": ${typesA.join('/')} in "${rowA.campaign_name}", ${typesB.join('/')} in "${rowB.campaign_name}"`,
                    location_a_campaign: rowA.campaign_name,
                    location_a_adgroup: rowA.ad_group_name,
                    location_a_criterion_id: rowA.ad_group_criterion_criterion_id,
                    location_a_impressions: perfA.impressions ?? '',
                    location_a_clicks: perfA.clicks ?? '',
                    location_a_cost: perfA.cost !== undefined ? perfA.cost.toFixed(2) : '',
                    location_a_conversions: perfA.conversions ?? '',
                    location_b_campaign: rowB.campaign_name,
                    location_b_adgroup: rowB.ad_group_name,
                    location_b_criterion_id: rowB.ad_group_criterion_criterion_id,
                    location_b_impressions: perfB.impressions ?? '',
                    location_b_clicks: perfB.clicks ?? '',
                    location_b_cost: perfB.cost !== undefined ? perfB.cost.toFixed(2) : '',
                    location_b_conversions: perfB.conversions ?? '',
                    negative_covered: covered,
                });
            }
        }
    }
}

console.log(`Cross-campaign match conflicts: ${crossConflictCount}`);

// ── Step 4: Duplicate keyword detection (D10) ───────────────────────
console.log('Checking duplicate keywords...');

const dupeGroups = new Map(); // key: "normalized_text|match_type"
for (const row of structural) {
    const key = `${normalize(row.ad_group_criterion_keyword_text)}|${row.ad_group_criterion_keyword_match_type}`;
    if (!dupeGroups.has(key)) dupeGroups.set(key, []);
    dupeGroups.get(key).push(row);
}

let dupeCount = 0;
for (const [, group] of dupeGroups) {
    if (group.length <= 1) continue;

    // Must be in different ad groups or campaigns to be a duplicate
    const locations = new Set(group.map(r => `${r.campaign_id}|${r.ad_group_id}`));
    if (locations.size <= 1) continue;

    dupeCount++;
    const kwText = group[0].ad_group_criterion_keyword_text;
    const matchType = group[0].ad_group_criterion_keyword_match_type;
    const locationList = group.map(r => `"${r.campaign_name} > ${r.ad_group_name}"`).join(', ');

    // Create pairwise overlaps (first vs each subsequent)
    for (let i = 1; i < group.length; i++) {
        const a = group[0];
        const b = group[i];
        const perfA = perfLookup.get(kwKey(a.ad_group_id, a.ad_group_criterion_criterion_id)) || {};
        const perfB = perfLookup.get(kwKey(b.ad_group_id, b.ad_group_criterion_criterion_id)) || {};

        // Check if either location has a negative covering this keyword
        const covA = checkNegativeCoverage(kwText, a.campaign_id, a.ad_group_id);
        const covB = checkNegativeCoverage(kwText, b.campaign_id, b.ad_group_id);
        const covered = covA || covB || '';

        overlaps.push({
            keyword_text: kwText,
            match_type: matchType,
            overlap_type: 'duplicate',
            flag_type: 'DUPLICATE_KEYWORD',
            flag_severity: 'Medium',
            flag_detail: `"${kwText}" [${matchType}] exists in ${group.length} locations: ${locationList}`,
            location_a_campaign: a.campaign_name,
            location_a_adgroup: a.ad_group_name,
            location_a_criterion_id: a.ad_group_criterion_criterion_id,
            location_a_impressions: perfA.impressions ?? '',
            location_a_clicks: perfA.clicks ?? '',
            location_a_cost: perfA.cost !== undefined ? perfA.cost.toFixed(2) : '',
            location_a_conversions: perfA.conversions ?? '',
            location_b_campaign: b.campaign_name,
            location_b_adgroup: b.ad_group_name,
            location_b_criterion_id: b.ad_group_criterion_criterion_id,
            location_b_impressions: perfB.impressions ?? '',
            location_b_clicks: perfB.clicks ?? '',
            location_b_cost: perfB.cost !== undefined ? perfB.cost.toFixed(2) : '',
            location_b_conversions: perfB.conversions ?? '',
            negative_covered: covered,
        });
    }
}

console.log(`Duplicate keyword groups: ${dupeCount}`);

// ── Step 5: PMax search term overlap (D12) ──────────────────────────
if (pmax.length > 0) {
    console.log('Checking PMax search term overlap...');

    // Build search keyword lookup: normalized_text → [rows]
    const searchKwLookup = new Map();
    for (const row of structural) {
        const key = normalize(row.ad_group_criterion_keyword_text);
        if (!searchKwLookup.has(key)) searchKwLookup.set(key, []);
        searchKwLookup.get(key).push(row);
    }

    // Also build phrase/broad lookup for containment matching
    const phraseAndBroad = [];
    for (const row of structural) {
        const mt = row.ad_group_criterion_keyword_match_type;
        if (mt === 'PHRASE' || mt === 'BROAD') {
            phraseAndBroad.push({
                normalized: normalize(row.ad_group_criterion_keyword_text),
                row,
            });
        }
    }

    let pmaxOverlapCount = 0;

    for (const pmaxRow of pmax) {
        const pmaxTerm = normalize(pmaxRow.campaign_search_term_view_search_term || pmaxRow.search_term || '');
        if (!pmaxTerm) continue;

        const pmaxPerf = {
            impressions: num(pmaxRow.metrics_impressions),
            clicks: num(pmaxRow.metrics_clicks),
            cost: num(pmaxRow.metrics_cost),
            conversions: num(pmaxRow.metrics_conversions),
        };

        // Exact match: PMax term === keyword text
        if (searchKwLookup.has(pmaxTerm)) {
            const matches = searchKwLookup.get(pmaxTerm);
            for (const searchRow of matches) {
                pmaxOverlapCount++;
                const searchPerf = perfLookup.get(kwKey(searchRow.ad_group_id, searchRow.ad_group_criterion_criterion_id)) || {};
                const covered = checkNegativeCoverage(pmaxTerm, searchRow.campaign_id, searchRow.ad_group_id) || '';

                overlaps.push({
                    keyword_text: searchRow.ad_group_criterion_keyword_text,
                    match_type: searchRow.ad_group_criterion_keyword_match_type,
                    overlap_type: 'pmax_overlap',
                    flag_type: 'PMAX_OVERLAP',
                    flag_severity: 'Medium',
                    flag_detail: `PMax term "${pmaxTerm}" matches Search keyword "${searchRow.ad_group_criterion_keyword_text}" [${searchRow.ad_group_criterion_keyword_match_type}]`,
                    location_a_campaign: searchRow.campaign_name,
                    location_a_adgroup: searchRow.ad_group_name,
                    location_a_criterion_id: searchRow.ad_group_criterion_criterion_id,
                    location_a_impressions: searchPerf.impressions ?? '',
                    location_a_clicks: searchPerf.clicks ?? '',
                    location_a_cost: searchPerf.cost !== undefined ? searchPerf.cost.toFixed(2) : '',
                    location_a_conversions: searchPerf.conversions ?? '',
                    location_b_campaign: pmaxRow.campaign_name,
                    location_b_adgroup: 'PMax',
                    location_b_criterion_id: '',
                    location_b_impressions: pmaxPerf.impressions,
                    location_b_clicks: pmaxPerf.clicks,
                    location_b_cost: pmaxPerf.cost.toFixed(2),
                    location_b_conversions: pmaxPerf.conversions,
                    negative_covered: covered,
                });
            }
            continue; // Already matched exactly, skip containment
        }

        // Phrase containment: PMax term contains a phrase/broad keyword
        for (const { normalized, row: searchRow } of phraseAndBroad) {
            if (pmaxTerm.includes(normalized) && pmaxTerm !== normalized) {
                pmaxOverlapCount++;
                const searchPerf = perfLookup.get(kwKey(searchRow.ad_group_id, searchRow.ad_group_criterion_criterion_id)) || {};
                const covered = checkNegativeCoverage(pmaxTerm, searchRow.campaign_id, searchRow.ad_group_id) || '';

                overlaps.push({
                    keyword_text: searchRow.ad_group_criterion_keyword_text,
                    match_type: searchRow.ad_group_criterion_keyword_match_type,
                    overlap_type: 'pmax_overlap',
                    flag_type: 'PMAX_OVERLAP',
                    flag_severity: 'Medium',
                    flag_detail: `PMax term "${pmaxTerm}" contains Search keyword "${searchRow.ad_group_criterion_keyword_text}" [${searchRow.ad_group_criterion_keyword_match_type}]`,
                    location_a_campaign: searchRow.campaign_name,
                    location_a_adgroup: searchRow.ad_group_name,
                    location_a_criterion_id: searchRow.ad_group_criterion_criterion_id,
                    location_a_impressions: searchPerf.impressions ?? '',
                    location_a_clicks: searchPerf.clicks ?? '',
                    location_a_cost: searchPerf.cost !== undefined ? searchPerf.cost.toFixed(2) : '',
                    location_a_conversions: searchPerf.conversions ?? '',
                    location_b_campaign: pmaxRow.campaign_name,
                    location_b_adgroup: 'PMax',
                    location_b_criterion_id: '',
                    location_b_impressions: pmaxPerf.impressions,
                    location_b_clicks: pmaxPerf.clicks,
                    location_b_cost: pmaxPerf.cost.toFixed(2),
                    location_b_conversions: pmaxPerf.conversions,
                    negative_covered: covered,
                });
            }
        }
    }

    console.log(`PMax search term overlaps: ${pmaxOverlapCount}`);
} else {
    console.log('No PMax search terms — skipping D12.');
}

// ── Step 6: Write output ────────────────────────────────────────────
const headers = [
    'keyword_text', 'match_type', 'overlap_type', 'flag_type', 'flag_severity', 'flag_detail',
    'location_a_campaign', 'location_a_adgroup', 'location_a_criterion_id',
    'location_a_impressions', 'location_a_clicks', 'location_a_cost', 'location_a_conversions',
    'location_b_campaign', 'location_b_adgroup', 'location_b_criterion_id',
    'location_b_impressions', 'location_b_clicks', 'location_b_cost', 'location_b_conversions',
    'negative_covered',
];

writeCsv(outputPath, headers, overlaps);
console.log(`\nFile: ${outputPath}`);
console.log(`Rows: ${overlaps.length}`);

// Summary
const typeCounts = {};
for (const o of overlaps) {
    typeCounts[o.flag_type] = (typeCounts[o.flag_type] || 0) + 1;
}
console.log(`Overlap types: ${JSON.stringify(typeCounts)}`);

// Negative coverage summary
const coveredCount = overlaps.filter(o => o.negative_covered).length;
const d04Covered = overlaps.filter(o => o.flag_type === 'CROSS_CAMPAIGN_MATCH_CONFLICT' && o.negative_covered).length;
const d04Total = typeCounts['CROSS_CAMPAIGN_MATCH_CONFLICT'] || 0;
const d10Covered = overlaps.filter(o => o.flag_type === 'DUPLICATE_KEYWORD' && o.negative_covered).length;
const d10Total = typeCounts['DUPLICATE_KEYWORD'] || 0;
console.log(`Negative coverage: ${coveredCount} of ${overlaps.length} overlaps covered`);
console.log(`  D04 cross-campaign: ${d04Covered}/${d04Total} covered`);
console.log(`  D10 duplicates: ${d10Covered}/${d10Total} covered`);
console.log('Done.');
