# PR Spec: Native Gmail Push Ingestion for Hermes

**Date:** 2026-04-15
**Branch:** `docs/native-gmail-push-pr-spec`

> **Intent:** This is the PR-level spec for making Gmail watcher and newsletter-digest workflows possible directly inside Hermes, without an external bridge/helper and without routing through OpenClaw code at runtime.

## TL;DR

Hermes should add a **first-class `gmail_push` gateway integration** that:

1. authenticates to Gmail with OAuth,
2. registers and renews a Gmail `users.watch`,
3. receives Pub/Sub push notifications directly in Hermes,
4. verifies Google-signed Pub/Sub JWTs,
5. uses the Gmail `history.list` + `messages.get` flow to resolve actual changed messages,
6. normalizes those messages into a Hermes-native event payload,
7. dispatches them as **direct `MessageEvent`s** into the existing gateway/agent pipeline,
8. leaves digesting/archival/delivery to normal Hermes cron jobs.

**Strong opinion:** after inspecting the current Hermes codebase, the best Hermes-native shape is **not** a new generic gateway service and **not** reuse of `platforms.webhook`. The best fit for Hermes *as it exists today* is a **new event-source platform adapter** at `gateway/platforms/gmail_push.py`.

Why:
- Hermes already uses platform adapters for non-human event sources (`webhook`, `homeassistant`).
- `GatewayRunner` already knows how to own adapter lifecycle, authorization exemptions, and status reporting for that abstraction.
- A new `service` abstraction would add framework work that does not improve the user experience for this feature.
- Reusing `webhook` internally would couple Gmail push to a separate platform and force unnecessary prompt-template indirection.

That makes the Hermes-native UX simpler:
- `hermes gmail-push setup`
- `hermes gmail-push status`
- `hermes gateway run`
- cron jobs for twice-daily digesting

---

## Context from the existing spec

The earlier doc at `~/.hermes/workspace/research/hermes-gmail-push-spec.md` established three important things:

1. OpenClaw’s watcher was mostly a thin supervisor around `gog`, not a giant bespoke Gmail subsystem.
2. Hermes already has the *cron* and *event dispatch* half of the workflow.
3. Hermes’ current IMAP email adapter is the wrong foundation because it intentionally skips automated/bulk mail via `_is_automated_sender(...)` in `gateway/platforms/email.py`.

That last point is decisive for this PR:

- `gateway/platforms/email.py` explicitly skips `noreply`, `List-Unsubscribe`, `Precedence: bulk|list|junk`, and related automated markers.
- The target digest/newsletter use case wants the exact opposite: newsletters, updates, bulk mail, and automated sender traffic should be eligible for ingestion.

So this feature must be **separate from the IMAP conversational email adapter**.

---

## Product goal

Make Hermes capable of the following end-to-end workflow with no external bridge:

1. watch a Gmail inbox in near real time,
2. ingest newsletter/update mail that the current email adapter would ignore,
3. let Hermes classify/tag/archive/store state immediately on arrival,
4. run scheduled digest jobs later (for example, twice daily),
5. keep the setup/operator experience Hermes-native and low-friction.

---

## Non-goals

This PR does **not** try to:

- replace the current IMAP/SMTP conversational email platform,
- build a full Gmail client inside Hermes,
- implement unsubscribe/archive/label mutation tools in the same PR,
- unify all HTTP ingress in Hermes behind one shared server abstraction,
- support arbitrary multi-account fleet management in v1.

Those can come later.

---

## Grounding constraints from Google’s API model

This PR must respect a few hard facts from Gmail/Pub/Sub:

### Gmail watch semantics

From Google’s Gmail push docs:
- `users.watch` requires an existing Pub/Sub topic.
- Gmail must have publish permission to `gmail-api-push@system.gserviceaccount.com` on that topic.
- `watch` returns `historyId` and `expiration`.
- Gmail watches expire within 7 days and should be renewed at least daily.

### Notification semantics

Pub/Sub push delivery does **not** contain the changed message body.
It only contains a Pub/Sub envelope whose `message.data` base64url-decodes to roughly:

```json
{
  "emailAddress": "user@example.com",
  "historyId": "9876543210"
}
```

So Hermes must not treat the push notification as the real email event.
It is just an invalidation signal.

### History sync semantics

The actual flow is:
1. store the last known `historyId`,
2. when a push arrives, call `users.history.list(startHistoryId=<previous_history_id>)`,
3. page through changes,
4. fetch the concrete message details with `users.messages.get`,
5. persist the new high-water `historyId`.

Critically, Hermes should use the **previous stored `historyId`**, not the notification’s `historyId`, as the `startHistoryId`.

Also from Google’s docs:
- `historyId`s are increasing but not contiguous,
- stale/invalid `startHistoryId` can produce `404`,
- `404` means Hermes must rebaseline or run a full sync.

### Pub/Sub push auth semantics

If Pub/Sub authenticated push is enabled, Hermes will receive a Google-signed JWT in `Authorization: Bearer ...`.
Hermes should verify:
- JWT signature,
- `aud` matches the configured audience,
- `email` matches the configured push-auth service account,
- `email_verified` is true.

This is the right trust boundary for a native Hermes implementation.

---

## Recommendation

## Make this a first-class platform: `gmail_push`

Add a new platform enum value and adapter:

- `Platform.GMAIL_PUSH = "gmail_push"`
- `gateway/platforms/gmail_push.py`

Even though Gmail push is not a person-to-agent chat transport, this is still the cleanest fit **inside current Hermes architecture** because:

1. `GatewayRunner` already owns adapter startup/shutdown.
2. `PlatformConfig` already gives us a home for enabled/extra settings.
3. Hermes already treats `webhook` and `homeassistant` as authenticated event-source platforms.
4. Platform adapters already produce `MessageEvent`s and participate in status/lifecycle.

This avoids inventing a new service manager abstraction just for one feature.

---

## High-level architecture

```text
Gmail mailbox
  -> Gmail users.watch(topic)
  -> Cloud Pub/Sub topic
  -> Cloud Pub/Sub push subscription
  -> Hermes gmail_push HTTP endpoint
      -> verify Google JWT
      -> decode Pub/Sub envelope
      -> users.history.list(from last stored historyId)
      -> users.messages.get(for relevant changed messages)
      -> normalize message payload
      -> synthesize MessageEvent(s)
      -> Hermes agent run(s)
  -> Hermes cron jobs summarize/store/deliver digests later
```

### Why direct `MessageEvent` injection is better than reusing `webhook`

**Recommendation:** `gmail_push` should dispatch directly into the agent pipeline, not POST back into `platforms.webhook`.

Reasons:
- no need to require the webhook platform to be enabled,
- no double-hop internal HTTP call,
- no secondary HMAC secret for internal handoff,
- no generic webhook prompt templating layer standing between Gmail payloads and agent dispatch,
- cleaner session keys and clearer gateway status.

`webhook` remains useful for external integrations, but Gmail push should be first-class.

---

## User experience

## Setup flow

### CLI

Add a dedicated CLI surface:

```bash
hermes gmail-push setup
hermes gmail-push status
hermes gmail-push renew
hermes gmail-push resync
hermes gmail-push test
```

### Recommended UX behavior

`hermes gmail-push setup` should:
1. validate/install optional deps if missing,
2. ask for or accept the Gmail account,
3. accept/store Google OAuth client credentials,
4. generate an OAuth URL,
5. accept a pasted auth code or redirect URL,
6. store the token in a profile-safe Hermes path,
7. validate topic/subscription config,
8. print the final callback URL / audience / required IAM bindings.

This is materially better UX than “edit YAML + figure out Google by hand.”

### Gateway usage

Once configured:

```bash
hermes gateway run
```

should automatically:
- restore gmail_push state,
- renew watches if needed,
- start the callback server,
- ingest events without further operator work.

### Digest usage

Digesting remains a normal cron concern, e.g.:
- a 7am digest job,
- a 7pm digest job,
- prompts that summarize newly ingested newsletter/update items.

That preserves Hermes’ existing cron mental model.

---

## Proposed config shape

Use the existing gateway config shape, not a new top-level `integrations:` tree.

```yaml
platforms:
  gmail_push:
    enabled: true
    extra:
      account: blspear@gmail.com
      topic: projects/my-project/topics/hermes-gmail-push
      subscription: hermes-gmail-push
      endpoint:
        host: 0.0.0.0
        port: 8645
        path: /gmail-push
        public_url: https://hermes.example.com/gmail-push
      oauth:
        client_secret_path: ~/.hermes/google_client_secret.json
        token_path: ~/.hermes/integrations/gmail_push/blspear@gmail.com/token.json
      watch:
        label_ids: [INBOX]
        label_filter_behavior: INCLUDE
        renew_every_hours: 24
      push_auth:
        service_account_email: hermes-pubsub-push@my-project.iam.gserviceaccount.com
        audience: https://hermes.example.com/gmail-push
      processing:
        history_types: [messageAdded]
        fetch_format: full
        include_headers:
          - From
          - To
          - Subject
          - Date
          - List-Unsubscribe
          - List-Id
          - Precedence
          - Auto-Submitted
        include_html: false
        max_body_chars: 20000
      state:
        path: ~/.hermes/integrations/gmail_push/blspear@gmail.com/state.json
```

### Notes

- `public_url` is the externally reachable HTTPS URL Pub/Sub calls.
- `host`/`port`/`path` are Hermes’ local bind settings.
- `audience` should usually equal `public_url` unless explicitly overridden.
- `fetch_format: full` is recommended for newsletter digesting because snippet-only ingestion is too lossy.
- `include_html: false` by default keeps the model away from raw newsletter HTML unless the user opts in.

---

## State model

Hermes should persist account-scoped state in a dedicated directory under `get_hermes_home()`.

Recommended path layout:

```text
{HERMES_HOME}/integrations/gmail_push/<account-slug>/
  token.json
  state.json
  recent_delivery_ids.json
```

### `state.json` should track at least

```json
{
  "account": "blspear@gmail.com",
  "last_history_id": "1234567890",
  "watch_expiration_ms": 1760000000000,
  "last_watch_renewed_at": "2026-04-16T01:30:00Z",
  "last_notification_at": "2026-04-16T02:01:14Z",
  "last_error": null,
  "last_successful_pubsub_message_id": "2070443601311540"
}
```

### Why explicit state matters

This feature is stateful in a way most Hermes platforms are not.
Without a durable `last_history_id`, Hermes cannot safely recover after restart.

---

## Adapter behavior

## Connect

On `connect()` the adapter should:

1. load config,
2. validate required deps,
3. load OAuth token,
4. start HTTP listener,
5. validate/ensure Pub/Sub push subscription configuration,
6. call `users.watch`,
7. persist returned baseline `historyId` + `expiration`,
8. start a renewal task,
9. mark itself connected.

### Important nuance

A successful `watch` call causes an immediate notification.
Hermes must treat that as part of the normal baseline flow and should not assume it represents a brand-new email body to ingest.

## Disconnect

On `disconnect()` the adapter should:
- cancel renewal tasks,
- stop the HTTP server,
- flush state,
- optionally call `users.stop` only if we explicitly want Hermes shutdown to disable watch state.

**Recommendation:** do **not** call `users.stop` on routine Hermes shutdown in v1. Keep the watch live and just renew again on next startup. That is less surprising operationally.

---

## HTTP endpoint behavior

Add a dedicated Pub/Sub push route owned by `gmail_push`, for example:

```text
POST /gmail-push
```

or account-scoped:

```text
POST /gmail-push/<account-slug>
```

**Recommendation:** single-account v1 can use `/gmail-push`; the adapter already knows which account it owns.

### Request handling steps

1. verify `Authorization` bearer token as a Google OIDC token,
2. verify audience,
3. verify service account email,
4. parse Pub/Sub envelope JSON,
5. base64url-decode `message.data`,
6. extract `emailAddress` and `historyId`,
7. dedupe on Pub/Sub `messageId`,
8. run Gmail history reconciliation,
9. enqueue one Hermes `MessageEvent` per qualifying new message,
10. return success immediately after durable state update / queueing.

### Response code recommendation

Return `204 No Content` or `200 OK` on successful receipt.

`202 Accepted` is also fine, but unlike generic webhook mode, Hermes here owns the whole flow. A simple success response is cleaner.

---

## History reconciliation algorithm

This is the core of the native implementation.

Given:
- stored `last_history_id = H_old`
- notification `historyId = H_new`

Hermes should:

1. call `users.history.list(startHistoryId=H_old, historyTypes=[messageAdded])`,
2. page until `nextPageToken` is exhausted,
3. collect message ids from `messagesAdded`,
4. fetch each message with `users.messages.get`,
5. normalize/filter/dedupe,
6. persist the mailbox high-water mark from the final `history.list` response (or `H_new` if appropriate),
7. dispatch agent events.

### Recommendation on 404 / stale history

If `users.history.list` returns `404`:

- mark adapter state as degraded,
- log a clear message that the history cursor is stale,
- re-run `users.watch` to establish a fresh baseline,
- persist the new baseline history id,
- do **not** automatically backfill all historical mail in v1,
- expose `hermes gmail-push resync` for explicit operator recovery.

Why this is the better v1 choice:
- avoids surprise floods of old email into the agent,
- keeps failure behavior reversible and understandable,
- matches the newsletter/digest use case better than an unbounded full sync.

---

## Message normalization

Hermes should normalize Gmail messages into a stable internal event shape before prompt creation.

Recommended normalized schema:

```json
{
  "source": "gmail_push",
  "account": "blspear@gmail.com",
  "pubsub_message_id": "2070443601311540",
  "history_id": "9876543210",
  "gmail_message": {
    "id": "18c7...",
    "thread_id": "18c7-thread...",
    "label_ids": ["INBOX", "CATEGORY_UPDATES"],
    "internal_date_ms": 1760581000000,
    "snippet": "Short Gmail snippet",
    "subject": "The week in AI",
    "from": "Some Newsletter <hi@example.com>",
    "from_email": "hi@example.com",
    "headers": {
      "List-Unsubscribe": "<mailto:...>",
      "List-Id": "...",
      "Precedence": "bulk"
    },
    "body_text": "Normalized text-only body, truncated to max_body_chars",
    "body_html": null
  }
}
```

### Normalization rules

- prefer `text/plain` bodies,
- if only HTML exists, strip HTML into text,
- preserve selected headers useful for later triage/unsubscribe/archive actions,
- truncate large bodies before prompt creation,
- keep raw payload available in `raw_message` metadata for debugging if needed.

### Important behavioral difference from `platforms/email.py`

`gmail_push` must **not** drop automated/bulk senders.
That is a feature here, not a bug.

---

## Agent event model

For each qualifying new Gmail message, synthesize a `MessageEvent` directly.

Recommended source/session identity:

- `source.platform = Platform.GMAIL_PUSH`
- `source.user_id = <gmail-account>`
- `source.chat_id = f"gmail_push:{account}:{gmail_message_id}"`
- `message_id = <gmail_message_id>`

### Why message-id sessions are better than thread-id sessions here

For newsletter/update ingestion, each arrival is usually an independent triage unit.
Using thread id would accidentally fuse unrelated recurring newsletter items into one long-running session.

### Synthetic prompt shape

Default prompt text should look like:

```text
New Gmail message for blspear@gmail.com

From: Some Newsletter <hi@example.com>
Subject: The week in AI
Labels: INBOX, CATEGORY_UPDATES
Date: 2026-04-16T01:59:00Z
Snippet: Short Gmail snippet

Body:
<normalized text body>
```

This gives the model the same ergonomics as a normal inbound message without exposing raw Pub/Sub mechanics.

### Delivery semantics

`GmailPushAdapter.send()` should **not** email the agent response back.
Default behavior should be:
- log/store the response,
- allow side-effectful tool usage during the run if the prompt calls for it,
- rely on cron or other explicit workflows for digest delivery.

---

## Recommended CLI surface

Create a new CLI module mirroring the style of `hermes_cli/webhook.py`.

Suggested commands:

### `hermes gmail-push setup`
- stores client secret
- prints auth URL
- exchanges auth code
- writes config block / validates config

### `hermes gmail-push status`
Print:
- enabled/disabled
- account
- endpoint URL / audience
- topic / subscription
- last history id
- watch expiration
- last renew timestamp
- last notification timestamp
- degraded / healthy state

### `hermes gmail-push renew`
Forces an immediate `users.watch` refresh.

### `hermes gmail-push resync`
Re-establishes a clean baseline history cursor.

### `hermes gmail-push test`
Runs a local health/config check, not a fake Pub/Sub delivery.

---

## Proposed files to create or modify

## Create

- `gateway/platforms/gmail_push.py`
  - adapter implementation
  - OAuth token loading/refresh
  - watch registration / renewal
  - Pub/Sub endpoint
  - history reconciliation
  - `MessageEvent` dispatch

- `hermes_cli/gmail_push.py`
  - CLI setup/status/renew/resync/test helpers

- `tests/gateway/test_gmail_push.py`
  - unit/integration tests for adapter behavior

- `tests/hermes_cli/test_gmail_push_cli.py`
  - CLI tests

## Modify

- `gateway/config.py`
  - add `Platform.GMAIL_PUSH`
  - load/merge config for the new platform
  - add any env-var wiring if we expose env support

- `gateway/run.py`
  - instantiate `GmailPushAdapter`
  - exempt `Platform.GMAIL_PUSH` from normal user allowlist checks, same spirit as webhook/homeassistant

- `hermes_cli/main.py`
  - add `gmail-push` subcommand parser

- `hermes_cli/config.py`
  - add default config entries if needed
  - add optional env var metadata for setup/status output

- `pyproject.toml`
  - add optional dependency group for Gmail push

- `tests/gateway/test_platform_reconnect.py`
  - if platform lifecycle assumptions need updates

- docs / website pages as appropriate

---

## Optional dependency set

Add a new optional extra, for example:

```toml
[project.optional-dependencies]
gmail-push = [
  "google-api-python-client>=2.0,<3",
  "google-auth>=2.0,<3",
  "google-auth-oauthlib>=1.0,<2",
  "aiohttp>=3.13.3,<4",
]
```

and include it in `all`.

### Why optional

This is the cleanest Hermes packaging story:
- not every Hermes install needs Google/Pub/Sub support,
- the gateway can report a clear missing-deps error,
- setup can instruct users to install `hermes-agent[gmail-push]`.

---

## Testing requirements

## Adapter tests

`tests/gateway/test_gmail_push.py` should cover at least:

1. `connect()` fails clearly when deps are missing.
2. `connect()` stores baseline `historyId` and `expiration` after `watch`.
3. Pub/Sub JWT verification rejects bad audience.
4. Pub/Sub JWT verification rejects wrong service-account email.
5. envelope parsing handles base64url Gmail payload correctly.
6. dedupe on repeated Pub/Sub `messageId` prevents duplicate runs.
7. history pagination is handled correctly.
8. `messageAdded` entries produce one `MessageEvent` each.
9. bulk/newsletter messages are **not** filtered out.
10. stale `historyId` / `404` triggers degraded state + rebaseline.
11. renewal task re-calls `watch` before expiration.
12. `disconnect()` cancels tasks and flushes state.

## CLI tests

`tests/hermes_cli/test_gmail_push_cli.py` should cover:

1. parser wiring for `hermes gmail-push ...`
2. setup/status output
3. resync/renew/test command routing
4. profile-safe path handling

## Gateway integration tests

Add at least one integration-level test that proves:
- `GatewayRunner` loads the adapter,
- an authenticated push request becomes a Hermes agent run,
- the final response is logged instead of sent as email.

---

## Rollout plan

## PR scope (recommended)

Keep the first PR to:

1. native Gmail push ingestion,
2. OAuth setup/status CLI,
3. watch renewal,
4. Pub/Sub JWT verification,
5. history reconciliation,
6. direct `MessageEvent` injection,
7. durable state,
8. tests/docs.

Do **not** include in the same PR:
- Gmail mutation tools,
- unsubscribe automation,
- label/archive actions,
- multi-account orchestration,
- shared HTTP ingress refactor.

That keeps the PR crisp and shippable.

---

## Open questions

These can stay open in the PR, but I’m giving a recommended answer where I have one.

### 1. Should Gmail push be a `service` or a `platform`?
**Recommendation:** platform.

Reason: current Hermes architecture already treats authenticated event sources as platforms, and `GatewayRunner` is built around that lifecycle.

### 2. Should Gmail push dispatch through `webhook` or direct `MessageEvent`?
**Recommendation:** direct `MessageEvent`.

Reason: cleaner, less coupled, fewer secrets, less internal plumbing.

### 3. Should Hermes create/manage the Pub/Sub subscription or require it to exist already?
**Recommendation:** require topic + subscription details in v1, but validate them aggressively and print exact remediation.

Why: fully managing subscription creation is nice UX, but it pulls in more IAM surface area and failure modes. It is a reasonable follow-up.

### 4. Should Hermes call `users.stop` on shutdown?
**Recommendation:** no, not in v1.

Reason: a watch naturally expires and is renewed on startup anyway; stopping it on every gateway restart adds churn and surprise.

### 5. What should happen on stale history `404`?
**Recommendation:** degrade + rebaseline, with explicit `resync` command.

Reason: safer than surprise backfills.

### 6. Should v1 support multiple Gmail accounts?
**Recommendation:** no.

Ship one-account-first. Design the state path to be account-scoped so multi-account can come later cleanly.

### 7. Should Hermes expose raw HTML to the model?
**Recommendation:** default off.

Newsletter HTML is noisy and prompt-expensive. Normalize to text first.

---

## Success criteria

This PR is successful if:

1. Hermes can watch a Gmail mailbox without any external bridge/helper.
2. A new newsletter/update message can trigger a Hermes run within seconds/minutes.
3. The integration ingests bulk/automated mail that `platforms/email.py` would skip.
4. Duplicate Pub/Sub retries do not create duplicate agent runs.
5. Watch renewal is automatic and visible.
6. The operator can inspect health/status from the CLI.
7. Cron jobs can summarize the resulting ingested corpus later.
8. The feature feels native to Hermes rather than like a bolt-on wrapper around another system.

---

## Final recommendation

If we want the version that is most aligned with Hermes and most seamless for the end user, the PR should say:

> Add a first-class `gmail_push` gateway platform to Hermes that directly implements Gmail watch registration, Pub/Sub authenticated push receipt, Gmail history reconciliation, normalized message extraction, and direct Hermes `MessageEvent` dispatch, while leaving digest aggregation and delivery to the existing cron system.

That is the cleanest native replacement for the old bridge-based Gmail watcher workflow.
