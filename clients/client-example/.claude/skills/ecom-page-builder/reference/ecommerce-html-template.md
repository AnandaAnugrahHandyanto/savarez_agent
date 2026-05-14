# Ecommerce HTML Template Reference

Agent-readable reference with CSS variable system, section HTML snippets, and responsive rules for generating self-contained ecommerce page wireframes. Includes templates for both Dedicated LPs (product-image-first hero, no nav) and Product Pages (gallery + info layout, with nav).

---

## HTML Structure

The generated file must be a single self-contained HTML file with:
- All CSS inline in a `<style>` block in the `<head>`
- No external CSS/JS dependencies
- No JavaScript
- Semantic HTML5 elements (`<section>`, `<header>`, `<main>`)

### Base Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{Company} — {Product Name} | {Page Type}</title>
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
            --color-star: #f5a623;
            --color-savings: #27ae60;
            --color-stock-low: #e74c3c;
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
        .placeholder-product-image {
            border: 2px dashed var(--color-border);
            border-radius: var(--border-radius);
            padding: 60px 20px;
            text-align: center;
            color: var(--color-text-light);
            font-style: italic;
            background: var(--color-bg-alt);
            min-height: 400px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .placeholder-customer-photo {
            border: 2px dashed var(--color-border);
            border-radius: var(--border-radius);
            padding: 20px;
            text-align: center;
            color: var(--color-text-light);
            font-style: italic;
            background: var(--color-bg-alt);
            min-height: 150px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        /* Grid Layouts */
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 32px; align-items: center; }
        .grid-2-image-first { display: grid; grid-template-columns: 3fr 2fr; gap: 40px; align-items: start; }
        .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px; }
        .grid-4 { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 20px; }

        /* Cards */
        .card {
            background: var(--color-bg);
            border: 1px solid var(--color-border);
            border-radius: var(--border-radius);
            padding: 24px;
        }

        /* Price Display */
        .price-display { margin: 16px 0; }
        .price-current { font-size: 2rem; font-weight: 800; color: var(--color-primary); }
        .price-original { font-size: 1.2rem; color: var(--color-text-light); text-decoration: line-through; margin-left: 8px; }
        .price-savings {
            display: inline-block;
            background: var(--color-savings);
            color: #fff;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 0.85rem;
            font-weight: 600;
            margin-left: 8px;
        }

        /* Star Rating */
        .star-rating { color: var(--color-star); font-size: 1.2rem; letter-spacing: 2px; }
        .review-count { font-size: 0.9rem; color: var(--color-text-light); margin-left: 8px; }

        /* Review Card */
        .review-card {
            background: var(--color-bg);
            border: 1px solid var(--color-border);
            border-radius: var(--border-radius);
            padding: 24px;
            margin-bottom: 16px;
        }
        .review-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
        .verified-badge {
            font-size: 0.8rem;
            color: var(--color-savings);
            font-weight: 600;
        }
        .review-text { font-style: italic; margin-bottom: 12px; line-height: 1.5; }
        .review-author { font-weight: 600; color: var(--color-primary); font-size: 0.9rem; }

        /* Trust Badge Row */
        .trust-badge-row {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 32px;
            flex-wrap: wrap;
            padding: 20px 0;
        }
        .trust-badge-item {
            text-align: center;
            font-size: 0.85rem;
            color: var(--color-text-light);
        }
        .trust-badge-icon { font-size: 1.5rem; margin-bottom: 4px; }

        /* Stock Indicator */
        .stock-indicator { font-size: 0.9rem; font-weight: 600; margin: 8px 0; }
        .stock-in { color: var(--color-savings); }
        .stock-low { color: var(--color-stock-low); }

        /* Specs Table */
        .specs-table { width: 100%; border-collapse: collapse; margin: 24px 0; }
        .specs-table td { padding: 12px 16px; border-bottom: 1px solid var(--color-border); }
        .specs-table td:first-child { font-weight: 600; color: var(--color-primary); width: 35%; }

        /* FAQ */
        .faq-item { border-bottom: 1px solid var(--color-border); padding: 20px 0; }
        .faq-question { font-weight: 600; color: var(--color-primary); margin-bottom: 8px; font-size: 1.1rem; }
        .faq-answer { color: var(--color-text); }

        /* Urgency Banner */
        .urgency-banner {
            background: var(--color-primary);
            color: var(--color-text-on-accent);
            text-align: center;
            padding: 16px 20px;
            font-weight: 600;
        }

        /* Express Checkout */
        .express-checkout {
            display: flex;
            gap: 12px;
            margin-top: 12px;
            flex-wrap: wrap;
        }
        .express-button {
            flex: 1;
            min-width: 100px;
            padding: 12px;
            border: 1px solid var(--color-border);
            border-radius: var(--border-radius);
            text-align: center;
            font-size: 0.85rem;
            color: var(--color-text);
            background: var(--color-bg);
            cursor: pointer;
        }

        /* Product Page: Gallery + Info Layout */
        .product-layout {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
            align-items: start;
        }
        .gallery-column { position: relative; }
        .gallery-thumbnails {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 8px;
            margin-top: 12px;
        }
        .gallery-thumb {
            border: 2px dashed var(--color-border);
            border-radius: 4px;
            padding: 8px;
            text-align: center;
            font-size: 0.7rem;
            color: var(--color-text-light);
            font-style: italic;
            min-height: 60px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        /* Cross-sell Grid */
        .cross-sell-card {
            background: var(--color-bg);
            border: 1px solid var(--color-border);
            border-radius: var(--border-radius);
            padding: 16px;
            text-align: center;
        }
        .cross-sell-card .placeholder {
            margin: 0 0 12px 0;
            padding: 30px 10px;
            min-height: 120px;
        }

        /* Responsive: Mobile */
        @media (max-width: 768px) {
            section { padding: var(--section-padding-mobile); }
            h1 { font-size: 1.9rem; }
            h2 { font-size: 1.5rem; }
            .grid-2, .grid-3, .grid-4, .grid-2-image-first, .product-layout {
                grid-template-columns: 1fr;
            }
            .cta-button {
                display: block;
                width: 100%;
                text-align: center;
                padding: var(--cta-padding-mobile);
            }
            .trust-badge-row { gap: 16px; }
            .gallery-thumbnails { grid-template-columns: repeat(5, 1fr); }
            .price-current { font-size: 1.6rem; }
            .express-checkout { flex-direction: column; }
        }
    </style>
</head>
<body>
    <!-- Sections go here -->
</body>
</html>
```

---

## Dedicated LP Section Snippets

### Section 1: Product Showcase (Hero)

```html
<section id="product-showcase" style="padding-top: 60px; padding-bottom: 60px;">
    <div class="container">
        <div class="grid-2-image-first">
            <div>
                <div class="placeholder-product-image">
                    [Product hero image — 800x800px minimum. Show the actual product clearly, not lifestyle-only.]
                </div>
            </div>
            <div>
                <p class="text-light" style="font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">
                    {Brand Name}
                </p>
                <h1>{Differentiator Tagline — under 10 words}</h1>
                <p style="font-size: 1.1rem; margin: 16px 0; color: var(--color-text-light);">
                    {Sub-headline — mechanism or proof}
                </p>
                <div class="price-display">
                    <span class="price-current">${price}</span>
                    <span class="price-original">${originalPrice}</span>
                    <span class="price-savings">Save ${savings} ({percent}%)</span>
                </div>
                <div style="margin-top: 24px;">
                    <a href="#purchase" class="cta-button">{CTA Button Text}</a>
                    <span class="cta-microcopy">{Microcopy — e.g., "Free shipping. 60-day returns."}</span>
                </div>
            </div>
        </div>
    </div>
</section>
```

### Section 2: Customer Evidence

```html
<section id="customer-evidence">
    <div class="container">
        <div class="text-center" style="margin-bottom: 40px;">
            <span class="star-rating">★★★★★</span>
            <h2>{Aggregate rating — e.g., "4.8 out of 5 from 2,347 verified reviews"}</h2>
        </div>
        <div class="grid-2">
            <div class="review-card">
                <div class="review-header">
                    <span class="star-rating" style="font-size: 1rem;">★★★★★</span>
                    <span class="verified-badge">✓ Verified Buyer</span>
                </div>
                <p class="review-text">"{Specific result quote — e.g., 'Wore these in a downpour, feet stayed completely dry.'}"</p>
                <div class="placeholder-customer-photo">[Customer photo with product]</div>
                <p class="review-author">{Name}, Verified Buyer [Replace with real customer review]</p>
            </div>
            <div class="review-card">
                <div class="review-header">
                    <span class="star-rating" style="font-size: 1rem;">★★★★★</span>
                    <span class="verified-badge">✓ Verified Buyer</span>
                </div>
                <p class="review-text">"{Specific result quote}"</p>
                <div class="placeholder-customer-photo">[Customer photo with product]</div>
                <p class="review-author">{Name}, Verified Buyer [Replace with real customer review]</p>
            </div>
        </div>
        <!-- UGC Grid -->
        <div class="grid-3" style="margin-top: 32px;">
            <div class="placeholder-customer-photo">[UGC photo 1]</div>
            <div class="placeholder-customer-photo">[UGC photo 2]</div>
            <div class="placeholder-customer-photo">[UGC photo 3]</div>
        </div>
        <div class="text-center" style="margin-top: 40px;">
            <a href="#purchase" class="cta-button">{CTA Button Text}</a>
            <span class="cta-microcopy">{Microcopy}</span>
        </div>
    </div>
</section>
```

### Section 3: Product Benefits

```html
<section id="product-benefits">
    <div class="container">
        <h2 class="text-center">{Benefits Section Headline}</h2>
        <div class="grid-3" style="margin-top: 40px;">
            <div class="card">
                <div class="placeholder" style="padding: 20px; margin: 0 0 16px 0;">[Benefit icon or product detail image]</div>
                <h3>{Benefit 1: Outcome headline}</h3>
                <p>{Feature-to-outcome description}</p>
            </div>
            <div class="card">
                <div class="placeholder" style="padding: 20px; margin: 0 0 16px 0;">[Benefit icon or product detail image]</div>
                <h3>{Benefit 2: Outcome headline}</h3>
                <p>{Feature-to-outcome description}</p>
            </div>
            <div class="card">
                <div class="placeholder" style="padding: 20px; margin: 0 0 16px 0;">[Benefit icon or product detail image]</div>
                <h3>{Benefit 3: Outcome headline}</h3>
                <p>{Feature-to-outcome description}</p>
            </div>
        </div>
    </div>
</section>
```

### Section 4: The Details

```html
<section id="details">
    <div class="container">
        <h2 class="text-center">{Details Section Headline}</h2>
        <div class="grid-2" style="margin-top: 40px;">
            <div>
                <h3>Specifications</h3>
                <table class="specs-table">
                    <tr><td>Material</td><td>{material}</td></tr>
                    <tr><td>Dimensions</td><td>{dimensions}</td></tr>
                    <tr><td>Weight</td><td>{weight}</td></tr>
                    <tr><td>Care</td><td>{care instructions}</td></tr>
                </table>
            </div>
            <div>
                <h3>What's Included</h3>
                <ul style="list-style: none; margin-top: 16px;">
                    <li style="padding: 8px 0;">&#10003; {Item 1}</li>
                    <li style="padding: 8px 0;">&#10003; {Item 2}</li>
                    <li style="padding: 8px 0;">&#10003; {Item 3}</li>
                </ul>
            </div>
        </div>
    </div>
</section>
```

### Section 5: Purchase Confidence

```html
<section id="purchase-confidence">
    <div class="container" style="max-width: 800px;">
        <h2 class="text-center">{Confidence Section Headline — e.g., "Buy With Confidence"}</h2>
        <!-- Trust badges row -->
        <div class="trust-badge-row" style="margin: 32px 0;">
            <div class="trust-badge-item">
                <div class="trust-badge-icon">🚚</div>
                <p>{Shipping promise — e.g., "Free Shipping"}</p>
            </div>
            <div class="trust-badge-item">
                <div class="trust-badge-icon">↩️</div>
                <p>{Return policy — e.g., "60-Day Returns"}</p>
            </div>
            <div class="trust-badge-item">
                <div class="trust-badge-icon">🔒</div>
                <p>Secure Checkout</p>
            </div>
            <div class="trust-badge-item">
                <div class="trust-badge-icon">✓</div>
                <p>{Guarantee — e.g., "Satisfaction Guaranteed"}</p>
            </div>
        </div>
        <!-- FAQ -->
        <h3 style="margin-top: 40px; margin-bottom: 16px;">Frequently Asked Questions</h3>
        <div>
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
        <div class="text-center" style="margin-top: 40px;">
            <a href="#purchase" class="cta-button">{CTA Button Text}</a>
            <span class="cta-microcopy">{Microcopy — guarantee reminder}</span>
        </div>
    </div>
</section>
```

### Section 6: Act Now (Optional — skip if no urgency)

```html
<section id="act-now" style="background: var(--color-primary); color: var(--color-text-on-accent);">
    <div class="container text-center">
        <h2 style="color: var(--color-text-on-accent);">{Urgency Headline}</h2>
        <p style="color: rgba(255,255,255,0.85); font-size: 1.1rem; margin-bottom: 24px;">
            {Urgency explanation — why the limitation exists}
        </p>
        <p style="font-size: 1.3rem; font-weight: 700; margin-bottom: 24px;">
            {Specific deadline or scarcity detail} [Replace with real deadline]
        </p>
        <a href="#purchase" class="cta-button" style="background: var(--color-bg); color: var(--color-primary);">
            {CTA Button Text}
        </a>
    </div>
</section>
```

### Section 7: Complete Your Purchase

```html
<section id="purchase" style="background: var(--color-primary); color: var(--color-text-on-accent); padding: 80px 20px;">
    <div class="container text-center" style="max-width: 700px;">
        <h2 style="color: var(--color-text-on-accent);">{Value Recap Headline}</h2>
        <ul style="list-style: none; text-align: left; max-width: 500px; margin: 24px auto; color: rgba(255,255,255,0.9);">
            <li style="padding: 8px 0;">&#10003; {Product + key feature}</li>
            <li style="padding: 8px 0;">&#10003; {Key benefit 1}</li>
            <li style="padding: 8px 0;">&#10003; {Key benefit 2}</li>
            <li style="padding: 8px 0;">&#10003; {Shipping promise}</li>
            <li style="padding: 8px 0;">&#10003; {Guarantee}</li>
        </ul>
        <div class="price-display" style="margin: 24px 0;">
            <span class="price-current" style="color: var(--color-text-on-accent); font-size: 2.4rem;">${price}</span>
            <span class="price-original" style="color: rgba(255,255,255,0.6);">${originalPrice}</span>
            <span class="price-savings">Save ${savings}</span>
        </div>
        <a href="#" class="cta-button" style="background: var(--color-accent); font-size: 1.2rem; padding: 20px 40px;">
            {CTA Button Text — strongest version}
        </a>
        <div class="express-checkout" style="justify-content: center; margin-top: 16px;">
            <div class="express-button" style="border-color: rgba(255,255,255,0.3); color: rgba(255,255,255,0.8);">Apple Pay</div>
            <div class="express-button" style="border-color: rgba(255,255,255,0.3); color: rgba(255,255,255,0.8);">Google Pay</div>
            <div class="express-button" style="border-color: rgba(255,255,255,0.3); color: rgba(255,255,255,0.8);">Shop Pay</div>
        </div>
        <span class="cta-microcopy" style="color: rgba(255,255,255,0.7); margin-top: 16px;">
            {Final microcopy — e.g., "Secure checkout. 60-day money-back guarantee."}
        </span>
    </div>
</section>
```

---

## Product Page Section Snippets

### Product Page: Header (with nav placeholder)

```html
<header style="border-bottom: 1px solid var(--color-border); padding: 16px 0;">
    <div class="container" style="display: flex; justify-content: space-between; align-items: center;">
        <div style="font-size: 1.2rem; font-weight: 700; color: var(--color-primary);">{Brand Name}</div>
        <nav style="color: var(--color-text-light); font-size: 0.9rem;">
            [Navigation placeholder — Shop | About | Contact | Cart (0)]
        </nav>
    </div>
</header>
<div class="container" style="padding: 12px 20px;">
    <p class="text-light" style="font-size: 0.85rem; margin: 0;">Home > {Category} > {Product Name}</p>
</div>
```

### Product Page: Sections 1-3 (Product Identity + Offer Stack + Add-to-Cart)

These three sections render as a single above-the-fold block with gallery on the left and info on the right.

```html
<section id="product-main" style="padding-top: 20px;">
    <div class="container">
        <div class="product-layout">
            <!-- Gallery Column -->
            <div class="gallery-column">
                <div class="placeholder-product-image">
                    [Product hero image — 800x800px. Updates with variant selection.]
                </div>
                <div class="gallery-thumbnails">
                    <div class="gallery-thumb">[Hero]</div>
                    <div class="gallery-thumb">[Angle]</div>
                    <div class="gallery-thumb">[Lifestyle]</div>
                    <div class="gallery-thumb">[Detail]</div>
                    <div class="gallery-thumb">[Scale]</div>
                </div>
            </div>
            <!-- Info Column -->
            <div class="info-column">
                <!-- Product Identity -->
                <div style="margin-bottom: 8px;">
                    <span class="star-rating">★★★★★</span>
                    <span class="review-count">({reviewCount} reviews)</span>
                </div>
                <h1 style="font-size: 2rem;">{Product Title — descriptive with key attributes}</h1>
                <p style="color: var(--color-text-light); margin: 8px 0 16px;">{One-line benefit summary}</p>

                <!-- Offer Stack -->
                <div class="price-display">
                    <span class="price-current">${price}</span>
                    <span class="price-original">${originalPrice}</span>
                    <span class="price-savings">Save ${savings} ({percent}%)</span>
                </div>

                <!-- Variant selectors -->
                <div style="margin: 20px 0;">
                    <p style="font-weight: 600; margin-bottom: 8px;">Color: {Selected Color}</p>
                    <div style="display: flex; gap: 8px;">
                        <div class="placeholder" style="width: 40px; height: 40px; padding: 4px; margin: 0; border-radius: 50%;">[Color 1]</div>
                        <div class="placeholder" style="width: 40px; height: 40px; padding: 4px; margin: 0; border-radius: 50%;">[Color 2]</div>
                        <div class="placeholder" style="width: 40px; height: 40px; padding: 4px; margin: 0; border-radius: 50%;">[Color 3]</div>
                    </div>
                </div>
                <div style="margin: 20px 0;">
                    <p style="font-weight: 600; margin-bottom: 8px;">Size: {Selected Size}</p>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                        <div class="placeholder" style="padding: 8px 16px; margin: 0;">{Size 1}</div>
                        <div class="placeholder" style="padding: 8px 16px; margin: 0;">{Size 2}</div>
                        <div class="placeholder" style="padding: 8px 16px; margin: 0;">{Size 3}</div>
                    </div>
                    <p style="font-size: 0.85rem; margin-top: 8px;"><a href="#" style="color: var(--color-accent);">Size Guide</a></p>
                </div>

                <!-- Offer stack details -->
                <div style="border: 1px solid var(--color-border); border-radius: var(--border-radius); padding: 16px; margin: 16px 0;">
                    <p class="stock-indicator stock-in" style="margin-bottom: 8px;">✓ In Stock — Ships within 24 hours</p>
                    <p style="font-size: 0.9rem; margin-bottom: 4px;">🚚 {Shipping info — e.g., "Free shipping on orders over $75"}</p>
                    <p style="font-size: 0.9rem; margin-bottom: 0;">↩️ {Return policy — e.g., "Free returns within 60 days"}</p>
                </div>

                <!-- Add-to-Cart Action -->
                <a href="#" class="cta-button" style="display: block; text-align: center; margin-top: 16px;">{Add to Cart}</a>
                <span class="cta-microcopy text-center">{Microcopy — e.g., "Free shipping + easy returns"}</span>
                <div class="express-checkout">
                    <div class="express-button">Apple Pay</div>
                    <div class="express-button">Google Pay</div>
                    <div class="express-button">Shop Pay</div>
                </div>
            </div>
        </div>
    </div>
</section>
```

### Product Page: Section 4 — Social Proof (Reviews)

```html
<section id="reviews">
    <div class="container">
        <h2>Customer Reviews</h2>
        <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 24px;">
            <span class="star-rating" style="font-size: 1.5rem;">★★★★★</span>
            <span style="font-size: 1.2rem; font-weight: 600;">{rating} out of 5</span>
            <span class="review-count">Based on {count} reviews</span>
        </div>
        <p class="text-light" style="margin-bottom: 24px;">Sort by: Most Helpful | Most Recent | Photos Only | ★★★★★ | ★★★★ | ★★★</p>
        <div class="grid-2">
            <div class="review-card">
                <div class="review-header">
                    <span class="star-rating" style="font-size: 1rem;">★★★★★</span>
                    <span class="verified-badge">✓ Verified Buyer</span>
                </div>
                <p class="review-text">"{Review text}" [Replace with real customer review]</p>
                <p class="review-author">{Name}</p>
            </div>
            <div class="review-card">
                <div class="review-header">
                    <span class="star-rating" style="font-size: 1rem;">★★★★★</span>
                    <span class="verified-badge">✓ Verified Buyer</span>
                </div>
                <p class="review-text">"{Review text}" [Replace with real customer review]</p>
                <p class="review-author">{Name}</p>
            </div>
        </div>
    </div>
</section>
```

### Product Page: Section 5 — Product Details

Uses the same specs table and FAQ snippets from the Dedicated LP sections 4 and 5.

### Product Page: Section 6 — Cross-sell

```html
<section id="cross-sell">
    <div class="container">
        <h2>Frequently Bought Together</h2>
        <div class="grid-3" style="margin-top: 24px;">
            <div class="cross-sell-card">
                <div class="placeholder">[Product image]</div>
                <h3 style="font-size: 1rem;">{Product Name 1}</h3>
                <p style="font-weight: 600; color: var(--color-primary);">${price}</p>
                <a href="#" style="color: var(--color-accent); font-size: 0.9rem;">+ Add to Cart</a>
            </div>
            <div class="cross-sell-card">
                <div class="placeholder">[Product image]</div>
                <h3 style="font-size: 1rem;">{Product Name 2}</h3>
                <p style="font-weight: 600; color: var(--color-primary);">${price}</p>
                <a href="#" style="color: var(--color-accent); font-size: 0.9rem;">+ Add to Cart</a>
            </div>
            <div class="cross-sell-card">
                <div class="placeholder">[Product image]</div>
                <h3 style="font-size: 1rem;">{Product Name 3}</h3>
                <p style="font-weight: 600; color: var(--color-primary);">${price}</p>
                <a href="#" style="color: var(--color-accent); font-size: 0.9rem;">+ Add to Cart</a>
            </div>
        </div>
        <div class="text-center" style="margin-top: 24px;">
            <a href="#" class="cta-button" style="background: var(--color-primary);">Add All to Cart — Save ${bundleSavings}</a>
        </div>
    </div>
</section>
```

### Product Page: Section 7 — Trust Reinforcement

```html
<section id="trust">
    <div class="container">
        <div class="trust-badge-row">
            <div class="trust-badge-item">
                <div class="trust-badge-icon">↩️</div>
                <p>{Return policy detail}</p>
            </div>
            <div class="trust-badge-item">
                <div class="trust-badge-icon">🔒</div>
                <p>Secure Checkout</p>
            </div>
            <div class="trust-badge-item">
                <div class="trust-badge-icon">💬</div>
                <p>{Contact option}</p>
            </div>
            <div class="trust-badge-item">
                <div class="placeholder" style="padding: 10px; margin: 0;">[Certification badge]</div>
                <p>{Certification name}</p>
            </div>
        </div>
    </div>
</section>
```

---

## CSS Variable Guide

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
| `--color-text-on-accent` | Text on accent buttons | `#ffffff` |
| `--color-star` | Star rating color | `#f5a623` |
| `--color-savings` | Savings/in-stock color | `#27ae60` |
| `--color-stock-low` | Low stock warning color | `#e74c3c` |
| `--font-heading` | Heading font-family | `system-ui, sans-serif` |
| `--font-body` | Body font-family | `system-ui, sans-serif` |

---

## Responsive Rules

| Rule | Desktop (>768px) | Mobile (<=768px) |
|------|------------------|------------------|
| Grids | Multi-column | Single column |
| Product layout | Gallery left, info right | Gallery stacked above info |
| CTA buttons | Inline, auto-width | Full-width, block |
| Section padding | 80px vertical | 48px vertical |
| h1 font size | 2.8rem (LP) / 2rem (product page) | 1.9rem / 1.5rem |
| Express checkout | Horizontal row | Vertical stack |
| Gallery thumbnails | 5 across | 5 across (smaller) |
| Trust badge row | Horizontal | Wrapped, tighter gaps |

---

## File Output

- **Dedicated LP path:** `created/landing-pages/{YYYYMMDD}_ecom-lp_{product}.html`
- **Product Page path:** `created/landing-pages/{YYYYMMDD}_product-page_{product}.html`
- **Naming:** Date, page type prefix, product name sanitized (lowercase, hyphens, no special chars)
- **Creates directory** if it doesn't exist

---

## Key Rules

1. **Self-contained:** No external stylesheets, scripts, or CDN links
2. **Dedicated LP — No navigation:** No nav bar, no footer links (one-page-one-goal)
3. **Product Page — Include nav:** Header nav placeholder, breadcrumbs, footer placeholder
4. **No JavaScript:** Pure CSS layout
5. **CTA repetition (Dedicated LP):** Minimum 4 placements (hero, after evidence, after confidence, final section)
6. **CTA at position 3 (Product Page):** Add-to-cart in the info column, above reviews and details
7. **Product image first:** Gallery/product image takes 60% of above-fold space
8. **Price visible above fold:** Always show price in the first viewport
9. **Placeholder patterns:**
   - Product images: `<div class="placeholder-product-image">[Descriptive text — dimensions]</div>`
   - Customer photos: `<div class="placeholder-customer-photo">[Customer photo with product]</div>`
   - General: `<div class="placeholder">[Descriptive text]</div>`
10. **Max container width:** 1100px centered, with 20px horizontal padding
