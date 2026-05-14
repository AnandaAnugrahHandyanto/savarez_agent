# LP Optimizer -- Cart & Checkout Optimization (LP-E05)

Used by: `/lp-optimizer cart`

**Vertical:** Ecommerce only. If vertical is not ecommerce, inform user and suggest a different action.

## Investigation Steps

### 1. Get Cart/Checkout URLs

- ASK user for cart page URL and checkout page URL
- If audit report has D39 findings, extract URLs from there
- Navigate to each page via Chrome DevTools

### 2. Audit Cart Page

Navigate to cart page and check each element:

| Element | What to check | How to evaluate |
|---------|--------------|----------------|
| **Order summary** | Product thumbnail, name, variant, quantity, unit price, line total visible? | Screenshot + DOM check |
| **Total breakdown** | Subtotal, shipping estimate, tax, discounts, total shown? | DOM check -- flag "calculated at checkout" |
| **Quantity editing** | +/- buttons with live total update (no page reload)? | Evaluate JS behavior |
| **Remove with undo** | Remove shows "Undo" option for 5 seconds? | Test interaction |
| **Free shipping bar** | Progress bar showing distance to free shipping threshold? | DOM check |
| **Cart cross-sell** | 2-3 complementary products with one-click add? | DOM check |
| **Coupon field** | Subdued (collapsible "Have a promo code?" link) vs prominent? | DOM check -- flag if prominent |
| **Checkout CTA** | "Proceed to secure checkout" (not "Continue")? | Extract button text |
| **CTA placement** | Checkout button at top AND bottom of cart? | DOM check |
| **Express pay** | Apple Pay, Google Pay, PayPal, Shop Pay visible? | DOM check |
| **Trust badges** | Payment method logos + security badge near CTA? | DOM check |
| **Return policy** | One-line reminder near CTA? | DOM check |

### 3. Audit Checkout Page

Navigate to checkout page and check:

| Element | What to check | How to evaluate |
|---------|--------------|----------------|
| **Guest checkout** | Form loads immediately without requiring login? | Check for login wall |
| **Email first** | Email is the first field? | DOM field order |
| **Express checkout** | Apple Pay/Google Pay/Shop Pay above the form? | DOM check |
| **Returning customer** | "Already have an account?" link available but not blocking? | DOM check |
| **Field count** | Count required vs optional fields | DOM check -- list all fields |
| **Unnecessary fields** | Company name, phone (if not needed), separate first/last? | Assess each field |
| **Single-column layout** | All fields in one column? | Layout check |
| **Smart defaults** | Auto-detect country, auto-fill city from postal code? | Test behavior |
| **Billing = shipping** | "Same as shipping" checked by default? | DOM check |
| **Inline validation** | Green checkmark on valid, red on invalid? | Test interaction |
| **Mobile keyboards** | Numeric for postal/phone/CC, email keyboard for email? | Check inputmode attributes |
| **Persistent summary** | Order summary visible alongside form? | Layout check |
| **Item thumbnails** | Product images in checkout summary? | DOM check |
| **Total matches cart** | Checkout total = cart total (no surprises)? | Compare values |
| **Payment methods** | Credit/debit + PayPal + 1 additional? | DOM check |
| **BNPL option** | Klarna/Afterpay for products > $50/EUR 50? | DOM check |
| **No navigation** | Header nav removed, only "Back to cart"? | DOM check |
| **Security badge** | Lock icon + "payment encrypted" near payment fields? | DOM check |
| **Guarantee reminder** | Money-back guarantee near place order button? | DOM check |
| **Contact access** | Chat or phone visible from checkout? | DOM check |
| **Place order button** | "Place order" or "Pay ${amount}" (not "Submit")? | Extract button text |

### 4. Identify Abandonment Drivers

Based on findings, classify issues by abandonment impact:

| Impact Level | Issues | Typical Revenue Loss |
|-------------|--------|---------------------|
| Critical | Forced registration, surprise shipping at checkout, no guest checkout | 25-35% cart abandonment |
| High | Prominent coupon field, no free shipping indicator, no inline validation | 10-20% cart abandonment |
| Medium | Missing trust badges, no cross-sell, weak CTA copy | 5-10% cart abandonment |
| Low | No micro-animations, no "save for later", no order bump | 1-5% cart abandonment |

## Fix Patterns

### Cart Page Quick Wins (P1)

| Issue | Fix | Expected Impact |
|-------|-----|-----------------|
| Prominent coupon field | Collapse to "Have a promo code?" text link | Reduces "coupon hunting" abandonment |
| Generic CTA | Change to "Proceed to Secure Checkout" | Clearer intent + trust signal |
| No shipping estimate | Show estimate or range on cart page | Prevents checkout surprise |
| Missing trust badges | Add payment logos + SSL badge near CTA | Increases checkout confidence |
| No return policy | Add one-line return policy near CTA | Reduces purchase anxiety |

### Checkout Page Quick Wins (P1)

| Issue | Fix | Expected Impact |
|-------|-----|-----------------|
| Forced account creation | Make guest checkout the default | +10-15% checkout completion |
| Email not first field | Move email to first position | Enables abandoned cart recovery |
| No inline validation | Add real-time field validation | Fewer submission errors |
| Generic "Submit" button | Change to "Place Order" or "Pay $X.XX" | Clearer action expectation |
| Full site navigation | Remove nav, keep only "Back to cart" | Reduces exit leaks |

### Strategic Fixes (P2)

| Issue | Fix | Expected Impact |
|-------|-----|-----------------|
| No express pay | Add Apple Pay/Google Pay/Shop Pay | +5-10% mobile conversion |
| No BNPL | Add Klarna/Afterpay for items > $50 | +10-15% AOV on eligible items |
| Too many fields | Remove non-essential, use smart defaults | +5-10% completion |
| No free shipping bar | Add progress bar with threshold | +5-10% AOV |
| No cross-sell | Add 2-3 complementary products | +5-10% AOV |

## Report Output Structure

```markdown
## Cart & Checkout Optimization Guide

### Cart Page Audit
| Element | Status | Current State | Recommendation |
|---------|--------|--------------|---------------|

### Checkout Page Audit
| Element | Status | Current State | Recommendation |
|---------|--------|--------------|---------------|

### Priority Fixes
{P1/P2 fixes with specific implementation steps}

### Abandonment Reduction Estimate
{Estimated impact of fixes on cart/checkout abandonment rates}

### Implementation Checklist
- [ ] Fix 1: {description} -- Owner: {role}
- [ ] Fix 2: {description} -- Owner: {role}

### Testing Recommendations
{What to A/B test after implementing fixes}
```
