# WooCommerce Store Triage Checklist

Use this before changing a live or unfamiliar WooCommerce store.

## Baseline

- Store URL:
- Environment: local / staging / production
- WooCommerce version:
- Active theme:
- Active store-critical plugins/extensions:
- Multisite involved? yes / no

## Catalog Surface

- Which product types are affected? simple / variable / grouped / bundled / subscription / booking / other
- Are stock, price, tax class, or shipping class involved?
- Are imports/sync jobs involved?

## Order Surface

- Which order statuses are relevant?
- Are payments, refunds, fulfillment, subscriptions, or webhooks involved?
- Is there a recent representative order to inspect?

## Customer Flow to Verify

- Product page
- Add to cart
- Cart totals
- Checkout load
- Payment step
- Order confirmation/admin order view

## Extension Risk Check

List any plugins that could override the affected behavior:
- gateway plugins
- shipping plugins
- tax/VAT plugins
- subscription/booking plugins
- multilingual/currency plugins
- checkout customization plugins
