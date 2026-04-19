---
name: cognition-retention
description: >
  Connect Hermes to a Cognition server to track what you learn, predict what you'll forget,
  and get proactive review nudges — turning every conversation into a learning event with
  Weibull forgetting curves and spectral retention modeling.
version: 1.0.0
author: Keshav Saxena (Cognition)
license: MIT
metadata:
  hermes:
    tags: [Productivity, Learning, Memory, Retention, Spaced-Repetition, Cognition]
    related_skills: [note-taking, research-paper-writing]
---

# Cognition Retention

Track what you learn across Hermes sessions, predict what you'll forget, and get proactive review nudges — powered by [Cognition](https://cognitionus.com)'s operator-theoretic retention model.

Unlike a notebook or bookmark, Cognition doesn't just *store* what you learned — it models *how fast you're forgetting it* using Weibull forgetting curves calibrated to your personal review history, and tells you exactly when to revisit.

## Setup

1. Get a Cognition API key at [cognitionus.com/clo/developers/claude-code](https://cognitionus.com/clo/developers/claude-code)
2. Set your key:
   ```bash
   hermes config set cognition_api_key cog_me_YOUR_KEY_HERE
   ```
3. Optionally set your Cognition server URL (defaults to production):
   ```bash
   hermes config set cognition_url https://www.cognitionus.com/api/integrations/claude-code/mcp
   ```

## What It Does

### Silent concept logging
Every time you work on something with Hermes — debugging code, reading a paper, learning a new tool — Cognition silently logs the concept with an inferred mastery score. No manual tagging needed.

### Session-start briefing
At the start of each session, fetch your retention state:
```bash
python scripts/cognition_briefing.py
```
Returns your weakest concepts, what's due for review, and what your teammates recently learned.

### Review nudges
Check what you're about to forget:
```bash
python scripts/cognition_review.py
```
Returns the top concepts decaying fastest, ranked by urgency, with optimal review timing.

### Log a learning event
After completing a task:
```bash
python scripts/cognition_log.py "react-server-components" --topic "React" --score 0.85 --weight active
```

### Batch log from a session
```bash
python scripts/cognition_batch.py session_concepts.json
```

### Brain health dashboard
```bash
python scripts/cognition_brain.py
```
Full retention report: overall score, weak topics, due-for-review, teammate signals.

## How It Works

Cognition models your memory using the **Weibull forgetting curve**:

```
R(t) = exp(-(t/S)^β)
```

where `S` (stability) is derived from the **spectral gap** of your personal knowledge graph's Laplacian — not a global average, but a quantity computed from how *your* concepts connect to each other. Concepts that are well-connected to things you already know decay slower; isolated concepts decay faster.

The system predicts `R(t)` for every concept you've logged, and when `R` drops below a threshold (default 0.6), it flags the concept for review.

## Integration with Hermes Memory

Cognition complements Hermes' built-in memory system:

| Hermes memory | Cognition |
|---|---|
| Stores what you said | Models how fast you're forgetting it |
| FTS5 keyword search | Ranked by predicted decay (most-at-risk first) |
| Session-scoped recall | Cross-session retention curves |
| Static storage | Dynamic: concepts strengthen with practice, weaken with time |

## API Reference

All scripts call the Cognition MCP server. Key endpoints:

| Script | Cognition tool | Purpose |
|---|---|---|
| `cognition_briefing.py` | `get_session_context` | Retention state + weak concepts + teammate nudges |
| `cognition_review.py` | `suggest_review` | Top concepts to review, ranked by urgency |
| `cognition_log.py` | `log_learning` | Record a learning event |
| `cognition_batch.py` | `log_learning_batch` | Batch ingest up to 200 events |
| `cognition_brain.py` | `get_user_retention` + `get_weak_topics` | Full brain health report |

## Practice Weights

When logging, specify how strong the learning signal is:

| Weight | Multiplier | When to use |
|---|---|---|
| `active` | 1.0× | Wrote code using the concept, debugged it, explained it |
| `passive` | 0.5× | Read docs, skimmed a tutorial |
| `reference` | 0.2× | Glanced at an index, bulk-imported a vault |

## Privacy

- Cognition stores concept IDs, labels, topics, and short excerpts (≤4000 chars)
- Never sends full file contents, message bodies, or credentials
- All data is scoped to your API key and org
- You can delete any concept via the Cognition dashboard

## Notes

- No dependencies beyond Python stdlib + `urllib`
- Works with any Cognition-compatible server (self-hosted or cloud)
- Concepts logged from Hermes appear in your Cognition dashboard alongside concepts from Claude Code, Notion, Obsidian, and other integrations
- The same brain, accessible from every tool
