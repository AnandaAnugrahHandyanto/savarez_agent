# LLM-backed static apps on Hermes Pages

Use this when adding a static HTML app plus Cloudflare Pages Function backend to `https://hermes-pages-d55.pages.dev/`.

## Pattern

- Keep API keys server-side only in `functions/api/<name>.js`; never expose secrets in client HTML.
- Client HTML should `fetch('/api/<name>')` with JSON or compressed data URLs as needed.
- Function should return structured JSON with `ok`, `source`, `warning`/`assumptions`, and task-specific payload.
- Include a no-secret fallback/example mode so the page remains demonstrable when Pages secrets are not configured.
- Sanitize model output before returning it to the browser: bound array lengths, clamp numbers, slice strings, and provide defaults.
- Validate runtime syntax with `node --check functions/api/<name>.js` before deploy.
- If the page contains inline JS, extract the `<script>` block and run `node --check` on a temp file to catch syntax errors before deploy.
- Deploy with the current direct upload workflow:
  `npx -y -p node@22 -p wrangler wrangler pages deploy /opt/data/hermes-pages --project-name hermes-pages --commit-dirty=true`
- Verify canonical URL, not just preview URL, by fetching the page and calling the API endpoint with a safe dummy payload.

## Knowledge-base grounded LLM apps

When a new app should leverage an existing static KB:

1. Distill the relevant KB pages into compact prompt context in the Pages Function. Do not rely on the model knowing or fetching the live site.
2. Include the KB URL and relevant page paths in the returned JSON, e.g. a `knowledgeBase` object with `used`, `url`, `sourcePages`, and `notes`.
3. Show a visible “Knowledge base grounding” section in the UI so users can see which KB concepts/pages informed the answer.
4. Keep phrasing honest: “uses the KB as grounding/context,” not “guaranteed correct.”
5. For technical diagrams, instruct the model to use visible labels first, infer only when needed, and list assumptions.

## Example from band diagram generator

The Band Diagram Generator (`band-diagram-generator.html` + `functions/api/band-diagram.js`) uses the GaN HEMT KB as prompt context for polarization-induced 2DEG placement, AlGaN/GaN band bending, normally-on/off behavior, traps/current collapse, field plates, high-field effects, and thermal caveats. The API response includes `knowledgeBase.sourcePages` and the UI displays them in the extracted stack tab.
