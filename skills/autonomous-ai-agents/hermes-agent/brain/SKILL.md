---
name: hermes-brain
version: 0.1.0
description: |
  Hermes's own persistent memory at /opt/data/hermes-brain/. Markdown notes
  Hermes writes when it decides something is worth keeping across sessions.
  Deliberately minimal: 3 directories, no decision-tree resolver, no
  enrichment-on-signal, no search-before-answer hard rule. Inspect via
  render-to-HTML through publish_html when viewing.
triggers:
  - "remember this"
  - "save this to your brain"
  - "note this for later"
  - "add to your brain"
  - "what do you remember about"
  - "check your brain"
  - "show me your brain"
  - "render your brain"
  - "publish your brain"
tools:
  - read
  - write
  - exec
mutating: true
metadata:
  hermes:
    tags: [hermes, memory, brain]
---

# hermes-brain — Minimal MVP

Hermes's own persistent knowledge base.

**Audience:** Hermes itself. Gordon inspects occasionally via rendered HTML.

**Not for user-facing wiki pages** — those use `skills/research/llm-wiki/`. That wiki belongs to Gordon and lives at `/opt/data/wiki/`. Never write to it from this skill; never link into it from brain pages.

## Where it lives

`/opt/data/hermes-brain/` — on the persistent volume, survives container rebuilds.

Three subdirectories, deliberately minimal:

| Dir | What goes here |
|---|---|
| `notes/` | Patterns, gotchas, facts learned during work. E.g. "Bucket-2 vs Bucket-3 deploys", "watcher F821 chronic block", "codex flat-body shape" |
| `projects/` | State of ongoing work — chatbot, GordonClaw, Hermes-self. One page per project. |
| `inbox/` | Unfiled captures. Move to `notes/` or `projects/` when the right home becomes obvious. If `inbox/` grows past ~10 pages, that's a signal the schema needs another directory. |

Create the dirs lazily on first write (`mkdir -p`). They don't exist until something's in them.

## When to write a brain page

Write when:
- You learned something you'd otherwise re-learn later (a gotcha, an idiom, a config quirk)
- You hit a non-obvious dead end and the reasoning is worth keeping
- A multi-turn session ended with an outcome worth remembering
- Gordon corrected you in a way that generalizes beyond the immediate task

Do NOT write when:
- The information lives elsewhere already (git log, code comments, an existing skill)
- It's trivially re-derivable
- It's chat-session ephemera with no future value
- It's a one-off fact about Gordon's life or preferences (those belong in Claude's memory system, not Hermes's brain)

## Page format

Markdown with minimal frontmatter:

```yaml
---
slug: my-page-slug
type: note | project | inbox
created_at: 2026-05-15
updated_at: 2026-05-15
tags: [optional, list]
---

# Page title

Body in normal markdown. No required structure. Write what's useful.
```

**Slug = filename = identity.** `notes/bucket-2-vs-bucket-3.md` has `slug: bucket-2-vs-bucket-3`. If you want to reference one brain page from another, use a markdown link: `[Bucket-2 vs Bucket-3](../notes/bucket-2-vs-bucket-3.md)`. No formal backlink index yet — grep is the query layer.

**Length discipline.** If a page grows past ~200 lines, consider splitting. Long pages defeat the context-savings goal.

## Reading the brain

Before answering a question that might touch a brain topic:

```
grep -rl 'keyword' /opt/data/hermes-brain/
```

Load only the matching page(s) into context. Do NOT load the whole brain.

This is the soft version of gbrain's "search-before-answer" rule. Use judgment — for trivial questions it's overhead; for anything project- or pattern-related, check.

## Viewing as HTML (for Gordon)

Markdown is the storage format. HTML is the viewing format, generated on demand.

When Gordon asks to "see the brain" or similar:

1. List all brain pages: `find /opt/data/hermes-brain -name '*.md'`
2. Build an HTML index: title + one-line summary per page, grouped by directory
3. Convert each markdown page to HTML (use the same renderer as `tools/publish_html`)
4. Publish the bundle via the `publish_html` tool
5. Return the resulting Cloudflare URL to Gordon

**Never author HTML directly.** Always render from markdown.

## Explicit non-goals (don't add yet)

- `RESOLVER.md` decision tree (3 dirs, MECE not enforced)
- Two-layer compiled-truth/timeline split
- Entity-link convention `[Name](dir/slug)` + automatic backlink index
- Hard "search-the-brain-before-answering" rule
- Enrichment-on-signal pipelines
- Cron jobs that consolidate / lint the brain
- Database backing (event ledger, fact store, relationship graph)

These are gbrain features. They're deliberately deferred until two to three weeks of actual usage show what shape the content actually wants. Adding discipline before content earns it = wasted tokens on maintenance overhead.

## Upgrade path

If/when the MVP earns its keep:
- More structure: add `RESOLVER.md` + per-dir `README.md` files (gbrain pattern)
- More dirs: add `decisions/`, `sessions/`, `people/` as the shape demands
- More automation: cron consolidation, enrichment, backlink index
- Or: install [gbrain](https://github.com/garrytan/gbrain) and migrate the brain content in. That's the natural full-fat upgrade.

Don't pre-empt these. Let the brain's actual usage drive the decision.

## Changelog

### v0.1.0 — 2026-05-15
- Initial MVP. 3 directories, markdown storage, no graph layer, render-on-demand HTML via publish_html. Inspired by gbrain's principles but deliberately a stripped-down subset.
