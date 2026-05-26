---
name: roombook-failure-autorecovery
description: Use when roombook / 有成会议 booking fails and a webhook should trigger automatic diagnosis, corrective re-booking, requester notification, and a Discord repair report to Kevin.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [roombook, dingtalk, webhook, incident-response, autorecovery, meeting-rooms]
    related_skills: [roombook, webhook-subscriptions, hermes-agent]
---

# Roombook Failure Auto-Recovery

## Overview

This skill defines the incident workflow for 钉钉群 / 有成会议 booking failures. It is designed for a Hermes webhook route that receives `task.failed`, `task.notify_failed`, `task.cookie_expired`, or similar roombook events, then drives the agent to:

1. **补任务**：if the original meeting still needs a room, create a replacement booking task or immediately book another suitable room.
2. **通知预定人**：after recovery succeeds, proactively notify the original requester / delegatee in the appropriate DingTalk group or DM.
3. **自动排查位置情况并修复**：diagnose whether the failure came from cookie, room availability, callback routing, DingTalk notification, DWS calendar, Hermes webhook delivery, profile/tooling, or roombook server-side notify errors; fix what is safe to fix.
4. **Discord 汇报 Kevin**：after the issue is understood and recovery/fix is complete, send a concise Discord summary to Kevin / origin Discord thread.

Load this together with `roombook` and `webhook-subscriptions` when building or operating the webhook flow.

## When to Use

Use this skill when:

- A roombook webhook reports booking failure, notification failure, cookie expiry, callback failure, or unclear task state.
- 钉钉群里用户 says “没订上 / 没通知 / 会议室预定失败 / 任务失败”.
- Kevin asks for a hook-based self-healing workflow for meeting-room booking incidents.
- You need to distinguish “任务创建成功”, “会议室正式预订成功”, “钉钉日程成功”, and “通知成功”.

Do **not** use it for:

- Normal one-off booking creation from user chat. Use `roombook`.
- Pure recurring booking setup. Use `roombook` recurring-booking guidance.
- Generic Hermes webhook routing unrelated to meeting rooms. Use `webhook-subscriptions`.

## Required Capabilities / Environment

The recovery agent normally needs these capabilities:

- Skills: `roombook`, `webhook-subscriptions`, this skill.
- Toolsets: `terminal`, `file`, `messaging`, optionally `session_search` and `web`.
- CLI/tools: roombook CLI script from the `roombook` skill; `dws` for DingTalk contact/group notification and calendar checks.
- Environment: `ROOMBOOK_API_URL`, `ROOMBOOK_SECRET_KEY`, `ROOMBOOK_NOTIFY_URL`, and, for admin repair, any project-specific roombook/server credentials already present in the runtime.

For DingTalk Work isolated profile, do **not** broaden the Work bot with `terminal` or `skills` just for user-facing booking. This recovery workflow should run in the admin/Hermes profile triggered by webhook or Discord, not inside the locked-down Work group bot unless Kevin explicitly approves broader tooling.

## Webhook Route Shape

Create a Hermes webhook subscription whose prompt is self-contained and loads this skill plus `roombook`:

```bash
hermes webhook subscribe roombook-failure-recovery \
  --events "task.failed,task.notify_failed,task.cookie_expired,unknown" \
  --skills "roombook,roombook-failure-autorecovery" \
  --deliver discord \
  --description "Auto-diagnose and recover failed roombook bookings" \
  --prompt "Roombook incident webhook received. Load roombook-failure-autorecovery and roombook. Payload JSON follows:\n{__raw__}\n\nGoals: (1) recover the booking if still needed and notify the requester after success; (2) diagnose room/location/notification/callback failure and fix safe issues; (3) report concise result to Kevin in Discord. Do not expose internal IDs to normal users."
```

Use `{__raw__}` for the full webhook body. The webhook adapter supports dot-notation fields plus this special raw-payload token; `{payload}` is not a built-in token and will remain literal, leaving the recovery agent without incident details.

Important event-filter pitfall: older Hermes webhook adapters classified roombook top-level `event` payloads as `unknown`; keep `unknown` in route events when supporting older deployments. Current adapters map `payload.event` after `payload.event_type`.

## Incident Triage: First 5 Minutes

1. **Parse payload and preserve evidence**
   - Record event type, human message, task fields, room/date/time/subject/requester/delegatee, and `fields.notify_state`.
   - Treat `notify_state` as opaque unless it is clearly JSON.
   - Do not show internal task/user IDs to normal DingTalk users.

2. **Classify incident**
   - Booking execution failed: room unavailable, cookie expired, API error, conflict, malformed task.
   - Notification failed: room was booked but original DingTalk/Discord notification did not arrive.
   - Calendar failed: room booked but DWS calendar event failed.
   - Callback failed: roombook could not POST to Hermes webhook, or Hermes accepted it but did not deliver cross-platform.
   - Unknown: webhook lacks enough detail; query roombook task state and logs.

3. **Check current business truth**
   - Use roombook task state to answer “did the official meeting room booking succeed?”
   - Use `room-availability` / `free-rooms` for real room availability. Never infer availability from `list-tasks` alone.
   - If notification failure is suspected, confirm booking success before saying “已订好”.

4. **Decide whether recovery is still needed**
   - If original meeting time has passed, do not create a replacement booking. Report and fix root cause only.
   - If room already booked successfully, do not create a duplicate. Fix/send missing notifications.
   - If booking failed and meeting is still future/currently actionable, create a replacement task or book an available alternative.

5. **Set user-facing posture**
   - To requester: short practical message: current status + recovered booking result + any action needed (e.g. refresh cookie).
   - To Kevin/Discord: incident details, root cause, repair action, verification.

## Recovery Decision Tree

### A. Cookie expired / no cookie

1. Run/check equivalent of `check-cookie` for the original booking user.
2. If meeting booking window is future and task can wait:
   - Create/keep a waiting task when the roombook rules allow future-task creation despite current expired cookie.
   - Notify requester to refresh 有成会议 cookie at the correct time (usually execution前一晚 20:30 for 00:00 window).
3. If booking needs immediate execution:
   - Notify requester that they must open DingTalk → 有成会议 once to refresh cookie.
   - Do not substitute Kevin/admin cookie for another requester unless this is explicitly an admin/delegated booking scenario.
4. After cookie is refreshed, re-run booking or create replacement task and verify.

### B. Target room unavailable / conflict

1. Query real-time availability with `room-availability` or `free-rooms` for the exact date/time and required seat range.
2. If the original room is now unavailable:
   - Prefer the closest suitable available room by seat count/location/name convention.
   - If multiple reasonable choices exist and time allows, ask requester; if webhook-run cannot ask, choose the smallest adequate room and mention the substitution.
3. Create replacement booking task using `--room-name`, never guessed `--room-id`.
4. Verify final task state / booking success.
5. Notify requester of the substituted room and reason.

### C. Task created but official booking not confirmed

1. Query task state via roombook (`list-tasks` / task details if available).
2. Distinguish:
   - Waiting task: not yet official booking.
   - Success with meetingId: official booking succeeded.
   - Failed: official booking failed and needs recovery.
3. If waiting but execution should have happened, inspect daemon/server logs or trigger safe retry if supported.
4. Only say “订好了” after official success is confirmed.

### D. Booking success but requester/group not notified

1. Confirm official booking success first: room, date, time, subject, requester/delegatee.
2. Identify original target:
   - Prefer task-level `notify_state.target` if present.
   - Otherwise inspect Hermes Work profile session/logs or roombook task metadata.
3. For DingTalk group notification, prefer DWS group send rather than short-lived Hermes DingTalk `session_webhook`:
   - Resolve delegatee/requester with `dws contact user search` or `dws aisearch person`.
   - Verify target group with `dws chat conversation-info`.
   - Send message with `<@userId>` plus `--at-users <userId>`.
   - Verify with `dws chat message search` when possible.
4. If notification route is broken, fix route/state/config after manual补发.

### E. Roombook → Hermes webhook POST failed

1. Check roombook server logs around event time for `notifyManager_*`, `EOF`, timeout, 401/403/404, or connection errors.
2. Verify task-level `notify_url` points to a URL reachable from the roombook server/container.
3. If using Tailscale MagicDNS and container reports EOF, test from inside container; switch to Hermes node Tailscale IPv4 if needed.
4. Verify Hermes webhook `/health`, route secret, route events, and gateway logs.
5. Re-send/retry notification if supported; otherwise manually notify requester and document the fix.

### F. Hermes accepted webhook but did not deliver to target

1. Check Hermes gateway logs for webhook route match and final cross-platform delivery.
2. Do not confuse `[Webhook] Sending response ... to webhook:...` with target delivery success.
3. Verify `deliver` / `deliver_extra.chat_id` and route target.
4. If DingTalk proactive delivery relies on `session_webhook`, remember it expires quickly (about 85 safe minutes). Use fixed DingTalk robot/DWS route for durable booking-result notifications.
5. Fix subscription config or notify-state construction, then test with `hermes webhook test` or a synthetic roombook payload.

### G. DWS calendar failed after booking success

1. Do not mark the meeting-room booking as failed just because calendar failed.
2. Verify mapping of requester/delegatee:
   - Explicit “给/帮某人订” means delegatee should receive calendar / @ notification.
   - Do not default to Kevin just because Kevin/admin initiated the request.
3. Use `dws calendar event create --dry-run` to validate summary, date/time, timezone, attendees, and compere before enabling real create.
4. Repair calendar separately and mention it in Discord summary.

## Safe Auto-Fix Policy

The recovery agent may do these without asking Kevin first:

- Query roombook task state, room list, room availability, cookie status.
- Query Hermes webhook/gateway logs.
- Send a missing “已订好” notice when booking success is already verified and target group/person is unambiguous.
- Create a replacement task for the same requester/time/subject when the original failed and the new room is the same room or the only clearly suitable available alternative.
- Fix task-level `notify_state` / webhook route if the correct target is unambiguous and change is low-risk.

Ask Kevin or report needing manual decision when:

- Multiple alternative rooms are plausible and no requester can be asked.
- The meeting time, requester, or room target is ambiguous.
- Fix requires code deployment, service restart, schema migration, or broad platform/toolset changes.
- The recovery would impersonate another user or use admin cookie for a non-admin requester.

## User Notification Templates

### Booking recovered, same room

```text
已处理：刚才会议室预订失败，我已重新补订成功。
会议：{subject}
时间：{date} {start}-{end}
会议室：{room}

后续你不用再操作。
```

### Booking recovered, alternative room

```text
已处理：原会议室当时不可订，我已为你改订可用会议室。
会议：{subject}
时间：{date} {start}-{end}
会议室：{new_room}
说明：原会议室 {old_room} 已被占用/不可订。
```

### Cookie action needed

```text
这次没有自动补订成功，原因是你的有成会议授权已过期。
请在钉钉里打开一次「有成会议」刷新授权；刷新后我会继续补订/你也可以再发一句“继续补订”。
```

### Manual decision needed

```text
我已排查到失败原因：{reason}。
当前有多个可选会议室：{options}。
请回复选哪个会议室，我再帮你补订。
```

## Discord Report Template for Kevin

Use bullets, not Markdown tables:

```text
会议室预订故障已处理：{status}

- 原因：{root_cause}
- 影响：{requester/delegatee} / {date} {start}-{end} / {subject}
- 恢复动作：{created replacement task | booked same room | changed to alternative room | resent notification | fixed webhook route}
- 当前结果：{official booking success? room? notification delivered? calendar?}
- 已修复：{config/code/route/cookie guidance/log evidence}
- 仍需关注：{none | manual action}
```

If user-facing identifiers are included, prefer names. Avoid raw `dingId`, `roomId`, and task IDs unless Kevin explicitly asks for debugging details.

## Implementation Checklist for the Webhook Automation

- [ ] Webhook platform enabled and `/health` reachable from roombook server/container.
- [ ] Subscription exists for failure-like events and includes `unknown` until payload event mapping is verified.
- [ ] Subscription prompt loads `roombook` and `roombook-failure-autorecovery`.
- [ ] Route delivery goes to Kevin’s Discord target or current origin thread for admin reports.
- [ ] `ROOMBOOK_NOTIFY_URL` is task-level and reachable from roombook.
- [ ] Task creation writes `notify_state` containing original platform/chat/person target when available.
- [ ] Recovery prompt tells the agent not to expose internal IDs to normal users.
- [ ] Synthetic webhook test covers: booking failed, booking success but notify failed, cookie expired, callback EOF.
- [ ] DingTalk requester notification path is durable: DWS group send / fixed robot preferred over `session_webhook`.
- [ ] Logs are checked for both roombook server notify and Hermes final cross-platform delivery.

## Verification Checklist Per Incident

- [ ] Official room booking state verified, not inferred from task creation alone.
- [ ] Room availability verified with `room-availability` / `free-rooms` if changing rooms.
- [ ] Replacement task/booking created only if still needed.
- [ ] Requester/delegatee notified after success, with @ mention if DingTalk group and person is unambiguous.
- [ ] Root cause categorized and safe repair applied.
- [ ] Webhook/callback route tested after repair when relevant.
- [ ] Kevin received Discord summary after recovery/fix.

## Common Pitfalls

1. **Saying “订好了” too early.** A task ID or created waiting task is not official booking success. Confirm task success / meeting ID first.

2. **Using `list-tasks` as availability.** `list-tasks` is history/status only. Real availability must come from `room-availability` / `free-rooms`.

3. **Fixing notification by writing `configure-webhook` byUser.** byUser is shared per dingId and can be overwritten by another agent/node. Prefer task-level `notify_url` + `notify_state`.

4. **Relying on DingTalk `session_webhook` for future proactive notifications.** It expires quickly. Use DWS/fixed robot for durable booking-result notices.

5. **Using Kevin/admin cookie for everyone.** In group booking, default requester is the sender; if their cookie is expired, ask them to refresh unless it is an explicit admin/delegated scenario.

6. **Notifying the wrong person in delegated bookings.** “给/帮 X 订” means X is the delegatee and should be @’d / calendared when recover succeeds.

7. **Only checking Hermes logs for notify failures.** If roombook POST failed before reaching Hermes, Hermes has no inbound record. Check roombook server logs too.

8. **Exposing internal IDs in group messages.** Keep `dingId`, `roomId`, task IDs, meeting IDs out of normal user-facing replies.
