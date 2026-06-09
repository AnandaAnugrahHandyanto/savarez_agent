---
name: ektro-mv
description: Turn one sentence into a finished music video with EKTRO-MV — it writes the song (lyrics + vocals), generates the video, optionally captions it, and renders a delivery-compliant MP4. Use when the user asks to "make an MV / music video / 神曲 / 一句话出片" from a short description.
version: 1.0.0
author: Hermes Agent (Nous Research)
license: MIT
metadata:
  hermes:
    tags: [Creative, Music-Video, Text-to-Video, Generative, Remotion]
    related_skills: [songwriting-and-ai-music]
    requires_toolsets: [ektro_mv]
---

# EKTRO-MV — one sentence → a music video

[EKTRO-MV](https://github.com/HorizonNowhere/EKTRO-MV) is an open-source TypeScript engine
that turns one sentence into a finished music video: an LLM writes the song and shotlist,
ACE-Step sings it, Seedance generates the visuals, Whisper aligns captions, and Remotion
renders the final MP4 (H.264 / yuv420p / AAC).

## Preferred: the `ektro_mv_create` tool

When the `ektro_mv` toolset is enabled (the `ektro-mv` CLI is resolvable), call the
**`ektro_mv_create`** tool:

- `prompt` (string): one sentence, e.g. `做一首赛博朋克 AI 觉醒神曲`.
- `brief` (optional): path to a CreativeBrief JSON — skips the LLM brain (no ANTHROPIC_API_KEY needed).
- `out` (optional): where to move the finished `.mp4`.
- `skip_subtitles` (optional, default true): the Whisper stage is opt-in.
- `timeout` (optional): seconds (default 900; raise for longer songs).

It returns JSON with `output_mp4` (path to the rendered video).

## Prerequisites (tell the user if missing)

- **Node.js 20+** and the EKTRO-MV CLI resolvable, via one of:
  - `npm install -g ektro-mv`, **or**
  - `EKTRO_MV_DIR=/path/to/EKTRO-MV` (a cloned + built repo), **or**
  - `EKTRO_MV_BIN=/path/to/EKTRO-MV/packages/cli/dist/bin.js`
- **`ARK_API_KEY`** — Volcengine Ark key for Seedance video.
- **`ANTHROPIC_API_KEY`** — only for `prompt` mode (the creative brain); not needed with `brief`.
- **ComfyUI running with ACE-Step** (local, GPU) for the vocal song.
- `ffmpeg` / `ffprobe` on PATH.
- Generation takes several minutes; the music stage needs a GPU.

## CLI fallback (via the terminal toolset)

If the tool isn't wired, drive the CLI directly:

```bash
ektro-mv "做一首赛博朋克 AI 觉醒神曲" --out mv.mp4 --skip-subtitles
# or from a cloned repo:
node /path/to/EKTRO-MV/packages/cli/dist/bin.js "make a cyberpunk anthem" --out mv.mp4 --skip-subtitles
```

## MCP alternative

EKTRO-MV also ships an MCP server exposing `ektro_mv_create`. Register it once:

```bash
hermes mcp add ektro-mv --command "node /path/to/EKTRO-MV/mcp/ektro-mv-mcp/dist/bin.js"
```

## Notes

- Output targets H.264 / yuv420p / AAC for broad platform compatibility.
- For a keyless, deterministic run, hand-write or generate a CreativeBrief JSON and pass `brief`.
- This skill drives the open-source EKTRO-MV engine; it creates no proprietary content itself.
