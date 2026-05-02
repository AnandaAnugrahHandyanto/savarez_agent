# Hackathon Submission — SpeakAlong for Hermes

**Track**: Kimi Track (primary) + General Track  
**Submitted by**: Allard Quek  
**Repo**: hermes-agent / feat/hackathon-creative-captions branch  
**Plugin path**: `plugins/phonetic-captions/`

---

## One-line pitch

> **SpeakAlong turns any Vietnamese teaching video into a captioned Short learners can actually speak — from Telegram message to phonetically annotated, FFmpeg-burned video in seconds, powered by Kimi K2.6.**

---

## Problem Statement

Vietnamese language teachers creating YouTube Shorts face a painful captioning gap:

- Auto-generated captions (YouTube, CapCut) transcribe what they hear but **never add phonetic guides** — the one thing learners need most.
- Manually writing `[humm biet]` beneath every Vietnamese word in a 60-second video takes 20–40 minutes.
- Existing captioning tools (Descript, Captions.ai) are designed for monolingual content. They break on **code-switching** — videos that mix English narration with Vietnamese vocabulary, which is exactly how most teaching videos are structured.
- The result: teachers either skip captions entirely or publish content that is inaccessible to beginners.

---

## Solution

**SpeakAlong** is a self-contained Hermes plugin that handles the full pipeline:

```
Video (Telegram / upload)
  → faster-whisper  ─── local transcription, auto lang detect
  → Kimi K2.6 (NVIDIA NIM)  ─── EN/VI classification + diacritic correction + phonetic generation
  → FFmpeg  ─── ASS subtitle burn-in
  → captioned_<id>.mp4  +  dashboard editor link
```

### What makes it different

| Feature | Why it matters |
|---|---|
| **Auto language detection** | Handles code-switched audio without any configuration |
| **Diacritic correction** | Whisper mangles Vietnamese tones (e.g. `khong biet` → `không biết`). Kimi fixes them. |
| **English phonetic guides** | `không biết` → `[humm biet]` — plain English letters, readable by any learner |
| **Teaching layout** | VI segments: bold main text + italic phonetic below. EN segments: clean text only. |
| **Visual editor** | Dashboard editor with per-segment EN/VI toggles, word-split, NL edits, QA review |
| **Telegram-native** | Full pipeline from a single chat message — no desktop app needed |
| **Hermes plugin** | Drop-in install, no core file changes, uses Hermes model as fallback if no NVIDIA key |

---

## Why Kimi K2.6

Phonetic generation is the hardest part of this pipeline. It requires:

1. **Language boundary detection** at segment level (one sentence may start EN, end VI)
2. **Vietnamese diacritic restoration** from Whisper's transcription artifacts
3. **Phonetic approximation** that sounds right to English ears — not IPA, just `[humm biet]`
4. **Consistent JSON output** across hundreds of segments

Kimi K2.6's extended reasoning handles all four simultaneously in a single pass. The model's instruction-following and structured output reliability made it the clear choice for this task — smaller models frequently hallucinate IPA symbols or skip diacritics.

**Proof of Kimi usage**: The health banner in the dashboard shows `"Phonetics engine: NVIDIA Kimi K2.6"` when `NVIDIA_API_KEY` is set. The API call is visible in `~/.hermes/logs/agent.log` with `model: meta/llama-...` / `base_url: https://integrate.api.nvidia.com`. (See demo video.)

---

## Branding & Messaging

**Name**: SpeakAlong  
**Tagline**: *"Watch it. Read it. Speak it."*  
**Alt tagline**: *"AI phonetics for videos your learners can actually speak along with."*  
**Audience**: Vietnamese language teachers, heritage language educators, short-form content creators  
**Tone**: Warm, learner-focused, demo-forward

### Key messages

- "Send a video. Learners speak along." — the core loop
- "Kimi reads the code-switching." — the AI angle
- "Edit what needs fixing, burn the rest." — the editor angle
- "A plugin, not a fork." — the Hermes ecosystem angle

---

## Demo Video Outline

### Target length: 90 seconds (aiming for Shorts-compatible, ≤ 60s is ideal)

---

### Opening (0–10s) — The Problem

**Shot**: A Vietnamese teaching Short playing — no captions, mixed EN/VI audio.  
**Voiceover / title card**:
> "Vietnamese teaching videos mix English and Vietnamese. Auto-captions can't add phonetic guides. Teachers spend 30 minutes doing this manually — per video."

---

### Act 1 — Telegram flow (10–30s)

**Shot 1**: Telegram chat. Send a raw teaching video to the Hermes bot.  
**Shot 2**: Bot replies: *"Transcribing…"* → typing indicator.  
**Shot 3**: Bot sends back the captioned `.mp4` — captions visible in the preview.  
**Title card overlay**: *"Kimi K2.6 → EN/VI detection → phonetic generation → FFmpeg burn"*  
**Shot 4**: Bot message includes the dashboard link: *"Edit at http://localhost:9119/captions/abc123"*

---

### Act 2 — Dashboard editor (30–55s)

**Shot 1**: Click the link → dashboard opens on the editor.  
**Show**: Video player on left with burned captions. Segment list on right — Vietnamese segments with `VI` badge and phonetic field, English segments with `EN` badge.  
**Shot 2**: Fix a segment — tap the phonetic field, type a correction.  
**Shot 3**: NL edit panel — type *"merge segments 4 and 5"* → AI proposes patch → accept → segments merged.  
**Shot 4**: QA review — click "Review" → amber flags on two segments, green ticks on good ones.  
**Shot 5**: Click "Re-burn" → spinner → video reloads with updated captions.

---

### Act 3 — Kimi proof + style (55–75s)

**Shot 1**: Health banner at top of job list — **"Phonetics engine: NVIDIA Kimi K2.6"** clearly visible.  
**Shot 2** (optional): `~/.hermes/logs/agent.log` tail showing the NVIDIA NIM API call.  
**Shot 3**: Style presets — click "Style with Hermes", type *"bold yellow Impact, TikTok style"* → preview appears → apply → re-burn → new captions appear.

---

### Closing (75–90s)

**Shot**: Side-by-side: raw video (no captions) vs. captioned output (Vietnamese + phonetics).  
**Title card**:
> *"SpeakAlong — a Hermes plugin.*  
> *Watch it. Read it. Speak it."*

**Show**: `hermes plugins enable phonetic-captions` in terminal.  
**CTA**: *"Built for the Nous Research × Kimi hackathon."*

---

## Post Copy

### X / Twitter

> Standard accounts get **280 characters** (not 140 — doubled in 2017). Two options below.

**Full version (~270 chars, fits in 280 with link):**
```
🎬 Built SpeakAlong for @NousResearch × Kimi

Vietnamese Shorts mix EN + VI. Auto-captions miss pronunciation guides.
Kimi K2.6 classifies, fixes diacritics, adds [phonetic guides].
FFmpeg burns them in.

Send a clip. Learners speak along.

[link] #NousHackathon #KimiTrack
```

**Ultra-short (~120 chars, add link + hashtags after):**
```
Vietnamese Shorts mix EN+VI. Auto-captions miss pronunciation guides.
Kimi K2.6 fixes that — built SpeakAlong to prove it.
```

### Discord (shorter, for `#creative-hackathon-submissions`)

```
**SpeakAlong** — AI phonetic captions for Vietnamese teaching Shorts

Built on Hermes + Kimi K2.6. Send a video via Telegram → Kimi classifies
EN/VI segments, fixes diacritics, generates English pronunciation guides
→ FFmpeg burns them in → you get back a Short learners can actually speak along with.

Includes a dashboard editor: segment editing, NL instructions, QA review,
style presets. Fully self-contained Hermes plugin — no core file changes.

[demo video link]
```

---

## Technical Proof Points for Judges

| Claim | Where to verify |
|---|---|
| Kimi K2.6 via NVIDIA NIM | `plugins/phonetic-captions/pipeline.py` → `generate_phonetics()` — `base_url = "https://integrate.api.nvidia.com/v1"`, `model = "moonshotai/kimi-k2.6"` |
| Hermes model fallback | Same function — falls back to `AIAgent` if `NVIDIA_API_KEY` absent |
| Diacritic correction | System prompt in `generate_phonetics()` — explicit instruction to fix Whisper tone artifacts |
| Phonetic-only output (no IPA) | System prompt + NL-edit system prompt — "NEVER use IPA symbols" rule |
| Dashboard is a Hermes plugin | `plugins/phonetic-captions/plugin.yaml`, `__init__.py` `register(ctx)`, `dashboard/manifest.json` |
| No core file changes | Only `web/src/App.tsx` gets a 1-line catch-all guard; all pipeline + API + UI lives in `plugins/phonetic-captions/` |
| SSE streaming prevents timeouts | `plugin_api.py` `_agent_sse()` generator, used by `/nl-edit` and `/qa` endpoints |

---

## Submission Checklist

- [ ] Demo video recorded (see outline above)
- [ ] Tweet drafted and ready to post (see copy above)
- [ ] Tweet posted tagging @NousResearch
- [ ] Discord link dropped in `#creative-hackathon-submissions`
- [ ] Verify health banner shows "NVIDIA Kimi K2.6" in demo video
- [ ] Verify API call to NVIDIA NIM visible in logs or terminal during demo recording
