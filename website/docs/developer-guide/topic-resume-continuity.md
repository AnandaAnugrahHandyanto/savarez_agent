# Topic Resume Continuity

Hermes topic continuity for Telegram/forum threads should be built from two layers:

1. **Canonical state** from the topic workspace `state.md`
2. **Recency** from the most recent user/assistant messages in the prior topic session

## Expected resume stack

When a threaded/topic session is resumed after an idle or daily auto-reset:

1. Resolve the topic workspace from `platform + chat_id + thread_id`
2. Read `state.md`
3. Prioritize:
   - `Operating Contract`
   - `Topic-Specific Instructions`
   - `Open Loops`
   - `Next Actions`
4. Load the last 5 to 10 user/assistant messages from the **previous session id**, not the fresh post-reset session id
5. Inject that topic resume context into the new turn before the model responds

## Why the previous session matters

After an auto-reset, the new session is usually empty or contains only the current morning check-in message.
If topic recency is loaded from the fresh session id, Hermes will fall back to stale `state.md` and lose the last real conversational checkpoint.

The correct source for recent topic messages after auto-reset is:

- `SessionEntry.previous_session_id`

If there was no auto-reset, recent topic messages can be loaded from the current `session_id`.

## Agent cache rule

Gateway agent caching must not survive a session boundary.

If a cached `AIAgent` is reused across a new `session_id`, stale session-scoped context can leak into the next turn.
To prevent that, the cache signature must include `session_id`.

## Logging guidance

Topic resume should log enough to answer "what did Hermes actually look at?" without forensic digging.
Recommended fields:

- workspace id
- trigger type (`new_session` vs `auto_reset`)
- recent-source session id
- recent message count

## Regression coverage

At minimum, keep tests for:

1. auto-reset preserving `previous_session_id`
2. topic resume reading recent messages from `previous_session_id`
3. cache signature changing when `session_id` changes
