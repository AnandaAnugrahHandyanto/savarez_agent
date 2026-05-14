# Hermes Migration Changes

Last updated: May 14, 2026, 2:50 PM EDT

## Runtime Changes

- Updated `/Users/admin/.hermes/plugins/cipher-workflows/__init__.py`.
  - Uses Hermes bridge wrappers under `/Users/admin/.hermes/scripts`.
  - Sets `CIPHER_OUTPUTS_DIR=/Users/admin/.hermes/outputs/cipher`.
  - Sets `CIPHER_STOCK_UPDATES_TRANSCRIBE_MODEL_ROOT=/Users/admin/.hermes/models`.
  - Sets `CIPHER_VIDEO_SUMMARY_TRANSCRIBE_MODEL_ROOT=/Users/admin/.hermes/models`.
  - Sets `CIPHER_STOCK_UPDATES_ACTIVE_RUN_DIR=/Users/admin/.hermes/state/stock-updates-command`.
  - Sets stock, video, and voice command script paths to
    `/Users/admin/.hermes/plugins/cipher-workflows/native`.
  - Sets `OPENCLAW_MLX_SKIP_ENSURE=1`.
  - Spawns bridge processes with cwd `/Users/admin/.hermes`.
  - Removed a stale unused `CLAW_ROOT` constant.

- Added and updated `/Users/admin/.hermes/scripts/hermes-command-bridge.mjs`.
  - Loads Hermes env files.
  - Forces `HOME=/Users/admin/.hermes`.
  - Forces generated cipher output under `/Users/admin/.hermes/outputs/cipher`.
  - Forces stock/video transcription model roots under `/Users/admin/.hermes/models`.
  - Imports Hermes-owned native command source from
    `/Users/admin/.hermes/plugins/cipher-workflows/native/plugins`.
  - Runs stock/video command scripts from
    `/Users/admin/.hermes/plugins/cipher-workflows/native/scripts`.

- Added and updated `/Users/admin/.hermes/scripts/hermes-voice-bridge.mjs`.
  - Loads Hermes env files.
  - Forces `HOME=/Users/admin/.hermes`.
  - Imports Hermes-owned native voice memo bridge source from
    `/Users/admin/.hermes/plugins/cipher-workflows/native/plugins/voice-memo-controls`.

- Added Hermes-owned native workflow source under
  `/Users/admin/.hermes/plugins/cipher-workflows/native`.
  - Copied migrated command plugins, shared Telegram helpers, stock/video runner
    scripts, voice-memo scripts, local-model registry helpers, and the
    `video-summarize` shared skill engine.
  - Left Claw originals intact as source-history copies.

- Replaced `/Users/admin/.hermes/scripts/mlx-openai-compat-server.py` with a
  Hermes-owned OpenAI-compatible MLX wrapper.
  - Serves Hermes model paths directly.
  - Supports non-streaming and streaming chat completions.
  - Emits OpenAI-style SSE chunks and `[DONE]` for streaming requests.

- Updated `/Users/admin/.hermes/.env`.
  - Added non-secret runtime exports for `CIPHER_OUTPUTS_DIR`,
    `CIPHER_VOICE_MEMO_CANARY_RUNS_DIR`, and `OPENCLAW_MLX_SKIP_ENSURE`.

- Updated `/Users/admin/Library/LaunchAgents/local.qwen-mlx-11435.plist`.
  - Program wrapper points to `/Users/admin/.hermes/scripts/mlx-openai-compat-server.py`.
  - Working directory is `/Users/admin/.hermes`.
  - stdout/stderr write under `/Users/admin/.hermes/logs`.
  - `--model` and `--model-id` point to
    `/Users/admin/.hermes/models/mlx_models/Qwen3.6-27B-OptiQ-4bit`.

- Updated `/Users/admin/.hermes/config.yaml`.
  - Added provider `mlx-studio`.
  - Added alias `mlx-qwen-optiq`.

- Updated `/Users/admin/.hermes/profiles/local-agent/config.yaml`.
  - Added non-default provider `mlx-studio`.
  - Added alias `mlx-qwen-optiq`.
  - Kept local-agent default model on Ollama.

- Updated `/Users/admin/claw/scripts/cipher/video-summary/video_summary_from_url.py`.
  - Added `--transcribe-model-root`.
  - Runs transcription with cwd set to the selected model root.
  - Defaults to `/Users/admin/.hermes/models` when run with
    `HOME=/Users/admin/.hermes`.

- Updated `/Users/admin/claw/scripts/cipher/stock-updates/stock-update-from-youtube.py`.
  - Defaults transcription cwd to `/Users/admin/.hermes/models` when run with
    `HOME=/Users/admin/.hermes`.

- Copied local model assets into Hermes:
  - `/Users/admin/.hermes/models/mlx_models/Qwen3.6-27B-OptiQ-4bit`
  - `/Users/admin/.hermes/models/mlx_models/distil-large-v3`

- Disabled Bonsai/OpenClaw MLX LaunchAgent.
  - Backed up to `/Users/admin/.hermes/migration/openclaw-disabled-launchagents-20260514-132807/local.bonsai-mlx.plist`.
  - Renamed active plist to
    `/Users/admin/Library/LaunchAgents/local.bonsai-mlx.plist.disabled-by-hermes-20260514-132807`.
  - Verified `local.bonsai-mlx` is not loaded and port `11437` is not listening.

- Created Hermes compatibility directories and symlinks.
  - `/Users/admin/.hermes/outputs/cipher`
  - `/Users/admin/.hermes/claw -> /Users/admin/claw`
  - `/Users/admin/.hermes/Library -> /Users/admin/Library`
  - `/Users/admin/.hermes/open-webui-env -> /Users/admin/open-webui-env`
  - `/Users/admin/.hermes/claw-cipher/outputs -> /Users/admin/.hermes/outputs/cipher`
  - `/Users/admin/.hermes/claw-cipher/.secrets -> /Users/admin/claw-cipher/.secrets`
  - `/Users/admin/.hermes/claw-cipher/.venvs -> /Users/admin/claw-cipher/.venvs`

- Restarted `local.qwen-mlx-11435` after LaunchAgent/wrapper/model changes.
- Restarted `ai.hermes.gateway` after bridge/plugin changes.

## Project Tracking Changes

- Added/updated `HERMES_MIGRATION_PLAN.md`.
- Added/updated `HERMES_MIGRATION_FINDINGS.md`.
- Added/updated `HERMES_MIGRATION_CHECKLIST.md`.
- Added/updated `HERMES_MIGRATION_CHANGES.md`.
- Added/updated `HERMES_MIGRATION_BLOCKERS.md`.
- Added/updated `HERMES_LOCAL_MODELS_MIGRATION_PLAN.md`.
- Added/updated `HERMES_LOCAL_MODELS_MIGRATION_CHECKLIST.md`.
- Updated `/Users/admin/.hermes/README.md`.

## Worktree Note

The Hermes checkout already had modified files before this migration pass:

- `gateway/platforms/telegram.py`
- `hermes_cli/plugins.py`
- `tests/gateway/test_telegram_approval_buttons.py`
- `tests/hermes_cli/test_plugins.py`

Those changes were preserved.
