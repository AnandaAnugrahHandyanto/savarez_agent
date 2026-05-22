#!/usr/bin/env node
// Fail if localized Docusaurus output contains double-prefixed docs links such
// as /docs/zh-Hans/docs/... . These usually come from markdown links that
// hard-code the deployment baseUrl (`/docs/`) instead of using locale-safe
// root-relative doc paths (`/user-guide/...`).

import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';

const websiteDir = resolve(import.meta.dirname, '..');
const buildDir = join(websiteDir, 'build');
const locales = ['zh-Hans', 'ko'];
const pattern = /\/docs\/(zh-Hans|ko)\/docs\//g;
const extensions = new Set(['.html', '.js', '.json']);

function* walk(dir) {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    const stats = statSync(path);
    if (stats.isDirectory()) {
      yield* walk(path);
    } else {
      yield path;
    }
  }
}

function hasCheckedExtension(path) {
  return [...extensions].some((ext) => path.endsWith(ext));
}

if (!existsSync(buildDir)) {
  console.error('[localized-doc-links] build directory not found; run npm run build first.');
  process.exit(1);
}

const missingLocales = locales.filter((locale) => !existsSync(join(buildDir, locale)));
if (missingLocales.length > 0) {
  console.error(`[localized-doc-links] missing localized build directories: ${missingLocales.join(', ')}`);
  process.exit(1);
}

const findings = [];
for (const file of walk(buildDir)) {
  if (!hasCheckedExtension(file)) continue;
  const text = readFileSync(file, 'utf8');
  const matches = [...new Set(text.match(pattern) ?? [])];
  for (const match of matches) {
    findings.push(`${relative(websiteDir, file)}: ${match}`);
  }
}

if (findings.length > 0) {
  console.error('[localized-doc-links] found double-prefixed localized docs links:');
  for (const finding of findings.slice(0, 100)) {
    console.error(`  - ${finding}`);
  }
  if (findings.length > 100) {
    console.error(`  ...and ${findings.length - 100} more`);
  }
  process.exit(1);
}

console.log('[localized-doc-links] no /docs/<locale>/docs/ links found in generated output.');
