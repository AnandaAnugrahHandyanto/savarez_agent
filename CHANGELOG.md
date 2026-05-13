# Changelog

All notable changes to the DeepParser Developer API are documented here.

## [1.0.0] — 2026-05-14

### Added
- **REST API**: FastAPI service with `/parse` (async + sync mode), `/parse/{job_id}` status polling, `/keys` self-service registration, `/admin/*` management endpoints, `/health` probe, `/openapi.json`
- **Python SDK** (`deepparser` pip package): `DeepParserClient` with `parse_file()`, `parse_file_sync()`, `get_job()`, `register_key()`, `revoke_key()`
- **Authentication**: API key auth via `X-API-Key` header with per-IP rate limiting (10 failures/60s, 5 registrations/hr)
- **Async parse pipeline**: `asyncio.Semaphore`-bounded concurrent parse slots with `SEMAPHORE_TIMEOUT_SECS` backpressure
- **Sync parse mode**: `?mode=sync` on `POST /parse` waits up to `SYNC_WAIT_SECS` and returns inline for small files (<5 MB)
- **Cleanup task**: Background loop deletes completed jobs after 24 h, orphaned in-flight jobs after 48 h
- **Fly.io deployment**: `fly.toml` + `Dockerfile.deepparser` for single-instance SQLite-safe deployment on `shared-cpu-1x`
- **Trusted proxy support**: `TRUSTED_PROXY_CIDRS` env var for correct IP extraction behind Fly.io (`fdaa::/16`) or nginx
- **File safety**: UUID-named uploads (original filename never reaches subprocess), disk reserve guard, size limit (50 MB)
- **Admin API**: `/admin/stats`, `/admin/keys`, `/admin/jobs`, `/admin/purge` protected by `ADMIN_PASSWORD`
- **Test suite**: 52 pytest tests covering auth, parse, admin, cleanup, SDK, and integration flows

### Security
- X-Forwarded-For only trusted from configured `TRUSTED_PROXY_CIDRS` — prevents IP rate-limit bypass
- File cleanup on DB INSERT failure — prevents orphaned uploads
- Semaphore `_acquired` flag prevents count inflation on `asyncio.wait_for` timeout cancellation
- All blocking I/O (`write_bytes`, `os.walk`) offloaded to `asyncio.to_thread` — no event-loop stalls

### Supported Formats
PDF, DOCX, DOC, PPT, PPTX, XLS, XLSX, CSV, TXT, MD, JPG, JPEG, PNG, DWG, DXF
