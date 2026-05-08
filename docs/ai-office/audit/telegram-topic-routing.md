# Hermes AI Office — Telegram Topic Routing Audit

Last updated: 2026-05-08 11:44 KST
Status: Stage 2 read-only audit. No Telegram config, gateway service, topics, or messages were changed.

## Scope

Audit how Hermes currently extracts Telegram chat/thread/topic information and how that can feed a future AI Office topic/room model.

Primary files inspected:

- `gateway/platforms/telegram.py`
- `gateway/session.py`
- `cron/scheduler.py`
- `plugins/kanban/dashboard/plugin_api.py`

Known local memory context:

- Telegram Hermes Hub chat id: `-1003775710032`
- `00-운영실` thread id: `2`
- `70-자동화` thread id: `11`
- Gateway home/startup target is `00-운영실` thread `2`
- Automation topic is `70-자동화` thread `11`

## Message event source extraction

`gateway/platforms/telegram.py::_build_message_event` builds a source object from Telegram messages.

Observed behavior:

- Determines `chat_type` as `dm`, `group`, or `channel`.
- Reads `message.message_thread_id` into source `thread_id`.
- For forum groups with no thread id, uses a general-topic thread constant.
- Resolves DM topic info through `_get_dm_topic_info` and cache helpers.
- Resolves group topic skill binding from `config.extra.get("group_topics", [])`, matching `chat_id` and `thread_id`.
- Builds `source` with:
  - `chat_id`
  - `chat_name`
  - `chat_type`
  - `user_id`
  - `user_name`
  - `thread_id`
  - `chat_topic`
- Begins reply context extraction through `message.reply_to_message`.

This source object is the best current runtime source for Telegram topic provenance.

## Delivery target parsing

Cron delivery can target Telegram topics using explicit target strings such as:

- `telegram:-1003775710032:11`

`cron/scheduler.py` resolves delivery targets into structured values with:

- `platform`
- `chat_id`
- `thread_id`

It also supports `deliver=origin`, preserving `origin.thread_id` where present, and logs a warning if an origin thread is lost during target resolution.

## Home channels and Kanban notifications

Kanban dashboard plugin reads configured gateway home channels:

- `GET /api/plugins/kanban/home-channels?task_id=&board=`

The returned home channel shape includes:

- `platform`
- `chat_id`
- `thread_id`
- `name`
- `subscribed`

Kanban notification subscriptions store `(task_id, platform, chat_id, thread_id)` in `kanban_notify_subs`. Current checked boards had zero subscriptions.

## Current topic inventory known for AI Office

From memory and live cron snapshot:

- `Telegram Hermes Hub` / `-1003775710032`
  - thread `2`: `00-운영실`, home/startup target
  - thread `11`: `70-자동화`, live cron delivery target for `daily-hermes-health-digest`

These should be treated as known labels, not discovered from a canonical topic registry. Avoid hardcoding them in product code before a registry design is approved.

## Fit for AI Office MVP

Recommended office mapping:

- Telegram supergroup = building or floor.
- Telegram topic/thread = room.
- Incoming message source = doorway/inbox event.
- Cron delivery target = automation bot assigned to a room.
- Kanban notify subscription = work item subscribed to a room.

The MVP can display known topics if they are available from config/home channel/origin metadata, but should clearly label unknown thread ids as raw ids.

## Gaps

- No dedicated dashboard endpoint lists Telegram topics, labels, and bindings as a clean registry.
- Topic labels are partly runtime-derived (`chat_topic`) and partly config/memory knowledge.
- Kanban tasks do not currently have first-class source Telegram fields.
- Cron `deliver` strings need parsing/normalization before display.
- Session DB `source` only stores platform-level source such as `telegram`; thread/topic is not visible in the core session schema inspected.
- Reply context exists in runtime message event processing but is not obviously normalized into the session/task provenance model.

## Privacy/security notes

- Chat ids and thread ids are operational identifiers; they are less sensitive than tokens but should still be treated as internal routing metadata.
- Do not expose raw Telegram messages in a public or remote dashboard.
- Do not expose bot token or environment config. This audit did not read token values.

## Recommendation for Stage 4 provenance design

Create a small topic registry/provenance model independent of Telegram raw API objects:

- `platform`: `telegram`
- `chat_id`
- `thread_id`
- `display_name`
- `purpose`: operations / automation / project / unknown
- `source`: config / observed_event / manual_alias / memory-import
- `last_observed_at`

Then reference this registry from sessions, cron delivery targets, and Kanban task provenance.
