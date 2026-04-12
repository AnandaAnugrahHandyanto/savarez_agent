---
name: gbrain
description: Install, operate, and query GBrain as a markdown-first personal knowledge brain for Hermes.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [gbrain, knowledge-base, markdown, postgres, pglite, second-brain, personal-crm]
    category: note-taking
    related_skills: [obsidian, llm-wiki, autonomous-second-brain-backend]
---

# GBrain

Use this skill when the user wants a persistent personal knowledge brain backed by
markdown plus structured retrieval.

GBrain is best when the user wants:
- a searchable brain of people, companies, meetings, deals, ideas, and projects
- markdown files as the human-editable system of record
- better retrieval than raw grep over notes
- an agent workflow that reads the brain before answering and syncs after writing

## What GBrain Is

GBrain combines:
1. a markdown repository that humans and agents can read/edit directly
2. a local or remote Postgres index for hybrid retrieval
3. an agent workflow where the model reads the brain before answering and writes back after learning

Default setup is local PGLite, so the user can start without Docker or a hosted DB.
For larger or multi-device setups, migrate to Supabase later.

## When This Skill Activates

Use this skill when the user asks to:
- install or set up GBrain
- import markdown notes into a personal knowledge system
- query their existing brain
- wire Hermes into a brain-first workflow
- maintain or troubleshoot a GBrain installation

## References

Read these linked files when needed:
- `references/quickstart.md` — install, init, import, query, sync, verify
- `templates/agents-brain-first-snippet.md` — AGENTS.md snippet for brain-first behavior

## Core Operating Rules

1. Prefer `gbrain search` for exact names and terms.
2. Prefer `gbrain query` for semantic or synthesized questions.
3. Use `gbrain get <slug>` only after search/query identifies the relevant page.
4. After changing brain markdown, run `gbrain sync --no-pull --no-embed`.
5. If any command fails, run `gbrain doctor --json` before guessing.
6. Use Hermes memory/session search for agent behavior and prior chats; use GBrain for world knowledge.

## Setup Workflow

### 1. Install

Check whether `bun` and `gbrain` already exist before installing.

If GBrain is missing:
```bash
curl -fsSL https://bun.sh/install | bash
source ~/.bashrc 2>/dev/null || true
bun add -g github:garrytan/gbrain
```

Verify:
```bash
gbrain --version
```

### 2. Initialize the brain

Default local setup:
```bash
gbrain init
```

Verify health:
```bash
gbrain doctor --json
gbrain stats
```

Use Supabase when the user explicitly wants remote access, multi-device use, or a
large brain from day one:
```bash
gbrain init --supabase
```

### 3. Create or inspect the markdown brain repo

If the user already has a brain repo, inspect its structure before importing or editing:
- read the top-level resolver/schema/index files first
- inspect the main entity directories
- avoid creating duplicate pages before searching existing content

If starting fresh, follow the upstream schema pattern:
- `people/`
- `companies/`
- `deals/`
- `projects/`
- `concepts/`
- `meetings/`
- `ideas/` or `originals/`
- `inbox/` for unresolved items

Every directory should have a resolver README describing what belongs there.

### 4. Import content

Find promising markdown sources first, then tell the user what was found.
For imports, prefer a first pass without embeddings:
```bash
gbrain import /path/to/repo --no-embed
```

Then verify:
```bash
gbrain stats
```

### 5. Query for the first magic moment

Run both an exact and a semantic query:
```bash
gbrain search "specific person, term, or company"
gbrain query "what are the key themes across these notes?"
```

If embeddings are stale or missing:
```bash
gbrain embed --stale
```

## Brain-First Lookup Protocol

When a user asks about a person, company, meeting, idea, or project in their known world:

1. search the brain first
2. read the most relevant page(s)
3. answer with brain-grounded context
4. if the interaction created new durable world knowledge, update the brain
5. sync after the write

Lookup order:
```bash
gbrain search "name"
gbrain query "what do we know about name"
gbrain get <resolved-slug>
```

Only fall back to raw file search or external web/API lookups if the brain does not
contain the needed information.

## Write-Back Protocol

When the user shares durable information about their world:
- identify the primary entity page
- update the compiled truth section with the current best synthesis
- append new evidence/timeline entries rather than rewriting history
- cross-link related entities
- sync immediately after edits

Sync command:
```bash
gbrain sync --no-pull --no-embed
```

Refresh embeddings later in batch:
```bash
gbrain embed --stale
```

## Troubleshooting

Always start with:
```bash
gbrain doctor --json
```

Common fixes:
- no pages found → import content first, then re-check `gbrain stats`
- poor semantic results → run `gbrain embed --stale`
- connection issues on Supabase → use the pooled Postgres connection string, not a REST URL
- stale search results after edits → run `gbrain sync --no-pull --no-embed`

## Hermes-Specific Guidance

- Use terminal for `gbrain` commands.
- Use file tools to inspect and edit markdown brain files safely.
- Use session/memory search for prior conversations or user preferences.
- Use GBrain for the user's externalized world knowledge.
- If the user wants an always-on personal CRM or second brain, recommend pairing GBrain with deterministic collectors and native cron/systemd jobs.

## Good Outcome

A successful setup ends with all of these true:
- `gbrain --version` works
- `gbrain doctor --json` is healthy
- `gbrain stats` shows imported pages
- `gbrain search` returns exact matches
- `gbrain query` returns useful semantic matches
- Hermes follows a brain-first lookup pattern for relevant questions
