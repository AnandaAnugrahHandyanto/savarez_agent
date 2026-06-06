# Progress: Mac-persona preclaim fix
Card: t_3d90fb92
Branch: bld-3d90-audit
Started: 2026-06-06T02:55Z

## Checklist
- [x] Read card and estimated
- [x] Add MAC_PERSONAS constant + _mac_session_name() helper
- [x] Add _spawn_mac_session() function
- [x] Add _set_mac_worker_info() function
- [x] Modify dispatch_once ready-loop: Mac personas claim with mac:<session>
- [x] Modify dispatch_once review-loop: same fix
- [x] Add focused tests for mac claim event shape (22 tests, all pass)
- [x] python3 -m py_compile hermes_cli/kanban_db.py passes
- [x] Tests passing: 233 kanban_db + 22 new mac dispatch = all green
- [ ] Pushed to branch

## Notes
- MAC_PERSONAS = {builder, reviewer, scout, designer}
- Session name shape: <profile>-<task_id_without_t_> e.g. builder-aec2624f
- When HERMES_MAC_SYNTHETIC=1: skip SSH, just record claim/metadata
- Previous impl f856808e6c45 not on origin/main — implementing full from clean base
- claim_task() and claim_review_task() both accept claimer= kwarg
