# Hermes Agent - Claude Code Guide

This file is the Claude Code entry point for this repository. The canonical,
more complete agent/developer guide is `AGENTS.md`; use it as the source of
truth when details differ.

## MANDATORY: Fetch Hermes Context First

**Before doing ANY work in this repo, load fleet context via Hermes MCP.** Do not
rely on cached or stale context from previous sessions.

**Canonical reference:** [Cursor & Hermes](website/docs/user-guide/features/cursor-hermes.md)
(source-of-truth hierarchy, skills-only vs gateway mode, `HERMES_AGENTS_DIR`).

**Cursor rule:** `.cursor/rules/hermes-fleet.mdc` mirrors this checklist.

### Session Start Checklist

Prefer `fleet_context_snapshot()` when available; otherwise run:

1. **`skills_list()`** — discover all custom agents and their SOUL.md files.
   This tells you what agents exist, which have skills documents, and where
   they live on disk.

2. **`agents_list(include_heartbeat=true)`** — load the full agent registry
   with lane assignments, authority levels, status, and live heartbeat data.
   This is how you know which agents are healthy vs. stale.

3. **`learnings_read()`** — read the HOT-tier persistent memory
   (`.learnings/memory.md`). This contains corrections, patterns, and
   operational knowledge the fleet has accumulated. Respect the 100-line cap.

4. **`knowledge_read(artifact="latest_state")`** — load the current knowledge
   layer state. This is the fleet's shared understanding of production status,
   anomalies, and operational context.

5. **`knowledge_read(artifact="held_spec_ledger")`** — check for any held
   specifications that constrain what changes are allowed.

### Before Modifying a Specific Agent

When the task involves a specific agent (e.g. "fix herald", "update bellringer"):

1. **`skills_read(name="<agent_name>")`** — read the agent's SOUL.md. This
   defines the agent's identity, purpose, constraints, and behavioral rules.
   You must understand the SOUL.md before changing anything about the agent.

2. **`agents_get(name="<agent_name>")`** — get the full agent detail including
   registry entry, heartbeat status, and file listing.

3. **`knowledge_read(artifact="contradiction_ledger")`** — check for known
   contradictions or discrepancies that may affect this agent.

### Before Modifying Pipeline or Infrastructure

When the task involves pipeline code, cron, CI, or infrastructure:

1. **`artifacts_list()`** — browse the artifacts directory to understand what
   operational outputs exist and their structure.

2. **`knowledge_read(artifact="operator_brief")`** — read the latest daily
   operator brief for current production status and known issues.

3. **`learnings_read(file="projects/")`** — list project-specific memory files
   for relevant namespace context.

### Why This Matters

The Hermes fleet has 30 agents with custom SOUL.md files, a 5-tier authority
model, 3 execution lanes, and a 4-layer monitoring stack. Changes that ignore
this context risk:

- Breaking agent authority boundaries
- Violating held specifications
- Contradicting fleet learnings
- Introducing regressions into a production pipeline that runs daily

**Read first. Then code.**

---

## Start Here

- Work from the current git branch unless the user asks you to switch.
- Prefer the repo's existing patterns and helper APIs over new abstractions.
- Do not revert unrelated user changes in the working tree.
- Keep edits scoped to the request and the affected subsystem.

## Environment

```bash
source .venv/bin/activate  # or: source venv/bin/activate
```

`scripts/run_tests.sh` is the required test wrapper. It probes `.venv`, `venv`,
and the shared Hermes checkout venv, then runs pytest with CI-like environment
settings.

## Test Commands

```bash
scripts/run_tests.sh
scripts/run_tests.sh tests/gateway/
scripts/run_tests.sh tests/tools/test_delegate.py::TestBlockedTools
.venv/bin/ruff check .
```

Do not call `pytest` directly unless there is no alternative; the wrapper
normalizes credentials, HOME, timezone, locale, and worker count.

## Important Project Invariants

- Profile-aware state paths must use `get_hermes_home()` from
  `hermes_constants`; user-facing path text should use `display_hermes_home()`.
- Tests must not write to a real `~/.hermes/`; use the existing fixtures and set
  `HERMES_HOME` when mocking home directories.
- Prompt caching must not be broken mid-conversation. Slash commands that alter
  tools, skills, memory, or system prompt state should defer invalidation unless
  an explicit `--now` flow exists.
- Built-in tools require both registration in `tools/*.py` and exposure through
  `toolsets.py`.
- Plugin capabilities should use generic plugin hooks/surfaces; do not hardcode
  plugin-specific logic into core files.

## High-Value Files

- `run_agent.py` - `AIAgent`, conversation loop, interrupts, compression.
- `model_tools.py` - tool discovery, schema filtering, function dispatch.
- `toolsets.py` - toolset definitions and platform bundles.
- `cli.py` - classic CLI and slash-command dispatch.
- `gateway/run.py` - messaging gateway runner.
- `hermes_cli/config.py` - default config and config migration.
- `tools/` - built-in tool implementations.
- `plugins/` - plugin systems and bundled plugins.
- `tests/` - pytest suite.

## MCP Server & Skills Integration

The Hermes MCP server (`mcp_serve.py`) runs as a stdio MCP server that Cursor
and Claude Code connect to automatically via `.cursor/mcp.json`. It provides
two tool surfaces:

### Messaging Tools (10 tools)

Conversations, messages, events, approvals across connected platforms:
`conversations_list`, `conversation_get`, `messages_read`,
`attachments_fetch`, `events_poll`, `events_wait`, `messages_send`,
`channels_list`, `permissions_list_open`, `permissions_respond`

### Skills & Knowledge Tools (hermes_skills_mcp.py, 7 tools)

Read-only access to the custom Hermes agent fleet, skills, knowledge layer,
and persistent memory.

| Tool | Purpose |
|------|---------| 
| `skills_list` | List all agent SOUL.md files and repo skills |
| `skills_read` | Read a specific SOUL.md or skill document |
| `agents_list` | List agents with registry data and optional heartbeat |
| `agents_get` | Full agent detail: registry, SOUL.md, heartbeat, files |
| `knowledge_read` | Read knowledge layer artifacts (latest_state, ledgers) |
| `learnings_read` | Read .learnings/ memory files (HOT/WARM/COLD tiers) |
| `artifacts_list` | Browse the artifacts/ directory tree |

**Key paths** (resolved via HERMES_HOME and HERMES_REPO):
- `agents/` - Custom agent directories, each with SOUL.md, HEARTBEAT.md
- `agents/AGENT_REGISTRY.json` - Authoritative agent fleet manifest
- `artifacts/ops/knowledge_layer/` - Knowledge layer state files
- `artifacts/ops/held_spec_ledger/` - Held specification tracking
- `.learnings/memory.md` - HOT-tier persistent memory (100-line cap)
- `skills/` - Upstream OpenClaw skill categories

### Architecture Notes

- `hermes_skills_mcp.py` is a standalone module imported by `mcp_serve.py`
- All tools are **read-only** — no mutation of skills, registry, or artifacts
- Gracefully degrades: if `hermes_skills_mcp` import fails, the messaging
  tools still work (logged at DEBUG level)
- Path resolution uses HERMES_HOME/HERMES_REPO env vars, same as the rest
  of the codebase

## Governance Constraints

**These constraints are active and must not be violated:**

1. **Read-only MCP access.** The skills MCP tools expose Hermes data for
   reading only. Do not attempt to write to `.learnings/`, `artifacts/`,
   `agents/AGENT_REGISTRY.json`, or any knowledge layer file through MCP
   or by circumventing the read-only surface.

2. **No Town-to-Hermes feedback automation.** The Town-Hermes Feedback
   Protocol is FROZEN until after h20d (May 26, 2026). Do not implement
   automated memory sync, contradiction-ledger routing, or `.learnings/`
   write paths. This is a governance decision, not a technical limitation.

3. **Held specifications.** Check the held_spec_ledger before making changes.
   If a specification is held, do not modify the constrained area without
   explicit operator approval.

4. **Authority model.** Respect the 5-tier authority model when modifying
   agent configurations. Most agents are `observe_only` or
   `observe_and_propose`. Only `crt_resolution_watcher` has `mutate_data`.
   No agent has `mutate_config` — that is operator-only.

5. **Lane constraints.** Lane A agents (deterministic) must not depend on
   LLM gateway tokens. Lane B agents use LLM on anomaly only. Lane C
   agents are manual-only, no cron.

## Recent CI/PR Notes

This branch contains audit fixes around:

- subagent blocked-tool enforcement,
- `AIAgent.close()` cleanup of shared terminal/background resources,
- Google Chat plugin platform registration and Pub/Sub handoff,
- setup-provider config resync,
- gateway runtime env reload authority,
- concurrent interrupt test scaffolding.

When touching these areas, rerun the focused tests listed in the PR body before
committing.

---

## Hermes Skills Reference (Town-Sourced)

The following sections are exported from the Town AI skill library for Cursor/Claude Code context.
They encode operational knowledge about the Hermes runtime, LLM configuration, pipeline diagnostics,
daily production operations, and the Town-Hermes feedback protocol.

**These are reference material.** Do not modify production systems based on this content without
explicit operator approval. Respect the governance constraints in the main CLAUDE.md above.

---

## Skill: hermes-runtime

### Session Lifecycle

1. **Config load:** `cli-config.yaml` for model routing, API keys, tool permissions
2. **Skill loading:** SKILL.md files from configured skill directories
3. **Memory load:** `.learnings/memory.md` (HOT tier, <=100 lines), then namespace-specific on demand
4. **Agent bootstrap:** Per-agent `SOUL.md` and `AGENTS.md` configuration
5. **Tool registration:** Based on agent authority level
6. **Session ready**

### Session End

1. Skill creation check (if 5+ tool calls)
2. Memory update to `.learnings/`
3. Artifact output
4. Heartbeat update (`HEARTBEAT.md`)

### Model Routing (May 2026)

| Model Pattern | API Gateway | Notes |
| --- | --- | --- |
| `llama*` | Together AI (OpenAI-compatible) | Primary for all agents |
| `claude*` | Anthropic SDK | Fallback for Claude-specific |
| Previous | OpenRouter | Out of credits 2026-05-13 |

Primary: **Llama 3.3 70B Instruct Turbo** (Together AI)

### Inference Parameters (Llama-optimized)

| Parameter | Value | Rationale |
| --- | --- | --- |
| Temperature | 0.2 | Governance determinism |
| Frequency penalty | 0.1 | Reduce repetition |
| Top_p | 0.95 | Tighter nucleus |
| Repetition penalty | 1.2 | Anti-loop |
| API timeout | 2400s | Together cold start spikes |
| Retry | Exponential backoff | 500ms-8000ms |
| Compression threshold | 0.5 | 131K context window |

### Cron Schedule

| Job | Time (ET) | Frequency |
| --- | --- | --- |
| Daily production pipeline | 5:30 PM | Weekdays |
| @reboot catch-up | On boot | -- |
| Universe maintenance | 10:00 AM | Weekdays |

**Critical:** No cron job may depend on a gateway token (Lane A constraint).

### Authority Levels

| Level | Capability | Holders |
| --- | --- | --- |
| observe_only | Read files, check status | Most monitoring agents |
| observe_and_propose | Read + suggest changes | Analysis agents |
| write_artifacts | Write to artifacts/ | Report generators |
| mutate_data | Write to data/ | Only `crt_resolution_watcher` |
| mutate_config | Modify configuration | No agent (operator only) |

### Execution Lanes

| Lane | Description | LLM Usage | Cron |
| --- | --- | --- | --- |
| A (Deterministic) | Scripts, cron, tests only | None | Yes |
| B (Cheap Monitoring) | File/JSON checks first, LLM on anomaly | Anomaly-triggered | Yes |
| C (High-Token Manual) | Synthesis, audits, refactoring | Full | No (manual only) |

### Monitoring Stack

| Layer | Tool | Purpose |
| --- | --- | --- |
| Heartbeat | `tools/agent_heartbeat_checks.py` | Per-agent health |
| Supervisor | `agents/ops_supervisor/supervisor.py` | Fleet-wide anomaly |
| Post-snapshot | `tools/run_post_snapshot_supervisor.py` | Post-pipeline orchestration |
| Sentinel | `tools/agent_supervisor_sentinel.py` | Final watchdog |

### Anomaly Classification

| Classification | Severity | Meaning |
| --- | --- | --- |
| new | ORANGE | First occurrence |
| carried | YELLOW | Same anomaly seen yesterday |
| resolved | GREEN | Previously seen, now gone |

Terminal agents (e.g., ops_supervisor) are intentionally unsupervised.

### Town-Hermes Bridge (Runtime Side)

```
Hermes job completes
  -> write ledger artifact (repo)
  -> send_operator_event(channel="town", ...)
    -> structured email to djschulz@gmail.com
    -> Town routine triggers on [Hermes] subject prefix
```

Phase A (dry-run, `OPERATOR_DELIVERY_DRY_RUN=1`): Complete.
Phase B (live delivery): Not started.

### Troubleshooting

| Symptom | Likely Cause | First Check |
| --- | --- | --- |
| Agent STALE (no heartbeat > 48h) | Cron missed or crash | `crontab -l`, `together_latency.log` |
| Pipeline timeout | AACT Monday batch or API latency | Check timed-out step |
| Herald DARK | Classification broken or dedupe failed | Check `deduped_{date}.jsonl` |
| CI RED | Test failure or dependency | GitHub Actions, PR status |
| Together API errors | Rate limit or outage | `monitor_together_latency.py` |
| Sleep-cliff miss | Windows host suspended | `data/snapshots/` gap |

---

## Skill: hermes-llm-config

### Key Facts

1. OpenAI is NOT a first-class Hermes provider (no `OPENAI_API_KEY` env var)
2. `OPENAI_BASE_URL` and `LLM_MODEL` env vars removed -- `config.yaml` is single source of truth
3. Secrets in `.env`, settings in `config.yaml`
4. Precedence: CLI args > `~/.hermes/config.yaml` > `~/.hermes/.env` > defaults

### Provider Access Paths

| Path | How |
| --- | --- |
| OpenRouter | `OPENROUTER_API_KEY` in `.env` |
| OpenAI Codex | `hermes model` OAuth device flow |
| Custom Endpoint | Point at `https://api.openai.com/v1` |
| GitHub Copilot | OAuth through Copilot API |

### Recommended config.yaml

```yaml
model:
  provider: openrouter
  default: anthropic/claude-sonnet-4-6

custom_providers:
  - name: openai-direct
    base_url: https://api.openai.com/v1
    key_env: OPENAI_API_KEY

fallback_providers:
  - provider: openrouter
    model: openai/gpt-5.3-codex
```

### Model Recommendations (May 2026)

**Daily coding:** Claude Sonnet 4.6 ($3/$15 per 1M), Qwen 3.6 Plus (~$0.56/hr), GPT-5.3-Codex
**Complex reasoning:** Claude Opus 4.7 ($5/$25), GPT-5.5 (1M context), Gemini 3.1 Pro ($2/$12, 2M context)
**Budget/volume:** GPT-5 Nano ($0.05/M input), Haiku 4.5 ($0.80/M), DeepSeek V3.2 (~$0.09/hr)

### CCFT-Aware Routing

| Code Surface | Minimum Model |
| --- | --- |
| CCFT enforcement, selector, scoring, catalyst | Sonnet 4.6 or Opus 4.7 |
| Walk-forward harness, SHA256 hash flows | Sonnet 4.6 |
| Tests, utility scripts, data ingestion | GPT-5.3-Codex or Sonnet 4.6 |
| Documentation, non-scoring agent code | GPT-5.3-Codex |
| Log summarization, terminal output | Deterministic scripts (no LLM) |

### Mid-Session Switching

```
/model custom:openai-direct:gpt-5.3-codex
/model openrouter:anthropic/claude-sonnet-4-6
/model openrouter:anthropic/claude-opus-4-7
```

### Directory Structure

```
~/.hermes/
  config.yaml     # Settings
  .env            # API keys (chmod 0600)
  auth.json       # OAuth credentials
  SOUL.md         # Agent identity
  memories/       # Persistent memory
  skills/         # Agent-created skills
  cron/           # Scheduled jobs
  sessions/       # Gateway sessions
  logs/           # Logs (secrets auto-redacted)
```

---

## Skill: pipeline-diagnostics

### Triage Priority Order

When multiple agents are down, fix in this order:

1. **hermes-mail bridge** -- if down, no agent can deliver email
2. **Herald Digest** -- highest-value daily signal
3. **Bellringer** -- earnings preview/results
4. **fleet_steward** -- restores health monitoring
5. **Intraday Mover Watch** -- real-time price alerts
6. **grok_biotech_watch** -- XAI API key, often longest outage
7. **Evening forward-shadow** -- watchdog
8. **postmortem memory-write** -- lowest priority

### Herald Dark Diagnosis

```bash
crontab -l | grep herald
tail -50 logs/daily_production_*.log | grep -i herald
python3 run_agent_direct.py --agent herald
python3 run_agent_direct.py --agent herald --skip-preflight
```

Root causes: timeout budget (sequential IR fetch over 341 tickers), hermes-mail bridge down, cron entry missing, preflight gate blocking.

### Bellringer Results Dark

```bash
crontab -l | grep -i bellringer
cat logs/bellringer_results_*.log | tail -50
python3 run_agent_direct.py --agent bellringer_results --date YYYY-MM-DD
```

Key: previews and results are different cron jobs.

### hermes-mail Bridge

```bash
python3 hermes_mail_smoke_test.py
cat ~/.hermes/.env | grep SMTP
```

Fix: regenerate Gmail app password at https://myaccount.google.com/apppasswords

### CI Failure Patterns

| Failure | Root Cause | Fix |
| --- | --- | --- |
| pytest CVE | Security advisory | Upgrade in requirements.txt |
| Agent registry enum | Invalid status values | Change to valid enum in AGENT_REGISTRY.json |
| Ruleset drift test | New source not in allowed list | Add to `test_decision_ruleset.py` |
| Critical F821/F811 | Undefined variables | Fix in source, run flake8 |
| Universe loading: 1 ticker | Stale `ipo_dates.json` | Update `last_price_date` |
| Intraday mover NO_DATA | Poll before snapshot | Shift first poll to after ~10:30 ET |

### Email Signal Verification

```
subject:"Herald" after:2026/05/12
from:djschulz@gmail.com subject:"Bellringer" "biotech earnings" after:2026/05/12
from:djschulz@gmail.com subject:"Bellringer" "results" after:2026/05/12
subject:"Intraday Mover" OR subject:"HIGH alert" after:2026/05/12
subject:"Morning Briefing" after:2026/05/12
```

---

## Skill: screener-ops

### Daily Production Pipeline

**Runner:** `tools/run_daily_production.py` (13-step orchestrator)
**Cron:** 5:30 PM ET weekdays + `@reboot` catch-up
**Timeout:** 6000s (100 min)

Steps: Price refresh -> Cache warm (incl FDA) -> Screen (`--inputs-manifest write`) -> Audit -> Gates -> Manifest + promotion -> Drift report -> Action packet -> Shadow portfolio -> Trade plan -> Portfolio report -> Readiness scorecard -> Ops digest + PIT backfill

**Rule:** Always warm 8-K cache BEFORE running screen.

### Knowledge Layer (Spec 089)

Generator: `tools/build_hermes_knowledge_layer.py`

Four layers: Capture (read-only from specs/artifacts/registry/git/cron) -> Normalize (structured ledgers) -> Reason (drift/contradiction/missed-run) -> Deliver (operator briefs)

Output artifacts:
- `artifacts/ops/knowledge_layer/latest_state.{json,md}`
- `artifacts/ops/held_spec_ledger/latest.{json,md}`
- `artifacts/ops/first_fire_ledger/latest.{json,md}`
- `artifacts/ops/contradiction_ledger/latest.md`
- `artifacts/ops/operator_brief/daily/YYYY-MM-DD.md`

### Agent Fleet (30 total)

- 27 active, 1 suppressed (bioshort_watch), 1 retired (company_news_ingest), 1 shadow (shadow_watch)
- Authority source: `agents/AGENT_REGISTRY.json`
- Only `crt_resolution_watcher` holds `mutate_data`

### Active Ruleset

- ID: `8887576e` (v1.14.0)
- File: `production_data/decision_rulesets/v1.14.0_coinvest_only_selector.json`
- Pinned in: `run_screen.py` AND `run_phase2_snapshot_delta.py` (must stay in sync)
- Architecture freeze: until post-h20d (~2026-05-26)

### Expectation Layer Coverage Gate (Spec 105)

| Field | Required Coverage |
| --- | --- |
| `short_interest_pct` | 0.90 |
| `close_price` | 0.99 |
| `market_cap_mm` | 0.95 |
| `priced_move_pct` | 0.80 |
| `insider_net_buy_value_90d` | 0.30 (diagnostic only) |

Gate hard-fails pipeline at Step 5 if any field below threshold.
Source of truth: `FEATURE_COVERAGE_REQUIREMENTS` (not hardcoded).

### Insider Model Isolation Guard (CRITICAL)

`insider_net_buy_value_90d` must NOT enter the expectation model's `market_features` input.
Guard options: input exclusion (preferred), weight zeroing, or drop guard with logged warning.

### Spec Lifecycle States

DRAFT -> IN PROGRESS -> HELD -> RESOLVED -> CLOSED (or SUPERSEDED/MITIGATED)

### Operational Routing (3 Lanes)

- Lane A: No LLM. Scripts, cron, tests only. No gateway token dependency.
- Lane B: File/JSON checks first. LLM on anomaly only via `run_agent_direct.py`.
- Lane C: Manual sessions. No cron.

---

## Skill: town-hermes-feedback

**Status:** DRAFT / NOT ACTIVE / FROZEN until after h20d (May 26, 2026)

### Current Communication Path

```
Hermes -> email -> Town (Spec 090, operational)
Town -> Hermes (NO FORMAL PATH - operator-mediated only)
```

### What Town Is NOT

- NOT a scheduler or cron controller for Hermes
- NOT a repo mutator or spec approver
- NOT allowed to reactivate suppressed agents (bioshort_watch)
- NOT the authoritative source for any production state
- NOT an automatic feedback channel

### Proposed Channels (Design Only - NOT ACTIVE)

1. **Memory Sync** (Town -> Hermes `.learnings/`): Weekly, selective (100-line cap)
2. **Audit Finding Routing** (Town -> Hermes Knowledge Layer): Via email or manual action
3. **Operator Decision Feedback** (Town -> Hermes Governance): Structured decision records

### Governance Decision (2026-05-22)

FROZEN until after h20d. No Channel 1 memory sync, no `.learnings/` write path,
no contradiction-ledger routing, no automated Town routine export, no cron/agent
activation before h20d.

Allowed before h20d: draft manual templates only.

Post-h20d sequence:
1. Pilot governance decision logging
2. Pilot manual memory sync weekly
3. Only after two clean manual cycles consider Town routine export with operator approval

### Dual Storage Model

- **Town:** `add_memory()` -- operator-facing store
- **Hermes:** `.learnings/` files -- agent-facing store
- Reconciliation: manual, operator-initiated, infrequent (monthly or at milestones)
