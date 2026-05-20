---
name: agent-brain-protocol
description: "Use when designing, configuring, or changing Hermes memory/brain systems: temporal graph memory, semantic facts, procedural skills, knowledge RAG, and human-readable mirrors."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [memory, brain, graphiti, zep, mem0, rag, skills, protocol]
    related_skills: [methodology-router, hermes-agent, native-mcp, obsidian]
---

# Agent Brain Protocol

## Overview

A serious agent brain is not a dump of chat logs. It is a layered memory system with clear write policies, retrieval policies, provenance, and cleanup.

Use this skill when changing Hermes memory, adding a memory provider, designing project knowledge, or deciding what should become a skill versus durable memory.

## When to Use

Use when:
- Configuring memory providers such as Graphiti/Zep, Mem0, Honcho, Hindsight, Holographic, or similar.
- Designing local-first memory with Ollama embeddings or graph storage.
- Adding project brain artifacts under `.hermes/`.
- Deciding whether a fact belongs in memory, a skill, a spec, or session history.
- Integrating RAG/knowledge systems such as Cognee, LightRAG, GraphRAG, or Obsidian.

Don't use for:
- Temporary task progress.
- One-off summaries that will be stale soon.
- Secrets, raw credentials, or sensitive data without explicit user approval and storage policy.

## Memory Layers

### Layer 0 — Working Memory

Current conversation, active tool results, and temporary scratchpad.

Storage:
- Model context.
- `todo` tool.
- Current session state.

Write policy:
- Do not persist by default.
- Summarize only if it creates durable value.

### Layer 1 — Episodic Memory

Timestamped events and interactions.

Examples:
- Conversation episodes.
- Tool execution summaries.
- Delegation outcomes.
- Major project decisions with time context.

Recommended backend:
- Graphiti/Zep temporal episodes.
- Session database remains the source for raw transcripts.

Write policy:
- Store concise event summaries, not full noisy logs.
- Include source, timestamp, actor, project/session scope.

### Layer 2 — Semantic Memory

Stable facts.

Examples:
- User preferences.
- Environment facts likely to remain true.
- Project conventions.
- Architecture decisions.
- API quirks.

Recommended backend:
- Graphiti/Zep entity nodes and edges.
- Mem0 if using a simpler memory layer.
- Built-in Hermes memory for compact high-value facts.

Write policy:
- Store declarative facts, not commands to the assistant.
- Avoid facts likely to become stale within a week.
- Include confidence/provenance when supported.

### Layer 3 — Procedural Memory

Reusable workflows.

Examples:
- How to debug a specific class of failures.
- How to deploy a project.
- How to perform a recurring review.

Recommended backend:
- Hermes skills, not normal memory.
- Skill metadata can be referenced by graph memory, but the procedure itself belongs in `SKILL.md`.

Write policy:
- Create or patch a skill after a difficult/iterative workflow succeeds.
- Keep procedures actionable: triggers, steps, commands, pitfalls, verification.

### Layer 4 — Knowledge Memory

Documents, codebases, APIs, PDFs, websites, and skill catalogs.

Recommended backend:
- Cognee, LightRAG, GraphRAG, or another corpus RAG system.
- Keep separate from user/personal memory.

Write policy:
- Index documents by source and version.
- Do not mix large document chunks into personal memory.
- Prefer citations/file paths in retrieval output.

### Layer 5 — Reflective / Consolidation Memory

Background maintenance that improves memory quality.

Examples:
- Deduplication.
- Conflict detection.
- Confidence updates.
- Stale fact review.
- Link/backlink creation.
- Skill suggestions after repeated patterns.

Recommended inspiration:
- A-MEM / Zettelkasten-style linked notes.
- LangMem-style background managers.
- Graphiti/Zep temporal invalidation.

Write policy:
- Consolidation jobs should be conservative.
- Never silently overwrite explicit user preferences without evidence.

## Recommended Hermes Brain Stack

### Local-First Default

Use when privacy/control matters:

- **Graph backend:** Graphiti with local Kuzu database.
- **Embeddings:** Ollama local embedding model, preferably GPU-loaded.
- **LLM extraction:** OpenRouter allowed when the user permits cloud LLM calls.
- **Knowledge corpus:** local Cognee/LightRAG later if needed.
- **Mirror:** optional Obsidian/Markdown export for auditability.

### Cloud-Pragmatic Default

Use when setup speed and managed reliability matter:

- **Memory:** Zep Cloud or Mem0 Cloud.
- **Embeddings/LLM:** managed provider.
- **Mirror:** optional Markdown export.

### Hybrid Default

Use for most power users:

- Local embeddings and graph storage for private/project memory.
- Cloud LLM for high-quality extraction/reasoning.
- Separate local RAG for large docs/code.

## Write Decision Tree

Before saving anything, ask:

1. **Will this still matter later?** If no, keep it in session only.
2. **Is it a stable fact?** If yes, semantic memory.
3. **Is it an event with time/order?** If yes, episodic memory.
4. **Is it a reusable procedure?** If yes, skill.
5. **Is it external/document knowledge?** If yes, knowledge RAG.
6. **Is it sensitive?** If yes, require explicit policy and avoid logs.

## Retrieval Policy

- Retrieve narrowly by task, project, user, and timeframe.
- Prefer graph/semantic results for decisions.
- Prefer session search for exact previous conversation details.
- Prefer knowledge RAG for docs/code/API facts.
- Keep injected memory compact; long memory blocks degrade reasoning.

## Hermes Integration Points

Least invasive order:

1. **Skills:** add or patch `SKILL.md` for reusable workflows.
2. **Config:** set `memory.provider`, MCP servers, or skill external dirs.
3. **User-installed memory plugin:** `$HERMES_HOME/plugins/<provider>/` implementing `MemoryProvider`.
4. **MCP server:** expose external memory or RAG tools through `mcp_servers`.
5. **Core changes:** only when the provider lifecycle or prompt assembly truly needs new primitives.

For Hermes memory providers:

- Implement `MemoryProvider`.
- Keep `is_available()` cheap and non-networked.
- Use `initialize()` for connections/resources.
- Use non-blocking `sync_turn()`.
- Use `queue_prefetch()` and `prefetch()` for compact recall.
- Expose only high-value tools to avoid schema bloat.

## Common Pitfalls

1. **Vector dump brain.** Embeddings alone are not memory governance.
2. **Mixing layers.** User preferences, repo docs, and task logs need different stores.
3. **Overwriting user truth.** Temporal memory should preserve changes over time, not hide conflicts.
4. **No provenance.** Memories without source/time are harder to trust.
5. **No deletion path.** Users need a way to remove wrong or sensitive memory.
6. **Saving stale artifacts.** PR numbers, commit SHAs, and issue status usually do not belong in durable memory.

## Verification Checklist

- [ ] Memory layers are separated.
- [ ] Backend choice matches privacy/budget/latency requirements.
- [ ] Embedding and graph storage are configured without exposing secrets.
- [ ] Retrieval output is compact and scoped.
- [ ] Write policy prevents stale/noisy memory.
- [ ] User can inspect, correct, or disable the system.
