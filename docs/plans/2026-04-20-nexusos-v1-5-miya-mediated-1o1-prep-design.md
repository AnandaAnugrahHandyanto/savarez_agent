# NexusOS V1.5 — Miya-mediated 1:1 prep design

## Recommendation
Adopt a **hybrid architecture**:

- **deterministic scheduler/service decides when a prep is due**
- **Miya decides what to send and sends it to Michael**
- **deterministic fallback sends a minimal note only if Miya misses a short SLA**

This keeps reliability in the machine path and judgment/voice in Miya.

---

## Why this is better than direct dispatch

### Direct dispatcher → Michael
**Strengths**
- simplest
- most reliable
- lowest latency / fewest moving parts

**Weaknesses**
- Miya is bypassed
- reminder becomes a system alert, not an assistant action
- weaker control over tone, emphasis, and context-sensitive phrasing
- product model becomes inconsistent: Miya owns people-manager judgment, but the service owns the actual founder-facing output

### Scheduler → Miya → Michael
**Strengths**
- cleaner product boundary
- Miya remains the author/operator
- better tone consistency
- preserves a single founder-facing voice

**Weaknesses**
- puts timing reliability at risk if Miya is blocked, offline, or gateway-busy
- creates more failure modes in the critical path

### Hybrid recommendation
Best balance:
- **service owns timing, dedupe, retries, logs, fallback**
- **Miya owns message rendering and founder-facing delivery when healthy**

---

## Design principle

### Separate clock from author
- **NexusOS scheduler/service = the clock**
- **Miya = the author**

The scheduler should not impersonate Miya.
It should determine that a prep is due and hand Miya a structured task.

---

## Target operating model

### Primary path
1. Local scheduler wakes every minute.
2. Deterministic due-engine checks the schedule registry.
3. If a prep is due, the engine creates an internal `one_on_one_prep_due` event.
4. Miya consumes that event.
5. Miya reads the report/profile context.
6. Miya renders the actual prep note in the expected Telegram style.
7. Miya sends Michael the note via the normal Telegram path.
8. System records success in the reminder log.

### Fallback path
If Miya does not complete within a short SLA window:
- system sends a **minimal deterministic fallback note** directly
- fallback is explicitly designed as a thin safety net, not the normal experience

Example fallback:
- `Thomas 1:1 in 5m`
- `top 5 priorities sync`
- `profile loaded but Miya response delayed`

Prefer a slightly better fallback if cheap:
- 1–3 deterministic topic bullets pulled from stored current topics
- no synthesis beyond that

---

## Proposed event contract

When something becomes due, the service should hand Miya a structured payload like:

```json
{
  "type": "one_on_one_prep_due",
  "profile_slug": "thomas-zhu",
  "name": "Thomas Zhu",
  "meeting_at": "2026-04-20T13:15:00+08:00",
  "prep_due_at": "2026-04-20T13:10:00+08:00",
  "deadline_at": "2026-04-20T13:11:00+08:00",
  "delivery_target": "origin",
  "report_path": "HERMES_HOME/projects/people-manager/reports/thomas-zhu.json",
  "template_style": "ultra_short_telegram",
  "fallback_allowed": true,
  "dedupe_key": "thomas-zhu::2026-04-20T13:15:00+08:00"
}
```

Optional derived fields:
- `sparse_profile: true/false`
- `current_topics_count`
- `last_touchpoint_at`
- `freshness_warnings`

These are useful for routing/fallback, but the core contract should stay small and deterministic.

---

## SLA recommendation

Use a short, explicit SLA:
- target: **send by T+30s** after prep_due_at
- hard fallback cutoff: **T+60s**

For a `13:10:00` prep trigger:
- Miya should normally send by `13:10:30`
- fallback fires at `13:11:00` if Miya has not confirmed send

This preserves the founder experience while still protecting against misses.

---

## State machine

Each due occurrence should move through explicit states:

1. `due_detected`
2. `queued_for_miya`
3. `claimed_by_miya`
4. `sent_by_miya`
5. `fallback_sent`
6. `failed`
7. `cancelled`

Only one terminal success state should be allowed:
- `sent_by_miya`
- or `fallback_sent`

Never both.

---

## Dedupe rules

Use a deterministic occurrence key:
- `<profile_slug>::<meeting_at_iso>`

For each occurrence:
- only one active claim
- if Miya sends successfully, fallback is suppressed
- if fallback sends, Miya should not later send a second full prep
- late Miya completion should log as `stale_completion_suppressed`

This is important because once Miya is in the loop, duplicate-send risk rises materially.

---

## Delivery semantics

### Preferred
Miya sends the final message through the same normal Telegram delivery path used for standard assistant replies.

Why:
- preserves product coherence
- keeps Michael’s mental model simple: Miya is talking to him
- consolidates founder-facing output into one voice/channel behavior

### Avoid
Service directly sending the normal prep note in the steady state.

Reserve direct service send for:
- fallback only
- or explicit operator/test mode

---

## Failure modes and handling

### 1. Scheduler down
Impact:
- no due event generated

Mitigation:
- healthcheck on scheduler heartbeat
- next-run dashboard / audit view
- alert if no scheduler tick in N minutes

### 2. Due engine works, Miya never claims task
Impact:
- reminder at risk

Mitigation:
- SLA timeout triggers fallback
- log `miya_missed_sla`

### 3. Miya claims but fails before send
Impact:
- reminder at risk

Mitigation:
- claim lease expires
- fallback fires after deadline
- log `miya_claim_failed`

### 4. Miya sends but ack/log write fails
Impact:
- potential duplicate on retry/fallback

Mitigation:
- write-ahead occurrence claim or idempotency token
- send result must atomically pair with occurrence completion if possible

### 5. Telegram API transient failure
Impact:
- delayed or failed send

Mitigation:
- retry with backoff
- keep retries inside SLA budget
- fallback can still use same token if Miya path fails

### 6. Sparse profile
Impact:
- overreaching/low-quality prep

Mitigation:
- Miya instructed to send minimal note instead of faking depth
- fallback note remains extremely lightweight

---

## Product boundary

### Miya owns
- final wording
- topic selection emphasis
- tone / relationship note
- light synthesis
- deciding when context is too thin for overreach

### NexusOS deterministic layer owns
- recurrence math
- exact due timing
- queue/event creation
- dedupe / claims
- SLA timer
- fallback trigger
- logs / audit trail

This is the cleanest division of responsibility.

---

## Recommended implementation shape

### V1.5 minimal
Keep the existing file-backed engine and add a small event/claim layer.

Possible components:
- `people_manager/schedule_store.py` — unchanged core recurrence logic
- `people_manager/reminder_log.py` — extend with Miya/fallback states
- `people_manager/prep_queue.py` — due-event queue / lease / ack logic
- `scripts/one_on_one_prep.py` — split into:
  - `enqueue-due`
  - `run-fallback`
  - `preview`
  - `list/show/log/audit`
- gateway/agent-side handler for internal `one_on_one_prep_due` tasks

### Event transport options
From best product architecture to simplest ops:

1. **internal local queue/state file**
   - best for determinism and auditability
   - Miya polls or consumes due events

2. **local scheduler triggers Hermes with a structured prompt/event**
   - workable transitional path
   - less clean than a real queue

3. **direct send only**
   - reliable but architecturally weaker

Recommendation: **option 1 as target, option 2 as bridge**.

---

## Operator semantics

What should happen at `13:10` exactly:

1. occurrence detected for Thomas
2. queue entry created with dedupe key
3. Miya receives internal task immediately
4. Miya sends prep note
5. queue marks `sent_by_miya`
6. if step 4/5 not completed by deadline, fallback sends minimal note and marks `fallback_sent`

Operator view should show:
- next due reminders
- queued occurrences
- claimed occurrences
- sent by Miya
- fallback sent
- failures / stale claims

---

## Decision

For NexusOS V1.5, adopt:
- **deterministic timing layer**
- **Miya-mediated authoring and normal delivery**
- **deterministic fallback for reliability**

In plain English:
- **service tells Miya it’s time**
- **Miya talks to Michael**
- **service only speaks directly if Miya misses the window**

---

## Immediate next build step

Implement a bridge version first:
1. keep current schedule registry and due logic
2. replace direct steady-state send with `queue-for-miya`
3. add send acknowledgment + SLA timeout
4. keep minimal fallback direct-send path
5. add audit commands for queued / sent / fallback / failed occurrences

That gets the product boundary right without overbuilding too early.