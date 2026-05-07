# Skills Prompt Budget & Nudge Redesign

Status: Draft
Date: 2026-05-08
Scope: `agent/skill_inventory.py` (new), `agent/prompt_builder.py`, `tools/skills_tool.py`, `tools/skill_manager_tool.py`, `run_agent.py`, `hermes_cli/config.py`, `cli-config.yaml.example`, slash-command dispatchers

---

## 1. Background

Hermes injects every available skill into the system prompt on every turn. Concretely:

- `agent/prompt_builder.py:621-847` `build_skills_system_prompt()` walks `~/.hermes/skills/` plus `external_dirs`, filters by platform / tool conditions / disabled list, and emits a `## Skills (mandatory)` block listing **every visible skill's `(name, description)`**.
- On this machine: 102 skills, average description 194 chars, total ~20k chars of description text alone. With category labels and the multi-paragraph framing preamble the block is **~6-8k tokens injected every turn**.
- The block is cached at two layers (in-process LRU + on-disk snapshot keyed by mtime/size manifest), so the *build* cost is amortized — but the *prompt token* cost is paid on every API call. Anthropic-side prompt caching helps within a session, but the system prompt is rebuilt whenever `available_tools` / `available_toolsets` / disabled list / platform changes, and the block is large enough to dominate other system content.

Separately, a **time-based nudge** at `run_agent.py:1607-1611, 9295-9299, 12176-12182` increments a per-iteration counter (`_iters_since_skill`) and triggers a background "skill review" when the counter reaches `creation_nudge_interval` (configured default `15`, constructor fallback `10`). The counter resets only when `skill_manage` is actually invoked.

Two problems flow from this:

1. **Prompt bloat (A).** Skill index grows linearly with the user's skill library. There is no token budget, no relevance filter, no priority tier — only "show / don't show." A user accumulating 200-500 skills (plausible after a year of use) would pay 12-40k tokens of system prompt overhead per turn.
2. **Nudge false positives (B).** The trigger is purely a tool-call counter. A long task that involves many tool calls but no reusable pattern (e.g., a large refactor, a debugging session) is treated identically to a task that just demonstrated a fresh, reusable workflow. The result is a background skill-review task firing in cases where there's nothing worth saving, wasting model cycles and producing low-signal suggestions.

This document proposes a redesign of both.

---

## 2. Goals & Non-Goals

### Goals

- **G1.** Cut the per-turn skill-index injection cost by ~70% in typical libraries (~2k tokens for 100 skills, scaling sub-linearly).
- **G2.** Preserve the ability for the model to discover and use any skill — no skill becomes "invisible" by default.
- **G3.** Preserve Anthropic-side prompt caching: the skill block must remain stable across turns within a session, i.e. it must NOT depend on user message content.
- **G4.** Replace the time-based nudge with signal-based triggers that fire only when there's evidence of a reusable pattern, while keeping a conservative time-based fallback.
- **G5.** Backward compatible: existing skills continue to work without metadata changes; new behavior is opt-in via frontmatter and config.

### Non-Goals

- **NG1.** Functional-overlap detection between skills (e.g., warning that two skills do similar things). Out of scope; defer to a follow-up.
- **NG2.** Embedding-based or LLM-based relevance ranking of skills against the user's message. Breaks G3 (prompt caching) and adds infrastructure cost. Defer.
- **NG3.** Changes to skill *content* loading (`skill_view`). Only the index and creation-nudge are in scope.

---

## 3. High-Level Design

### A. Two-tier skill index

When `skills.index_v2: true`, the system prompt switches from "every skill with full description" to a **structural index** organized by category, with descriptions reserved for skills the model explicitly opts into.

- **Tier 1 (always in system prompt, cache-stable):**
  - Category name + optional category description (already supported via `DESCRIPTION.md`).
  - Skill names within each category, comma-separated.
  - **Exception:** skills with frontmatter `priority: critical` keep their full description in Tier 1. Reserved for cross-cutting workflow skills the model should always be aware of (e.g., `verification-before-completion`, `systematic-debugging`).
- **Tier 2 (on-demand):**
  - A new tool, `skill_describe`, registered in `tools/skills_tool.py` alongside `skills_list` / `skill_view`, returns descriptions for one or more skills (or all skills in a category). The model calls this when a Tier 1 entry looks relevant and it wants the description before deciding whether to `skill_view` the full content.
- **Hard budget (safety net):**
  - The Tier 1 block has a configurable token budget (default `2000` tokens, conservative). If the rendered block would exceed it (e.g., a user with 1000+ skills), categories beyond the budget are folded into a single line: `… and N more categories — call skill_describe(category=...) to expand`. Categories are ranked for inclusion by recent usage (see §6).

### B. Signal-based nudge

The time-based counter is **demoted to a fallback** with a higher default threshold. Primary triggers become **signals** observed during the turn:

- **S1. Repeated tool pattern.** The same tool name with structurally similar arguments invoked ≥3 times in the current turn. (Heuristic: same tool, same first argument token, varying suffixes — strongly suggests an extractable workflow.)
- **S2. Novel external CLI.** A `terminal` / `process` invocation introduces a CLI binary not seen in the last 30 days of session history. (Suggests a new tool worth documenting.)
- **S3. Explicit user signal.** The current user message contains phrases like "next time", "remember", "from now on", "记一下", "下次", "以后" (configurable list). (Direct user request to remember.)
- **S4. Resolved repeated error.** The same error string appears in tool results ≥2 times within the turn, then a subsequent call succeeds. (A pitfall worth recording.)

Signal evaluation runs in the same place the counter is incremented today (`run_agent.py:9295-9299`), and feeds a `_skill_nudge_signals` set that, if non-empty at end-of-turn, triggers the background review. The existing time counter remains but its default rises to `50` and acts only when no signal has fired for that many iterations.

A per-session disable (`/skills nudge off` slash command, plus `HERMES_SKILL_NUDGE_DISABLE=1` env var) is added.

---

## 4. Detailed Design — Skill Index

### 4.1 Frontmatter additions

Skills opt into Tier 1 description retention via SKILL.md frontmatter:

```yaml
---
name: verification-before-completion
description: Run verification commands before claiming completion …
priority: critical    # NEW. One of: "critical" | "normal" (default).
---
```

`priority: critical` is the only new field. Anything else (or absent) is treated as `normal`.

### 4.2 Render format

**Current** (`build_skills_system_prompt()` output, abbreviated):

```
## Skills (mandatory)
Before replying, scan the skills below … [multi-paragraph preamble]

<available_skills>
  apple/  Apple ecosystem integrations
    - apple-reminders: Manage Apple Reminders via remindctl CLI (list, add, complete, delete).
    - imessage: Send and receive iMessages/SMS via the imsg CLI on macOS.
    - findmy: Track Apple devices and AirTags via FindMy.app on macOS using AppleScript and screen capture.
    [… 99 more entries with full descriptions …]
</available_skills>
```

**New** (Tier 1):

```
## Skills

Tools available:
  - skill_view(name): load full skill content
  - skill_describe(category=..., names=[...]): get one-line descriptions for a category or specific skills
  - skill_manage: create / patch / write_file

The list below shows every available skill organized by category. Skills with descriptions are critical workflows you should consider on every task. For other skills, the name is a hint — if any look relevant, call skill_describe(category="<cat>") to see one-line descriptions, then skill_view(name) to load the full content.

<available_skills>
  apple/  Apple ecosystem integrations
    apple-reminders, imessage, findmy, apple-notes
  research/  Academic and information retrieval
    arxiv, llm-wiki, research-paper-writing, polymarket
  superpowers/  Workflow disciplines
    - verification-before-completion: Run verification commands before claiming completion, fixed, or passing — evidence before assertions always.
    - systematic-debugging: Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes.
    [other superpowers names without descriptions]
  [...]
</available_skills>
```

Token comparison on this machine (102 skills):

| Component                 | Current  | New      |
|---------------------------|----------|----------|
| Preamble                  | ~250 tok | ~150 tok |
| Per-skill (96 normal)     | ~5500 tok | ~600 tok |
| Per-skill (6 critical)    | ~360 tok | ~360 tok |
| Category labels           | ~200 tok | ~200 tok |
| **Total**                 | ~6300 tok | ~1300 tok |

Reduction: ~80% in this configuration.

### 4.3 The `skill_describe` tool

New tool registered alongside `skill_view` / `skill_manage`. Signature:

```python
skill_describe(
    category: str | None = None,    # return all skills in this category
    names: list[str] | None = None, # return specific skills
) -> dict
```

Output: `{"success": true, "skills": [{"name": "...", "category": "...", "description": "..."}, ...]}`. Errors on unknown category/name and when both args are empty.

Backed by a shared skill-inventory helper extracted from `agent/prompt_builder.py`, not by the rendered prompt-string LRU directly. The helper returns filtered metadata (`name`, `category`, `description`, `priority`, conditions) for both `build_skills_system_prompt()` and `skill_describe()`. Local skills continue to use the disk snapshot; external dirs follow the current behavior and are scanned directly so read-only shared skill directories do not become stale. The tool may memoize category/name lookups per process, but it must invalidate when `clear_skills_system_prompt_cache(clear_snapshot=True)` is called.

### 4.4 Budget enforcement

`skills.index_token_budget` config option (default `2000`). Token estimation via simple `len(text) // 4` heuristic — exact tokenization is unnecessary for a soft cap, and avoiding a tokenizer dependency keeps `prompt_builder.py` lightweight.

Algorithm:

1. Build the full Tier 1 block.
2. If under budget, emit as-is.
3. If over, rank categories by **recent usage** (last 30 turns, tracked in a small JSON file at `~/.hermes/.skill_usage.json`, updated whenever `skill_view` / `skill_describe` is called). Most-used categories first. "Category" matches the existing derivation at `agent/prompt_builder.py:730-733`: the path components between `skills_dir` and the SKILL.md file, joined with `/`, defaulting to `general`.
4. Greedily include categories until adding the next would exceed budget. Emit the rest as `… and N more categories: <comma-list of category names>. Call skill_describe(category=...) to expand any of these.`

This guarantees the fold-back text always names the hidden categories so the model can still pull them deliberately.

### 4.5 Cache key changes

Existing cache key in `build_skills_system_prompt()`:

```python
cache_key = (
    str(skills_dir.resolve()),
    tuple(str(d) for d in external_dirs),
    tuple(sorted(str(t) for t in (available_tools or set()))),
    tuple(sorted(str(ts) for ts in (available_toolsets or set()))),
    _platform_hint,
    tuple(sorted(disabled)),
)
```

Add: `("v2", index_v2_enabled, token_budget, usage_rank_epoch)`. The `v2` literal and `_SKILLS_SNAPSHOT_VERSION = 2` force invalidation of stale in-process and on-disk snapshots after the upgrade. `usage_rank_epoch` is a day-level key derived from the usage file only when v2 budget folding is enabled; it keeps the prompt stable within a session and avoids rebuilding on every `skill_view` / `skill_describe` call.

Do not put rendered `skill_describe` results into `_SKILLS_PROMPT_CACHE`; that cache stores prompt strings. Share the parsed inventory instead.

### 4.6 Backward compatibility

- Existing skills with no `priority` field render as `normal`. No migration needed.
- `external_dirs` skills follow the same rules.
- Old on-disk snapshots are invalidated by the `v2` cache key prefix.
- The disabled-list behavior (`get_disabled_skill_names()`) is unchanged.
- The existing `_skill_should_show()` filtering (`requires_tools`, `fallback_for_tools`, etc.) still applies before tier assignment.

---

## 5. Detailed Design — Signal-Based Nudge

### 5.1 Signal evaluation

A new `_evaluate_skill_nudge_signals()` method runs per iteration alongside the existing counter increment in `run_agent.py:9295-9299`. It returns a set of fired signal names.

State held on the run-agent instance:

```python
self._tool_call_history: deque  # last 10 (tool_name, arg_signature) pairs
self._error_history: deque      # last 10 error-message hashes
self._known_clis: set           # CLIs seen in the last 30 days, loaded from ~/.hermes/.skill_known_clis.json
self._nudge_signals: set        # accumulated signals for current turn
```

**S1 (repeated pattern):** for each new tool call, append `(name, arg_signature)` to `_tool_call_history`. The signature is a small per-tool function:

- `terminal` / `process`: first whitespace-delimited token of the command (`gh`, `npm`, `git subcommand`, …).
- `read_file` / `write_file` / `edit_file`: directory portion of the path.
- known web/search tools: host or query prefix when available.
- unknown tools: do not fire S1 until a tool-specific signature is added. Counting only the tool name would make any three calls to the same tool look reusable even when the arguments are unrelated.

Trigger if any `(name, sig)` pair has count ≥3 in the deque.

**S2 (novel CLI):** when the tool is `terminal` or `process`, parse the first whitespace-delimited token from the command, strip path. Record every observed CLI, but fire only when the CLI is not in `_known_clis`, not in a small default suppression list (`git`, `python`, `python3`, `node`, `npm`, `pnpm`, `uv`, `pytest`, `rg`, `sed`, `cat`, `ls`, `mkdir`), and the invocation succeeds or repeats in the same turn. The `_known_clis` file is rotated daily (entries older than 30 days drop off). This avoids treating first-run common developer commands as skill-worthy.

**S3 (explicit user signal):** runs once per turn at start, scans `original_user_message` for trigger phrases. Phrase list is configurable; default in `cli-config.yaml.example` includes EN/ZH variants.

**S4 (resolved repeated error):** for each tool result, hash the first 200 chars of the error string (if any). If a hash appears ≥2 times then a later call with the same tool succeeds, fire signal.

### 5.2 Trigger gating

End-of-turn block at `run_agent.py:12176-12204` changes from:

```python
if (self._skill_nudge_interval > 0
        and self._iters_since_skill >= self._skill_nudge_interval
        and "skill_manage" in self.valid_tool_names):
    _should_review_skills = True
    self._iters_since_skill = 0
```

to:

```python
if "skill_manage" not in self.valid_tool_names:
    pass  # tool not available
elif self._nudge_disabled:
    pass  # session-disabled
elif self._nudge_signals:
    _should_review_skills = True
    self._nudge_signals.clear()
    self._iters_since_skill = 0
elif (self._skill_nudge_interval > 0
        and self._iters_since_skill >= self._skill_nudge_interval):
    _should_review_skills = True
    self._iters_since_skill = 0
```

The default `creation_nudge_interval` is bumped from `15` to `50` as part of Phase 3 (see §7) — Phase 1-2 keep the existing default to limit blast radius.

### 5.3 Per-session disable

- Slash command `/skills nudge off` sets `self._nudge_disabled = True` on the active agent/session. The existing `hermes_cli.skills_hub.handle_skills_slash()` is a hub command router and does not receive an `AIAgent`; implement this as a special case in the CLI / TUI / gateway slash dispatch layer before delegating other `/skills ...` commands to the hub router.
- Env var `HERMES_SKILL_NUDGE_DISABLE=1` read at session init.
- Both are session-scoped; not persisted.

### 5.4 Background review unchanged

Once `_should_review_skills` is true, the existing `_spawn_background_review()` path runs as today. The background reviewer receives the fired signals as additional context (so it can write a more targeted suggestion: "you re-ran `gh pr view` 4 times — consider a skill that wraps PR-status checks").

---

## 6. Data Files & Config

New files:

- `~/.hermes/.skill_usage.json` — `{category_name: [unix_ts, unix_ts, ...]}`, last 30 entries per category. Used by §4.4.
- `~/.hermes/.skill_known_clis.json` — `{cli_name: last_seen_unix_ts}`. Used by §5.1 S2. Pruned on read (drop entries > 30 days old).

Both are best-effort — corruption falls back to empty state, never crashes.

Config additions to `cli-config.yaml.example`:

```yaml
skills:
  # Existing
  creation_nudge_interval: 15      # Phase 1-2: unchanged. Phase 3 changes this to 50.

  # NEW
  index_v2: false                  # Phase 1-2 opt-in. Phase 3 flips to true.
  index_token_budget: 2000         # Soft cap on Tier 1 system-prompt skill block.
  nudge_signals:
    enabled: false                 # Phase 1-2 opt-in. Phase 3 flips to true.
    repeated_pattern_threshold: 3  # S1
    novel_cli_window_days: 30      # S2
    common_cli_suppressions:       # S2
      - git
      - python
      - python3
      - node
      - npm
      - pnpm
      - uv
      - pytest
      - rg
      - sed
      - cat
      - ls
      - mkdir
    user_phrases:                  # S3
      - "next time"
      - "remember"
      - "from now on"
      - "记一下"
      - "下次"
      - "以后"
    error_repeat_threshold: 2      # S4
```

---

## 7. Migration & Rollout

1. **Phase 1 (this PR): index redesign behind flag.** New rendering path lives behind `skills.index_v2: true` in config. Default `false` until validated.
2. **Phase 2 (this PR): nudge redesign behind flag.** `skills.nudge_signals.enabled` default `false`; manual opt-in.
3. **Phase 3 (follow-up PR, after dogfooding):** flip both defaults to `true`. Update `creation_nudge_interval` default to `50`.
4. **Phase 4:** remove the v1 rendering path and the flag plumbing once the v2 path has been default for one minor version.

---

## 8. Testing Strategy

### 8.1 Unit tests (`tests/agent/test_prompt_builder.py`)

- Tier 1 rendering with mix of `priority: critical` and `normal` skills produces expected output.
- Budget enforcement: synthetic 500-skill dir produces a block under the budget with fold-back line listing remaining categories.
- Cache key invalidates correctly on `priority` flip / budget change / category usage shift.
- Backward compat: skills without `priority` field render under `normal`.

### 8.2 Unit tests (`tests/run_agent/test_run_agent.py`)

- Each signal (S1-S4) fires correctly given a synthetic tool-call sequence.
- No false positive when a tool runs once.
- Fallback time counter still triggers when no signal fired for `creation_nudge_interval` iterations.
- Per-session disable suppresses both signal and time triggers.

### 8.3 Unit tests (`tests/tools/test_skills_tool.py` or new adjacent file)

- `skill_describe` tool returns expected output for category and name lookups.
- `skill_describe` errors on unknown categories/names and on empty input.
- `skill_view` / `skill_describe` both update `.skill_usage.json` best-effort without failing the tool call when the file is corrupt or unwritable.

### 8.4 Integration test

- End-to-end: synthetic 100-skill dir, run a 10-turn session, assert the system prompt block stays under budget across all turns and that no skill is permanently invisible (each can be reached via `skill_describe`).

### 8.5 Manual dogfooding checklist (Phase 1-2)

- Run a normal coding session with v2 on, confirm prompt size in logs.
- Force each signal (run a repeated tool, invoke a fresh CLI, type "next time", trigger and resolve a repeated error) and confirm review fires.
- Run a long task with 60+ tool calls and confirm time fallback eventually fires when no signal hits.

---

## 9. Risks & Open Questions

### Risks

- **R1. Model-behavior regression.** Without descriptions for most skills, the model may fail to recognize a relevant skill from its name alone, leading to missed loads. **Mitigation:** category descriptions remain visible; `skill_describe` is one cheap call away; `priority: critical` covers the most universally-applicable skills.
- **R2. Extra round-trip.** A task that needs a non-critical skill now costs at least one `skill_describe` call before the `skill_view`. **Mitigation:** `skill_describe(category=...)` returns a whole category at once, amortizing over multiple decisions in the same task.
- **R3. Signal heuristics noise.** Especially S2 (novel CLI) — a developer who runs many one-off tools could see every one of them flagged. **Mitigation:** suppress common CLIs by default, require success or same-turn repetition for novel CLIs, and keep the review as a background suggestion rather than an action. If suggestions are too noisy, the threshold, suppression list, or window is tunable.
- **R4. Snapshot file corruption.** `.skill_usage.json` / `.skill_known_clis.json` corruption could disable parts of the system. **Mitigation:** read-with-fallback-to-empty, no hard dependency.

### Open Questions

- **Q1.** Should `priority: critical` be limited to a small allowlist (say ≤10 skills) to prevent it from becoming the new default and undoing the savings? Proposal: log a warning at index-build time if more than 15 skills are marked `critical`.
- **Q2.** Should `skill_describe(category=...)` results be cached on the agent side for the rest of the session (so the model doesn't repeat the call)? Proposal: yes, simple per-session memo on the tool's own state.
- **Q3.** Should the nudge surface its triggering signal to the user (e.g., "I noticed you ran `gh pr view` 4 times — want me to save a skill?") or stay fully internal? Proposal: surface, with the trigger reason, since transparency reduces user friction with the nudge.

---

## 10. References

- Current implementation: `agent/prompt_builder.py:621-847`
- Nudge counter: `run_agent.py:1607-1611, 9295-9299, 12176-12204`
- Existing skill tool registration: `tools/skills_tool.py:1392-1445`
- Existing `/skills` hub router: `hermes_cli/skills_hub.py:1172-1383`
- Skill creation / collision check: `tools/skill_manager_tool.py:326-379`
- Existing config keys: `cli-config.yaml.example:480-500` (skills section)
