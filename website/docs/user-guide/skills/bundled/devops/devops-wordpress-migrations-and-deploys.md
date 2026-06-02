---
title: "Wordpress Migrations And Deploys"
sidebar_label: "Wordpress Migrations And Deploys"
description: "Use when moving, deploying, syncing, backing up, or rolling back a WordPress site across local, staging, and production environments"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Wordpress Migrations And Deploys

Use when moving, deploying, syncing, backing up, or rolling back a WordPress site across local, staging, and production environments.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/devops/wordpress-migrations-and-deploys` |
| Version | `1.0.0` |
| Author | Hermes Agent |
| License | MIT |
| Tags | `wordpress`, `migration`, `deploy`, `backup`, `rollback` |
| Related skills | [`wordpress-project-triage`](/docs/user-guide/skills/bundled/software-development/software-development-wordpress-project-triage), [`wordpress-wpcli-ops`](/docs/user-guide/skills/bundled/devops/devops-wordpress-wpcli-ops), [`webhook-subscriptions`](/docs/user-guide/skills/bundled/devops/devops-webhook-subscriptions), [`writing-plans`](/docs/user-guide/skills/bundled/software-development/software-development-writing-plans), [`requesting-code-review`](/docs/user-guide/skills/bundled/software-development/software-development-requesting-code-review) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# WordPress Migrations and Deploys

## Overview

Use this skill for WordPress moves and releases that cross environment boundaries: local to staging, staging to production, production to local, host-to-host migrations, rollback planning, and deploy verification.

WordPress moves are rarely just "copy files." A working site depends on the interaction between code, database content, uploads/media, environment configuration, caches, and URL assumptions. The safest workflow separates those layers explicitly.

**Core principle:** treat code, database, uploads, secrets/config, and cache as separate migration surfaces with separate checkpoints.

## When to Use

Use this skill when:
- moving a site between local, staging, and production
- changing domains or URLs
- deploying code that depends on database state or media assets
- creating backup/restore checkpoints
- planning rollback before a risky WordPress release

Do not use this skill when:
- the task is a small runtime admin change better handled by `wordpress-wpcli-ops`
- the project shape is still unknown; triage first
- the task is only plugin/theme code editing with no environment move

## The Five Migration Surfaces

Always reason about these separately:
1. **Code** — themes, plugins, mu-plugins, config, build artifacts
2. **Database** — posts, options, plugin settings, users, orders, serialized data
3. **Uploads/media** — `wp-content/uploads/` and any offloaded media assumptions
4. **Environment/config** — `.env`, `wp-config.php`, salts, domains, credentials, object cache, CDN, mail
5. **Cache/runtime** — page cache, object cache, transients, opcode cache, CDN cache, cron backlog

## Preflight Checklist

Before moving anything, confirm:
- source and target environments
- canonical source of truth for code
- backup method for database and uploads
- whether WooCommerce or memberships are involved
- maintenance window or content-freeze expectations
- search-replace scope and old/new domains
- rollback owner and rollback trigger point

## Safe Migration Workflow

### 1. Snapshot the baseline
Capture:
- current site URL/home URL
- active plugins/themes
- WordPress and PHP versions
- database dump location
- uploads backup location
- deployment commit SHA or release identifier

### 2. Separate what is actually moving
Common patterns:
- **staging → prod release:** code only, plus DB migration or option changes
- **prod → local clone:** code + DB + uploads + URL rewrite
- **host migration:** everything, plus DNS/CDN/runtime config
- **theme/plugin deploy:** code only, but still verify dependent options and caches

### 3. Back up before mutation
Minimum safe stance:
- a database backup you can restore
- an uploads backup or sync checkpoint when media matters
- confidence that the exact deployed code version can be restored

### 4. Use serialized-data-safe replacement
For domain/path changes, prefer WP-CLI search-replace rather than raw SQL:
```bash
wp search-replace 'https://old.example.com' 'https://new.example.com' --all-tables --dry-run
wp search-replace 'https://old.example.com' 'https://new.example.com' --all-tables
```

### 5. Rebuild and clear only what is needed
Potential post-move steps:
- rebuild theme/plugin assets
- flush caches
- clear transients
- re-save permalinks if routing changed
- run due cron if queues are stuck

### 6. Verify in layers
Check all of these before calling the move done:
- homepage loads
- admin login works
- one representative content page works
- media loads from expected storage
- forms/cart/checkout/account flows work if applicable
- background jobs or cron are not obviously stuck

## Common Migration Scenarios

### Production → local
Typical needs:
- DB dump/import
- uploads sync
- URL rewrite
- mail/payment safeguards disabled locally
- search indexing disabled locally if needed

Watch for:
- hardcoded domains
- object cache config carried over incorrectly
- third-party API side effects from copied cron/jobs

### Staging → production
Typical needs:
- deploy code from version control
- run targeted DB changes only if required
- avoid blindly copying staging DB over production
- clear deploy-related caches

Watch for:
- overwriting production orders, users, comments, or form submissions
- schema changes not matched by code
- environment constants drifting between staging and production

### Host-to-host migration
Typical needs:
- full code sync
- full DB transfer
- uploads/media transfer
- DNS/SSL/CDN alignment
- PHP extension/version parity

Watch for:
- file permissions/ownership
- Nginx/Apache rewrites
- object cache or Redis/Memcached endpoints
- offloaded media or CDN origin paths

## Rollback Planning

Define rollback before deployment, not after failure.

Minimum rollback plan:
- what exact code version to restore
- where the last known-good DB backup lives
- whether uploads changed during the release window
- who decides rollback vs forward-fix
- what user-visible checks trigger rollback

If a release includes irreversible data mutation, say that explicitly and tighten the checkpoint discipline.

## WooCommerce and Other High-Risk Sites

Extra caution for:
- live orders/payments
- subscriptions/memberships
- booking systems
- LMS/course progress
- form submissions

Rules of thumb:
- do not overwrite a live production DB with stale staging content
- minimize maintenance windows but prefer explicit freeze rules for risky changes
- verify order creation, checkout, tax/shipping, and email side effects after release

## Post-Move Verification

Run a representative smoke test set:
- front page
- key landing page
- admin dashboard
- plugin/theme status
- media rendering
- contact form or transactional path
- WooCommerce cart/checkout for stores
- cron or scheduled job visibility

## Related Reference

See `references/rollback-checklist.md` for a compact rollback checklist you can copy into a deployment handoff.

## Common Pitfalls

1. **Treating WordPress deploys as code-only when data changed too.**
   Many failures are option, URL, upload, or cache mismatches.

2. **Using raw SQL for URL rewrites.**
   Serialized data corruption is a classic self-inflicted outage.

3. **Overwriting production data with staging data.**
   Especially dangerous on WooCommerce or membership sites.

4. **Skipping uploads/media as a distinct surface.**
   Broken media is one of the most common post-migration issues.

5. **No rollback plan.**
   A backup that cannot be found or restored is not a real fallback.

6. **Calling the deploy done after one homepage check.**
   Always verify at least one real business-critical path.

## Verification Checklist

- [ ] Identified which of code, DB, uploads, config, and cache are changing
- [ ] Captured or confirmed backups/checkpoints before mutation
- [ ] Used serialized-data-safe search-replace where URLs/paths changed
- [ ] Defined rollback inputs and trigger conditions before release
- [ ] Verified representative frontend, admin, and business-critical paths after the move
- [ ] Avoided destructive staging-to-production data overwrite for live transactional sites
