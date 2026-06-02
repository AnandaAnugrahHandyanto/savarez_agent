---
title: "Woocommerce Store Ops"
sidebar_label: "Woocommerce Store Ops"
description: "Use when operating or validating a WooCommerce store for catalog changes, order inspection, merchandising sanity checks, and extension-aware verification"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Woocommerce Store Ops

Use when operating or validating a WooCommerce store for catalog changes, order inspection, merchandising sanity checks, and extension-aware verification.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/productivity/woocommerce-store-ops` |
| Version | `1.0.0` |
| Author | Hermes Agent |
| License | MIT |
| Tags | `woocommerce`, `wordpress`, `ecommerce`, `catalog`, `orders` |
| Related skills | [`wordpress-project-router`](/docs/user-guide/skills/bundled/software-development/software-development-wordpress-project-router), [`wordpress-project-triage`](/docs/user-guide/skills/bundled/software-development/software-development-wordpress-project-triage), [`wordpress-wpcli-ops`](/docs/user-guide/skills/bundled/devops/devops-wordpress-wpcli-ops), [`wordpress-migrations-and-deploys`](/docs/user-guide/skills/bundled/devops/devops-wordpress-migrations-and-deploys), [`requesting-code-review`](/docs/user-guide/skills/bundled/software-development/software-development-requesting-code-review) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# WooCommerce Store Operations

## Overview

Use this skill for the operational side of WooCommerce: product/catalog changes, order inspection, coupon/shipping/tax sanity checks, extension-aware troubleshooting, and post-change validation.

WooCommerce work looks deceptively like ordinary WordPress content work, but store behavior depends on product types, stock rules, taxes, shipping zones, coupons, checkout settings, payment gateways, and extension hooks. Small changes can have revenue impact.

**Core principle:** make small store changes, then verify the exact customer or operator flow affected.

## When to Use

Use this skill when:
- the user asks about WooCommerce products, variations, orders, coupons, tax, shipping, payments, or fulfillment behavior
- you need to validate a store after plugin changes or a deployment
- you need to inspect a store's operational state before editing settings or catalog data

Do not use this skill when:
- the project is not actually using WooCommerce
- the task is only generic WordPress runtime maintenance with no store-specific behavior
- the request is a host migration or deploy plan; use the migration skill first

## Store Triage First

Before changing anything, capture:
- WooCommerce version
- active store-critical plugins/extensions
- payment gateways in use
- shipping method assumptions
- tax configuration relevance
- whether the store is live and transacting now

Useful checks include:
- active plugin list
- order status patterns
- representative product types in the catalog
- cart and checkout routes

See `references/store-triage-checklist.md` for a concise pre-change checklist.

## High-Value Operational Surfaces

### 1. Product and catalog updates
Common tasks:
- title/description updates
- price or sale-price changes
- stock/availability changes
- category/tag cleanup
- image/media sanity checks
- variation review for attributes, stock, and pricing consistency

Verification after product changes:
- product page renders correctly
- price displays correctly
- add-to-cart works for the intended product type
- stock status matches expectation
- variation selectors behave correctly

### 2. Order inspection
Common tasks:
- inspect recent orders and statuses
- verify payment or fulfillment progression
- identify stuck processing/on-hold/failed patterns
- confirm whether a plugin or deploy changed checkout outcomes

Verification after order-related changes:
- one recent representative order still shows expected metadata/state
- admin order view loads without errors
- emails/webhooks are not obviously broken if the change touched those flows

### 3. Coupons, shipping, and tax sanity checks
Common tasks:
- confirm a coupon applies when and where expected
- validate shipping-zone assumptions
- verify tax display and totals at a high level

Verification after settings changes:
- test cart subtotal/discount math on a representative product
- confirm shipping methods appear for the right destination
- confirm tax-inclusive/exclusive display still matches expectation

### 4. Extension-aware troubleshooting
Always check for extensions that materially alter behavior:
- subscriptions
- bookings
- bundles/composites
- multilingual/currency plugins
- ERP/fulfillment integrations
- payment gateway add-ons
- checkout customization plugins

Rule: do not assume core WooCommerce owns the bug until extension interactions are reviewed.

## Safe Change Workflow

1. Inspect the current state first.
2. Name the exact store surface being changed.
3. Prefer the smallest reversible change.
4. Re-check the same operational surface after the change.
5. Verify one customer-visible flow if the change could affect revenue.

Examples:
- changing product stock → verify product page + add-to-cart
- changing shipping settings → verify cart/checkout shipping availability
- changing coupon rules → verify discount application on a test cart

## Common Risk Areas

### Product types
Different verification is needed for:
- simple products
- variable products
- grouped/bundled/composite products
- downloadable/virtual products
- subscription or booking products

### Payment and checkout
Be extra careful when the task touches:
- checkout fields or validation
- payment gateways
- taxes and totals
- shipping calculations
- stock reservation/reduction timing

### Deploys and plugin updates
After deploys or plugin changes, verify at minimum:
- storefront loads
- one product page loads
- cart works
- checkout loads
- admin orders load
- no obvious fatal/plugin conflict is present

## Operational Heuristics

- A display problem on product pages may be theme/template override related.
- A totals or checkout issue may come from taxes, shipping, or gateway extensions.
- A missing product may be catalog visibility, stock status, schedule, or sync-related.
- An order-state issue may be payment webhook, fulfillment extension, or custom automation related.

## Reference Workflow

Use the reference checklist when starting on a live store:
- `references/store-triage-checklist.md`

## Common Pitfalls

1. **Treating WooCommerce as ordinary posts/pages.**
   Store logic has revenue and fulfillment implications.

2. **Changing settings without testing a customer path.**
   Admin values can look correct while checkout is broken.

3. **Ignoring extensions.**
   Many store behaviors are extension-defined, not core-defined.

4. **Testing only one product shape.**
   Variable, bundled, subscription, or booking products often behave differently.

5. **Applying content-style verification to operational changes.**
   Store ops need cart/checkout/order verification, not just page rendering.

6. **Overlooking live-transaction risk.**
   Be explicit when a change could affect active orders or payments.

## Verification Checklist

- [ ] Confirmed WooCommerce is active and identified major store-critical extensions
- [ ] Identified whether the task affects catalog, orders, shipping, tax, coupons, or checkout
- [ ] Captured the relevant baseline before changing anything
- [ ] Verified the same store surface after the change
- [ ] Verified at least one customer-visible or operator-visible flow tied to the change
- [ ] Escalated caution appropriately for checkout, payments, or live transactional risk
