# Adding a New Language to Hermes Desktop

## Quick Start

1. Copy the English source file as your template:
   ```bash
   cp src/locales/en.json src/locales/{your-code}.json
   ```

2. Translate the values in your new file. Group by section prefix:
   - `appearance.*` — Settings > Appearance
   - `settings.*` — Settings sidebar
   - `chat.*` — Chat interface
   - `commandCenter.*` — Command center
   - `composer.*` — Message composer
   - `gateway.*` — Gateway settings
   - `model.*` — Model settings & auxiliary tasks
   - `sessions.*` — Sessions list
   - `onboarding.*` — First-run setup
   - `config.*` — Config panel labels & descriptions
   - `mcp.*` / `keys.*` — MCP & API Keys settings
   - `common.*` — Shared labels (Save, Cancel, etc.)
   - `nav.*` — Navigation
   - `tool.*` — Tool output
   - `errors.*` / `updates.*` / `boot.*` — System messages

3. Add your language's self-name to the `language.{code}` entry.

4. Add the same display label to `LANGUAGE_LABELS` in `src/store/i18n.tsx` so
   the language selector can show a friendly name for the new locale.

5. Open a PR with your new `{code}.json` file and the `LANGUAGE_LABELS` update.

## Auto-Discovery

The i18n system uses `import.meta.glob`, so any `.json` file in
`src/locales/` is automatically loaded into the catalog registry.

The language selector still needs a display label in `LANGUAGE_LABELS`
(`src/store/i18n.tsx`). Adding a locale currently requires both the catalog file
and that label entry.

## Translation Guidelines

- Keep `{variable}` placeholders intact (e.g., `{count}`, `{name}`, `{time}`)
- Keep language self-name keys in the language's native script
  (`language.en`, `language.ja`, etc.)
- Do NOT translate provider names in `keys.*` descriptions
- Keep stable identifiers such as provider IDs, model IDs, environment variable
  names, command examples, JSON, logs, and file paths unchanged
- Use natural, conversational tone
- Run locale checks before opening a PR:
  ```bash
  npm run test:ui -- src/locales/locales.test.ts src/store/i18n.test.ts
  ```
- Test the packaged UI when possible: `npm run build && npm run pack`

## Current Status

All locale catalogs are expected to keep key parity with `en.json`. The
`src/locales/locales.test.ts` regression test enforces this for every supported
locale.
