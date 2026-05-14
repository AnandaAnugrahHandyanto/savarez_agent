#!/usr/bin/env node

/**
 * Resolve Primary VTC — placement-auditor
 *
 * Reads VTC data segmented by conversion action, filters to primary actions only,
 * and outputs a lookup CSV that analyze-placement-performance.js consumes.
 *
 * Primary action resolution (in priority order):
 *   1. Config: conversionActions in ads-context.config.json (explicit user preference)
 *   2. Fallback: conversion_action.primary_for_goal = true from conversions-audit.csv
 *
 * Usage:
 *   node resolve-primary-vtc.js \
 *     --vtc-csv=context/google-ads/data/placement-vtc-by-action.csv \
 *     --conversions-audit-csv=context/google-ads/data/conversions-audit.csv \
 *     --output=context/google-ads/data/placement-vtc-primary.csv
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

const vtcCsvPath = resolve(_projectRoot, args['vtc-csv'] || '');
const conversionsAuditCsvPath = resolve(_projectRoot, args['conversions-audit-csv'] || '');
const outputPath = resolve(_projectRoot, args['output'] || 'context/google-ads/data/placement-vtc-primary.csv');

// ── Validation ──────────────────────────────────────────────────────

if (!args['vtc-csv']) {
    console.error('Error: --vtc-csv is required');
    process.exit(1);
}

// ── Load CSV ────────────────────────────────────────────────────────

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

// ── URL Normalization (must match analyze-placement-performance.js) ──

function normalizeUrl(url) {
    if (!url) return '';
    let normalized = url.trim();
    normalized = normalized.replace(/^https?:\/\//i, '');
    normalized = normalized.replace(/^www\./i, '');
    normalized = normalized.replace(/^m\./i, '');
    normalized = normalized.replace(/\/+$/, '');
    return normalized;
}

// ── Main ────────────────────────────────────────────────────────────

function run() {
    // 1. Resolve primary conversion action names
    const primaryActionNames = resolvePrimaryActions();

    if (primaryActionNames.size === 0) {
        console.error('Warning: No primary conversion actions found. Output will have 0 VTC for all placements.');
    } else {
        console.log(`Primary conversion actions (${primaryActionNames.size}): ${[...primaryActionNames].join(', ')}`);
    }

    // 2. Load segmented VTC data
    const vtcRows = loadCsv(vtcCsvPath);
    console.log(`Loaded ${vtcRows.length} VTC rows (segmented by conversion action)`);

    if (vtcRows.length === 0) {
        writeEmptyOutput();
        return;
    }

    // 3. Filter to primary actions and aggregate per placement+campaign
    const aggregated = new Map();
    let primaryRows = 0;
    let secondaryRows = 0;

    for (const row of vtcRows) {
        const actionName = row['segments.conversion_action_name'] || '';
        const vtc = num(row['metrics.view_through_conversions']);

        if (vtc === 0) continue;

        const placement = normalizeUrl(row['group_placement_view.placement'] || '');
        const campaignId = row['campaign.id'] || '';
        const key = `${placement.toLowerCase()}||${campaignId}`;

        if (primaryActionNames.has(actionName)) {
            primaryRows++;
            if (aggregated.has(key)) {
                const existing = aggregated.get(key);
                existing.primary_vtc += vtc;
            } else {
                aggregated.set(key, { placement, campaign_id: campaignId, primary_vtc: vtc });
            }
        } else {
            secondaryRows++;
        }
    }

    console.log(`VTC rows: ${primaryRows} primary, ${secondaryRows} secondary (filtered out)`);
    console.log(`Unique placement+campaign combos with primary VTC: ${aggregated.size}`);

    // 4. Write output
    const header = 'placement,campaign_id,primary_vtc';
    const csvRows = Array.from(aggregated.values()).map(r =>
        `"${r.placement}","${r.campaign_id}",${r.primary_vtc}`
    );

    const outputDir = dirname(outputPath);
    if (!existsSync(outputDir)) mkdirSync(outputDir, { recursive: true });
    writeFileSync(outputPath, [header, ...csvRows].join('\n'), 'utf8');

    console.log(`\nWrote ${csvRows.length} rows to ${outputPath}`);
}

function resolvePrimaryActions() {
    const primaryNames = new Set();

    // Priority 1: Config conversionActions
    try {
        const configPath = resolve(_projectRoot, 'config/ads-context.config.json');
        if (existsSync(configPath)) {
            const config = JSON.parse(readFileSync(configPath, 'utf8'));
            const configActions = config.googleAds?.conversionActions || [];
            if (configActions.length > 0) {
                for (const name of configActions) {
                    primaryNames.add(name);
                }
                console.log(`Resolved ${primaryNames.size} primary actions from config.googleAds.conversionActions`);
                return primaryNames;
            }
        }
    } catch (e) {
        console.log('Note: Could not read config, falling back to conversions-audit.csv');
    }

    // Priority 2: Fallback to primary_for_goal from conversions-audit.csv
    const auditRows = loadCsv(conversionsAuditCsvPath);
    if (auditRows.length === 0) {
        console.log('Warning: No conversions-audit.csv found and no config conversionActions — cannot resolve primary actions');
        return primaryNames;
    }

    for (const row of auditRows) {
        const isPrimary = row['conversion_action.primary_for_goal'] === 'true';
        const status = row['conversion_action.status'] || '';
        const name = row['conversion_action.name'] || '';
        if (isPrimary && status === 'ENABLED' && name) {
            primaryNames.add(name);
        }
    }

    console.log(`Resolved ${primaryNames.size} primary actions from conversions-audit.csv (primary_for_goal=true, ENABLED)`);
    return primaryNames;
}

function writeEmptyOutput() {
    const header = 'placement,campaign_id,primary_vtc';
    const outputDir = dirname(outputPath);
    if (!existsSync(outputDir)) mkdirSync(outputDir, { recursive: true });
    writeFileSync(outputPath, header + '\n', 'utf8');
    console.log(`No VTC data — wrote empty output to ${outputPath}`);
}

run();
