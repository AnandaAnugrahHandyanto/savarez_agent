# UI direction recovery pattern

Use this when an ecommerce redesign lands visually wrong or the user rejects the UI.

## Trigger

- User says the UI is bad, not liked, or not the right vibe.
- User gave a broad reference site and the implementation copied the surface style but not the ecommerce need.
- The task is aesthetic/product-positioning heavy and another production CSS rewrite would be guesswork.

## Recovery workflow

1. Stop editing the production UI.
2. Keep the running app intact.
3. Create 2-3 disposable, self-contained HTML sketches under `sketches/`.
4. Make each variant a different stance, not just a color swap.
5. Use realistic product names, prices, stock, and CTAs from the actual shop.
6. Open each sketch with browser tools and visually verify no obvious layout breakage.
7. Present the choices bluntly and recommend based on business fit.
8. Only apply the selected direction to production after the user chooses or asks for a hybrid.

## Useful variant stances for small Instagram/WhatsApp shops

- Premium Boutique: warm, professional, buyer-ready; good trust but less category personality.
- Gamer Drop: dark, energetic, anime/gaming identity; strong vibe but more niche.
- Mobile Market: phone-first with search/chips/order summary; best for practical conversion from social traffic.

## Pitfall

A portfolio reference can be useful for polish, spacing, and typography, but copying its calm/light aesthetic directly may make an ecommerce shop feel sterile. Translate the reference into shop goals: product clarity, CTAs, trust, and mobile buying flow.
