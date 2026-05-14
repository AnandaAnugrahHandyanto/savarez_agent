#!/usr/bin/env node

/**
 * Quality Score — Customizer Integrity Analysis
 *
 * Reads:
 *   - customizer-attributes.csv       (attribute definitions)
 *   - ad-group-customizers.csv        (AG-level bindings)
 *   - keyword-customizers.csv         (keyword-level bindings)
 *   - campaign-customizers.csv        (campaign-level bindings)
 *   - customer-customizers.csv        (customer-level / account-wide bindings)
 *   - qs-ads.csv                      (RSAs — scans headlines/descriptions for {CUSTOMIZER.<name>})
 *
 * Writes:
 *   - qs-customizers.csv              (one row per ad group, summarising customizer state)
 *
 * Resolution order (Google Ads hierarchy): KEYWORD → AD_GROUP → CAMPAIGN → CUSTOMER
 * → inline ":default" fallback in the placeholder.
 *
 * The output feeds:
 *   - The Headline Test (Phase 1.5) — does the AG have dynamic headlines?
 *   - QS-D17 Customizer Integrity (INFO-only) — do any RSAs reference attributes that
 *     don't exist (BROKEN), or reference attributes with no binding at any level
 *     (EFFECTIVELY_STATIC — Google renders :default every time)?
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { parse } from 'csv-parse/sync';

const __dirname = dirname(fileURLToPath(import.meta.url));
let _projectRoot = __dirname;
while (_projectRoot !== '/' && !existsSync(resolve(_projectRoot, 'config'))) {
    _projectRoot = resolve(_projectRoot, '..');
}

const args = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const eqIndex = arg.indexOf('=');
        const key = arg.slice(0, eqIndex).replace(/^--/, '');
        const value = arg.slice(eqIndex + 1);
        if (key && value) acc[key] = value;
    }
    return acc;
}, {});

const dataDir = resolve(_projectRoot, 'context/google-ads/data');
const attrsPath = resolve(_projectRoot, args['attributes-csv'] || `${dataDir}/customizer-attributes.csv`);
const agBindingsPath = resolve(_projectRoot, args['ag-bindings-csv'] || `${dataDir}/ad-group-customizers.csv`);
const kwBindingsPath = resolve(_projectRoot, args['kw-bindings-csv'] || `${dataDir}/keyword-customizers.csv`);
const campaignBindingsPath = resolve(_projectRoot, args['campaign-bindings-csv'] || `${dataDir}/campaign-customizers.csv`);
const customerBindingsPath = resolve(_projectRoot, args['customer-bindings-csv'] || `${dataDir}/customer-customizers.csv`);
const adsPath = resolve(_projectRoot, args['ads-csv'] || `${dataDir}/qs-ads.csv`);
const outputPath = resolve(_projectRoot, args['output'] || `${dataDir}/qs-customizers.csv`);

function loadCsv(path) {
    if (!path || !existsSync(path)) return [];
    const raw = readFileSync(path, 'utf8');
    const rows = parse(raw, { columns: true, skip_empty_lines: true, relax_column_count: true });
    return rows.map(row => {
        const norm = {};
        for (const [k, v] of Object.entries(row)) {
            norm[k.replace(/\./g, '_')] = v;
        }
        return norm;
    });
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

// ── Load inputs ─────────────────────────────────────────────────────
console.log('Loading customizer inputs...');
const attrs = loadCsv(attrsPath);
const agBindings = loadCsv(agBindingsPath);
const kwBindings = loadCsv(kwBindingsPath);
const campaignBindings = loadCsv(campaignBindingsPath);
const customerBindings = loadCsv(customerBindingsPath);
const ads = loadCsv(adsPath);

console.log(`Attributes: ${attrs.length} | AG: ${agBindings.length} | KW: ${kwBindings.length} | Campaign: ${campaignBindings.length} | Customer: ${customerBindings.length} | RSAs: ${ads.length}`);

// ── Build attribute name lookup (resource_name → name) ──────────────
// customizer_attribute rows come in with `resource_name` and `name`.
// Bindings reference the attribute via `ad_group_customizer.customizer_attribute`
// which holds the attribute's resource_name.
const attrByResourceName = new Map();
const attrNameSet = new Set();
for (const a of attrs) {
    const rn = a.customizer_attribute_resource_name;
    const name = a.customizer_attribute_name;
    if (rn) attrByResourceName.set(rn, { name, type: a.customizer_attribute_type });
    if (name) attrNameSet.add(name);
}

// ── Extract {CUSTOMIZER.<name>} references from each ad ─────────────
// Placeholder syntax: {CUSTOMIZER.attribute_name:default} or {CUSTOMIZER.attribute_name}
// Scan headlines + descriptions text. Google Ads API returns these as arrays of
// asset-link objects; the serialised CSV puts them in a single cell (pipe/comma
// delimited). Since we only care whether ANY {CUSTOMIZER.X} substring appears,
// regex the whole cell.
const customizerRegex = /\{CUSTOMIZER\.([A-Za-z0-9_]+)(?::[^}]*)?\}/g;

const rsaRefsByAg = new Map(); // ad_group_id → Set<attribute_name_referenced>
function recordRefs(agId, text) {
    if (!text) return;
    customizerRegex.lastIndex = 0;
    let match;
    while ((match = customizerRegex.exec(text)) !== null) {
        const name = match[1];
        if (!rsaRefsByAg.has(agId)) rsaRefsByAg.set(agId, new Set());
        rsaRefsByAg.get(agId).add(name);
    }
}

for (const ad of ads) {
    const agId = ad.ad_group_id;
    if (!agId) continue;
    const blob = [
        ad.ad_group_ad_ad_responsive_search_ad_headlines,
        ad.ad_group_ad_ad_responsive_search_ad_descriptions,
        ad.ad_group_ad_ad_responsive_search_ad_path1,
        ad.ad_group_ad_ad_responsive_search_ad_path2,
    ].filter(Boolean).join(' ');
    recordRefs(agId, blob);
}

// ── Build per-AG binding maps ───────────────────────────────────────
const agBindingsByAg = new Map(); // ad_group_id → Set<attribute_name>
const agMetaByAg = new Map(); // ad_group_id → {campaign_id, campaign_name, ad_group_name}

function resolveBinding(resourceName) {
    if (!resourceName) return null;
    const attr = attrByResourceName.get(resourceName);
    return attr ? attr.name : null;
}

for (const b of agBindings) {
    const agId = b.ad_group_id;
    if (!agId) continue;
    const name = resolveBinding(b.ad_group_customizer_customizer_attribute);
    if (!agBindingsByAg.has(agId)) agBindingsByAg.set(agId, new Set());
    if (name) agBindingsByAg.get(agId).add(name);
    agMetaByAg.set(agId, {
        campaign_id: b.campaign_id,
        campaign_name: b.campaign_name,
        ad_group_name: b.ad_group_name,
    });
}

const kwBindingsByAg = new Map(); // ad_group_id → Set<attribute_name>
const kwBindingKeywordCountByAg = new Map(); // ad_group_id → Set<criterion_id> (distinct keyword count)

for (const b of kwBindings) {
    const agId = b.ad_group_id;
    if (!agId) continue;
    const name = resolveBinding(b.ad_group_criterion_customizer_customizer_attribute);
    if (!kwBindingsByAg.has(agId)) kwBindingsByAg.set(agId, new Set());
    if (name) kwBindingsByAg.get(agId).add(name);
    if (!kwBindingKeywordCountByAg.has(agId)) kwBindingKeywordCountByAg.set(agId, new Set());
    if (b.ad_group_criterion_criterion_id) kwBindingKeywordCountByAg.get(agId).add(b.ad_group_criterion_criterion_id);
    if (!agMetaByAg.has(agId)) {
        agMetaByAg.set(agId, {
            campaign_id: b.campaign_id,
            campaign_name: b.campaign_name,
            ad_group_name: b.ad_group_name,
        });
    }
}

// Also fill meta from any ad group that has an RSA customizer reference, in case
// the AG has referenced-but-unbound attributes (no bindings rows → no metadata).
for (const ad of ads) {
    const agId = ad.ad_group_id;
    if (!agId || agMetaByAg.has(agId)) continue;
    agMetaByAg.set(agId, {
        campaign_id: ad.campaign_id,
        campaign_name: ad.campaign_name,
        ad_group_name: ad.ad_group_name,
    });
}

// Campaign-level bindings: campaign_id → Set<attribute_name>
const campaignBindingsByCampaign = new Map();
for (const b of campaignBindings) {
    const campaignId = b.campaign_id;
    if (!campaignId) continue;
    const name = resolveBinding(b.campaign_customizer_customizer_attribute);
    if (!campaignBindingsByCampaign.has(campaignId)) campaignBindingsByCampaign.set(campaignId, new Set());
    if (name) campaignBindingsByCampaign.get(campaignId).add(name);
}

// Customer-level bindings: one Set<attribute_name> for the whole account
const customerBindingNames = new Set();
for (const b of customerBindings) {
    const name = resolveBinding(b.customer_customizer_customizer_attribute);
    if (name) customerBindingNames.add(name);
}

// ── Emit one row per ad group ───────────────────────────────────────
const allAgs = new Set([
    ...agMetaByAg.keys(),
    ...rsaRefsByAg.keys(),
    ...agBindingsByAg.keys(),
    ...kwBindingsByAg.keys(),
]);

// Resolve the effective binding level for one (AG, attribute) pair.
// Returns the highest-priority level where the attribute is bound, or 'NONE'.
function resolveLevel(agId, campaignId, attrName) {
    if ((kwBindingsByAg.get(agId) || new Set()).has(attrName)) return 'KEYWORD';
    if ((agBindingsByAg.get(agId) || new Set()).has(attrName)) return 'AD_GROUP';
    if ((campaignBindingsByCampaign.get(campaignId) || new Set()).has(attrName)) return 'CAMPAIGN';
    if (customerBindingNames.has(attrName)) return 'CUSTOMER';
    return 'NONE';
}

const output = [];
for (const agId of allAgs) {
    const meta = agMetaByAg.get(agId) || {};
    const campaignId = meta.campaign_id || '';
    const agBound = agBindingsByAg.get(agId) || new Set();
    const kwBound = kwBindingsByAg.get(agId) || new Set();
    const rsaRefs = rsaRefsByAg.get(agId) || new Set();
    const kwCount = (kwBindingKeywordCountByAg.get(agId) || new Set()).size;

    const referenced = Array.from(rsaRefs);
    const missing = referenced.filter(name => !attrNameSet.has(name));
    // Attributes that exist but don't resolve at any level for this AG → render :default every time
    const staticRefs = referenced.filter(name => attrNameSet.has(name) && resolveLevel(agId, campaignId, name) === 'NONE');
    // The effective binding level for each referenced attribute (highest-priority match)
    const effectiveLevels = referenced.map(name => {
        if (!attrNameSet.has(name)) return `${name}:MISSING`;
        return `${name}:${resolveLevel(agId, campaignId, name)}`;
    });

    let integrityStatus;
    if (referenced.length === 0) {
        integrityStatus = 'NO_CUSTOMIZERS';
    } else if (missing.length > 0) {
        integrityStatus = 'BROKEN';
    } else if (staticRefs.length === referenced.length) {
        // All referenced attributes fall back to :default (no binding resolves anywhere)
        integrityStatus = 'EFFECTIVELY_STATIC';
    } else {
        integrityStatus = 'OK';
    }

    // Headline-test modifier — determined by the highest level at which ANY
    // referenced attribute actually resolves.
    let headlineTestMode;
    if (referenced.length === 0) {
        headlineTestMode = 'STANDARD';
    } else {
        const levels = referenced
            .filter(name => attrNameSet.has(name))
            .map(name => resolveLevel(agId, campaignId, name));
        if (levels.includes('KEYWORD')) {
            headlineTestMode = 'RELAXED_KW_LEVEL';
        } else if (levels.includes('AD_GROUP') || levels.includes('CAMPAIGN') || levels.includes('CUSTOMER')) {
            // Values are constant within the AG at serve time — Headline Test runs standard
            // but the finding should note customizer context.
            headlineTestMode = 'AG_LEVEL_CONSTANT';
        } else {
            // Referenced but nothing resolves — :default is the effective headline
            headlineTestMode = 'STANDARD';
        }
    }

    output.push({
        campaign_id: campaignId,
        campaign_name: meta.campaign_name || '',
        ad_group_id: agId,
        ad_group_name: meta.ad_group_name || '',
        has_kw_level_bindings: kwBound.size > 0 ? 'true' : 'false',
        kw_level_keyword_count: kwCount,
        kw_level_attributes: Array.from(kwBound).join('|'),
        has_ag_level_bindings: agBound.size > 0 ? 'true' : 'false',
        ag_level_attributes: Array.from(agBound).join('|'),
        rsa_references_customizers: rsaRefs.size > 0 ? 'true' : 'false',
        referenced_attribute_names: referenced.join('|'),
        missing_attribute_names: missing.join('|'),
        static_attribute_names: staticRefs.join('|'),
        effective_resolution: effectiveLevels.join('|'),
        integrity_status: integrityStatus,
        headline_test_mode: headlineTestMode,
    });
}

const headers = [
    'campaign_id', 'campaign_name', 'ad_group_id', 'ad_group_name',
    'has_kw_level_bindings', 'kw_level_keyword_count', 'kw_level_attributes',
    'has_ag_level_bindings', 'ag_level_attributes',
    'rsa_references_customizers', 'referenced_attribute_names', 'missing_attribute_names',
    'static_attribute_names', 'effective_resolution',
    'integrity_status', 'headline_test_mode',
];
writeCsv(outputPath, headers, output);

const statusCounts = output.reduce((acc, r) => {
    acc[r.integrity_status] = (acc[r.integrity_status] || 0) + 1;
    return acc;
}, {});

console.log(`File: ${outputPath}`);
console.log(`Ad groups analysed: ${output.length}`);
console.log(`Integrity: ${JSON.stringify(statusCounts)}`);
console.log('Done.');
