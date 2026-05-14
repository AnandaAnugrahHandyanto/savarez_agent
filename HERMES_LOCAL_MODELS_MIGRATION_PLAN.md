# Hermes Local Models Migration Plan

Last updated: May 14, 2026, 2:23 PM EDT

## Goal

Make Hermes the clear owner of every local model it needs to register and use,
without leaving active model-serving, transcription, or command paths dependent
on Claw/OpenClaw model folders.

Canonical Hermes model root:

```text
/Users/admin/.hermes/models
```

## Final Answer

The active local-model migration is complete. Hermes owns the direct MLX Qwen
asset and served model id, the `distil-large-v3` transcription model asset, and
the provider/alias used to access the direct MLX service. The old model paths
were preserved as source copies and archive candidates; they are no longer active
runtime paths for the migrated Hermes workflows.

## Live Inventory

### Registered In Hermes

| Source | Endpoint | Hermes status | Models |
| --- | --- | --- | --- |
| Studio Ollama | `http://127.0.0.1:11434/v1` | Registered in Hermes config and active profiles. | `qwen3.6:35b-a3b-q4_K_M`, `qwen3.6:27b-q5_K_M`, `gemma4:31b` |
| Mac mini Ollama | `http://admins-Mac-mini.local:11434/v1` | Registered in Hermes config and active profiles. | `qwen3:4b-instruct`, `qwen3:8b` |
| Hermes direct MLX | `http://127.0.0.1:11435/v1` | Registered as provider `mlx-studio` and alias `mlx-qwen-optiq`. | `/Users/admin/.hermes/models/mlx_models/Qwen3.6-27B-OptiQ-4bit` |

### Migrated Assets

| Asset | Hermes path | Size | Status |
| --- | --- | ---: | --- |
| Qwen MLX OptiQ | `/Users/admin/.hermes/models/mlx_models/Qwen3.6-27B-OptiQ-4bit` | 15G | Served by `local.qwen-mlx-11435`; `/v1/models` returns this Hermes path. |
| Whisper MLX fallback | `/Users/admin/.hermes/models/mlx_models/distil-large-v3` | 1.4G | Used by stock/video transcription through Hermes model-root env and Hermes-home defaults. |

### Preserved Or Optional

| Asset | Path | Status |
| --- | --- | --- |
| Original Qwen MLX source copy | `/Users/admin/claw/models/mlx_models/Qwen3.6-27B-OptiQ-4bit` | Preserved; no active Qwen process references it after migration. |
| Original `distil-large-v3` source copy | `/Users/admin/claw/models/mlx_models/distil-large-v3` | Preserved; migrated stock/video flow resolves the Hermes copy. |
| Bonsai MLX canary | `/Users/admin/claw/models/mlx_models/Bonsai-8B-mlx-1bit` | Disabled canary/archive candidate; port `11437` is not listening. |
| Qwen GGUF source copy | `/Users/admin/models/gguf/Qwen3.6-27B-GGUF/Qwen3.6-27B-Q5_K_M.gguf` | Source/import duplicate candidate; not active Hermes runtime. |
| Bonsai GGUF source copy | `/Users/admin/models/bonsai-original/Bonsai-8B.gguf` | Bonsai provenance/archive candidate. |
| Ollama blob store | `/Users/admin/.ollama/models` | Still active Ollama store; optional later service-window migration only. |
| qmd embedding cache | `/Users/admin/.cache/qmd/models` | Cache/embedding state, not a Hermes chat model. |

## Target Layout

```text
/Users/admin/.hermes/models/
|-- mlx_models/
|   |-- Qwen3.6-27B-OptiQ-4bit/
|   `-- distil-large-v3/
|-- gguf/
|-- ollama/
`-- archive-candidates/
```

## Execution Record

### Phase 0: Freeze Evidence

- Recorded `hermes status`, `hermes profile list`, LaunchAgent state, process
  state, and model endpoints.
- Confirmed `/Users/admin/.hermes/profiles` exists and was not modified.
- Recorded source sizes for Qwen MLX, `distil-large-v3`, Bonsai MLX, GGUF
  source copies, Ollama blobs, qmd cache, and LM Studio.

### Phase 1: Move The Active MLX Qwen Model

- Copied Qwen MLX with Apple-compatible `rsync -a --progress --stats`.
- Verified file count, `du -sh` parity, representative checksums, and checksum
  dry-run parity.
- Updated `~/Library/LaunchAgents/local.qwen-mlx-11435.plist` so `--model` and
  `--model-id` use
  `/Users/admin/.hermes/models/mlx_models/Qwen3.6-27B-OptiQ-4bit`.
- Restarted only `local.qwen-mlx-11435`.
- Verified `/v1/models`, non-streaming chat completion, and streaming SSE chat
  completion.

### Phase 2: Register The Direct MLX Service In Hermes

- Added `mlx-studio` provider and `mlx-qwen-optiq` alias to
  `/Users/admin/.hermes/config.yaml`.
- Added the same provider/alias to
  `/Users/admin/.hermes/profiles/local-agent/config.yaml` without changing the
  local-agent default Ollama model.
- Left `luna` unchanged because no Luna direct-MLX requirement was established.
- Verified YAML parsing and two Hermes smokes:
  explicit provider/model and alias-only.

### Phase 3: Move The Whisper Transcription Fallback

- Copied `distil-large-v3` with `rsync -a --progress --stats`.
- Verified `du -sh` parity, representative checksum, and checksum dry-run
  parity.
- Set these bridge/plugin env values:

```text
CIPHER_STOCK_UPDATES_TRANSCRIBE_MODEL_ROOT=/Users/admin/.hermes/models
CIPHER_VIDEO_SUMMARY_TRANSCRIBE_MODEL_ROOT=/Users/admin/.hermes/models
```

- Hardened the stock/video script defaults so `HOME=/Users/admin/.hermes`
  resolves transcription cwd to `/Users/admin/.hermes/models`.
- Ran the minimal local transcription smoke. It loaded `distil-large-v3` from
  cwd `/Users/admin/.hermes/models` and wrote artifacts under
  `/Users/admin/.hermes/outputs/verification`.

### Phase 4: Decide Bonsai And GGUF Copies

- Kept Bonsai disabled.
- Wrote classification for Bonsai MLX, Bonsai GGUF, and Qwen GGUF source copies.
- Deleted nothing.

### Phase 5: Optional Ollama Store Migration

Skipped. The active Ollama store is not Claw-owned and its models are already
usable through Hermes providers. Moving 59G of Ollama blobs should be a separate
service-window task if full Hermes filesystem ownership is required.

## Verification Commands

```bash
hermes status
hermes profile list
curl -s http://127.0.0.1:11434/v1/models
curl -s http://127.0.0.1:11435/v1/models
curl -s http://admins-Mac-mini.local:11434/v1/models
hermes chat --ignore-rules -Q -q 'Reply with exactly: ok' --provider mlx-studio -m /Users/admin/.hermes/models/mlx_models/Qwen3.6-27B-OptiQ-4bit
hermes --ignore-rules -z 'Reply with exactly: ok' -m mlx-qwen-optiq
python3 -m unittest discover -s /Users/admin/claw/scripts/cipher/video-summary -p 'test_video_summary_from_url.py' -v
python3 -m unittest discover -s /Users/admin/claw/scripts/cipher/stock-updates -p 'test_stock_update_from_youtube.py' -v
```

## Done Criteria

- [x] The active direct MLX service reads from `/Users/admin/.hermes/models`.
- [x] Hermes has a registered provider/alias for the direct MLX service.
- [x] Stock/video transcription fallbacks resolve model roots under
  `/Users/admin/.hermes/models`.
- [x] Ollama and Mac mini models remain listed and usable through Hermes.
- [x] Every remaining Claw/OpenClaw model path is classified as legacy source,
  duplicate archive candidate, disabled canary, or intentionally preserved.
- [x] No model-serving service writes logs, pid files, generated artifacts, or
  runtime state into `/Users/admin/claw*`.
