# DevOps runbook drift after reverse proxy / healthcheck changes

Use this when an existing app portfolio project has just gained Nginx/reverse-proxy routing, Compose healthchecks, or DB-backed health endpoints.

## Durable lesson
After runtime changes pass, the README/runbook often becomes the next source of bugs. Treat documentation as an operational artifact: it must match the real Compose topology, published ports, health routes, and smoke-test commands.

## What to update
- Architecture diagram: show public host port, reverse proxy, internal app port, DB service, and volume.
- Tech stack: include reverse proxy service/version if present.
- Implemented-work list: include Nginx/reverse proxy, DB-backed health endpoints, healthcheck dependency ordering.
- Run locally section: public URL should use the reverse proxy port, not the app's internal port.
- Expected containers: include proxy, app, and db with health status and published ports.
- Smoke tests: include `/health`, `/api/health` if supported, and a real data endpoint like `/products`.
- Healthchecks: document the actual commands from Compose, not the old API route.
- Logs/troubleshooting: include proxy logs and published-port conflicts.
- Production TODOs: remove items that are already done (for example “add Nginx” or “add real health endpoint”).
- Portfolio summary: mention concrete operational proof, e.g. DB-backed healthchecks and reverse proxying.

## Verification pattern
Run checks after editing docs:

```bash
# Find stale docs; remaining :3000 references should be explicitly internal-only.
grep -n 'localhost:3000\|:3000\|Add Nginx\|real `/health`' README.md || true

# Confirm the new topology and health docs are present.
grep -n '8080\|nginx\|Nginx\|/api/health\|DB-backed' README.md | sed -n '1,120p'

# Runtime still agrees with the docs.
docker compose config --quiet
curl -fsS http://localhost:8080/health >/dev/null
curl -fsS http://localhost:8080/api/health >/dev/null
curl -fsS http://localhost:8080/products >/dev/null
```

## Pitfall: secret-like placeholders in docs
Tool output may mask strings that look like bearer tokens, making it appear that a Markdown curl example is still broken or unchanged. Prefer examples like:

```bash
-H "Authorization: Bearer ${ADMIN_TOKEN}" \
```

Then verify structurally instead of trusting displayed output:

```python
from pathlib import Path
line = [l for l in Path('README.md').read_text().splitlines() if 'Authorization:' in l][0]
assert '${ADMIN_TOKEN}' in line
assert line.rstrip().endswith('" \\')
```

The lesson is not “the tool is broken”; the durable pattern is to avoid literal secret-looking placeholders and validate the file content structurally when redaction/masking may affect display.