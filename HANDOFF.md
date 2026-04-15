# Project Handoff: hermes-agent
Last updated: 2026-04-15T22:55:00Z
Last session: source=cli model=gpt-5.4

## Current State
Hermes Agent repo is still broadly dirty with many unrelated uncommitted workstreams, but the browser-security/browser-latency track is now finished through Upgrades 8, 9, and 10 in the actual repo at `/home/ubuntu/.hermes/hermes-agent`. Upgrade 8 scoped browser authority + receipts is implemented. Upgrade 9 adds `browser_batch` for sequential multi-step browser execution in one tool call. Upgrade 10 adds an internal browser boundary shim with an in-process reference implementation. Targeted verification for the full browser track is green.
Score/status: Upgrades 8-10 implemented and verified with targeted pytest; not committed because the repo contains unrelated dirty changes.

## What Was Done Last Session
- Recovered prior context from session history and existing HANDOFF before touching code.
- Verified Upgrade 8 authority/receipt work and added missing API test coverage for `/v1/responses` and `/v1/runs` authority propagation.
- Implemented Upgrade 9 `browser_batch` in `tools/browser_tool.py`, wired it into `model_tools.py` and `toolsets.py`, documented it, and added focused tests.
- Implemented Upgrade 10 internal browser boundary shim via `tools/browser_boundary.py` plus shim routing/hooks in `tools/browser_tool.py`, documented it, and added focused tests.
- Ran final verification:
  - `source venv/bin/activate && pytest -q tests/tools/test_browser_authority.py tests/tools/test_browser_batch.py tests/tools/test_browser_boundary_shim.py tests/test_model_tools.py tests/gateway/test_api_server.py tests/gateway/test_api_server_toolset.py`
  - Result: `161 passed, 78 warnings in 20.66s`

## Active Decisions (DO NOT REVISIT)
- Local browser use remains permissive by default for backward compatibility.
- Remote browser authority is capability-gated and ownership-scoped.
- Browser session receipts live under `~/.hermes/browser_sessions/<session_name>/metadata.json` and `audit.jsonl`.
- `browser_batch` executes actions sequentially through the existing high-level browser wrappers, not raw command bypasses.
- The browser boundary shim is internal architecture only. Do not add a new external API parameter for shim selection unless there is a very good reason.
- Do not mix this browser-track work with the many unrelated dirty files in the repo when staging/committing.

## Anti-Patterns (DO NOT DO)
- Do not claim the browser track is still only partly implemented. 8, 9, and 10 are done in the actual repo.
- Do not regress remote session reuse into implicit trust; owner checks must stay enforced.
- Do not bypass browser wrapper behavior in `browser_batch` by routing directly to raw CLI commands.
- Do not create a broad repo-wide commit from this working tree unless the unrelated dirty changes are intentionally included.

## Next Steps (in priority order)
1. If you want this shipped cleanly, isolate the browser-track files from unrelated dirty changes and commit only those.
2. If broader confidence is needed, run a higher-level browser integration pass against a real site/session to exercise receipts + batch execution together.
3. If future transport work is needed, extend `tools/browser_boundary.py` with a second shim implementation instead of changing the public browser tool API.

## Architecture Notes
- `tools/browser_authority.py`: authority schema, normalization, capability mapping, owner checks, metadata/audit helpers.
- `tools/browser_boundary.py`: internal boundary shim protocol + in-process reference implementation.
- `tools/browser_tool.py`: browser tool schemas, browser wrappers, `browser_batch`, authority enforcement, session lifecycle, and shim routing for session lookup / command execution / cleanup.
- `gateway/platforms/api_server.py`: parses `X-Hermes-Browser-Authority` / `body.browser_authority`, forwards authority into chat/responses flows, and installs authority inside `/v1/runs` executor-thread execution.
- `tests/tools/test_browser_authority.py`: authority normalization, enforcement, session metadata persistence.
- `tests/tools/test_browser_batch.py`: batch schema/wiring/validation/step-order behavior.
- `tests/tools/test_browser_boundary_shim.py`: default shim, shim override, command routing, cleanup routing, authority visibility.
- `tests/gateway/test_api_server.py`: API parsing/forwarding tests for chat, responses, and runs authority propagation.
- `tests/gateway/test_api_server_toolset.py`: confirms browser tool exposure including `browser_batch`.
- `website/docs/user-guide/features/browser.md`: scoped authority docs, `browser_batch` docs, boundary shim docs.

## Branch Strategy
Current branch: main (repo working tree at `/home/ubuntu/.hermes/hermes-agent`)
Protected branch: main
Note: the wrapper CLI session itself may be in a sparse Hermes worktree, but the real repo-under-edit for this browser work is `/home/ubuntu/.hermes/hermes-agent`.
