## GBrain brain-first lookup

When answering questions about the user's world (people, companies, meetings, projects, ideas, deals), search GBrain before relying on model recall or external APIs.

Lookup order:
1. `gbrain search "name or exact term"`
2. `gbrain query "what do we know about X"`
3. `gbrain get <slug>` after resolving the relevant page

After editing any brain markdown files, run:
```bash
gbrain sync --no-pull --no-embed
```

Use GBrain for world knowledge.
Use Hermes memory/session search for user preferences and prior conversation state.

If GBrain commands fail, run:
```bash
gbrain doctor --json
```
