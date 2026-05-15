# Multi-Agent Routing E2E Validation — Matrix → code Agent

**Date:** 2026-05-15  
**Scope:** Single-gateway-multi-agent feature (PR #25532+). Verify that the Matrix platform routes to a dedicated `code` agent while existing platforms (weixin, wecom) continue to route correctly.  
**Environment:** Local Dendrite homeserver (`@hermes-bot:localhost`), Element Web client.

---

## 1. Routing Resolution

### TC-01: Matrix DM routes to `code`
**Purpose:** Confirm that a Matrix DM triggers the `code` agent, not `main`.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Open Element Web, start a DM with `@hermes-bot:localhost`. | Bot auto-joins room. |
| 2 | Send: `hello` | Gateway log shows `inbound message: platform=matrix ...` and session key contains `agent:code`. |
| 3 | Check `~/.hermes/logs/gateway.log` for the line. | `agent:code:matrix:dm:!u00jd7u1b1WqHly1:localhost` (or similar). |

**Pass:** Session key prefix is `agent:code:matrix:...`.

### TC-02: Matrix room routes to `code`
**Purpose:** Confirm that a Matrix room (not DM) also routes to `code`.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Create a public room `#test-room:localhost` and invite `@hermes-bot:localhost`. | Bot joins room. |
| 2 | Send a message mentioning the bot. | Gateway log shows `agent:code:matrix:group:...` or `agent:code:matrix:channel:...`. |

**Pass:** Session key contains `agent:code`.

### TC-03: Weixin still routes to `main` (default)
**Purpose:** Regression — weixin must continue using the default `main` agent.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Send any message to the weixin bot. | Gateway log shows `agent:main:weixin:...`. |

**Pass:** Session key prefix is `agent:main:weixin:...`.

### TC-04: WeCom still routes to `wecom-agent`
**Purpose:** Regression — explicit wecom route must remain intact.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Send any message to the wecom bot. | Gateway log shows `agent:wecom-agent:wecom:...`. |

**Pass:** Session key prefix is `agent:wecom-agent:wecom:...`.

### TC-05: Unknown platform falls back to `default_agent`
**Purpose:** If a new platform is added without a route, it must fall back to `default_agent` (`main`).

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | (Simulated via unit test — see `test_agent_routing.py::TestResolveAgentId::test_no_match_returns_default`) | `resolve_agent_id(source, routes, default="main")` returns `"main"`. |

**Pass:** Unit test passes.

---

## 2. Profile Isolation

### TC-10: `code` agent sessions are isolated from `main`
**Purpose:** Messages handled by `code` must not leak into `main`'s session DB.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Send a message from Matrix. | `~/.hermes/profiles/code/sessions.json` gains a new entry with key containing `matrix`. |
| 2 | Send a message from weixin. | `~/.hermes/sessions.json` (main) gains a new entry with key containing `weixin`. |
| 3 | Verify no `matrix` key exists in `~/.hermes/sessions.json`. | `grep matrix ~/.hermes/sessions.json` returns empty. |

**Pass:** Matrix sessions only in `code` profile; weixin sessions only in `main` profile.

### TC-11: `code` agent memory is isolated
**Purpose:** Memory files (USER.md, MEMORY.md) must be per-profile.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Send from Matrix: "记住我叫 Alice" | Response acknowledges. |
| 2 | Check `~/.hermes/profiles/code/memory/` | Contains `USER.md` or `MEMORY.md` with "Alice". |
| 3 | Check `~/.hermes/memory/` | Does **not** contain "Alice" (or is unchanged from before). |
| 4 | Send from weixin: "我叫谁？" | `main` agent does not know "Alice". |

**Pass:** Memory is physically separated by profile directory.

### TC-12: `code` agent SOUL.md is independent
**Purpose:** Each agent can have its own system prompt.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Write a custom `SOUL.md` into `~/.hermes/profiles/code/SOUL.md` with a distinctive trait (e.g. "You only speak in Python code comments."). | File exists. |
| 2 | Restart gateway (`hermes gateway restart`). | Gateway starts without errors. |
| 3 | Send from Matrix: "introduce yourself" | Response reflects the custom SOUL.md (e.g. starts with `#`). |
| 4 | Send from weixin: "introduce yourself" | Response reflects `~/.hermes/SOUL.md` (default), not the code agent's. |

**Pass:** Per-agent SOUL.md is loaded and applied.

---

## 3. Model & Toolset Configuration

### TC-20: `code` agent inherits correct model
**Purpose:** The `code` agent config specifies `model: kimi-for-coding` / `provider: moonshot`.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Run `hermes agent show code`. | Output shows `Model: kimi-for-coding`, `Provider: moonshot`. |
| 2 | Send a message from Matrix and inspect gateway log. | API call uses `kimi-for-coding` (log line `model=kimi-for-coding`). |

**Pass:** Model matches config.

### TC-21: `main` agent model unchanged
**Purpose:** Regression — `main` must not be affected by `code` agent's model.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Send from weixin. | API call uses the global default model (`kimi-for-coding` in this env). |

**Pass:** `main` continues to use its configured/default model.

---

## 4. Gateway Lifecycle & Resilience

### TC-30: Gateway restart preserves routing config
**Purpose:** Config must survive restart.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Run `hermes gateway restart`. | Gateway starts, all platforms connect. |
| 2 | Check `hermes agent list`. | Shows `code` with 1 route (`platform: matrix`). |
| 3 | Send from Matrix. | Still routes to `code`. |

**Pass:** No config loss across restart.

### TC-31: Removing `code` agent gracefully
**Purpose:** Agent removal must clean up registry and warn about orphaned routes.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Run `hermes agent remove code`. | CLI warns: "Route(s) still reference 'code'...". |
| 2 | Confirm removal with `--yes`. | Agent removed from `config.yaml`. |
| 3 | Restart gateway. | Matrix messages fall back to `main` (default_agent). |

**Pass:** Graceful degradation; no crash.

---

## 5. Backward Compatibility

### TC-40: Single-agent install unaffected
**Purpose:** Existing installs without `agents:` / `routes:` must behave exactly as before.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | (Simulated) Temporarily rename `~/.hermes/config.yaml` to `config.yaml.bak`, restore a pre-multi-agent config, restart gateway. | All messages route to `main`; session keys are `agent:main:...`. |
| 2 | Restore modern config. | Re-test TC-01–TC-04. |

**Pass:** Zero behavioral change for legacy configs.

---

## Appendix: Quick Commands

```bash
# Verify routing config
hermes agent list
hermes agent show code

# Tail gateway logs
tail -f ~/.hermes/logs/gateway.log | grep -E "inbound message|agent:code|agent:main|agent:wecom"

# Check session isolation
ls ~/.hermes/profiles/code/sessions.json
ls ~/.hermes/sessions.json

# Check memory isolation
ls ~/.hermes/profiles/code/memory/
ls ~/.hermes/memory/
```
