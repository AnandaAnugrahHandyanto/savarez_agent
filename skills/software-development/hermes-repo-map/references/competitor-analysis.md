# Hermes repo-map competitor analysis

This note is a quick reference for comparing Hermes repo-understanding work against current external implementations.

## Aider

Observed implementation:
- main file: `aider/repomap.py`
- uses syntax/symbol extraction infrastructure (`tree_sitter`, `grep_ast`, language tag queries)
- persists tag/cache data on disk (`.aider.tags.cache...`)
- keeps in-memory caches for map/tree context reuse
- generates a token-budgeted repo map rather than dumping the full tree

Pattern worth copying into Hermes:
- compact structural summary
- symbol-aware extraction
- explicit token budget
- cached rebuilds instead of rediscovery every turn

Pattern Hermes should avoid copying directly:
- anything that would make a live mutable repo map part of the default prompt for every session
- heavyweight always-refresh behavior that undermines stable prompt-prefix caching

## Roo Code

Observed implementation:
- relevant areas include `src/services/code-index/` and `packages/types/src/codebase-index.ts`
- supports a dedicated code indexing subsystem with configuration, orchestration, and storage/provider abstractions
- appears oriented around heavier indexing/search infrastructure than a lightweight prompt synopsis

Pattern worth copying into Hermes:
- separation of config/state/orchestration
- explicit indexing lifecycle and cache invalidation discipline
- clear distinction between code-index service concerns and prompt/context concerns

Pattern Hermes should avoid copying directly for a first implementation:
- mandatory vector-index infrastructure
- always-on indexing complexity for simple Hermes self-development use cases
- external-service assumptions when a compact local synopsis would solve the immediate problem

## Hermes-specific conclusion

Best first Hermes approach:
- keep repo-map behavior opt-in and task-specific
- package it as a skill for Hermes self-development work
- build a compact architecture map from fixed anchor files plus task-specific hotspots
- use competitor research to improve the workflow, not to justify prompt-cache-hostile defaults

In short:
- Aider is the best reference for compact structural repo maps
- Roo is the best reference for disciplined indexing architecture
- Hermes should start with a lightweight skill-based repo map, not a default always-on system-prompt feature
