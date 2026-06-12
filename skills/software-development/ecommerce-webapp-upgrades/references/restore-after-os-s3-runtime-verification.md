# Restore-after-OS S3 + runtime verification pattern

Use when the user says they formatted/reinstalled the OS and restored an ecommerce/project folder from S3 or other backup storage, then asks whether everything is there.

## Goal

Do not treat "files restored" and "project ready to work" as the same claim. Verify in layers and report each layer separately:

1. Backup completeness: compare the restored local tree against the S3 prefix or backup manifest.
2. Local toolchain: verify runtime binaries required by the repo (`node`, `npm`, Docker, Compose, Buildx, GitHub CLI if GitHub work is requested).
3. Dependency integrity: run package install from lockfiles and syntax/tests/audit.
4. Container/runtime health: build/start the Compose stack, inspect container health, then smoke-test HTTP endpoints.
5. Repository continuity: verify git remotes/auth separately before promising GitHub sync or deployment readiness.

## Practical sequence

### 1) Compare backup to local project

Prefer an explicit local-vs-S3 diff/count, not a vague `aws s3 ls` scan. Report the result as:

- missing files: N
- extra local files: N, if relevant
- skipped/generated directories, if excluded intentionally (`node_modules`, build outputs, DB volumes, caches)

### 2) Repair runtime without calling it project loss

After an OS format, missing binaries, broken symlinks, uninstalled Docker, and stale shell group membership are runtime/tooling issues, not proof that the project backup failed. Keep the language clean:

- "Project artifacts restored" = source/config/assets are present.
- "Local workstation ready" = tools/deps/services/tests have been verified.

### 3) Verify Node/Express projects

Typical minimum checks:

```bash
npm ci
node --check index.js
node --check public/app.js
npm test
npm audit --omit=dev --audit-level=high
```

Adapt file names to the real project; inspect before assuming `index.js` or `public/app.js` exists.

### 4) Verify Docker/Compose projects

```bash
docker compose up -d --build
docker compose ps
```

If Docker group membership was just changed and the current shell cannot access `/var/run/docker.sock`, use the `docker-on-ubuntu-24-from-apt` skill's same-session verification pattern (`sg docker -c 'docker ...'`) and tell the user to open a new terminal or run `newgrp docker`.

### 5) Smoke-test through the user-facing entrypoint

For a local Caddy/reverse-proxy stack, verify the proxy, not only the app container:

```bash
curl -fsS http://localhost/health
curl -fsS http://localhost/api
curl -fsS http://localhost/products
curl -fsSI http://localhost/
curl -fsSI http://localhost/admin
```

Also test auth boundaries when relevant:

```bash
curl -s -o /tmp/orders-noauth.json -w '%{http_code}\n' http://localhost/orders
```

Expected result depends on the app, but unauthenticated admin/order mutation access should not be open.

### 6) Check Compose project naming drift

If the restored folder name differs from the intended product name, Compose may derive surprising container names (for example `aa-app-1` instead of `rscollection-app-1`). If scripts/docs expect stable names, recommend adding an explicit top-level Compose name:

```yaml
name: rscollection
```

Then recreate the stack deliberately. Do not make this change silently if it will rename existing containers/volumes; explain the scope first.

## Reporting format

Separate the final report into:

- **Backup completeness** — whether files are present.
- **Tooling repaired/verified** — exact versions or blockers.
- **Project verification** — tests, audit, build, container health, HTTP smoke results.
- **Remaining safe next actions** — e.g. GitHub auth/remote reconnect, Compose naming cleanup.

Avoid saying "everything is there" until both artifact completeness and runtime verification are done. If final endpoint/GitHub checks were blocked or not run, say that plainly and leave them as next actions rather than implying completion.
