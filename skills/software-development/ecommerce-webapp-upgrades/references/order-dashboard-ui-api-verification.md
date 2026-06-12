# Order/request dashboard upgrade lessons

Use this reference when upgrading a small ecommerce app from product CRUD into a shop-owner management panel.

## Durable implementation pattern

- Treat customer requests as first-class app data, not just WhatsApp text.
- Add public order submission plus protected admin management:
  - `POST /orders` for storefront/customer order requests.
  - `GET /orders` for admin order queue.
  - `PATCH /orders/:id/status` for simple owner workflow updates.
  - Prefer a consolidated `PATCH /orders/:id` when the dashboard grows beyond status, so status, priority, and private owner notes save together.
- For a more realistic owner queue, add validated admin-only fields:
  - `priority` (`normal` / `priority`) for urgent follow-up.
  - `admin_note` for private shop-owner notes, with a sane length cap.
- Snapshot order items at request time:
  - product name
  - unit price
  - quantity
  - line total
  - total price
- Validate at the backend boundary:
  - customer name present
  - phone/WhatsApp contact shape
  - city/location present
  - cart has at least one item
  - product IDs and quantities are positive integers
  - product is active/publicly available
  - requested quantity does not exceed current stock
- Use a simple owner workflow before adding payment complexity:
  - new
  - contacted
  - confirmed
  - cancelled
  - fulfilled

## Admin dashboard UX pattern

A real owner panel needs a follow-up queue, not only product CRUD:

- Order/request section near the top of admin workspace.
- Stats cards for:
  - new orders
  - pending follow-up (`new` + `contacted`)
  - confirmed
  - fulfilled
- Add queue controls once orders become more than a handful:
  - search by order id, customer name, phone, city, public notes, and private admin note
  - status filter
  - priority filter
  - sort by newest, oldest, highest value, and priority-first
- Each request card should show:
  - customer name
  - phone/WhatsApp
  - city/location
  - created time
  - item snapshots
  - total
  - customer notes
  - current status
  - priority badge/control
  - private owner-note textarea
  - save owner-update button
  - quick WhatsApp/customer contact action with a prefilled item summary
- Keep dangerous inventory actions non-destructive: archive/restore beats hard delete.

## Verification pitfalls found in session

- `node --check` plus tests can pass while browser init still fails. Browser-smoke the actual page after app.js edits and verify no initialization `ReferenceError` before claiming UI success.
- After adding a new event listener, explicitly verify the referenced handler exists in the final file. A missing handler like `submitOrderRequest` can block all later storefront initialization, leaving product grids stuck at “Loading products...”.
- Browser smoke should check semantic UI state, not just page load:
  - product cards rendered
  - catalog summary updated
  - cart drawer opens
  - order request form exists
  - submitting invalid form shows clear validation
  - admin page loads after token and renders orders panel
- API smoke tests that create temporary data must clean it up using the same DB connection settings as the app. With `pg`, do not rely on default localhost settings inside ad-hoc scripts; pass `host`, `port`, `database`, `user`, and `password` from app env explicitly.
- Browser order-submission checks that decrement stock must restore the touched product/order rows afterward so verification does not leave demo data polluted or products unexpectedly sold out.
- When smoke-testing admin auth in an isolated container, pass a known `ADMIN_TOKEN` explicitly and use that same value in browser/sessionStorage/localStorage. A placeholder token mismatch can make the dashboard look broken even though the API and UI are fine.
- If using an isolated container to protect the user's DevOps lane, treat it as a runtime probe only: do not edit Compose/Docker/env files, pass sanitized app env explicitly, verify `/health`, then remove the container after checks.
- When several local app containers/ports exist, first map which one the browser/API target is actually hitting. It is common for `docker compose app` to be healthy but not host-published, while an older smoke container still owns `127.0.0.1:3000` and serves stale code. Verify each candidate with `/api` and `/orders` before claiming the rebuilt app is live; if needed, rebuild the image, restart the Compose service, then recreate the host-published smoke container from the fresh image with sanitized env.
- For browser smoke tests where accessibility clicks do not visibly change state, inspect and drive the DOM deliberately via browser console: list buttons/cards, check localStorage/cart state, click the intended `.add-cart-button`, and verify semantic UI text (`Order 1`, cart rows, success message) instead of repeating the same snapshot/click loop.
- If using masked/redacted phone values in examples, make sure the validator accepts them or use a real-shaped fake number. Test fixtures should match production validation rules.

## Good final gate for this class of upgrade

Before final report or commit:

1. `node --check index.js && node --check public/app.js`
2. `npm test`
3. Health check returns database connected.
4. API smoke:
   - create temporary active product
   - submit order request
   - confirm admin list includes item snapshot
   - patch order status
   - invalid order returns 400 with clear error
   - delete temporary order/product rows
5. Browser smoke:
   - storefront renders products automatically
   - no console `ReferenceError` or failed API initialization appears after page load
   - cart/order-request form works or shows validation
   - successful browser order displays the returned request/order id
   - the submitted order is visible through the backend/admin data path
   - any stock/order fixture changes from the smoke test are restored
   - admin orders panel renders with no console errors
   - if priority/admin-note controls were added, save one owner update through the browser and verify the updated row appears in the admin data/API
   - if the browser/API smoke creates temporary products or orders, clean them up before final report; if a hard tool/runtime limit prevents cleanup, name the exact temporary IDs/slugs so the user can remove them
6. `git diff --name-only` confirms no DevOps/infrastructure files changed unless explicitly requested.
