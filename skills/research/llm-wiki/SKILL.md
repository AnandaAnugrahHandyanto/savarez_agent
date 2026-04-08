---
name: llm-wiki
description: Build and maintain a persistent, interlinked markdown wiki with Hermes and Obsidian.
---

# LLM Wiki

Use Hermes to maintain a persistent markdown wiki that compounds over time.

This follows Karpathy's "LLM Wiki" idea:
- raw sources stay immutable
- Hermes maintains the compiled wiki
- Obsidian is the human-facing IDE for browsing, linking, and reviewing changes

## Path Resolution

The wiki path resolves in this order:

1. `LLM_WIKI_PATH`
2. `knowledge.wiki_path` in `~/.hermes/config.yaml`
3. Existing legacy `~/hermes-kb`
4. If `OBSIDIAN_VAULT_PATH` is set, `"$OBSIDIAN_VAULT_PATH/Hermes/Wiki"`

Recommended setup:
- Keep the wiki inside the same Obsidian vault as the rest of your Hermes knowledge.
- Let Hermes own the wiki directory.
- Put the wiki under git.

## Architecture

Hermes expects a structure like:

```text
Wiki/
├── SCHEMA.md
├── index.md
├── log.md
├── raw/
│   ├── articles/
│   ├── papers/
│   ├── transcripts/
│   └── assets/
├── entities/
├── concepts/
├── comparisons/
├── queries/
└── articles/
```

### Raw Sources

`raw/` is immutable source material:
- clipped web pages
- PDFs
- transcripts
- locally downloaded assets

Hermes may read from `raw/`, but should not edit raw files.

### Wiki Pages

Hermes writes the wiki pages:
- `entities/` for people, companies, tools, models, products
- `concepts/` for ideas, frameworks, recurring topics
- `comparisons/` for trade-off analyses
- `queries/` for durable answers worth preserving
- `articles/` for synthesis pages and source summaries

### Schema

`SCHEMA.md` is the operating contract.
Update it when the domain or conventions change.

## First Run

Preferred first-run flow:

1. `/wiki init [domain]`
2. `/wiki ingest <url-or-local-file>`
3. `/wiki review`
4. `/wiki map`

If you need low-level control, initialize the wiki directly:

```python
kb(action="init", domain="Your wiki domain here")
```

After initialization:
- inspect `SCHEMA.md`
- refine the domain conventions
- open the wiki in Obsidian

## Core Workflow

### Preferred Command Loop

Use the direct `/wiki` commands when the workflow matches:

- `/wiki init [domain]` to create the wiki
- `/wiki ingest <source>` to capture a source and seed article/entity/concept pages
- `/wiki review` to inspect the latest ingest
- `/wiki map` to see graph state, recent pages, and likely next actions
- `/wiki file-query <question> :: <answer>` to preserve a durable answer
- `/wiki compare <title> :: <option A> => <notes> || <option B> => <notes>` to preserve a tradeoff
- `/wiki entity <title> :: <notes>` to deepen a stable entity node
- `/wiki concept <title> :: <notes>` to deepen a reusable abstract idea
- `/wiki lint` to audit wiki health

Use raw `kb(...)` calls when you need fine-grained edits or custom page construction.

### 1. Ingest

When the user adds a source:

1. Prefer `/wiki ingest <source>` for the standard path
2. Save or locate the raw source in `raw/`
3. Read the relevant existing wiki pages with `kb(search=...)` and `kb(read=...)`
4. Create or update wiki pages with `kb(action="file", ...)`
5. Cross-link related pages with `[[wikilinks]]`
6. Make sure the new page belongs in the right section of `index.md`
7. Report which files were changed

Prefer one source at a time unless the user explicitly wants batching.

### 2. Query

When the user asks a deep question:

1. Start with `kb(action="search", query="...")`
2. Read the most relevant pages
3. Synthesize from the compiled wiki, not only from raw sources
4. If the answer is durable, prefer `/wiki file-query ...` or `/wiki compare ...`

Examples:

```python
kb(action="search", query="mixture of experts routing")
kb(action="file", title="When to use MoE", page_type="query", tags="ml,models,architecture", content="...")
```

### 3. Lint

Run periodic health checks:

```python
kb(action="lint")
```

Use lint to look for:
- orphan pages
- broken wikilinks
- pages missing frontmatter
- pages missing from the index
- stale pages that need review

## Writing Rules

- Always use YAML frontmatter.
- Always use lowercase, hyphenated filenames.
- Prefer updating an existing page over creating a near-duplicate.
- Every page should link to at least one other page when possible.
- Keep pages scannable; move long analysis into dedicated comparison or article pages.
- If a source would touch many existing pages, summarize the proposed scope before doing a broad rewrite.

## Good Page Types

### Entity

Use for a thing with stable identity:
- person
- company
- model
- product
- organization

### Concept

Use for an idea or topic:
- mechanism
- strategy
- framework
- recurring theme

### Comparison

Use when the value comes from trade-offs:
- A vs B
- tool evaluation
- model selection
- architecture choice

### Query

Use when a chat answer is too valuable to lose:
- synthesis
- recommendation memo
- investigation result
- due-diligence note

### Article

Use for broader synthesis:
- source summary
- reading note
- multi-source overview

## Obsidian Workflow

Recommended loop:

1. Keep Obsidian open beside Hermes
2. Let Hermes update files
3. Review graph view and backlinks in Obsidian
4. Follow links to inspect whether the wiki structure still makes sense

Useful Obsidian features:
- internal links / backlinks
- graph view
- properties / YAML frontmatter
- Dataview if you use it

## Tooling Notes

- `kb` is the primary wiki tool
- `/wiki` is the primary workflow layer for common wiki operations
- `knowledge` is the structured fact store for notes/people/projects/decisions
- `obsidian` is the ad hoc note-browsing/editing skill

Use them together:
- `knowledge` for structured personal facts
- `kb` for compiled research and synthesized markdown pages
- Obsidian for browsing, reviewing, and navigating the result
