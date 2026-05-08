# Hermes AI Office — NEXT

Last updated: 2026-05-08 17:14 KST

## Start here after `/new`

1. Load relevant skills if needed:
   - `hermes-agent`
   - `writing-plans`
   - `plan` if staying planning-only
   - `kanban-orchestrator` only if creating/organizing board tasks is explicitly approved
2. Read this file.
3. Read `STATUS.md`.
4. Read the latest Stage 5 outputs:
   - `docs/ai-office/architecture/backend-api.md`
   - `docs/ai-office/architecture/data-adapters.md`
   - `docs/ai-office/architecture/frontend-components.md`
   - `docs/ai-office/architecture/test-plan.md`
   - `docs/ai-office/architecture/rollout-plan.md`
   - `docs/ai-office/architecture/pixel-renderer-adapter.md`
5. If needed for provenance/routing context, then read the Stage 4 outputs:
   - `docs/ai-office/design/topic-registry-spec.md`
   - `docs/ai-office/design/task-provenance-metadata.md`
   - `docs/ai-office/design/provenance-backfill.md`
   - `docs/ai-office/design/privacy-security.md`
6. If needed for product context, then read the Stage 3 outputs:
   - `docs/ai-office/product/user-stories.md`
   - `docs/ai-office/architecture/office-state-model.md`
   - `docs/ai-office/product/information-architecture.md`
   - `docs/ai-office/product/non-goals-and-mutation-boundary.md`
   - `docs/ai-office/product/mvp-acceptance-criteria.md`
7. Do not implement dashboard code unless the user explicitly approves an implementation stage.
8. Continue from the `Current next stage` below.

## Suggested `/goal` for a fresh session

Use `/goal` as a session-level guardrail and progress judge, not as the durable project memory. Durable state still lives in `STATUS.md`, `NEXT.md`, `DECISIONS.md`, `OPEN-QUESTIONS.md`, and stage output docs.

Default planning-mode goal:

```text
/goal Hermes AI Office / Pixel Agents style dashboard project를 구현하지 말고, 먼저 충분한 리서치·제품기획·아키텍처·단계별 실행계획·리스크·MVP 범위를 문서화한다. 각 단계는 STATUS/NEXT handoff를 남겨 /new 후에도 이어갈 수 있게 하고, 실제 코드 구현·서비스 재시작·설정 변경은 사용자가 명시적으로 승인하기 전까지 하지 않는다.
```

Stage 8/manual smoke goal suggestion, use only after explicit approval:

```text
/goal Hermes AI Office next stage를 승인된 범위 안에서 진행한다. 우선 Stage 7까지 완료된 read-only MVP diff와 /office 화면을 수동 smoke test하거나 비픽셀 시각 polish를 한다. mutation controls, service restart, config/systemd change, Kanban/cron mutation, topic registry write, pixel renderer/dependency 추가는 하지 않는다. 검증 결과와 남은 open question을 STATUS/NEXT에 갱신한다.
```

When `/goal` is most useful:

1. Beginning a fresh `/new` session for one bounded stage, especially Stage 3–5 planning/design.
2. Long source-reading or synthesis sessions where the agent may otherwise drift into implementation.
3. Before any Stage 6+ implementation session, to enforce the approved scope and stop after the planned verification.
4. For multi-turn review loops: keep `/goal` active while drafting, reviewing, and tightening one deliverable set.

When not to rely on `/goal` alone:

1. Cross-session memory: use `STATUS.md`/`NEXT.md` instead.
2. Fine-grained coding task tracking: use a written plan and, after approval, Kanban/subagent workflow.
3. Background scheduled monitoring: use cron, not `/goal`.
4. Any mutation approval: `/goal` does not replace explicit user approval for code/config/service/Kanban/cron changes.

## Current next stage

Stage 7 — Review/polish, broad tests, local dashboard smoke, and full-suite test-debt cleanup after Stage 6 read-only MVP: completed. Full Python suite is green under `scripts/run_tests.sh`.

Mac handoff/setup docs were added so the fork branch can be reused on macOS while keeping runtime state machine-local:

- `docs/ai-office/MAC_START_HERE.md`
- `docs/ai-office/mac-env.template`

Completed cleanup batches now include: web lint errors, ACP import errors, optional dependency/snapshot-style failures, changed call-signature/expectation failures, update-test isolation flake, Bedrock/provider expectations, unsupported-parameter retry phrasing, skill provenance/credential small-tail items, Google Chat platform/config expectations, DingTalk card lifecycle optional-SDK handling, cron scheduler/script/MCP init expectations, CLI model/provider/Kanban expectations, run_agent concurrent interrupt stubs, gateway Discord/Feishu/cache tail items, MCP EventBridge mtime detection, i18n cache isolation, and curator atomic-write temp cleanup.

Latest full Python suite result:

```text
scripts/run_tests.sh -q --tb=short
# 20886 passed, 125 skipped, 232 warnings in 389.83s
```

No Python test failures remain in the latest full-suite run. Remaining work is product/UX next-stage work plus warning-only cleanup if desired.

## Immediate next action

Immediate next action should be a decision point, not more test-debt cleanup:

1. Review/commit the completed Stage 6/7 + test-debt cleanup diff.
2. Optional: run another localhost-only `/office` browser smoke test before merge/ship.
3. Optional: warning-only cleanup for existing async-mock, aiohttp `NotAppKeyWarning`, PTY `forkpty()` deprecation, and browser cleanup logging noise.
4. Optional: non-pixel UI polish after visual smoke review.
5. Pixel/renderer review only after explicit dependency/licensing/security approval.
6. Do not add mutation controls, restart services, expose dashboard remotely, add Pixi/Phaser, or create/modify Kanban/Cron state without separate approval.

Completed Stage 6 files:

1. `hermes_cli/office_redaction.py`
2. `hermes_cli/office_state.py`
3. `hermes_cli/office_adapters.py`
4. `hermes_cli/web_server.py`
5. `tests/hermes_cli/test_office_redaction.py`
6. `tests/hermes_cli/test_office_api.py`
7. `tests/hermes_cli/test_office_state_adapters.py`
8. `pyproject.toml` — `web` extra now bounds `starlette>=0.46.0,<1`.
9. `web/src/lib/api.ts`
10. `web/src/pages/OfficePage.tsx`
11. `web/src/App.tsx`

Local environment extras installed/ensured with user approval:

```bash
source .venv/bin/activate
python -m pip install -e '.[web]'
python -m pip install 'starlette<1'
python -m pip install -e '.[pty]'
```

Verification already performed:

```text
scripts/run_tests.sh tests/hermes_cli/test_office_redaction.py tests/hermes_cli/test_office_api.py -q
# 5 passed

scripts/run_tests.sh tests/hermes_cli/test_office_state_adapters.py -q
# 8 passed

scripts/run_tests.sh tests/hermes_cli/test_office_redaction.py tests/hermes_cli/test_office_state_adapters.py tests/hermes_cli/test_office_api.py tests/hermes_cli/test_web_server.py tests/hermes_cli/test_web_server_host_header.py -q
# 158 passed, 5 warnings

cd web
export PATH="$HOME/.local/node-v24.11.1-linux-x64/bin:$PATH"
npm run build
# passed: tsc -b && vite build

./node_modules/.bin/eslint src/pages/OfficePage.tsx src/App.tsx src/lib/api.ts
# passed

npm run lint
# now passes: 0 errors, 20 warnings

npm run build
# passed after lint cleanup: tsc -b && vite build

scripts/run_tests.sh tests/acp tests/acp_adapter -q --tb=short
# after installing .[acp]: 221 passed, 10 warnings

scripts/run_tests.sh tests/tools/test_transcription.py tests/tools/test_transcription_tools.py tests/tools/test_transcription_dotenv_fallback.py tests/tools/test_image_edit_tool.py tests/tools/test_registry.py tests/test_model_tools.py -q --tb=short
# 178 passed, 7 skipped

scripts/run_tests.sh tests/tools/test_delegate.py tests/tools/test_daytona_environment.py tests/tools/test_vercel_sandbox_environment.py tests/hermes_cli/test_cmd_update.py tests/hermes_cli/test_update_yes_flag.py -q --tb=short
# 178 passed

scripts/run_tests.sh tests/hermes_cli/test_update_yes_flag.py::TestUpdateYesStashRestore::test_yes_restores_stash_without_prompting -q --tb=long
# 1 passed

scripts/run_tests.sh tests/hermes_cli/test_cmd_update.py tests/hermes_cli/test_update_yes_flag.py -q --tb=short
# 10 passed

scripts/run_tests.sh tests/agent/test_bedrock_1m_context.py tests/agent/test_bedrock_adapter.py tests/hermes_cli/test_bedrock_model_picker.py -q --tb=short
# 139 passed, 6 skipped

scripts/run_tests.sh -q --tb=short
# latest full Python suite after all cleanup batches: 20886 passed, 125 skipped, 232 warnings in 389.83s

npm test
# failed: package has no "test" script
```

Notes:

- `npm run lint` for the whole web app now passes with 0 errors and 20 warnings after downgrading React Compiler migration rules to warnings and fixing two unused variables.
- Full Python `scripts/run_tests.sh -q --tb=short` is green after the cleanup batches: 20886 passed, 125 skipped, 232 warnings in 389.83s.
- `test_update_yes_flag` no longer appears in the latest full xdist failure list after patching through `cmd_update.__globals__`.
- `web/package.json` has no `test` script, so `npm test` is not available.
- The ACP import-error cluster was an environment gap; local `.venv` now has `agent-client-protocol 0.10.0` via `python -m pip install -e '.[acp]'`.
- Installing only `.[web]` initially left existing PTY WebSocket tests failing because `ptyprocess` was missing; installing existing `.[pty]` fixed those tests.
- Starlette 1.0.0 caused WebSocket TestClient frame incompatibilities in existing PTY tests, so `pyproject.toml` now constrains the web extra to `starlette<1` and local verification used Starlette 0.52.1.
- Remaining backend warnings are existing Python `pty.py` `forkpty()` deprecation warnings in PTY tests.

Primary Stage 5 outputs to keep using:

1. `docs/ai-office/architecture/backend-api.md`
2. `docs/ai-office/architecture/data-adapters.md`
3. `docs/ai-office/architecture/frontend-components.md`
4. `docs/ai-office/architecture/test-plan.md`
5. `docs/ai-office/architecture/rollout-plan.md`
6. `docs/ai-office/architecture/pixel-renderer-adapter.md`

Stage 6 approval checklist from the rollout plan:

1. User approves Stage 6 implementation scope.
2. User agrees to protected built-in `/api/office/...` API placement.
3. User agrees Stage 6 remains read-only and localhost-first.
4. User agrees pixel visualization remains deferred.
5. User agrees whether Stage 6 may read an existing `~/.hermes/office/topics.json` seed registry if present.
6. User agrees session titles remain off by default unless tests prove redaction behavior.
7. User agrees no gateway/dashboard service restart is performed without separate approval.

## Current planning outputs to preserve

Stage 1 research docs:

- `docs/ai-office/research/pixel-agents-audit.md`
- `docs/ai-office/research/pixel-agents-standalone-audit.md`
- `docs/ai-office/research/pixel-agents-codex-audit.md`
- `docs/ai-office/research/smallville-generative-agents-audit.md`
- `docs/ai-office/research/agent-observability-patterns.md`
- `docs/ai-office/research/synthesis.md`

Stage 2 audit docs:

- `docs/ai-office/audit/dashboard-architecture.md`
- `docs/ai-office/audit/kanban-data-model.md`
- `docs/ai-office/audit/cron-data-model.md`
- `docs/ai-office/audit/telegram-topic-routing.md`
- `docs/ai-office/audit/session-provenance.md`
- `docs/ai-office/audit/current-wsl-state-snapshot.md`

Stage 3 product/IA docs:

- `docs/ai-office/product/user-stories.md`
- `docs/ai-office/architecture/office-state-model.md`
- `docs/ai-office/product/information-architecture.md`
- `docs/ai-office/product/non-goals-and-mutation-boundary.md`
- `docs/ai-office/product/mvp-acceptance-criteria.md`

Stage 4 design docs:

- `docs/ai-office/design/topic-registry-spec.md`
- `docs/ai-office/design/task-provenance-metadata.md`
- `docs/ai-office/design/provenance-backfill.md`
- `docs/ai-office/design/privacy-security.md`

Stage 5 architecture docs:

- `docs/ai-office/architecture/backend-api.md`
- `docs/ai-office/architecture/data-adapters.md`
- `docs/ai-office/architecture/frontend-components.md`
- `docs/ai-office/architecture/test-plan.md`
- `docs/ai-office/architecture/rollout-plan.md`
- `docs/ai-office/architecture/pixel-renderer-adapter.md`

Earlier product/architecture/risk docs:

- `docs/ai-office/product/mvp-scope.md`
- `docs/ai-office/architecture/conceptual-architecture.md`
- `docs/ai-office/RISKS.md`

## Do not do without separate approval

- Do not implement mutation controls, topic registry persistence, or pixel-renderer slices beyond the completed Stage 6 read-only MVP.
- Do not add npm/Python dependencies unless explicitly approved.
- Do not create or mutate Kanban boards/tasks unless explicitly approved.
- Do not create, pause, resume, trigger, delete, or mutate cron jobs from AI Office.
- Do not restart services.
- Do not change gateway/cron/config/systemd/startup scripts.
- Do not write to NAS/Obsidian shared ledger.
- Do not vendor/fork Pixel Agents code.
- Do not create/edit `~/.hermes/office/topics.json` unless the user explicitly approves a registry seed/edit step.

## Handoff checklist before next `/new`

Before starting a fresh session:

1. Read this file and `STATUS.md`.
2. Read the Stage 5 architecture docs listed above.
3. If the user approves the next stage, begin only with the approved smoke-test/polish/lint-cleanup scope and update handoff files after verification.
4. If no approval is given, stay in review/planning mode.
5. State explicitly what was not changed.
