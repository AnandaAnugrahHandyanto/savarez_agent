# WP-CLI Common Commands

Use these as a quick reference after you have already confirmed the correct install path and environment.

## Core and Environment

```bash
wp --info
wp cli version
wp core version
wp core is-installed
wp option get siteurl
wp option get home
```

## Plugins and Themes

```bash
wp plugin list
wp plugin status <plugin-slug>
wp plugin activate <plugin-slug>
wp plugin deactivate <plugin-slug>
wp theme list
wp theme status <theme-slug>
wp theme activate <theme-slug>
```

## Users and Roles

```bash
wp user list --fields=ID,user_login,user_email,roles
wp user get <id-or-login>
wp role list
```

## Content and Taxonomy

```bash
wp post list --post_type=page --fields=ID,post_title,post_status
wp post get <post-id>
wp term list category --fields=term_id,name,slug
wp menu list
```

## Maintenance

```bash
wp cron event list
wp cron event run --due-now
wp transient list
wp transient delete --all
wp cache flush
```

## Search/Replace

```bash
wp search-replace 'https://old.example.com' 'https://new.example.com' --all-tables --dry-run
wp search-replace 'https://old.example.com' 'https://new.example.com' --all-tables
```

## Multisite

```bash
wp site list
wp --url=https://sub.example.com plugin list
wp --url=https://sub.example.com option get home
```
