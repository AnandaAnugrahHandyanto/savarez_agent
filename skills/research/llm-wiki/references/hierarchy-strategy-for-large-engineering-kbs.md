# Hierarchy strategy for large internal engineering knowledge bases

This captures the distinction between prompt-derived wiki hierarchy and a more programmatic graph/community approach, using `nashsu/llm_wiki` as a reference point.

## Current Gordon static/public KB approach

The agent infers and maintains hierarchy semantically:

- root index contains only top-level hubs
- broad domain → hub page
- major bucket/theme → child hub
- specific opportunity/company/source/deep dive → leaf page
- repeated/shared analysis is promoted to an intermediate hub
- parent pages stay concise maps, not dumping grounds
- child pages are linked from parents and back to parents

These are mainly LLM/skill instructions, not a deterministic optimizer.

## What the more programmatic approach adds

`nashsu/llm_wiki`-style systems add encoded infrastructure around the wiki:

- two-stage ingest: analyze first, then generate/update pages
- graph built from `[[wikilinks]]`
- relevance scoring from direct links, source overlap, common neighbors / Adamic-Adar, and type affinity
- Louvain community detection to identify emergent clusters
- persistent ingest queue with retry/cancel/crash recovery
- vector search / embedding layer
- review queue for contradictions, duplicates, missing pages, and suggestions

## Pros of LLM-derived hierarchy

- Better semantic and pedagogical judgment for human-readable KBs.
- Can organize by reader intent, such as onboarding, device physics, design guidance, or business decision-making.
- Flexible when the right structure is domain-specific and not obvious from graph metrics.
- Avoids mechanical clusters that are statistically related but poor as navigation.

## Cons of LLM-derived hierarchy

- Less deterministic and harder to test.
- At hundreds/thousands of pages, local updates can degrade global structure if the agent lacks full context.
- Large refactors are expensive: move pages, preserve URLs, update backlinks, clean duplication.
- Multi-user/team edits need stronger invariants and review gates.

## Pros of programmatic graph/hierarchy signals

- Scales mechanically to large corpora.
- Repeatable metrics for orphan pages, dense clusters, source overlap, stale pages, missing backlinks, duplicate-ish pages.
- Better observability for engineering teams: subsystem clusters, ownership gaps, underlinked docs.
- Useful as a trigger for refactor candidates.

## Cons of programmatic hierarchy

- Graph communities are not automatically good navigation or teaching order.
- Bad links or overly broad sources produce misleading clusters.
- Regenerating hierarchy too aggressively can destabilize familiar navigation.
- Still needs LLM/human naming and curation.

## Recommended architecture for a large engineering team

Use a hybrid:

1. **Programmatic substrate** enforces invariants and computes signals:
   - stable IDs/slugs
   - backlinks
   - source provenance
   - owners/freshness
   - duplicate/orphan/stale detection
   - graph communities
   - max page size / child count warnings
   - redirects for moves
   - review queue
2. **LLM semantic maintainer** uses those signals to:
   - name clusters
   - write summaries
   - decide when a cluster deserves a hub
   - split/merge pages
   - convert raw docs into readable pages
   - explain contradictions
   - propose topology refactors
3. **Human review** is required for disruptive topology changes:
   - move/rename major hubs
   - merge/delete pages
   - re-home many pages
   - regenerate top-level navigation

Small updates, new leaf pages, backlinks, and obvious splits can be automatic.

## Practical rule of thumb

- Curated expert/public KBs: LLM-derived hierarchy is usually best.
- Large, continuously updated internal engineering KBs: programmatic graph + LLM curation is more scalable.
- Do not choose pure graph hierarchy as the reader-facing structure without an LLM/human curation layer.
