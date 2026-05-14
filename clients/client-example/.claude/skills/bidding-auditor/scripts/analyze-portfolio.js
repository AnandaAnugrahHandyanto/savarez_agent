#!/usr/bin/env node

/**
 * Bidding Auditor — Portfolio Health + Conversion Value Rules engine
 *
 * Modules covered:
 *   Module 4 — Portfolio Health (BID-D14–D17)
 *   Module 7 — Conversion Value Rules (BID-D25, BID-D26)
 *
 * Reads:
 *   bidding-strategies.csv     (portfolio members and targets)
 *   campaigns-bidding-perf.csv (campaign types + bidding strategy + budget)
 *   campaign-budgets.csv       (optional, reused from /budget-auditor)
 *   conversion-value-rules.csv (optional, may be empty)
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import {
    PROJECT_ROOT, readCsv, num, microsToDollars, getChannelType,
    isSmartBidding, isValueBased,
    indexPortfoliosByResource, makeFinding,
} from './lib.js';

const __dirname = dirname(fileURLToPath(import.meta.url));

const args = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const i = arg.indexOf('=');
        acc[arg.slice(0, i).replace('--', '')] = arg.slice(i + 1);
    }
    return acc;
}, {});

const perfPath = args['perf-csv'] || resolve(PROJECT_ROOT, 'context/google-ads/data/campaigns-bidding-perf.csv');
const portfoliosPath = args['portfolios-csv'] || resolve(PROJECT_ROOT, 'context/google-ads/data/bidding-strategies.csv');
const valueRulesPath = args['value-rules-csv'] || resolve(PROJECT_ROOT, 'context/google-ads/data/conversion-value-rules.csv');
const findingsOut = args['findings-output'] || resolve(PROJECT_ROOT, 'context/analysis/bidding/findings-portfolio.json');

const configPath = resolve(PROJECT_ROOT, 'config/ads-context.config.json');
const config = JSON.parse(readFileSync(configPath, 'utf8'));
const ba = config.biddingAudit || {};

const perfRows = readCsv(perfPath).filter(r => r['campaign.serving_status'] !== 'ENDED');
const portfolioRows = readCsv(portfoliosPath);
const valueRules = readCsv(valueRulesPath);
const portfoliosById = indexPortfoliosByResource(portfolioRows);

const findings = [];

// ── Module 4: Portfolio Health ─────────────────────────────────────────

// BID-D14: Mixed campaign types in a single portfolio
{
    const byPortfolio = new Map();
    for (const c of perfRows) {
        const portfolio = c['campaign.bidding_strategy'];
        if (!portfolio) continue;
        if (!byPortfolio.has(portfolio)) byPortfolio.set(portfolio, []);
        byPortfolio.get(portfolio).push(c);
    }

    for (const [portfolio, members] of byPortfolio) {
        const channels = new Set(members.map(getChannelType));
        const portfolioName = portfoliosById.get(portfolio)?.['bidding_strategy.name'] || portfolio;
        const meta = { portfolio: portfolioName, members: members.length };
        if (channels.size > 1) {
            findings.push(makeFinding('BID-D14', 'WARN', 'medium',
                `Portfolio "${portfolioName}" mixes campaign types: ${[...channels].join(', ')}.`,
                { ...meta, channels: [...channels] }));
        } else {
            findings.push(makeFinding('BID-D14', 'PASS', 'low',
                `Portfolio "${portfolioName}" is type-consistent (${[...channels][0]}).`, meta));
        }
    }

    if (byPortfolio.size === 0) {
        findings.push(makeFinding('BID-D14', 'SKIP', 'low', 'No portfolio strategies in account.', {}));
    }
}

// BID-D15: CPC cap active (anywhere)
// BID-D16: Cap vs. top-CPC keywords (informational — relies on keyword-auditor data if available)
{
    const capActiveCampaigns = perfRows.filter(c =>
        num(c['campaign.target_roas.cpc_bid_ceiling_micros']) > 0
        || num(c['campaign.percent_cpc.cpc_bid_ceiling_micros']) > 0
        || num(c['campaign.target_impression_share.cpc_bid_ceiling_micros']) > 0
    );
    const capPortfolios = portfolioRows.filter(p =>
        num(p['bidding_strategy.target_roas.cpc_bid_ceiling_micros']) > 0
        || num(p['bidding_strategy.target_impression_share.cpc_bid_ceiling_micros']) > 0
    );

    if (capActiveCampaigns.length || capPortfolios.length) {
        findings.push(makeFinding('BID-D15', 'WARN', 'medium',
            `${capActiveCampaigns.length} campaigns + ${capPortfolios.length} portfolios have a CPC cap active. Caps can constrain smart bidding.`,
            { capped_campaigns: capActiveCampaigns.length, capped_portfolios: capPortfolios.length }));
    } else {
        findings.push(makeFinding('BID-D15', 'PASS', 'low', 'No CPC caps set on smart bidding.', {}));
    }

    findings.push(makeFinding('BID-D16', 'INFO', 'low',
        'CPC cap vs. top-keyword CPCs comparison: rerun /keyword-auditor performance and compare top-quartile CPCs against any active caps.', {}));
}

// BID-D17: Shared budget + portfolio strategy conflict
{
    const conflicts = [];
    for (const c of perfRows) {
        const isShared = (c['campaign_budget.explicitly_shared'] || '').toString().toLowerCase() === 'true';
        const portfolio = c['campaign.bidding_strategy'];
        if (isShared && portfolio) {
            conflicts.push({
                campaign: c['campaign.name'],
                portfolio: portfoliosById.get(portfolio)?.['bidding_strategy.name'] || portfolio,
            });
        }
    }
    if (conflicts.length) {
        findings.push(makeFinding('BID-D17', 'FAIL', 'high',
            `${conflicts.length} campaigns combine a shared budget with a portfolio bid strategy — pacing and learning will fight each other.`,
            { conflicts }));
    } else {
        findings.push(makeFinding('BID-D17', 'PASS', 'low', 'No shared-budget + portfolio conflicts detected.', {}));
    }
}

// ── Module 7: Conversion Value Rules ───────────────────────────────────

// BID-D25: rules on non-value campaigns
// BID-D26: rules substituting for tracking → handoff
{
    if (!valueRules.length) {
        findings.push(makeFinding('BID-D25', 'SKIP', 'low', 'No conversion value rules present.', {}));
        findings.push(makeFinding('BID-D26', 'SKIP', 'low', 'No conversion value rules present.', {}));
    } else {
        const valueCampaignCount = perfRows.filter(c => isValueBased(c['campaign.bidding_strategy_type'])).length;
        if (valueCampaignCount === 0) {
            findings.push(makeFinding('BID-D25', 'WARN', 'medium',
                `${valueRules.length} active value rules but no value-based bid strategies in the account — rules may be unused.`,
                { rules: valueRules.length }));
        } else {
            findings.push(makeFinding('BID-D25', 'PASS', 'low',
                `${valueRules.length} value rules on ${valueCampaignCount} value-based campaigns.`, {}));
        }

        // BID-D26 is a heuristic — surface as INFO and recommend tracking-specialist handoff
        findings.push(makeFinding('BID-D26', 'INFO', 'medium',
            `Value rules detected. If these correct for missing per-channel/device/geo conversion data, route to /tracking-specialist — value rules should not be substituting for missing tracking.`,
            { rules: valueRules.length, handoff: 'tracking-specialist' }));
    }
}

// ── Write outputs ──────────────────────────────────────────────────────

function writeJson(path, data) {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, JSON.stringify(data, null, 2));
}

writeJson(findingsOut, findings);

const counts = findings.reduce((acc, f) => { acc[f.verdict] = (acc[f.verdict] || 0) + 1; return acc; }, {});
console.log(`analyze-portfolio: ${findings.length} findings`);
console.log(`  ${JSON.stringify(counts)}`);
console.log(`  output: ${findingsOut}`);
