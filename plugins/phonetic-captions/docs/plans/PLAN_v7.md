# Hermes Caption Plugin — Plan v7 (Distributability)

**Hackathon**: Hermes Agent Creative Hackathon  
**Previous plans**: v1–v6 executed (see PLAN_v1.md … PLAN_v6.md)

---

## Goal

Make `phonetic-captions` a proper drop-in Hermes plugin that a new user can
install and run without touching core repo files. Current blocker: the
pipeline code lives in `tools/video_caption.py` (core tree), so the plugin
is not self-contained and NVIDIA_API_KEY is listed as a hard prerequisite even
though it's optional.

---

## Changes

### Phase 1 — Self-contained structure

| Action | File |
|--------|------|
| CREATE | `plugins/phonetic-captions/plugin.yaml` |
| CREATE | `plugins/phonetic-captions/pipeline.py` (pipeline moved from `tools/video_caption.py`) |
| CREATE | `plugins/phonetic-captions/__init__.py` (`register(ctx)` wires tool into Hermes plugin system) |
| UPDATE | `plugins/phonetic-captions/dashboard/plugin_api.py` — import from `..pipeline` instead of `tools.video_caption` |
| DELETE | `tools/video_caption.py` |
| UPDATE | `toolsets.py` — remove `video-caption` entry (tool now registered via plugin) |

**plugin.yaml fields:**
```yaml
name: phonetic-captions
version: 1.0.0
description: "Bilingual EN/VI phonetic caption editor for teaching videos"
pip_dependencies:
  - faster-whisper
  - openai         # only needed if NVIDIA_API_KEY is set
provides_tools:
  - video-caption
```
No `requires_env` — NVIDIA_API_KEY is optional, not a gate.

**Ordering constraint:** `plugin_api.py` import update (Phase 1 Step 4) MUST be
applied before deleting `tools/video_caption.py` (Step 5). These two happen
atomically in the same implementation pass.

### Phase 2 — NVIDIA fallback to Hermes model

Modify `generate_phonetics()` in `pipeline.py`:

- **With `NVIDIA_API_KEY`**: use `moonshotai/kimi-k2.6` via NVIDIA NIM (best quality, current behaviour)
- **Without key**: call `_call_agent()` (same helper already used by `plugin_api.py` for NL-edit / QA)
  using the user's configured Hermes model

This removes NVIDIA_API_KEY as a user-facing prerequisite entirely. The `openai` pip package
remains listed in `pip_dependencies` for users who want the NVIDIA path.

### Phase 3 — Frontend health banner

**New endpoint** `GET /health` in `plugin_api.py`:
```json
{
  "ffmpeg": true,
  "faster_whisper": false,
  "phonetics_source": "nvidia" | "hermes" | "unavailable",
  "hermes_model": "claude-3-7-sonnet"
}
```

**New component** `PrerequisitesBanner` in `src/index.tsx`, rendered at top of `JobListView`:
- Fetches `/health` on mount
- **Error strip** (red/amber): missing `ffmpeg` or `faster_whisper` with exact install command
- **Info strip** (blue): phonetics source — *"Using NVIDIA Kimi K2.6"* or *"Using [model] (no NVIDIA key)"*
- Dismissible; non-blocking (app still navigable with missing deps)

---

## What does NOT change

- `plugins/phonetic-captions/dashboard/manifest.json` — unchanged
- `plugins/phonetic-captions/dashboard/src/index.tsx` — only adds `PrerequisitesBanner`
- Gateway video path injection (`gateway/run.py`) — unchanged
- Caption config in `hermes_cli/config.py` — unchanged
- Skills — unchanged

---

## Installation steps for new users (after this plan)

```bash
# 1. Copy plugin into Hermes plugins directory
cp -r plugins/phonetic-captions ~/.hermes/plugins/

# 2. Install Python dependencies
pip install faster-whisper openai

# 3. Install FFmpeg
brew install ffmpeg        # macOS
# sudo apt install ffmpeg  # Linux

# 4. (Optional) Set NVIDIA API key for best-quality phonetics
echo "NVIDIA_API_KEY=nvapi-..." >> ~/.hermes/.env
# Without this key, phonetics fall back to your configured Hermes model.

# 5. Enable the plugin
hermes plugins enable phonetic-captions

# 6. Enable the dashboard and open
hermes dashboard
# → Click the "Captions" tab
```
