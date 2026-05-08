# Hermes AI Office — Stage 4 Topic Registry Spec

Last updated: 2026-05-08 12:05 KST
Status: Stage 4 provenance/routing design. Documentation-only; no implementation approved.

## Stage 4 `/goal`

```text
/goal Hermes AI Office Stage 4를 구현 없이 진행한다. Stage 2 audit 문서와 Stage 3 OfficeState/user-story/IA 문서를 근거로 Telegram topic registry, task/session/cron provenance metadata, source/delivery routing normalization, backfill strategy, privacy/security classification, Stage 5로 넘길 결정사항을 문서화하고 STATUS/NEXT handoff를 갱신한다.
```

This goal is a session guardrail only. It does not approve code changes, dependency installs, gateway/cron/config mutations, Kanban mutations, service restarts, NAS/Obsidian writes, or public dashboard exposure.

## Purpose

The topic registry is the proposed read-only lookup layer that lets `OfficeState` display Telegram topics as safe office rooms/destinations without hardcoding user-specific chat/thread ids in product code.

It answers:

1. What platform/chat/thread does this topic represent?
2. What label and purpose may the dashboard safely show?
3. Where did that label come from, and how confident is it?
4. What should be shown when the label is missing or stale?

## Non-goals

The registry does not:

- fetch full Telegram history,
- display raw Telegram message text,
- store bot tokens or `.env` values,
- send messages,
- create/edit Telegram topics,
- replace gateway routing config,
- become the source of truth for delivery execution.

Delivery still uses existing Hermes gateway/cron mechanisms. The registry only normalizes safe labels and references for display/provenance.

## Recommended storage posture

Stage 4 recommendation for Stage 5 design:

1. Use a small Hermes-home registry file or table as the canonical AI Office topic label cache, not hardcoded memory facts.
2. Keep it profile-local under Hermes home, because Telegram topics and allowed display policy are runtime/profile specific.
3. Treat config/home-channel/gateway observations as inputs into the registry projection, not as user-facing labels by themselves.
4. Avoid Obsidian/NAS as a runtime dependency. A future read-only mirror may exist, but Hermes startup/dashboard should not depend on sync.

Candidate Stage 5 storage options:

| Option | Pros | Cons | Stage 4 recommendation |
|---|---|---|---|
| `~/.hermes/office/topics.json` | Simple, profile-local, easy to inspect/back up | Needs write path later for manual aliases | Best initial canonical registry if implemented |
| `~/.hermes/state.db` table | Queryable with sessions/provenance | Requires migration and locking discipline | Good if provenance also lives in state DB |
| `config.yaml` section | Existing config workflow | Blurs runtime labels with settings; config edits are mutation-sensitive | Use only for seed/home-channel references, not main registry |
| Kanban board DB | Close to task subscriptions | Topic registry should span cron/sessions/gateway too | Not recommended |
| Obsidian/NAS note | Cross-device human-readable | Sync/runtime dependency risk | Optional mirror only |

## Registry record shape

Proposed logical record:

```yaml
topic_registry_entry:
  id: "topic:telegram:<chat_key>:<thread_key>"
  platform: "telegram"
  chat_id_raw: "internal only; never remote default"
  chat_id_display: "internal|-100...|hash:abc123|hidden"
  chat_key: "stable hash or internal id depending mode"
  thread_id_raw: 11
  thread_id_display: "11|hidden"
  display_name: "70-자동화"
  purpose: "operations|automation|project|content|runtime|unknown"
  source: "manual_alias|home_channel|config_group_topic|observed_event|cron_delivery|memory_import|derived|unknown"
  confidence: "observed|manual|derived|unknown"
  first_observed_at: "optional timestamp"
  last_observed_at: "optional timestamp"
  last_verified_at: "optional timestamp"
  safe_display_modes:
    localhost: "label_and_internal_ids|label_only|hash_only"
    remote: "label_only|hash_only|hidden"
  notes_redacted: "optional safe note"
```

Implementation can split raw/internal fields away from serializer output. The important contract is that `OfficeState.topics[]` never needs raw Telegram API objects.

## Identifier rules

### Canonical key

Use the tuple:

```text
(platform, chat_id, thread_id)
```

For Telegram forum topics:

- `platform = telegram`
- `chat_id` identifies the supergroup/channel/DM context.
- `thread_id` identifies a forum topic when present.
- A missing forum topic should use an explicit sentinel such as `general` or `none`, not an empty string.

### Display id

`OfficeState` should expose a display-safe topic id:

```text
telegram:<chat_display_key>:<thread_display_key>
```

Where `chat_display_key` depends on mode:

- localhost/internal mode: raw chat id may be acceptable if clearly labeled internal.
- future remote mode: hashed chat id or label-only by default.

Do not expose bot token, invite link, raw message URL, or Telegram username unless explicitly classified safe later.

## Source precedence for labels

When multiple sources mention the same topic, choose display name/purpose by precedence:

1. `manual_alias`: user-approved alias in registry.
2. `home_channel`: Hermes home channel config with a user-facing name.
3. `config_group_topic`: existing group topic skill binding label if present.
4. `observed_event`: gateway source `chat_topic` observed from live Telegram message.
5. `cron_delivery`: explicit delivery string only; can identify ids but normally not label.
6. `memory_import`: planning/audit memory seed; must be marked imported and reviewed before becoming canonical.
7. `derived`: generic fallback such as `Telegram topic 11`.
8. `unknown`: no label.

Rules:

- Higher-precedence label wins unless it is empty or fails redaction.
- Lower-precedence sources can update `last_observed_at` and provenance notes.
- Imported memory facts must not silently become code constants.
- If two high-confidence labels conflict, mark `confidence=unknown` or add a `warning=label_conflict` until reviewed.

## Purpose classification

Allowed purpose values for MVP:

- `operations`: startup/status/owner operations topics.
- `automation`: cron/health/report delivery topics.
- `project`: project-specific workstream topics.
- `content`: content production workstream topics.
- `runtime`: system/runtime alerts.
- `unknown`: fallback when not known.

Do not infer purpose from message text. Purpose may be manual, configured, or derived from explicitly known delivery/home-channel role.

## Known local examples from audit

Planning examples only; future product code must not hardcode these:

| Platform | Chat | Thread | Label | Purpose | Safe source |
|---|---|---:|---|---|---|
| telegram | Telegram Hermes Hub | 2 | `00-운영실` | operations | memory/audit/home target |
| telegram | Telegram Hermes Hub | 11 | `70-자동화` | automation | memory/audit/cron delivery |

These should be seed candidates for a future registry, not implementation constants.

## `OfficeState` mapping

Registry entries project into `OfficeState.topics[]`:

```yaml
office_topic:
  id: "telegram:internal:-1003775710032:11"   # localhost example only
  platform: "telegram"
  chat_id_display: "internal:-1003775710032"
  thread_id: 11
  display_name: "70-자동화"
  purpose: "automation"
  source: "manual_alias|home_channel|observed_event|cron_delivery|unknown"
  last_observed_at: "timestamp"
```

`OfficeState.rooms[]` may then create a `telegram_topic` room from the topic record.

## Failure and unknown behavior

If the registry is unavailable:

- `data_sources.topics.status = unavailable|error`.
- Work items/automations keep their raw-safe provenance as unknown or id-only.
- Do not convert missing registry into zero known topics.

If a topic id is known but label is missing:

- Show `display_name = "unknown"` or `Telegram topic <thread_id>` depending display policy.
- Set `confidence = unknown|derived`.
- Add `unknown_topic_label` warning.

If a chat id is hidden by policy:

- Preserve internal join ability server-side.
- Return hash/label-only to browser.

## Stage 5 decisions needed

1. Choose storage: JSON registry file vs SQLite table.
2. Decide whether Stage 6 may include read-only manual seed records, or only observed/config-derived records.
3. Define local vs remote display mode switch and default.
4. Decide whether a future registry editor is allowed; if so, it belongs after read-only MVP and needs mutation approval.
5. Define tests proving unknown topics are not fabricated and raw messages/tokens are absent.
