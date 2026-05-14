# HTML Template Reference

Agent-readable reference with CSS variable system, section HTML snippets, and responsive rules for generating self-contained landing page wireframes.

---

## HTML Structure

The generated file must be a single self-contained HTML file with:
- All CSS inline in a `<style>` block in the `<head>`
- No external CSS/JS dependencies
- No JavaScript (except optional smooth-scroll for anchor nav)
- Semantic HTML5 elements (`<section>`, `<header>`, `<main>`)

### Base Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{Company} — {Offer Type} Landing Page</title>
    <style>
        /* CSS Variables */
        :root {
            --color-primary: #1a1a2e;
            --color-secondary: #16213e;
            --color-accent: #e94560;
            --color-accent-hover: #d63851;
            --color-bg: #ffffff;
            --color-bg-alt: #f8f9fa;
            --color-text: #333333;
            --color-text-light: #666666;
            --color-text-on-accent: #ffffff;
            --color-border: #e0e0e0;
            --font-heading: 'system-ui', -apple-system, sans-serif;
            --font-body: 'system-ui', -apple-system, sans-serif;
            --container-max: 1100px;
            --section-padding: 80px 20px;
            --section-padding-mobile: 48px 16px;
            --border-radius: 8px;
            --cta-padding: 16px 32px;
            --cta-padding-mobile: 16px 24px;
            --cta-font-size: 18px;
        }

        /* Reset & Base */
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        html { scroll-behavior: smooth; }
        body {
            font-family: var(--font-body);
            color: var(--color-text);
            background: var(--color-bg);
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }

        /* Container */
        .container {
            max-width: var(--container-max);
            margin: 0 auto;
            padding: 0 20px;
        }

        /* Section Base */
        section { padding: var(--section-padding); }
        section:nth-child(even) { background: var(--color-bg-alt); }

        /* Typography */
        h1 { font-family: var(--font-heading); font-size: 2.8rem; line-height: 1.15; font-weight: 800; color: var(--color-primary); }
        h2 { font-family: var(--font-heading); font-size: 2rem; line-height: 1.25; font-weight: 700; color: var(--color-primary); margin-bottom: 16px; }
        h3 { font-family: var(--font-heading); font-size: 1.25rem; line-height: 1.35; font-weight: 600; color: var(--color-primary); margin-bottom: 8px; }
        p { margin-bottom: 16px; color: var(--color-text); }
        .text-light { color: var(--color-text-light); }
        .text-center { text-align: center; }

        /* CTA Button */
        .cta-button {
            display: inline-block;
            background: var(--color-accent);
            color: var(--color-text-on-accent);
            padding: var(--cta-padding);
            font-size: var(--cta-font-size);
            font-weight: 700;
            text-decoration: none;
            border-radius: var(--border-radius);
            border: none;
            cursor: pointer;
            transition: background 0.2s ease;
        }
        .cta-button:hover { background: var(--color-accent-hover); }
        .cta-microcopy {
            display: block;
            font-size: 0.85rem;
            color: var(--color-text-light);
            margin-top: 8px;
        }

        /* Visual Placeholder */
        .placeholder {
            border: 2px dashed var(--color-border);
            border-radius: var(--border-radius);
            padding: 40px 20px;
            text-align: center;
            color: var(--color-text-light);
            font-style: italic;
            background: var(--color-bg-alt);
            margin: 24px 0;
        }

        /* Grid Layouts */
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 32px; align-items: center; }
        .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px; }
        .grid-4 { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 20px; }

        /* Cards */
        .card {
            background: var(--color-bg);
            border: 1px solid var(--color-border);
            border-radius: var(--border-radius);
            padding: 24px;
        }

        /* Testimonial */
        .testimonial {
            background: var(--color-bg);
            border-left: 4px solid var(--color-accent);
            padding: 24px;
            border-radius: 0 var(--border-radius) var(--border-radius) 0;
            margin-bottom: 24px;
        }
        .testimonial-text { font-style: italic; font-size: 1.05rem; margin-bottom: 12px; }
        .testimonial-author { font-weight: 600; color: var(--color-primary); }
        .testimonial-role { font-size: 0.9rem; color: var(--color-text-light); }

        /* FAQ */
        .faq-item { border-bottom: 1px solid var(--color-border); padding: 20px 0; }
        .faq-question { font-weight: 600; color: var(--color-primary); margin-bottom: 8px; font-size: 1.1rem; }
        .faq-answer { color: var(--color-text); }

        /* Trust Badges */
        .trust-bar {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 40px;
            flex-wrap: wrap;
            padding: 20px 0;
        }
        .trust-item { text-align: center; color: var(--color-text-light); font-size: 0.9rem; }

        /* Urgency Banner */
        .urgency-banner {
            background: var(--color-primary);
            color: var(--color-text-on-accent);
            text-align: center;
            padding: 16px 20px;
            font-weight: 600;
        }

        /* Responsive: Mobile First */
        @media (max-width: 768px) {
            section { padding: var(--section-padding-mobile); }
            h1 { font-size: 1.9rem; }
            h2 { font-size: 1.5rem; }
            .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; }
            .cta-button {
                display: block;
                width: 100%;
                text-align: center;
                padding: var(--cta-padding-mobile);
            }
            .trust-bar { gap: 20px; }
        }
    </style>
</head>
<body>
    <!-- Sections go here -->
</body>
</html>
```

---

## Section Snippets

### Section 1: Hero

```html
<section id="hero" style="padding-top: 60px; padding-bottom: 60px;">
    <div class="container">
        <div class="grid-2">
            <div>
                <h1>{Headline}</h1>
                <p style="font-size: 1.2rem; margin: 16px 0 24px; color: var(--color-text-light);">
                    {Sub-headline}
                </p>
                <a href="#cta" class="cta-button">{CTA Button Text}</a>
                <span class="cta-microcopy">{Microcopy}</span>
            </div>
            <div>
                <div class="placeholder">[{Visual placeholder description}]</div>
            </div>
        </div>
    </div>
</section>
```

### Section 2: Benefits

```html
<section id="benefits">
    <div class="container">
        <h2 class="text-center">{Benefits Section Headline}</h2>
        <p class="text-center text-light" style="max-width: 600px; margin: 0 auto 40px;">
            {Benefits intro text}
        </p>
        <div class="grid-3">
            <div class="card">
                <h3>{Benefit 1 Title}</h3>
                <p>{Benefit 1 Description}</p>
            </div>
            <div class="card">
                <h3>{Benefit 2 Title}</h3>
                <p>{Benefit 2 Description}</p>
            </div>
            <div class="card">
                <h3>{Benefit 3 Title}</h3>
                <p>{Benefit 3 Description}</p>
            </div>
        </div>
        <div class="text-center" style="margin-top: 40px;">
            <a href="#cta" class="cta-button">{CTA Button Text}</a>
            <span class="cta-microcopy">{Microcopy}</span>
        </div>
    </div>
</section>
```

### Section 3: Trust/Authority

```html
<section id="trust">
    <div class="container">
        <h2 class="text-center">{Trust Section Headline}</h2>
        <div class="trust-bar">
            <div class="trust-item">
                <div class="placeholder" style="padding: 20px; margin: 0;">[{Trust Badge 1}]</div>
                <p style="margin-top: 8px;">{Trust label 1}</p>
            </div>
            <div class="trust-item">
                <div class="placeholder" style="padding: 20px; margin: 0;">[{Trust Badge 2}]</div>
                <p style="margin-top: 8px;">{Trust label 2}</p>
            </div>
            <div class="trust-item">
                <div class="placeholder" style="padding: 20px; margin: 0;">[{Trust Badge 3}]</div>
                <p style="margin-top: 8px;">{Trust label 3}</p>
            </div>
        </div>
    </div>
</section>
```

### Section 4: Social Proof

```html
<section id="social-proof">
    <div class="container">
        <h2 class="text-center">{Social Proof Headline}</h2>
        <div class="grid-2" style="margin-top: 32px;">
            <div class="testimonial">
                <p class="testimonial-text">"{Testimonial quote 1}"</p>
                <p class="testimonial-author">{Name 1}</p>
                <p class="testimonial-role">{Role/Company 1} [Replace with real testimonial]</p>
            </div>
            <div class="testimonial">
                <p class="testimonial-text">"{Testimonial quote 2}"</p>
                <p class="testimonial-author">{Name 2}</p>
                <p class="testimonial-role">{Role/Company 2} [Replace with real testimonial]</p>
            </div>
        </div>
        <div class="text-center" style="margin-top: 40px;">
            <a href="#cta" class="cta-button">{CTA Button Text}</a>
            <span class="cta-microcopy">{Microcopy}</span>
        </div>
    </div>
</section>
```

### Section 5: Objection Handling (FAQ)

```html
<section id="objections">
    <div class="container" style="max-width: 800px;">
        <h2 class="text-center">{FAQ Headline}</h2>
        <div style="margin-top: 32px;">
            <div class="faq-item">
                <p class="faq-question">{Question 1}</p>
                <p class="faq-answer">{Answer 1}</p>
            </div>
            <div class="faq-item">
                <p class="faq-question">{Question 2}</p>
                <p class="faq-answer">{Answer 2}</p>
            </div>
            <div class="faq-item">
                <p class="faq-question">{Question 3}</p>
                <p class="faq-answer">{Answer 3}</p>
            </div>
        </div>
        <!-- Guarantee near CTA -->
        <div class="text-center" style="margin-top: 40px;">
            <p style="font-weight: 600; color: var(--color-primary);">{Guarantee Statement}</p>
            <a href="#cta" class="cta-button" style="margin-top: 16px;">{CTA Button Text}</a>
            <span class="cta-microcopy">{Microcopy}</span>
        </div>
    </div>
</section>
```

### Section 6: Urgency/Scarcity (Optional)

```html
<section id="urgency" style="background: var(--color-primary); color: var(--color-text-on-accent);">
    <div class="container text-center">
        <h2 style="color: var(--color-text-on-accent);">{Urgency Headline}</h2>
        <p style="color: rgba(255,255,255,0.85); font-size: 1.1rem; margin-bottom: 24px;">
            {Urgency explanation — why the limitation exists}
        </p>
        <p style="font-size: 1.3rem; font-weight: 700; margin-bottom: 24px;">
            {Specific deadline or scarcity detail} [Replace with real deadline]
        </p>
        <a href="#cta" class="cta-button" style="background: var(--color-bg); color: var(--color-primary);">
            {CTA Button Text}
        </a>
    </div>
</section>
```

### Section 7: Final CTA

```html
<section id="cta" style="background: var(--color-primary); color: var(--color-text-on-accent); padding: 80px 20px;">
    <div class="container text-center" style="max-width: 700px;">
        <h2 style="color: var(--color-text-on-accent);">{Value Recap Headline}</h2>
        <ul style="list-style: none; text-align: left; max-width: 500px; margin: 24px auto; color: rgba(255,255,255,0.9);">
            <li style="padding: 8px 0;">&#10003; {Value point 1}</li>
            <li style="padding: 8px 0;">&#10003; {Value point 2}</li>
            <li style="padding: 8px 0;">&#10003; {Value point 3}</li>
            <li style="padding: 8px 0;">&#10003; {Value point 4}</li>
            <li style="padding: 8px 0;">&#10003; {Value point 5 — guarantee}</li>
        </ul>
        <a href="#" class="cta-button" style="background: var(--color-accent); font-size: 1.2rem; padding: 20px 40px;">
            {CTA Button Text — strongest version}
        </a>
        <span class="cta-microcopy" style="color: rgba(255,255,255,0.7);">{Final microcopy}</span>
    </div>
</section>
```

---

## CSS Variable Guide

When populating CSS variables from Chrome DevTools extraction:

| Variable | Source | Fallback |
|----------|--------|----------|
| `--color-primary` | Nav/header background or heading color | `#1a1a2e` |
| `--color-secondary` | Secondary/darker background | `#16213e` |
| `--color-accent` | CTA button background color | `#e94560` |
| `--color-accent-hover` | Darken accent by ~10% | Darken `--color-accent` |
| `--color-bg` | Main background | `#ffffff` |
| `--color-bg-alt` | Alternate section background | `#f8f9fa` |
| `--color-text` | Body text color | `#333333` |
| `--color-text-light` | Secondary text color | `#666666` |
| `--color-text-on-accent` | Text color on accent buttons | `#ffffff` |
| `--font-heading` | Heading font-family from h1 | `system-ui, sans-serif` |
| `--font-body` | Body font-family | `system-ui, sans-serif` |

---

## Responsive Rules

| Rule | Desktop (>768px) | Mobile (<=768px) |
|------|------------------|------------------|
| Grids | Multi-column | Single column |
| CTA buttons | Inline, auto-width | Full-width, block |
| Section padding | 80px vertical | 48px vertical |
| h1 font size | 2.8rem | 1.9rem |
| h2 font size | 2rem | 1.5rem |
| Trust bar | Horizontal row | Wrapped row, tighter gaps |

---

## File Output

- **Path:** `created/landing-pages/{YYYYMMDD}_{company}_{offer-type}.html`
- **Naming:** Date, company from brand.md, offer type from questionnaire. Sanitize: lowercase, replace spaces with hyphens, remove special chars
- **Creates directory** if it doesn't exist

---

## Key Rules

1. **Self-contained:** No external stylesheets, scripts, or CDN links
2. **No navigation:** No nav bar, no footer links (one-page-one-goal)
3. **No JavaScript:** Pure CSS layout (smooth-scroll via `html { scroll-behavior: smooth }`)
4. **CTA repetition:** Place CTA after hero, benefits, social proof, objections, and in final section (5 placements minimum)
5. **Alternating backgrounds:** Even sections get `var(--color-bg-alt)` via `section:nth-child(even)`
6. **Placeholder pattern:** `<div class="placeholder">[Descriptive text, e.g., "Product Screenshot — replace with real image"]</div>`
7. **Max container width:** 1100px centered, with 20px horizontal padding
