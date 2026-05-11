# Enforced Goal Execution — Design Document

## TL;DR

Stock `/goal` uses a binary yes/no judge to decide if a goal is done. The agent can
ignore the judge, self-report completion without verification, and loop indefinitely
on failing approaches. Enforced goal execution adds pre-processing that **overrides**
the judge when loops or regressions are detected, caps completion scores until
artifacts are verified, and injects persistent "DO NOT" rules into every continuation
prompt. Drop-in replacement. No API changes. 39 tests pass.

---

## The Problem With Stock `/goal`

Stock goals work like this:

```
/goal "Build X"
  → Execute turn
  → Judge: "done?" → yes/no
  → If no: same prompt, try again
  → 20 turns, then give up
```

This has three failure modes that compound in production:

### 1. The judge is advisory, not authoritative

The judge returns a verdict ("done" or "continue"), but the agent can ignore it.
If the agent decides the judge is wrong, it keeps doing what it was doing. The
judge's "pivot" or "refine" suggestions are just that — suggestions. No mechanism
prevents the agent from retrying the same failing pattern.

### 2. Completion is self-reported

The judge asks: "Is the goal done?" based on what the agent SAID it did, not what
it ACTUALLY did. The agent says "I've written all the tests" and the judge says
"done." No one checked if the tests exist, pass, or even compile.

### 3. There's no memory of what failed

Each turn is independent. If the agent curls localhost and gets connection refused
on turn 3, it will curl localhost again on turn 4. And turn 5. There's no mechanism
to say "this has been tried 3 times, try something else."

The stock system is a loop with a rubber stamp. It works for simple tasks but
breaks down on anything requiring error recovery.

---

## Architecture

Enforced goal execution runs every turn through a three-stage pipeline:

```
              ┌────────────┐
              │  Agent turn│
              └─────┬──────┘
                    │
         ┌──────────▼──────────┐
         │ PRE-PROCESSING       │
         │ • Semantic loop check│
         │ • Error pattern check│
         │ • Trend detection    │
         └──────────┬──────────┘
                    │
         ┌──────────▼──────────┐
         │ LLM JUDGE            │
         │ • Completion (0-1)   │
         │ • Progress signal    │
         │ • Quality (0-1)      │
         │ • Negative constraint│
         └──────────┬──────────┘
                    │
         ┌──────────▼──────────┐
         │ POST-PROCESSING      │
         │ • Hard pivot override│
         │ • Verification gate  │
         │ • Constraint storage │
         └──────────┬──────────┘
                    │
         ┌──────────▼──────────┐
         │ CONTINUATION PROMPT  │
         │ (with injected       │
         │  constraints)        │
         └─────────────────────┘
```

### Stage 1: Pre-processing (deterministic)

Before the LLM judge runs, the system runs three deterministic checks:

**Semantic loop detection:**
Every tool call is classified by INTENT, not just name+args.

- `pip install foo`, `pip install bar`, `brew install baz` → all classified as "install"
- `curl localhost:3000/health`, `curl localhost:3000/status` → both classified as "http_request"
- `read_file(path="/src/a.py")`, `read_file(path="/src/b.py")` → classified as "read:<filename>"

Two thresholds:
- Exact match (same tool + same first arg): fire at 2 repetitions
- Semantic intent (same classification): fire at 3 repetitions

When a loop is detected, it's flagged for hard override in stage 3.

**Error pattern tracking:**
Errors are tracked in the scratchpad. A command that triggers errors 3+ times across
turns is classified as systemic. This is distinct from transient failures (network
blip, rate limit).

**Trend detection:**
The last 5 verdict scores are compared. If 3+ are strictly decreasing, the system
flags it as regression. A single-turn judge can't see a trend — this catches silent
backsliding.

### Stage 2: LLM judge (unchanged from stock)

The judge model still runs the same API call. But the system prompt has been upgraded
from a simple "done? yes/no" to calibrated scoring with concrete examples:

| Completion band | Meaning | Example |
|----------------|---------|---------|
| 0.00-0.15 | Nothing produced | "I'll start by looking at the code" |
| 0.16-0.35 | Scaffolding exists | Skeleton file created, plans written |
| 0.36-0.55 | Partial work | Core logic exists, incomplete |
| 0.56-0.75 | Mostly done | Main deliverable exists, no verification |
| 0.76-0.90 | Complete but unverified | Everything written, nothing confirmed |
| 0.91-1.00 | Verified complete | Tests pass, files confirmed, services up |

The judge also receives pre-detected loop/error signals as context, plus scratchpad
state showing what sub-tasks are done, what artifacts have been created, and what
approaches have been tried.

### Stage 3: Post-processing (hard enforcement)

This is where the system overrides the judge:

**Hard pivot override:** If pre-processing detected a semantic loop, exact loop, or
systemic error pattern, AND the LLM judge returned anything other than "pivot_strategy",
"done", "failed", or "ask_user", the verdict is FORCED to "pivot_strategy." The
negative constraint is set automatically from the detected pattern.

**Regression override:** If trend detection flagged regression, the verdict is forced
to "pivot_strategy" unless the judge independently returned "done", "failed", or
"ask_user."

**Verification gate:** If completion was scored above 0.75 but zero artifacts are
marked as verified, completion is CAPPED at 0.75 and the action is changed to
"refine_output" with a message to verify artifacts first. "Done" requires:
- Completion ≥ 0.91
- Quality ≥ 0.70
- At least one artifact with `verified=true`
- Agent explicitly says "done" or "complete" (not "next I'll" or "I still need to")

**Negative constraint storage:** If the verdict includes a `negative_constraint`
("do NOT curl localhost"), it's saved to the scratchpad and injected into every
future continuation prompt until the goal completes.

---

## Scratchpad: The Working Memory

The scratchpad is serialized alongside GoalState in SessionDB and persists across
turns. New fields for enforced execution:

| Field | Purpose |
|-------|---------|
| `sub_tasks[].depends_on` | DAG edges. Task B can't start until task A finishes. Enables parallel dispatch. |
| `negative_constraints` | List of "do NOT do" rules. Deduplicated case-insensitively. Injected into every continuation prompt. |
| `error_patterns` | Dict of error message → count. Tracks systemic errors for pattern detection. |
| `history` | List of past verdicts. Kept at max 50 entries. Enables trend detection. |
| `previous_approaches` | List of strategies tried. Deduplicated. Presented to the judge to prevent retries. |

### DAG decomposition

When a goal is decomposed, sub-tasks can specify dependencies:

```json
{
  "sub_tasks": [
    {"description": "Create project structure", "depends_on": []},
    {"description": "Write backend", "depends_on": ["Create project structure"]},
    {"description": "Write frontend", "depends_on": ["Create project structure"]}
  ]
}
```

The `get_parallel_batches()` method groups tasks into waves:

```
Wave 1: ["Create project structure"]              ← no dependencies
Wave 2: ["Write backend", "Write frontend"]       ← both depend on wave 1, can run together
```

If no explicit edges exist, `infer_dependencies()` creates a linear chain as
the safe default. This is backward-compatible with the stock linear decomposition.

### Continuation prompt injection

The continuation prompt now includes:

1. **Action signal:** "HARD PIVOT — change approach now" vs "Continue toward goal"
2. **Negative constraints:** Active "do NOT do" rules, visible to the agent
3. **Recurring errors:** Systemic error patterns with counts
4. **Scratchpad context:** Sub-task progress, artifacts, blockers, approaches tried
5. **Judge verdict:** Reason, suggested next action, suggested pivot

All injected as user-role messages to preserve prompt caching.

---

## Budget Management

Stock: fixed 20 turns. Pauses when exhausted.

Enforced: adaptive budget (5-200 turns) estimated from goal complexity using
12 regex signals. Auto-extends by +25% when ≥50% complete and moving forward.
Pauses when progress stalls.

Complexity estimation:

```
base = max(10, word_count / 3)
bonus = sum of signal matches (e.g., "build" = +3, "deploy" = +2)
subtask_budget = subtask_count * 5
result = max(MIN_TURNS, min(MAX_TURNS, base + bonus + subtask_budget))
```

---

## Backward Compatibility

This is a drop-in replacement for the three files in `hermes_cli/`:

- `goals.py`: GoalManager class — same public API (`set`, `pause`, `resume`, `clear`, `evaluate_after_turn`)
- `goal_judge.py`: NEW file — extracted from stock `goals.py` monolith
- `goal_scratchpad.py`: NEW file — extracted from stock `goals.py` monolith

The `GoalManager.evaluate_after_turn()` return dict has the same shape (`status`,
`should_continue`, `continuation_prompt`, `verdict_action`, `verdict_label`,
`message`, `completion`, `quality`). The stock field `verdict` was renamed to
`verdict_action` for clarity but the dict is otherwise identical.

Active goals at upgrade time: `GoalState` serialization is backward-compatible.
The new scratchpad fields (history, error_patterns, negative_constraints) are
optional in `from_json()` and default to empty. An existing paused goal will
resume normally.

No config changes required. The existing `goals.max_turns` config is honored
as the default budget. The new adaptive budget only applies when no explicit
`max_turns` is set.

---

## Testing

39 tests in `tests/hermes_cli/test_goals.py` cover:

- Judge parsing: clean JSON, markdown-fenced JSON, prose-embedded JSON, malformed, empty
- Judge evaluation: done, continue, stalled, empty goal, empty response, API error
- Semantic loop detection: exact loops, semantic loops, diverse intents
- GoalManager lifecycle: set, pause, resume, clear, persistence across instances
- Turn evaluation: done, continue, budget exhaustion, inactive state
- Budget: auto-extend on progress, pause on exhaustion
- Negative constraints: persistence across turns, injection into prompts
- DAG: dependency inference, ready-task detection, parallel batching
- Error tracking: pattern counting, persistence
- History: verdict recording, history length management

All 39 pass: `python -m pytest tests/hermes_cli/test_goals.py -q`
