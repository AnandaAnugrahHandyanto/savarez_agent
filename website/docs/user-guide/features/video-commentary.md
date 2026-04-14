---
title: Visual-first video commentary
sidebar_position: 6
---

# Visual-first video commentary

Hermes now includes an engineering-friendly Python pipeline for turning a slide deck recording, UI walkthrough, or product demo into a **基于视频画面的中文讲解版**.

This pipeline is intentionally **visual-first**, not a speech-to-speech translation layer. It looks at the video frames, detects presentation segments, asks an Azure OpenAI vision-capable deployment to summarize what changed on screen, and then uses Azure Speech to generate a Chinese narration track that fits each segment's time budget.

## What it produces

Given an input `.mp4`, the pipeline can generate:

- a dubbed commentary video
- a standalone mixed commentary audio track
- a Chinese `.srt` subtitle file
- a segment manifest JSON for review/regeneration workflows

## Entry point

```bash
python scripts/visual_commentary_pipeline.py \
  --input input.mp4 \
  --output out/commentary_zh.mp4 \
  --workdir out/work
```

## Required environment variables

### Azure OpenAI

```bash
export AZURE_OPENAI_ENDPOINT="https://<resource>.openai.azure.com"
export AZURE_OPENAI_API_KEY="..."
export AZURE_OPENAI_DEPLOYMENT="<vision-capable deployment>"
# optional
export AZURE_OPENAI_API_VERSION="2024-10-21"
```

### Azure Speech

```bash
export AZURE_SPEECH_KEY="..."
export AZURE_SPEECH_REGION="eastus"
# optional
export AZURE_SPEECH_VOICE="zh-CN-XiaoxiaoNeural"
```

## How timing control works

For slide-by-slide narration, the best results come from combining three layers:

1. **Segment-aware script generation** — the prompt asks the model to keep each narration short enough for the current segment.
2. **Azure Speech SSML rate/style control** — the pipeline emits SSML with `prosody rate` and `mstts:express-as` style.
3. **Azure `mstts:audioduration` targeting** — each TTS request can request a target duration for the segment before ffmpeg does any fallback tempo fitting.

The pipeline therefore follows this strategy:

- first shorten the text at generation time
- then ask Azure Speech to aim for the segment budget
- finally use ffmpeg `atempo` as a last-mile fit when the clip is still slightly too long

This produces far more natural results than trying to stretch an entire full-video narration after the fact.

## Useful flags

```bash
python scripts/visual_commentary_pipeline.py \
  --input demo.mp4 \
  --output out/demo_commentary.mp4 \
  --workdir out/demo_work \
  --scene-threshold 0.32 \
  --min-segment 3 \
  --max-segment 12 \
  --segment-buffer 0.35 \
  --base-rate "+0%" \
  --azure-style professional
```

### Flag meanings

- `--scene-threshold`: ffmpeg scene detection sensitivity
- `--min-segment`: merge tiny cuts into neighboring segments
- `--max-segment`: split overly long segments into smaller narration windows
- `--segment-buffer`: reserve a little silence inside each segment
- `--base-rate`: global SSML speaking-rate adjustment
- `--azure-style`: Azure Speech expressive speaking style such as `professional`, `calm`, or `cheerful`

## When this works best

This pipeline is best for:

- slide deck recordings
- Azure / portal walkthroughs
- product demos
- dashboards and analytics demos
- architecture explanation videos

It is less suitable for:

- dense multi-speaker conversational videos
- videos where the main information is only in source audio
- highly dynamic cinematic footage with no stable screen structure

## Engineering layout

The implementation is split into:

- `tools/video_commentary/core.py` — reusable timing / SRT / SSML helpers
- `tools/video_commentary/pipeline.py` — Azure + ffmpeg end-to-end pipeline
- `scripts/visual_commentary_pipeline.py` — runnable script entrypoint
- `tests/tools/test_video_commentary.py` — unit coverage for core helpers

## Dependencies and assumptions

The pipeline expects:

- `ffmpeg` and `ffprobe` available on `PATH`, or `imageio-ffmpeg` installed
- network access to Azure OpenAI and Azure Speech
- an Azure OpenAI deployment that supports image input

## Recommended workflow for productization

If you're using this for a real deck-production workflow, keep each segment as a reviewable unit with:

- segment start/end
- generated Chinese narration
- raw TTS clip duration
- fitted clip duration
- frame samples used for prompt grounding

That makes it easy to selectively regenerate only one slide after script edits, voice changes, or glossary fixes.
