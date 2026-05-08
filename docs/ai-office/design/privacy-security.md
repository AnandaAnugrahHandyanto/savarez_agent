# Hermes AI Office — Stage 4 Privacy and Security Classification

Last updated: 2026-05-08 12:05 KST
Status: Stage 4 provenance/routing design. Documentation-only; no implementation approved.

## Purpose

AI Office exists to make Hermes operational state visible, but Hermes state can include private prompts, transcripts, tool outputs, local paths, credentials, Telegram identifiers, cron scripts, and logs. This document classifies fields for the read-only MVP and future provenance design.

## Security posture

Stage 4 recommendation:

1. MVP is localhost-first and read-only.
2. Browser API should return redacted projections only, not raw source objects.
3. Future remote/Tailscale/public modes require separate security review.
4. Plugin route authentication gap found in Stage 2 must be resolved before exposing OfficeState through plugin HTTP routes.
5. No mutation endpoints or service controls are part of MVP.

## Classification levels

| Level | Meaning | Default MVP behavior |
|---|---|---|
| Public-safe metadata | Low-risk operational metadata | Show after normal validation |
| Internal routing metadata | Useful locally but identifies private infrastructure | Show in localhost only or hash/label depending policy |
| Sensitive content | User/private/task content | Hide by default; maybe redacted summary later |
| Secret | Credentials/tokens/auth material | Never read for display, never return |
| Dangerous control | Actions that mutate runtime/security state | Not present in MVP |

## Field classification matrix

| Field/category | Classification | Localhost MVP | Future remote mode | Notes |
|---|---|---|---|---|
| `OfficeState.schema_version` | Public-safe metadata | Show | Show | DTO contract |
| `generated_at` | Public-safe metadata | Show | Show | Safe timestamp |
| data-source status/counts | Public-safe metadata | Show | Show | Must not mask failures as zero |
| Kanban board id/name | Public-safe metadata | Show | Show after redaction | Board names can still reveal projects; redaction pass recommended |
| Kanban task id | Internal routing metadata | Show | Hash or hide by default | Needed for local troubleshooting |
| Kanban task title | Sensitive-ish metadata | Show only after redaction pass | Hide or redacted/title-off by default | Titles may contain content/secrets |
| Kanban status/priority/assignee | Public-safe/internal metadata | Show after redaction pass | Show/hash assignee as needed | Assignee may be person/profile name |
| Task body/result/comments | Sensitive content | Hide | Hide | Link to existing detail only after review |
| Worker logs/tool output | Sensitive content | Hide | Hide | High leakage risk |
| Raw task event payload | Sensitive content | Hide/summarize kind only | Hide/summarize | Event kind/status transition is safer |
| Diagnostic kind/severity | Public-safe metadata | Show | Show | Error summary must be redacted |
| Stack traces | Sensitive content | Redacted summary only | Redacted summary only | Paths/secrets may appear |
| Cron job id/name | Public-safe/internal metadata | Show after redaction pass | Show/hash id as needed | Name normally safe |
| Cron schedule/state/timestamps | Public-safe metadata | Show | Show | Operational health |
| Cron `deliver` target | Internal routing metadata | Normalize and show label/id per mode | Label/hash only | Do not show token/env |
| Cron `origin` | Internal routing metadata | Normalize if structured | Label/hash only | Missing origin must be unknown |
| Cron prompt/script/context/output | Sensitive content | Hide | Hide | Script path may be path-sensitive |
| Cron last error | Sensitive-ish content | Redacted summary | Redacted summary | Current timeout summary is acceptable after path redaction policy |
| Output artifact count | Public-safe metadata | Show count only | Show count only | Raw output hidden |
| Output artifact path | Internal/path metadata | Hide or redact | Hide | Absolute paths can leak profile/home |
| Platform name (`telegram`) | Public-safe metadata | Show | Show | Source type is useful |
| Telegram chat id | Internal routing metadata | Show only as internal or hash | Hash/hide | Less sensitive than token but private infrastructure id |
| Telegram thread id | Internal routing metadata | Show in local mode when useful | Hash/hide or label only | Topic label preferred |
| Telegram topic name | Sensitive-ish metadata | Show after registry/redaction | Show only if approved | Names may reveal project/domain |
| Telegram message id | Internal routing metadata | Hide or internal display | Hide/hash | No message URLs by default |
| Telegram sender user id | Internal personal metadata | Hide/hash | Hide/hash | Prefer display role, not id |
| Telegram sender display name | Personal metadata | Redact or hide by default | Hide | Need separate policy |
| Telegram message text/snippet | Sensitive content | Hide | Hide | No raw messages in MVP |
| Session id | Internal routing metadata | Show local/internal | Hash/hide | Useful for debugging |
| Session source | Public-safe metadata | Show | Show | `cli`, `telegram`, `cron` |
| Session title | Sensitive-ish metadata | Off by default or redacted | Hide by default | Decide in Stage 5 |
| Session preview/snippet | Sensitive content | Hide by default | Hide | Search snippets may leak prompts |
| Session counts/model/timestamps | Public-safe/internal metadata | Show | Show with provider policy | Model/base URL may need redaction if custom endpoint |
| System prompt | Sensitive content | Hide | Hide | Never default Office content |
| Reasoning fields | Sensitive content | Hide | Hide | Never default Office content |
| Tool args/tool calls/tool output | Sensitive content | Hide | Hide | High leakage risk |
| `.env` values/API keys/tokens | Secret | Never show | Never show | Do not read for UI display |
| `auth.json`/credential pool | Secret | Never show | Never show | Never return |
| Absolute home/cache/log paths | Internal/path metadata | Redact or show only if necessary | Hide | Paths can reveal usernames/projects |
| Gateway/service status | Public-safe/internal metadata | Read-only summary only if in scope | Read-only summary after review | No restart controls |
| Config/tool/model settings | Internal/security metadata | Mostly out of MVP | Out of MVP | Existing dashboard may handle separately |

## Display modes

### Localhost/internal mode

Default for Stage 6 if approved.

Allowed with labels:

- internal ids when operationally useful, clearly marked `internal`,
- topic labels from registry,
- session ids,
- board/task ids,
- redacted error summaries.

Still hidden:

- raw transcripts,
- tool args/output,
- cron prompt/script/output,
- credentials,
- bot tokens,
- raw Telegram message text,
- system prompts/reasoning.

### Future remote mode

Requires separate security review. Default should be:

- labels over ids,
- hashes over raw chat/user/session ids,
- no title/preview unless explicitly approved,
- stricter path hiding,
- no raw logs/errors beyond compact codes.

## Redaction rules

Every future serializer should apply at least:

1. Secret pattern removal: API keys, tokens, bearer strings, Telegram bot token patterns.
2. Credential file/path suppression: `.env`, `auth.json`, credential pool references.
3. Email/phone/user id handling depending display mode.
4. Absolute path redaction under home, `.hermes`, OneDrive, NAS, cache, logs, scripts.
5. Length limits for error summaries and labels.
6. Category-level omission reports rather than placeholder leaking structure.

Recommended report shape remains:

```yaml
office_redaction_report:
  policy_version: 1
  redacted_field_count: 0
  omitted_sections:
    - session_messages
    - cron_prompt
    - task_logs
  warnings:
    - safe warning codes only
```

## Auth and endpoint placement implications

Stage 2 found plugin HTTP routes under `/api/plugins/` are skipped by dashboard auth middleware, while the Kanban WebSocket checks a token.

Stage 4 recommendation for Stage 5:

- Prefer protected built-in routes such as `/api/office/state` for OfficeState.
- Or explicitly fix plugin HTTP auth before using plugin routes for AI Office.
- Do not expose a raw proxy to `/api/plugins/kanban` or `/api/cron/jobs` as the Office API.
- Return only server-side redacted DTOs.

## Mutation boundary security

The read-only MVP must not include:

- Kanban task create/edit/reassign/reclaim/dispatch/archive controls,
- cron create/edit/pause/resume/trigger/delete controls,
- gateway restart/start/stop or systemd controls,
- config/model/toolset/MCP/skill/memory editors,
- pairing approvals,
- message sending,
- NAS/Obsidian writes,
- dashboard public exposure toggles.

Later mutation stages require separate design for auth, confirmation, audit logging, rollback/failure behavior, and tests.

## Privacy-safe unknown behavior

When data is missing or unsafe:

- show `unknown`, `hidden`, `redacted`, or `unavailable`,
- include `missing_reason` or redaction category when safe,
- do not silently drop the object if it changes counts,
- do not replace unavailable source with zero,
- do not infer topic/user/session from content.

## Stage 5 decisions needed

1. Exact API/auth placement for `OfficeState`.
2. Whether local mode may show raw chat/thread ids by default or only after a toggle.
3. Whether session title/preview can be included after redaction tests.
4. Redaction utility location and test fixtures.
5. Whether dashboard should expose a visible redaction report to the user or only use it internally.
6. How to represent remote mode if it is not implemented yet: absent, disabled, or explicit `unsupported`.
