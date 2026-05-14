# Hermes Migration Checklist

Last updated: May 14, 2026, 2:23 PM EDT

## Completion Status

- [x] Ran live-state probes from `/Users/admin/.hermes/hermes-agent`.
- [x] Preserved `/Users/admin/.hermes/profiles` as Hermes-owned runtime state.
- [x] Verified Hermes default gateway is running through `ai.hermes.gateway`.
- [x] Verified `hermes status` reports the gateway running.
- [x] Verified Telegram reconnects from Hermes after gateway restart.
- [x] Verified active Hermes cron jobs write output under
  `/Users/admin/.hermes/cron/output`.
- [x] Redirected migrated cipher outputs to `/Users/admin/.hermes/outputs/cipher`.
- [x] Redirected migrated stock transcript output to
  `/Users/admin/.hermes/outputs/cipher/stock-update-transcripts`.
- [x] Redirected migrated video and voice-memo recordings through
  `/Users/admin/.hermes/claw-cipher/outputs/recordings`, backed by
  `/Users/admin/.hermes/outputs/cipher`.
- [x] Redirected migrated Telegram bridge logs to
  `/Users/admin/.hermes/logs/cipher-workflows`.
- [x] Redirected Qwen MLX runtime wrapper, cwd, logs, model path, and model id
  to Hermes-owned paths.
- [x] Created Hermes local model root at `/Users/admin/.hermes/models`.
- [x] Migrated active Qwen MLX model asset from `/Users/admin/claw/models` to
  `/Users/admin/.hermes/models`.
- [x] Migrated `distil-large-v3` transcription fallback from
  `/Users/admin/claw/models` to `/Users/admin/.hermes/models`.
- [x] Registered the direct MLX service in Hermes as provider `mlx-studio` and
  alias `mlx-qwen-optiq`.
- [x] Disabled stale Bonsai/OpenClaw MLX service and verified port `11437` is
  not listening.
- [x] Verified OpenClaw gateway is not loaded and port `18789` is not listening.
- [x] Listed remaining Claw/OpenClaw dependencies with exact classifications.
- [x] Verified no migrated workflow uses Claw/OpenClaw as a fallback output sink.
- [x] Recorded findings, changes, blockers, plan, local-model checklist, and
  local-model execution evidence in the Hermes project checkout.

## Verification Evidence

| Check | Result |
| --- | --- |
| `pwd` | `/Users/admin/.hermes/hermes-agent` |
| `git status --short` | Pre-existing modifications in `gateway/platforms/telegram.py`, `hermes_cli/plugins.py`, `tests/gateway/test_telegram_approval_buttons.py`, and `tests/hermes_cli/test_plugins.py`; migration docs are untracked tracking files. |
| `hermes status` | Gateway running, Telegram configured, 3 active cron jobs, 5 active sessions. |
| `launchctl print gui/$(id -u)/ai.hermes.gateway` | Running from cwd `/Users/admin/.hermes/hermes-agent` with logs under `/Users/admin/.hermes/logs`. |
| `find /Users/admin/.hermes -maxdepth 3 -type d -name profiles -print` | `/Users/admin/.hermes/profiles` |
| `hermes profile list` | `default`, `local-agent`, and `luna` all running. |
| `curl http://127.0.0.1:11434/v1/models` | Studio Ollama lists `gemma4:31b`, `qwen3.6:27b-q5_K_M`, and `qwen3.6:35b-a3b-q4_K_M`. |
| `curl http://127.0.0.1:11435/v1/models` | Direct MLX service returns `/Users/admin/.hermes/models/mlx_models/Qwen3.6-27B-OptiQ-4bit`. |
| `curl http://admins-Mac-mini.local:11434/v1/models` | Mac mini Ollama lists `qwen3:8b` and `qwen3:4b-instruct`. |
| Qwen MLX `rsync` parity | Source and destination both `15G`; checksum dry-run transferred `0` files across `16492963859` bytes. |
| `distil-large-v3` `rsync` parity | Source and destination both `1.4G`; checksum dry-run transferred `0` files across `1509130380` bytes. |
| `python3 -m py_compile` for stock/video scripts | Pass |
| `python3 -m unittest discover -s /Users/admin/claw/scripts/cipher/video-summary -p 'test_video_summary_from_url.py' -v` | 6 tests passed. |
| `python3 -m unittest discover -s /Users/admin/claw/scripts/cipher/stock-updates -p 'test_stock_update_from_youtube.py' -v` | 17 tests passed. |
| `node --check /Users/admin/.hermes/scripts/hermes-command-bridge.mjs` | Pass |
| `python3 -m py_compile /Users/admin/.hermes/scripts/mlx-openai-compat-server.py` | Pass |
| Direct MLX non-streaming chat completion | Returned `ok`. |
| Direct MLX streaming chat completion | Returned OpenAI-style SSE chunks and `[DONE]`. |
| Hermes explicit provider smoke | `hermes chat ... --provider mlx-studio -m /Users/admin/.hermes/models/mlx_models/Qwen3.6-27B-OptiQ-4bit` returned `ok`. |
| Hermes alias smoke | `hermes --ignore-rules -z 'Reply with exactly: ok' -m mlx-qwen-optiq` returned `ok`. |
| Transcription smoke | `LightningWhisperMLX('distil-large-v3', ...)` ran from cwd `/Users/admin/.hermes/models` and wrote `/Users/admin/.hermes/outputs/verification/distil-large-v3-smoke-final.json`. |
| `launchctl print gui/$(id -u)/local.bonsai-mlx` | Not found. |
| `launchctl print gui/$(id -u)/ai.openclaw.gateway` | Not found. |
| `lsof -nP -iTCP:18789 -sTCP:LISTEN` | No listener. |
| `lsof -nP -iTCP:11437 -sTCP:LISTEN` | No listener. |

## Final Classification

- Migrated to Hermes: gateway runtime, profiles, cron outputs, Telegram command
  bridge, stock/video/voice output roots, Qwen MLX wrapper/log/cwd/model path,
  direct MLX provider/alias, transcription model root, and native copies of
  migrated command/plugin/script source under
  `/Users/admin/.hermes/plugins/cipher-workflows/native`.
- Preserved as source or credentials: original Claw command/script source copies,
  Claw-Cipher SnapTrade secrets/venv, active AutoResearch dashboard.
- Preserved as source model copies pending approval: original Claw Qwen MLX and
  `distil-large-v3` directories.
- Stale/disabled: OpenClaw gateway/watchdogs and Bonsai MLX LaunchAgent.
- Optional future work: Ollama blob-store migration to
  `/Users/admin/.hermes/models/ollama` and model duplicate/archive cleanup.
