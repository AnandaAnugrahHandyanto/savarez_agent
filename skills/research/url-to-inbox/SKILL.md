---
name: url-to-inbox
description: >
  Convert any URL (YouTube video, blog post, X/Twitter thread, PDF, raw email body)
  into a structured InboxRecord and append it to neuro-os's research inbox at
  ~/.neuro_os_research/inbox.jsonl. Pairs with the neuro-os research vertical
  (URL-to-Living-Knowledge loop). Use when the user forwards a link, asks to
  "capture" or "save" content for later review, or wants research material to
  land as a MechanismCardProposal instead of a flat note.
version: 0.1.0
author: Hermes Agent + Neuro-OS
license: MIT
metadata:
  hermes:
    tags: [Research, Knowledge, Inbox, Neuro-OS, Capture, URL]
    related_skills: [youtube-content, blogwatcher, ocr-and-documents, google-workspace]
    homepage: https://github.com/wjlgatech/neuro-os/blob/main/docs/url-to-living-knowledge.md
---

# URL → Neuro-OS Research Inbox

Take a URL → extract text → append a pre-validated `InboxRecord` JSON line to
`~/.neuro_os_research/inbox.jsonl`. On the next `neuro-os research inbox ingest`,
the record becomes a `MechanismCardProposal` in the user's review queue and
eventually a `MechanismCard` linked (via `research goal`) to a startup-vertical
revenue goal.

This skill is the **producer** half of the URL-to-Living-Knowledge loop. The
**consumer** half is neuro-os; nothing in this skill talks to neuro-os over the
network — the contract is a JSONL file both sides can read and write.

## Quick reference

| Action | Command |
|---|---|
| Extract a URL → JSON payload | `python SKILL_DIR/scripts/extract_url.py --url <URL>` |
| Append a payload to the inbox | `python SKILL_DIR/scripts/append_inbox.py --url <URL> --source-type <T> --title <S> --text-file <PATH>` |
| One-shot (extract + append) | `python SKILL_DIR/scripts/extract_url.py --url <URL> --out-json /tmp/p.json && python SKILL_DIR/scripts/append_inbox.py --url <URL> --source-type "$(jq -r .source_type /tmp/p.json)" --title "$(jq -r .title /tmp/p.json)" --text-file <(jq -r .extracted_text /tmp/p.json)` |
| Show the InboxRecord schema (consumer side) | See [neuro-os/agent/research/inbox.py](https://github.com/wjlgatech/neuro-os/blob/main/agent/research/inbox.py) |

`SKILL_DIR` is the directory containing this `SKILL.md`.

## The contract (InboxRecord)

One JSON object per line in `~/.neuro_os_research/inbox.jsonl`. The schema is
defined by `agent.research.inbox.InboxRecord` on the neuro-os side; this skill's
`append_inbox.py` mirrors the constraints so you fail fast if a producer writes
something invalid.

```json
{
  "url":            "https://...",            // required, 1..2000
  "source_type":    "youtube",                // required: youtube|blog|twitter|pdf|email-body|other
  "title":          "Distribution is the moat", // required, 1..400
  "author":         "Speaker Name",           // default "unknown", 1..200
  "extracted_text": "...transcript or body...", // required, 1..400_000
  "extracted_at":   "2026-05-23T12:00:00+00:00", // ISO-8601, set automatically
  "sender":         "paul@example.com",       // optional, checked against neuro-os inbox_allowlist.json
  "urge_tag":       "novelty",                // optional founder-loop drift mode
  "topic_tags":     ["mlops","agents"]        // optional, max 20
}
```

`urge_tag` is one of `novelty | social | frustration | fatigue | decision_fatigue | embodied`
(matches neuro-os's founder-loop drift modes). When present, neuro-os prefixes
the resulting proposal's `reasoning` with `[urge:<tag>]` so the human reviewer
sees provenance — "this came in during a novelty urge, not a focused capture."

## Dispatch table (source_type by URL)

| Host / pattern | `source_type` | Extractor |
|---|---|---|
| `youtube.com`, `youtu.be`, `*.youtube.com` | `youtube` | `youtube_transcript_api` (with HTML fallback) |
| `twitter.com`, `x.com` | `twitter` | static HTML scrape (best-effort; client-rendered threads need the `xitter` skill upstream) |
| URL ends with `.pdf` | `pdf` | NOT handled here — pipe through `ocr-and-documents` skill first |
| anything else | `blog` / `other` | urllib + stdlib HTML reducer (script/style stripped, paragraphs preserved) |

Use `--source-type auto` (default) to let the script detect. Override with a
specific value when you know better (e.g. a Substack post on a non-`.blog` host).

## Typical flows

### Manual (one URL, from a terminal)

```bash
SKILL_DIR=~/.hermes/skills/url-to-inbox

# 1. Extract.
python "$SKILL_DIR/scripts/extract_url.py" \
  --url "https://youtube.com/watch?v=abc123" \
  --out-json /tmp/yt.json

# 2. Append.
python "$SKILL_DIR/scripts/append_inbox.py" \
  --url "$(jq -r .url /tmp/yt.json)" \
  --source-type "$(jq -r .source_type /tmp/yt.json)" \
  --title "$(jq -r .title /tmp/yt.json)" \
  --author "$(jq -r .author /tmp/yt.json)" \
  --text-file <(jq -r .extracted_text /tmp/yt.json) \
  --sender paul@example.com \
  --urge-tag novelty

# 3. Hand off to neuro-os (different repo, separate command).
neuro-os research inbox ingest
```

### Gmail watcher (Hermes cron)

Run this skill from a Hermes cron job that watches your Gmail inbox via the
`google-workspace` skill. For each new email with a URL, dispatch to
`extract_url.py` then `append_inbox.py`, using the email's `From:` header as
`--sender`. neuro-os's `inbox_allowlist.json` decides whether the sender is
authorised; you don't need to filter at this layer.

### Telegram forward

Receive a message in your Hermes Telegram gateway → extract URLs from the
message body → for each URL, run `extract_url.py` → `append_inbox.py`. Pass
`--urge-tag` if the user attached a `#novelty` / `#social` / `#frustration`
hashtag.

### Browser share-target / macOS Share Sheet

Wire a POST endpoint that receives `{url, title?, sender?}`, then runs the same
two scripts. Append-only writes are safe under concurrent producers (each is
one `f.write(line + "\n")` call holding the file open in append mode).

## Idempotency + dedup

This skill DOES NOT dedup — every `append_inbox.py` call writes one new line.
neuro-os deduplicates on the **sha256 of the body text** at consume time, so:

- Re-extracting the same URL while the page is unchanged → second proposal
  collapsed into `records_skipped_duplicate` in the run summary.
- Re-extracting the same URL after the page changed → both proposals emitted
  (different sha → different proposals).

If you want producer-side dedup (e.g. cron polling Gmail), keep your own URL
log; this skill stays simple by leaving dedup to neuro-os.

## Allowlist behaviour (sender field)

`--sender` is forwarded verbatim to the InboxRecord. neuro-os checks the value
against `~/.neuro_os_research/inbox_allowlist.json` at ingest time:

- File missing or empty → every record passes (solo / local-only).
- File populated → only records whose `sender` is listed pass; others are
  counted in `records_skipped_disallowed` and skipped without proposals.

The skill itself never reads the allowlist — that's a deliberate separation so
producers can run as untrusted code while neuro-os enforces auth.

## Failure modes

| Symptom | Diagnosis | Fix |
|---|---|---|
| `append_inbox.py` exits 2 with "X must be at least Y chars" | A required field is missing or empty in your producer call. | Check the schema in the "Contract" section above. |
| `extract_url.py` returns "(youtube-transcript-api not installed)" | `youtube_transcript_api` Python package isn't installed. | `pip install youtube-transcript-api` |
| Twitter extraction returns mostly metadata | X/Twitter renders threads client-side; static HTML has only og:tags. | Use Hermes's `xitter` skill upstream to fetch full thread text, then call `append_inbox.py` directly. |
| neuro-os shows `records_skipped_disallowed=N` after a batch | The sender isn't on the allowlist. | Add it to `~/.neuro_os_research/inbox_allowlist.json`, OR drop the allowlist file entirely. |
| Inbox grows but `neuro-os research inbox status` shows `cursor=<old>` | You haven't run `neuro-os research inbox ingest` yet. | Run it. |

## Related skills

- **youtube-content** — alternative front-end if you want the transcript as
  Markdown/chapters/threads instead of into the neuro-os inbox.
- **google-workspace** — the Gmail polling side of the cron flow above.
- **ocr-and-documents** — preprocess PDFs before piping the text into
  `append_inbox.py --source-type pdf`.
- **xitter** — fetch full X/Twitter threads when this skill's static HTML
  scraper isn't enough.
- **neuro-os research vertical** — the consumer side. See
  https://github.com/wjlgatech/neuro-os/blob/main/docs/url-to-living-knowledge.md
  for the end-to-end walkthrough.

## Why a skill, not a tool?

This is a workflow that composes other tools (HTTP fetch, transcript API,
JSONL append). Putting it in `tools/` would require a registry entry, schema,
and toolset wiring. As a skill, the LLM reads SKILL.md, dispatches the scripts,
and the user can run the same scripts from a shell. No prompt-cache cost for
users who don't enable it.
