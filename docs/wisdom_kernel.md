# Hermes Wisdom Kernel

Hermes Wisdom Kernel v1 is a local, source-backed capture and recall subsystem for Telegram-first personal knowledge.

It preserves accepted user originals exactly, stores them in a Wisdom-owned SQLite database, classifies them with deterministic rules, searches originals and annotations, and creates internal application proposals. It does not write to the old productivity database and does not take external actions.

## Storage

Default database:

```text
~/.hermes/wisdom/wisdom.db
```

Wisdom also creates a local HMAC salt at:

```text
~/.hermes/wisdom/salt
```

The salt is used to hash session and message identifiers before storage. It is not printed or rendered.

## Exact Originals

The exact accepted original is stored in `raw_events.original_text`.

Wisdom does not normalize punctuation, whitespace, capitalization, emojis, or line breaks in that field. Cleaned text, titles, interpretations, and application proposals are annotations only.

Secret-like captures are rejected by default instead of storing a redacted value while claiming exact preservation.

## Commands

```text
/wisdom status
/wisdom capture <text>
/wisdom inbox
/wisdom search <query>
/wisdom original <id>
/wisdom interpret <id>
/wisdom apply <id>
/wisdom archive <id>
/wisdom review
/wisdom on
/wisdom off
/wisdom help
```

`/wisdom original <id>` returns the exact stored original for accepted non-secret captures.

## Natural Capture

When enabled, v1 captures only explicit trigger prefixes:

```text
remember this:
remember this <space>
save this:
save this thought:
note this:
business idea:
investing thought:
health note:
life thought:
book note:
podcast idea:
```

The match is prefix-only and case-insensitive after leading whitespace. Ordinary chat and non-Wisdom slash commands are not captured.

## Configuration

Primary configuration lives in `config.yaml`:

```yaml
wisdom:
  enabled: true
  db_path: ""
  capture_mode: explicit
  max_results: 5
  interpret_timeout_seconds: 5
  interpretation:
    mode: deterministic
```

Environment variables are accepted as runtime/test overrides:

```text
HERMES_WISDOM_ENABLED
HERMES_WISDOM_DB_PATH
HERMES_WISDOM_CAPTURE_MODE
HERMES_WISDOM_MAX_RESULTS
HERMES_WISDOM_INTERPRET_TIMEOUT
HERMES_WISDOM_INTERPRETATION_MODE
```

V1 supports `off` and `explicit` capture modes. Smart capture is intentionally not implemented.

## Interpretation and Applications

Capture never calls an LLM.

`/wisdom interpret <id>` creates a deterministic interpretation when none exists. The interpretation is conservative and includes a counterpoint.

`/wisdom apply <id>` creates internal application proposals only. It does not create Hermes todos, reminders, files, calendar entries, Telegram messages, or old productivity DB rows.

## Gateway Behavior

Wisdom is wired as a normal built-in gateway command and a small post-auth, pre-agent natural capture intercept.

If Wisdom fails while handling ordinary non-command text, Hermes continues to the normal chat path. If a `/wisdom` command fails, the user receives a concise error.

The running launchd gateway must be restarted in a later approved run before it loads the new code.

## Known Limitations

- No smart capture.
- No voice transcription capture.
- No scheduled reviews.
- No embeddings or dashboard.
- No old productivity migration.
- No external task/reminder execution.

## Future V2 Ideas

- Smart capture mode.
- Voice note transcript capture.
- Topic-specific capture modes.
- Weekly and monthly reviews.
- Skeptic/challenge mode.
- Theme graph and recurring patterns.
- First-class principles and checklists.
- Source-backed task/reminder execution.
- Optional import from old productivity data after source recovery.
- Apple Notes, Readwise, Notion, or Obsidian import/export.
- Semantic embeddings and dashboard/export.
