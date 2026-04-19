# Internal Knowledge Bot — Advanced v2.2

Confidentiality-first internal AI system for teams that need trustworthy answers from private knowledge.

## What is now included

- Tenant-aware auth (JWT)
- Role-based access (`admin`, `manager`, `employee`, `viewer`)
- Group-based access controls for documents
- Tenant policy engine:
  - policy packs (`safe`, `balanced`, `aggressive`)
  - minimum confidence threshold
  - force-handoff keywords
  - PII redaction toggle
  - citation limits
  - policy rules (mini DSL)
- Budget guardrails per tenant:
  - daily query budget
  - daily run budget
  - daily estimated cost budget (USD)
  - max `top_k`
  - max question size
- Hybrid retrieval (semantic + keyword + freshness weighting)
- Citation-rich grounded answers with anchors:
  - chunk index
  - char offsets
  - section label/page fields
  - source URL
- Ask idempotency (duplicate request replay by idempotency key)
- Run ledger + trace timeline:
  - run status, duration, input/output token estimate, cost estimate
  - step timeline (`validate_and_budget`, `retrieve`, `critic`, `repair`, `verify`)
  - run replay endpoint
- Async ingestion jobs with retry/backoff
- Human handoff queue with manager/admin controls
  - SLA due dates
  - acknowledge endpoint
  - breach tracking
- Source freshness updater (scheduled/manual run)
- Audit log events + JSON/CSV export
- Analytics expansion:
  - answer rate, confidence, keyword/rule escalations, handoff SLA metrics
  - usage snapshot + remaining budgets
  - run-level metrics
- Integration connectors scaffold (Slack, Notion, GDrive, Webhook)
- Landing page + operator console (updated for v2.2 features)

---

## Run backend

```bash
cd internal-knowledge-bot/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload --port 8787
```

Open:
- API docs: `http://localhost:8787/docs`
- Landing page: `internal-knowledge-bot/landing/index.html`
- Operator app: `internal-knowledge-bot/app/index.html`

---

## New API surface (v2.2)

### Governance & policy
- `GET /api/policy`
- `PUT /api/policy`
- `POST /api/policy/validate`

### Budget + operations
- `GET /api/analytics/usage`
- `GET /healthz` (includes ingestion queue depth + dead-letter count)

### Audit
- `GET /api/audit/events`
- `GET /api/audit/events/export?format=json|csv&limit=N`

### Run ledger
- `GET /api/analytics/runs?limit=N`
- `POST /api/analytics/runs/{run_id}/replay`

### Ask
- `POST /api/ask`
  - supports `idempotency_key`
  - returns `run_id`, `run_status`, `budget_enforced`
- `GET /api/ask/history`

### Existing core (still available)
- `POST /api/feedback`
- `POST /api/handoffs`
- `GET /api/handoffs`
- `POST /api/handoffs/{id}/ack`
- `POST /api/handoffs/{id}/resolve`
- `GET /api/analytics/overview`
- `GET /api/analytics/confidence-buckets`
- `GET /api/analytics/unanswered`
- `POST /api/documents/text`
- `POST /api/documents/upload`
- `GET /api/documents`
- `DELETE /api/documents/{id}`
- `POST /api/documents/ingestion-jobs`
- `GET /api/documents/ingestion-jobs`
- `POST /api/documents/ingestion-jobs/process`
- `POST /api/documents/freshness/run`
- `GET /api/groups`
- `POST /api/groups`
- `POST /api/groups/{group_id}/members/by-email`
- `DELETE /api/groups/{group_id}/members/{user_id}`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/users`

---

## Notes

- For existing local DB files from older versions, remove `knowledge_bot.db` once before first run to regenerate schema.
- If you enable background ingestion worker (`INGESTION_WORKER_ENABLED=true`), startup launches a lightweight worker loop that processes queued jobs.
- Cost/token values are estimates intended for guardrails and operator visibility.
