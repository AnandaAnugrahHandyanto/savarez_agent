#!/usr/bin/env node

/**
 * Placement Performance Analysis — placement-auditor
 *
 * Processes raw placement CSVs and flags violations for PL-D02, PL-D03, PL-D04, PL-D07.
 * Outputs placement-flags.csv (flagged items only) + placements-for-review.csv (top 1000 by spend for sub-agent).
 *
 * Usage:
 *   node analyze-placement-performance.js \
 *     --performance-csv=context/google-ads/data/placement-performance.csv \
 *     --detail-csv=context/google-ads/data/placement-detail.csv \
 *     --pmax-csv=context/google-ads/data/pmax-placements.csv \
 *     --domain-patterns=.claude/skills/placement-auditor/reference/domain-patterns.json \
 *     --campaigns-csv=context/google-ads/data/campaigns.csv \
 *     --portfolios-csv=context/google-ads/data/bidding-strategies.csv \
 *     --vtc-primary-csv=context/google-ads/data/placement-vtc-primary.csv \
 *     --output=context/google-ads/data/placement-flags.csv
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

const perfCsvPath = resolve(_projectRoot, args['performance-csv'] || '');
const detailCsvPath = resolve(_projectRoot, args['detail-csv'] || '');
const pmaxCsvPath = resolve(_projectRoot, args['pmax-csv'] || '');
const domainPatternsPath = resolve(_projectRoot, args['domain-patterns'] || '');
const campaignsCsvPath = resolve(_projectRoot, args['campaigns-csv'] || '');
const portfoliosCsvPath = args['portfolios-csv']
    ? resolve(_projectRoot, args['portfolios-csv'])
    : resolve(_projectRoot, 'context/google-ads/data/bidding-strategies.csv');
const vtcPrimaryCsvPath = resolve(_projectRoot, args['vtc-primary-csv'] || 'context/google-ads/data/placement-vtc-primary.csv');
const outputPath = resolve(_projectRoot, args['output'] || 'context/google-ads/data/placement-flags.csv');

// ── Load config ─────────────────────────────────────────────────────
let placementConfig = {};
try {
    const configPath = resolve(_projectRoot, 'config/ads-context.config.json');
    if (existsSync(configPath)) {
        const fullConfig = JSON.parse(readFileSync(configPath, 'utf8'));
        placementConfig = fullConfig.placementAudit || {};
    }
} catch (e) { /* use defaults */ }

const CFG = {
    extremeCpaMultiplier: placementConfig.extremeCpaMultiplier ?? 3.0,
    highRoasMultiplier: placementConfig.highRoasMultiplier ?? 0.5,
    minClicks: placementConfig.minClicks ?? 50,
    minWasteSpend: placementConfig.minWasteSpend ?? 50,
    vtcDiscountFactor: placementConfig.vtcDiscountFactor ?? 0.3,
    useVtcInWasteCheck: placementConfig.useVtcInWasteCheck ?? true,
};

// ── Validation ──────────────────────────────────────────────────────

if (!args['performance-csv']) {
    console.error('Error: --performance-csv is required');
    process.exit(1);
}

// ── URL Normalization ────────────────────────────────────────────────

function normalizeUrl(url) {
    if (!url) return '';
    let normalized = url.trim();
    normalized = normalized.replace(/^https?:\/\//i, '');
    normalized = normalized.replace(/^www\./i, '');
    normalized = normalized.replace(/^m\./i, '');
    normalized = normalized.replace(/\/+$/, '');
    return normalized;
}

// ── Load CSV ─────────────────────────────────────────────────────────

function loadCsv(filePath) {
    if (!existsSync(filePath)) {
        console.log(`Note: ${filePath} not found, skipping`);
        return [];
    }
    const content = readFileSync(filePath, 'utf8');
    if (!content.trim()) return [];
    return parse(content, { columns: true, skip_empty_lines: true, relax_column_count: true });
}

// ── Load domain patterns ─────────────────────────────────────────────

function loadDomainPatterns(filePath) {
    if (!existsSync(filePath)) {
        console.log('Note: domain-patterns.json not found, domain checks will be skipped');
        return null;
    }
    return JSON.parse(readFileSync(filePath, 'utf8'));
}

// ── Google-owned check ───────────────────────────────────────────────

function isGoogleOwned(placement, patterns) {
    if (!patterns) return false;
    const normalized = normalizeUrl(placement).toLowerCase();
    return patterns.google_owned_placements.some(gp => {
        const normalGp = normalizeUrl(gp).toLowerCase();
        return normalized === normalGp || normalized.startsWith(normalGp + '/');
    });
}

// ── Standard post-query filters ──────────────────────────────────────

function applyStandardFilters(rows) {
    return rows.filter(row => {
        if (row['campaign.experiment_type'] === 'EXPERIMENT') return false;
        if (row['campaign.serving_status'] === 'ENDED') return false;
        return true;
    });
}

// ── Domain pattern matching ──────────────────────────────────────────

function checkDomainPatterns(placement, patterns) {
    if (!patterns) return null;
    const normalized = normalizeUrl(placement).toLowerCase();
    const domainPart = normalized.split('.')[0] || '';
    const tld = '.' + normalized.split('.').pop();

    // Non-Latin/Punycode domains (check first — almost always irrelevant in Display)
    if (patterns.non_latin_domain_patterns) {
        for (const pat of patterns.non_latin_domain_patterns) {
            if (new RegExp(pat, 'i').test(normalized)) {
                return { flag_type: 'RANDOM_DOMAIN', flag_detail: 'Punycode/IDN domain — likely irrelevant' };
            }
        }
    }

    // Parked domains
    if (patterns.parked_domain_patterns) {
        for (const pat of patterns.parked_domain_patterns) {
            if (new RegExp(pat, 'i').test(normalized)) {
                return { flag_type: 'PARKED_DOMAIN', flag_detail: `Matches parked domain pattern: ${pat}` };
            }
        }
    }

    // MFA patterns
    if (patterns.mfa_patterns) {
        for (const pat of patterns.mfa_patterns) {
            if (new RegExp(pat, 'i').test(normalized)) {
                return { flag_type: 'MFA_SITE', flag_detail: `Matches MFA pattern: ${pat}` };
            }
        }
    }

    // Random domain indicators — regex patterns (min_length 6)
    const minLen = patterns.random_domain_indicators?.min_length_for_random_check ?? 8;
    if (domainPart.length >= minLen && patterns.random_domain_indicators?.patterns) {
        for (const pat of patterns.random_domain_indicators.patterns) {
            if (new RegExp(pat, 'i').test(normalized)) {
                return { flag_type: 'RANDOM_DOMAIN', flag_detail: 'Domain name appears auto-generated' };
            }
        }
    }

    // Random domain indicators — statistical checks (min_length 10 to avoid false positives on short brand names)
    const minLenRatio = patterns.random_domain_indicators?.min_length_for_ratio_check ?? 10;
    if (domainPart.length >= minLenRatio) {
        // Consonant ratio check
        const consonants = domainPart.replace(/[aeiou0-9-_.]/gi, '').length;
        const ratio = consonants / domainPart.length;
        if (ratio >= (patterns.random_domain_indicators?.min_consonant_ratio ?? 0.7)) {
            return { flag_type: 'RANDOM_DOMAIN', flag_detail: `High consonant ratio (${(ratio * 100).toFixed(0)}%) suggests auto-generated domain` };
        }

        // Numeric ratio check
        const numerics = domainPart.replace(/[^0-9]/g, '').length;
        const numRatio = numerics / domainPart.length;
        if (numRatio >= (patterns.random_domain_indicators?.min_numeric_ratio ?? 0.4)) {
            return { flag_type: 'RANDOM_DOMAIN', flag_detail: `High numeric ratio (${(numRatio * 100).toFixed(0)}%) suggests auto-generated domain` };
        }
    }

    // Entropy / DGA detection (independent of min_length gate)
    if (patterns.random_domain_indicators?.entropy_patterns) {
        for (const pat of patterns.random_domain_indicators.entropy_patterns) {
            if (new RegExp(pat, 'i').test(normalized)) {
                return { flag_type: 'RANDOM_DOMAIN', flag_detail: 'Domain matches DGA entropy pattern' };
            }
        }
    }

    // Two-tier high-risk TLD system (with backward compat for old single-list field)
    if (patterns.high_risk_tlds_tier1?.includes(tld)) {
        // Tier 1: auto-flag — Freenom + ultra-cheap gTLDs with >95% spam rate
        return { flag_type: 'HIGH_RISK_TLD', flag_detail: `Tier 1 high-risk TLD (${tld}) — auto-flagged` };
    }

    if (patterns.high_risk_tlds_tier2?.includes(tld)) {
        // Tier 2: flag with low bar for combined signals
        if (domainPart.length <= 10 || /\d/.test(domainPart) || domainPart.includes('-') || !/[aeiou]{2,}/i.test(domainPart)) {
            return { flag_type: 'HIGH_RISK_TLD', flag_detail: `Tier 2 high-risk TLD (${tld}) with suspicious domain name` };
        }
    }

    // Backward compat: fall back to old single high_risk_tlds field
    if (!patterns.high_risk_tlds_tier1 && !patterns.high_risk_tlds_tier2 && patterns.high_risk_tlds?.includes(tld)) {
        if (domainPart.length <= 5 || /\d{3,}/.test(domainPart) || /^[a-z]{2,3}\d+/.test(domainPart)) {
            return { flag_type: 'HIGH_RISK_TLD', flag_detail: `High-risk TLD (${tld}) combined with suspicious domain name` };
        }
    }

    return null;
}

// ── Numeric helpers ──────────────────────────────────────────────────

function num(val) {
    const n = parseFloat(val);
    return isNaN(n) ? 0 : n;
}

// Note: query.js already converts _micros fields to dollars — no division needed here

// ── Main analysis ────────────────────────────────────────────────────

function run() {
    const domainPatterns = loadDomainPatterns(domainPatternsPath);

    // Load CSVs
    let perfRows = applyStandardFilters(loadCsv(perfCsvPath));
    let detailRows = applyStandardFilters(loadCsv(detailCsvPath));
    let pmaxRows = applyStandardFilters(loadCsv(pmaxCsvPath));

    console.log(`Loaded: ${perfRows.length} group placements, ${detailRows.length} detail placements, ${pmaxRows.length} PMax placements`);

    // Deduplicate by normalized placement + campaign (sum metrics)
    // Key uses lowercase for case-insensitive dedup; placement preserves original case
    const deduped = new Map();
    for (const row of perfRows) {
        const placement = normalizeUrl(row['group_placement_view.placement'] || '');
        const campaignId = row['campaign.id'] || '';
        const key = `${placement.toLowerCase()}||${campaignId}`;
        if (deduped.has(key)) {
            const existing = deduped.get(key);
            existing.impressions += num(row['metrics.impressions']);
            existing.clicks += num(row['metrics.clicks']);
            existing.cost += num(row['metrics.cost']);
            existing.conversions += num(row['metrics.conversions']);
            existing.conversions_value += num(row['metrics.conversions_value']);
            existing.all_conversions += num(row['metrics.all_conversions']);
            existing.view_through_conversions += num(row['metrics.view_through_conversions']);
        } else {
            deduped.set(key, {
                placement,
                display_name: row['group_placement_view.display_name'] || '',
                target_url: row['group_placement_view.target_url'] || '',
                placement_type: row['group_placement_view.placement_type'] || '',
                campaign_id: campaignId,
                campaign_name: row['campaign.name'] || '',
                campaign_channel_type: row['campaign.advertising_channel_type'] || '',
                ad_group_id: row['ad_group.id'] || '',
                ad_group_name: row['ad_group.name'] || '',
                impressions: num(row['metrics.impressions']),
                clicks: num(row['metrics.clicks']),
                cost: num(row['metrics.cost']),
                conversions: num(row['metrics.conversions']),
                conversions_value: num(row['metrics.conversions_value']),
                all_conversions: num(row['metrics.all_conversions']),
                view_through_conversions: num(row['metrics.view_through_conversions']),
            });
        }
    }
    perfRows = Array.from(deduped.values());

    // ── Load primary VTC lookup (from resolve-primary-vtc.js) ──────────
    // This file contains VTCs filtered to primary conversion actions only,
    // avoiding contamination from secondary actions (page views, scroll depth, etc.)
    const primaryVtcLookup = new Map();
    const vtcPrimaryRows = loadCsv(vtcPrimaryCsvPath);
    if (vtcPrimaryRows.length > 0) {
        for (const row of vtcPrimaryRows) {
            const placement = normalizeUrl(row['placement'] || '');
            const campaignId = row['campaign_id'] || '';
            const key = `${placement.toLowerCase()}||${campaignId}`;
            const vtc = num(row['primary_vtc']);
            primaryVtcLookup.set(key, (primaryVtcLookup.get(key) || 0) + vtc);
        }
        console.log(`Loaded primary VTC lookup: ${primaryVtcLookup.size} placement+campaign combos`);
    } else {
        console.log('Warning: placement-vtc-primary.csv not found — falling back to raw metrics.view_through_conversions (may include secondary actions)');
    }
    const usePrimaryVtc = primaryVtcLookup.size > 0;

    // Compute CTR, CPA, ROAS, and adjusted conversions per row
    const vtcDiscountFactor = CFG.useVtcInWasteCheck ? CFG.vtcDiscountFactor : 0;
    for (const row of perfRows) {
        row.ctr = row.impressions > 0 ? row.clicks / row.impressions : 0;
        row.cost_per_conversion = row.conversions > 0 ? row.cost / row.conversions : 0;
        row.roas = row.cost > 0 ? row.conversions_value / row.cost : 0;

        // Use primary-only VTC when available; fall back to raw VTC
        const key = `${row.placement.toLowerCase()}||${row.campaign_id}`;
        const vtcForCalc = usePrimaryVtc ? (primaryVtcLookup.get(key) || 0) : row.view_through_conversions;
        row.primary_vtc = usePrimaryVtc ? (primaryVtcLookup.get(key) || 0) : row.view_through_conversions;

        row.adjusted_conversions = row.conversions + (vtcForCalc * vtcDiscountFactor);
        row.secondary_conversions = row.all_conversions - row.conversions;
    }

    // ── Load portfolio bid strategies ───────────────────────────────────
    // Portfolio targets live on the bidding_strategy resource, not the campaign,
    // so campaign.target_cpa / campaign.target_roas return null for portfolio-attached
    // campaigns. Without this join we'd misclassify portfolio-constrained campaigns
    // as "unknown mode" and fall through to account-wide thresholds.
    const portfolioTargets = {};
    const portfolioRows = existsSync(portfoliosCsvPath) ? loadCsv(portfoliosCsvPath) : [];
    for (const p of portfolioRows) {
        const rn = p['bidding_strategy.resource_name'] || '';
        if (!rn) continue;
        const tCpa = num(p['bidding_strategy.target_cpa.target_cpa'])
                  || num(p['bidding_strategy.maximize_conversions.target_cpa']);
        const tRoas = num(p['bidding_strategy.target_roas.target_roas'])
                   || num(p['bidding_strategy.maximize_conversion_value.target_roas']);
        portfolioTargets[rn] = {
            name: p['bidding_strategy.name'] || '',
            target_cpa: tCpa,
            target_roas: tRoas,
        };
    }
    if (Object.keys(portfolioTargets).length > 0) {
        console.log(`Loaded portfolio targets for ${Object.keys(portfolioTargets).length} bid strategies`);
    }

    // ── Load campaign targets from campaigns.csv ────────────────────────
    // Priority order: inline campaign target → portfolio target → none.
    const campaignTargets = {};
    const campaignRows = loadCsv(campaignsCsvPath);
    for (const row of campaignRows) {
        const cid = row['campaign.id'] || '';
        if (!cid) continue;
        let tCpa = num(row['campaign.maximize_conversions.target_cpa']) || num(row['campaign.target_cpa.target_cpa']);
        let tRoas = num(row['campaign.maximize_conversion_value.target_roas']) || num(row['campaign.target_roas.target_roas']);
        let targetSource = (tCpa > 0 || tRoas > 0) ? 'campaign_inline' : 'none';
        let portfolioName = '';

        if (targetSource === 'none') {
            const portfolioRef = row['campaign.bidding_strategy'] || '';
            if (portfolioRef && portfolioTargets[portfolioRef]) {
                const pt = portfolioTargets[portfolioRef];
                if (pt.target_cpa > 0 || pt.target_roas > 0) {
                    tCpa = pt.target_cpa;
                    tRoas = pt.target_roas;
                    targetSource = 'portfolio';
                    portfolioName = pt.name;
                }
            }
        }

        let mode = 'unknown';
        if (tRoas > 0) mode = 'roas';
        else if (tCpa > 0) mode = 'cpa';
        campaignTargets[cid] = {
            target_cpa: tCpa,
            target_roas: tRoas,
            mode,
            target_source: targetSource,
            portfolio_name: portfolioName,
        };
    }
    console.log(`Loaded campaign targets for ${Object.keys(campaignTargets).length} campaigns`);

    // Compute campaign averages (fallback when no target set)
    const campaignStats = {};
    for (const row of perfRows) {
        const cid = row.campaign_id;
        if (!campaignStats[cid]) {
            campaignStats[cid] = {
                name: row.campaign_name,
                channel_type: row.campaign_channel_type,
                total_cost: 0,
                total_clicks: 0,
                total_impressions: 0,
                total_conversions: 0,
            };
        }
        const cs = campaignStats[cid];
        cs.total_cost += row.cost;
        cs.total_clicks += row.clicks;
        cs.total_impressions += row.impressions;
        cs.total_conversions += row.conversions;
    }

    const campaignAvgs = {};
    for (const [cid, cs] of Object.entries(campaignStats)) {
        campaignAvgs[cid] = {
            name: cs.name,
            avg_cpa: cs.total_conversions > 0 ? cs.total_cost / cs.total_conversions : 0,
            avg_ctr: cs.total_impressions > 0 ? cs.total_clicks / cs.total_impressions : 0,
        };
    }

    // ── Flag violations ──────────────────────────────────────────────

    const flags = [];
    const googleOwnedSkipped = new Set();

    for (const row of perfRows) {
        // Google-owned: flag and skip all other checks (can't exclude these)
        if (isGoogleOwned(row.placement, domainPatterns)) {
            googleOwnedSkipped.add(row.placement);
            flags.push({
                ...row,
                campaign_avg_cpa: campaignAvgs[row.campaign_id]?.avg_cpa || 0,
                campaign_avg_ctr: campaignAvgs[row.campaign_id]?.avg_ctr || 0,
                flag_type: 'GOOGLE_OWNED',
                flag_severity: 'Info',
                flag_detail: 'Google-owned surface — cannot be excluded',
            });
            continue;
        }

        const avgCpa = campaignAvgs[row.campaign_id]?.avg_cpa || 0;
        const avgCtr = campaignAvgs[row.campaign_id]?.avg_ctr || 0;
        const target = campaignTargets[row.campaign_id] || {};
        const benchmarkCpa = target.target_cpa || avgCpa;
        const benchmarkRoas = target.target_roas || 0;
        const campaignMode = target.mode || (avgCpa > 0 ? 'cpa' : 'unknown');
        const minWasteSpend = CFG.minWasteSpend;

        const addFlag = (flag_type, flag_severity, flag_detail) => {
            flags.push({ ...row, campaign_avg_cpa: avgCpa, campaign_avg_ctr: avgCtr, flag_type, flag_severity, flag_detail });
        };

        // PL-D02: Zero-click (1000+ impressions, 0 clicks)
        if (row.impressions >= 1000 && row.clicks === 0) {
            addFlag('ZERO_CLICK', 'Medium', `${row.impressions} impressions with 0 clicks`);
        }

        // PL-D02: Accidental clicks (CTR > 10%, exclude converting placements)
        if (row.ctr > 0.10 && row.clicks > 0 && row.adjusted_conversions === 0) {
            addFlag('HIGH_CTR_ACCIDENTAL', 'High', `CTR ${(row.ctr * 100).toFixed(1)}% suggests accidental clicks`);
        }

        // PL-D02: Invalid traffic (CTR > 3%, 0 adjusted conversions, 100+ clicks)
        if (row.ctr > 0.03 && row.adjusted_conversions === 0 && row.clicks >= CFG.minClicks) {
            addFlag('HIGH_CTR_NO_CONV', 'High', `CTR ${(row.ctr * 100).toFixed(1)}% with 0 conversions over ${row.clicks} clicks`);
        }

        // PL-D02: Zero-conversion waste (significant spend, 0 adjusted conversions)
        if (row.adjusted_conversions === 0 && row.clicks > 0) {
            const wasteThreshold = benchmarkCpa > 0 ? benchmarkCpa * 2 : minWasteSpend;
            if (row.cost > wasteThreshold) {
                addFlag('ZERO_CONV_WASTE', 'High', `$${row.cost.toFixed(2)} spent (${(row.cost / wasteThreshold).toFixed(1)}x threshold) with 0 conversions`);
            }
        }

        // PL-D02: High CPA (CPA > 3x benchmark, 100+ clicks) — CPA mode
        if (benchmarkCpa > 0 && row.cost_per_conversion > 0 && row.cost_per_conversion > benchmarkCpa * CFG.extremeCpaMultiplier && row.clicks >= CFG.minClicks) {
            const label = target.target_cpa ? 'target CPA' : 'campaign avg CPA';
            addFlag('HIGH_CPA', 'High', `CPA $${row.cost_per_conversion.toFixed(2)} is ${(row.cost_per_conversion / benchmarkCpa).toFixed(1)}x ${label} ($${benchmarkCpa.toFixed(2)})`);
        }

        // PL-D02: Low ROAS (ROAS < 0.5x target ROAS) — ROAS mode only
        if (campaignMode === 'roas' && benchmarkRoas > 0 && row.conversions > 0 && row.roas < benchmarkRoas * CFG.highRoasMultiplier && row.clicks >= CFG.minClicks) {
            addFlag('LOW_ROAS', 'High', `ROAS ${row.roas.toFixed(2)} is ${(row.roas / benchmarkRoas).toFixed(2)}x target ROAS (${benchmarkRoas.toFixed(2)})`);
        }

        // PL-D04: Known-bad domain patterns
        if (row.placement_type === 'WEBSITE' || !row.placement_type) {
            const domainFlag = checkDomainPatterns(row.placement, domainPatterns);
            if (domainFlag) {
                addFlag(domainFlag.flag_type, 'High', domainFlag.flag_detail);
            }
        }
    }

    // PL-D03: Video placement quality (from detail view)
    for (const row of detailRows) {
        const placement = normalizeUrl(row['detail_placement_view.placement'] || '');
        const channelType = row['campaign.advertising_channel_type'] || '';
        if (channelType !== 'VIDEO' && channelType !== 'DEMAND_GEN') continue;

        if (isGoogleOwned(placement, domainPatterns)) continue;

        const campaignId = row['campaign.id'] || '';
        const avgCpa = campaignAvgs[campaignId]?.avg_cpa || 0;
        const detailTarget = campaignTargets[campaignId] || {};
        const benchmarkCpa = detailTarget.target_cpa || avgCpa;
        const cost = num(row['metrics.cost']);
        const conversions = num(row['metrics.conversions']);
        const ctr = num(row['metrics.ctr']);

        // Video with zero conversions + high spend (>2x benchmark CPA)
        if (conversions === 0 && benchmarkCpa > 0 && cost > benchmarkCpa * 2) {
            flags.push({
                placement,
                display_name: row['detail_placement_view.display_name'] || '',
                target_url: row['detail_placement_view.target_url'] || '',
                placement_type: row['detail_placement_view.placement_type'] || '',
                campaign_id: campaignId,
                campaign_name: row['campaign.name'] || '',
                campaign_channel_type: channelType,
                ad_group_id: row['ad_group.id'] || '',
                ad_group_name: row['ad_group.name'] || '',
                impressions: num(row['metrics.impressions']),
                clicks: num(row['metrics.clicks']),
                ctr,
                cost,
                conversions: 0,
                cost_per_conversion: 0,
                conversions_value: num(row['metrics.conversions_value']),
                // detail GAQL doesn't query all_conversions/view_through_conversions
                all_conversions: 0,
                view_through_conversions: 0,
                campaign_avg_cpa: avgCpa,
                campaign_avg_ctr: campaignAvgs[campaignId]?.avg_ctr || 0,
                flag_type: 'VIDEO_NO_CONV',
                flag_severity: 'High',
                flag_detail: `Video placement spent $${cost.toFixed(2)} (${(cost / benchmarkCpa).toFixed(1)}x ${detailTarget.target_cpa ? 'target' : 'avg'} CPA) with 0 conversions`,
            });
        }

        // Video CTR anomaly (CTR > 10%)
        if (ctr > 0.10 && num(row['metrics.clicks']) > 0) {
            flags.push({
                placement,
                display_name: row['detail_placement_view.display_name'] || '',
                target_url: row['detail_placement_view.target_url'] || '',
                placement_type: row['detail_placement_view.placement_type'] || '',
                campaign_id: campaignId,
                campaign_name: row['campaign.name'] || '',
                campaign_channel_type: channelType,
                ad_group_id: row['ad_group.id'] || '',
                ad_group_name: row['ad_group.name'] || '',
                impressions: num(row['metrics.impressions']),
                clicks: num(row['metrics.clicks']),
                ctr,
                cost,
                conversions,
                cost_per_conversion: conversions > 0 ? cost / conversions : 0,
                conversions_value: num(row['metrics.conversions_value']),
                // detail GAQL doesn't query all_conversions/view_through_conversions
                all_conversions: 0,
                view_through_conversions: 0,
                campaign_avg_cpa: avgCpa,
                campaign_avg_ctr: campaignAvgs[campaignId]?.avg_ctr || 0,
                flag_type: 'VIDEO_CTR_ANOMALY',
                flag_severity: 'Medium',
                flag_detail: `Video CTR ${(ctr * 100).toFixed(1)}% is abnormally high`,
            });
        }
    }

    // PL-D07: PMax brand safety (domain patterns only — impressions only, no perf flags)
    for (const row of pmaxRows) {
        const placement = normalizeUrl(row['performance_max_placement_view.placement'] || '');
        if (isGoogleOwned(placement, domainPatterns)) continue;

        const placementType = row['performance_max_placement_view.placement_type'] || '';
        if (placementType === 'WEBSITE' || !placementType) {
            const domainFlag = checkDomainPatterns(placement, domainPatterns);
            if (domainFlag) {
                flags.push({
                    placement,
                    display_name: row['performance_max_placement_view.display_name'] || '',
                    target_url: row['performance_max_placement_view.target_url'] || '',
                    placement_type: placementType,
                    campaign_id: row['campaign.id'] || '',
                    campaign_name: row['campaign.name'] || '',
                    campaign_channel_type: 'PERFORMANCE_MAX',
                    ad_group_id: '',
                    ad_group_name: '',
                    impressions: num(row['metrics.impressions']),
                    clicks: 0,
                    ctr: 0,
                    cost: 0,
                    conversions: 0,
                    cost_per_conversion: 0,
                    conversions_value: 0,
                    all_conversions: 0,
                    view_through_conversions: 0,
                    campaign_avg_cpa: 0,
                    campaign_avg_ctr: 0,
                    flag_type: 'PMAX_BAD_DOMAIN',
                    flag_severity: 'Medium',
                    flag_detail: domainFlag.flag_detail,
                });
            }
        }
    }

    // ── Keyword pre-filter (catch obvious content patterns before sub-agent) ──

    const contentKeywordPatterns = {
        KIDS_CONTENT: {
            severity: 'Critical',
            patterns: [
                /\b(kids|children|child|nursery|cartoon|lullaby|lullabies|toddler|baby\s?shark|preschool|kindergarten)\b/i,
                /\b(sesame|peppa|cocomelon|paw\s?patrol|bluey|dora|barbie|disney\s?junior)\b/i,
                /\b(kinder|niños|enfants|crianças|дети|çocuk|anak|أطفال|子供|बच्चे|아이들)\b/i,
                /\b(bedtime\s+stor|fairy\s+tale|nursery\s+rhyme|kids\s+song|children.?s\s+song)\b/i,
                /\bmade\s+for\s+kids\b/i,
            ],
        },
        MUSIC_PASSIVE: {
            severity: 'Medium',
            patterns: [
                /\b(lyrics?|karaoke|official\s+audio|full\s+album|audio\s+only|lyric\s+video)\b/i,
                /\bvevo\b/i,
                /\b(歌詞|가사)\b/i,
            ],
        },
        SPAM_CONTENT: {
            severity: 'High',
            patterns: [
                /\b(top\s+\d+|compilation|best\s+of\b|best\s+clips|HD\s+clips|funny\s+moments|epic\s+fail)\b/i,
                /\b(satisfying\s+video|oddly\s+satisfying|try\s+not\s+to|you\s+won.?t\s+believe)\b/i,
                /\b(best\s+videos?\s+\d{4}|top\s+clips|viral\s+video)\b/i,
            ],
        },
    };

    const allPlacements = [...perfRows, ...pmaxRows.map(r => ({
        placement: normalizeUrl(r['performance_max_placement_view.placement'] || ''),
        display_name: r['performance_max_placement_view.display_name'] || '',
        target_url: r['performance_max_placement_view.target_url'] || '',
        placement_type: r['performance_max_placement_view.placement_type'] || '',
        campaign_id: r['campaign.id'] || '',
        campaign_name: r['campaign.name'] || '',
        campaign_channel_type: 'PERFORMANCE_MAX',
        impressions: num(r['metrics.impressions']),
        cost: 0,
    }))];

    // Run keyword patterns on ALL placements (content safety flags apply regardless of performance flags)
    const contentFlaggedKeys = new Set(); // track placement+flagType to avoid duplicates
    let keywordCaughtCount = 0;
    for (const row of allPlacements) {
        if (isGoogleOwned(row.placement, domainPatterns)) continue;
        const name = row.display_name || '';
        if (!name) continue;
        for (const [flagType, cfg] of Object.entries(contentKeywordPatterns)) {
            const dedupKey = `${row.placement}||${flagType}`;
            if (contentFlaggedKeys.has(dedupKey)) continue;
            for (const pattern of cfg.patterns) {
                if (pattern.test(name)) {
                    flags.push({
                        placement: row.placement,
                        display_name: name,
                        target_url: row.target_url || '',
                        placement_type: row.placement_type || '',
                        campaign_id: row.campaign_id || '',
                        campaign_name: row.campaign_name || '',
                        campaign_channel_type: row.campaign_channel_type || '',
                        ad_group_id: row.ad_group_id || '',
                        ad_group_name: row.ad_group_name || '',
                        impressions: row.impressions || 0,
                        clicks: row.clicks || 0,
                        ctr: row.ctr || 0,
                        cost: row.cost || 0,
                        conversions: row.conversions || 0,
                        cost_per_conversion: row.cost_per_conversion || 0,
                        conversions_value: row.conversions_value || 0,
                        all_conversions: row.all_conversions || 0,
                        view_through_conversions: row.view_through_conversions || 0,
                        campaign_avg_cpa: campaignAvgs[row.campaign_id]?.avg_cpa || 0,
                        campaign_avg_ctr: campaignAvgs[row.campaign_id]?.avg_ctr || 0,
                        flag_type: flagType,
                        flag_severity: cfg.severity,
                        flag_detail: `Display name keyword match: "${name}"`,
                    });
                    contentFlaggedKeys.add(dedupKey);
                    keywordCaughtCount++;
                    break; // matched this category, check next category
                }
            }
        }
    }
    console.log(`Keyword pre-filter caught ${keywordCaughtCount} content flags`);

    // Filter out flagged + Google-owned, send top 300 by spend to sub-agent
    const flaggedPlacements = new Set(flags.map(f => f.placement));
    const forReview = allPlacements
        .filter(p => !flaggedPlacements.has(p.placement) && !isGoogleOwned(p.placement, domainPatterns))
        .sort((a, b) => (b.cost || 0) - (a.cost || 0))
        .slice(0, 300);

    const reviewOutputPath = outputPath.replace('placement-flags.csv', 'placements-for-review.csv');
    const reviewHeader = 'placement,display_name,placement_type,campaign_name,campaign_channel_type,impressions,cost';
    const reviewRows = forReview.map(r =>
        `"${r.placement}","${(r.display_name || '').replace(/"/g, '""')}","${r.placement_type}","${(r.campaign_name || '').replace(/"/g, '""')}","${r.campaign_channel_type}",${r.impressions},${r.cost || 0}`
    );
    const reviewDir = dirname(reviewOutputPath);
    if (!existsSync(reviewDir)) mkdirSync(reviewDir, { recursive: true });
    writeFileSync(reviewOutputPath, [reviewHeader, ...reviewRows].join('\n'), 'utf8');
    console.log(`Wrote ${forReview.length} placements to ${reviewOutputPath} for content review`);

    // ── Write placement-flags.csv ────────────────────────────────────

    const header = 'placement,display_name,placement_type,campaign_name,campaign_id,campaign_channel_type,impressions,clicks,ctr,cost,conversions,cost_per_conversion,conversions_value,view_through_conversions,all_conversions,campaign_avg_cpa,campaign_avg_ctr,flag_type,flag_severity,flag_detail';
    const csvRows = flags.map(f =>
        `"${f.placement}","${(f.display_name || '').replace(/"/g, '""')}","${f.placement_type}","${(f.campaign_name || '').replace(/"/g, '""')}","${f.campaign_id}","${f.campaign_channel_type}",${f.impressions},${f.clicks},${f.ctr.toFixed(4)},${(f.cost || 0).toFixed(2)},${f.conversions},${f.cost_per_conversion.toFixed(2)},${f.conversions_value || 0},${f.view_through_conversions || 0},${f.all_conversions || 0},${f.campaign_avg_cpa.toFixed(2)},${f.campaign_avg_ctr.toFixed(4)},"${f.flag_type}","${f.flag_severity}","${(f.flag_detail || '').replace(/"/g, '""')}"`
    );

    const outputDir = dirname(outputPath);
    if (!existsSync(outputDir)) mkdirSync(outputDir, { recursive: true });
    writeFileSync(outputPath, [header, ...csvRows].join('\n'), 'utf8');

    // ── Summary stats ───────────────────────────────���────────────────

    const flagsByType = {};
    for (const f of flags) {
        flagsByType[f.flag_type] = (flagsByType[f.flag_type] || 0) + 1;
    }

    const totalFlaggedSpend = flags.reduce((sum, f) => sum + (f.cost || 0), 0);

    // ── Placement type breakdown ──────────────────────────────────────
    const typeBreakdown = {};
    for (const row of perfRows) {
        const ptype = row.placement_type || 'UNKNOWN';
        if (!typeBreakdown[ptype]) {
            typeBreakdown[ptype] = { placements: 0, spend: 0, conversions: 0, conversions_value: 0, clicks: 0, impressions: 0 };
        }
        const t = typeBreakdown[ptype];
        t.placements++;
        t.spend += row.cost || 0;
        t.conversions += row.conversions || 0;
        t.conversions_value += row.conversions_value || 0;
        t.clicks += row.clicks || 0;
        t.impressions += row.impressions || 0;
    }
    for (const t of Object.values(typeBreakdown)) {
        t.cpa = t.conversions > 0 ? t.spend / t.conversions : 0;
        t.roas = t.spend > 0 ? t.conversions_value / t.spend : 0;
        t.ctr = t.impressions > 0 ? t.clicks / t.impressions : 0;
        // Round for readability
        t.spend = +t.spend.toFixed(2);
        t.cpa = +t.cpa.toFixed(2);
        t.roas = +t.roas.toFixed(2);
        t.ctr = +t.ctr.toFixed(4);
    }

    // ── Top wasters (0 conversions, ranked by spend) ────────────────
    const topWasters = perfRows
        .filter(r => r.conversions === 0 && r.cost > 0)
        .sort((a, b) => b.cost - a.cost)
        .slice(0, 20)
        .map(r => ({
            placement: r.placement,
            display_name: r.display_name,
            placement_type: r.placement_type,
            campaign_name: r.campaign_name,
            spend: +r.cost.toFixed(2),
            clicks: r.clicks,
            impressions: r.impressions,
            view_through_conversions: r.view_through_conversions || 0,
            primary_vtc: r.primary_vtc || 0,
        }));

    const summary = {
        vtc_source: usePrimaryVtc ? 'primary_only' : 'raw_all_actions',
        total_placements_analyzed: perfRows.length + detailRows.length + pmaxRows.length,
        total_flagged: flags.length,
        flags_by_type: flagsByType,
        google_owned_skipped: Array.from(googleOwnedSkipped),
        placements_sent_to_content_reviewer: forReview.length,
        total_flagged_spend: totalFlaggedSpend.toFixed(2),
        campaigns_analyzed: Object.keys(campaignStats).length,
        placement_type_breakdown: typeBreakdown,
        top_wasters: topWasters,
        campaign_benchmarks: Object.fromEntries(
            Object.entries(campaignStats).map(([cid, cs]) => {
                const avg = campaignAvgs[cid];
                const target = campaignTargets[cid] || {};
                return [cs.name, {
                    mode: target.mode || 'unknown',
                    target_cpa: target.target_cpa || null,
                    target_roas: target.target_roas || null,
                    avg_cpa: avg.avg_cpa.toFixed(2),
                    avg_ctr: avg.avg_ctr.toFixed(4),
                    benchmark_source: target.target_cpa || target.target_roas ? 'target' : 'average',
                }];
            })
        ),
    };

    // Write summary JSON
    const summaryPath = outputPath.replace('.csv', '-summary.json');
    writeFileSync(summaryPath, JSON.stringify(summary, null, 2), 'utf8');

    console.log(`\nPlacement Performance Analysis Complete`);
    console.log(`  Total placements analyzed: ${summary.total_placements_analyzed}`);
    console.log(`  Total flagged: ${summary.total_flagged}`);
    console.log(`  Flagged spend: $${summary.total_flagged_spend}`);
    console.log(`  Campaigns: ${summary.campaigns_analyzed}`);
    console.log(`  Flags by type:`);
    for (const [type, count] of Object.entries(flagsByType)) {
        console.log(`    ${type}: ${count}`);
    }
    console.log(`\nOutputs:`);
    console.log(`  Flags: ${outputPath}`);
    console.log(`  Summary: ${summaryPath}`);
    console.log(`  For review: ${reviewOutputPath}`);
}

run();
