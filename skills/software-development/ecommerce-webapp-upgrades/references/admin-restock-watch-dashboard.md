# Admin restock watch dashboard pattern

Use this reference when upgrading an ecommerce admin dashboard from basic CRUD into a shop-owner operations tool.

## Trigger

A simple store already has products, stock counts, protected admin mutations, and possibly orders/customer requests. The next visible admin upgrade should help the owner notice operational problems quickly.

## Pattern

Add a low-stock/restock watch panel before heavier features like uploads or analytics:

- Define a small threshold, usually `stock <= 3` for boutique/demo stores.
- Only include active/publicly sellable products unless the admin explicitly asks to monitor archived/draft items too.
- Sort low-stock items by stock ascending so critical items appear first.
- Show practical context in each row: thumbnail, product name, style/category, price, and stock count.
- Make rows actionable: clicking a low-stock row should filter/search the inventory table to that product, or open the edit drawer.
- Add an empty state that reassures the owner when no products need restock.
- Pair the panel with a dashboard KPI card (`Low stock alerts`) so the summary and detailed list agree.

## Verification checklist

- Rebuild/restart the running app when frontend assets are served from a container or reverse proxy.
- Verify the served admin HTML includes the new panel markers and retains `noindex,nofollow`.
- Run existing unit tests.
- Browser-check the admin page and console for JavaScript errors.
- If the live DB has no low-stock products, inject safe temporary frontend data or use a reversible test fixture to verify rendering without leaving fake products public.
- Do not reduce real stock permanently just to demonstrate the panel; restore stock or avoid DB mutation.

## Why this is high-value

For a portfolio ecommerce project, this makes the admin dashboard feel like a real owner workflow rather than a form collection. It is small, visible, easy to verify, and does not cross into the user's DevOps lane.