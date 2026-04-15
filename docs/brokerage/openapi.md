# Brokerage FastAPI Service

Local-only HTTP API for the deterministic brokerage engine.

## Run

```bash
uvicorn brokerage.app:app --host 127.0.0.1 --port 8787
```

Or:

```bash
python -m brokerage.app
```

## Authentication

When `brokerage.service_token` is configured, all trade-intent endpoints require:

```text
Authorization: Bearer <TOKEN>
```

`GET /healthz` is intentionally unauthenticated.

## Endpoints

### `GET /healthz`

Response:

```json
{
  "ok": true
}
```

### `POST /trade-intents`

Create a pending trade intent.

Request body:

```json
{
  "account_mode": "paper",
  "symbol": "AAPL",
  "side": "BUY",
  "quantity": 10,
  "order_type": "MARKET",
  "asset_class": "stock",
  "raw_request_text": "buy 10 shares of AAPL at market in paper"
}
```

Response:

```json
{
  "intent_id": "ti_123456789abc",
  "status": "pending_confirmation",
  "confirmation_code": "T-82K4",
  "preview": {
    "account_mode": "paper",
    "side": "BUY",
    "symbol": "AAPL",
    "quantity": 10,
    "order_type": "MARKET",
    "asset_class": "stock"
  },
  "expires_at": "2026-04-14T22:30:00+00:00"
}
```

### `POST /trade-intents/{intent_id}/confirm`

Submit a confirmation phrase for a pending intent.

Request body:

```json
{
  "confirmation_text": "CONFIRM T-82K4"
}
```

Response on accepted broker submission:

```json
{
  "intent_id": "ti_123456789abc",
  "status": "submitted",
  "broker_order_id": "ib-123",
  "broker_status": "Submitted",
  "detail": null
}
```

Response on broker rejection:

```json
{
  "intent_id": "ti_123456789abc",
  "status": "rejected",
  "broker_order_id": null,
  "broker_status": "Rejected",
  "detail": "insufficient buying power"
}
```

### `POST /trade-intents/{intent_id}/cancel`

Cancel a pending confirmation before broker submission.

Response:

```json
{
  "intent_id": "ti_123456789abc",
  "status": "cancelled",
  "account_mode": "paper",
  "symbol": "AAPL",
  "side": "BUY",
  "quantity": 10,
  "order_type": "MARKET",
  "asset_class": "stock",
  "confirmation_code": "T-82K4",
  "confirmation_expires_at": "2026-04-14T22:30:00+00:00",
  "created_at": "2026-04-14T22:28:00+00:00"
}
```

### `GET /trade-intents/{intent_id}`

Fetch the current stored state for an intent.

Response shape matches the persisted SQLite trade-intent row, including current `status`, `confirmation_code`, `confirmation_expires_at`, and `ibkr_order_id` when present.

## Error behavior

- `401 Unauthorized`
  - Missing bearer header when auth is enabled
  - Wrong bearer token
- `400 Bad Request`
  - Invalid order payload
  - Confirmation phrase mismatch
  - Cancel/confirm attempted from an invalid state
- `404 Not Found`
  - Unknown `intent_id`
