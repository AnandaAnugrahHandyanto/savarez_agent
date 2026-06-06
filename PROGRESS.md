# Progress: Fix Mac-persona auto-dispatch: repo inference + packet-landing
Card: t_cea89616
Branch: bld-cea89616-macroute
Started: 2026-06-06T13:25Z

## Checklist
- [x] Read card and estimated
- [x] Orient: git log, test suite, file structure
- [x] Study existing bld-5650-f856 Mac dispatch code (source branch)
- [x] Add MAC_PERSONAS constant + detect_crashed_workers skip
- [x] Add _mac_session_name, _set_mac_worker_info, _infer_mac_repo_path
- [x] Add fixed _spawn_mac_session (repo inference, preflight, launch verify)
- [x] Patch dispatch_once (ready + review) for Mac preclaim
- [x] Patch _default_spawn for Mac routing fallback
- [x] Add TestMacPersonaDispatch tests from bld-5650-f856
- [x] Add new tests: repo inference, t_2ad4b03f life-engine regression, t_d80003fa ccat-guru regression
- [x] Run tests (246 pass, 35 new)
- [x] Pushed to branch (fork: bld-cea89616-macroute)
- [x] Open PR: https://github.com/NousResearch/hermes-agent/pull/40516

## Acceptance Criteria Self-Check
- [x] AC1: No default to /projects/ccat — PASS (_infer_mac_repo_path defaults to hermes-agent)
- [x] AC2: ccat-guru resolves correctly — PASS (test_ccat_guru_beats_ccat, test_ccat_guru_via_title)
- [x] AC3: life-engine resolves correctly — PASS (test_life_engine_regression_t_2ad4b03f, test_life_engine_via_title)
- [x] AC4: herald resolves correctly — PASS (test_herald_workspace)
- [x] AC5: hermes-agent resolves correctly — PASS (test_hermes_infra_resolves_to_hermes_agent)
- [x] AC6: scout/unknown workspace falls back to hermes-agent — PASS (test_scout_unknown_workspace_falls_back_to_hermes_agent)
- [x] AC7: Preflight: Mac preclaim uses mac: lock, not conductor: — PASS (TestMacPersonaDispatch)
- [x] AC8: Claude launch verify before send — PASS (step 5 in _spawn_mac_session; SYNTHETIC noop)
- [x] AC9: mac: preclaim invariant — PASS (claimed events have mac:<session> lock)
- [x] AC10: host_local=False in metadata — PASS (test_task_runs_metadata_host_local_false)
- [x] AC11: Tests pass — PASS (246 total including 35 new)
- [x] AC12: No conductor:* transient lock — PASS (test_claimed_event_lock_starts_with_mac)

## Notes
- MAC_PERSONAS = builder, reviewer, scout, designer
- origin/main does NOT have _spawn_mac_session; porting from bld-5650-f856 + fixing
- Key fixes: repo_path default "ccat" -> infer via ordered map; wait for Claude idle before send
- HERMES_MAC_SYNTHETIC=1 suppresses actual bridge calls in tests
- claim_task/claim_review_task both accept claimer= kwarg (already in origin/main)
