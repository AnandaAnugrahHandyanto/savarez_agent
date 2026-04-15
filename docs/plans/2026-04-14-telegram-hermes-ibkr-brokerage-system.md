# Telegram → Hermes → IBKR Brokerage System Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build an open-source, extensible brokerage workflow where a user sends a natural-language trade request to Hermes over Telegram, Hermes creates a pending structured trade intent, the user explicitly confirms it in chat, and deterministic code submits the order to IBKR paper trading first and live trading later.

**Architecture:** Keep the LLM in the UI/intent-formation role only. Actual validation, confirmation state, risk checks, persistence, and broker submission must live in deterministic Python code behind a local FastAPI service. Hermes should integrate with that service via a custom tool so the execution layer stays testable, auditable, and reusable across Telegram and other Hermes gateways.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, SQLite (stdlib `sqlite3`), `ib_insync`, `httpx`, Hermes tool registry, pytest, pytest-asyncio.

---

## Non-Goals for v1

- No options, futures, forex, crypto, or short selling
- No autonomous trading or strategy execution
- No direct LLM-to-broker order placement without confirmation
- No broker abstraction beyond IBKR in the first release, though the code should be broker-extensible
- No Telegram-specific inline-button UX in v1; use confirmation messages with deterministic tokens first

## Core Safety Rules

1. The assistant never directly places a trade from raw natural language.
2. Every request becomes a `pending` trade intent first.
3. The user must explicitly confirm with an exact confirmation token before submission.
4. Paper and live must be separate modes with distinct confirmations and config.
5. The deterministic service enforces all policy checks before broker submission.
6. Every state transition is durably logged.

## Recommended Repository Layout

```text
brokerage/
├── __init__.py
├── config.py
├── models.py
├── storage.py
├── policy.py
├── service.py
├── app.py
└── brokers/
    ├── __init__.py
    ├── base.py
    └── ibkr_tws.py

tools/
└── brokerage_tool.py

tests/
├── brokerage/
│   ├── test_models.py
│   ├── test_storage.py
│   ├── test_policy.py
│   ├── test_service.py
│   ├── test_app.py
│   └── test_ibkr_tws.py
└── tools/
    └── test_brokerage_tool.py

docs/
├── plans/
│   └── 2026-04-14-telegram-hermes-ibkr-brokerage-system.md
└── brokerage/
    ├── README.md
    └── openapi.md
```

---

## Task 0: Prepare git workspace safely

**Objective:** Start from a clean, reviewable workspace before implementation.

**Files:**
- No code changes required

**Step 1: Inspect git status**

Run:
```bash
git status --short --branch
```
Expected: See current branch and any unrelated modified/untracked files.

**Step 2: Avoid mixing unrelated work**

If unrelated files are present, either commit/stash them first or create a fresh worktree.

Preferred:
```bash
git fetch origin
git worktree add ../hermes-brokerage-worktree -b feat/brokerage-telegram-ibkr origin/main
```

Fallback in the current tree only after cleaning unrelated files:
```bash
git checkout -b feat/brokerage-telegram-ibkr
```

**Step 3: Verify clean workspace**

Run:
```bash
git status --short
```
Expected: no unrelated changes.

**Step 4: Commit**

No commit for this task.

---

## Task 1: Add packaging and config scaffolding for the brokerage subsystem

**Objective:** Make the repo capable of shipping a brokerage subsystem and optional trading dependencies.

**Files:**
- Modify: `pyproject.toml`
- Modify: `hermes_cli/config.py`
- Create: `brokerage/__init__.py`
- Create: `brokerage/config.py`
- Test: `tests/brokerage/test_models.py`

**Step 1: Write failing test for config defaults**

Create `tests/brokerage/test_models.py` with a first test like:
```python
from brokerage.config import BrokerageSettings


def test_brokerage_settings_defaults_to_paper_mode_and_local_service():
    settings = BrokerageSettings()
    assert settings.service_url == "http://127.0.0.1:8787"
    assert settings.default_account_mode == "paper"
    assert settings.confirmation_ttl_seconds == 120
```

**Step 2: Run test to verify failure**

Run:
```bash
pytest tests/brokerage/test_models.py::test_brokerage_settings_defaults_to_paper_mode_and_local_service -v
```
Expected: FAIL because `brokerage.config` does not exist yet.

**Step 3: Add minimal implementation**

Create:
- `brokerage/__init__.py`
- `brokerage/config.py`

Implement a `BrokerageSettings` Pydantic model with at least:
- `service_url: str = "http://127.0.0.1:8787"`
- `service_token: str | None = None`
- `default_account_mode: Literal["paper", "live"] = "paper"`
- `confirmation_ttl_seconds: int = 120`
- `allowed_asset_classes: tuple[str, ...] = ("stock",)`

Modify `pyproject.toml`:
- add `"brokerage", "brokerage.*"` to `[tool.setuptools.packages.find].include`
- add optional extra:
```toml
trading = [
  "fastapi>=0.104.0,<1",
  "uvicorn[standard]>=0.24.0,<1",
  "ib_insync>=0.9.86,<1",
]
```

Modify `hermes_cli/config.py`:
- add a `brokerage` section to `DEFAULT_CONFIG`
- add `BROKERAGE_SERVICE_TOKEN` to optional env vars if appropriate

**Step 4: Run test to verify pass**

Run:
```bash
pytest tests/brokerage/test_models.py::test_brokerage_settings_defaults_to_paper_mode_and_local_service -v
```
Expected: PASS.

**Step 5: Run targeted regression checks**

Run:
```bash
pytest tests/brokerage/test_models.py -v
```
Expected: PASS.

**Step 6: Commit**

```bash
git add pyproject.toml hermes_cli/config.py brokerage/__init__.py brokerage/config.py tests/brokerage/test_models.py
git commit -m "feat: add brokerage config scaffolding"
```

---

## Task 2: Define domain models for trade intents and state transitions

**Objective:** Create explicit typed models for pending confirmations, broker submissions, and audit events.

**Files:**
- Create: `brokerage/models.py`
- Modify: `tests/brokerage/test_models.py`

**Step 1: Write failing tests for domain models**

Add tests for:
- valid paper trade intent
- invalid live mode without stricter confirmation requirements
- allowed order types (`market`, `limit`)
- status transitions (`pending_confirmation`, `confirmed`, `submitted`, `filled`, `rejected`, `cancelled`, `expired`)

Example:
```python
from brokerage.models import TradeIntent


def test_trade_intent_normalizes_symbol_to_uppercase():
    intent = TradeIntent(
        request_id="r1",
        account_mode="paper",
        symbol="aapl",
        side="buy",
        quantity=10,
        order_type="market",
        asset_class="stock",
    )
    assert intent.symbol == "AAPL"
    assert intent.side == "BUY"
```

**Step 2: Run tests to verify failure**

Run:
```bash
pytest tests/brokerage/test_models.py -v
```
Expected: FAIL because `TradeIntent` does not exist.

**Step 3: Write minimal implementation**

In `brokerage/models.py`, define:
- `TradeIntent`
- `TradeConfirmation`
- `BrokerSubmissionResult`
- `TradeEvent`
- enums/literals for account mode, side, order type, status

Rules:
- normalize `symbol` uppercase
- normalize `side` uppercase (`BUY`/`SELL`)
- support only `asset_class="stock"` in v1
- `limit_price` required for limit orders, forbidden for market orders

**Step 4: Run tests to verify pass**

Run:
```bash
pytest tests/brokerage/test_models.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add brokerage/models.py tests/brokerage/test_models.py
git commit -m "feat: add brokerage domain models"
```

---

## Task 3: Build SQLite persistence for intents and audit events

**Objective:** Persist intents and every state transition durably for traceability and recovery.

**Files:**
- Create: `brokerage/storage.py`
- Create: `tests/brokerage/test_storage.py`

**Step 1: Write failing tests**

Add tests covering:
- schema initialization
- insert trade intent
- update status
- fetch by `intent_id`
- append audit event
- expire stale pending intents

**Step 2: Run tests to verify failure**

Run:
```bash
pytest tests/brokerage/test_storage.py -v
```
Expected: FAIL because storage module does not exist.

**Step 3: Write minimal implementation**

Implement a `SQLiteBrokerageStore` using stdlib `sqlite3`.

Database location:
- `get_hermes_home() / "brokerage" / "brokerage.db"`

Create tables:
- `trade_intents`
- `trade_events`

Minimum columns on `trade_intents`:
- `intent_id`
- `created_at`
- `status`
- `account_mode`
- `symbol`
- `side`
- `quantity`
- `order_type`
- `limit_price`
- `asset_class`
- `confirmation_code`
- `confirmation_expires_at`
- `telegram_chat_id` (optional metadata only; keep generic naming if preferred)
- `session_id`
- `ibkr_order_id`
- `raw_request_text`

**Step 4: Run tests to verify pass**

Run:
```bash
pytest tests/brokerage/test_storage.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add brokerage/storage.py tests/brokerage/test_storage.py
git commit -m "feat: add brokerage sqlite persistence"
```

---

## Task 4: Implement deterministic policy and risk checks

**Objective:** Enforce guardrails before any broker submission.

**Files:**
- Create: `brokerage/policy.py`
- Create: `tests/brokerage/test_policy.py`

**Step 1: Write failing tests**

Cover these rules:
- paper and live are explicit only
- only stocks allowed in v1
- only market and limit orders allowed in v1
- quantity must be positive integer
- block notional above configured cap
- block expired confirmation tokens
- require stronger confirmation phrase for live mode

**Step 2: Run tests to verify failure**

Run:
```bash
pytest tests/brokerage/test_policy.py -v
```
Expected: FAIL.

**Step 3: Write minimal implementation**

Implement:
- `PolicyDecision`
- `BrokeragePolicy`
- `validate_new_intent(intent, market_snapshot=None)`
- `validate_confirmation(intent, confirmation_text)`

Configuration knobs:
- `paper_max_shares`
- `paper_max_notional`
- `live_enabled`
- `live_max_shares`
- `live_max_notional`
- `allowed_symbols` / `blocked_symbols` (optional simple lists)

**Step 4: Run tests to verify pass**

Run:
```bash
pytest tests/brokerage/test_policy.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add brokerage/policy.py tests/brokerage/test_policy.py
git commit -m "feat: add brokerage policy engine"
```

---

## Task 5: Add broker adapter interface and IBKR TWS implementation

**Objective:** Isolate IBKR-specific behavior behind a stable broker interface.

**Files:**
- Create: `brokerage/brokers/__init__.py`
- Create: `brokerage/brokers/base.py`
- Create: `brokerage/brokers/ibkr_tws.py`
- Create: `tests/brokerage/test_ibkr_tws.py`

**Step 1: Write failing tests**

Cover:
- paper mode chooses paper port
- live mode chooses live port
- adapter maps `BUY/SELL` + `market/limit` into IB order objects
- adapter rejects unsupported asset classes/order types
- submission response captures broker order id/status

**Step 2: Run tests to verify failure**

Run:
```bash
pytest tests/brokerage/test_ibkr_tws.py -v
```
Expected: FAIL.

**Step 3: Write minimal implementation**

In `brokerage/brokers/base.py` define:
- `BrokerAdapter` protocol / abstract base class
- `submit_order(intent) -> BrokerSubmissionResult`
- `get_order_status(order_id)`
- `cancel_order(order_id)`

In `brokerage/brokers/ibkr_tws.py` implement `IBKRTwsBrokerAdapter` using `ib_insync`.

Defaults from IBKR docs:
- TWS live: `7496`
- TWS paper: `7497`
- IB Gateway live: `4001`
- IB Gateway paper: `4002`

Prefer IB Gateway defaults in examples, but keep ports configurable.

Do not require a real TWS/IB Gateway session in tests. Mock `ib_insync.IB`.

**Step 4: Run tests to verify pass**

Run:
```bash
pytest tests/brokerage/test_ibkr_tws.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add brokerage/brokers/__init__.py brokerage/brokers/base.py brokerage/brokers/ibkr_tws.py tests/brokerage/test_ibkr_tws.py
git commit -m "feat: add ibkr tws broker adapter"
```

---

## Task 6: Build the brokerage service state machine

**Objective:** Centralize create/confirm/cancel/submit logic in deterministic code.

**Files:**
- Create: `brokerage/service.py`
- Create: `tests/brokerage/test_service.py`

**Step 1: Write failing tests**

Cover:
- creating a new intent returns a confirmation code and `pending_confirmation`
- confirming with wrong token fails
- confirming after expiry fails
- confirming with valid token moves to `submitted` when broker accepts
- broker rejection moves to `rejected`
- cancelling pending intent moves to `cancelled`
- intent IDs and confirmation codes are one-time use

**Step 2: Run tests to verify failure**

Run:
```bash
pytest tests/brokerage/test_service.py -v
```
Expected: FAIL.

**Step 3: Write minimal implementation**

Implement a `BrokerageService` that composes:
- `BrokerageSettings`
- `SQLiteBrokerageStore`
- `BrokeragePolicy`
- `BrokerAdapter`

Public methods:
- `create_intent(...)`
- `confirm_intent(intent_id, confirmation_text)`
- `cancel_intent(intent_id)`
- `get_intent(intent_id)`
- `expire_stale_intents()`

Generate confirmation codes like `T-82K4` or longer. Keep them short enough for Telegram, but unguessable enough for safe single-user use.

**Step 4: Run tests to verify pass**

Run:
```bash
pytest tests/brokerage/test_service.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add brokerage/service.py tests/brokerage/test_service.py
git commit -m "feat: add brokerage service state machine"
```

---

## Task 7: Expose the service over FastAPI

**Objective:** Make the deterministic brokerage engine available to Hermes through a local HTTP API.

**Files:**
- Create: `brokerage/app.py`
- Create: `tests/brokerage/test_app.py`
- Create: `docs/brokerage/openapi.md`

**Step 1: Write failing API tests**

Cover these endpoints:
- `GET /healthz`
- `POST /trade-intents`
- `POST /trade-intents/{intent_id}/confirm`
- `POST /trade-intents/{intent_id}/cancel`
- `GET /trade-intents/{intent_id}`

Use `fastapi.testclient.TestClient`.

**Step 2: Run tests to verify failure**

Run:
```bash
pytest tests/brokerage/test_app.py -v
```
Expected: FAIL.

**Step 3: Write minimal implementation**

Implement a FastAPI app bound locally only.

Use a bearer token header for Hermes → service requests, for example:
- `Authorization: Bearer <BROKERAGE_SERVICE_TOKEN>`

Suggested response shape for create:
```json
{
  "intent_id": "ti_123",
  "status": "pending_confirmation",
  "confirmation_code": "T-82K4",
  "preview": {
    "account_mode": "paper",
    "side": "BUY",
    "symbol": "AAPL",
    "quantity": 10,
    "order_type": "MARKET"
  }
}
```

Add a small `main()` so users can run:
```bash
uvicorn brokerage.app:app --host 127.0.0.1 --port 8787
```

**Step 4: Run tests to verify pass**

Run:
```bash
pytest tests/brokerage/test_app.py -v
```
Expected: PASS.

**Step 5: Document the API**

Write `docs/brokerage/openapi.md` summarizing endpoints, auth header, and sample payloads.

**Step 6: Commit**

```bash
git add brokerage/app.py tests/brokerage/test_app.py docs/brokerage/openapi.md
git commit -m "feat: add brokerage fastapi service"
```

---

## Task 8: Add Hermes brokerage tools that call the local service

**Objective:** Let Hermes convert chat messages into structured intents and confirmations without embedding broker logic in the LLM loop.

**Files:**
- Create: `tools/brokerage_tool.py`
- Modify: `model_tools.py`
- Modify: `toolsets.py`
- Create: `tests/tools/test_brokerage_tool.py`

**Step 1: Write failing tool tests**

Cover:
- tool registration succeeds
- create-intent tool sends expected payload to local service
- confirm-intent tool forwards confirmation text and intent id
- cancel-intent tool works
- service errors become JSON errors
- tool availability is gated by config/token presence

**Step 2: Run tests to verify failure**

Run:
```bash
pytest tests/tools/test_brokerage_tool.py -v
```
Expected: FAIL.

**Step 3: Write minimal implementation**

Create `tools/brokerage_tool.py` with these initial tools:
- `create_trade_intent`
- `confirm_trade_intent`
- `cancel_trade_intent`
- `get_trade_intent_status`

Recommended schema for `create_trade_intent`:
- `account_mode`
- `symbol`
- `side`
- `quantity`
- `order_type`
- `limit_price` (optional)
- `asset_class` (default `stock`)
- `time_in_force` (optional, default `DAY`)
- `raw_user_text` (optional; persisted for audit)

Tool description must instruct the model:
- create pending intent first
- never submit a trade without confirmation
- if the user has not confirmed, do not call confirm tool

Modify `model_tools.py` to import `tools.brokerage_tool` in `_discover_tools()`.

Modify `toolsets.py`:
- add toolset `brokerage`
- do not include it in `_HERMES_CORE_TOOLS` yet unless you explicitly want this enabled everywhere

**Step 4: Run tests to verify pass**

Run:
```bash
pytest tests/tools/test_brokerage_tool.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add tools/brokerage_tool.py model_tools.py toolsets.py tests/tools/test_brokerage_tool.py
git commit -m "feat: add hermes brokerage tools"
```

---

## Task 9: Write end-to-end paper-trading tests with a fake broker

**Objective:** Prove the full intent → confirm → submit flow without requiring a live IBKR session.

**Files:**
- Modify: `tests/brokerage/test_service.py`
- Modify: `tests/tools/test_brokerage_tool.py`
- Optionally create: `tests/brokerage/test_end_to_end.py`

**Step 1: Write failing tests**

Add an end-to-end case:
1. create AAPL paper market intent
2. receive confirmation code
3. confirm exact code
4. fake broker returns accepted order id
5. final status is `submitted`

Add a rejection case too.

**Step 2: Run tests to verify failure**

Run:
```bash
pytest tests/brokerage/test_end_to_end.py -v
```
Expected: FAIL.

**Step 3: Write minimal implementation**

Use a fake broker implementation in tests only. Do not modify production logic beyond what is needed for dependency injection.

**Step 4: Run tests to verify pass**

Run:
```bash
pytest tests/brokerage/test_end_to_end.py -v
pytest tests/brokerage/ tests/tools/test_brokerage_tool.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/brokerage tests/tools/test_brokerage_tool.py
git commit -m "test: add end-to-end brokerage flow coverage"
```

---

## Task 10: Document local development and paper-trading operation

**Objective:** Make the feature understandable and open-source-ready for contributors and users.

**Files:**
- Create: `docs/brokerage/README.md`
- Modify: `README.md`
- Optionally create: `examples/brokerage.env.example`

**Step 1: Write docs-first checklist**

Document:
- what the subsystem does
- current v1 limitations
- required dependencies
- how to run IB Gateway paper locally
- API/TWS settings from IBKR docs
- default ports:
  - TWS live 7496
  - TWS paper 7497
  - IB Gateway live 4001
  - IB Gateway paper 4002
- how to run the local FastAPI service
- how Hermes is configured to talk to it
- security warnings for live mode

**Step 2: Add README section**

Update the top-level `README.md` with a short section linking to `docs/brokerage/README.md`.

**Step 3: Verify docs paths**

Run:
```bash
python -m pytest tests/brokerage/ tests/tools/test_brokerage_tool.py -q
```
Expected: PASS.

**Step 4: Commit**

```bash
git add docs/brokerage/README.md README.md examples/brokerage.env.example
git commit -m "docs: add brokerage setup and usage guide"
```

---

## Task 11: Add a live-mode feature gate without enabling it by default

**Objective:** Prepare for live trading safely while keeping v1 paper-only in practice.

**Files:**
- Modify: `brokerage/config.py`
- Modify: `brokerage/policy.py`
- Modify: `tests/brokerage/test_policy.py`

**Step 1: Write failing tests**

Cover:
- live mode blocked when `live_enabled=False`
- live mode requires explicit stronger confirmation phrase
- live mode has stricter size/notional caps than paper

**Step 2: Run tests to verify failure**

Run:
```bash
pytest tests/brokerage/test_policy.py -v
```
Expected: FAIL.

**Step 3: Write minimal implementation**

Add config:
- `live_enabled: bool = False`
- `live_max_shares`
- `live_max_notional`

Add confirmation rule like:
```text
CONFIRM LIVE BUY 10 AAPL T-82K4
```

**Step 4: Run tests to verify pass**

Run:
```bash
pytest tests/brokerage/test_policy.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add brokerage/config.py brokerage/policy.py tests/brokerage/test_policy.py
git commit -m "feat: add gated live trading safeguards"
```

---

## Task 12: Run final verification and integration review

**Objective:** Confirm the subsystem is ready for paper-trading trials and open-source iteration.

**Files:**
- No new files required

**Step 1: Run focused suite**

Run:
```bash
pytest tests/brokerage/ tests/tools/test_brokerage_tool.py -v
```
Expected: PASS.

**Step 2: Run broader regression suite**

Run:
```bash
python -m pytest tests/ -o 'addopts=' -q
```
Expected: PASS.

**Step 3: Review diff**

Run:
```bash
git diff --stat origin/main...
```
Expected: only brokerage-related files and intentional config/package changes.

**Step 4: Manual paper smoke test**

With IB Gateway Paper running and API enabled:
```bash
uvicorn brokerage.app:app --host 127.0.0.1 --port 8787
```
Then in Hermes over Telegram, try:
```text
Buy 1 share of AAPL at market in paper
```
Expected:
- Hermes produces a pending confirmation preview
- Hermes does not submit immediately
- confirming with exact code submits through paper mode
- status response includes broker order id or simulated broker response

**Step 5: Final commit if needed**

```bash
git add -A
git commit -m "feat: complete telegram hermes ibkr brokerage paper trading flow"
```

---

## Design Notes

### Why a local FastAPI service instead of putting everything in the Hermes tool?

- Keeps broker logic deterministic and independently testable
- Makes future non-Hermes clients possible
- Keeps the Hermes tool thin and auditable
- Makes eventual open-sourcing cleaner

### Why SQLite first?

- Zero extra infra
- Easy local development
- Good fit for audit logs and pending intents
- Easy to swap later behind a repository interface

### Why `ib_insync`?

- Much simpler ergonomics than raw IB API
- Well-documented connect pattern
- Easy to mock in tests

### Why no Telegram inline buttons in v1?

- Text confirmation is messaging-platform-agnostic
- Much less gateway coupling
- Easier to open source and test
- Hermes already supports Telegram chat input, so no extra gateway work is required to get the first version working

### Telegram-specific future enhancement

After paper-mode stability, add optional Telegram inline confirmation buttons by reusing patterns already covered by:
- `gateway/platforms/telegram.py`
- `tests/gateway/test_telegram_approval_buttons.py`

That should be a separate feature branch after v1 is stable.

---

## Suggested Execution Order

1. Task 0
2. Task 1
3. Task 2
4. Task 3
5. Task 4
6. Task 5
7. Task 6
8. Task 7
9. Task 8
10. Task 9
11. Task 10
12. Task 11
13. Task 12

This order ensures the core deterministic engine exists before Hermes integration.

---

## Open Questions to resolve during implementation

1. Should the default broker connection assume IB Gateway or TWS? Recommendation: IB Gateway.
2. Should confirmation codes be short human tokens only, or full exact phrases from v1? Recommendation: short token for paper, exact full phrase for live.
3. Should market quotes be fetched before preview to estimate notional? Recommendation: no for initial implementation unless quote access is already available; keep quantity/notional caps conservative first.
4. Should the initial Hermes tool be hidden behind an explicit `brokerage` toolset? Recommendation: yes.

---

## Definition of Done

- User can send a Telegram message to Hermes describing a paper stock trade
- Hermes creates a structured pending intent via the brokerage tool
- Hermes returns a confirmation preview and token
- User confirms with exact required text
- Deterministic service validates and submits to IBKR paper through `ib_insync`
- Order status is stored and returned
- Every step is tested and logged
- Live mode remains disabled by default
- Setup and contributor docs exist for open-source users
