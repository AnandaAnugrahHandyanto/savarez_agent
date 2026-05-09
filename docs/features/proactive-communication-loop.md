# Proactive Communication Loop

> *"I'd love to see some sort of proactive loop where every night Hermes takes everything
> from the day, synthesizes it, and tries to start finding ways to act or message proactively.
> I'd love to have Hermes message me occasionally on its own. That can't be easy though..."*
>
> — @charlesmcdowell, May 8 2026 · 2.2K views
>
> Teknium replied: *"This is a good idea 🤔"*

---

## What This Is

The **Proactive Communication Loop** gives Hermes a synthesis-and-initiative pass that runs
on a configurable schedule (by default: nightly). After synthesizing the day, Hermes decides
**on its own** whether it has something worth saying — and if so, sends the user a message
**without being asked**.

This is the difference between a tool and a partner. A tool waits. A partner notices.

---

## The Two Modes

### Mode 1: Recency-only synthesis

Hermes reviews the last N hours of conversation history and asks:
*"Did I finish something worth reporting? Is there an unresolved thread that now has an answer?
Did the user ask me to let them know about something?"*

This works well for daily wrap-ups and completed task notifications.

### Mode 2: BartokGraph-augmented synthesis (the powerful one)

When a local model and BartokGraph are available, Hermes goes further. BartokGraph is a
**knowledge graph builder** that maps concepts, projects, people, and ideas from the user's
files and conversation history into a weighted graph with typed edges
(`TEACHES`, `BUILDS_ON`, `CONTRADICTS`, `MENTIONS`, etc.).

With BartokGraph, the synthesis pass can answer:

> *"Does anything from today connect to something the user worked on 3 weeks ago
> that they may have forgotten? Are there cross-domain connections they can't see
> because they can't hold months of context in their head?"*

**Three new message types only BartokGraph enables:**

| Type | Example message |
|------|----------------|
| **Temporal bridge** | "Hey — you worked on this exact problem 3 weeks ago. The approach you used then applies here." |
| **Cross-domain connection** | "Your regime detection work and your soil carbon research share the same underlying structure — both are looking for state transitions in noisy signals." |
| **Person-knowledge bridge** | "Alice mentioned the Kenya soil project last week. You're working on bioavailability today. These connect to Guruji's objective #6 directly." |

Without BartokGraph: Hermes sees a *transcript snippet*.  
With BartokGraph: Hermes sees a *web of weighted, time-stamped knowledge* — and can ask
whether today's work activates a dormant thread.

This is what makes users say **"how did it know that?"**

---

## BartokGraph

BartokGraph is an open-source knowledge graph builder created by the same author.
It is included with this PR as an **optional bundled plugin** (`plugins/bartokgraph/`).

### What BartokGraph does

1. **Scans** a folder (your Hermes workspace, notes, research files) and extracts concepts,
   entities, and relationships.
2. **Builds** a weighted graph where nodes are concepts and edges are typed relationships.
3. **Detects communities** (clusters of related concepts) using topology-based analysis —
   **no embeddings or API calls required**.
4. **Runs locally** using Ollama (default model: `qwen3:8b`) — **zero API cost**.
5. **Supports** any OpenAI-compatible endpoint as an alternative.

### Running BartokGraph standalone

Users who want to explore their knowledge graph without the proactive loop can use it directly:

```bash
# Build a graph from your Hermes workspace
hermes bartokgraph build ~/my-notes

# Query the graph
hermes bartokgraph query ~/my-notes "what connects my AI work to my health goals?"

# Generate a report
hermes bartokgraph report ~/my-notes

# Use a specific local model (default: qwen3:8b via Ollama)
BARTOKGRAPH_LLM_MODEL=gemma2:27b hermes bartokgraph build ~/my-notes

# Use OpenAI or any compatible endpoint
BARTOKGRAPH_API_BASE=https://api.openai.com/v1 \
BARTOKGRAPH_API_KEY=$OPENAI_API_KEY \
BARTOKGRAPH_LLM_MODEL=gpt-4o-mini \
hermes bartokgraph build ~/my-notes
```

### Local model priority

BartokGraph checks for available providers in this order:

1. `BARTOKGRAPH_API_BASE` + `BARTOKGRAPH_API_KEY` + `BARTOKGRAPH_LLM_MODEL` (explicit override)
2. Ollama at `http://localhost:11434` with `BARTOKGRAPH_LLM_MODEL` (default: `qwen3:8b`)
3. LM Studio at `http://localhost:1234` (auto-detected)
4. Any OpenAI-compatible server discovered on common local ports

This means **users with a local LLM already running pay zero API cost** for graph building.

---

## Architecture

```
┌───────────────────────────────────────────────────────────────┐
│              PROACTIVE COMMUNICATION LOOP                      │
│                                                               │
│  Trigger: cron schedule (default: 10pm nightly)               │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  SYNTHESIS PASS                                          │  │
│  │                                                          │  │
│  │  1. Load recent history (last 16h)                       │  │
│  │  2. [Optional] BartokGraph traversal:                    │  │
│  │     - Find today's active topics                         │  │
│  │     - Query graph for dormant related nodes              │  │
│  │     - Detect cross-temporal connections                  │  │
│  │  3. Build synthesis prompt (with or without graph ctx)   │  │
│  │  4. Judge call (cheap/fast local model):                 │  │
│  │     - Score novelty (0-1) + relevance (0-1)              │  │
│  │     - Apply threshold (conservative=0.75 default)        │  │
│  │  5. If above threshold: compose natural message           │  │
│  └─────────────────────────────────────────────────────────┘  │
│                         │                                     │
│                   should_send?                                │
│                    ↓        ↓                                 │
│                  YES        NO                                │
│                   │          │                                │
│            Send message    Silence (prefer silence)           │
│            via configured  Log reasoning                      │
│            channels        to audit trail                     │
└───────────────────────────────────────────────────────────────┘
```

### New files

```
hermes_cli/
├── proactive_communication_loop.py   ← Core engine
└── bartokgraph_adapter.py            ← BartokGraph → Hermes bridge

plugins/bartokgraph/
├── __init__.py                       ← Plugin registration
├── builder.py                        ← Graph construction (Python wrapper)
├── query.py                          ← Graph query interface
├── local_model.py                    ← Local model provider detection
└── cli_commands.py                   ← `hermes bartokgraph` commands

docs/features/
└── proactive-communication-loop.md   ← This document

tests/
├── test_proactive_communication_loop.py
└── test_bartokgraph_adapter.py
```

---

## Privacy and Safety

- **Opt-in by default**: `proactive_communication.enabled = false`
- **Rate limiting**: hard cap of `max_per_day` messages (default: 1)
- **Audit log**: every synthesis pass recorded with reasoning, whether sent or not
- **Kill switch**: `hermes proactive off` immediately stops all future proactive messages
- **BartokGraph privacy**: redacts personal identifiers (phone numbers, email, VIP IDs) before graph storage
- **Local first**: BartokGraph runs entirely on-device with local models — no data leaves the machine
- **No graph = graceful degradation**: if BartokGraph is not installed or has no data, falls back to recency-only synthesis. The loop never fails.

---

## Configuration

```yaml
# ~/.hermes/config.yaml
proactive_communication:
  enabled: false              # opt-in
  schedule: "0 22 * * *"     # 10pm nightly (cron expression)
  threshold: conservative     # conservative | balanced | eager
  max_per_day: 1
  bartokgraph:
    enabled: true             # use graph augmentation when available
    workspace: "~"            # what to graph (default: home dir)
    local_model: qwen3:8b     # model for graph building (Ollama)
    rebuild_interval_days: 7  # how often to rebuild the full graph
```

---

## Message Examples

**Without BartokGraph (recency-only):**
> "Hey — I finished scanning those logs you asked about earlier. Found something:
> errors appear every 4 hours at exactly :15 past. That's almost certainly a cron job.
> Want me to find which one?"

**With BartokGraph (temporal bridge):**
> "Connecting something — you worked on funding rate arbitrage today, and 3 weeks ago
> you designed the HMM regime detector. They're solving the same problem from different
> angles: both are trying to detect which of two stable states the market is in.
> The regime detector could gate the funding arb bot."

**With BartokGraph (cross-domain):**
> "Your soil carbon work and your trading bot regime detection share an interesting structure.
> Both are looking for state transitions in noisy time-series signals.
> The HMM you built for BTC markets could potentially be adapted for soil health monitoring."

---

## What's Left for Follow-up PRs

This PR is the full architecture, engine, BartokGraph plugin, tests, and documentation.
The remaining work to wire it into a running gateway deployment:

1. Gateway cron scheduling hookup (triggers `run_synthesis` at configured time)
2. Per-provider LLM call implementation (wires into session's configured model)
3. Delivery path integration (uses `callbacks.py` notify to send via configured channels)

The scaffolding pattern (ship the engine cleanly, wire it in a follow-up) is how GoalManager
was landed. It keeps this diff reviewable while establishing the complete design.
