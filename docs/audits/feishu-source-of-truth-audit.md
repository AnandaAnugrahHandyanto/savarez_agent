# Feishu Source of Truth Audit

**Date:** 2026-06-02
**Auditor:** Codex
**Scope:** Identify where Feishu integration lives and whether Phase 5 refactor is safe

---

## 1. File Inventory

### Feishu-related files in this repository

| File | Lines | Role |
|------|-------|------|
| `gateway/platforms/feishu.py` | 5101 | **Core Feishu platform adapter** — WebSocket/Webhook transport, message receive/send, approval handling, card buttons, reaction events |
| `gateway/platforms/feishu_comment.py` | ~200 | Comment/review helpers for Feishu message threads |
| `gateway/platforms/feishu_comment_rules.py` | ~150 | Rules for Feishu comment processing |
| `gateway/platforms/helpers.py` | ~300 | Shared platform helpers (includes Feishu-specific HTTP client limits) |
| `gateway/platforms/_http_client_limits.py` | ~50 | HTTP rate limit configuration (Feishu referenced) |
| `gateway/platforms/base.py` | ~500 | BasePlatformAdapter ABC — FeishuAdapter inherits this |
| `gateway/run.py` | ~5600 | GatewayRunner — starts/stops/manages all platform adapters including Feishu |
| `gateway/config.py` | ~300 | Platform enum includes FEISHU; config loading |
| `gateway/session.py` | ~200 | Session key builder used by FeishuAdapter |
| `tools/send_message_tool.py` | ~400 | Cross-platform send tool (Feishu target regex, send logic) |
| `tools/feishu_doc_tool.py` | ~150 | Feishu document/cloud drive tool |
| `tools/feishu_drive_tool.py` | ~150 | Feishu drive file operations |
| `tests/gateway/test_feishu_comment.py` | ~100 | Tests for Feishu comment helpers |
| `tests/gateway/test_feishu_comment_rules.py` | ~80 | Tests for Feishu comment rules |
| `tests/gateway/feishu_helpers.py` | ~50 | Test fixtures for Feishu tests |

### Feishu-related files NOT in this repository

| Expected path | Status | Notes |
|---------------|--------|-------|
| `hermes_cli/feishu_martini_bot/main.py` | **NOT FOUND** | Referenced in memory as "马尔蒂尼/Maldini" bot; appears to be external deployment code or a separate repository |

---

## 2. Current Integration Architecture

### How Feishu messages flow today

```
Feishu WS/Webhook → gateway/platforms/feishu.py
                        ↓
                    FeishuAdapter._on_message_event()
                        ↓
                    _process_inbound_message()
                        ↓
                    _dispatch_inbound_event()
                        ↓
                    GatewayRunner._route_message()
                        ↓
                    agent execution (conversation_loop / delegate_tool)
```

### Key architectural facts

1. **FeishuAdapter is a `BasePlatformAdapter` subclass**, not an `EntryAdapter`.
2. **It handles its own transport** (WebSocket thread, webhook server, token refresh).
3. **It has its own session model** (`session_key` built from `chat_id:thread_id:platform:bot_name`).
4. **It dispatches directly to agent execution** via `GatewayRunner._route_message()`.
5. **It handles approvals, reactions, card buttons** internally — these are NOT normalized through any common event model.
6. **It has its own dedup logic** (`_dedup_state`, `_pending_inbound`).
7. **It uses lark_oapi SDK** for Feishu API calls.

### Session model in FeishuAdapter

```python
# gateway/session.py
session_key = build_session_key(
    chat_id,      # Feishu chat/open_chat ID
    thread_id,    # Feishu thread/root_id if any
    "feishu",
    bot_name
)
```

This session key is **not** the same as the v2.10 `Session.session_id` model.

---

## 3. What "马尔蒂尼" / Feishu Bot Actually Is

The user has a Feishu bot nicknamed "马尔蒂尼" (Maldini). Based on memory:
- It is a Feishu bot bridge that connects Feishu messages to Hermes
- It may live in a **separate repository or deployment** (e.g. `~/hermes-projects/feishu-martini-bot/`)
- It is NOT in this repository's `hermes_cli/feishu_martini_bot/`
- This repo's `gateway/platforms/feishu.py` is the **platform adapter** that the bot would call into

**Risk:** If "马尔蒂尼" is external deployment code, Phase 5 must not assume it can be modified in this repo.

---

## 4. Gap Analysis: FeishuAdapter vs EntryAdapter Model

### What FeishuAdapter CAN do today

| Capability | Status | How |
|-----------|--------|-----|
| Receive messages | ✅ | WebSocket/Webhook handlers |
| Send messages | ✅ | `_send_message()` with media support |
| Thread/reply context | ✅ | `thread_id` from `message.root_id` |
| Session isolation | ✅ | `session_key` per chat+thread |
| Approval buttons | ✅ | Interactive card buttons with callback |
| Reaction events | ✅ | Synthetic text events from reactions |
| Dedup | ✅ | `_dedup_state` per session |
| Gateway health | ✅ | Adapter health via `GatewayRunner` |

### What FeishuAdapter CANNOT do (vs EntryAdapter model)

| Capability | Status | Gap |
|-----------|--------|-----|
| Emit `EntryEvent` | ❌ | No normalization to common event schema |
| Workspace resolution | ❌ | No `Workspace` model integration |
| Session binding store | ❌ | Session keys are ephemeral strings, not persisted `Session` records |
| Adapter isolation | ❌ | FeishuAdapter dispatches directly to agent execution, not via Hermes Core |
| Approval-only mode | ❌ | Feishu is primary message handler, not notification/approval-only |
| Ambiguity guard | ❌ | No explicit `UnsupportedEntryPointError` equivalent |

---

## 5. What Can Be Refactored in This Repo

### Safe to refactor (this repo)

1. **Add FeishuEntryAdapter class** that wraps FeishuAdapter's inbound event handling
2. **Normalize Feishu events to EntryEvent** in the new adapter
3. **Add thread-to-session binding** using v2.10 `SessionBinding` store
4. **Add workspace resolution** (guild/chat → workspace, thread → session)
5. **Keep FeishuAdapter transport intact** — do not touch WebSocket/Webhook logic
6. **Add approval/notification mode** config (primary vs notification-only)

### Requires external repo / deployment changes

1. **"马尔蒂尼" bot deployment** — if it has its own repo, it needs its own Phase 5
2. **Bot registration / app_id rotation** — if managed externally
3. **Feishu app credentials** — already env-var based, no code change needed

---

## 6. Recommended Phase 5 Implementation Slices

### Slice A: FeishuEntryAdapter (safe, this repo)

Create `agent/managed_agents/feishu_entry_adapter.py`:
- Implements `EntryAdapter` protocol
- Wraps `FeishuAdapter`'s inbound event → `EntryEvent`
- Maps: chat_id → workspace, thread_id → session
- Preserves Feishu transport logic untouched

### Slice B: Session binding integration (safe, this repo)

- Store Feishu `session_key` → `Session` binding in `SessionBinding` store
- Read binding on inbound message to resolve workspace/session
- Fallback to default workspace/session if no binding exists

### Slice C: Approval/notification mode config (safe, this repo)

- Add config flag: `FEISHU_MODE = "primary" | "notification"`
- Primary = current behavior (full message handling)
- Notification = only approvals, status checks, quick commands
- This maps to the ADR's "Feishu role" recommendation

### Slice D: Gateway refactor (higher risk)

- Change `GatewayRunner` to route Feishu events through `EntryAdapterRegistry`
- This touches `gateway/run.py` and `gateway/platforms/feishu.py`
- Should be done carefully with backward compatibility

---

## 7. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| FeishuAdapter transport is complex (5101 lines) | Medium | Do not touch transport; only wrap inbound event normalization |
| External "马尔蒂尼" bot may be separate repo | Low | Phase 5 focuses on adapter normalization; external bot can adopt later |
| Session key model differs from v2.10 Session model | Medium | Add mapping layer; do not replace existing session_key |
| GatewayRunner directly calls agent execution | Medium | Introduce EntryAdapter routing as optional path first |
| Approval/card button handling is Feishu-specific | Low | Keep in FeishuAdapter; EntryAdapter only handles text/message events |

---

## 8. Go / No-Go Recommendation

**Recommendation: GO for Phase 5 Slice A + B + C.**

- Feishu platform adapter exists in this repo and is well-structured
- It can be wrapped without modifying transport
- Session binding can be added as a mapping layer
- Approval/notification mode is a config addition
- No external repo changes required for core refactor

**Defer Slice D** (GatewayRunner refactor) until Slices A-C are validated.

---

## 9. Key Files for Phase 5

```
gateway/platforms/feishu.py          # Existing — DO NOT modify transport
gateway/platforms/base.py            # Existing — BasePlatformAdapter
gateway/run.py                       # Existing — GatewayRunner
gateway/session.py                   # Existing — session_key builder
agent/managed_agents/entry_adapter.py     # v2.10 Phase 3 — EntryAdapter protocol
agent/managed_agents/entry_event.py         # v2.10 Phase 1 — EntryEvent model
agent/managed_agents/session_binding.py   # v2.10 Phase 1 — SessionBinding store
configs/managed_agents/agents.yaml   # Agent configs (may need capability contracts)
```
