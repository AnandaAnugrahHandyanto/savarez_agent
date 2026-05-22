#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const websiteDir = path.resolve(__dirname, '..');
const buildDir = path.join(websiteDir, 'build');
const siteOrigin = 'https://hermes-agent.nousresearch.com';
const baseUrl = '/docs/';
const canonicalBase = `${siteOrigin}${baseUrl}`;

const failures = [];
const checked = [];

function fail(message) {
  failures.push(message);
}

function pass(message) {
  checked.push(message);
}

function readRequired(relativePath) {
  const absolutePath = path.join(buildDir, relativePath);
  if (!fs.existsSync(absolutePath)) {
    fail(`Missing generated file: ${relativePath}`);
    return '';
  }

  const contents = fs.readFileSync(absolutePath, 'utf8');
  if (!contents.trim()) {
    fail(`Generated file is empty: ${relativePath}`);
  } else {
    pass(`Found ${relativePath}`);
  }
  return contents;
}

function expectIncludes(contents, needle, label) {
  if (!contents.includes(needle)) {
    fail(`${label} is missing ${needle}`);
    return;
  }
  pass(`${label} includes ${needle}`);
}

function jsonLdBlocks(html, relativePath) {
  const blocks = [];
  const scriptPattern = /<script\b[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
  let match;
  while ((match = scriptPattern.exec(html)) !== null) {
    blocks.push(match[1].trim());
  }

  if (blocks.length === 0) {
    fail(`${relativePath} is missing application/ld+json structured data`);
  } else {
    pass(`${relativePath} includes ${blocks.length} JSON-LD block${blocks.length === 1 ? '' : 's'}`);
  }

  return blocks;
}

function graphNodes(jsonLd) {
  if (Array.isArray(jsonLd?.['@graph'])) return jsonLd['@graph'];
  if (Array.isArray(jsonLd)) return jsonLd.flatMap((entry) => graphNodes(entry));
  return jsonLd ? [jsonLd] : [];
}

function nodeHasType(node, expectedType) {
  const type = node?.['@type'];
  return Array.isArray(type) ? type.includes(expectedType) : type === expectedType;
}

function extractUrls(value, urls = []) {
  if (!value) return urls;
  if (typeof value === 'string') {
    if (/^https?:\/\//.test(value)) urls.push(value);
    return urls;
  }
  if (Array.isArray(value)) {
    for (const item of value) extractUrls(item, urls);
    return urls;
  }
  if (typeof value === 'object') {
    for (const item of Object.values(value)) extractUrls(item, urls);
  }
  return urls;
}

function checkJsonLdRoute(route, expectations) {
  const relativePath = htmlPathForRoute(route);
  const html = readRequired(relativePath);
  if (!html) return;

  const parsedBlocks = [];
  for (const [index, payload] of jsonLdBlocks(html, relativePath).entries()) {
    if (!payload) {
      fail(`${relativePath} JSON-LD block ${index + 1} is empty`);
      continue;
    }
    if (payload.includes('<')) {
      fail(`${relativePath} JSON-LD block ${index + 1} contains an unescaped < character`);
    }

    try {
      parsedBlocks.push(JSON.parse(payload));
      pass(`${relativePath} JSON-LD block ${index + 1} parses as JSON`);
    } catch (error) {
      fail(`${relativePath} JSON-LD block ${index + 1} is malformed JSON: ${error.message}`);
    }
  }

  const nodes = parsedBlocks.flatMap((block) => graphNodes(block));
  for (const expectedType of expectations.types) {
    if (!nodes.some((node) => nodeHasType(node, expectedType))) {
      fail(`${relativePath} JSON-LD is missing @type ${expectedType}`);
    } else {
      pass(`${relativePath} JSON-LD includes @type ${expectedType}`);
    }
  }

  const urls = extractUrls(parsedBlocks);
  for (const expectedUrl of expectations.urls) {
    if (!urls.includes(expectedUrl)) {
      fail(`${relativePath} JSON-LD is missing canonical URL ${expectedUrl}`);
    } else {
      pass(`${relativePath} JSON-LD references ${expectedUrl}`);
    }
  }
}

function htmlPathForRoute(route) {
  const normalized = route.replace(/^\//, '').replace(/\/$/, '');
  return normalized ? `${normalized}/index.html` : 'index.html';
}

function getAttr(tag, attrName) {
  const match = tag.match(new RegExp(`\\s${attrName}=["']([^"']+)["']`, 'i'));
  return match?.[1] ?? '';
}

function findTag(html, pattern, label) {
  const match = html.match(pattern);
  if (!match) {
    fail(label);
    return '';
  }
  return match[0];
}

function checkMetaRoute(route) {
  const relativePath = htmlPathForRoute(route);
  const html = readRequired(relativePath);
  if (!html) return;

  const routePath = route.replace(/^\//, '');
  const expectedUrl = route === '/'
    ? canonicalBase
    : `${canonicalBase}${routePath.replace(/\/$/, '')}${routePath.endsWith('/') ? '/' : ''}`;
  const title = html.match(/<title[^>]*>([^<]+)<\/title>/i)?.[1]?.trim() ?? '';
  if (!title) {
    fail(`${relativePath} has an empty or missing <title>`);
  } else {
    pass(`${relativePath} has title: ${title}`);
  }

  const canonicalTag = findTag(
    html,
    /<link\b[^>]*rel=["']canonical["'][^>]*>/i,
    `${relativePath} is missing <link rel="canonical">`,
  );
  if (canonicalTag) {
    const href = getAttr(canonicalTag, 'href');
    if (href !== expectedUrl) {
      fail(`${relativePath} canonical href ${href || '(missing)'} did not match ${expectedUrl}`);
    } else {
      pass(`${relativePath} canonical URL matches ${expectedUrl}`);
    }
  }

  const metaDescription = findTag(
    html,
    /<meta\b[^>]*name=["']description["'][^>]*>/i,
    `${relativePath} is missing meta description`,
  );
  if (metaDescription) {
    const description = getAttr(metaDescription, 'content').trim();
    if (!description) {
      fail(`${relativePath} meta description is empty`);
    } else {
      pass(`${relativePath} has non-empty meta description`);
    }
  }

  const requiredMeta = [
    ['og:url', /^https:\/\/hermes-agent\.nousresearch\.com\/docs\//],
    ['og:image', /^https:\/\/hermes-agent\.nousresearch\.com\/docs\/img\//],
    ['twitter:card', /\S/],
    ['twitter:image', /^https:\/\/hermes-agent\.nousresearch\.com\/docs\/img\//],
  ];

  for (const [property, valuePattern] of requiredMeta) {
    const tag = findTag(
      html,
      new RegExp(`<meta\\b[^>]*(?:property|name)=["']${property}["'][^>]*>`, 'i'),
      `${relativePath} is missing ${property} metadata`,
    );
    if (!tag) continue;
    const content = getAttr(tag, 'content').trim();
    if (!valuePattern.test(content)) {
      fail(`${relativePath} ${property} content ${content || '(empty)'} did not match ${valuePattern}`);
    } else {
      pass(`${relativePath} has valid ${property}`);
    }
  }
}

if (!fs.existsSync(buildDir)) {
  fail(`Build output directory does not exist: ${buildDir}. Run npm run build first.`);
} else {
  pass(`Inspecting generated output in ${path.relative(websiteDir, buildDir)}`);
}

const sitemap = readRequired('sitemap.xml');
for (const route of [
  '',
  'getting-started/quickstart',
  'skills/',
  'reference/skills-catalog',
  'reference/optional-skills-catalog',
]) {
  expectIncludes(sitemap, `${canonicalBase}${route}`, 'sitemap.xml');
}

const robots = readRequired('robots.txt');
expectIncludes(robots, `Sitemap: ${canonicalBase}sitemap.xml`, 'robots.txt');
for (const disallow of ['/docs/api/', '/docs/internal/', '/docs/admin/']) {
  expectIncludes(robots, `Disallow: ${disallow}`, 'robots.txt');
}

const llms = readRequired('llms.txt');
const llmsFull = readRequired('llms-full.txt');
for (const file of [
  ['llms.txt', llms],
  ['llms-full.txt', llmsFull],
]) {
  const [label, contents] = file;
  expectIncludes(contents, `${canonicalBase}getting-started/quickstart`, label);
  expectIncludes(contents, `${canonicalBase}reference/skills-catalog`, label);
}

for (const route of ['/', '/getting-started/quickstart', '/skills/']) {
  checkMetaRoute(route);
}

checkJsonLdRoute('/', {
  types: ['WebSite', 'Organization', 'SoftwareApplication'],
  urls: [canonicalBase],
});
checkJsonLdRoute('/skills/', {
  types: ['CollectionPage', 'ItemList'],
  urls: [`${canonicalBase}skills/`],
});

if (failures.length > 0) {
  console.error('SEO generated-output checks failed:');
  for (const failure of failures) {
    console.error(`  ✗ ${failure}`);
  }
  console.error(`\n${checked.length} checks passed before failure.`);
  process.exit(1);
}

console.log('SEO generated-output checks passed:');
for (const message of checked) {
  console.log(`  ✓ ${message}`);
}
console.log(`\n${checked.length} checks passed.`);
