# Public static knowledge bases on Hermes Pages

Use this when Gordon asks for a new LLM wiki / knowledge base to be visible from the Hermes Pages homepage, and does not explicitly ask for the protected personal `/wiki/`.

## Pattern

- Location: `/opt/data/hermes-pages/<topic-kb>/`
- Public URL: `https://hermes-pages-d55.pages.dev/<topic-kb>/`
- Homepage card: add to `/opt/data/hermes-pages/index.html`
- Deploy: `npx -y -p node@22 -p wrangler wrangler pages deploy /opt/data/hermes-pages --project-name hermes-pages --commit-dirty=true`

## Page structure

Create a small linked site rather than a monolith:

- `index.html` — overview, map of pages, one-sentence mental model
- 5–10 topic pages — concise deep dives
- `sources.html` — reading list with source titles and URLs

For technical research topics, good page classes are:

- fundamentals / definitions
- core physics or mechanisms
- reliability / failure modes
- applications / commercial context
- latest research directions
- sources / reading list

## Research workflow

For non-trivial technical topics, run parallel research streams before writing:

1. Fundamentals / device physics / stable concepts
2. Latest research and open questions
3. Applied/commercial context and standards

Then synthesize into the KB. Do not just dump source summaries.

## Verification

Before deploy:

- Count generated pages.
- Scan every local `href` and confirm internal relative links exist.
- Confirm homepage contains `<topic-kb>/`.

After deploy:

- Verify `https://hermes-pages-d55.pages.dev/` contains the homepage card.
- Verify the KB hub and representative child pages return expected content.
- Use browser-like headers (`User-Agent: Mozilla/5.0`) when fetching.

## Style

- High contrast text; avoid dim gray substantive content.
- Sticky side nav works well for compact topic maps.
- Keep source notes readable and separate from synthesized conclusions.
