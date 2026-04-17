# Stack: Obsidian Sync (CouchDB + LiveSync)

**Images:** `couchdb:3.3`, `livesync-cli:latest`
**URL:** [couchdb.jaxmind.xyz](https://couchdb.jaxmind.xyz)
**Networks:** `proxy`

---

## Purpose

Provides Obsidian LiveSync backend so the Obsidian vault on mobile/desktop syncs via a self-hosted CouchDB instance rather than Obsidian Sync (paid service) or iCloud/Dropbox.

## Services

### CouchDB

Standard CouchDB 3.3. The Obsidian LiveSync plugin connects directly to `https://couchdb.jaxmind.xyz` using the CouchDB HTTP API.

**CORS config:** Required for the Obsidian app (which runs as a local/capacitor origin) to make cross-origin requests to CouchDB. Configured via Traefik headers middleware:
- Allowed methods: `GET, PUT, POST, HEAD, DELETE`
- Allowed headers: `accept, authorization, content-type, origin, referer`
- Allowed origins: `app://obsidian.md, capacitor://localhost, http://localhost`

### obsidian-livesync-daemon

A daemon that runs `livesync-cli` in a loop every 10 seconds:
1. `livesync-cli mirror` — mirrors vault changes to a local CouchDB database
2. `livesync-cli sync` — syncs the local database with the remote CouchDB

This provides a server-side sync process so the vault is always up-to-date even when no Obsidian clients are connected.

**Note:** There is an open issue ([PAB-8](https://linear.app/pablot/issue/PAB-8)) to replace this daemon approach with native CouchDB replication.

## Data

- `couchdb_data` volume — CouchDB database files (on `/mnt/data/docker`)
- `/lab/obsidian_vault` — local copy of the Obsidian vault on VPS

## Config Choices

| Decision | Why |
|---|---|
| CouchDB instead of other sync backends | Obsidian LiveSync plugin natively supports CouchDB |
| No basic auth on CouchDB router | Auth is handled by CouchDB itself (username/password in plugin settings) |
| CORS via Traefik headers middleware | CouchDB built-in CORS config can be complex; Traefik headers are reliable |

## Secrets

| Env var | What it is |
|---|---|
| `COUCHDB_USER` | CouchDB admin username |
| `COUCHDB_PASSWORD` | CouchDB admin password |

## Known Issues

- CouchDB restart loop ([PAB-5](https://linear.app/pablot/issue/PAB-5)) — intermittent restarts under investigation
- livesync-cli daemon approach may be replaced ([PAB-8](https://linear.app/pablot/issue/PAB-8))

## Obsidian Plugin Setup

In Obsidian: Settings → Community Plugins → Self-hosted LiveSync:
- Remote database URI: `https://couchdb.jaxmind.xyz`
- Username + password from `.env`
- Database name: (your vault name)
