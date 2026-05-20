#!/usr/bin/env node
// Lightweight docs quality gates that complement the Docusaurus build.
// Docusaurus catches broken links. This script catches repository-specific
// drift: docs missing from the sidebar, generated docs that were not committed,
// and stale generated LLM entrypoints.

import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const websiteDir = resolve(scriptDir, "..");
const repoRoot = resolve(websiteDir, "..");
const docsDir = join(websiteDir, "docs");
const sidebarFile = join(websiteDir, "sidebars.ts");

const allowlistedOrphans = new Set([
  // Root landing page is routed as / and intentionally not listed as a sidebar item.
  "index",
  // Advanced/dev docs that are linked contextually but intentionally hidden from primary nav.
  "developer-guide/browser-supervisor",
  "developer-guide/web-search-provider-plugin",
  "guides/google-gemini",
  "guides/local-ollama-setup",
  "guides/minimax-oauth",
  "guides/pipe-script-output",
  "user-guide/messaging/google_chat",
  "user-guide/skills/godmode",
  "user-guide/skills/google-workspace",
]);

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    const st = statSync(path);
    if (st.isDirectory()) out.push(...walk(path));
    else out.push(path);
  }
  return out;
}

function docIdFromPath(path) {
  let rel = relative(docsDir, path).replaceAll("\\\\", "/");
  rel = rel.replace(/\.(md|mdx)$/u, "");
  if (rel.endsWith("/index")) return rel.slice(0, -"/index".length);
  return rel;
}

function collectSidebarIds() {
  const source = readFileSync(sidebarFile, "utf8");
  const ids = new Set();
  for (const match of source.matchAll(/['"]([^'"]+)['"]/gu)) {
    const value = match[1];
    if (!value.includes("/") && !value.startsWith("user-stories")) continue;
    ids.add(value);
    if (value.endsWith("/index")) ids.add(value.slice(0, -"/index".length));
  }
  return ids;
}

function checkSidebarCoverage() {
  const sidebarIds = collectSidebarIds();
  const docs = walk(docsDir)
    .filter((p) => /\.(md|mdx)$/u.test(p))
    .filter((p) => !p.endsWith("_category_.json"))
    .map(docIdFromPath);

  const missing = docs
    .filter((id) => !sidebarIds.has(id) && !allowlistedOrphans.has(id))
    .sort();

  if (missing.length > 0) {
    console.error("Docs missing from website/sidebars.ts:");
    for (const id of missing) console.error(`  - ${id}`);
    console.error("Add them to the sidebar or intentionally allowlist them in scripts/check-docs.mjs.");
    process.exitCode = 1;
  }
}

function checkGeneratedFreshness() {
  const generated = [
    "website/src/data/skills.json",
    "website/static/llms.txt",
    "website/static/llms-full.txt",
    "website/docs/reference/skills-catalog.md",
    "website/docs/reference/optional-skills-catalog.md",
  ].filter((p) => existsSync(join(repoRoot, p)));

  if (generated.length === 0) return;

  try {
    execFileSync("git", ["diff", "--quiet", "--", ...generated], {
      cwd: repoRoot,
      stdio: "pipe",
    });
  } catch {
    console.error("Generated docs/data are stale after prebuild:");
    const diff = execFileSync("git", ["diff", "--", ...generated], {
      cwd: repoRoot,
      encoding: "utf8",
      maxBuffer: 1024 * 1024,
    });
    console.error(diff.slice(0, 12000));
    console.error("Run `npm run prebuild` in website/ and commit the generated outputs.");
    process.exitCode = 1;
  }
}

checkSidebarCoverage();
checkGeneratedFreshness();

if (process.exitCode) process.exit(process.exitCode);
console.log("Docs checks passed: sidebar coverage + generated freshness.");
