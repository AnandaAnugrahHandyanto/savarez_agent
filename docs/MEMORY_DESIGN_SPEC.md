# Hermes Memory System — Design Spec

**Date:** 2026-04-01
**Status:** Proposal — replacing Memory V2 (3,913 lines) with a right-sized system
**Target:** ~600-800 lines total (engine + tool + extraction)

---

## Executive Summary

The current Memory V2 is over-engineered: knowledge graph, YAKE NLP, session memory templates, embedding cascades, graph traversal, procedure learning — most of which never fires in real usage. The upstream it replaced was 548 lines of flat files. Claude Code (the gold standard) uses markdown files in a directory + a Sonnet sidecar for relevance selection. Cursor uses a `.cursorrules` file. These simple systems work.

**The design principle:** Memory should be a flat, inspectable, human-debuggable notepad with just enough structure to not drown the prompt in noise. Nothing more.

---

## 1. What Does Hermes Actually Need to Remember?

Based on analysis of Claude Code's taxonomy (which was eval-validated) and Hermes' usage patterns:

### Memory Types (4 types, matching Claude Code)

| Type | What | Lifespan | Example |
|------|------|----------|---------|
| **user** | Who the user is: role, expertise, preferences, communication style | Long-lived | "Senior backend dev, prefers terse responses, swears when frustrated" |
| **feedback** | Corrections and confirmations of behavior — what to do/not do | Permanent | "Don't summarize at end of responses" / "Single bundled PR was right call" |
| **project** | Ongoing work context, deadlines, who's doing what | Medium (weeks) | "Merge freeze after 2026-03-05 for mobile release" |
| **reference** | Pointers to external resources | Long-lived | "Pipeline bugs tracked in Linear project INGEST" |

### What NOT to remember (from Claude Code, eval-validated)

- Code patterns, architecture, file paths — derivable from reading the project
- Git history — `git log` is authoritative
- Debugging solutions — the fix is in the code
- Ephemeral task state — dies with the session
- Activity summaries — ask what was *surprising*, save that

### Key insight from Claude Code's memoryTypes.ts

The "What NOT to save" exclusions apply **even when the user explicitly asks**. If they say "save this PR list," the right response is to ask what was non-obvious about it. This prevents activity-log noise that pollutes retrieval.

---

## 2. Storage Architecture

### Flat markdown files in a directory (Claude Code pattern)

```
~/.hermes/memories/
├── MEMORY.md          # The index — always injected into system prompt
├── user-profile.md    # Who the user is
├── feedback-terse.md  # Don't summarize
├── project-freeze.md  # Merge freeze info
└── ref-linear.md      # Where bugs are tracked
```

**Why files, not SQLite:**
- Human-inspectable and editable (open in any editor)
- Git-friendly (can version control memories)
- Debuggable (when memory misbehaves, `cat` the file)
- No migration headaches
- Claude Code chose this over a database — they had the resources to build anything

**Each memory file has YAML frontmatter:**
```markdown
---
type: feedback
created: 2026-04-01
description: User prefers terse responses without trailing summaries
---

Don't add summary paragraphs at the end of responses. User can read the diff.
Why: User explicitly corrected this behavior.
How to apply: After completing any task, stop. Don't recap.
```

### MEMORY.md — The Index

Always loaded into the system prompt. Contains a brief manifest of what memories exist (name + one-line description), so the model knows what's available without reading every file.

```markdown
# Memory Index

## User
- user-profile: Senior backend dev, terse style, experienced with Go/Python

## Feedback  
- feedback-terse: Don't summarize at end of responses
- feedback-bundled-prs: Prefer single bundled PR for refactors

## Project
- project-freeze: Merge freeze 2026-03-05 for mobile release

## Reference
- ref-linear: Pipeline bugs in Linear project INGEST
```

### Size Budget

- **MEMORY.md index:** ~500-1500 chars (always in prompt)
- **Individual memory files:** Read on-demand when relevant
- **Total active memories:** Cap at ~50 files (beyond this, consolidation needed)
- **Per-memory budget:** 200-500 chars each (force concision)

---

## 3. Retrieval Strategy

### Three-tier retrieval (simplest to most expensive)

**Tier 1: Always-on index (free)**
MEMORY.md is always in the system prompt. The model sees what memories exist and can decide whether to read any.

**Tier 2: Explicit tool recall**
The model uses `memory(action="read", name="feedback-terse")` to load a specific memory when it knows it needs it. This is the primary retrieval path.

**Tier 3: Relevance selection (optional, like Claude Code)**
At session start or when context seems relevant, use a cheap sidecar query (auxiliary model) to select which memories to pre-load based on the user's first message. Cap at 5 memories.

### Why NOT embedding search / FTS5 / BM25

For <50 memory files with short descriptions, an LLM reading the index is a better relevance judge than any keyword/embedding search. The model understands *intent*; BM25 matches *tokens*. Claude Code validated this: they use a Sonnet sidecar reading frontmatter descriptions, not vector search.

Embedding search only wins when you have hundreds+ of memories. At that point you have a different problem (you're storing too much).

---

## 4. Memory Lifecycle

### Creation: Explicit + Auto-Extract (two paths, mutually exclusive)

**Path 1: Explicit save (model-initiated)**
The model decides during conversation to save a memory. Uses the memory tool directly.

**Path 2: Auto-extraction (background, post-turn)**
After each completed response, a lightweight extraction check runs:
- Looks at recent messages for correction signals ("don't", "stop", "actually"), confirmation signals ("perfect", "exactly"), or new user facts
- If something worth extracting, writes it to the memory directory
- Skips if the model already wrote memories in this turn (mutual exclusion, from Claude Code)
- Runs every 1-3 turns, not every turn (configurable)

**Extraction prompt (kept simple):**
```
Review the last N messages. Extract any durable facts that should survive this session.

EXISTING MEMORIES (don't duplicate):
{memory index}

ONLY extract:
- User preferences, corrections, or personal details
- Behavioral feedback (what to do / not do)  
- Project context not derivable from code
- External resource pointers

DO NOT extract:
- Task progress or debugging state
- Facts derivable from files or git
- Anything already in existing memories
```

### Aging & Lifecycle

| Type | Lifecycle |
|------|-----------|
| **feedback** | Permanent until explicitly contradicted. Corrections are the most valuable memories. |
| **user** | Long-lived. Update in-place when facts change. |
| **reference** | Long-lived. Remove when resource no longer exists. |
| **project** | Decays naturally. Convert relative dates to absolute on save. After ~30 days, candidate for archival. |

### Consolidation: Simple, Infrequent

Run consolidation only when memory count exceeds threshold (~40 files) OR manually triggered. No 5-gate scheduling system — just a simple check.

Consolidation = ask an LLM to:
1. Merge memories covering the same topic
2. Remove memories contradicted by newer ones  
3. Archive project memories with passed deadlines
4. Ensure total stays under ~50

Output: a list of file operations (merge, delete, update).

---

## 5. Memory Tool Interface

### Single tool, simple actions

```python
memory(
    action: "save" | "read" | "list" | "delete" | "search",
    name: str,          # filename (without .md)
    type: str,          # user | feedback | project | reference
    content: str,       # memory content
    description: str,   # one-line description for the index
    query: str,         # for search action
)
```

**Actions:**
- `save`: Write/update a memory file + update MEMORY.md index
- `read`: Read a specific memory file by name
- `list`: Show the full index (same as MEMORY.md)
- `delete`: Remove a memory file + update index
- `search`: Full-text grep across all memory files (simple substring/regex, no embeddings)

### Migration from V1 flat files

If MEMORY.md / USER.md exist in old format:
1. Parse entries (split by §)
2. Create individual .md files with frontmatter
3. Build new MEMORY.md index
4. Rename old files to .bak

---

## 6. System Prompt Integration

### Injection pattern (session-scoped, cache-friendly)

```python
# At session start, inject memory context as a discrete system message
system_messages = [
    {"role": "system", "content": main_system_prompt},
    {"role": "system", "content": memory_context},  # Separate message
]
```

Memory context structure:
```
═══════════════════════════════════
MEMORY (your persistent notes across conversations)
═══════════════════════════════════

## What you remember
{MEMORY.md index content}

## Pre-loaded memories (relevant to this conversation)
{0-5 full memory files, selected by relevance}

## Memory instructions
- Use memory(action="read", name="...") to load any memory from the index
- Use memory(action="save", ...) to create new memories
- Memories persist across conversations — save facts that should survive
- Don't save code patterns, git history, or task progress
- When recalling a memory that names a file/function, verify it still exists before recommending
```

### Frozen snapshot

Memory context is frozen at session start for prompt cache stability. New memories saved during the session are written to disk but don't change the injected context until next session.

---

## 7. What We're Deliberately NOT Building

| Feature | Why not |
|---------|---------|
| **Knowledge graph** | <50 memories don't need graph traversal. An index + grep is sufficient. |
| **YAKE keyword extraction** | Frontmatter descriptions written by the LLM are better than statistical keywords. |
| **Embedding vectors** | LLM reading descriptions > cosine similarity for this scale. Adds dependency + complexity. |
| **Session memory (9-section template)** | The conversation IS the session memory. No need to maintain parallel state. |
| **Tiered lifecycle (active/archived/consolidated/superseded)** | Just active and deleted. If you need "archived," move to an `archive/` subdirectory. |
| **BM25 scoring + recency decay + strength weighting** | Over-optimization for a <50 item collection. |
| **Procedure learning** | Hermes doesn't repeat complex multi-step procedures enough to justify this. |
| **Entity tracking** | Not a knowledge base. Save the fact you need, not an entity graph. |
| **Near-duplicate detection (cosine > 0.92)** | The extraction prompt already has the index. Just tell it not to duplicate. |
| **Budget enforcement (50 memory / 25 user hard caps)** | Soft cap via consolidation prompt. Hard caps create silent data loss. |

---

## 8. Implementation Estimate

### Files

| File | Lines | Purpose |
|------|------:|---------|
| `tools/memory_store.py` | ~250 | File I/O: read/write/delete .md files, index management |
| `tools/memory_tool.py` | ~150 | Tool interface: save/read/list/delete/search actions |
| `agent/memory_extractor.py` | ~150 | Post-turn extraction hook (background, aux model) |
| **Total** | **~550** | Down from 3,913 |

### Dependencies

- **Zero new dependencies.** File I/O, YAML frontmatter parsing (stdlib or trivial), regex search.
- Aux model for extraction uses existing auxiliary_client infrastructure.

### Config

```yaml
memory:
  enabled: true
  auto_extract: true
  extract_interval: 2        # Extract every N turns
  memory_dir: ~/.hermes/memories/
  max_memories: 50           # Soft cap, triggers consolidation warning
  relevance_select: false    # Optional: use aux model to pre-select memories at session start
```

---

## 9. Design Principles

1. **Inspectable.** A user should be able to `ls ~/.hermes/memories/` and immediately understand everything Hermes remembers. No databases, no binary formats.

2. **Debuggable.** When memory misbehaves, the fix is editing a markdown file, not debugging SQL queries or embedding pipelines.

3. **Concise.** Each memory is 1-3 sentences. The extraction prompt enforces brevity. The model's context window is precious.

4. **Durable where it matters.** Feedback/corrections are permanent. Project context naturally expires. User profile evolves.

5. **Simple enough to explain.** The entire system fits in this document. No knowledge graph, no embedding cascade, no 5-gate scheduler. Just files.

6. **Model-native retrieval.** The LLM reads an index and decides what to load. This beats keyword search for <100 items because the model understands intent, not just tokens.

7. **Backward compatible.** Existing MEMORY.md/USER.md entries are migrated into the new file structure on first run.

---

## 10. Success Criteria

The memory system is working when:
- Hermes remembers user corrections across sessions without being told twice
- Hermes adapts to user communication preferences (terse vs detailed)
- Project context from last week is available without re-explaining
- Memory doesn't pollute the prompt with stale/irrelevant facts
- A user can manually edit memories when the system gets it wrong
- The entire system can be understood by reading ~550 lines of Python

---

## Appendix: Lessons From Existing Systems

### Claude Code (production, eval-validated)
- **Storage:** Markdown files in `~/.claude/projects/<path>/memory/`
- **Index:** MEMORY.md always in system prompt
- **Retrieval:** Sonnet sidecar reads frontmatter descriptions, selects top 5
- **Extraction:** Forked agent post-turn, mutual exclusion with main agent writes
- **Types:** user, feedback, project, reference (eval-validated taxonomy)
- **Key insight:** "What NOT to save" is as important as "what to save"

### Cursor
- **Storage:** `.cursorrules` file (project-level instructions)
- **No persistent memory across sessions** — rules are static
- **Key insight:** Project-level context files that humans maintain work great

### HiveMind/MAGMA (our prior art)
- **Storage:** SQLite + FTS5 + optional embeddings
- **Features:** Knowledge graph, YAKE keywords, tiered lifecycle, power-law decay
- **Key insight:** Most of this complexity was never exercised. The graph was empty. YAKE keywords weren't used for retrieval. Embeddings were optional and usually off.

### Paperclip's Memory Landscape Survey
- **Finding:** All systems converge on: ingest, query, scope, provenance, maintenance, context assembly
- **Key insight:** "The smallest contract that can sit above different memory systems" — for Hermes, we don't need the abstraction layer. We're one system for one user.

### The Upstream (548 lines)
- **Storage:** Two flat files (MEMORY.md, USER.md) with § delimiters
- **Cap:** ~3.5KB total
- **Search:** None (substring match only)
- **Key insight:** This worked! Users were productive with it. The limitation was the hard cap and lack of search, not the simplicity.
