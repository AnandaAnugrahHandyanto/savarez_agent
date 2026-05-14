# Hermes Local Models Migration Checklist

Last updated: May 14, 2026, 2:23 PM EDT

## Summary

The active Hermes local-model migration is complete. Hermes now owns the direct
MLX Qwen model asset, the `distil-large-v3` transcription model asset, the MLX
serving wrapper, the direct MLX provider registration, and the migrated
stock/video transcription model root.

Approval-only cleanup remains for disabled or duplicate model copies. No model
source directories were deleted.

## Preflight

- [x] Ran from `/Users/admin/.hermes/hermes-agent`.
- [x] Verified `hermes status` reports the gateway running.
- [x] Verified `hermes profile list` reports `default`, `local-agent`, and
  `luna` running.
- [x] Verified `/Users/admin/.hermes/profiles` exists and was preserved.
- [x] Recorded live LaunchAgents and processes for Hermes, Ollama, Qwen MLX,
  Open WebUI, and disabled Bonsai/OpenClaw state.
- [x] Recorded endpoint evidence for:
  - [x] `http://127.0.0.1:11434/v1/models`
  - [x] `http://127.0.0.1:11435/v1/models`
  - [x] `http://admins-Mac-mini.local:11434/v1/models`

## Hermes Model Root

- [x] Created and used `/Users/admin/.hermes/models`.
- [x] Created and used `/Users/admin/.hermes/models/mlx_models`.
- [x] Created `/Users/admin/.hermes/models/gguf`.
- [x] Created `/Users/admin/.hermes/models/ollama`.
- [x] Created `/Users/admin/.hermes/models/archive-candidates`.
- [x] Confirmed no profile folders were moved, deleted, recreated, or
  overwritten.

## Active MLX Qwen Migration

- [x] Copied Qwen MLX OptiQ from:
  `/Users/admin/claw/models/mlx_models/Qwen3.6-27B-OptiQ-4bit`
  to:
  `/Users/admin/.hermes/models/mlx_models/Qwen3.6-27B-OptiQ-4bit`.
- [x] Verified source and destination size parity: `15G`.
- [x] Verified destination file count: `28`.
- [x] Verified representative SHA-256 checksums for `config.json`,
  `tokenizer.json`, and the safetensors index.
- [x] Verified checksum dry-run transferred `0` files across
  `16492963859` bytes.
- [x] Updated `~/Library/LaunchAgents/local.qwen-mlx-11435.plist` so both
  `--model` and `--model-id` point at the Hermes model path.
- [x] Restarted only `local.qwen-mlx-11435`.
- [x] Verified `curl -s http://127.0.0.1:11435/v1/models` returns the Hermes
  path model id.
- [x] Verified a direct non-streaming chat completion against
  `127.0.0.1:11435`.
- [x] Verified a direct streaming chat completion against
  `127.0.0.1:11435`.
- [x] Confirmed Qwen logs write under `/Users/admin/.hermes/logs`.
- [x] Confirmed the active Qwen process no longer references
  `/Users/admin/claw/models`.

## Hermes Registration

- [x] Added `mlx-studio` provider to `/Users/admin/.hermes/config.yaml`.
- [x] Added friendly alias `mlx-qwen-optiq` to `/Users/admin/.hermes/config.yaml`.
- [x] Added the non-default `mlx-studio` provider and `mlx-qwen-optiq` alias to
  `/Users/admin/.hermes/profiles/local-agent/config.yaml`.
- [x] Kept `local-agent` default model on Ollama
  `qwen3.6:35b-a3b-q4_K_M`; the direct MLX model is available by explicit
  provider or alias.
- [x] Did not modify `luna` for direct MLX because no Luna direct-MLX need was
  established.
- [x] Verified YAML parsing for root and `local-agent` configs.
- [x] Verified Hermes accepts the explicit provider/model:
  `hermes chat --ignore-rules -Q -q 'Reply with exactly: ok' --provider mlx-studio -m /Users/admin/.hermes/models/mlx_models/Qwen3.6-27B-OptiQ-4bit`.
- [x] Verified Hermes accepts the alias:
  `hermes --ignore-rules -z 'Reply with exactly: ok' -m mlx-qwen-optiq`.

## Whisper Transcription Model Migration

- [x] Copied `distil-large-v3` from:
  `/Users/admin/claw/models/mlx_models/distil-large-v3`
  to:
  `/Users/admin/.hermes/models/mlx_models/distil-large-v3`.
- [x] Verified source and destination size parity: `1.4G`.
- [x] Verified destination file count: `2`.
- [x] Verified representative SHA-256 checksum for `config.json`.
- [x] Verified checksum dry-run transferred `0` files across `1509130380`
  bytes.
- [x] Set stock-update transcription root to:
  `CIPHER_STOCK_UPDATES_TRANSCRIBE_MODEL_ROOT=/Users/admin/.hermes/models`.
- [x] Set video-summary transcription root to:
  `CIPHER_VIDEO_SUMMARY_TRANSCRIBE_MODEL_ROOT=/Users/admin/.hermes/models`.
- [x] Hardened stock and video script defaults so `HOME=/Users/admin/.hermes`
  resolves the transcription model root to `/Users/admin/.hermes/models`
  instead of a Claw fallback.
- [x] Verified stock/video transcription constants resolve to
  `/Users/admin/.hermes/models` in the Hermes bridge environment.
- [x] Ran a local `distil-large-v3` transcription smoke from cwd
  `/Users/admin/.hermes/models`.
- [x] Confirmed smoke artifacts land under
  `/Users/admin/.hermes/outputs/verification`.

## Bonsai And Duplicate Cleanup

- [x] Kept `local.bonsai-mlx` disabled.
- [x] Verified port `11437` is not listening.
- [x] Classified `/Users/admin/claw/models/mlx_models/Bonsai-8B-mlx-1bit` as
  disabled canary/archive candidate.
- [x] Classified `/Users/admin/models/bonsai-original/Bonsai-8B.gguf` as
  Bonsai archive/provenance candidate.
- [x] Classified `/Users/admin/models/gguf/Qwen3.6-27B-GGUF` as a Qwen GGUF
  source/import duplicate candidate, not an active Hermes runtime dependency.
- [x] Deleted no model assets.

## Optional Ollama Store Migration

- [x] Left active Ollama blob store at `/Users/admin/.ollama/models`.
- [x] Classified Ollama store migration as a separate optional service-window
  task because it is 59G and already registered through Hermes providers.

## Final Audit

- [x] Ran path audits for Claw/OpenClaw/model references across Hermes configs,
  scripts, plugins, LaunchAgents, and related Claw command sources.
- [x] Classified remaining Claw/OpenClaw model references in
  `HERMES_MIGRATION_FINDINGS.md`.
- [x] Updated `HERMES_MIGRATION_CHECKLIST.md` with model migration evidence.
- [x] Updated `HERMES_LOCAL_MODELS_MIGRATION_PLAN.md` with final execution
  evidence.
- [x] Updated `/Users/admin/.hermes/README.md` with final model layout.
- [x] Verified Hermes gateway health after restarting the gateway.
- [x] Verified no generated verification outputs were written into
  `/Users/admin/claw*`.
