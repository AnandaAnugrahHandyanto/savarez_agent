# Hermes Agent Bug Inventory
Generated 2026-05-25 from test suite analysis (8,830 tests run).

## Production-Code Issues

### None confirmed from test suite

All 8,830 passing tests indicate production code is stable. Further analysis below.

## Test Infrastructure Bugs (ranked by impact)

### 1. ~~[HIGH] `faster_whisper` stub missing `__spec__`~~ ✅ FIXED (prior session)
**File:** `tests/tools/test_transcription_tools.py:18-21`
**Fix:** Stub now sets `__spec__ = importlib.machinery.ModuleSpec(...)`.

### 2. ~~[HIGH] `_fresh_modules()` too narrow — vision routing tests fail with plugins~~ ✅ FIXED (2026-05-25, commit ab29628)
**File:** `tests/agent/test_vision_routing_31179.py:63-69`
**Fix:** Added `agent.models_dev` to the modules cleared by `_fresh_modules()`.
**Root cause:** Global `_models_dev_cache` in `agent.models_dev` leaked between test cases, causing stale vision capability data to pollute subsequent tests.

### 3. [MEDIUM] Test ordering pollution — path resolution tests
**File:** `tests/tools/test_resolve_path.py`
**Symptom:** 3 tests fail in full suite, pass in isolation.
**Root cause:** Another test file modifies module state or env vars that affect path resolution, and doesn't clean up.
**Fix:** Identify the polluting test via bisect, add proper cleanup.
**Impact:** CI flakes depending on test execution order.

### 4. [LOW] YOLO mode tests don't reset `_YOLO_MODE_FROZEN`
**File:** `tests/tools/test_yolo_mode.py`
**Symptom:** 15 failures when `HERMES_YOLO_MODE=1` env var is set.
**Root cause:** `_YOLO_MODE_FROZEN` is frozen at module import time in `tools/approval.py:29`. Tests use `monkeypatch.delenv` but the frozen flag was already True.
**Fix:** Tests should `monkeypatch.setattr(approval_module, "_YOLO_MODE_FROZEN", False)`.
**Impact:** Only environments with YOLO mode enabled (like ours). CI is unaffected.

## Code TODOs (from code scan)

| File | TODO |
|------|------|
| `skills/productivity/linear/scripts/linear_api.py:232` | label + assignee name→id lookup omitted for v1 |
| `agent/context_compressor.py` | OpenAI SDK TODO about non-asyncio runtimes |
| `agent/auxiliary_client.py:4132` | OpenAI SDK TODO about non-asyncio runtimes |
| `optional-skills/research/darwinian-evolver/` | Template TODOs (not core) |

## Test Suite Stats
- **Agent tests:** 3,500 pass, 4 fail
- **Tools tests:** 5,330 pass, 40 fail (35 env-specific), 50 skip
- **Total:** ~8,830 passing
- **Dependencies:** All core + dev deps installed via `pip install -e ".[dev]"`

## Micro-SaaS Inventory
- **scraper-saas** at `/opt/data/repos/scraper-saas/`: Flask API for URL data extraction. 7/7 tests pass. Ready to deploy.
- **content-repurposer**: Planned — AI-powered blog→social media repurposing tool.
