# Profile archetypes (M4 proposal)

> Least-privilege **intent** definitions. Does not change any live profile.  
> Live inventory: M2b + `PYTHONPATH=<M1-worktree> hermes profile list` (2026-06-09).

## Archetypes

### safe-research
- **Purpose:** Web/search/read-only synthesis; receipts only.
- **Mutation:** none (no write_file, patch, git commit, cron create).
- **Network:** web/search allowed; no deploy/push.
- **Gateway/cron:** must not own gateway; no cron steward role.
- **Preflight:** `hermes -p <id> doctor` (read-only); credential shape `OPENROUTER_API_KEY` or search keys = set.

### coder
- **Purpose:** Isolated worktree implementation slices.
- **Mutation:** source edits in assigned worktree only; **no push/PR/merge** without operator.
- **Network:** yes for deps/docs.
- **Gateway/cron:** no ownership.
- **Preflight:** `git status` clean scope; `pytest` target path; profile `.env` present.

### reviewer
- **Purpose:** Read-only PR/diff/test review; verdict receipt.
- **Mutation:** none.
- **Network:** optional (GitHub API via gh).
- **Gateway/cron:** no ownership.
- **Preflight:** `gh auth status`; reviewer profile `.env` if API needed.

### gateway
- **Purpose:** **Single** messaging/voice owner for the fleet.
- **Mutation:** no code mutation; gateway run/restart is approval-gated.
- **Network:** yes (platform adapters + MCP).
- **Gateway/cron:** **owns** gateway unit; does not own unrelated cron stewards unless explicitly assigned.
- **Preflight:** `hermes -p <id> gateway status`; exactly one `running` gateway across fleet.

### cron
- **Purpose:** Recurring watchers; script or bounded agent ticks.
- **Mutation:** no dangerous commands; **no recursive cron creation** in job prompts.
- **Network:** as required by watcher script.
- **Gateway/cron:** runs **under** a profile; cron mutations require operator.
- **Preflight:** `hermes cron list`; job `profile` field matches intended owner.

### kanban-worker
- **Purpose:** Board-assigned tasks only; isolated worktrees; live auth/model smoke before spawn.
- **Mutation:** per card scope; no board/credential repair without approval.
- **Network:** per lane (impl may need git/network).
- **Gateway/cron:** no gateway ownership.
- **Preflight:** block spawn if `~/.hermes/profiles/<id>/.env` missing and provider requires keys; `hermes -p <id> profile show` + cheap no-network config read.

### operator
- **Purpose:** High-trust interactive profile (you).
- **Mutation:** broad, but config/profile/gateway/cron/credential changes remain **explicit approval**.
- **Network:** yes.
- **Gateway/cron:** may **host** gateway + scheduled jobs (current: `auto-coder`).
- **Preflight:** M2 setup gate ladder receipt before large setup changes.

## Mapping live profiles → proposed archetype

| Profile | Proposed archetype | Notes |
|---------|-------------------|--------|
| `auto-coder` | **operator** + **gateway** | Only profile with gateway **running**; hosts cron jobs in M2b |
| `gateway-minimal` | gateway (standby) | Must stay **stopped** while `auto-coder` owns gateway |
| `kanban-impl` | kanban-worker | Implementation lane; **no `.env`** — spawn risk |
| `kanban-triage` | kanban-worker | Triage lane; **no `.env`** |
| `kanban-review` | kanban-worker + reviewer | Has `.env` |
| `kanban-pr` | kanban-worker | PR lane; **no `.env`** |
| `kanban-merge-steward` | kanban-worker | Merge steward; **no `.env`** |
| `kanban-ops-steward` | kanban-worker | Ops steward; **no `.env`** |
| `builder` | coder | OpenRouter mini model |
| `default` | operator (legacy) | Multi-provider; avoid new work here |
| `hoc-canary` | safe-research / canary | Stopped gateway |
| `lcm-test` | coder (experimental) | Test profile |
| `mcplab` | safe-research | MCP experiments |
| `worker-minimal` | kanban-worker (minimal) | No model line in list — verify before dispatch |

## Gateway ownership rule (proposal)

**Canonical owner:** `auto-coder` (`hermes-gateway-auto-coder.service`, verified M2b).

All other profiles with gateway capability (`gateway-minimal`, etc.) remain **stopped** unless operator runs an approval-gated ownership transfer procedure (documented in M5 repair plan).

## Cron ownership rule (proposal)

Cron jobs observed on `auto-coder` (M2b): nightly retrospective, daily AI edge briefing, portable backup sync. **Proposal:** keep cron definitions on operator profile until a dedicated `cron-steward` profile is explicitly approved and credentialed.

## Approval gates before implementing registry

- Creating/editing profiles or copying `.env` between profiles
- Starting a second gateway profile
- Assigning Kanban workers without `.env` / provider smoke
- Pinning models across profiles fleet-wide