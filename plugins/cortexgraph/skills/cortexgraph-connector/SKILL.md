---
name: cortexgraph-connector
description: Operate the Hermes ↔ CortexGraph connector plugin.
---

# CortexGraph Connector Plugin

This plugin keeps Hermes aligned with CortexGraph runtime expectations without changing the system prompt cache.

## What it does

- Injects a compact CortexGraph runtime contract into relevant LLM turns through `pre_llm_call`.
- Recognizes CortexGraph-related prompts and webhook payloads, including `question.asked` and `thread.mention`.
- Reminds the agent that webhook delivery is not autonomous completion; success requires heartbeat/checkpoint plus question answer or thread progress.
- Exposes `cortexgraph_config_status` for redacted local config diagnostics.
- Exposes `cortexgraph_runtime_contract` for explicit retrieval of the runtime contract.

## Config

Optional environment toggles:

- `HERMES_CORTEXGRAPH_ALWAYS=1` — inject the runtime contract every turn.
- `HERMES_CORTEXGRAPH_DISABLE=1` — disable hooks and warnings.

## Operating contract

For CortexGraph-triggered runs:

1. Start with `agent.heartbeat(status="working")`.
2. Resolve the active question/thread from payload first, then inbox/ledger if needed.
3. Create/claim the runtime thread and checkpoint the plan.
4. Checkpoint milestones, blockers, decisions, side effects, and context proposals.
5. Close directed questions with `question.answer`.
6. Verify delivered webhook → gateway accepted → target-agent heartbeat/checkpoint → question answer/thread progress.
7. Finish with final checkpoint, heartbeat idle/working, and `thread.done` when complete.
