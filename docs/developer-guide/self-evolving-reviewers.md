# Self-Evolving Reviewers

This document inventories the current Hermes self-learning stack and the shipped Phase 1-4 integration points.

## Phase 1: Current stack inventory

### Hot memory

- Storage: `get_hermes_home()/memories/MEMORY.md` and `get_hermes_home()/memories/USER.md`.
- Implementation: `tools/memory_tool.py`.
- Runtime class: `MemoryStore`.
- Validation boundary: `MemoryStore.add`, `MemoryStore.replace`, `MemoryStore.remove`, and `_scan_memory_content`.
- Prompt injection: `run_agent.py` builds the memory context block when memory/user profile are enabled.

### Procedural memory

- Storage: `get_hermes_home()/skills/**/SKILL.md`, bundled `skills/**/SKILL.md`, optional `optional-skills/**/SKILL.md`, and configured `skills.external_dirs`.
- Listing/loading: `tools/skills_tool.py` and `agent/skill_utils.py`.
- Mutation: `tools/skill_manager_tool.py::skill_manage`.
- Validation boundary: name/category/frontmatter/content-size/path checks plus optional security guard.

### Raw/auditable history

- Storage: `get_hermes_home()/state.db`.
- Implementation: `hermes_state.py::SessionDB`.
- Search surface: `tools/session_search_tool.py` and `session_search` tool.

### Background reviewers

- Trigger/orchestration: `run_agent.py`.
- Memory cadence: `memory.nudge_interval`, default `10` user turns.
- Skill cadence: `skills.creation_nudge_interval`, default `10` tool-loop iterations.
- Reviewer runner: `AIAgent._spawn_background_review`.
- Reviewer prompts: `_MEMORY_REVIEW_PROMPT`, `_SKILL_REVIEW_PROMPT`, `_COMBINED_REVIEW_PROMPT`.
- Mutation path: reviewers must use the same `memory` and `skill_manage` tools as foreground agents.

## Phase 2: Reviewer audit log

Background reviewer lifecycle events are written to:

```text
get_hermes_home()/logs/reviewer_audit.jsonl
```

Implemented in `agent/reviewer_audit.py`.

Events:

- `review.started`
- `review.tool_result`
- `review.completed`
- `review.failed`

The audit writer is best-effort and must never break the main user turn. Content-like fields are hashed and previewed; all string fields pass through Hermes secret redaction before persistence.

## Phase 3: Memory reviewer

The existing background memory reviewer is retained and audited. It runs through normal `AIAgent.run_conversation`, with recursive reviewer nudges disabled, and uses the shared `MemoryStore` plus normal `memory` tool validation.

## Phase 4: Skill reviewer

The existing background skill reviewer is retained and audited. It uses the normal agent tool path and is instructed to inspect existing skills before patching or creating procedural memory. Skill writes continue through `skill_manage` validation and optional guard scanning.
