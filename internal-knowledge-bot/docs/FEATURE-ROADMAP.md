# Feature Roadmap

## v2 shipped (current)
- Hybrid retrieval scoring (semantic + lexical + freshness)
- Group-level access controls for docs
- Tenant policy engine (confidence threshold, force-handoff keywords, redaction)
- Governance audit events
- Analytics expansion (answer rate, confidence, keyword escalations)
- Role gates for risky actions (manager/admin)

## v2.1 shipped (this implementation)
- Async ingestion jobs + retry queue (`/api/documents/ingestion-jobs`, `/process`)
- Optional startup worker loop for background ingestion processing
- Better citation anchors:
  - chunk index
  - char offsets
  - section labels/page fields
  - source URL
- Source freshness auto-updater (`/api/documents/freshness/run`)
- Handoff SLA timers:
  - due_at on creation
  - acknowledge endpoint (`/api/handoffs/{id}/ack`)
  - breached status tracking + analytics metrics
- Policy validation endpoint + rules DSL (`/api/policy/validate`, `rules` in policy)

## Next step (v2.2)
- Worker health endpoint + queue depth metrics
- Source freshness adapters per provider (Notion/Drive/Slack-specific metadata)
- Better citation anchors for PDFs (real page offsets)
- Handoff escalation channels (Slack/email webhook notifications)

## v3
- SSO/OIDC + SCIM
- Vault-backed secrets for integration tokens
- Approval workflow for policy responses
- Multilingual retrieval & response
- Autodetected knowledge gaps with recommended SOP updates
