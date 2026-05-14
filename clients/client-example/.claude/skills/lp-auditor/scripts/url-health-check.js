#!/usr/bin/env node

/**
 * URL Health Checker
 *
 * Batch checks HTTP status codes and redirect chains for a list of URLs.
 * Fires parallel HEAD requests with concurrency limit.
 *
 * Usage:
 *   node url-health-check.js --urls="https://a.com,https://b.com" [--output=results.json] [--concurrency=10]
 *   node url-health-check.js --file=urls.txt [--output=results.json]
 *
 * Input:
 *   --urls     Comma-separated list of URLs
 *   --file     Path to a file with one URL per line
 *
 * Output (JSON to stdout or file):
 *   [{ url, statusCode, redirectChain, finalUrl, responseTime, error }]
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

const concurrency = parseInt(args.concurrency || '10', 10);
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

// Deduplicate
urls = [...new Set(urls)];

if (urls.length === 0) {
  console.error('No URLs provided. Use --urls=... or --file=...');
  process.exit(1);
}

console.error(`Checking ${urls.length} URLs with concurrency ${concurrency}...`);

/**
 * Check a single URL: follow redirects, record chain, measure time.
 */
function checkUrl(url, maxRedirects = 10) {
  return new Promise((resolve) => {
    const start = Date.now();
    const chain = [];
    let currentUrl = url;
    let redirectCount = 0;

    function follow(targetUrl) {
      if (redirectCount >= maxRedirects) {
        resolve({
          url,
          statusCode: 0,
          redirectChain: chain,
          finalUrl: targetUrl,
          responseTime: Date.now() - start,
          error: `Too many redirects (${maxRedirects})`
        });
        return;
      }

      const protocol = targetUrl.startsWith('https') ? https : http;
      const req = protocol.request(targetUrl, { method: 'HEAD', timeout: 15000 }, (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          chain.push({ url: targetUrl, statusCode: res.statusCode });
          redirectCount++;
          let nextUrl = res.headers.location;
          // Handle relative redirects
          if (nextUrl.startsWith('/')) {
            const parsed = new URL(targetUrl);
            nextUrl = `${parsed.protocol}//${parsed.host}${nextUrl}`;
          }
          follow(nextUrl);
        } else {
          resolve({
            url,
            statusCode: res.statusCode,
            redirectChain: chain,
            finalUrl: targetUrl,
            responseTime: Date.now() - start,
            error: null
          });
        }
      });

      req.on('error', (err) => {
        resolve({
          url,
          statusCode: 0,
          redirectChain: chain,
          finalUrl: targetUrl,
          responseTime: Date.now() - start,
          error: err.message
        });
      });

      req.on('timeout', () => {
        req.destroy();
        resolve({
          url,
          statusCode: 0,
          redirectChain: chain,
          finalUrl: targetUrl,
          responseTime: Date.now() - start,
          error: 'Timeout (15s)'
        });
      });

      req.end();
    }

    follow(currentUrl);
  });
}

/**
 * Run checks with concurrency limit.
 */
async function runChecks(urls, limit) {
  const results = [];
  let index = 0;

  async function worker() {
    while (index < urls.length) {
      const i = index++;
      const result = await checkUrl(urls[i]);
      results.push(result);
      const status = result.error ? `ERROR: ${result.error}` : `${result.statusCode}`;
      const redirects = result.redirectChain.length > 0 ? ` (${result.redirectChain.length} redirect${result.redirectChain.length > 1 ? 's' : ''})` : '';
      console.error(`  [${results.length}/${urls.length}] ${status}${redirects} — ${urls[i]}`);
    }
  }

  const workers = Array.from({ length: Math.min(limit, urls.length) }, () => worker());
  await Promise.all(workers);

  return results;
}

// Run
const results = await runChecks(urls, concurrency);

// Summary
const healthy = results.filter(r => r.statusCode === 200).length;
const broken = results.filter(r => r.statusCode !== 200).length;
const withRedirects = results.filter(r => r.redirectChain.length > 0).length;

console.error(`\nDone: ${healthy} healthy, ${broken} broken, ${withRedirects} with redirects`);

// Output
const output = JSON.stringify(results, null, 2);
if (outputPath) {
  mkdirSync(dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, output);
  console.error(`Results written to: ${outputPath}`);
} else {
  console.log(output);
}
