---
name: wordpress-wpcli-ops
description: Use when operating or inspecting a WordPress install with WP-CLI for safe runtime changes, diagnostics, cleanup, and verification.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [wordpress, wp-cli, operations, maintenance, multisite]
    related_skills: [wordpress-project-triage, wordpress-migrations-and-deploys, woocommerce-store-ops, systematic-debugging, requesting-code-review]
---

# WordPress WP-CLI Operations

## Overview

Use this skill when the safest control surface is a live or local WordPress install and WP-CLI is available. It covers discovery, inspection, low-risk operational changes, cleanup, and post-change verification.

WP-CLI is often the fastest reliable way to inspect plugins, themes, users, options, cron events, transients, and content relationships without poking the database directly or guessing through the admin UI.

**Core principle:** confirm the target install and environment first, then make the smallest runtime change with a clear before/after verification step.

## When to Use

Use this skill when:
- the task is primarily runtime inspection or maintenance on a known WordPress install
- you need to inspect plugins, themes, users, posts, options, cron, cache, or transients
- you need to run a safe search-replace or URL update
- the user asks for quick WordPress ops without opening the browser admin first

Do not use this skill when:
- the project path or target install is still ambiguous
- the task is a migration, environment move, or rollback-heavy deploy
- the task is mainly WooCommerce store operations needing store-specific verification

## Safe Discovery First

### 1. Confirm WP-CLI is available
Typical checks:
```bash
wp --info
wp cli version
```

### 2. Confirm the correct install path
Run WP-CLI from the install root, or pass an explicit path:
```bash
wp core version
wp option get siteurl
wp option get home
```

If multiple installs may exist, inspect the filesystem first and verify the site URL before changing anything.

### 3. Confirm environment context
Before state-changing commands, record:
- hostname / environment name
- site URL
- multisite vs single-site
- active theme
- active plugins

Useful commands:
```bash
wp core is-installed
wp plugin list
wp theme list
wp option get blogname
```

## High-Value Operations

### Plugin and theme inspection
```bash
wp plugin list
wp plugin status woocommerce
wp theme list
wp theme status twentytwentyfour
```

Use for:
- active/inactive status
- version drift
- update opportunities
- identifying obvious ownership surfaces

### User and role inspection
```bash
wp user list --fields=ID,user_login,user_email,roles
wp role list
```

Use for:
- checking admin access
- verifying role assignments
- finding content owners or test accounts

### Option inspection
```bash
wp option get siteurl
wp option get home
wp option get permalink_structure
```

Use for:
- confirming URL assumptions
- debugging environment mismatches
- checking basic site configuration

### Content inspection
```bash
wp post list --post_type=page --fields=ID,post_title,post_status
wp post get 123 --field=post_title
wp term list category --fields=term_id,name,slug
```

Use for:
- confirming content presence
- enumerating pages or custom post types
- tracing relationships before editing

### Cron inspection
```bash
wp cron event list
wp cron event run --due-now
```

Use for:
- identifying stuck tasks
- checking whether scheduled tasks are overdue
- validating whether a plugin relies on WP-Cron behavior

### Cache and transient cleanup
```bash
wp transient list
wp transient delete --all
wp cache flush
```

Use carefully:
- clear transients when debugging stale settings or cached remote results
- flush caches after deploys or major option changes
- verify front-end effects after cleanup

## Search-Replace Safety

Use `wp search-replace` instead of raw SQL when changing URLs or paths in WordPress data.

Recommended flow:
1. Confirm source and target values exactly.
2. Dry-run first.
3. Prefer precise scope over blanket replacement.
4. Re-verify URLs and sample pages after the change.

Example:
```bash
wp search-replace 'https://old.example.com' 'https://new.example.com' --all-tables --dry-run
wp search-replace 'https://old.example.com' 'https://new.example.com' --all-tables
```

Notes:
- WP-CLI handles serialized data safely; direct SQL often does not.
- Avoid casual replacement across multiple unrelated installs.
- On large sites, expect this command to take time and verify backups first.

## Safe Change Workflow

For any state-changing WP-CLI operation:
1. Inspect current state.
2. Save or report the baseline.
3. Make the smallest change.
4. Re-run the same inspection command.
5. Verify one browser-visible or admin-visible outcome where possible.

Examples:
- before/after `wp option get siteurl`
- before/after `wp plugin status plugin-name`
- before/after `wp cron event list`

## Multisite Caveats

Before making changes, determine if the install is multisite:
```bash
wp site list
wp network meta list 1
```

Important caveats:
- plugin activation can be site-specific or network-wide
- options may live at the site or network level
- user membership can vary by site
- path and domain assumptions differ across sites
- `--url=<site>` may be required to target the correct site

Examples:
```bash
wp --url=https://sub.example.com option get home
wp --url=https://sub.example.com plugin list
```

## Commands to Avoid or Treat as High Risk

Be cautious with:
- direct SQL writes via `wp db query`
- bulk destructive deletion without a precise filter
- plugin/theme updates on production without impact awareness
- blanket cache flushes during incident response unless needed
- search-replace without a dry run and backup confidence

## Verification Patterns

### After plugin changes
- re-run `wp plugin list`
- verify one affected route or admin page
- check logs if the change was error-driven

### After option changes
- re-run `wp option get ...`
- verify the corresponding browser/admin behavior

### After transient/cache cleanup
- verify the stale behavior is actually gone
- confirm no plugin immediately recreates the bad state

### After cron actions
- re-run `wp cron event list`
- inspect plugin-specific downstream effects if applicable

## Related Reference

See `references/common-commands.md` for a grab-bag of frequently useful WP-CLI commands.

## Common Pitfalls

1. **Running WP-CLI against the wrong install.**
   Always confirm the path and `siteurl` first.

2. **Using destructive commands without baseline capture.**
   Before/after inspection is part of the job.

3. **Using raw SQL where WP-CLI has a safe wrapper.**
   Search-replace is the classic example.

4. **Ignoring multisite context.**
   A correct command on one site can be wrong at the network level.

5. **Assuming a CLI change is enough verification.**
   Browser-visible confirmation still matters.

6. **Overusing cache flushes.**
   Clear only what helps the diagnosis.

## Verification Checklist

- [ ] Confirmed WP-CLI availability and the correct install path
- [ ] Captured the target site's URL/environment before making changes
- [ ] Checked for multisite context when relevant
- [ ] Used dry-run or inspection-first flow for risky commands
- [ ] Verified the same surface before and after the change
- [ ] Verified at least one live/admin outcome when possible
