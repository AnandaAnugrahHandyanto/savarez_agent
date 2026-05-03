# BusinessOS Runbook

## Canonical paths

Workspace root:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS`

Repo root used for commands below:
- `/home/yuiop/.hermes/hermes-agent`

SQLite DB:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS/03_DATA/db/businessos.db`

Support env file:
- `/home/yuiop/.config/businessos/support-email.env`

## Primary docs to open first

1. `PROJECT.md`
2. `docs/architecture.md`
3. `docs/decisions.md`
4. `docs/open-questions.md`
5. latest files under `05_REPORTS/support/`, `05_REPORTS/tasks/`, `05_REPORTS/monthly/`, and `05_REPORTS/daily/`

## Run the pipeline manually

From `/home/yuiop/.hermes/hermes-agent`:

```bash
set -a && source /home/yuiop/.config/businessos/support-email.env >/dev/null 2>&1 && set +a
venv/bin/python BusinessOS/04_AUTOMATIONS/scripts/run_support_pipeline.py
```

What this should do currently:
- poll live IMAP intake
- poll live Telegram intake for the Steady support lane
- scan `00_INBOX/manual-drop/`
- auto-file eligible documents into `01_DOCUMENTS/`
- create/update tasks from task-formatted email and Telegram messages
- rebuild current support health/readiness and finance/task summaries
- emit operator Telegram updates and the previous-day summary when eligible
- mirror configured outputs to Dropbox

## Check current DB counts quickly

```bash
sqlite3 /home/yuiop/.hermes/hermes-agent/BusinessOS/03_DATA/db/businessos.db \
"SELECT 'documents', count(*) FROM documents
 UNION ALL SELECT 'communication_threads', count(*) FROM communication_threads
 UNION ALL SELECT 'communication_messages', count(*) FROM communication_messages
 UNION ALL SELECT 'feedback_items', count(*) FROM feedback_items
 UNION ALL SELECT 'feedback_clusters', count(*) FROM feedback_clusters
 UNION ALL SELECT 'bug_candidates', count(*) FROM bug_candidates
 UNION ALL SELECT 'feature_candidates', count(*) FROM feature_candidates
 UNION ALL SELECT 'source_accounts', count(*) FROM source_accounts
 UNION ALL SELECT 'ingestion_checkpoints', count(*) FROM ingestion_checkpoints;"
```

## Check the latest report outputs

Support reports:
```bash
find /home/yuiop/.hermes/hermes-agent/BusinessOS/05_REPORTS/support -maxdepth 1 -type f | sort | tail
```

Task reports:
```bash
find /home/yuiop/.hermes/hermes-agent/BusinessOS/05_REPORTS/tasks -maxdepth 1 -type f | sort | tail
```

Finance reports:
```bash
find /home/yuiop/.hermes/hermes-agent/BusinessOS/05_REPORTS/monthly -maxdepth 1 -type f | sort | tail
```

Daily summaries:
```bash
find /home/yuiop/.hermes/hermes-agent/BusinessOS/05_REPORTS/daily -maxdepth 1 -type f | sort | tail
```

## Check live memory state for Hermes

```bash
hermes memory status
sqlite3 ~/.hermes/memory_store.db '.tables'
sqlite3 ~/.hermes/memory_store.db 'SELECT fact_id, category, content FROM facts ORDER BY fact_id LIMIT 30;'
```

## Important configs

- `BusinessOS/04_AUTOMATIONS/configs/support-inboxes.yaml`
- `BusinessOS/04_AUTOMATIONS/configs/telegram-sources.yaml`
- `BusinessOS/04_AUTOMATIONS/configs/communication-lane-policy.yaml`
- `BusinessOS/04_AUTOMATIONS/configs/operator-updates.yaml`
- `BusinessOS/04_AUTOMATIONS/configs/dropbox-mirror.yaml`

## Safety checks before claiming the system is healthy

- verify the relevant scripts actually exist on disk
- verify current configs match the intended lanes
- verify the SQLite checkpoints and latest report timestamps moved after a run
- verify a fresh human-generated test message if the question is about live intake
- do not confuse historical DB population with fresh successful ingestion

## Current limitations to remember

- full historical downstream rebuild behavior is not fully restored yet
- outbound approval/send execution is still not the fully restored end state
- Holographic and Hindsight cannot both be active as external Hermes memory providers at the same time
