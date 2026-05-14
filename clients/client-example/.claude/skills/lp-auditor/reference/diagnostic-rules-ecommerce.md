# LP Auditor — Ecommerce Diagnostics (LP-D38–D40)

Data source: Chrome DevTools page content (DOM extraction + screenshot)

Reference: `sops/Ecommerce Page Quality Checklist.md`, `sops/Ecommerce Conversion Engine Mental Model.md`

**Prerequisite:** Only runs when vertical = ecommerce (from business.md). For lead gen/SaaS audits, this entire module is SKIP.

---

## LP-D38: Product Page Elements
**Severity:** High (10 pts) | **Data:** Chrome DevTools DOM extraction + screenshot

**Rule:** Product pages must have all critical conversion elements present and properly placed to support purchase decisions.

**How to check:**
1. Navigate to product page URL via Chrome DevTools
2. Check for required elements (per Ecommerce Page Quality Checklist):

**Above the fold (product identity):**
- Product images: multiple angles? (minimum 4-5)
- Gallery supports zoom?
- Gallery includes video or 360-degree view?
- Product title descriptive with key attributes?
- Star rating + review count visible near title?

**Offer stack:**
- Price prominent and near add-to-cart?
- If discounted: original price (strikethrough) + new price + savings shown?
- Shipping info visible near CTA?
- Return/guarantee policy summarized near CTA?
- Stock availability shown?

**Add-to-cart action:**
- Add-to-cart button visually prominent?
- Variant selectors functional?
- Size chart accessible (for sized products)?
- Express pay options visible (Apple Pay, Google Pay)?
- Clear feedback after adding to cart?
- Sticky CTA on mobile?

**Social proof:**
- Customer reviews with star ratings?
- Review sorting/filtering available?
- Customer photos from verified buyers?
- Sufficient review count (≥5)?

**Product details:**
- Description leads with benefits?
- Specs in scannable table format?
- FAQ section present?

3. Score by element count: tally present vs missing from the checklist above

**Pass/Fail:**
- PASS: 80%+ of required elements present and properly placed
- WARN: 60-79% of elements present, or key elements present but poorly placed
- FAIL: <60% of elements present, OR critical elements missing (no price visible, no add-to-cart, no images)

**Routing on FAIL:** `/lp-optimizer elements` or `/ecom-page-builder` for rebuild

---

## LP-D39: Cart & Checkout Flow
**Severity:** High (10 pts) | **Data:** Chrome DevTools navigation (requires user-provided URLs)

**Rule:** Cart and checkout must minimize friction. Every friction point costs conversions.

**How to check:**
1. **ASK user:** "What is the cart page URL? (Leave blank to skip)"
   - If blank: SKIP this diagnostic
   - If provided: proceed

**Cart page checks:**
- Each item shows: thumbnail, name, variant, quantity, price?
- Order total breakdown visible (subtotal, shipping, tax, discounts)?
- No hidden charges?
- Quantity can be changed with live total update?
- Items can be removed with undo?
- Free shipping progress bar (if threshold exists)?
- Coupon field present but subdued?
- Cross-sell section with complementary products?
- "Proceed to checkout" button prominent?
- Express pay buttons visible?
- Trust badges near checkout CTA?

2. **ASK user:** "What is the checkout page URL? (Leave blank to skip checkout checks)"
   - If blank: evaluate cart only

**Checkout page checks (if URL provided):**
- Guest checkout available as default?
- Email is first field (for abandoned checkout recovery)?
- Express checkout options prominent above form?
- Single-column form layout?
- Minimal field count?
- "Billing same as shipping" checkbox default-checked?
- Inline validation active?
- Order summary visible alongside form?
- Multiple payment methods offered?
- Buy-now-pay-later for orders >€50?
- No navigation links (only "back to cart")?
- SSL badge near payment fields?
- Clear "Place order" button text?

3. Score by checklist completion

**Pass/Fail:**
- PASS: 80%+ of applicable cart/checkout items pass
- WARN: 60-79% pass, or cart is good but checkout has issues
- FAIL: <60% pass, OR critical issues (no guest checkout, hidden fees, broken form)
- SKIP: User did not provide cart/checkout URLs

**Routing on FAIL:** `/lp-optimizer cart`

---

## LP-D40: Category Page Quality
**Severity:** Medium (5 pts) | **Data:** Chrome DevTools DOM extraction + screenshot

**Rule:** Category pages must support efficient product discovery with filtering, sorting, and clear product cards.

**How to check:**
1. **ASK user:** "What is a category page URL? (Leave blank to skip)"
   - If blank: SKIP this diagnostic
   - If provided: proceed

2. Navigate to category page and check:

**Header and orientation:**
- Category name (H1) descriptive and matches search intent?
- Breadcrumbs show hierarchy?
- Product count visible?

**Filtering and sorting:**
- Sort options available (bestsellers, price, newest, top rated)?
- Filters visible by default on desktop?
- Applied filters shown as removable chips?
- Filters update dynamically (no full page reload)?

**Product cards:**
- Each card shows: image, title, price (current + original if discounted), rating, review count?
- Images consistent in size and style?
- Variant availability visible (color swatches, "5 colors")?
- Social proof badges ("Bestseller", "New", "Trending")?
- Low-stock indicators where genuine?

3. Score by checklist completion

**Pass/Fail:**
- PASS: 80%+ of applicable items pass, filtering/sorting functional
- WARN: 60-79% pass, or filtering exists but is limited
- FAIL: <60% pass, OR no filtering/sorting, OR product cards missing critical info (no price, no image)
- SKIP: User did not provide category page URL

**Routing on FAIL:** `/lp-optimizer elements` or `/ecom-page-builder` for rebuild
