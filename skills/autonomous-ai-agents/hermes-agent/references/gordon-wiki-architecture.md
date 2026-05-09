# Gordon's Wiki — Architecture Notes

**Created:** 2026-05-09

## Where the wiki lives
- **Primary:** `/opt/data/wiki/` — local directory, NOT pushed to any repo automatically
- **Pattern:** Passive maintenance — Gordon reads it in Obsidian, I file updates during conversations without asking

## Key design decisions (2026-05-09)
1. **Not synced to GitHub by default** — Gordon decides if/when to create `rousegordon-ops/wiki` and I push there
2. **Passive maintenance** — I file relevant info from conversations without prompting. Don't ask "should I add this?"
3. **Obsidian is the frontend** — Gordon browses in Obsidian with graph view + wikilinks
4. **Karpathy LLM Wiki pattern** — layered architecture: raw/ (immutable sources), wiki pages (LLM-owned), SCHEMA.md (conventions)

## Current pages
- `entities/gordon-rouse.md` — full career, contacts, targets, constraints
- `entities/kla.md` — current employer, 31-year tenure
- `concepts/ventura-relocation.md` — the Bay Area → Ventura move driving job search
- `raw/articles/karpathy-llm-wiki.md` — the methodology source ingested as reference

## Tag taxonomy (from SCHEMA.md)
- `entity` — people, companies
- `concept` — technical topics, decisions, life events
- `life` — career/life decisions (not heavily used yet)
- `meta` — schema, index, log

## To sync to GitHub later
When Gordon creates `rousegordon-ops/wiki`:
```bash
cd /opt/data/wiki
git init
git add .
git commit -m "Initial wiki commit"
# Then add remote + push
git remote add origin https://github.com/rousegordon-ops/wiki.git
git push -u origin main
```
Or use the GitHub PAT from `/opt/data/.git-credentials` with the authed URL pattern.

## Future pages to file
- Target employer entities: `northrop-grumman.md`, `teledyne.md`, `amgen.md`
- `concepts/career-decision-framework.md` — when we discuss the tradeoffs more
- `hobbies/gordon-rouse-hobbies.md` — when we create the hobbies page
- GitHub link for hobbies page: `github.com/rousegordon-ops`