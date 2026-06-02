---
name: wordpress-project-router
description: Use when a request might involve WordPress, WooCommerce, a theme, a plugin, or site operations and you need to route to the right specialized skill first.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [wordpress, woocommerce, routing, triage, skills]
    related_skills: [wordpress-project-triage, wordpress-wpcli-ops, wordpress-migrations-and-deploys, woocommerce-store-ops, systematic-debugging]
---

# WordPress Project Router

## Overview

Use this skill to decide what kind of WordPress surface you are actually dealing with before you start changing code, content, data, or infrastructure.

WordPress requests are easy to misroute. A user may say "fix my WordPress site" when the real task is one of several very different jobs: plugin development, theme work, WooCommerce catalog operations, WP-CLI maintenance, a staging-to-production migration, or admin/editor cleanup. The right first move is to classify the surface, then load the downstream skill that fits.

**Core principle:** do not treat all WordPress work as generic PHP or generic web debugging. Route first, then act.

## When to Use

Use this skill when:
- the user mentions WordPress, WooCommerce, wp-content, wp-admin, Gutenberg, block themes, plugins, themes, or WP-CLI
- the repo or server might be a WordPress install but that is not yet confirmed
- the task could involve both code and content/admin operations
- you need to decide whether to inspect files, use WP-CLI, browse the live site, or plan a migration

Do not use this skill when:
- the project type is already confirmed and a narrower WordPress skill clearly applies
- the work is generic Linux or generic database administration with no WordPress-specific behavior

## Quick Routing Questions

Ask yourself these in order:
1. Is this a **WordPress install**, a **theme/plugin repo**, or only a **server hosting WordPress**?
2. Is the request about **code**, **content/admin**, **store operations**, or **deployment/migration**?
3. Is there a **live site** to inspect, a **repo** to inspect, or both?
4. Is the safest control surface **files**, **WP-CLI**, **browser/admin UI**, or a **deployment workflow**?

## Fast Signals to Inspect First

### Filesystem / repo signals
- `wp-config.php`
- `wp-content/`
- `wp-content/plugins/<name>/`
- `wp-content/themes/<name>/`
- `style.css` with WordPress theme headers
- `theme.json`
- `block.json`
- `composer.json`
- `package.json`
- `mu-plugins/`
- `docker-compose.yml`, `.ddev/`, `.lando.yml`, `Local/`, `Bedrock/`, `Trellis/`

### Site / runtime signals
- `/wp-admin/`
- `/wp-json/`
- WooCommerce endpoints like `/cart`, `/checkout`, `/my-account`
- visible block-theme editing or Site Editor usage
- hosting/deployment references such as WP Engine, Kinsta, Pantheon, Pressable, or shared cPanel workflows

## Routing Map

### 1. Unknown WordPress project or unfamiliar repo
Load: `wordpress-project-triage`

Use when:
- you need to confirm whether the repo is a full site, theme, plugin, headless frontend, or only ops tooling
- you do not yet know the validation surface
- you need to inspect version assumptions, build chains, and boundaries first

### 2. WP-CLI-driven site operations
Load: `wordpress-wpcli-ops`

Use when tasks involve:
- plugin/theme activation or deactivation
- option, user, post, menu, comment, or cron inspection
- safe cache/transient cleanup
- search-replace or URL updates
- maintenance on a live or staging install

### 3. Migration, deploy, backup, staging, or rollback work
Load: `wordpress-migrations-and-deploys`

Use when tasks involve:
- moving a site between local, staging, and production
- syncing code, database, and uploads
- URL rewrites
- deployment risk management
- backup checkpoints and rollback planning

### 4. WooCommerce store changes or investigations
Load: `woocommerce-store-ops`

Use when tasks involve:
- products, variations, stock, orders, coupons, shipping, tax, payment gateways
- store behavior after plugin changes
- order triage or catalog sanity checks

### 5. Theme/plugin/block development
Usually start with: `wordpress-project-triage`, then continue with the repo's normal software-development skills.

Typical cases:
- plugin bug fixes
- custom theme or child-theme work
- block/theme.json/block.json problems
- REST integration or headless behavior

### 6. Content/editor/admin workflows
If the task is mainly publishing, menus, patterns, templates, or page-builder/UI work, begin with triage and prefer browser-backed verification over code-first assumptions.

## Common Project Shapes

### Full WordPress site repo
Signals:
- root contains `wp-config.php` or Bedrock equivalents
- includes `wp-content/`, deployment config, maybe database helpers

Bias:
- start with `wordpress-project-triage`
- use `wordpress-wpcli-ops` for safe runtime inspection
- use `wordpress-migrations-and-deploys` for release/move work

### Plugin repo
Signals:
- plugin header in a main PHP file
- `readme.txt`, `composer.json`, PHPUnit or WP test config

Bias:
- start with `wordpress-project-triage`
- treat activation/testing boundaries carefully
- do not assume theme-level control

### Theme or block-theme repo
Signals:
- `style.css`, `functions.php`, templates, `theme.json`, `templates/`, `parts/`

Bias:
- start with `wordpress-project-triage`
- verify whether this is classic theme, hybrid, or full-site editing theme
- browser verification matters after code edits

### WooCommerce-heavy project
Signals:
- WooCommerce plugin dependency
- custom checkout/cart/product logic
- order-management or fulfillment hooks

Bias:
- route to `woocommerce-store-ops` for operational tasks
- combine with `wordpress-project-triage` when code ownership is unclear

### Headless WordPress
Signals:
- WordPress used for content/backend only
- frontend repo in Next.js/Nuxt/Gatsby or another stack
- heavy REST or GraphQL use

Bias:
- triage both repos or both surfaces
- do not assume a frontend bug lives inside WordPress
- verify content, API, and frontend layers separately

### Ops-only server task
Signals:
- user asks about backups, disk usage, PHP-FPM, Nginx/Apache, cron, SSL, or deploy failures

Bias:
- confirm whether the issue is above WordPress or inside it
- use WordPress-specific skills only after the hosting layer is understood

## Recommended First Move by Situation

- "I have a WordPress repo and I don't know what kind" → `wordpress-project-triage`
- "Change the site URL / inspect plugins / clear transients" → `wordpress-wpcli-ops`
- "Move staging to production" → `wordpress-migrations-and-deploys`
- "Update products / inspect orders" → `woocommerce-store-ops`
- "Fix this custom plugin/theme bug" → `wordpress-project-triage`, then continue with normal code and test workflows

## Common Pitfalls

1. **Treating WooCommerce as ordinary WordPress content.**
   Product, order, tax, shipping, and extension interactions need store-specific checks.

2. **Jumping into PHP edits before classifying the repo.**
   Many WordPress repos are deployment wrappers, Bedrock structures, or theme/plugin-only repos.

3. **Using WP-CLI blindly on the wrong install.**
   Always confirm the target path, URL, environment, and multisite context first.

4. **Assuming browser-visible bugs are always theme bugs.**
   They may come from plugin hooks, cache layers, WooCommerce templates, or editor settings.

5. **Using migration steps for small content changes.**
   If the task is just runtime inspection or a single setting update, prefer WP-CLI or admin verification.

## Verification Checklist

- [ ] Confirmed this is actually WordPress or WooCommerce
- [ ] Classified the request as code, runtime ops, migration/deploy, or store ops
- [ ] Identified whether the primary surface is repo, server, site admin, or live frontend
- [ ] Loaded the narrower downstream skill before making changes
- [ ] Named the validation surface before acting
