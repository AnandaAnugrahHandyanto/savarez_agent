---
sidebar_position: 16
title: "Persistent Goals"
description: "Set a standing goal and let Hermes keep working across turns until it's done. Our take on the Ralph loop, with enforcement."
---

# Persistent Goals (`/goal`)

`/goal` gives Hermes a standing objective that survives across turns. After every turn, a staged evaluation pipeline checks whether the goal is satisfied. If not, Hermes automatically feeds a continuation prompt back into the same session and keeps working — with enforcement to prevent loops, detect regression, and verify completion.

It's our take on the **Ralph loop**, directly inspired by [Codex CLI 0.128.0's `/goal`](https://github.com/openai/codex) by Eric Traut (OpenAI). The core idea — keep a goal alive across turns and don't stop until it's achieved — is theirs. The implementation here is independent and adapted to Hermes' architecture.

## When to use it

Use `/goal` for tasks where you want Hermes to iterate on its own without you re-prompting every turn:

- "Fix every lint error in `src/` and verify `ruff check` passes"
- "Port feature X from repo Y, including tests, and get CI green"
- "Investigate why session IDs sometimes drift on mid-run compression and write up a report"
- "Build a small CLI to rename files by their EXIF dates, then test it against the photos/ folder"

Tasks where the agent does one turn and stops don't need `/goal`. Tasks where *you'd otherwise have to say "keep going" three times* are where this shines.

## Quick start

```
/goal Fix every failing test in tests/hermes_cli/ and make sure scripts/run_tests.sh passes for that directory
```

What you'll see:

1. **Goal accepted** — `⊙ Goal set (N-turn budget): <your goal>`
2. **Turn 1 runs** — Hermes starts working as if you'd sent the goal as a normal message.
3. **Evaluation runs** — after the turn, the system checks for loops, evaluates progress, and scores completion.
4. **Loop fires if needed** — if the goal isn't done, you'll see the verdict and Hermes takes the next step automatically.
5. **Terminates** — eventually you see either `✓ Goal achieved` or `⏸ Goal paused — N/N turns used`.

## Commands

| Command | What it does |
|---|---|
| `/goal <text>` | Set (or replace) the standing goal. Kicks off the first turn immediately so you don't need to send a separate message. |
| `/goal` or `/goal status` | Show the current goal, its status, and turns used. |
| `/goal pause` | Stop the auto-continuation loop without clearing the goal. |
| `/goal resume` | Resume the loop (resets the turn counter back to zero). |
| `/goal clear` | Drop the goal entirely. |

Works identically on the CLI and every gateway platform (Telegram, Discord, Slack, Matrix, Signal, WhatsApp, SMS, iMessage, Webhook, API server, and the web dashboard).

## How it works

### The evaluation pipeline

After each turn, the system runs a three-stage pipeline:

1. **Pre-processing (deterministic):** Checks for semantic loops (repeating the same intent), exact loops (same command), error patterns, and score regression across turns. These are computed, not guessed — they don't use the LLM judge.

2. **LLM judge:** An auxiliary model scores completion (0-1), progress signal (forward/stalled/looping/regressing), and quality (0-1). The judge can also suggest pivots, refine actions, and negative constraints (what NOT to do).

3. **Post-processing (enforcement):** If pre-processing detected loops or regression, the system **overrides** the judge's verdict and forces a pivot. If completion was scored high but no artifacts are verified, the score is capped and the agent must verify first. A goal marked "done" requires: completion ≥ 0.91, quality ≥ 0.70, at least one verified artifact, and explicit confirmation from the agent.

### Completion bands

The judge uses calibrated scoring with concrete examples:

| Band | Meaning | Example |
|------|---------|---------|
| 0.00-0.15 | Nothing produced | "I'll start by looking at the code" |
| 0.16-0.35 | Scaffolding exists | Skeleton file created, plans written |
| 0.36-0.55 | Partial work | Core logic exists, incomplete |
| 0.56-0.75 | Mostly done | Main deliverable exists, no verification |
| 0.76-0.90 | Complete but unverified | Everything written, nothing confirmed |
| 0.91-1.00 | Verified complete | Tests pass, files confirmed to exist |

### Loop detection

The system detects loops two ways:

- **Exact:** Same tool + same arguments called 2+ times → forced pivot
- **Semantic:** Same INTENT repeated 3+ times (e.g., three different install commands) → forced pivot

When a loop is detected, the system automatically adds a negative constraint ("DO NOT retry this pattern") that persists across all future turns of the goal.

### Budget

The turn budget is estimated from goal complexity (5-200 turns). It auto-extends by 25% when you're ≥50% complete and making forward progress. If progress stalls, the goal pauses before burning the full budget.

Set an explicit budget with `/goal <text> max_turns=N`.

### Fail-open semantics

If the judge errors (network blip, malformed response, unavailable aux client), Hermes treats the verdict as "continue" — a broken judge never wedges progress. The turn budget and pre-processing loops are the real backstops.

### User messages always preempt

Any real message you send while a goal is active takes priority over the continuation loop. On the CLI your message lands in `_pending_input` ahead of the queued continuation; on the gateway it goes through the adapter FIFO the same way. The evaluation pipeline runs again after your turn — so if your message happens to complete the goal, the judge will catch it and stop.

### Mid-run safety (gateway)

While an agent is already running, `/goal status`, `/goal pause`, and `/goal clear` are safe to run — they only touch control-plane state and don't interrupt the current turn. Setting a **new** goal mid-run (`/goal <new text>`) is rejected with a message telling you to `/stop` first, so the old continuation can't race the new one.

### Persistence

Goal state lives in `SessionDB.state_meta` keyed by `goal:<session_id>`. That means `/resume` picks up right where you left off — set a goal, close your laptop, come back tomorrow, `/resume`, and the goal is still standing exactly as you left it (active, paused, or done). The scratchpad (sub-tasks, artifacts, constraints, error history) persists alongside.

### Prompt cache

The continuation prompt is a plain user-role message appended to history. It does **not** mutate the system prompt, swap toolsets, or touch the conversation in any way that invalidates Hermes' prompt cache. Running a 20-turn goal costs the same cache-wise as 20 turns of normal conversation.

## Configuration

Add to `~/.hermes/config.yaml`:

```yaml
goals:
  # Max continuation turns before Hermes auto-pauses and asks you to
  # /goal resume. Default 20 in stock mode; enforced mode uses adaptive
  # budget (5-200) unless explicit max_turns is set.
  max_turns: 20
```

### Choosing the judge model

The judge uses the `goal_judge` auxiliary task. By default it resolves to your main model (see [Auxiliary Models](/docs/user-guide/configuration#auxiliary-models)). If you want to route the judge to a cheap fast model to keep costs down, add an override:

```yaml
auxiliary:
  goal_judge:
    provider: openrouter
    model: google/gemini-3-flash-preview
```

The judge call is small (~400 output tokens) and runs once per turn, so a cheap fast model is usually the right call.

## Example walkthrough

```
You: /goal Create four files /tmp/note_{1..4}.txt, one per turn, each containing its number as text

  ⊙ Goal set (20-turn budget): Create four files /tmp/note_{1..4}.txt, one per turn, each containing its number as text

Hermes: Creating /tmp/note_1.txt now.
  💻 echo "1" > /tmp/note_1.txt   (0.1s)
  I've created /tmp/note_1.txt with the content "1". I'll continue with the remaining files on the next turn.

  → Continue toward goal (1/20): 1 of 4 files created

Hermes: [→ Continue toward goal]
  💻 echo "2" > /tmp/note_2.txt   (0.1s)
  Created /tmp/note_2.txt. Two more to go.

  → Continue toward goal (2/20): 2 of 4 files created

Hermes: [→ Continue toward goal]
  💻 echo "3" > /tmp/note_3.txt   (0.1s)
  Created /tmp/note_3.txt.

  → Continue toward goal (3/20): 3 of 4 files created

Hermes: [→ Continue toward goal]
  💻 echo "4" > /tmp/note_4.txt   (0.1s)
  All four files have been created: /tmp/note_1.txt through /tmp/note_4.txt, each containing its number.

  ✓ Goal achieved: All four files created and verified.

You: _
```

Four turns, one `/goal` invocation, zero "keep going" prompts from you.

## When things go wrong

Two failure modes to watch for:

**False negative — system says continue when the goal is actually done.** The turn budget catches this. You'll see `⏸ Goal paused` and can `/goal clear` or just send a new message.

**False positive — system says done when work remains.** Rare due to the verification gate. If you see `✓ Goal achieved` but know better, send a follow-up message to continue, or re-set the goal more precisely: `/goal <more specific text>`.

If you find a verdict unconvincing, the reason text in the verdict line tells you exactly what was evaluated. That's usually enough to diagnose whether the goal text was ambiguous or the agent's response was insufficient.

## Attribution

`/goal` is Hermes' take on the **Ralph loop** pattern. The user-facing design — keep a goal alive across turns, don't stop until it's achieved, with create/pause/resume/clear controls — was popularised and shipped in [Codex CLI 0.128.0](https://github.com/openai/codex) by Eric Traut on OpenAI's Codex team. Our implementation is independent (central `CommandDef` registry, `SessionDB.state_meta` persistence, auxiliary-client judge, adapter-FIFO continuation on the gateway side) but the idea is theirs. Credit where credit's due.

The enforcement layer (pre-processing, hard pivot override, verification gate, semantic loop detection) is our contribution on top of that foundation.
