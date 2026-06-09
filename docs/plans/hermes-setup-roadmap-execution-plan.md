# Hermes Docs Refresh + Setup Excellence — Execution Plan (M2a → M8 + M1 Handoff)

> Planning artifact only. No source/config/profile/gateway/cron mutation authorized by this document. All live probes flagged below require separate operator approval.

## 1. Executive summary

- **Critical path:** M1 PR handoff → M2a audit script → M2b live dogfood receipt → M2c promotion decision → M3 routing matrix → (M4 archetypes ∥ M5 gateway/cron) → M6 watcher → M7 hygiene → M8 optional.
- **M2 is the keystone.** Every later milestone (M3–M6) consumes the read-only receipt M2 produces; building them before a clean M2 receipt means guessing at runtime truth instead of reading it.
- **Biggest risk #1:** the operator-blocked compound probes. M2b *cannot* complete unattended — it needs live `hermes tools`/`portal`/`cron list`/`gateway status` runs that the approval layer gates. Treat M2b as an attended session, not a worker.
- **Biggest risk #2:** config-vs-runtime drift. Smart-routing flags in `config.yaml` can exist without the runtime symbols being importable; the audit must label every fact `Verified|Config-only`, never conflate.
- **Biggest risk #3:** WSL + 1.257 GB of suffixless `~/.local/bin` binaries. M1 fixed `profile list`, but any new probe that re-scans that dir (or shells broadly) re-introduces the 16s stall. Keep probes bounded.
- **Lightest path to value:** M1 PR + M2a/M2b in the next two sessions yields a real receipt; M3–M8 are then read-and-propose artifacts gated behind that evidence.

## 2. Dependency graph

```
M1 (DONE, committed) ──► M1-PR (operator "Push")
                            │
M2 spec (DONE) ─────────────┤
                            ▼
                          M2a  read-only audit script
                            │
                            ▼
                          M2b  live dogfood receipt  ◄── needs attended approvals
                            │
              ┌─────────────┼───────────────────────────┐
              ▼             ▼                            ▼
            M2c          M3 routing matrix          (receipt feeds all below)
        (promote,         │
         approval)        ▼
              ┌───────────┴───────────┐
              ▼                       ▼
        M4 archetypes/registry   M5 gateway+cron hygiene   ← independent, parallelizable
              └───────────┬───────────┘
                          ▼
                    M6 docs/User-Stories watcher
                          ▼
                    M7 skill/memory/wiki hygiene  (runs after source lands)
                          ▼
                    M8 optional exhaustive docs v2  (operator-triggered only)
```

**Hard blocks:** M2b ⟵ M2a; M2c ⟵ M2b; M3 ⟵ M2b receipt; M6 ⟵ M3 (watcher should know routing lanes); M7 ⟵ M1 merged + M3/M4 artifacts. **Soft/parallel:** M3, M4, M5 read the same M2b receipt and can be drafted concurrently as read-only artifacts.

---

## 3. Per-milestone sections

### M2a — Read-only audit script (workflow-local)

| | |
|---|---|
| **Objective** | Implement the G0–G7 ladder from `setup-gate-ladder-audit.md` as a deterministic read-only script that emits `receipt.json` + `synthesis.md`. |
| **Deliverables** | `~/.hermes/profiles/auto-coder/scripts/setup_gate_ladder_audit.py` (profile-local) **or** `/tmp/hermes-workflows/setup-gate-ladder/<run-id>/audit.py`. Receipts under `/tmp/hermes-workflows/setup-gate-ladder/<run-id>/`. |
| **Permission boundary** | Write only under `scripts/` (profile-local, **operator-approved path**) or `/tmp`. **Zero** mutation subprocess calls. No `config.yaml`/`.env`/profile/gateway/cron writes. |

**Tasks**
1. (S) Scaffold script + receipt schema v1 exactly per spec lines 108–131; hardcode `permission_boundary: "read-only"`.
2. (M) Implement G0–G7 probes as **read-only subprocess wrappers** with per-probe `timeout` and a `status: pass|warn|fail|skipped` envelope. Every probe captures stdout to `evidence`, never raises.
3. (M) Implement the secret-redaction layer (spec lines 102–106) as a single `redact()` chokepoint every `evidence` value passes through: `VAR=set|unset`, `sha256:abcd…`, deliver-target last-4.
4. (S) Implement `Verified` vs `Config-only` tagging: each gate reads config *and* attempts the runtime probe; mismatch → `blocker`.
5. (S) Mark all spend-bearing / mutation probes (G1 live smoke, any restart) as `skipped` + `blocker: approval_required` by default; gate behind a `--allow-live-smoke` flag that is **never** set in unattended runs.

**Acceptance criteria + verification**
- Script runs read-only and exits 0 with a receipt even when probes are skipped:
  `python ~/.hermes/profiles/auto-coder/scripts/setup_gate_ladder_audit.py --dry-run --out /tmp/hermes-workflows/setup-gate-ladder/$(printf %s dryrun)/`
- Static no-mutation grep gate (must return nothing):
  `grep -nE 'cron (create|update|remove)|gateway (start|stop|restart)|config.*write|open\(.+,[ ]*.w' ~/.hermes/profiles/auto-coder/scripts/setup_gate_ladder_audit.py`
- Schema validity: `python -c "import json,sys; json.load(open(sys.argv[1]))" <receipt.json>`
- Secret spot-check: `grep -niE 'sk-|api_key=|bearer |authorization' <receipt.json>` returns nothing.

**Approval gate / stop point:** Writing the script to the profile-local `scripts/` dir is the one side effect — confirm path with operator before first write (constraint: no profile mutation w/o approval; a new file under the profile arguably counts). If denied, fall back to `/tmp`. **Stop after script exists + `--dry-run` passes.** Do not run live probes here.

---

### M2b — Live dogfood receipt (attended)

| | |
|---|---|
| **Objective** | Produce the **one real read-only receipt** from the live `auto-coder` environment that M2's definition-of-done requires (spec line 145). |
| **Deliverables** | `/tmp/hermes-workflows/setup-gate-ladder/<run-id>/receipt.json` + `synthesis.md` from live state. |
| **Permission boundary** | Read-only execution. Each probe runs **only with operator present** because the approval layer gates compound probes (this blocked once already). |

**Tasks**
1. (S) Re-ground: `hermes --version`, `git -C /home/khall/.hermes/hermes-agent status --short --branch`.
2. (M) Run G0–G7 probes **one at a time, attended**, accepting each approval prompt. Record any `approval_denied` as `status: skipped` — **do not retry alternate phrasing** (spec stop rule, line 153).
3. (S) Verify `profile list` now completes <5s inside the receipt (this is M1's payoff feeding M2): `PYTHONPATH=/home/khall/.hermes/.worktrees/profile-list-fast-alias-scan timeout 5s hermes profile list`.
4. (S) Manual spot-check receipt for secrets; tag `Verified` vs `Config-only` per gate.

**Acceptance + verification**
- Receipt exists with ≥6 of G0–G6 at `pass|warn|skipped` (not `fail` from crashes).
- `overall` ∈ `{pass, needs_operator}`; `next_actions[]` non-empty and each tied to an `approval_gates` entry.
- Manual secret spot-check signed off by operator.

**Approval gates:** Each live probe (G1 provider, G2 portal, G5 cron list, G6 gateway status) is its own gate. **Stop point:** receipt written + operator confirms no secret material. Do **not** proceed to M2c in the same session.

---

### M2c — Promote to `hermes doctor setup --json` (approval-gated)

| | |
|---|---|
| **Objective** | After ≥1 dogfood receipt proves value, integrate the ladder into source as `hermes doctor setup --json`. |
| **Deliverables** | `hermes_cli/doctor.py` (modify) + `tests/hermes_cli/test_doctor*.py`. New worktree `khall/doctor-setup-audit`. |
| **Permission boundary** | Source edit in isolated worktree only. No push/PR/merge without "Push". |

**Tasks**
1. (S) New worktree from `origin/main`.
2. (M) Port the M2a script's gate functions into `doctor.py` behind a `setup` subcommand + `--json`; reuse the redaction chokepoint.
3. (M) TDD: write failing tests for schema shape, redaction, and `skipped`-on-denied before porting logic.
4. (S) Verify focused pytest + in-process `compile()` syntax check (not `py_compile`, per roadmap line 132).

**Acceptance + verification**
- `venv/bin/python -m pytest tests/hermes_cli/test_doctor*.py -q` passes.
- `hermes doctor setup --json | python -c "import json,sys;json.load(sys.stdin)"` validates.
- `git diff --check` clean.

**Approval gate:** **Do not start M2c until operator explicitly says the receipt proved value** (spec non-goal line 18). Stop at local commit.

---

### M3 — Routing matrix and spend/runaway policy

| | |
|---|---|
| **Objective** | Make model/tool routing explicit and verified against runtime symbols, not just config. |
| **Deliverables** | `docs/plans/routing-matrix.md` (artifact) + optional `scripts/routing_smoke.py` (no-network classifier check). |
| **Permission boundary** | Read-only artifact. No `config.yaml` edits. Live provider pings only behind a separate approved slice. |

**Tasks**
1. (S) Extract matrix fields (roadmap lines 180–190) into a table: lane, provider/model, cost tier, toolsets, network y/n, workdir, timeout/budget, fallback, smoke cmd, escalation.
2. (M) **Verify live before documenting** the remembered lanes — cheap=`gpt-5.4-mini`, routine=`gpt-5.3-codex`, hard=`gpt-5.5` (roadmap line 192). These are *remembered*, not confirmed; read actual `config.yaml model:` keys via M2b receipt.
3. (S) Add a no-network router/classifier smoke before any spend-bearing ping (roadmap line 199).
4. (S) Label every row `Verified|Config-only`.

**Acceptance + verification**
- Matrix distinguishes desired config from runtime truth (every row tagged).
- `python scripts/routing_smoke.py --no-network` exits 0 and asserts router resolves lanes without a network call.
- No `config.yaml` in `git diff`.

**Approval gate:** Any live completion ping is a spend gate — flag separately. Stop at artifact + no-network smoke.

---

### M4 — Least-privilege profile archetypes + worker registry

| | |
|---|---|
| **Objective** | Turn the 7 archetypes (roadmap lines 210–217) into a governed read-only registry **proposal**. |
| **Deliverables** | `docs/plans/profile-archetypes.md` + `docs/plans/worker-registry.md` (proposal only). |
| **Permission boundary** | **Read-only proposal.** Zero profile/config edits — profile creation/edit is explicitly approval-gated. |

**Tasks**
1. (S) Document archetypes: `safe-research`, `coder`, `reviewer`, `gateway`, `cron`, `kanban-worker`, `operator`.
2. (M) Build registry table (roadmap lines 219–230): profile id, role, model, toolsets, workdirs, mutation perms, gateway/cron ownership, credential *shape* (not values), last-smoke, rollback/disable cmd, approval gates.
3. (S) Populate from M2b receipt's live profile inventory (now fast post-M1), not from memory.
4. (S) Include per-worker auth/model preflight command per archetype.

**Acceptance + verification**
- Registry generated **before** any profile edit (it's a proposal doc).
- Every archetype names gateway + cron ownership explicitly.
- Cross-check profile ids against live: `PYTHONPATH=<worktree> timeout 5s hermes profile list`.

**Approval gate:** Implementing/editing actual profiles is a hard stop — proposal only. Parallelizable with M5.

---

### M5 — Gateway and cron hygiene

| | |
|---|---|
| **Objective** | Bring always-on surfaces under documented single-owner, approval-gated control. |
| **Deliverables** | `docs/plans/gateway-status-receipt.md`, `docs/plans/cron-inventory-receipt.md`, `docs/plans/service-repair-plan.md` (repair = proposal). |
| **Permission boundary** | Read-only inventory. **No gateway restart, no cron create/update/pause** without explicit approval. Single gateway owner respected. |

**Tasks**
1. (S) Read-only gateway status: owner profile / PID / service unit (attended, `hermes gateway status`).
2. (S) Read-only cron inventory: id, schedule, target profile, prompt/script, deliver target (redacted last-4), mutation risk class.
3. (M) Draft repair plan for any owner/service-definition mismatch — **with backup + rollback steps** — as a proposal, not an action.

**Acceptance + verification**
- Gateway owner/PID/unit identified and recorded.
- Every cron job classified by mutation risk.
- Repair plan includes rollback; **no restart executed.**

**Approval gate:** Gateway restart and any cron mutation are hard stops requiring explicit "go." Parallelizable with M4.

---

### M6 — Docs and User Stories watcher

| | |
|---|---|
| **Objective** | Detect upstream docs/User-Stories changes without re-running full swarms. |
| **Deliverables** | `scripts/hermes_docs_watcher.py` (no-agent) + local watermark file. Cron wiring deferred. |
| **Permission boundary** | Network fetch of public docs only (hashes/counts). No auto-rewrite, no auto skill-patch. Cron creation approval-gated. |

**Tasks**
1. (M) Fetch + hash: `docs/sitemap.xml`, `docs/llms.txt`, the `llms-full` asset, and `userStories.json` (raw GitHub) — **separately**, because story tiles are absent from `llms-full` (roadmap line 280).
2. (S) Store watermark locally; emit a report **only on change**, silent otherwise.
3. (S) On change: write a receipt + recommend a *bounded* docs-refresh workflow — never auto-run it.

**Acceptance + verification**
- `python scripts/hermes_docs_watcher.py` prints nothing on unchanged state, exits 0.
- Forced watermark mismatch produces a one-screen change report.
- User Stories checked independently of `llms-full`.

**Approval gate:** Registering this as cron is a hard stop (cron mutation). Stop at manual-run script.

---

### M7 — Skill/memory/wiki hygiene loop

| | |
|---|---|
| **Objective** | Make current setup knowledge durable; purge stale guidance after source lands. |
| **Deliverables** | Wiki integration of roadmap+receipts; `hermes-agent` skill hygiene pass; memory audit. |
| **Permission boundary** | Edits to skill reference docs + wiki only. Memory writes only on explicit operator trigger (per global injection guard). |

**Tasks**
1. (S) Remove stale `hermes login --provider`, raw-GitHub-installer, off-by-default redaction guidance from active skill docs.
2. (S) Wiki: point to receipt paths + official docs hashes so future sessions discover the roadmap without chat compaction.
3. (S) Memory audit: keep stable env/preference facts; task progress stays in session/wiki receipts, not memory.

**Acceptance + verification**
- `grep -rniE 'login --provider|raw\.githubusercontent.*install' <skill dir>` returns nothing in active docs.
- Wiki entry resolves to live receipt paths + official-docs hash.

**Approval gate:** Runs **after M1 merges** and M3/M4 artifacts exist. Memory writes only when operator says "wrap up / save this."

---

### M8 — Optional exhaustive docs refresh v2

| | |
|---|---|
| **Objective** | Decide whether the targeted scan becomes a full 344-page semantic reconciliation. |
| **Deliverables** | Per-section receipts + raw URL/source map under `/tmp/hermes-workflows/docs-refresh-v2/<run-id>/`. |
| **Permission boundary** | Read-only fetch; independently-verified skill edits only. No config/profile/gateway/cron mutation. |

**Tasks**
1. (M) Deterministic bulk collection first; partition by docs section/source type; cap per-worker source budget (worker-timeout lesson: one run hit 46 calls / ~200k tokens → 600s timeout kill).
2. (M) Per-section receipts; every changed local reference cites official URL/source handle.
3. (S) Independently verify any proposed skill edit before applying.

**Acceptance + verification**
- Every changed reference cites an official URL/source handle.
- Failed lanes explicitly reported (no silent truncation).

**Approval gate:** **Operator-triggered only** (roadmap line 304). Do not start speculatively.

---

## 4. PR strategy for M1

| Item | Detail |
|---|---|
| **Branch** | `khall/profile-list-fast-alias-scan` @ `3c434bc9a` |
| **First-PR contents** | **`3c434bc9a` only** — `hermes_cli/profiles.py` (+99/−29) and `tests/hermes_cli/test_profiles.py` (+51). **Exclude** `7ac50c864` (the M2 docs spec) from the M1 PR — it's a planning artifact, ship it separately or keep local. A reviewer wants the bug fix isolated. |
| **Fork vs upstream** | `origin` = upstream `NousResearch/hermes-agent`; `fork` = `SollanSystems/hermes-agent`. **Push to `fork`, open PR fork→`NousResearch:main` as a draft.** Never push branches to `origin` (upstream). |
| **Test evidence to cite** | (1) 130 profiles pytest passed; (2) the two new regression tests — large-suffixless-file-not-read + multi-profile bounded-scan; (3) live: `PYTHONPATH=/home/khall/.hermes/.worktrees/profile-list-fast-alias-scan timeout 5s hermes profile list` completes <5s vs prior ~16s; (4) `git diff --check` clean. |
| **PR body** | Root cause (per-profile full-file scan of 1.257 GB `~/.local/bin`), fix (one-pass bounded alias map, `_WRAPPER_ALIAS_MAX_BYTES` prefix cap), before/after timing (16s→0.15s alias-disabled baseline), preserved behaviors (custom-alias precedence, `.bat` strip, deterministic sort). |
| **Trigger** | Operator says **"Push"** = push to fork + open **draft** PR. Until then, M1 stays a local commit. |

**Pre-push checklist (run in worktree, attended):**
```bash
git -C /home/khall/.hermes/.worktrees/profile-list-fast-alias-scan log --oneline origin/main..HEAD
venv/bin/python -m pytest tests/hermes_cli/test_profiles.py tests/hermes_cli/test_subcommands_profile_gateway.py -q
git diff --check
PYTHONPATH=/home/khall/.hermes/.worktrees/profile-list-fast-alias-scan timeout 5s hermes profile list
```

---

## 5. Parallelization

| Can run as read-only sidecar (parallel-safe) | Must be serialized (attended / mutating) |
|---|---|
| M3 routing-matrix **artifact** drafting | M2b live dogfood (approval prompts, one probe at a time) |
| M4 archetypes/registry **proposal** | M2c source port (depends on M2b sign-off) |
| M5 gateway/cron **inventory read** (status reads can run; *plan* is doc-only) | M1 push/PR (operator "Push") |
| M6 watcher script authoring (no cron) | Any cron registration / gateway restart |
| M7 skill-doc grep/cleanup (text only) | Memory writes (explicit trigger only) |

**M4 ∥ M5** are the cleanest parallel pair — both consume the same M2b receipt, neither mutates, no shared files. Drafting M3 alongside is also safe. **Never** parallelize anything that shells `~/.local/bin` broadly or touches the single gateway owner.

---

## 6. Runtime allocation — Hermes vs Claude Code vs Kanban vs cron

| Milestone | Runtime | Why |
|---|---|---|
| M1 PR handoff | **In-session (attended)** | Push/PR needs operator "Push"; pre-push tests are interactive. |
| M2a script author | **Claude Code `-p` print / in-session** | Bounded single-file write; no agent fan-out needed. |
| M2b live dogfood | **In-session Hermes, attended** | Compound probes hit approval prompts — was operator-blocked once; cannot be a headless worker. |
| M2c source port | **In-session worktree (TDD)** | Production code = Opus-tier, attended commit. |
| M3 / M4 / M5 artifacts | **Claude Code print, read-only** | Doc synthesis from M2b receipt; cheap, parallelizable sidecars. |
| M6 watcher | **In-session author; cron steward later (approval)** | Script is bounded; cron registration is a deferred, gated steward job. |
| M7 hygiene | **In-session + `/wrap-up` + `/wiki-integrate`** | Memory/wiki writes require explicit trigger. |
| M8 docs v2 | **Bounded dynamic workflow / Kanban workers** | Only milestone justifying fan-out — partitioned, source-budgeted workers per the timeout lesson. |

**Subagent model routing (global contract):** read→Haiku, reason→Sonnet, write→Opus, each `Agent`/`agent()` call names `model:` explicitly. M8 workers reporting inventory = Haiku; M3/M4/M5 synthesis = Sonnet; M2c/M1 code = Opus.

---

## 7. Risks & pitfalls (top 8, environment-specific)

1. **`~/.local/bin` re-scan regression.** Any new probe (M2, M6) that walks `~/.local/bin` or greps wrappers re-creates the 16s stall M1 just killed. *Mitigation:* bound every dir scan with size/prefix caps; reuse M1's bounded helper, never raw `find`.
2. **Compound-probe approval block (recurrence).** M2b's chained probes already got operator-blocked once. *Mitigation:* attended, one probe per approval, `skipped`+`approval_denied` on deny, no alternate-phrasing retries.
3. **Config-vs-runtime conflation.** Smart-routing flags in `config.yaml` without importable runtime symbols → false "configured" reads. *Mitigation:* probe imports in the *authoritative checkout*; flag-without-symbol = `blocker`, never `pass`.
4. **Secret leakage into receipts.** Probes capturing `hermes tools`/`portal`/`mcp` output can surface keys/tokens. *Mitigation:* single `redact()` chokepoint; `grep -niE 'sk-|bearer|api_key'` gate before any receipt is shared.
5. **WSL path/PID mismatch (gateway).** WSL service/PID semantics differ from systemd; "outdated service definition" already observed. *Mitigation:* record unit + PID read-only, propose repair only, never restart.
6. **Stale-memory poisoning M3/M4.** Remembered lanes (`gpt-5.4-mini` etc.) and profile lists may be outdated. *Mitigation:* verify against live `config.yaml`/`profile list` before documenting; tag `Verified|Config-only`.
7. **Push to upstream `origin` by reflex.** `origin` is `NousResearch` (upstream); a habitual `git push origin` would target upstream main. *Mitigation:* push only to `fork`; draft PR; verify remote before push.
8. **Worker token blowout (M8).** Broad "docs + setup + recommend everything" prompt hit 46 calls / ~200k tokens → 600s kill. *Mitigation:* partition by section, cap source/tool budget per worker, preserve failed-lane accounting — never raise `child_timeout_seconds` to paper over scope.

---

## 8. Recommended next 3 sessions

### Session A — M1 PR handoff (attended, ~30 min)
- **Goal:** Get the verified M1 fix onto the fork as a draft PR.
- **Entry prompt:**
  > Load hermes-agent skill. In worktree `/home/khall/.hermes/.worktrees/profile-list-fast-alias-scan`, re-verify M1: run `git log --oneline origin/main..HEAD`, the focused pytest (`tests/hermes_cli/test_profiles.py` + `test_subcommands_profile_gateway.py`), `git diff --check`, and `PYTHONPATH=<worktree> timeout 5s hermes profile list`. Report output. Then **wait for "Push"** before pushing commit `3c434bc9a` only to remote `fork` and opening a draft PR to `NousResearch:main`. Exclude the M2 docs commit `7ac50c864`.
- **Exit receipt:** test output + timing pasted; on "Push," draft PR URL on fork.

### Session B — M2a audit script (attended author, ~1 hr)
- **Goal:** Build the read-only G0–G7 audit script; pass `--dry-run`; no live probes.
- **Entry prompt:**
  > Load hermes-agent + hermes-dynamic-workflows. Read `docs/plans/setup-gate-ladder-audit.md`. Implement `setup_gate_ladder_audit.py` (confirm whether profile-local `scripts/` or `/tmp` — ask before writing under the profile). Schema v1 per spec; single `redact()` chokepoint; all spend/mutation probes default `skipped`+`approval_required`. Verify: `--dry-run` exits 0, schema validates, no-mutation grep returns nothing, secret grep returns nothing. Do **not** run live probes.
- **Exit receipt:** script path + `--dry-run` receipt + grep-gate output (both empty).

### Session C — M2b live dogfood (attended, ~45 min)
- **Goal:** Generate the one real read-only receipt M2 requires; spot-check secrets.
- **Entry prompt:**
  > Attended M2b run. Execute the M2a script's G0–G7 probes **one at a time**, accepting each approval prompt; on any denial record `skipped`+`approval_denied` and do not retry. Include `PYTHONPATH=<worktree> timeout 5s hermes profile list` to confirm <5s. After the receipt is written, do a manual secret spot-check together and tag each gate Verified|Config-only. Stop — do not start M2c or M3.
- **Exit receipt:** `receipt.json` + `synthesis.md` paths; `overall` verdict; operator's secret-clean sign-off. This receipt is the input that unlocks M3/M4/M5.

> Flagged for separate approval before they run live: every G1/G2/G5/G6 probe in Session C; any M3 provider ping; M5 gateway status read; all cron registration (M6) and gateway restart (M5).