# Gordon's Wiki — Architecture Notes

**Created:** 2026-05-09
**Updated:** 2026-05-10

## Where the wiki lives
- **Source:** `/opt/data/hermes-pages/gordons-llm-wiki/` — markdown pages
- **HTML output:** `/opt/data/hermes-pages/wiki/` — generated HTML for Cloudflare Pages
- **Pattern:** Passive maintenance — Gordon reads in Obsidian; I file updates during conversations without asking

## Publishing workflow
1. Edit/add markdown in `gordons-llm-wiki/` (entities/, concepts/, projects/, etc.)
2. Run: `python3 scripts/md2html.py gordons-llm-wiki` (from `/opt/data/hermes-pages/`)
3. Copy output: `cp -r /opt/data/hermes-pages-repo/wiki/* wiki/`
4. Deploy directly to Cloudflare Pages via `publish_html` tool — NO GitHub intermediate needed
5. Auto-deploy URL: `https://hermes-pages.rouse-gordon.workers.dev/wiki/`

## md2html.py notes
- Markdown `[[assets/filename.jpg]]` → inline `<img>` tag (styled, lazy-loaded)
- Wiki links `[[page-name]]` → `<a>` links using `WIKI_PATH_MAP`
- Full page refresh every time (no incremental updates needed)

## Key design decisions
1. **Cloudflare direct deploy via wrangler** — the `publish_html` tool writes to `/opt/data/hermes-pages-files/` and runs `wrangler pages deploy`. No GitHub in the loop.
2. **Passive maintenance** — I file relevant info from conversations without prompting. Don't ask "should I add this?"
3. **Obsidian is the frontend** — Gordon browses in Obsidian with graph view + wikilinks
4. **Karpathy LLM Wiki pattern** — layered: raw/ (immutable sources), wiki pages (LLM-owned), SCHEMA.md (conventions)

## Wiki path map (md2html.py)
```
gordon-rouse → entities/gordon-rouse
kla → entities/kla
ventura-relocation → concepts/ventura-relocation
sidekick-studio → projects/sidekick-studio
hobbies/* → hobbies/<name>
log → log
```

## Cloudflare Pages deploy requirements
- `CLOUDFLARE_API_TOKEN` — token with "Cloudflare Pages: Edit" permission
- `CLOUDFLARE_ACCOUNT_ID` — account ID (57b8042d1457f799edfa7595c8a4cebd)
- Node.js v22+ for wrangler (use `n` package: `N_PREFIX=/opt/data/.nvm /opt/data/.npm-global/bin/n 22`)
- Token goes in Railway env vars (NOT hardcoded)

## Cloudflare token invalid? Debug steps
1. `curl -s -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" https://api.cloudflare.com/client/v4/user/tokens/verify`
2. If 401 → token is invalid/expired/rotated. Get fresh one from Cloudflare Dashboard → Profile → API Tokens
3. Update Railway env var with new token value

## GitHub sync (DEPRECATED — don't use)
The old pattern was: edit → git commit → git push to rousegordon-ops/hermes-pages → Cloudflare Pages on push. This is no longer needed. Use the direct deploy above instead. The GitHub repo is now a mirror/backup only.

## Current pages (as of 2026-05-10)
- `entities/gordon-rouse.md` — full career, contacts, targets, constraints
- `entities/kla.md` — current employer, 31-year tenure
- `concepts/ventura-relocation.md` — Bay Area → Ventura move + house photo
- `projects/hermes-agent.md` — Hermes Agent project page
- `raw/` — immutable source material (e.g. karpathy-llm-wiki.md)

## Future pages to file
- Target employer entities: `northrop-grumman.md`, `teledyne.md`, `amgen.md`
- `concepts/career-decision-framework.md` — tradeoffs when discussed
- `hobbies/gordon-rouse-hobbies.md` — hobbies page when created