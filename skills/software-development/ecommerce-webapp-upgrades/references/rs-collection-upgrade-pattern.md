# RS Collection storefront upgrade pattern

Session pattern from upgrading a small Express/PostgreSQL shop into a branded anime/gaming accessories storefront.

## Durable lessons

- Changing `init.sql` updates fresh databases only. Existing Docker Compose PostgreSQL named volumes keep old rows. After changing seed products/branding, verify `/products` from the running app, not just files.
- If the live local DB still has old demo products, ask before replacing rows because it is destructive local data mutation. After approval, apply a small seed refresh against the dev DB and verify with SQL plus `/products`.
- UI brand replacement should include:
  - public title/meta/header/footer
  - admin title/header/placeholders
  - API metadata
  - seed product names/categories/descriptions
  - smoke-test scripts that assert seeded products
  - localStorage keys if cart/admin state names include the old brand
- Buyer-ready contact CTAs can be implemented without payment integration:
  - add-to-order-list/cart
  - product detail modal
  - `Order on WhatsApp` with encoded order summary
  - `Message on Instagram`
  - delivery/policy/contact trust cards
- If no real WhatsApp number is known, use a generic `wa.me/?text=...` placeholder and call out that it should become `https://wa.me/<number>?text=...` later.

## Verification checklist used

- `node --check index.js`
- `node --check public/app.js`
- `docker compose config --quiet`
- `docker compose up -d --build`
- `docker compose ps` shows app/db/nginx healthy
- `curl /health` returns DB connected
- `curl /api` returns new shop metadata
- `curl /products` returns new branded product rows
- Browser smoke test:
  - homepage title/hero/brand visible
  - catalog renders product cards
  - category filter changes result count
  - details modal opens with specs
  - cart/order list updates
  - console has no JS errors
- Existing stack script still passes after updating expected seed product name.
