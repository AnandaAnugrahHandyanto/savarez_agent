---
title: "Ecommerce Webapp Upgrades"
sidebar_label: "Ecommerce Webapp Upgrades"
description: "Upgrade small ecommerce web apps into professional, customer-facing storefronts while preserving hostability and separating admin/security concerns"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Ecommerce Webapp Upgrades

Upgrade small ecommerce web apps into professional, customer-facing storefronts while preserving hostability and separating admin/security concerns.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/software-development/ecommerce-webapp-upgrades` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Ecommerce Webapp Upgrades

Use this skill when the user asks to make an online shop/ecommerce project look more professional, realistic, hostable, or buyer-ready.

## Core workflow

1. **Inspect the real project first**
   - Identify framework/runtime, public entrypoints, API routes, database/schema, env files, and local run method.
   - If the project was restored after an OS format/reinstall, first distinguish restored project artifacts from restored runtime tooling: report what files/code are present separately from what could actually be run/verified locally. For S3/backups, use the layered backup→toolchain→deps/tests→Compose→HTTP→GitHub flow in `references/restore-after-os-s3-runtime-verification.md`.
   - For admin/dashboard review requests, inspect both the static UI and the unlocked/admin state if safely possible, then cross-check backend write routes, schema fields, and runtime/Compose health before recommending features.
   - For order/request dashboard upgrades, consult `references/order-dashboard-ui-api-verification.md` before final verification.
   - Do not assume the UI/backend shape from memory.

1a. **For `/goal` or delegation prompts, make them decisive and lane-aware**
   - When the user asks for a reusable goal/prompt for ecommerce portfolio work, do more than list features: encode the operating loop `inspect current repo → choose highest-impact non-DevOps upgrade → implement → verify → report`.
   - If the user owns DevOps learning, put a strict lane split in the prompt: assistant may improve storefront/admin/backend app behavior; user owns Docker/Compose, Caddy/Nginx, env/secrets, DB volume decisions, deployment, CI/CD, backups, domain/server setup, monitoring, and hardening.
   - Prioritize visible portfolio value first: polished storefront screenshots/demo, then admin dashboard quality, then backend/product reliability.
   - Include execution rules that forbid guessing and require real verification commands plus a final report of changed files, verification results, DevOps next steps, and best next app upgrade.

2. **When visual direction is uncertain, sketch before committing**
   - If the user dislikes a UI direction or gives a broad reference like "make it like this site," do not keep repainting the production UI blindly.
   - Create 2-3 disposable HTML mockups with genuinely different stances (e.g. premium boutique, gamer/drop culture, phone-first marketplace), visually verify them, then let the user pick or combine.
   - Preserve the working app until a direction is chosen; production edits should follow the selected variant, not guesswork.
   - For ecommerce, adapt references to buyer behavior instead of cloning a portfolio aesthetic that may not fit a shop.

3. **Act as manager for medium/large upgrades**
   - Delegate focused subagent tasks when useful:
     - ecommerce UI/UX review
     - frontend implementation plan
     - backend/admin/security review
   - Treat subagent outputs as proposals, not truth. Compare, reject weak ideas, and verify before reporting success.

3. **Make the customer storefront primary**
   - Public homepage should look like a real shop: hero, catalog, product cards, clear prices, details, stock/status, calls to action, search/filtering, contact/order intent, trust sections, mobile polish.
   - Remove demo/admin cues from the customer journey.
   - Avoid public edit/delete/create controls.

4. **Separate admin from public storefront**
   - Move admin UI to a separate admin page/route or hidden access flow.
   - Do not merely hide admin controls with CSS or frontend conditionals.
   - Backend mutation routes must be protected too.

5. **Protect backend write paths**
   - Identify every create/update/delete endpoint.
   - Require authentication/authorization for mutations, even if the admin page is not linked publicly.
   - For simple portfolio/local projects, a server-side `ADMIN_TOKEN` with `Authorization: Bearer <token>` can be an acceptable temporary step.
   - Do not print secrets. Do not commit `.env`.

6. **Keep DevOps scope separate when requested**
   - If the user wants to personally handle DevOps/hosting, do not change deployment, AWS, CI/CD, domains, Docker strategy, or hosting unless explicitly asked.
   - Local Docker/runtime use for verification is okay if it does not change deployment architecture.

7. **For subjective UI direction, sketch before committing**
   - If the user says they dislike the UI, says a direction is only partly right, or asks for "something new", do not keep rewriting production CSS blindly.
   - Create 2-3 disposable HTML mockups under `sketches/` with genuinely different design stances, visually verify them, then let the user pick or combine directions.
   - When the user likes a direction "but not that much", refine nearby alternatives rather than jumping to a totally unrelated style.
   - When the user asks for "something new", branch into clearly different concepts, not small color/spacing variations.
   - If the user delegates the choice back to you ("you pick", "do best thing", "if I don't like it I'll change it"), stop asking for preference and choose the strongest direction using product evidence: real photos, buyer flow, brand trust, and audience fit. Apply reversible UI/file changes directly, but pause before destructive data changes such as deleting/reseeding running DB rows. See `references/design-direction-delegation-and-db-boundary.md`.

8. **Verify before reporting completion**
   - Run syntax checks for app code.
   - Add focused app-level tests for behavior changes where feasible. For small Express apps without an existing test harness, a pragmatic pattern is to guard startup with `if (require.main === module) { ...app.listen... }`, export pure helpers such as payload validators/query builders, and test them with Node's built-in `node:test` before touching DB/runtime state.
   - Start the app locally if possible.
   - Test public storefront loads products.
   - Test no admin link/panel/edit/delete appears on the public homepage.
   - Test cart/detail/filter/order-intent interactions if added.
   - If seed products/branding changed, verify the live `/products` response; do not assume `init.sql` changed an existing Docker/PostgreSQL volume.
   - If new routes were added, verify the running app actually loaded them via `/api` or direct HTTP probes; tests can pass while an old Docker/Node process still serves stale code.
   - If public launch/discovery is part of the task, verify through the user-facing entrypoint/reverse proxy, add lightweight crawl/share metadata, and clean up smoke-test artifacts. See `references/public-discovery-and-smoke-cleanup.md`.
   - If an existing local/dev DB still contains old demo rows, ask before replacing or deleting rows, then verify via SQL and the HTTP endpoint after approval.
   - Test unauthenticated mutation routes fail.
   - Test authorized admin CRUD works if admin auth was implemented.
   - Use browser smoke tests and console checks for UI work.
   - When smoke tests create real orders or reduce stock, neutralize the artifacts before final reporting: cancel/mark test orders via the app workflow, restore stock, and archive fake test products from public visibility instead of leaving them exposed.
   - When browser-smoke-testing a Compose app with a one-off `docker run`, do not blindly pass the project's `.env` with `--env-file`: quoted values may be preserved literally by Docker even when the app's dotenv loader strips them. Prefer Compose exec where possible, or pass sanitized `-e DB_HOST=db -e DB_PORT=5432 ...` values and verify `/health` before using the browser.

## Implementation patterns

### Product storefront features

Prefer pragmatic buyer-facing improvements:

- polished hero section
- category rail or filters
- product grid/card redesign
- product detail modal/page
- stock and price visibility
- local cart or order-summary flow before payment integration exists
- direct contact CTAs such as WhatsApp/Instagram order links with encoded product/order summaries
- contact/order intent section
- delivery, return/refund policy, and social/contact trust sections
- footer/trust sections
- responsive mobile layout

For product/shop visual work, prioritize real product imagery over placeholder/stock imagery whenever the user has provided an image folder. Copy images into a stable public asset path, update all demos/mockups/product cards to use those local assets, and align product names/categories/copy with what the images actually show. Verify with a repository search that external stock-image URLs are gone and browser-check representative pages.

### Admin separation

Common route structure for simple Express apps:

- `/` -> public storefront
- `/admin` -> admin UI
- public APIs: `GET /products`, `GET /featured-products`
- protected APIs: `POST /products`, `PUT /products/:id`, `DELETE /products/:id`

### Admin dashboard upgrade review

When the user asks what to add to an existing ecommerce admin dashboard, ground the advice in the real dashboard instead of giving generic CRUD ideas:

- Open/inspect the protected gate and the unlocked dashboard state if safe; screenshots/browser inspection catch hierarchy, empty-state, and form UX issues that code review alone misses.
- Compare visible admin features against backend/schema reality: auth/session model, protected mutations, product fields, inventory stats, image handling, product visibility/status, and order/request storage.
- Before promising runtime behavior, verify the local stack parses/starts; if Compose or runtime config blocks DB-backed testing, call that out separately from product recommendations.
- Prioritize additions that turn CRUD into a client-ready admin tool: real login/session/logout, image upload + preview, product status/draft/archive, inventory search/filter/sort/quick stock edits, low-stock/restock watch panels, order/inquiry dashboard, audit logs, safer archive/delete flow, and dashboard KPI cards.
- If implementing immediately, choose the smallest operational workflow that makes the admin feel real and can be verified live. Good first upgrades are:
  - inventory/status workflow: add `active/draft/sold_out/archived`, filter public APIs to active products, require admin auth for all-status views, and add admin search/filter/sort/quick-stock controls. See `references/admin-inventory-status-workflow.md`.
  - low-stock/restock watch: derive active products with `stock <= 3`, sort by stock ascending, show actionable rows, connect rows to inventory filtering/editing, and verify rendering without leaving smoke-test stock mutations behind. See `references/admin-restock-watch-dashboard.md`.
- Keep recommendations ordered by implementation value so the user can build incrementally, especially when they own DevOps learning work.

### Pitfalls

- A separate admin page is not security by itself. Protect backend writes.
- A good-looking shop still feels fake if products lack price, stock, details, and buying/contact intent.
- A reference site can be aesthetically attractive but wrong for ecommerce. Portfolio-style minimalism may make a shop feel sterile; validate against the shop's buyer flow and brand category before applying it broadly.
- If the user says they dislike the UI after a redesign, treat it as a direction-selection failure, not a minor CSS bug. Stop production repainting and offer verified mockup directions.
- Docker/PostgreSQL seed files are not replayed against an existing named volume. When product branding changes, verify the running DB and refresh local rows only with user approval.
- Brand changes often leave residue in admin pages, API metadata, smoke-test scripts, localStorage keys, README text, and seed data. Search the repo for the old brand/category language before final verification.
- If no real WhatsApp number is available, use a generic `wa.me/?text=...` placeholder and explicitly tell the user it should be replaced with `https://wa.me/<number>?text=...` later.
- Do not let subagents perform external side effects without verifiable handles and manager verification.
- Avoid trademarked product names when building fantasy/anime/game-inspired shops.

## References

- `references/realm-relics-upgrade-pattern.md` — condensed pattern from a session upgrading a plain Express/PostgreSQL fantasy accessories shop into a more professional storefront with separated admin.
- `references/rs-collection-upgrade-pattern.md` — brand refresh pattern for an anime/gaming accessories storefront, including local DB seed refresh verification and WhatsApp/Instagram CTAs.
- `references/ui-direction-recovery-pattern.md` — recovery workflow for rejected ecommerce UI directions: pause production edits, create verified mockup variants, then apply the selected stance.
- `references/rs-collection-dark-premium-direction.md` — finalization pattern when the user delegates uncertain design choice: pick based on product-photo fit, implement a dark premium drop-shop, refresh dev DB with approval, rebuild image-served assets, and verify mobile clipping/interactions.
- `references/admin-inventory-status-workflow.md` — admin dashboard upgrade pattern for product lifecycle statuses, public/admin product visibility split, inventory search/filter/sort, quick stock edits, and DevOps-lane boundaries.
- `references/admin-order-request-dashboard.md` — order/customer request dashboard pattern: public order form, persisted order/items, admin follow-up queue, statuses, priority, internal notes, and live-runtime verification.
- `references/admin-restock-watch-dashboard.md` — low-stock/restock watch admin pattern: thresholding active products, actionable rows, KPI alignment, and safe verification without leaving stock/test artifacts.
- `references/public-discovery-and-smoke-cleanup.md` — launch-readiness pattern for public discoverability metadata, robots.txt, real-domain SEO follow-up, reverse-proxy verification, and cleanup of smoke-test orders/products/stock.
- `references/restore-after-os-s3-runtime-verification.md` — restore-after-format verification pattern: compare S3/backups, distinguish source artifacts from workstation tooling, run deps/tests/audit, build Compose, smoke-test proxy endpoints, and check GitHub continuity separately.
