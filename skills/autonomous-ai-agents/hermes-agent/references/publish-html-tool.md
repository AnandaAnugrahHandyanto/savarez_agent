# publish_html — Cloudflare Pages Direct Deploy

**Purpose:** Tool that writes HTML files locally and deploys them to Cloudflare Pages via wrangler. No GitHub in the loop.

## Quick test
```python
import sys
sys.path.insert(0, '/opt/hermes')
from tools.publish_html import publish_html
result = publish_html(slug='test-page', html_content='<!doctype html><html><body><p>Hello</p></body></html>')
print(result)
```

## Architecture
- Files written to: `/opt/data/hermes-pages-files/` (configurable via `HERMES_PAGES_FILES_DIR`)
- Filename pattern: `{12-char-hash}-{slug}.html`
- Deploy command: `wrangler pages deploy <dir> --project-name <project> --branch main`
- Uses a threading lock so concurrent calls don't fight over wrangler

## Requirements
1. **Cloudflare API token** with "Cloudflare Pages: Edit" permission (`CLOUDFLARE_API_TOKEN`)
2. **Account ID** (`CLOUDFLARE_ACCOUNT_ID` — Gordon's: `57b8042d1457f799edfa7595c8a4cebd`)
3. **Node.js v22+** — wrangler 4.x requires it; Railway container has v20. Fix: `N_PREFIX=/opt/data/.nvm /opt/data/.npm-global/bin/n 22`
4. **wrangler** installed at `/opt/data/.npm-global/bin/wrangler` (auto-installed on first use)

## Token invalid debugging
If deploy fails with "Authentication error [code: 10000]" or API returns 401:
```bash
# Verify token
curl -s -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  https://api.cloudflare.com/client/v4/user/tokens/verify

# If invalid: get new token from Cloudflare Dashboard → Profile → API Tokens
# Then update Railway env var CLOUDFLARE_API_TOKEN
```

## Node.js version fix (Railway container has v20)
```bash
npm install -g n --prefix /opt/data/.npm-global
N_PREFIX=/opt/data/.nvm /opt/data/.npm-global/bin/n 22
export PATH=/opt/data/.nvm/bin:$PATH  # add to PATH before using wrangler
```

## Gordon's config
- Project: `hermes-pages`
- Base URL: `https://hermes-pages.rouse-gordon.workers.dev`
- Branch: `main`