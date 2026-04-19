# Deployment Runbook

## Local
```bash
cd internal-knowledge-bot/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8787
```

## Production baseline
- API behind Nginx/Caddy
- Postgres + pgvector
- Redis + worker
- S3/R2 for documents
- TLS + CORS allowlist + rate limiting
- audit retention enabled
