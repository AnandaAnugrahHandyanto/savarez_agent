# Public discovery + smoke-test cleanup pattern

Use when an ecommerce portfolio app is being prepared for people to find/use publicly.

## Practical launch-readiness steps

1. Verify the app is live through the same entrypoint users will hit, not only the app container/internal port.
   - Check health, `/api`, public homepage, and key static files through the reverse proxy when present.
   - If static metadata or API route docs changed, rebuild/restart the runtime and re-check the live response.

2. Keep smoke tests realistic but non-polluting.
   - Create an order/request via the public flow to verify customer submission.
   - Verify admin-protected order listing and updates with the admin token.
   - After the test, mark smoke/test orders as cancelled/ignored via the app workflow instead of deleting rows unless the user explicitly approves deletion.
   - Restore any product stock reduced by smoke orders.
   - Archive/remove fake browser/test products from public visibility before final browser verification.

3. Add lightweight discoverability basics before public sharing.
   - Homepage: title, useful meta description, `robots: index, follow`, OpenGraph tags, Twitter card tags, and JSON-LD Store/Product-ish structured data when appropriate.
   - `public/robots.txt`: allow crawling unless the user explicitly wants privacy.
   - After the real public domain is known, add canonical URL, `og:url`, and `sitemap.xml`; do not hardcode fake domains.

4. Verify metadata from the served page, not just source files.
   - Fetch the live homepage to a temp file, then inspect for metadata markers.
   - Avoid piping remote HTTP directly into interpreters; save then parse.

5. Final advice to user should separate app-readiness from discovery channels.
   - App readiness: working contact links, clean product data, verified order/admin flow.
   - Discovery: live domain/subdomain, Search Console, sitemap, links from portfolio/GitHub/LinkedIn/socials, and one concise project post.

## Pitfalls

- Passing unit tests is not enough; old containers can still serve stale code or stale static assets.
- Browser smoke tests can create real DB rows and reduce stock; clean up or neutralize test artifacts before declaring the site ready.
- Adding SEO metadata with placeholder social/domain URLs creates misleading previews. Use relative image paths if domain is unknown, and add absolute canonical/OG URLs only after deployment URL is decided.
- A `robots.txt` file helps crawlers access the site, but it does not submit the site to Google; Search Console and real inbound links are still needed.