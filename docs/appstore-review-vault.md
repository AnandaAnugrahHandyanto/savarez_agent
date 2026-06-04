# App Store Review Vault

Local web app for collecting public iOS App Store reviews from Apple's iTunes RSS customerreviews endpoints.

## Scope

For each active app ID it fetches:

- countries: `us`, `gb`, `ca`, `au`
- sorts: `mostrecent`, `mosthelpful`
- pages: `1..10`
- format: JSON

Endpoint shape:

```text
https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortby={sort}/json
```

This collects only reviews Apple exposes through the public RSS endpoint. It is capped at roughly 500 reviews per country per sort.

## Run

```bash
appstore-review-vault --host 0.0.0.0 --port 8765
```

Or directly:

```bash
uvicorn appstore_review_vault.main:app --host 0.0.0.0 --port 8765
```

Open:

```text
http://localhost:8765
```

Over Tailscale, use the host's Tailscale name/IP and port `8765`.

## Seed apps

Edit `data/apps.yaml`:

```yaml
apps:
  - app_id: "1477376905"
    name: "GitHub"
```

Apps can also be added in the web UI.

## Storage

Default SQLite path:

```text
data/appstore_reviews.sqlite
```

Back up with:

```bash
sqlite3 data/appstore_reviews.sqlite ".backup 'data/appstore_reviews.backup.sqlite'"
```

## Archive behavior

Apps are archived, not deleted. Archived apps are excluded from refresh-all and hidden by default, but reviews remain stored and can be included in searches/exports.

## Rate limits

The fetcher stops a run after 3 consecutive `403` or `429` responses. Keep refreshes manual and conservative.
