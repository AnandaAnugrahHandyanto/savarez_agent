# Admin order/request dashboard pattern

Use this pattern when an ecommerce portfolio shop has a polished storefront and product CRUD/inventory management, but the shop owner still cannot track customer order intent inside the app.

## Trigger

- Public storefront has cart/order-list or WhatsApp ordering, but no persisted customer requests.
- Admin dashboard has product management but no customer follow-up queue.
- User wants app/admin/business features while keeping Docker/Compose/Caddy/CI/deploy work as their DevOps lane.

## High-value upgrade

Turn the shop from a catalog into a small business workflow:

### Public storefront

- Keep WhatsApp quick-order as an optional path.
- Add an order request form in the cart/order drawer:
  - customer name
  - phone / WhatsApp
  - city / location
  - notes
  - cart items and quantities
- Show validation errors and success confirmation clearly.

### Backend

For simple Express/PostgreSQL apps, add app-level order storage:

- `orders` table:
  - `id`
  - `customer_name`
  - `phone`
  - `city`
  - `notes`
  - `admin_note` optional
  - `priority` such as `normal` / `priority`
  - `total_price`
  - `status`
  - `created_at`
- `order_items` table:
  - `order_id`
  - `product_id` nullable / set-null if product is removed
  - product name snapshot
  - unit price snapshot
  - quantity
  - line total
- `POST /orders` public endpoint:
  - validate customer fields and items
  - verify products exist and are orderable
  - reject non-positive quantities
  - reject quantities above stock
  - snapshot product name/price at order time
- Protected admin endpoints:
  - `GET /orders`
  - `PATCH /orders/:id/status`
  - optionally `PATCH /orders/:id` for `status`, `priority`, `admin_note`

Recommended statuses:

- `new`
- `contacted`
- `confirmed`
- `cancelled`
- `fulfilled`

### Admin dashboard

Add an Orders / Requests section with:

- request count
- customer name, phone, city/location, notes
- ordered products and total price
- status chip
- priority chip
- created time
- WhatsApp/contact action
- status update controls
- admin internal note field
- filters:
  - status
  - priority
  - search by customer/phone/city/order id
- sorting:
  - newest
  - oldest
  - highest value
  - priority first
- stats:
  - new orders
  - pending follow-up (`new` + `contacted`)
  - confirmed
  - priority
  - fulfilled

## Verification checklist

1. Code checks:
   - `npm test`
   - `node --check index.js`
   - `node --check public/app.js`
   - `npm audit --omit=dev --audit-level=high` if dependencies changed or the user wants a quality check.
2. Live runtime checks after rebuild/restart:
   - `GET /api` lists the order endpoints.
   - unauthenticated `GET /orders` returns `401`, not HTML fallback.
   - invalid public `POST /orders` returns `400` JSON.
   - valid public `POST /orders` creates an order.
   - authorized `GET /orders` returns the new order with item snapshots.
   - authorized status/admin-note/priority update works.
3. Browser checks:
   - customer adds product to cart and submits request.
   - admin dashboard shows request.
   - admin can move `new -> contacted -> confirmed -> fulfilled`.
   - filters/stats update.
   - browser console has no JS errors.

## Runtime reload pitfall

Passing tests and syntax checks only proves the working tree. In Docker/long-running Node setups, the browser and API may still be served by an older container/process. Always compare the running API against the new code before claiming the feature is live.

Good probes:

- `curl http://localhost:<port>/api` should list newly added routes.
- A new protected API such as `/orders` should return `401` when unauthenticated; if it returns the storefront HTML, the running server does not have that route loaded.
- If the live app is stale, tell the user the feature is built but not live-loaded yet, and hand the rebuild/restart step back to the user's DevOps lane when they own Docker/Compose/runtime work.

## Pitfalls

- Do not replace WhatsApp ordering entirely; keep it as a fast fallback unless the user asks otherwise.
- Do not decrement stock automatically unless the user explicitly wants reservation/payment semantics. For request-style orders, stock should usually remain unchanged until the owner confirms.
- Do not expose `GET /orders` publicly.
- Do not let the catch-all storefront route make failed API verification look successful; inspect status codes and response type.
- Avoid modifying Docker, Caddy, CI/CD, domains, deployment, or backups when the user reserved DevOps work for themselves.
