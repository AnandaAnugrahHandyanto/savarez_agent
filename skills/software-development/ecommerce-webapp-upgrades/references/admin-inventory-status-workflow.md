# Admin inventory/status workflow pattern

Use this pattern when a small ecommerce project already has basic product CRUD but the admin dashboard still feels like a demo.

## Trigger

- User asks to review/admin dashboard and improve what should be added.
- Project has products with stock/featured/images but no real product lifecycle workflow.
- User owns DevOps/deployment work and wants app/business improvements handled separately.

## High-value upgrade

Turn CRUD into inventory control by adding a product lifecycle field and admin-side table tools:

- `status`: `active`, `draft`, `sold_out`, `archived`
- Public product endpoints show only `active` products by default.
- Admin product list can include all statuses, but only through a protected admin path/token/session.
- Admin form includes status selection.
- Inventory table gets:
  - search
  - status filter
  - useful sort options such as newest, lowest stock, highest price, name A-Z
  - status badges
  - quick stock `+1`/`-1` controls
  - active vs hidden/draft dashboard counts

## Backend shape

For simple Express/PostgreSQL apps:

- Add `status TEXT NOT NULL DEFAULT 'active'` to product schema.
- On startup/migration, add the column idempotently for existing local DBs:
  - `ALTER TABLE products ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active'`
- Public list query should filter `WHERE status = 'active'` unless an authorized admin requests all products.
- Featured products should also require active status.
- Product create/update accepts validated status values only.
- Optional quick stock endpoint:
  - `PATCH /products/:id/stock`
  - protected by admin auth
  - validates non-negative integer stock
  - if stock reaches `0` while active, auto-mark `sold_out`

## Verification checklist

- Syntax-check server and frontend JavaScript.
- Verify protected all-products/admin paths reject unauthenticated requests.
- Verify public `/products` excludes draft/sold_out/archived products.
- Verify admin UI renders search/filter/sort/status controls without console errors.
- If Docker/Compose is the user's learning lane, keep Compose/startup changes out of scope unless needed only for read-only verification and explicitly explain that split.

## Pitfalls

- Do not treat frontend hiding as product visibility control; public APIs must filter hidden statuses.
- Do not let `includeAll=true` leak archived/draft products without admin authorization.
- Do not change Docker, CI, Caddy, domain, or deployment files when the user explicitly reserved DevOps work for themselves.
- If pulling from GitHub overwrites/conflicts with local work, preserve local state on a backup branch before resetting/merging, then report exactly what changed and what lane it belongs to.
