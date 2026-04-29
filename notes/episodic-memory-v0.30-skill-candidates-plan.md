# Episodic Memory v0.30 Optional Skill-Candidate Pipeline Plan

> **For Hermes:** Use subagent-driven-development if/when executing this plan. Runtime source of truth is `~/.hermes/plugins/episodic/`; keep the mirror under `~/.hermes/hermes-agent/user-plugins/episodic/` in sync.

**Goal:** Add an optional, user-toggleable skill-candidate pipeline to episodic memory that can detect repeated workflows cheaply, optionally draft candidate skills with an LLM, and never auto-publish by default.

**Architecture:** Extend the current zero-LLM journal-first episodic plugin with a second, fully gated pipeline. Stage 1 is deterministic candidate detection over session JSONL / journal artifacts. Stage 2 is optional LLM drafting for individual candidates or scheduled batches. Candidate review and publishing remain human-controlled. Reuse the existing `on_session_end()` hook, config loader, SQLite store, and journal artifacts rather than introducing a parallel memory substrate.

**Tech Stack:** Hermes episodic plugin (`~/.hermes/plugins/episodic/`), Python 3.11, SQLite/JSONL session store, existing config resolver in `config.py`, optional `call_llm()` path already used by extraction/wiki distillation.

---

## Current state confirmed

### Live runtime
- Runtime plugin: `~/.hermes/plugins/episodic/`
- Mirror in repo worktree: `~/.hermes/hermes-agent/user-plugins/episodic/`
- Active plugin manifest: `~/.hermes/plugins/episodic/plugin.yaml` at `version: 0.20.0`

### Existing hook points
- `~/.hermes/plugins/episodic/config.py`
  - already has feature flags:
    - `ENABLE_LLM_EXTRACTION = False`
    - `ENABLE_SESSION_JOURNAL = True`
- `~/.hermes/plugins/episodic/provider.py`
  - `on_session_end()` already branches between:
    - lightweight journal path
    - heavy LLM extraction/merge/compress path
- `~/.hermes/plugins/episodic/journal.py`
  - already converts JSONL turns into tagged markdown with deterministic tool-derived tags

### Design constraint
The system already learned that sparse banks and broad synthesis can create false positives. So v0.30 must separate:
1. **candidate detection**
2. **LLM drafting**
3. **actual skill creation**

These must never be one silent auto-publish path.

---

# Config schema for v0.30

Add a dedicated config block under the episodic plugin layer:

```yaml
memory:
  episodic:
    skill_candidates_enabled: true
    skill_candidate_mode: detect-only   # off | detect-only | draft
    skill_candidate_auto_publish: false
    skill_candidate_min_occurrences: 3
    skill_candidate_review_limit: 10
    skill_candidate_scan_source: jsonl  # jsonl | journal | both
    skill_candidate_draft_model: ""    # empty = resolve from main config
```

## Semantics
- `skill_candidates_enabled: false`
  - hard-off switch; nothing runs
- `skill_candidate_mode: off`
  - same as disabled, but explicit state for downstream logic
- `detect-only`
  - run pattern mining and persist candidate metadata only
  - no LLM drafting in background
- `draft`
  - run detection and permit LLM drafting
  - still no publishing
- `skill_candidate_auto_publish: false`
  - keep false in v0.30
  - if ever supported later, require separate explicit opt-in plus approval workflow

## Recommended default for beta

```yaml
skill_candidates_enabled: true
skill_candidate_mode: detect-only
skill_candidate_auto_publish: false
```

Reason: users get value from discovery without surprise token cost or skill spam.

---

# File-level implementation plan

## Task 1: Extend config parsing for skill-candidate flags

**Objective:** Add stable feature flags and typed accessors without disturbing the current journal/extraction toggles.

**Files:**
- Modify: `~/.hermes/plugins/episodic/config.py`
- Mirror: `~/.hermes/hermes-agent/user-plugins/episodic/config.py`
- Test: `~/.hermes/plugins/episodic/tests/test_phase3_distillation.py` or create `~/.hermes/plugins/episodic/tests/test_skill_candidates.py`

**Implementation details:**
- Add constants with safe defaults:
  - `ENABLE_SKILL_CANDIDATES = True`
  - `SKILL_CANDIDATE_MODE = "detect-only"`
  - `SKILL_CANDIDATE_AUTO_PUBLISH = False`
  - `SKILL_CANDIDATE_MIN_OCCURRENCES = 3`
  - `SKILL_CANDIDATE_REVIEW_LIMIT = 10`
  - `SKILL_CANDIDATE_SCAN_SOURCE = "jsonl"`
- Add a helper:

```python
def get_skill_candidate_settings() -> dict:
    cfg = load_config() or {}
    mem_cfg = cfg.get("memory") if isinstance(cfg, dict) else {}
    episodic_cfg = mem_cfg.get("episodic") if isinstance(mem_cfg, dict) else {}
    return {
        "enabled": bool(episodic_cfg.get("skill_candidates_enabled", ENABLE_SKILL_CANDIDATES)),
        "mode": str(episodic_cfg.get("skill_candidate_mode", SKILL_CANDIDATE_MODE)).strip().lower() or "off",
        "auto_publish": bool(episodic_cfg.get("skill_candidate_auto_publish", SKILL_CANDIDATE_AUTO_PUBLISH)),
        "min_occurrences": int(episodic_cfg.get("skill_candidate_min_occurrences", SKILL_CANDIDATE_MIN_OCCURRENCES)),
        "review_limit": int(episodic_cfg.get("skill_candidate_review_limit", SKILL_CANDIDATE_REVIEW_LIMIT)),
        "scan_source": str(episodic_cfg.get("skill_candidate_scan_source", SKILL_CANDIDATE_SCAN_SOURCE)).strip().lower() or "jsonl",
    }
```

**Verification:**
- Unit tests for:
  - default settings
  - custom config overrides
  - invalid mode fallback to `off` or `detect-only`

---

## Task 2: Add persistent candidate storage

**Objective:** Store discovered candidates independently of episodes/entities so detection is cheap and reviewable.

**Files:**
- Modify: `~/.hermes/plugins/episodic/store.py`
- Mirror: `~/.hermes/hermes-agent/user-plugins/episodic/store.py`
- Test: `~/.hermes/plugins/episodic/tests/test_skill_candidates.py`

**Add SQLite table:**

```sql
CREATE TABLE IF NOT EXISTS skill_candidates (
  id TEXT PRIMARY KEY,
  fingerprint TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'detected',
  pattern_type TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 0,
  occurrence_count INTEGER NOT NULL DEFAULT 0,
  first_seen_at REAL NOT NULL,
  last_seen_at REAL NOT NULL,
  source_sessions_json TEXT NOT NULL DEFAULT '[]',
  evidence_json TEXT NOT NULL DEFAULT '[]',
  draft_markdown TEXT,
  draft_generated_at REAL,
  published_skill_name TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_skill_candidates_fingerprint
ON skill_candidates(fingerprint);
```

**Store methods:**
- `upsert_skill_candidate(candidate: dict) -> dict`
- `list_skill_candidates(status: str | None = None, limit: int = 20) -> list[dict]`
- `get_skill_candidate(candidate_id: str) -> dict | None`
- `update_skill_candidate_status(candidate_id: str, status: str, **fields)`

**Status values for v0.30:**
- `detected`
- `drafted`
- `approved`
- `rejected`
- `published`
- `snoozed`

**Verification:**
- migration test on existing DB
- upsert dedup by fingerprint
- status transition tests

---

## Task 3: Implement zero-LLM candidate detection module

**Objective:** Build the cheap pattern-mining layer that works without an LLM.

**Files:**
- Create: `~/.hermes/plugins/episodic/skill_candidates.py`
- Mirror: `~/.hermes/hermes-agent/user-plugins/episodic/skill_candidates.py`
- Test: `~/.hermes/plugins/episodic/tests/test_skill_candidates.py`

**Detection inputs:**
- primary: `~/.hermes/memory/sessions/*.jsonl`
- optional secondary: `~/wiki/session-recordings/**.md`

**Rule-based signals:**
1. repeated tool sequences
2. repeated tool-set combinations
3. repeated file-path targets in assistant tool usage
4. repeated repo/workspace context markers
5. repeated user phrasing such as:
   - `last time`
   - `again`
   - `same process`
   - `can you do that for`
6. repeated successful resolution patterns:
   - same tool chain across 3+ sessions
   - same error token followed by same fix token

**Candidate record shape:**

```python
{
  "id": "cand_<hash>",
  "fingerprint": "workflow:terminal>read_file>patch>pytest",
  "title": "Repeated code-fix workflow using terminal + patch + pytest",
  "pattern_type": "workflow",
  "confidence": 0.78,
  "occurrence_count": 4,
  "source_sessions": ["20260428_...", "20260427_..."],
  "evidence": [
    {"type": "tool_sequence", "value": ["terminal", "read_file", "patch", "terminal"]},
    {"type": "path_prefix", "value": "~/.hermes/hermes-agent/"}
  ],
  "metadata": {"scan_source": "jsonl"}
}
```

**Important v0.30 rule:**
No LLM call in this module. Keep it deterministic.

**Verification:**
- fixture with synthetic sessions that should produce one candidate
- fixture with sparse/noisy sessions that should produce none
- duplicate sessions should increment occurrence count rather than create clones

---

## Task 4: Wire candidate detection into `on_session_end()` behind flags

**Objective:** Reuse existing lifecycle plumbing without slowing ordinary sessions when disabled.

**Files:**
- Modify: `~/.hermes/plugins/episodic/provider.py`
- Mirror: `~/.hermes/hermes-agent/user-plugins/episodic/provider.py`
- Test: `~/.hermes/plugins/episodic/tests/test_skill_candidates.py`

**Implementation details:**
- After journal write succeeds, read `settings = get_skill_candidate_settings()`
- Branch:
  - if disabled or mode `off`: return without scan
  - if `detect-only` or `draft`: run detector on the current session and maybe recent historical sessions
- Do **not** block journal generation on candidate scan failures
- Fail loudly but independently:
  - create separate failure artifact key such as `skill-candidate-failure`

**Pseudo-flow:**

```python
if ENABLE_SESSION_JOURNAL:
    write_session_journal(...)

candidate_settings = get_skill_candidate_settings()
if candidate_settings["enabled"] and candidate_settings["mode"] in {"detect-only", "draft"}:
    try:
        from .skill_candidates import detect_skill_candidates_for_session
        detect_skill_candidates_for_session(store=self._store, session_id=sid, settings=candidate_settings)
    except Exception as e:
        logger.error("Skill candidate detection failed: %s", e)
        self._emit_failure_alert(...)
```

**Verification:**
- with feature off, detector is not called
- with `detect-only`, candidate rows are created
- failure path emits artifact but journal still writes

---

## Task 5: Add optional LLM drafting for candidates

**Objective:** Make the expensive part explicitly optional and separately gated.

**Files:**
- Modify: `~/.hermes/plugins/episodic/skill_candidates.py`
- Possibly create: `~/.hermes/plugins/episodic/skill_candidate_drafts.py`
- Mirror same changes in `~/.hermes/hermes-agent/user-plugins/episodic/`
- Test: `~/.hermes/plugins/episodic/tests/test_skill_candidates.py`

**Behavior:**
- only run when mode is `draft`
- only draft candidates meeting minimum threshold
- draft exactly one of:
  - current-session candidate when explicitly requested, or
  - top N undrafted candidates in a batch job

**Draft prompt inputs:**
- candidate metadata
- 2-3 representative source sessions
- extracted evidence list
- required output schema:
  - title
  - why recurring
  - when to use
  - numbered steps
  - pitfalls
  - verification

**Output target:**
Store in `skill_candidates.draft_markdown`; do not call `skill_manage.create` automatically.

**Verification:**
- mock LLM path test
- ensure detect-only never invokes LLM
- ensure drafted candidate status moves `detected -> drafted`

---

## Task 6: Add review surfaces before any publish action

**Objective:** Expose candidate discovery to the user without auto-creating skills.

**Files:**
- Preferred: add new episodic memory tools in `~/.hermes/plugins/episodic/provider.py`
- Optional helper: `~/.hermes/plugins/episodic/skill_candidates.py`
- Mirror same in repo path
- Tests: `~/.hermes/plugins/episodic/tests/test_skill_candidates.py`

**New tools for v0.30:**
- `memory_list_skill_candidates`
- `memory_get_skill_candidate`
- `memory_draft_skill_candidate`
- `memory_update_skill_candidate`

**Suggested schemas:**
- `memory_list_skill_candidates(status?, limit?)`
- `memory_get_skill_candidate(candidate_id)`
- `memory_draft_skill_candidate(candidate_id)`
- `memory_update_skill_candidate(candidate_id, action)` where action is `approve|reject|snooze`

**Important safety rule:**
Publishing to the skills system remains a separate explicit action. In v0.30, the user should inspect the candidate and then deliberately create/patch a skill.

**Verification:**
- tool schema exposure only when episodic provider is available
- list/get/update happy paths
- invalid candidate ID errors are clear

---

## Task 7: Add one explicit publish path, still human-gated

**Objective:** Allow promotion from reviewed candidate to actual skill, but only with user confirmation.

**Files:**
- Modify: `~/.hermes/plugins/episodic/provider.py` or `skill_candidates.py`
- Possibly integrate with existing `skill_manage` workflow rather than direct filesystem writes
- Mirror same in repo path
- Tests: `~/.hermes/plugins/episodic/tests/test_skill_candidates.py`

**Rule:**
- v0.30 should support *drafting* and *approval state*
- actual skill creation should be initiated by the normal agent flow using `skill_manage`, not an unattended background hook

**Recommended implementation:**
- store `approved` state in episodic DB
- when user says “promote candidate X,” the agent reads `draft_markdown` and calls `skill_manage(action='create')`
- after success, mark candidate `published` and save `published_skill_name`

This keeps responsibility boundaries clean.

---

## Task 8: Documentation and release notes

**Objective:** Make the toggle behavior obvious and reduce surprise spend/confusion.

**Files:**
- Modify: `~/.hermes/plugins/episodic/README.md`
- Modify: `~/.hermes/plugins/episodic/plugin.yaml` (`version: 0.30.0` when released)
- Create: `~/.hermes/hermes-agent/notes/episodic-memory-v0.30.md`
- Mirror docs summary in `~/.hermes/hermes-agent/user-plugins/episodic/README.md` if maintained

**Docs must explain:**
- feature is optional
- `detect-only` is the recommended beta mode
- draft mode uses LLM spend
- no auto-publishing by default
- how to review / reject / snooze candidates

**Release note language:**
- “v0.30 introduces optional skill-candidate detection from episodic session history.”
- “LLM drafting is separately gated and disabled unless the user enables draft mode.”
- “Candidate promotion to an actual skill remains human-approved.”

---

# Testing plan

## New test file
Create:
- `~/.hermes/plugins/episodic/tests/test_skill_candidates.py`

## Minimum test cases
1. config defaults resolve to `detect-only`
2. disabled mode skips scanning
3. repeated synthetic sessions create one deduped candidate
4. sparse/noisy sessions do not create false positives
5. draft mode calls mocked LLM path; detect-only does not
6. candidate status transitions work
7. publish path requires explicit action and never runs in background
8. provider failure path emits `skill-candidate-failure` artifact without breaking journal

## Suggested commands
Run in runtime plugin directory:

```bash
cd ~/.hermes/plugins/episodic
source ~/.hermes/hermes-agent/venv/bin/activate
python -m pytest tests/test_skill_candidates.py -q
python -m pytest tests/test_journal_alerting.py tests/test_skill_candidates.py -q
```

Broader confidence pass:

```bash
cd ~/.hermes/hermes-agent
source venv/bin/activate
python -m pytest tests/agent/test_memory_provider.py tests/run_agent/test_run_agent.py -q
```

---

# Suggested v0.30 scope cut

## Include in v0.30
- config flags
- candidate storage table
- deterministic detector
- provider integration
- candidate review tools
- optional single-candidate drafting

## Defer to v0.40+
- automatic batch drafting at scale
- cross-entity graph-assisted candidate ranking
- direct skill patch suggestions
- auto-publish path
- confidence learning from user approvals/rejections

This keeps v0.30 aligned with the “slow, steady beta progression” principle.

---

# Acceptance criteria

A v0.30 implementation is complete when all of the following are true:

1. A user can leave the feature fully off.
2. A user can enable `detect-only` and incur no LLM drafting cost.
3. Repeated workflows across sessions generate stable candidate records.
4. Candidate drafting is separately gated by mode.
5. No skill is auto-created without explicit user action.
6. Failures in candidate detection/drafting do not break journal creation.
7. Runtime plugin and repo mirror are updated together.
8. Tests cover off/detect-only/draft modes.

---

# Recommended next move

Implement **Tasks 1-4 first** as the v0.30 backbone. That gives you:
- the optional toggle
- cheap recurring-pattern discovery
- no forced LLM spend
- a stable substrate for later drafting/review

Then layer **Task 5** only after the detector proves it yields clean candidates.
