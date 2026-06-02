---
title: "Wordpress Project Triage"
sidebar_label: "Wordpress Project Triage"
description: "Use when inspecting an unfamiliar WordPress repo, site, plugin, or theme so you can map boundaries, tooling, risks, and validation surfaces before editing"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Wordpress Project Triage

Use when inspecting an unfamiliar WordPress repo, site, plugin, or theme so you can map boundaries, tooling, risks, and validation surfaces before editing.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/software-development/wordpress-project-triage` |
| Version | `1.0.0` |
| Author | Hermes Agent |
| License | MIT |
| Tags | `wordpress`, `triage`, `repo-inspection`, `plugins`, `themes` |
| Related skills | [`wordpress-project-router`](/docs/user-guide/skills/bundled/software-development/software-development-wordpress-project-router), [`wordpress-wpcli-ops`](/docs/user-guide/skills/bundled/devops/devops-wordpress-wpcli-ops), [`wordpress-migrations-and-deploys`](/docs/user-guide/skills/bundled/devops/devops-wordpress-migrations-and-deploys), [`systematic-debugging`](/docs/user-guide/skills/bundled/software-development/software-development-systematic-debugging), [`requesting-code-review`](/docs/user-guide/skills/bundled/software-development/software-development-requesting-code-review) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# WordPress Project Triage

## Overview

Use this skill to inspect an unfamiliar WordPress project before making changes. The goal is to determine what kind of WordPress surface you have, where responsibility boundaries are, which toolchain controls it, and how you can verify changes safely.

WordPress projects vary wildly: full-site repos, Bedrock setups, plugin-only repos, classic themes, block themes, child themes, headless content backends, Dockerized local stacks, and shared-hosting exports. Good triage prevents edits in the wrong layer.

**Core principle:** identify structure, ownership boundaries, runtime assumptions, and validation paths before touching code or data.

## When to Use

Use this skill when:
- a repo or server might be WordPress but you have not classified it yet
- the user asks you to "look at this WordPress project" or "figure out how this site is wired"
- you need to know whether the task belongs to a plugin, theme, infrastructure, content, or store layer
- you need to discover test/build/deploy surfaces in a WordPress codebase

Do not use this skill when:
- the exact project shape is already known and a narrower WordPress skill clearly applies
- the task is only a simple live-site WP-CLI operation and the install/path is already known

## Triage Workflow

### 1. Confirm the WordPress surface
Inspect for these markers first:
- `wp-config.php`
- `wp-content/`
- `wp-includes/version.php`
- `wp-content/plugins/`
- `wp-content/themes/`
- Bedrock signals such as `config/application.php`, `web/wp`, `.env`, `composer.json` with roots/bedrock packages
- local dev stack files like `.ddev/`, `.lando.yml`, `docker-compose.yml`, `wp-env.json`

If none appear, do not force a WordPress interpretation.

### 2. Classify the repo shape
Pick the closest fit:
- **Full site repo** — contains WordPress app structure or Bedrock layout
- **Plugin repo** — isolated plugin code, plugin header, plugin tests/build files
- **Theme repo** — classic or block theme, likely `style.css`, `functions.php`, templates, `theme.json`
- **Child theme repo** — minimal overrides over a parent theme
- **Headless split** — WordPress backend plus separate frontend app
- **Ops wrapper** — deployment scripts, infra config, backup/migration tooling

### 3. Detect boundaries that matter
Record where each concern lives:
- theme/presentation logic
- plugin/business logic
- WooCommerce/store behavior
- site configuration and secrets
- build outputs and generated assets
- deployment configuration
- custom mu-plugins or must-use bootstrap code

### 4. Detect build and dependency chains
Inspect for:
- `composer.json` / `composer.lock`
- `package.json` / lockfiles
- bundlers: Vite, Webpack, Parcel, @wordpress/scripts
- PHP standards/test tools: PHPUnit, PHPCS, Pest, Rector, PHPStan
- JS test tools: Vitest, Jest, Playwright, Cypress
- local stacks: DDEV, Lando, wp-env, Docker Compose

Important: identify **source files vs built assets**. Do not patch a generated bundle if the source tree is present.

### 5. Infer WordPress/runtime assumptions
Check for:
- WordPress core version pins or expectations
- PHP version requirements
- WooCommerce dependency/version requirements
- multisite assumptions
- custom constants, env vars, salts, domain mappings, or content-dir moves

### 6. Identify available validation surfaces
Prefer the strongest available signals:
- unit/integration tests
- lint/type/static-analysis tools
- local site startup commands
- WP-CLI commands
- browser-visible routes or admin flows
- deployment preview/staging environment

If tests are absent, define a manual verification path before editing.

## File and Directory Signals

### Full site or Bedrock
Common signals:
- `wp-config.php`
- `wp-content/`
- `web/wp` or `web/app`
- `config/application.php`
- `.env.example`

### Plugin repo
Common signals:
- main plugin PHP file with `Plugin Name:` header
- `readme.txt`
- `uninstall.php`
- `languages/`, `assets/`, `includes/`, `src/`

### Theme repo
Common signals:
- `style.css` with `Theme Name:` header
- `functions.php`
- `templates/`, `parts/`, `patterns/`
- `theme.json`
- `block-templates/` or block assets

### WooCommerce-heavy customization
Common signals:
- checkout/cart hooks
- product import/export helpers
- custom order admin code
- extension-specific folders or package names

## Questions to Answer Before Editing

Write down concise answers to these:
1. What exact WordPress surface is this?
2. Which folder or repo owns the requested behavior?
3. Is WooCommerce involved?
4. What versions or environment assumptions matter?
5. What command or browser path will prove the change worked?
6. What could break if this assumption is wrong?

## Triage Commands and Checks

Typical actions:
- search for WordPress marker files and headers
- inspect `composer.json` and `package.json`
- search for plugin/theme names mentioned by the user
- read config/bootstrap files before editing behavior files
- look for CI/test scripts and project README setup notes

When a live install is available, combine repo inspection with safe runtime discovery:
- `wp core version`
- `wp plugin list`
- `wp theme list`
- `wp option get siteurl`

Use runtime commands only after confirming the correct project path and environment.

## Boundary Heuristics

### If a bug is visual
Check, in order:
1. theme/template overrides
2. block theme templates or patterns
3. WooCommerce template overrides
4. plugin CSS/JS injection
5. cache/minification layers

### If a bug is behavioral
Check, in order:
1. plugin hooks/filters/actions
2. custom mu-plugins
3. theme `functions.php`
4. WooCommerce extensions
5. server/runtime configuration

### If a bug appears only after deploy or migration
Prefer `wordpress-migrations-and-deploys` and inspect:
- URL/path assumptions
- serialized data changes
- uploads/media sync
- cache invalidation
- environment-specific constants

## Hand-off Guidance

After triage, route clearly:
- runtime maintenance or inspection → `wordpress-wpcli-ops`
- migration/release/rollback → `wordpress-migrations-and-deploys`
- store/catalog/order issues → `woocommerce-store-ops`
- code implementation → continue with normal repo workflows after the WordPress boundaries are mapped

## Common Pitfalls

1. **Editing the wrong layer.**
   WordPress often splits behavior across plugin, theme, mu-plugin, and admin settings.

2. **Ignoring generated assets.**
   Many modern themes/plugins compile JS/CSS; patch source, then rebuild if needed.

3. **Assuming the repo contains the full site.**
   Some repos only ship a plugin or theme and depend on an external WordPress install.

4. **Skipping version assumptions.**
   A block-theme fix may depend on WordPress core or WooCommerce versions.

5. **Using live WP-CLI before confirming environment.**
   The same server may host several installs.

6. **Trusting only repo structure.**
   Runtime state, active plugins, and admin settings can materially change behavior.

## Verification Checklist

- [ ] Confirmed whether this is a full site, plugin, theme, child theme, headless backend, or ops wrapper
- [ ] Identified the directories or files that actually own the requested behavior
- [ ] Identified Composer/npm/build/test surfaces, if any
- [ ] Noted WordPress, PHP, WooCommerce, and multisite assumptions where relevant
- [ ] Chosen a downstream skill or validation path before editing
- [ ] Avoided changing generated artifacts when source files are available
