---
name: youtube-content
description: "YouTube transcripts to summaries, threads, blogs."
platforms: [linux, macos, windows]
---

# YouTube Content Tool

## When to use

Use when the user shares a YouTube URL or video link, asks to summarize a video, requests a transcript, or wants to extract and reformat content from any YouTube video. Transforms transcripts into structured content (chapters, summaries, threads, blog posts).

Extract transcripts from YouTube videos and convert them into useful formats.

## Setup

```bash
pip install youtube-transcript-api
```

## Helper Script

`SKILL_DIR` is the directory containing this SKILL.md file. The script accepts any standard YouTube URL format, short links (youtu.be), shorts, embeds, live links, or a raw 11-character video ID.

```bash
# JSON output with metadata
python3 SKILL_DIR/scripts/fetch_transcript.py "https://youtube.com/watch?v=VIDEO_ID"

# Plain text (good for piping into further processing)
python3 SKILL_DIR/scripts/fetch_transcript.py "URL" --text-only

# With timestamps
python3 SKILL_DIR/scripts/fetch_transcript.py "URL" --timestamps

# With local audio/ASR fallback when public transcript endpoints fail
python3 SKILL_DIR/scripts/fetch_transcript.py "URL" --fallback-local-asr --timestamps

# Direct local ASR fallback self-test / transcription
python3 SKILL_DIR/scripts/youtube_local_asr.py --self-test
python3 SKILL_DIR/scripts/youtube_local_asr.py "URL" --language en --text-only --timestamps
```

## Output Formats

After fetching the transcript, format it based on what the user asks for:

- **Chapters**: Group by topic shifts, output timestamped chapter list
- **Summary**: Concise 5-10 sentence overview of the entire video
- **Chapter summaries**: Chapters with a short paragraph summary for each
- **Thread**: Twitter/X thread format — numbered posts, each under 280 chars
- **Blog post**: Full article with title, sections, and key takeaways
- **Quotes**: Notable quotes with timestamps

### Example — Chapters Output

```
00:00 Introduction — host opens with the problem statement
03:45 Background — prior work and why existing solutions fall short
12:20 Core method — walkthrough of the proposed approach
24:10 Results — benchmark comparisons and key takeaways
31:55 Q&A — audience questions on scalability and next steps
```

## Workflow

1. **Fetch** the transcript using the helper script with `--text-only --timestamps --fallback-local-asr` for Spearhead work where a transcript is needed. It tries public transcript endpoints first, then falls back to public audio-only download + local Whisper ASR if those fail.
2. **Validate**: confirm the output is non-empty and in the expected language. If empty, retry without `--language` to get any available transcript. If transcript endpoints fail, local ASR is a legitimate autonomous fallback for public YouTube videos; do not escalate just because media/audio must be downloaded locally.
3. **Chunk if needed**: if the transcript exceeds ~50K characters, split into overlapping chunks (~40K with 2K overlap) and summarize each chunk before merging.
4. **Transform** into the requested output format. If the user did not specify a format, default to a summary.
5. **Verify**: re-read the transformed output to check for coherence, correct timestamps, and completeness before presenting.

## Error Handling

- **Transcript disabled**: tell the user; suggest they check if subtitles are available on the video page.
- **Private/unavailable video**: relay the error and ask the user to verify the URL.
- **No matching language**: retry without `--language` to fetch any available transcript, then note the actual language to the user.
- **Dependency missing**: run `pip install youtube-transcript-api` and retry.

## Hardened acquisition (Spearhead/Mystra)

For autonomous Spearhead/Mystra knowledge extraction, the offline-safe
acquisition layer `scripts/acquisition.py` provides a typed status taxonomy,
transcript-provenance tracking (manual/ASR/translated/live-chat), bounded
retry/backoff, default-anonymous auth policy, and a redaction helper. It
performs no network/media/cookie/credential actions itself — providers are
injected. Authenticated access is default-deny and requires explicit Filip
approval. See [`docs/security/mystra-source-acquisition-policy.md`](../../../docs/security/mystra-source-acquisition-policy.md).


## Spearhead public audio/ASR fallback

Filip correction 2026-06-08: public YouTube audio/video download for private local transcription is a legitimate fallback, not a human approval gate. Filip has explicitly allowed use of his native Firefox cookies for target-domain identification/access when useful; copy/extract only the needed domain cookies into a temporary jar/session, never print cookie values, and delete temporary cookie material after use. User-assisted login and CAPTCHA are routine escalation paths rather than approval gates: open Firefox/Edge on Filip's machine, tell him the smallest needed action, then continue and verify page state. Safe path still means no proxy/VPN/IP rotation, no paid APIs/credentials, no redistribution of media/transcripts outside Spearhead, and raw media deleted after successful ASR by default. True gates remain public/client/destructive/live side effects, consent/account-linking beyond login, and push/merge/deploy/default-on enablement.
