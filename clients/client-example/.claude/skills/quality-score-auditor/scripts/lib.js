/**
 * Shared utilities for the quality-score-auditor analysis engines.
 * Account-agnostic — never assumes a specific currency, KPI, or campaign.
 */

import { existsSync, readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

let _projectRoot = __dirname;
while (_projectRoot !== '/' && !existsSync(resolve(_projectRoot, 'config'))) {
    _projectRoot = resolve(_projectRoot, '..');
}
export const PROJECT_ROOT = _projectRoot;

// ── Number coercion ────────────────────────────────────────────────────

export function num(v, fallback = 0) {
    if (v === null || v === undefined || v === '') return fallback;
    const n = typeof v === 'number' ? v : Number(v);
    return Number.isFinite(n) ? n : fallback;
}

// ── Config loading ─────────────────────────────────────────────────────

export function loadFullConfig() {
    const configPath = resolve(_projectRoot, 'config/ads-context.config.json');
    if (!existsSync(configPath)) return {};
    try {
        return JSON.parse(readFileSync(configPath, 'utf8'));
    } catch {
        return {};
    }
}

// ── Currency formatting (uses top-level accountCurrency from config) ──
//
// Mirrors `.claude/skills/budget-auditor/scripts/lib.js`. Money rendered in
// CSV `flag_detail` strings and by analyzers must go through these helpers
// so the audit never bakes in a `$` symbol. Reader skills (and Claude when
// writing the report) read top-level `accountCurrency` from the config.

export function formatCurrency(amount, currency = 'USD') {
    const n = num(amount);
    return new Intl.NumberFormat('en-US', {
        style: 'currency', currency, maximumFractionDigits: 0,
    }).format(n);
}

export function formatCurrencyPrecise(amount, currency = 'USD') {
    const n = num(amount);
    return new Intl.NumberFormat('en-US', {
        style: 'currency', currency, maximumFractionDigits: 2,
    }).format(n);
}

/**
 * Resolve the account currency from full config. Defaults to "USD" and
 * emits a single warning to stderr — never crashes the analysis run.
 */
export function resolveAccountCurrency(fullConfig) {
    const code = fullConfig?.accountCurrency;
    if (typeof code === 'string' && /^[A-Z]{3}$/.test(code)) return code;
    if (!resolveAccountCurrency._warned) {
        console.warn('[quality-score-auditor] accountCurrency not set in config — defaulting to USD. Run /quality-score-auditor reconfirm to set it.');
        resolveAccountCurrency._warned = true;
    }
    return 'USD';
}
