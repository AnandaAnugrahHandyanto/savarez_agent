# RS Collection dark premium ecommerce direction

Condensed lesson from an RS Collection online shop redesign where the user was unsure which visual direction to use.

## When the user cannot pick a design

If the user says they do not know which design to use and asks the assistant to do the best thing:

1. Stop offering more equal options.
2. Pick one direction based on product fit and buyer behavior.
3. State the rationale briefly.
4. Implement it fully.
5. Verify desktop, mobile, and core ecommerce interactions.
6. Leave room for later changes, but do not stall.

For dark/silver accessory products, a **dark premium drop-shop** direction can outperform a clean portfolio style because it matches the photography and social-commerce audience.

## Practical implementation pattern

- Use real local product images as the main visual driver, not placeholder/stock imagery.
- Make the hero a product-gallery composition: one large featured product plus smaller supporting product images.
- Use dark background, cream text, muted copy, and gold accent CTAs/prices.
- Keep WhatsApp/Instagram ordering obvious.
- Keep the catalog practical: price, stock, category, detail button, add/order button.
- Avoid overfitting to a portfolio reference when the artifact is a shop.

## DB seed + running dev DB pattern

Changing `init.sql` does not update an existing PostgreSQL Docker volume. For a running local dev stack:

1. Update `init.sql` for fresh environments.
2. Ask before replacing/deleting current local dev rows.
3. Replace dev rows only after approval.
4. Verify through SQL and the HTTP `/products` endpoint.
5. Update smoke-check scripts to assert the new expected product names.

This row replacement is app/content/data work, while the durable DevOps lesson is understanding volume persistence, backups, and migration/reset safety.

## Verification checklist

- `node --check` for JS files.
- `docker compose config --quiet`.
- Rebuild the app image if static files are copied into the image; restart alone may serve stale HTML/CSS/assets.
- Run the local stack smoke script.
- Verify `/products` returns the new rows and local asset paths.
- Search for old stock-image URLs and old product/brand names.
- Browser-check desktop for image loading and visual polish.
- Browser-check mobile with a real small viewport screenshot; large headings often clip on mobile even if desktop looks good.
- Test category filter, product detail modal, add-to-order/cart, and console errors.

## Pitfalls

- Too many design options can become a stall. If the user explicitly delegates judgment, pick and execute.
- Hero typography that looks strong on desktop may clip on mobile; verify with a mobile screenshot and reduce headline length/font-size if needed.
- `docker compose restart` is not enough when the app image contains copied static assets. Rebuild/recreate the app service.
- Keep the GitHub push separate; redesign and local verification do not imply publishing.
