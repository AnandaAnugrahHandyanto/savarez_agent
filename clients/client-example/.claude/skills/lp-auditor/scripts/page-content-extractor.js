#!/usr/bin/env node

/**
 * Page Content Extractor
 *
 * Batch-fetches pages and extracts key conversion elements:
 * H1, sub-headline, hero text, offer/pricing section, CTA texts, meta description.
 *
 * Usage:
 *   node page-content-extractor.js --urls="https://a.com,https://b.com" [--output=results.json] [--concurrency=5]
 *   node page-content-extractor.js --file=urls.txt [--output=results.json]
 *
 * Output (JSON to stdout or file):
 *   [{ url, h1, subHeadline, heroText, offerSection, ctaTexts, metaDescription, title, error }]
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';
import https from 'https';
import http from 'http';

const __dirname = dirname(fileURLToPath(import.meta.url));
let _projectRoot = __dirname;
while (_projectRoot !== '/' && !existsSync(resolve(_projectRoot, 'config'))) {
  _projectRoot = resolve(_projectRoot, '..');
}

// Parse arguments
const args = process.argv.slice(2).reduce((acc, arg) => {
  if (arg.includes('=')) {
    const eqIndex = arg.indexOf('=');
    const key = arg.slice(0, eqIndex).replace('--', '');
    const value = arg.slice(eqIndex + 1);
    if (key && value) acc[key] = value;
  }
  return acc;
}, {});

const concurrency = parseInt(args.concurrency || '5', 10);
const outputPath = args.output ? resolve(_projectRoot, args.output) : null;

// Collect URLs
let urls = [];
if (args.urls) {
  urls = args.urls.split(',').map(u => u.trim()).filter(Boolean);
} else if (args.file) {
  const filePath = resolve(_projectRoot, args.file);
  const content = readFileSync(filePath, 'utf-8');
  urls = content.split('\n').map(u => u.trim()).filter(u => u && u.startsWith('http'));
}

urls = [...new Set(urls)];

if (urls.length === 0) {
  console.error('No URLs provided. Use --urls=... or --file=...');
  process.exit(1);
}

console.error(`Extracting content from ${urls.length} URLs with concurrency ${concurrency}...`);

/**
 * Fetch full HTML of a page (follows redirects).
 */
function fetchPage(url, maxRedirects = 5) {
  return new Promise((resolvePromise) => {
    let redirectCount = 0;

    function fetch(targetUrl) {
      if (redirectCount >= maxRedirects) {
        resolvePromise({ html: null, error: 'Too many redirects' });
        return;
      }

      const protocol = targetUrl.startsWith('https') ? https : http;
      const req = protocol.get(targetUrl, {
        timeout: 20000,
        headers: {
          'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
          'Accept': 'text/html,application/xhtml+xml',
          'Accept-Language': 'en-US,en;q=0.9'
        }
      }, (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          redirectCount++;
          let nextUrl = res.headers.location;
          if (nextUrl.startsWith('/')) {
            const parsed = new URL(targetUrl);
            nextUrl = `${parsed.protocol}//${parsed.host}${nextUrl}`;
          }
          res.resume();
          fetch(nextUrl);
          return;
        }

        const chunks = [];
        res.on('data', chunk => chunks.push(chunk));
        res.on('end', () => {
          resolvePromise({ html: Buffer.concat(chunks).toString('utf-8'), error: null });
        });
      });

      req.on('error', (err) => {
        resolvePromise({ html: null, error: err.message });
      });

      req.on('timeout', () => {
        req.destroy();
        resolvePromise({ html: null, error: 'Timeout (20s)' });
      });
    }

    fetch(url);
  });
}

/**
 * Extract text content from between HTML tags (simple regex-based extraction).
 * Not a full parser — sufficient for extracting key content from well-structured pages.
 */
function extractText(html, tagPattern) {
  const regex = new RegExp(`<${tagPattern}[^>]*>(.*?)</${tagPattern.split(/\s/)[0]}>`, 'gis');
  const matches = [];
  let match;
  while ((match = regex.exec(html)) !== null) {
    const text = match[1].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
    if (text) matches.push(text);
  }
  return matches;
}

/**
 * Extract page content for message match analysis.
 */
function extractContent(html, url) {
  if (!html) return null;

  // Title
  const titleMatch = html.match(/<title[^>]*>(.*?)<\/title>/is);
  const title = titleMatch ? titleMatch[1].replace(/\s+/g, ' ').trim() : '';

  // Meta description
  const metaMatch = html.match(/<meta\s+name=["']description["']\s+content=["'](.*?)["']/is)
    || html.match(/<meta\s+content=["'](.*?)["']\s+name=["']description["']/is);
  const metaDescription = metaMatch ? metaMatch[1].trim() : '';

  // H1 (first one = main headline)
  const h1s = extractText(html, 'h1');
  const h1 = h1s[0] || '';

  // Sub-headline (first H2, or text immediately after H1 container)
  const h2s = extractText(html, 'h2');
  const subHeadline = h2s[0] || '';

  // Hero text (combine H1 + first H2 + nearby paragraph text)
  const firstParagraphs = extractText(html, 'p').slice(0, 3);
  const heroText = [h1, subHeadline, ...firstParagraphs].filter(Boolean).join(' | ');

  // CTA texts (buttons and submit inputs)
  const buttonTexts = extractText(html, 'button');
  const inputSubmits = [];
  const submitRegex = /<input[^>]*type=["']submit["'][^>]*value=["'](.*?)["']/gi;
  let submitMatch;
  while ((submitMatch = submitRegex.exec(html)) !== null) {
    inputSubmits.push(submitMatch[1].trim());
  }
  const ctaTexts = [...buttonTexts, ...inputSubmits].filter(t => t.length > 1 && t.length < 100);

  // Offer/pricing section (look for price patterns, offer keywords)
  const offerPatterns = [];
  // Find price mentions
  const priceRegex = /(?:[$€£¥][\d,.]+|\d+(?:\.\d{2})?\s*(?:USD|EUR|GBP|per\s+month|\/mo|\/year))/gi;
  const prices = html.match(priceRegex) || [];
  if (prices.length > 0) offerPatterns.push(`Prices found: ${prices.slice(0, 5).join(', ')}`);
  // Find offer keywords near text
  const offerKeywords = ['free trial', 'free consultation', 'free demo', 'get started', 'sign up', 'book a call',
    'schedule', 'download', 'no credit card', 'money-back', 'guarantee', 'discount', '% off'];
  const lowerHtml = html.toLowerCase();
  for (const kw of offerKeywords) {
    if (lowerHtml.includes(kw)) offerPatterns.push(kw);
  }
  const offerSection = offerPatterns.join(', ') || 'No clear offer detected';

  return {
    url,
    title,
    h1,
    subHeadline,
    heroText,
    offerSection,
    ctaTexts,
    metaDescription,
    error: null
  };
}

/**
 * Process a single URL.
 */
async function processUrl(url) {
  const { html, error } = await fetchPage(url);
  if (error) {
    return { url, h1: '', subHeadline: '', heroText: '', offerSection: '', ctaTexts: [], metaDescription: '', title: '', error };
  }
  return extractContent(html, url);
}

/**
 * Run extractions with concurrency limit.
 */
async function runExtractions(urls, limit) {
  const results = [];
  let index = 0;

  async function worker() {
    while (index < urls.length) {
      const i = index++;
      const result = await processUrl(urls[i]);
      results.push(result);
      const status = result.error ? `ERROR: ${result.error}` : `H1: "${result.h1.slice(0, 50)}"`;
      console.error(`  [${results.length}/${urls.length}] ${status} — ${urls[i]}`);
    }
  }

  const workers = Array.from({ length: Math.min(limit, urls.length) }, () => worker());
  await Promise.all(workers);

  return results;
}

// Run
const results = await runExtractions(urls, concurrency);

// Summary
const success = results.filter(r => !r.error).length;
const failed = results.filter(r => r.error).length;

console.error(`\nDone: ${success} extracted, ${failed} failed`);

// Output
const output = JSON.stringify(results, null, 2);
if (outputPath) {
  mkdirSync(dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, output);
  console.error(`Results written to: ${outputPath}`);
} else {
  console.log(output);
}
