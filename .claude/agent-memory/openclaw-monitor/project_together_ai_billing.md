---
name: together-ai-credit-exhausted
description: Together.ai API credit limit hit, blocking all LLM-backed agents on that provider (review_queue_steward, grok_biotech_watch escalation, LLM heartbeat escalation)
metadata:
  type: project
---

Together.ai credit limit exceeded as of approximately 2026-05-08 (grok_biotech_watch last artifact 2026-05-07). review_queue_steward hit 402 on 2026-05-21. LLM escalation in agent_heartbeat_checks.py also rejected.

**Why:** Fleet-wide model migration to `deepseek/deepseek-v4-flash:free` (see [[hermes-model-migration-deepseek]]) was intended, but Together.ai billing limits were hit before/during migration. The agents running on Together.ai (review_queue_steward, grok_biotech_watch in some paths) are blocked.

**How to apply:** When review_queue_steward, grok_biotech_watch, or heartbeat LLM escalation fail with 402, root cause is Together.ai credit — not agent logic. Requires credit top-up at api.together.ai/settings/billing. Agents that route through Anthropic (Claude) or meta-llama via direct invocation are unaffected.
