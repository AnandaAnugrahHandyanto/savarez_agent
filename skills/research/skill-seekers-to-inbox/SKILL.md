---
name: skill-seekers-to-inbox
description: >
  Bridge between the skill-seekers CLI (docs-site / GitHub repo / PDF / video
  bulk crawler) and the neuro-os research inbox. Run skill-seekers to flatten a
  source into one Markdown file per page, then this skill loops the
  references/*.md files into ~/.neuro_os_research/inbox.jsonl as
  one InboxRecord per page. Use when the user wants to ingest a whole
  documentation site, a GitHub repo, or a PDF (rather than a single URL —
  for one URL, use the url-to-inbox skill).
version: 0.1.0
author: Hermes Agent + Neuro-OS
license: MIT
metadata:
  hermes:
    tags: [Research, Inbox, Neuro-OS, Bulk-Ingest, Skill-Seekers]
    related_skills: [url-to-inbox, youtube-content, ocr-and-documents]
    homepage: https://github.com/wjlgatech/neuro-os/blob/main/docs/url-to-living-knowledge.md
prerequisites:
  pip: [skill-seekers]
---

# Skill-Seekers → Neuro-OS Inbox

Convert a documentation site / GitHub repo / PDF / video / Jupyter notebook into
one neuro-os `InboxRecord` per page, so the **research vertical's** review +
compression pipeline takes over from there. This skill is the **bulk** sibling
of `url-to-inbox` (which handles a single URL at a time).

## Why both `url-to-inbox` and this skill exist

| Use case | Pick |
|---|---|
| Paul forwards one YouTube link or one blog post | `url-to-inbox` (one record, one append) |
| Paul wants to ingest a whole docs site, a GitHub repo, a PDF book | `skill-seekers-to-inbox` (N records, one batch) |
| Paul wants ongoing monitoring of a blog | `blogwatcher` skill — different pipeline (RSS polling), no neuro-os bridge |

This skill **composes** `url-to-inbox`'s `append_inbox.py` rather than
duplicating the InboxRecord schema. There is exactly one producer in the
codebase. If neuro-os evolves the schema, both skills inherit the change.

## Pipeline

```
SOURCE (URL/repo/PDF/video)
        │
        │  skill-seekers create
        ▼
<output_dir>/
  SKILL.md             ← skill-seekers' wrapper (we ignore)
  references/
    index.md           ← we skip (navigation file)
    section_01.md      ← one InboxRecord
    section_02.md      ← one InboxRecord
    ...
        │
        │  flush_references.py
        ▼
~/.neuro_os_research/inbox.jsonl
        │
        │  neuro-os research inbox ingest
        ▼
MechanismCardProposals → research review → goal-link → living knowledge
```

`flush_references.py` does NOT call skill-seekers itself — that's a deliberate
separation so the user runs skill-seekers with whatever flags suit their source
(`--repo`, `--pdf`, `--video-url`, `--max-pages`, etc.) and then hands the
output directory to this skill.

## Quick reference

```bash
# 1. Crawl with skill-seekers (no API key needed for default 'scrape-only').
skill-seekers create \
  --url https://docs.something.com \
  --output /tmp/something-docs \
  --max-pages 50 \
  --skip-scrape false \
  --non-interactive

# 2. Flush the references/ folder into the neuro-os inbox.
SKILL_DIR=~/.hermes/skills/skill-seekers-to-inbox
python "$SKILL_DIR/scripts/flush_references.py" \
  --references-dir /tmp/something-docs/references \
  --base-url https://docs.something.com \
  --sender paul@example.com \
  --source-type blog

# 3. neuro-os does the rest.
neuro-os research inbox ingest
```

## Source-type-by-skill-seekers-mode

skill-seekers can ingest 10+ source types; map each to a sensible `--source-type`
when flushing:

| skill-seekers invocation | Recommended `--source-type` |
|---|---|
| `--url <docs site>` | `blog` |
| `--repo owner/repo` | `other` (treat README + key .md files as blog-equivalent) |
| `--pdf <path>` | `pdf` |
| `--video-url <YouTube playlist>` | `youtube` |
| `--video-file <file>` | `youtube` (closest match; "video" is not in the neuro-os enum) |
| Notebook / wiki / EPUB | `other` |

If the right answer is genuinely "other," set `--source-type other` — that's a
first-class value in the neuro-os InboxRecord schema and ingest treats it the
same as `blog` downstream.

## Front-matter handling

`flush_references.py` parses YAML-ish front-matter at the top of each `.md`:

```yaml
---
source_url: https://docs.example.com/page-3
title: Page Three
author: Some Person
---
# Page Three

Body content...
```

Resolution order for each field:

| Field | Lookup |
|---|---|
| `url` | `source_url` → `url` → `permalink` → `canonical` → `base_url + slug` → `skill-seekers://<filename>` |
| `title` | `title` → first `# H1` line → filename humanized |
| `author` | `author` → "skill-seekers" |

If you ran `skill-seekers create` with a `--base-url` known and the per-page
files lack `source_url`, pass `--base-url` to `flush_references.py` so URLs
resolve to something useful (`<base>/<slug>`) instead of synthetic
`skill-seekers://...` ones.

## Idempotency

Same rules as the upstream `url-to-inbox` skill:

- Re-running `flush_references.py` against the same directory appends every
  file again. neuro-os's sha256 dedup at ingest time catches re-extracted
  identical bodies, counting them in `records_skipped_duplicate`.
- If the source changed, both versions get distinct proposals (different sha).

If you want producer-side idempotency, run with `--dry-run` first to see
what WOULD be appended, then with `--max-records` to stage in batches.

## Why this is a bridge skill, not a tool

Same reasoning as `url-to-inbox` — composing two CLIs (skill-seekers and the
sibling skill's `append_inbox.py`) is a workflow, not a function call. Keeping
it as a skill means:

- No prompt-cache cost for users who never use skill-seekers.
- `flush_references.py` works equally well from cron, the Telegram gateway,
  or a one-shot `bash` invocation — no agent loop needed.
- The bridge has its OWN tests; the schema lives only in
  `url-to-inbox/scripts/append_inbox.py`.

## Failure modes (real ones)

| Symptom | Diagnosis | Fix |
|---|---|---|
| `flush_references.py` exits 1: "references dir not found" | skill-seekers's output dir is at `<out>/SKILL.md` + `<out>/references/`, not just `<out>/`. | Point `--references-dir` at the `references/` subfolder explicitly. |
| All records skipped with `schema: title must be at least 1 char` | The .md files have empty H1 lines and no front-matter `title`. | Pass `--base-url` and rely on filename-derived titles, or fix the upstream skill-seekers run with `--enhance-level metadata`. |
| URLs in inbox come out as `skill-seekers://<filename>` | The .md files lacked front-matter URLs and no `--base-url` was passed. | Re-run with `--base-url <root>`; neuro-os accepts the synthetic URLs but they're noisy in the dashboard. |
| neuro-os shows `records_skipped_duplicate=N` after a re-flush | Same source content, sha256 matches existing proposals. | That's working as intended — neuro-os dedup is body-based, not URL-based. |

## Related

- **`url-to-inbox`** — single-URL producer. Use that for one link at a time.
- **`skill-seekers`** (PyPI) — the upstream crawler. `pip install skill-seekers`.
  See https://skillseekersweb.com/ for preset configs.
- **neuro-os research vertical** — the consumer side:
  https://github.com/wjlgatech/neuro-os/blob/main/docs/url-to-living-knowledge.md
- **`agentskills-integration-eval.md`** (in neuro-os/docs/plans/) — design
  notes on why this skill exists as a bridge instead of as a Claude-Code skill
  that competes with neuro-os's extraction layer.
