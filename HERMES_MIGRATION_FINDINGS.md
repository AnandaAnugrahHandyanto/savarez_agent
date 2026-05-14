# Hermes Migration Findings

Last updated: May 14, 2026, 2:23 PM EDT

## Live Hermes State

- Project checkout: `/Users/admin/.hermes/hermes-agent`
- Runtime home: `/Users/admin/.hermes`
- Profiles root: `/Users/admin/.hermes/profiles`
- Main gateway: `ai.hermes.gateway`, running from
  `/Users/admin/.hermes/hermes-agent` with logs under `/Users/admin/.hermes/logs`
- Qwen MLX service: `local.qwen-mlx-11435`, running from Hermes wrapper/cwd/logs
  and serving the Hermes model path
- Active Hermes profiles: `default`, `local-agent`, `luna`
- Active Hermes local model root: `/Users/admin/.hermes/models`

## Hermes Runtime Inventory

- Profiles: `/Users/admin/.hermes/profiles`
- Default runtime logs: `/Users/admin/.hermes/logs`
- Default runtime sessions/state: `/Users/admin/.hermes/sessions`,
  `/Users/admin/.hermes/state.db`
- Cron config/output: `/Users/admin/.hermes/cron/jobs.json`,
  `/Users/admin/.hermes/cron/output`
- Migrated cipher output root: `/Users/admin/.hermes/outputs/cipher`
- Hermes local model root: `/Users/admin/.hermes/models`
- Hermes bridge wrappers:
  - `/Users/admin/.hermes/scripts/hermes-command-bridge.mjs`
  - `/Users/admin/.hermes/scripts/hermes-voice-bridge.mjs`
  - `/Users/admin/.hermes/scripts/mlx-openai-compat-server.py`
- Compatibility aliases:
  - `/Users/admin/.hermes/claw -> /Users/admin/claw` for preserved legacy source imports.
  - `/Users/admin/.hermes/claw-cipher/outputs -> /Users/admin/.hermes/outputs/cipher` for migrated artifact writes.
  - `/Users/admin/.hermes/claw-cipher/.secrets -> /Users/admin/claw-cipher/.secrets` for preserved SnapTrade secrets.
  - `/Users/admin/.hermes/claw-cipher/.venvs -> /Users/admin/claw-cipher/.venvs` for preserved SnapTrade venv.

## Migrated Command Classification

| Surface | Classification | Evidence |
| --- | --- | --- |
| `/stockupdates` | Migrated to Hermes runtime/output/model root | Hermes bridge sets `CIPHER_OUTPUTS_DIR=/Users/admin/.hermes/outputs/cipher` and `CIPHER_STOCK_UPDATES_TRANSCRIBE_MODEL_ROOT=/Users/admin/.hermes/models`; stock script fallback also prefers `/Users/admin/.hermes/models` when `HOME=/Users/admin/.hermes`. |
| `/videosummary`, `/videosummarize` | Migrated to Hermes runtime/output/model root | Hermes bridge sets `HOME=/Users/admin/.hermes` and `CIPHER_VIDEO_SUMMARY_TRANSCRIBE_MODEL_ROOT=/Users/admin/.hermes/models`; video script fallback also prefers `/Users/admin/.hermes/models` when `HOME=/Users/admin/.hermes`. |
| `/voicememo` | Migrated to Hermes runtime/output | Hermes voice bridge sets `HOME=/Users/admin/.hermes`; state path probe resolves under `/Users/admin/.hermes/claw-cipher/outputs/recordings/.state/vm-recording`. |
| `/activitymonitor` | Migrated to Hermes Telegram bridge | Dry bridge dispatch loads from Hermes wrapper and returns JSON `ok: true` for a nonmatching command without writing Claw output. |
| `/birdclaw` | Migrated to Hermes Telegram bridge | Dry bridge dispatch loads from Hermes wrapper and returns JSON `ok: true` for a nonmatching command without writing Claw output. |
| Hermes cron delivery | Hermes-owned | Active jobs are delivered by Hermes with outputs under `/Users/admin/.hermes/cron/output`. |
| Qwen MLX runtime | Migrated to Hermes runtime/model path | LaunchAgent runs `/Users/admin/.hermes/scripts/mlx-openai-compat-server.py`, cwd `/Users/admin/.hermes`, logs `/Users/admin/.hermes/logs/qwen-mlx-11435.*`, model path `/Users/admin/.hermes/models/mlx_models/Qwen3.6-27B-OptiQ-4bit`. |

## Local Model Inventory

| Source | Classification | Evidence |
| --- | --- | --- |
| Studio Ollama at `127.0.0.1:11434` | Already registered in Hermes | Endpoint lists `gemma4:31b`, `qwen3.6:27b-q5_K_M`, and `qwen3.6:35b-a3b-q4_K_M`. |
| Mac mini Ollama at `admins-Mac-mini.local:11434` | Already registered in Hermes | Endpoint lists `qwen3:8b` and `qwen3:4b-instruct`. |
| Direct MLX Qwen at `127.0.0.1:11435` | Migrated and registered | Endpoint reports `/Users/admin/.hermes/models/mlx_models/Qwen3.6-27B-OptiQ-4bit`; Hermes provider `mlx-studio` and alias `mlx-qwen-optiq` both return `ok` in smoke tests. |
| `distil-large-v3` Whisper fallback | Migrated | Copied to `/Users/admin/.hermes/models/mlx_models/distil-large-v3`; transcription smoke ran from cwd `/Users/admin/.hermes/models`. |
| LM Studio | No migration needed now | `/Users/admin/.lmstudio/models` is empty and `127.0.0.1:1234` is not listening. |
| Ollama blob store | Optional future migration | Active store remains `/Users/admin/.ollama/models`; not Claw-owned, already served through Hermes providers. |

## Remaining Claw/OpenClaw Path Inventory

| Item | Classification | Notes |
| --- | --- | --- |
| `/Users/admin/claw/models/mlx_models/Qwen3.6-27B-OptiQ-4bit` | Preserved source copy | Qwen service now serves the Hermes copy; no deletion performed. |
| `/Users/admin/claw/models/mlx_models/distil-large-v3` | Preserved source copy | Stock/video transcription now resolves the Hermes copy in the migrated environment; no deletion performed. |
| `/Users/admin/claw/models/mlx_models/Bonsai-8B-mlx-1bit` | Disabled canary/archive candidate | `local.bonsai-mlx` is not loaded and port `11437` is not listening. |
| `/Users/admin/models/gguf/Qwen3.6-27B-GGUF` | Duplicate/provenance candidate | Not active Hermes runtime; check provenance before archiving. |
| `/Users/admin/models/bonsai-original/Bonsai-8B.gguf` | Bonsai provenance/archive candidate | Not active Hermes runtime. |
| `/Users/admin/claw/projects/autoresearch-dashboard` | Intentional non-migrated legacy service | Active service outside this Hermes model migration; migration or shutdown needs separate approval. |
| `/Users/admin/claw/plugins/*` and `/Users/admin/claw/scripts/cipher/*` | Intentional preserved source | Hermes wrappers import legacy command source while forcing Hermes HOME, output roots, and model roots. |
| `/Users/admin/claw-cipher/.secrets` and `/Users/admin/claw-cipher/.venvs` | Intentional preserved config/venv | Exposed via Hermes compatibility symlinks for stock portfolio support; generated outputs go to Hermes. |

## Disabled Or Stale OpenClaw State

- `launchctl print gui/$(id -u)/ai.openclaw.gateway`: not found.
- Port `18789`: no listener.
- `/Users/admin/.openclaw`: no active runtime home found; prior state is
  archived under `.openclaw.pre-migration`.
- `local.bonsai-mlx`: not loaded; port `11437` has no listener.
- Disabled LaunchAgent backup files remain as historical records and were not
  re-enabled.

## Critical Assessment

The high-risk local-model dependency was the direct MLX service: before this
migration, Hermes could call a service that still reported and loaded a Claw
model path. That is now fixed at both the LaunchAgent and provider levels. The
service reports a Hermes model id, supports the non-streaming and streaming
OpenAI-compatible request shapes Hermes needs, and is registered behind an
explicit Hermes alias.

The second risk was transcription fallback drift. The migrated bridge now sets
Hermes model-root env values, and the reusable stock/video scripts no longer
fall back to a Claw model root when run with `HOME=/Users/admin/.hermes`.

Remaining Claw references are either preserved source imports, credential/venv
compatibility paths, disabled services, or source/duplicate model copies that
need an explicit archive/delete decision. They are not blockers for the active
Hermes migration.
