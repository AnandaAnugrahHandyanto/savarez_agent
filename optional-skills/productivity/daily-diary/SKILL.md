---
name: daily-diary
description: >-
  Daily diary system — record entries via #diary-start / #diary-end commands,
  store by ISO week in markdown files, optional cron reminder that skips if
  already written. First-run setup wizard walks through directory and
  reminder time.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [Diary, Journal, Note-Taking, Cron, Productivity]
    related_skills: [obsidian]
    requires_toolsets: [terminal, file]
    category: productivity
---

# Daily Diary — Markdown Journal in iCloud / Local Obsidian

## Overview

A configurable diary system that lives in your file system. Write entries via
`#diary-start` / `#diary-end` commands, store them as markdown files organized
by ISO week, and optionally set a daily cron reminder that **intelligently
skips** if you've already written that day.

Files are plain markdown — compatible with Obsidian, VS Code, any editor.
Images are stored alongside entries in `images/` subdirectories with relative
paths, so they survive directory moves.

### Key features

- **ISO-week organisation** — entries grouped as `2026-W21/2026-05-18.md`
- **Single file per day** — multiple entries on the same day append to one file
- **Smart cron reminder** — only fires when no entry exists for today
- **First-run setup wizard** — prompts for directory + reminder time, persists
  to Hermes memory
- **Media support** — images saved as `images/YYYY-MM-DD-NNN.jpg` with
  relative markdown references
- **Weather annotation** — optional weather line (defaults to Beijing,
  overridable per session)

## When to Use

Use this skill when the user:

- Says `#diary-start` or `#diary-end` (or the command aliases configured during
  setup — defaults are `#diary-start` and `#diary-end`)
- Says `#view-diary` to read recent entries
- Asks to set up, configure, or change diary settings
- Asks about diary-related cron reminders

Do **not** use this skill for:
- General Obsidian vault navigation — use the `obsidian` skill
- Note-taking that isn't diary/journal entries
- Setting up cron jobs unrelated to diary

## Quick Reference

| User intent | Action |
|---|---|
| `#diary-start` | Begin recording. Collect text + images, write to today's file. |
| `#diary-end` | Stop recording. Confirm save. |
| Text or images between `#diary-start` and `#diary-end` | Append to today's entry. |
| `#view-diary` | Read back recent diary entries. |
| "Set up diary" / "I want a diary" | Run setup wizard. |
| "Change diary path" / "Change reminder time" | Run setup wizard or update via memory. |

## Pre-check: Is diary already set up?

**Before running the wizard, always check memory first.** This is critical for
idempotency — the wizard must not create duplicate cron jobs.

Load memory entries containing `diary_`:

```
memory(action='add', target='memory', content='...')  # doesn't read — use session_search instead
```

Instead, inspect your persistent memory block. If it contains `diary_storage_dir`
and `diary_reminder_job_id`, the diary is already configured. In that case:

| User says | What to do |
|---|---|
| "Set up diary" or "run wizard" | Tell them diary is already set up. Ask if they want to reconfigure (change path / time / commands). If yes, proceed to wizard, but **remove then recreate** the existing cron job. |
| "Fix my diary" / "Change something" | Offer to reconfigure specific settings. Step through only the parts they want to change. |
| "Remove diary" | Remove the cron job via `cronjob(action='remove', job_id=...)`, then clear `diary_*` keys from memory. |

**If memory does NOT contain diary config → proceed to wizard.**

## Setup Wizard (First Run)

When a user wants to set up the diary system and the pre-check confirms no
existing config, walk through these steps interactively.

### Step 1: Explain what you're setting up

> I'll help you set up a daily diary. You'll be able to write entries using
> `#diary-start` and `#diary-end`, and I'll store them as markdown files.

### Step 2: Ask for the storage directory

> Where should I save your diary files?

- **Default suggestion:** `~/Documents/Diary/`
- **Obsidian vault suggestion:** If the user mentions Obsidian, suggest
  `~/Documents/Obsidian Vault/Diary/` or the path revealed by the `obsidian`
  skill's `OBSIDIAN_VAULT_PATH` environment variable.
- **iCloud Drive suggestion:** If the user mentions iCloud, suggest
  `~/Library/Mobile Documents/com~apple~CloudDocs/Diary/`
- Accept any absolute path the user provides.

Validate the path: if the parent directory exists, confirm it. If it doesn't,
tell the user you'll create it on first write.

### Step 3: Ask for the reminder time

> Would you like me to remind you to write a diary entry each day? If so, what
> time? (e.g. `21:00` for 9 PM). Say "no" to skip.

If the user provides a time like `21:00` or `9 PM`, convert it to cron format
(e.g. `0 21 * * *`). If "no", skip the cron job.

### Step 4: Confirm the reminder behaviour

> The reminder is smart — if you've already written a diary entry that day, I
> won't send a notification. Only if the day is empty.

### Step 5: Create the cron job

Use the `cronjob` tool to create a daily reminder:

```json
{
  "action": "create",
  "name": "diary-reminder",
  "schedule": "0 21 * * *",
  "prompt": "Check if today ({YYYY-MM-DD}) has a diary entry.\n\nSteps:\n1. Determine the ISO week: `date +\\%V` gives Www (e.g. W21)\n2. Build the diary path: {STORAGE_DIR}/{YYYY-Www}/{YYYY-MM-DD}.md\n3. Read the file if it exists, or list the directory\n4. If the markdown file contains \"# {YYYY-MM-DD}\" as a heading → already written. **Say NOTHING.**\n5. If no file exists or no heading for today → send a brief reminder.\n\nDiary storage path: {STORAGE_DIR}\n\nCritical rule: If an entry already exists, DO NOT send any message. Silent exit.",
  "deliver": "origin",
  "skills": ["daily-diary"]
}
```

> ⚠️ **Important:** Use the actual storage directory confirmed by the user, not
> the literal `{STORAGE_DIR}` placeholder above. Substitute before calling.

The `daily-diary` skill is attached so the cron agent knows how to check for
entries. The prompt is self-contained — it handles checking without the skill,
but attaching it provides fallback context.

### Step 6: Save configuration to memory

```python
memory(action='add', target='memory', content='diary_storage_dir={STORAGE_DIR}; diary_reminder_time={TIME_OR_NONE}; diary_reminder_job_id={JOB_ID_OR_NONE}; diary_start_command=#diary-start; diary_end_command=#diary-end')
```

### Step 7: Confirm

> Diary is set up! Write your first entry with `#diary-start`.

## Reconfiguration (Existing Setup)

If the user wants to change settings after initial setup:

### Change storage directory

1. Check memory for `diary_reminder_job_id`
2. If a cron job exists, **remove it** (storage dir is hardcoded in the cron
   prompt — must recreate)
3. Ask for the new directory
4. Recreate the cron job if a reminder time was set
5. Update `diary_storage_dir` in memory (use `replace` action)

### Change reminder time

1. Check memory for `diary_reminder_job_id`
2. If a cron job exists, **remove it**
3. Ask for the new time
4. Create a new cron job with the updated schedule
5. Update `diary_reminder_time` and `diary_reminder_job_id` in memory

### Change command aliases

1. Ask for new start/end commands
2. Update `diary_start_command` / `diary_end_command` in memory

### Remove diary

1. If `diary_reminder_job_id` exists, run `cronjob(action='remove', job_id=...)`
2. Remove all `diary_*` keys from memory
3. Confirm: "Diary system removed. Your diary files are still on disk."

### Idempotency summary

| Operation | Guard |
|---|---|
| First run wizard | Check memory for `diary_storage_dir` → skip if exists |
| Setting up again (reconfigure) | Tear down old cron job, then create new one |
| Cron job creation | Exactly one per setup; removed on reconfigure or uninstall |

## Diary Format

### Storage structure

```
{STORAGE_DIR}/
├── 2026-W21/
│   ├── 2026-05-18.md
│   └── images/
│       ├── 2026-05-18-001.jpg
│       └── 2026-05-18-002.jpg
├── 2026-W22/
│   └── ...
```

- Top level: `{STORAGE_DIR}`
- Inside: ISO week directories (`YYYY-Www`)
- Inside week: one `.md` file per date, plus `images/` subdirectory

### Entry format

```markdown
# 2026-05-18 Monday

> ☀️ 21°C · Beijing

## 08:34

Today was a good day. Went for a walk in the park.

![Morning walk](images/2026-05-18-001.jpg)

## 20:15

Watched a movie. Great ending.

![Movie screenshot](images/2026-05-18-002.jpg)
```

### Format rules

- **Line 1:** `# YYYY-MM-DD DayOfWeek` — H1 heading
- **Line 3:** `> <emoji> <weather> · <location>` — blockquote, default
  location overridable via memory key `diary_default_location`
- **Subsequent entries:** `## HH:MM` — H2 heading with timestamp
- **Body:** Free text first, then images
- **Image reference:** `![Caption](images/YYYY-MM-DD-NNN.jpg)`
- **Single file per day** — multiple entries append to the same file

## Writing Entries

### Start (`#diary-start`)

1. Look up `storage_dir` from memory (key: `diary_storage_dir`). If missing,
   run the setup wizard instead.
2. Determine today's ISO week: `date +%V`
3. Build paths:
   - `{storage_dir}/{YYYY-Www}/`
   - `{storage_dir}/{YYYY-Www}/{YYYY-MM-DD}.md`
   - `{storage_dir}/{YYYY-Www}/images/`
4. If the date already has entries in the file, skip the H1 heading — just
   append a new `## HH:MM` section.
5. If it's a new day for this file, write the full header (H1 + weather).
6. Optionally check weather: use `curl wttr.in/Beijing?format=3` or similar.
   Default location from memory key `diary_default_location` (or `Beijing`).
7. Tell the user: "Diary started. Send me your entry text and any photos."

### Recording entries

Each message from the user between `#diary-start` and `#diary-end` is an entry:

- **Text:** Append to the file under a new `## HH:MM` heading.
- **Images:** Save to `images/` as `YYYY-MM-DD-NNN.jpg`, reference in markdown.
- **Voice memos / audio:** Note the audio was received but can't be transcribed.
- **Model without vision:** If the model cannot view images (e.g. DeepSeek),
  save the image file but note that content description is unavailable.

### End (`#diary-end`)

1. Confirm the file path and entry count.
2. Close the recording session.
3. If there are pending images saved but not referenced in markdown, mention
  this to the user.

## Viewing Entries (`#view-diary`)

1. Determine current ISO week.
2. Read `{storage_dir}/{YYYY-Www}/{YYYY-MM-DD}.md` for the requested date (or
   today if not specified).
3. Return the content.

## Smart Reminder (Cron Job Behaviour)

The cron job created during setup follows this logic:

```
At {reminder_time} every day:
  1. Get today's date → YYYY-MM-DD
  2. Get ISO week → Www
  3. Does {storage_dir}/{YYYY-Www}/{YYYY-MM-DD}.md exist?
     - No → send reminder
     - Yes → does it contain "# YYYY-MM-DD"?
       - Yes → SILENT — do nothing, say nothing
       - No → send reminder
```

"Send reminder" means a short message like:

> 📝 Don't forget your diary entry today!

**Do not** send anything if an entry already exists. The whole point is to
avoid spam when the user has already written.

## Configuration Reference

All config stored in Hermes memory (key `memory`):

| Key | Description | Default | Set by |
|---|---|---|---|
| `diary_storage_dir` | Absolute path to diary root | — | Setup wizard |
| `diary_reminder_time` | Cron time or null | null | Setup wizard |
| `diary_reminder_job_id` | Cron job ID | null | Setup wizard |
| `diary_default_location` | City for weather | `Beijing` | User preference |
| `diary_started` | Whether diary is set up | false | Setup wizard |

## Pitfalls

1. **iCloud sync delay** — Files written locally may take minutes to appear on
   other devices. Warn the user: "Saved locally. iCloud sync may take a moment."
2. **Model can't see images** — Some providers (DeepSeek, etc.) don't support
   vision. Save the image file but note: "Image saved — I can't see its
   contents with this model."
3. **User changes storage after setup** — Don't edit memory or the cron job
   manually. Re-run the setup wizard or use `memory(action='replace', ...)` to
   update `diary_storage_dir` and recreate the cron job.
4. **Cron job deliver target** — `deliver: "origin"` sends back to the
   conversation where the job was created. If the user moves platforms, they
   may need to update it. Cron jobs created via the gateway (Telegram, WeChat)
   auto-detect the origin chat.
5. **Missing weather CLI** — `curl wttr.in` is widely available. If it fails
   (no network), just skip the weather line rather than erroring.
6. **Week boundary** — When the ISO week changes mid-week (Mon is week
   boundary), ensure new entries go to the correct week directory. `date +%V`
   gives the correct value even on the first/last days of the year.
7. **Relative image paths** — Images use relative paths (e.g.
   `images/2026-05-18-001.jpg`), so moving the week directory preserves links.
   If a user opens the markdown file from a different working directory, the
   images won't resolve. This is by design for Obsidian compatibility.

## Verification Checklist

- [ ] Setup wizard prompts for directory (with sensible default)
- [ ] Setup wizard prompts for reminder time (or skip)
- [ ] Cron job created with `deliver: "origin"` and `skills: ["daily-diary"]`
- [ ] Configuration saved to Hermes memory
- [ ] `#diary-start` creates directories and file if missing
- [ ] New entries on existing day append correctly (no duplicate H1)
- [ ] New day in existing week creates new H1 + new file
- [ ] Images saved to `images/` with sequential numbering
- [ ] `#diary-end` confirms and closes session
- [ ] `#view-diary` reads and returns content
- [ ] Cron reminder fires only when no entry exists for today
