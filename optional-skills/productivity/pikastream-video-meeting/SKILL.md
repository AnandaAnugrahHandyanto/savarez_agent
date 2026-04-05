---
name: pikastream-video-meeting
description: Join a Google Meet or Zoom call as a real-time AI avatar using the open-source Pika Skills workflow and the Pika Developer API.
version: 1.0.0
author: Hermes Agent + Pika Labs
license: Apache-2.0
metadata:
  hermes:
    tags: [video, meetings, google-meet, zoom, avatar, voice-cloning, pika, realtime]
    related_skills: [imessage, telephony, google-workspace]
    category: productivity
---

# PikaStream Video Meeting

This official optional skill vendors the open-source `pikastream-video-meeting` workflow from Pika Labs into Hermes' optional-skills catalog so users can install it with:

```bash
hermes skills install official/productivity/pikastream-video-meeting
```

Use this skill when the user wants Hermes to join a Google Meet or Zoom call as a video participant with a generated or uploaded avatar and an optional cloned voice.

Requirements:
- `PIKA_DEV_KEY` for the Pika Developer API
- Python 3
- `requests` (installed from `requirements.txt`)
- `ffmpeg` if the user wants audio conversion during voice cloning

Upstream source:
- Repo: https://github.com/Pika-Labs/Pika-Skills
- Upstream skill path: `pikastream-video-meeting/`
- License: Apache 2.0

Notes for Hermes:
- This is an optional third-party workflow, not a Hermes core tool.
- The vendored script is adapted as a normal installed Hermes skill and should be run from the installed skill directory.
- For paid actions or user-provided identity assets, always ask before proceeding.

## First-time setup

Run once after install:

```bash
SCRIPT="$(find ~/.hermes/skills -path '*/pikastream-video-meeting/scripts/pikastreaming_videomeeting.py' -print -quit)"
pip install -r "$(dirname "$SCRIPT")/../requirements.txt"
```

If `SCRIPT` is empty, the skill is not installed yet.

### Avatar

Check whether `identity/videomeeting-avatar.png` exists and is larger than 1 KB.

If not:
1. Ask the user for a headshot/portrait image, or ask whether they want you to generate one.
2. Do not proceed until they answer.
3. If they send an image, save it to `identity/videomeeting-avatar.png`.
4. If they want generation, run:

```bash
python "$SCRIPT" generate-avatar   --output identity/videomeeting-avatar.png
```

If they describe the avatar, append `portrait headshot suitable for video calls` to the prompt.
Show the generated avatar and ask whether to keep it or regenerate it.

### Voice

Check whether `life/voice_id.txt` exists and is non-empty.

If it exists, inspect `life/voice_config.json` when available. If the cloned voice is 6+ days old, warn the user that Pika voice clones may expire after 7 days of non-use and ask whether to re-clone or try the existing voice.

If there is no saved voice (or the user wants to re-clone):
1. Ask for a 10s-5min voice recording with clear speech, or let them say `skip` to use the default voice.
2. Do not proceed until they answer.
3. If they say `skip`, use `English_radiant_girl`.
4. If they send audio, run:

```bash
python "$SCRIPT" clone-voice   --audio <file> --name <bot-name> --noise-reduction
```

If cloning succeeds, read `life/voice_id.txt` and use that voice ID.
If cloning fails, show the error and ask whether to retry or fall back to the default voice.

## Join flow

### Step 1 — validate and gather context

Before joining:
- verify `identity/videomeeting-avatar.png` exists and is > 1 KB
- verify a voice is available, or intentionally fall back to `English_radiant_girl`
- gather fresh context instead of reusing a stale prompt file

Read workspace files (for example `MEMORY.md`, notes, logs, or identity files). If there is not enough local context, ask the user what name the bot should use and keep the reference card short.

Write a concise meeting reference card to `/tmp/meeting_system_prompt.txt` using concrete facts, recent activity, people, and current context. Do not invent facts.

### Step 2 — join

```bash
python "$SCRIPT" join   --meet-url <url>   --bot-name <name>   --image identity/videomeeting-avatar.png   --system-prompt-file /tmp/meeting_system_prompt.txt   --voice-id <id>
```

Optional:
- add `--meeting-password <pw>` for password-protected meetings
- use `--platform zoom` if URL inference fails

Important:
- Exit code `0` means the bot joined successfully.
- Exit code `6` means insufficient credits; show the returned `checkout_url` to the user.
- Keep the returned `session_id` if you may need to leave later.

## Leave

```bash
python "$SCRIPT" leave --session-id <id from join output>
```

## Safety and expectations

- Always confirm before joining a live meeting.
- Never upload a user's likeness or voice without explicit consent.
- Treat meeting URLs, voice recordings, and generated identity assets as sensitive.
- Pika credits and API availability are external to Hermes.

## Verification

After installing dependencies, a local smoke check is:

```bash
python "$SCRIPT" --help
python "$SCRIPT" generate-avatar --help
python "$SCRIPT" clone-voice --help
python "$SCRIPT" join --help
```
