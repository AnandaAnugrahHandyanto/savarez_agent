# Design direction delegation + local DB boundary

Use this when an ecommerce user is unsure which UI direction to choose and says something like “you pick,” “do best thing,” or “if I don’t like it I’ll change it.”

## Pattern

1. **Stop asking for more aesthetic preference.** Treat the user’s message as delegation of the design call.
2. **Choose based on product evidence, not personal taste.** For shops, prioritize the direction that best matches:
   - actual product photos,
   - audience/buyer behavior,
   - ordering flow clarity,
   - brand trust.
3. **Prefer production-safe UI edits first.** Copy, CSS, hero layout, product card styling, and static image references are reversible file changes and can be applied directly when scope is clear.
4. **Do not perform destructive data replacement silently.** If the selected design requires replacing existing local/dev database rows, pause and ask for explicit approval before `DELETE`, truncate, reseed, or volume reset.
5. **After approval, verify both layers:**
   - source seed file contains the new product data,
   - running database/API returns the same products,
   - browser renders the expected images/products,
   - mobile/responsive view is usable.

## RS Collection example

For an accessory shop with dark/silver real product photos, the best direction was a **dark premium accessory drop shop** rather than a clean portfolio style. The rationale:

- dark background improves silver jewelry/product contrast,
- real product photos reduce the “fake demo shop” feeling,
- WhatsApp/Instagram ordering remains obvious,
- the vibe fits Instagram/TikTok small-shop customers better than sterile portfolio minimalism.

Production-safe changes applied first:

- dark premium CSS,
- hero gallery using local `/assets/products/*` images,
- copy focused on necklaces/pendants/charms,
- category labels aligned with actual inventory,
- fallback image changed from external stock URL to local asset.

Boundary held:

- replacing running PostgreSQL dev rows was paused for user approval because it deletes existing rows, even if local/dev only.
