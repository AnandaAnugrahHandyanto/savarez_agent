# Realm Relics upgrade pattern

Condensed reusable detail from a session upgrading a small Express/PostgreSQL ecommerce shop.

## Situation

The project had a public storefront and admin functions mixed together:

- public homepage exposed admin navigation/actions
- product cards included edit/delete controls
- backend mutation routes were unauthenticated
- the UI looked like a demo inventory dashboard rather than a buyer-facing shop

## Useful manager/subagent split

For similar upgrades, delegate these independent reviews:

1. **Ecommerce UI/UX review**
   - What makes the current shop feel amateur?
   - What sections/features make it feel like a real shop?
   - What should be prioritized for customer trust and purchase intent?

2. **Frontend implementation plan**
   - Which files/components change?
   - How to add product detail, filters, cart/order intent, mobile polish?
   - What can be done without changing deployment scope?

3. **Backend/admin/security review**
   - Where are public write routes?
   - Is admin only hidden visually, or actually protected server-side?
   - What minimal auth is appropriate for a portfolio/local app?

The manager must verify and reject weak subagent output. If a subagent crashes or gives generic advice, continue from direct inspection.

## Accepted upgrade choices

- Customer homepage becomes the main experience.
- Admin moves to `/admin` or an equivalent private flow.
- Public product cards only show buyer actions: details/add-to-cart/order intent.
- Backend mutations require authorization.
- Product data should support realistic ecommerce display: name, slug, description, material, color, style/category, size, price, stock, featured, image.

## Express token-auth pattern

For simple non-production/portfolio ecommerce projects, a temporary server-side token gate can protect admin mutations:

```js
const crypto = require("crypto");

function requireAdmin(req, res, next) {
  const expectedToken = process.env.ADMIN_TOKEN;
  if (!expectedToken) {
    return res.status(500).json({ error: "Admin protection is not configured" });
  }

  const authHeader = req.get("authorization") || "";
  const suppliedToken = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : "";
  const expected = Buffer.from(expectedToken);
  const supplied = Buffer.from(suppliedToken);

  if (expected.length !== supplied.length || !crypto.timingSafeEqual(expected, supplied)) {
    return res.status(401).json({ error: "Unauthorized" });
  }

  return next();
}

app.post("/products", requireAdmin, async (req, res) => { /* create */ });
app.put("/products/:id", requireAdmin, async (req, res) => { /* update */ });
app.delete("/products/:id", requireAdmin, async (req, res) => { /* delete */ });
```

Do not print `ADMIN_TOKEN`. Do not commit `.env`.

## Verification checklist

Minimum proof before claiming success:

- syntax checks pass, e.g. `node --check index.js` and `node --check public/app.js`
- app starts locally
- `GET /products` returns product data
- unauthenticated `POST /products` returns `401`, not `201`
- authorized admin create/update/delete works with the token
- browser storefront loads without console errors
- public homepage has no visible admin link/panel/edit/delete controls
- `/admin` shows an admin gate before dashboard access

## Local Compose verification pitfall

For Express/PostgreSQL apps verified with Docker Compose, the database host inside the app container should usually be the Compose service name (for example `DB_HOST=db`), not `localhost`. `localhost` from inside the app container points back to the app container itself, not the database container. If the app logs "server running" but API calls fail or DB access is broken, check `docker compose config`, app logs, and the DB host value before assuming the UI code is broken.

Do not treat this as deployment work when the user has reserved DevOps for themselves; it is a local verification fix only. Do not redesign Docker/hosting unless explicitly asked.

## Scope caution

If the user says DevOps/hosting is their responsibility, do not change hosting, AWS, CI/CD, domain, Docker architecture, or deployment files. Local Docker/build commands for verification are fine, but separate them clearly from DevOps implementation.