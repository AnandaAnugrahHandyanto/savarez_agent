# Hermes Wisdom Kernel

Hermes Wisdom Kernel is a local, source-backed capture and recall subsystem for conversational personal knowledge.

v1 built the durable kernel: exact-original preservation, deterministic capture/classification, search, deterministic interpretation, and internal application proposals.

v2 exposes that kernel as native Hermes model tools, so normal Hermes/Codex conversations can save, search, retrieve exact wording, review, and apply saved ideas without requiring `/wisdom` syntax. `/wisdom` commands remain as fallback/debug/power-user controls.

Wisdom does not write to the old productivity database and does not take external actions.

## Natural Language Tools

Hermes now registers these native model tools in the default CLI and messaging toolsets, including Telegram:

```text
wisdom_status
wisdom_capture
wisdom_search
wisdom_original
wisdom_interpret
wisdom_apply
wisdom_review
wisdom_archive
wisdom_inbox
wisdom_set_enabled
```

Expected natural-language behavior:

```text
Remember this: clients don't buy alpha, they buy peace of mind.
Find that idea about peace of mind.
Show me exactly what I wrote about peace of mind.
Turn that into client language for x10x.
What have I been thinking about investing recently?
```

The model sees tool descriptions that tell it when to use Wisdom. There is no large regex command translator in v2. The model decides when a durable operation is needed, calls the relevant Wisdom tool, and replies from the tool result.

Wisdom should not be used for ordinary informational chat such as:

```text
Explain PMS vs AIF.
Help me debug Hermes.
```

unless the user explicitly asks to remember, save, find, retrieve, review, or apply saved Wisdom material.

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

Commands and native tools share the same Wisdom service layer and the same SQLite-backed kernel.

## Explicit Gateway Capture

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

The match is prefix-only and case-insensitive after leading whitespace. Ordinary chat and non-Wisdom slash commands are not captured by this deterministic gateway intercept.

This v1 intercept remains for low-friction explicit capture. v2 natural-language use happens through model tool calls, not through expanding this deterministic router.

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

`/wisdom apply <id>` and `wisdom_apply` create internal application proposals only. They do not create Hermes todos, reminders, files, calendar entries, Telegram messages, or old productivity DB rows.

For richer wording, the model can use the stored proposal and produce a natural response. Durable writes still go through the deterministic Wisdom kernel.

## Gateway Behavior

Wisdom is wired as a normal built-in gateway command and a small post-auth, pre-agent explicit capture intercept. v2 does not add a new gateway router; it relies on the existing AIAgent tool loop.

If Wisdom fails while handling ordinary non-command text, Hermes continues to the normal chat path. If a `/wisdom` command fails, the user receives a concise error.

The running launchd gateway must be restarted after deploying v2 before it loads the new tool module.

Safe restart command:

```bash
launchctl kickstart -k gui/$(id -u)/ai.hermes.gateway
```

## Known Limitations

- No smart capture.
- No auto-capture of every conversation.
- No voice transcription capture.
- No scheduled reviews.
- No embeddings or dashboard.
- No old productivity migration.
- No external task/reminder execution.
- No live model-call tests are required for the tool layer; tests prove registration, schemas, dispatcher behavior, and deterministic tool results.
- `period` and `context` tool inputs are lightweight guidance for review/reply ergonomics, not new schedulers or creative DB writers.

## Future V3 Ideas

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
