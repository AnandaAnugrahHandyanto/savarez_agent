---
name: acestep
description: Set up and use ACE-Step 1.5 for AI music generation. Handles installation, API server startup, and registration of ACE-Step's bundled skills (songwriting, generation, lyrics transcription, MV rendering, thumbnail creation). Use when users mention generating music, creating songs, AI music, ACE-Step, or want an open-source Suno alternative.
version: 1.0.0
metadata:
  hermes:
    tags: [music, audio, generation, ai, acestep, ace-step, lyrics, songs, suno-alternative]
    related_skills: [heartmula, audiocraft, songwriting-and-ai-music]
---

# ACE-Step 1.5 — Open-Source Music Generation

ACE-Step 1.5 is a state-of-the-art open-source music foundation model (MIT license) by StepFun. It generates commercial-grade music from lyrics and style tags, with support for cover generation, repainting, vocal-to-BGM, LoRA fine-tuning, and 50+ languages.

- **Repo**: https://github.com/ACE-Step/ACE-Step-1.5
- **Online Demo**: https://acemusic.ai
- **Models**: https://huggingface.co/ACE-Step

## Decision Flow

**Step 1 — Check if ACE-Step is already installed:**

```bash
ls ~/ACE-Step-1.5/.claude/skills/acestep/SKILL.md 2>/dev/null && echo "INSTALLED" || echo "NOT INSTALLED"
```

- If **INSTALLED** → skip to **Using ACE-Step** below.
- If **NOT INSTALLED** → proceed to **Installation**.

## Installation

### Prerequisites

- Python 3.11–3.12
- `uv` package manager
- GPU recommended (NVIDIA CUDA, Apple MPS, AMD ROCm, or Intel XPU). CPU works but is slow.

| GPU VRAM | Recommended Model | Notes |
|----------|-------------------|-------|
| 6–8 GB | 2B turbo | Lightweight, fast |
| 8–16 GB | 2B turbo/sft | Good balance |
| 16–24 GB | XL turbo/sft | Best quality (may need CPU offload below 20 GB) |
| 24 GB+ | XL sft + 4B LM | Maximum quality |

### Steps

```bash
# 1. Install uv if not present
command -v uv || curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone and install
cd ~/
git clone https://github.com/ACE-Step/ACE-Step-1.5.git
cd ACE-Step-1.5
uv sync

# 3. Start the API server (models auto-download on first run)
uv run acestep-api          # REST API at http://localhost:8001
# or: uv run acestep        # Gradio Web UI at http://localhost:7860
```

### Register ACE-Step's bundled skills

ACE-Step ships with a comprehensive skill suite in `.claude/skills/`. To make them available in Hermes, add the path to `~/.hermes/config.yaml`:

```yaml
skills:
  external_dirs:
    - ~/ACE-Step-1.5/.claude/skills
```

Then restart the gateway:

```bash
hermes gateway restart
```

This registers the following skills that are maintained upstream by ACE-Step:

| Skill | Purpose |
|-------|---------|
| `acestep` | Core music generation — text-to-music, cover, repainting via API |
| `acestep-songwriting` | Songwriting guide — captions, lyrics, BPM/key/duration |
| `acestep-lyrics-transcription` | Transcribe audio → timestamped lyrics (LRC/SRT) |
| `acestep-simplemv` | Render music videos with waveform and synced lyrics |
| `acestep-thumbnail` | Generate album art / MV backgrounds via Gemini API |
| `acestep-docs` | Documentation, GPU setup, troubleshooting |

**Note**: Once registered, these upstream skills take precedence for music generation tasks. They include scripts, API wrappers, and detailed guides that this skill does not duplicate. Keeping them as external_dirs means `git pull` in the ACE-Step repo automatically updates the skills.

## Using ACE-Step

Once installed and the bundled skills are registered, use the upstream `/acestep` skill directly for all music generation tasks. That skill provides:

- `scripts/acestep.sh` — CLI wrapper for all API operations (generate, cover, repaint, status, config)
- Caption mode (lyrics + style tags) for vocal songs
- Simple/random mode for quick exploration
- Cloud API (`https://api.acemusic.ai`) and local API support
- Full MV production pipeline via companion skills

### Quick example (after upstream skills are registered):

```bash
# Check API health
cd ~/ACE-Step-1.5/.claude/skills/acestep/ && ./scripts/acestep.sh health

# Generate a song
./scripts/acestep.sh generate -c "pop, female vocal, piano" -l "[Verse] Your lyrics here..." --duration 120
```

Refer to the upstream `/acestep` skill for complete usage instructions, API configuration, and output format details.

## Updating

```bash
cd ~/ACE-Step-1.5
git pull
uv sync
```

Skills update automatically since Hermes reads them from the live repo directory.

## Links

- GitHub: https://github.com/ACE-Step/ACE-Step-1.5
- Models: https://huggingface.co/ACE-Step/Ace-Step1.5
- Project Page: https://ace-step.github.io/ace-step-v1.5.github.io/
- Technical Report: https://arxiv.org/abs/2602.00744
- Online Demo: https://acemusic.ai
- Discord: https://discord.gg/PeWDxrkdj7
