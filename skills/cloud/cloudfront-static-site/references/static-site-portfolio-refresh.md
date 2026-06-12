# Static portfolio refresh on S3 + CloudFront + GitHub Actions

Use this when refreshing an existing personal/portfolio static site that is deployed from a GitHub repository to S3 and served through CloudFront.

## Durable workflow

1. Identify the source of truth before editing:
   - Confirm the GitHub repo that deploys the site.
   - Confirm the S3 bucket and CloudFront distribution.
   - Confirm the workflow path, usually `.github/workflows/deploy.yml`.
2. Clone or update the repo locally; do not edit the S3 bucket directly for content that should be controlled by CI.
3. Inspect the existing `index.html`, README, and asset list before replacing content.
4. When rewriting a portfolio, prefer a polished single-page layout with:
   - clear hero positioning and contact CTA
   - proof of real infrastructure in the content, not vague skill claims
   - selected projects tied to deployed systems
   - concise service/contact section
   - responsive CSS and accessible link labels
5. Remove stale claims and mismatches while editing. Examples:
   - remove Docker if the user does not use Docker
   - remove old assistant names or inside jokes from public copy
   - remove stale nested project paths such as `hama/` if they are not part of the portfolio
6. Verify locally before push:
   - serve with `python3 -m http.server <port> --bind 127.0.0.1`
   - open in browser and check console for JS errors
   - use visual inspection/browser vision for above-the-fold layout quality
   - confirm contact links exist and use the right schemes: `mailto:`, `tel:`, and `https://wa.me/` where applicable
   - grep/search for stale terms before commit
   - for theme toggles, click both directions and inspect `data-theme`, button text/ARIA state, and `meta[name="theme-color"]`
7. Commit and push to `main` only after local verification.
8. Watch the GitHub Actions run to completion.
9. Verify production after CI:
   - use a cache-busting URL such as `https://domain/?v=<short-sha>`
   - confirm page title and new headline/content
   - confirm removed terms are absent
   - confirm visitor/API widgets degrade gracefully if unavailable
   - confirm S3 object list contains only intended files/prefixes

## Conversion/contact polish pass

Use this pass after the site is visually acceptable but still weak at turning visitors into clients.

- Add direct contact paths near the hero and again in the contact section: `mailto:` email and WhatsApp are usually stronger for local freelance work than only GitHub/social links.
- For WhatsApp links, use the international number format in the URL, e.g. `https://wa.me/<countrycode><number>?text=<encoded intro>`, while displaying the local-friendly number in text.
- Public phone numbers improve conversion but can attract spam. If the user worries about spam later, keep only a WhatsApp button or contact form instead of visible digits.
- Do not add a parent/father name unless it is part of the user's public business identity or the local market expects it. A concise professional name is usually cleaner on a portfolio.
- Add trust chips near the hero: location, working languages, and service category. These are fast credibility signals without making the page verbose.
- Add a "Services" section written for non-technical clients, not engineers. Examples: website + domain setup, DNS/SSL fixes, AWS hosting, deployment automation, cloud cleanup, handoff documentation.
- Rewrite project cards as outcomes, not just tech stacks: custom domain, HTTPS, locked S3 origin, CI/CD deployment, CloudFront invalidation, serverless visitor counter, etc.
- Keep GitHub as supporting proof, not the primary conversion path. Primary CTAs should be contact-oriented when freelance work is the goal.


- Manual S3 deletion is not enough if the GitHub repo still contains the deleted paths. The next successful sync can re-upload them.
- If a deploy run fails at `Configure AWS Credentials`, check repository secret names/update times, refresh the intended secrets from a known-good local AWS profile without printing secrets, then rerun the failed job.
- Cache invalidation may complete but a browser can still show cached HTML. Use a cache-busting query parameter for verification.
- Avoid `curl` pipelines that may hang when all you need is production verification; browser navigation plus DOM checks is often more robust for live static pages.

## Quality bar for professional portfolio refreshes

- Lead with what the user actually does and can deliver.
- Use the deployed infrastructure itself as evidence: S3, CloudFront, GitHub Actions, API Gateway/Lambda/DynamoDB where relevant.
- Make the primary CTA contact-oriented if the portfolio should bring freelance work.
- Keep copy direct and credible; remove hype, jokes, broken sections, and inconsistent tech claims.
- Verify desktop visually and at least reason about mobile responsiveness before shipping.
