#!/usr/bin/env node

/**
 * Exclusion Coverage Analysis — placement-auditor
 *
 * Analyzes mobile app category gaps, campaign exclusion list coverage,
 * and list hygiene. Outputs exclusion-coverage.json.
 *
 * Usage:
 *   node analyze-exclusion-coverage.js \
 *     --app-exclusions-csv=context/google-ads/data/account-exclusions-apps.csv \
 *     --app-categories-csv=context/google-ads/data/mobile-app-categories.csv \
 *     --exclusion-lists-csv=context/google-ads/data/exclusion-lists.csv \
 *     --list-items-csv=context/google-ads/data/exclusion-list-items.csv \
 *     --list-links-csv=context/google-ads/data/exclusion-list-links.csv \
 *     --campaigns-csv=context/google-ads/data/campaigns.csv \
 *     --placement-performance-csv=context/google-ads/data/placement-performance.csv \
 *     --output=context/google-ads/data/exclusion-coverage.json
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { parse } from 'csv-parse/sync';

// Find project root
const __dirname = dirname(fileURLToPath(import.meta.url));
let _projectRoot = __dirname;
while (_projectRoot !== '/' && !existsSync(resolve(_projectRoot, 'config'))) {
    _projectRoot = resolve(_projectRoot, '..');
}

// Parse CLI args
const args = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const eqIndex = arg.indexOf('=');
        const key = arg.slice(0, eqIndex).replace('--', '');
        const value = arg.slice(eqIndex + 1);
        if (key && value) acc[key] = value;
    }
    return acc;
}, {});

const appExclusionsCsv = resolve(_projectRoot, args['app-exclusions-csv'] || '');
const appCategoriesCsv = resolve(_projectRoot, args['app-categories-csv'] || '');
const exclusionListsCsv = resolve(_projectRoot, args['exclusion-lists-csv'] || '');
const listItemsCsv = resolve(_projectRoot, args['list-items-csv'] || '');
const listLinksCsv = resolve(_projectRoot, args['list-links-csv'] || '');
const campaignsCsv = resolve(_projectRoot, args['campaigns-csv'] || '');
const perfCsv = resolve(_projectRoot, args['placement-performance-csv'] || '');
const outputPath = resolve(_projectRoot, args['output'] || 'context/google-ads/data/exclusion-coverage.json');

// ── CSV loader ───────────────────────────────────────────────────────

function loadCsv(filePath) {
    if (!existsSync(filePath)) {
        console.log(`Note: ${filePath} not found, skipping`);
        return [];
    }
    const content = readFileSync(filePath, 'utf8');
    if (!content.trim()) return [];
    return parse(content, { columns: true, skip_empty_lines: true, relax_column_count: true });
}

function num(val) {
    const n = parseFloat(val);
    return isNaN(n) ? 0 : n;
}

// ── Main analysis ────────────────────────────────────────────────────

function run() {
    const appExclusions = loadCsv(appExclusionsCsv);
    const appCategories = loadCsv(appCategoriesCsv);
    const exclusionLists = loadCsv(exclusionListsCsv);
    const listItems = loadCsv(listItemsCsv);
    const listLinks = loadCsv(listLinksCsv);
    const campaigns = loadCsv(campaignsCsv);
    const perfRows = loadCsv(perfCsv);

    // ── PL-D01: Mobile app gap analysis ──────────────────────────────

    // All available app categories — filter out parent/umbrella categories
    // The API returns ~150 entries including top-level groupings (id=0 "/", 60000 "Google Play",
    // 60500 "Apple App Store", etc.) that are parent nodes, not excludable leaf categories.
    // Parent categories have no resource_name OR are known umbrella IDs.
    const PARENT_CATEGORY_IDS = new Set([
        '0',      // "/" root
        '60000',  // "Google Play" (parent)
        '60008',  // "Games" (Google Play parent)
        '60056',  // "Family" (Google Play parent)
        '60500',  // "Apple App Store" (parent)
        '60506',  // "Games" (Apple parent)
        '60513',  // "Newsstand" (Apple parent)
        '60572',  // "Stickers" (Apple parent)
        '61001',  // "Windows Phone Apps" (parent)
        '69500',  // "All Apps" (umbrella)
    ]);

    const allCategories = appCategories
        .map(row => ({
            id: row['mobile_app_category_constant.id'] || '',
            name: row['mobile_app_category_constant.name'] || '',
            resource_name: row['mobile_app_category_constant.resource_name'] || '',
        }))
        .filter(cat => {
            // Exclude parent categories: no resource_name OR known parent ID
            if (!cat.resource_name) return false;
            if (PARENT_CATEGORY_IDS.has(cat.id)) return false;
            return true;
        });

    // Currently excluded app categories
    const excludedCategoryConstants = new Set(
        appExclusions.map(row =>
            row['customer_negative_criterion.mobile_app_category.mobile_app_category_constant'] || ''
        ).filter(Boolean)
    );

    // Find missing categories
    const missingCategories = allCategories.filter(cat => {
        // Check both resource_name and id-based reference
        const resourceMatch = excludedCategoryConstants.has(cat.resource_name);
        const idMatch = excludedCategoryConstants.has(`mobileAppCategoryConstants/${cat.id}`);
        return !resourceMatch && !idMatch;
    });

    // Calculate app placement spend from performance data
    let appSpendMicros = 0;
    let appConversions = 0;
    let totalSpendMicros = 0;
    for (const row of perfRows) {
        const placementType = row['group_placement_view.placement_type'] || '';
        const costMicros = num(row['metrics.cost_micros']);
        totalSpendMicros += costMicros;
        if (placementType === 'MOBILE_APPLICATION' || placementType === 'MOBILE_APP_CATEGORY') {
            appSpendMicros += costMicros;
            appConversions += num(row['metrics.conversions']);
        }
    }

    const appAudit = {
        total_categories: allCategories.length,
        excluded_count: allCategories.length - missingCategories.length,
        missing_categories: missingCategories.map(c => ({ id: c.id, name: c.name })),
        app_placement_spend_micros: appSpendMicros,
        app_placement_spend_dollars: (appSpendMicros / 1_000_000).toFixed(2),
        app_placement_conversions: appConversions,
        app_spend_share_pct: totalSpendMicros > 0 ? ((appSpendMicros / totalSpendMicros) * 100).toFixed(1) : '0.0',
    };

    // ── PL-D05: Campaign coverage matrix ─────────────────────────────

    // Active campaigns that need exclusion coverage
    const eligibleTypes = new Set(['DISPLAY', 'VIDEO', 'DEMAND_GEN', 'PERFORMANCE_MAX']);
    const eligibleCampaigns = campaigns.filter(row => {
        const status = row['campaign.status'] || '';
        const channelType = row['campaign.advertising_channel_type'] || '';
        const experimentType = row['campaign.experiment_type'] || '';
        return status === 'ENABLED' && eligibleTypes.has(channelType) && experimentType !== 'EXPERIMENT';
    }).map(row => ({
        id: row['campaign.id'] || '',
        name: row['campaign.name'] || '',
        channel_type: row['campaign.advertising_channel_type'] || '',
    }));

    // Build exclusion list inventory
    const lists = exclusionLists.map(row => ({
        id: row['shared_set.id'] || '',
        name: row['shared_set.name'] || '',
        member_count: num(row['shared_set.member_count']),
        reference_count: num(row['shared_set.reference_count']),
        resource_name: row['shared_set.resource_name'] || '',
    }));

    // Build campaign → linked lists mapping
    const campaignListLinks = {};
    for (const row of listLinks) {
        const campaignId = row['campaign.id'] || '';
        const listName = row['shared_set.name'] || '';
        const listId = row['shared_set.id'] || '';
        if (!campaignListLinks[campaignId]) campaignListLinks[campaignId] = [];
        campaignListLinks[campaignId].push({ id: listId, name: listName });
    }

    // Build coverage matrix
    const coverageMatrix = eligibleCampaigns.map(c => ({
        campaign: c.name,
        campaign_id: c.id,
        channel_type: c.channel_type,
        lists_linked: (campaignListLinks[c.id] || []).map(l => l.name),
    }));

    const uncovered = coverageMatrix.filter(c => c.lists_linked.length === 0);
    const partiallyCovered = coverageMatrix.filter(c => c.lists_linked.length > 0 && c.lists_linked.length < lists.length);
    const fullyCovered = coverageMatrix.filter(c => c.lists_linked.length >= lists.length && lists.length > 0);

    const campaignCoverage = {
        total_eligible_campaigns: eligibleCampaigns.length,
        fully_covered: fullyCovered.length,
        partially_covered: partiallyCovered.length,
        uncovered: uncovered.length,
        uncovered_campaigns: uncovered.map(c => ({
            id: c.campaign_id,
            name: c.campaign,
            channel_type: c.channel_type,
        })),
        coverage_matrix: coverageMatrix,
    };

    // ── PL-D09: List hygiene analysis ────────────────────────────────

    const LIST_CAPACITY = 65000;

    // Build list items by list ID for overlap analysis
    const listItemsByList = {};
    for (const row of listItems) {
        const listId = row['shared_set.id'] || '';
        const placement = row['shared_criterion.placement.url'] ||
                          row['shared_criterion.youtube_channel.channel_id'] ||
                          row['shared_criterion.youtube_video.video_id'] ||
                          row['shared_criterion.mobile_app_category.mobile_app_category_constant'] || '';
        if (!listItemsByList[listId]) listItemsByList[listId] = new Set();
        if (placement) listItemsByList[listId].add(placement.toLowerCase());
    }

    // Cross-list overlap count
    let crossListOverlaps = 0;
    const listIds = Object.keys(listItemsByList);
    for (let i = 0; i < listIds.length; i++) {
        for (let j = i + 1; j < listIds.length; j++) {
            const setA = listItemsByList[listIds[i]];
            const setB = listItemsByList[listIds[j]];
            for (const item of setA) {
                if (setB.has(item)) crossListOverlaps++;
            }
        }
    }

    const listHygiene = {
        total_lists: lists.length,
        lists: lists.map(l => {
            const capacityPct = (l.member_count / LIST_CAPACITY * 100).toFixed(1);
            let status = 'OK';
            if (l.reference_count === 0) status = 'UNUSED';
            else if (l.member_count / LIST_CAPACITY > 0.8) status = 'NEAR_CAPACITY';
            return {
                name: l.name,
                id: l.id,
                member_count: l.member_count,
                capacity_pct: parseFloat(capacityPct),
                reference_count: l.reference_count,
                status,
            };
        }),
        cross_list_overlaps: crossListOverlaps,
    };

    // ── Output ───────────────────────────────────────────────────────

    const result = {
        app_audit: appAudit,
        campaign_coverage: campaignCoverage,
        list_hygiene: listHygiene,
    };

    const outputDir = dirname(outputPath);
    if (!existsSync(outputDir)) mkdirSync(outputDir, { recursive: true });
    writeFileSync(outputPath, JSON.stringify(result, null, 2), 'utf8');

    console.log(`\nExclusion Coverage Analysis Complete`);
    console.log(`  App categories: ${appAudit.excluded_count}/${appAudit.total_categories} excluded (${missingCategories.length} missing)`);
    console.log(`  App spend: $${appAudit.app_placement_spend_dollars} (${appAudit.app_spend_share_pct}% of total) with ${appAudit.app_placement_conversions} conversions`);
    console.log(`  Campaign coverage: ${fullyCovered.length} full, ${partiallyCovered.length} partial, ${uncovered.length} uncovered (of ${eligibleCampaigns.length})`);
    console.log(`  Exclusion lists: ${lists.length} lists, ${crossListOverlaps} cross-list overlaps`);
    console.log(`\nOutput: ${outputPath}`);
}

run();
