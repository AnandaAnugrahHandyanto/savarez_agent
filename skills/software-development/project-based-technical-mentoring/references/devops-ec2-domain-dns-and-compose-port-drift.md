# EC2 Docker Compose domain/DNS and port-drift coaching notes

Use this when coaching an EC2 + Docker Compose deployment that is being connected to a registrar-managed domain and the runtime/docs/CI have drifted.

## Verify real state before advising

Check all three layers separately:

1. **Runtime/service**
   - `docker compose ps`
   - `curl -fsS http://localhost/health`
   - `curl -fsS http://localhost/products | grep -q "<known product>"`
2. **External reachability**
   - `curl -I http://PUBLIC_IP/`
   - `curl http://PUBLIC_IP/health`
   - `curl http://DOMAIN/health`
3. **AWS networking**
   - EC2 public/Elastic IP attached to the expected instance.
   - Security group has only needed public web ports: 80 and later 443.
   - Remove stale ports such as public 8080 after Compose moves to `80:80`.
   - Do not tighten SSH from `0.0.0.0/0` unless the user's current IP is known, or you may lock them out.

## Compose port drift pattern

If containers show something like:

```text
nginx   0.0.0.0:80->80/tcp
```

then local checks must use:

```bash
curl -fsS http://localhost/health
curl -fsS http://localhost/products
```

not `localhost:8080`.

When `docker-compose.yaml` changes from `8080:80` to `80:80`, search and update all references:

- `.github/workflows/*.yml`
- `scripts/check-stack.sh`
- `README.md`
- smoke-test commands
- security group rules

Typical fixes:

```bash
# CI/smoke checks
http://localhost:8080/health   -> http://localhost/health
http://localhost:8080/products -> http://localhost/products

# exposure assertion
grep 'published: "8080"' -> grep 'published: "80"'
```

## API path drift pattern

Do not assume `/api/products` exists. Inspect backend routes. If the app exposes `/products` and `/featured-products`, CI and smoke checks should use those exact paths. A false-positive symptom is `/api/products` returning frontend HTML with HTTP 200 due to SPA/static fallback; content-type/body assertions must catch this.

## Hostinger DNS pattern

For a root domain on Hostinger pointing to EC2:

```text
A      @      ELASTIC_IP
CNAME  www    root-domain.example
```

Do **not** add `A www` if `www` already has a CNAME; DNS forbids CNAME coexisting with other record types for the same name.

Delete duplicate/conflicting root A records. Authoritative Hostinger nameservers may be correct while public resolvers still cache an old Hostinger parking IP. Verify with multiple layers:

```bash
dig +short NS example.com
dig +short A example.com @<authoritative-ns>
dig +short A example.com @1.1.1.1
dig +short A example.com @8.8.8.8
curl -I http://example.com
curl http://example.com/health
```

If the browser still shows Hostinger parking while authoritative DNS points to EC2, coach the user to flush DNS/cache and open `http://` explicitly. Before HTTPS is configured, browsers may auto-upgrade to `https://` and fail even though HTTP works.

## HTTPS next-step guidance

Once HTTP domain and `www` work, add HTTPS. For a Docker Compose app with an Nginx container used only as a reverse proxy, Caddy is a practical next step:

```text
Internet 80/443 -> Caddy container -> app:3000 -> db
```

Caddyfile pattern:

```caddyfile
example.com, www.example.com {
    reverse_proxy app:3000
}
```

Ensure the EC2 security group has 443 open before deploying Caddy. Verify:

```bash
curl -I https://example.com
curl -fsS https://example.com/health
```

## Git pull conflict on EC2

If `git pull` aborts because local deployment files changed, first inspect:

```bash
git status --short
git diff -- docker-compose.yaml
```

For reproducible DevOps, avoid uncommitted server-only config drift. If the same change is already in GitHub, discard the server edit and pull:

```bash
git checkout -- docker-compose.yaml
git pull
```

Only stash if the local change is intentionally different and still needed.
