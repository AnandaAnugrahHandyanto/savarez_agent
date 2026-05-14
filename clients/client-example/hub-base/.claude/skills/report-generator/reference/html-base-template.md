# HTML Base Template

Self-contained HTML shell for branded audit reports. CSS variables are populated from `my-brand/brand.json`. All styles inline — no external dependencies.

## Base Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_title} — {client_name} | {company_name}</title>
    {google_fonts_link}
    <style>
        /* CSS Variables — populated from brand.json */
        :root {
            --color-primary: {colors.primary};
            --color-secondary: {colors.secondary};
            --color-accent: {colors.accent};
            --color-bg: {colors.background};
            --color-bg-alt: {colors.backgroundAlt};
            --color-text: {colors.text};
            --color-text-light: {colors.textLight};
            --color-border: #e0e0e0;
            --color-success: #22c55e;
            --color-warning: #f59e0b;
            --color-danger: #ef4444;
            --color-info: #3b82f6;
            --color-skip: #94a3b8;
            --font-heading: '{fonts.heading}', system-ui, -apple-system, sans-serif;
            --font-body: '{fonts.body}', system-ui, -apple-system, sans-serif;
            --container-max: 900px;
            --border-radius: 8px;
        }

        /* Reset & Base */
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
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
            padding: 0 32px;
        }

        /* Report Header */
        .report-header {
            background: var(--color-primary);
            color: #ffffff;
            padding: 40px 0;
        }
        .report-header .container {
            display: flex;
            align-items: center;
            gap: 24px;
        }
        .report-logo {
            width: 64px;
            height: 64px;
            object-fit: contain;
            flex-shrink: 0;
        }
        .report-header h1 {
            font-family: var(--font-heading);
            font-size: 1.5rem;
            font-weight: 700;
            color: #ffffff;
            margin: 0;
        }
        .report-header .tagline {
            font-size: 0.9rem;
            opacity: 0.8;
            margin-top: 4px;
        }

        /* Report Meta Bar */
        .report-meta {
            background: var(--color-bg-alt);
            border-bottom: 1px solid var(--color-border);
            padding: 20px 0;
        }
        .report-meta .container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
        }
        .report-meta h2 {
            font-family: var(--font-heading);
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--color-primary);
            margin: 0;
        }
        .meta-details {
            display: flex;
            gap: 24px;
            font-size: 0.9rem;
            color: var(--color-text-light);
        }
        .meta-details span { white-space: nowrap; }

        /* Typography */
        h2 {
            font-family: var(--font-heading);
            font-size: 1.4rem;
            font-weight: 700;
            color: var(--color-primary);
            margin: 32px 0 16px;
            padding-bottom: 8px;
            border-bottom: 2px solid var(--color-primary);
        }
        h3 {
            font-family: var(--font-heading);
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--color-primary);
            margin: 24px 0 12px;
        }
        p { margin-bottom: 12px; }

        /* Score Badge */
        .score-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            border-radius: var(--border-radius);
            font-weight: 700;
            font-size: 1.1rem;
        }
        .score-badge.excellent { background: #dcfce7; color: #166534; }
        .score-badge.good { background: #dbeafe; color: #1e40af; }
        .score-badge.needs-attention { background: #fef3c7; color: #92400e; }
        .score-badge.critical { background: #fee2e2; color: #991b1b; }

        /* Overall Score Card */
        .overall-score {
            text-align: center;
            padding: 32px;
            margin: 24px 0;
            background: var(--color-bg-alt);
            border-radius: var(--border-radius);
            border: 1px solid var(--color-border);
        }
        .overall-score .score-value {
            font-size: 3rem;
            font-weight: 800;
            font-family: var(--font-heading);
            color: var(--color-primary);
        }
        .overall-score .score-grade {
            font-size: 1.1rem;
            color: var(--color-text-light);
            margin-top: 4px;
        }

        /* Progress Bar */
        .progress-bar {
            width: 100%;
            height: 8px;
            background: var(--color-border);
            border-radius: 4px;
            overflow: hidden;
        }
        .progress-bar .fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s ease;
        }
        .progress-bar .fill.excellent { background: var(--color-success); }
        .progress-bar .fill.good { background: var(--color-info); }
        .progress-bar .fill.needs-attention { background: var(--color-warning); }
        .progress-bar .fill.critical { background: var(--color-danger); }

        /* Tables */
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 16px 0;
            font-size: 0.9rem;
        }
        thead {
            background: var(--color-primary);
            color: #ffffff;
        }
        th {
            padding: 10px 12px;
            text-align: left;
            font-weight: 600;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        td {
            padding: 10px 12px;
            border-bottom: 1px solid var(--color-border);
            vertical-align: top;
        }
        tbody tr:nth-child(even) { background: var(--color-bg-alt); }
        tbody tr:hover { background: #f0f0f0; }

        /* Status Pills */
        .status-pill {
            display: inline-block;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }
        .status-pill.pass { background: #dcfce7; color: #166534; }
        .status-pill.warn { background: #fef3c7; color: #92400e; }
        .status-pill.fail { background: #fee2e2; color: #991b1b; }
        .status-pill.skip { background: #f1f5f9; color: #64748b; }

        /* Critical Issue Card */
        .issue-card {
            border-left: 4px solid var(--color-danger);
            background: #fef2f2;
            padding: 16px 20px;
            border-radius: 0 var(--border-radius) var(--border-radius) 0;
            margin: 12px 0;
        }
        .issue-card.warning {
            border-left-color: var(--color-warning);
            background: #fffbeb;
        }
        .issue-card .issue-id {
            font-weight: 700;
            color: var(--color-danger);
            font-size: 0.85rem;
        }
        .issue-card.warning .issue-id { color: var(--color-warning); }
        .issue-card .issue-title {
            font-weight: 600;
            color: var(--color-text);
            margin-top: 4px;
        }
        .issue-card .issue-impact {
            font-size: 0.9rem;
            color: var(--color-text-light);
            margin-top: 4px;
        }

        /* Module Section */
        .module-section {
            margin: 24px 0;
            padding: 24px;
            background: var(--color-bg);
            border: 1px solid var(--color-border);
            border-radius: var(--border-radius);
        }
        .module-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }
        .module-header h3 {
            margin: 0;
            font-size: 1.1rem;
        }

        /* Verdict Banner (for strategy audit) */
        .verdict-banner {
            text-align: center;
            padding: 20px;
            border-radius: var(--border-radius);
            margin: 24px 0;
            font-size: 1.2rem;
            font-weight: 700;
            font-family: var(--font-heading);
        }
        .verdict-banner.go { background: #dcfce7; color: #166534; border: 2px solid #22c55e; }
        .verdict-banner.conditional { background: #fef3c7; color: #92400e; border: 2px solid #f59e0b; }
        .verdict-banner.no-go { background: #fee2e2; color: #991b1b; border: 2px solid #ef4444; }

        /* Module Scores Grid */
        .scores-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin: 24px 0;
        }
        .score-card {
            padding: 20px;
            border-radius: var(--border-radius);
            border: 1px solid var(--color-border);
            text-align: center;
        }
        .score-card .module-name {
            font-size: 0.85rem;
            color: var(--color-text-light);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }
        .score-card .module-score {
            font-size: 2rem;
            font-weight: 800;
            font-family: var(--font-heading);
        }
        .score-card .module-grade {
            font-size: 0.85rem;
            margin-top: 4px;
        }

        /* Recommendations */
        .recommendations {
            background: var(--color-bg-alt);
            border-radius: var(--border-radius);
            padding: 24px;
            margin: 24px 0;
        }
        .recommendations ol {
            padding-left: 20px;
        }
        .recommendations li {
            padding: 8px 0;
            line-height: 1.5;
        }

        /* Report Footer */
        .report-footer {
            background: var(--color-primary);
            color: rgba(255, 255, 255, 0.8);
            padding: 32px 0;
            margin-top: 48px;
            font-size: 0.85rem;
        }
        .report-footer .container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
        }
        .report-footer .company-name {
            font-weight: 700;
            color: #ffffff;
        }
        .report-footer a {
            color: rgba(255, 255, 255, 0.8);
            text-decoration: none;
        }

        /* Print Styles */
        @media print {
            body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
            .report-header, .report-footer, .score-badge, .status-pill,
            .issue-card, .verdict-banner, .score-card, thead, .overall-score {
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }
            .container { max-width: 100%; padding: 0 16px; }
            .module-section { break-inside: avoid; }
            .issue-card { break-inside: avoid; }
            table { break-inside: avoid; }
            h2, h3 { break-after: avoid; }
            .report-footer { break-before: avoid; }
        }

        /* Responsive */
        @media (max-width: 768px) {
            .container { padding: 0 16px; }
            .report-header .container { flex-direction: column; text-align: center; }
            .report-meta .container { flex-direction: column; text-align: center; }
            .meta-details { justify-content: center; }
            .scores-grid { grid-template-columns: 1fr 1fr; }
            .overall-score .score-value { font-size: 2.5rem; }
            h2 { font-size: 1.2rem; }
            table { font-size: 0.8rem; }
            th, td { padding: 8px; }
        }
    </style>
</head>
<body>

    <!-- HEADER -->
    <header class="report-header">
        <div class="container">
            {logo_img_tag}
            <div>
                <h1>{company_name}</h1>
                <div class="tagline">{company_tagline}</div>
            </div>
        </div>
    </header>

    <!-- REPORT META -->
    <div class="report-meta">
        <div class="container">
            <h2>{report_title}</h2>
            <div class="meta-details">
                <span>Client: <strong>{client_name}</strong></span>
                <span>Date: <strong>{report_date}</strong></span>
                <span>Vertical: <strong>{client_vertical}</strong></span>
            </div>
        </div>
    </div>

    <!-- REPORT BODY -->
    <main class="container">
        {report_body_sections}
    </main>

    <!-- FOOTER -->
    <footer class="report-footer">
        <div class="container">
            <div>
                <span class="company-name">{company_name}</span>
                {company_tagline_footer}
            </div>
            <div>
                <a href="mailto:{company_email}">{company_email}</a>
                {company_website_footer}
            </div>
        </div>
    </footer>

</body>
</html>
```

## Placeholder Reference

| Placeholder | Source | Example |
|-------------|--------|---------|
| `{colors.*}` | `my-brand/brand.json` → colors object | `#1a1a2e` |
| `{fonts.*}` | `my-brand/brand.json` → fonts object | `Inter` |
| `{company_name}` | `my-brand/brand.json` → company.name | `Pitcocy Digital` |
| `{company_tagline}` | `my-brand/brand.json` → company.tagline | `Google Ads That Actually Work` |
| `{company_email}` | `my-brand/brand.json` → company.email | `hello@pitcocy.com` |
| `{report_title}` | From selected audit type(s) | `Account structure audit` |
| `{client_name}` | From business.md or directory name | `Acme Corporation` |
| `{client_vertical}` | From business.md | `SaaS` |
| `{report_date}` | Current date (YYYY-MM-DD) | `2026-03-26` |
| `{logo_img_tag}` | file:// path to logo or empty | `<img src="file:///Users/me/hub/my-brand/logo.png" class="report-logo" alt="Logo">` |
| `{google_fonts_link}` | Google Fonts `<link>` tag if custom font | `<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">` |
| `{report_body_sections}` | Populated from section-*.md templates | (HTML sections) |

## Google Fonts Link

If `fonts.heading` or `fonts.body` is not a system font, include:

```html
<link href="https://fonts.googleapis.com/css2?family={font_name}:wght@400;600;700;800&display=swap" rel="stylesheet">
```

System fonts that do NOT need a Google Fonts link: `system-ui`, `Arial`, `Helvetica`, `Georgia`, `Times New Roman`, `Courier New`, `Verdana`, `Tahoma`.

## Logo

Reference the logo with an absolute `file://` path so the browser loads it when the HTML is opened locally:

```html
<img src="file://{absolute_path_to_logo}" class="report-logo" alt="{company_name} logo">
```

**Examples by OS:**
- macOS/Linux: `file:///Users/me/ppcos-hub/my-brand/logo.png`
- Windows: `file:///C:/Users/me/ppcos-hub/my-brand/logo.png`

The browser renders the logo when the user opens the HTML. Print > Save as PDF captures it in the output.

Do NOT base64-encode the logo — it bloats the HTML and the context window.

If no logo exists, omit the `<img>` tag entirely — the header works fine with text only.

## Score Grade Classes

Use these CSS classes based on the score percentage:

| Score Range | Grade | CSS Class |
|-------------|-------|-----------|
| 90-100% | Excellent | `excellent` |
| 70-89% | Good | `good` |
| 50-69% | Needs attention | `needs-attention` |
| 0-49% | Critical | `critical` |

Apply to: `.score-badge`, `.progress-bar .fill`, `.score-card`
