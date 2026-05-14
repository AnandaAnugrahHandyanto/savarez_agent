# Hermes Local Models Migration Goal Prompt

Last updated: May 14, 2026, 1:57 PM EDT

```text
/goal
Complete the Hermes local models migration so Hermes can register and utilize
all required local models without active model-serving, transcription, logs,
runtime state, generated artifacts, or migrated command behavior depending on
Claw/OpenClaw model or output folders.

Objective:
Make `/Users/admin/.hermes/models` the canonical Hermes-owned local model root
for migrated Hermes workflows. Move or redirect all required local model assets
with verification, then register the resulting local endpoints/aliases in
Hermes config only after the served model ids and runtime paths are Hermes-owned.

Project Folder:
`/Users/admin/.hermes/hermes-agent`

Hermes Runtime Home:
`/Users/admin/.hermes`

Hermes Profiles Folder:
`/Users/admin/.hermes/profiles`

Hermes Model Root:
`/Users/admin/.hermes/models`

Audit-Only OpenClaw/Claw Paths:
- `/Users/admin/claw`
- `/Users/admin/claw-cipher`
- `/Users/admin/.openclaw`

Known Current Model State:
- Studio Ollama endpoint `http://127.0.0.1:11434/v1` is live and already
  Hermes-registered for:
  - `gemma4:31b`
  - `qwen3.6:27b-q5_K_M`
  - `qwen3.6:35b-a3b-q4_K_M`
- Mac mini Ollama endpoint `http://admins-Mac-mini.local:11434/v1` is live and
  already Hermes-registered for:
  - `qwen3:4b-instruct`
  - `qwen3:8b`
- Direct MLX Qwen endpoint `http://127.0.0.1:11435/v1` is live but still serves
  model id `/Users/admin/claw/models/mlx_models/Qwen3.6-27B-OptiQ-4bit`.
- Whisper fallback model `distil-large-v3` still lives at
  `/Users/admin/claw/models/mlx_models/distil-large-v3`.
- Bonsai MLX is disabled and must remain disabled unless a separate canary is
  explicitly approved.
- LM Studio has no active migration need unless live evidence changes.

Definition of Done:
- Hermes gateway is running and healthy via `ai.hermes.gateway` and
  `hermes status`.
- `/Users/admin/.hermes/profiles` is preserved and documented as Hermes-owned
  runtime state.
- `/Users/admin/.hermes/models` exists and is the canonical Hermes-owned model
  asset root for migrated workflows.
- Active direct MLX Qwen model asset is copied to:
  `/Users/admin/.hermes/models/mlx_models/Qwen3.6-27B-OptiQ-4bit`
- `local.qwen-mlx-11435` LaunchAgent points `--model` and `--model-id` at the
  Hermes model path, not `/Users/admin/claw/models`.
- `curl -s http://127.0.0.1:11435/v1/models` returns the Hermes model path.
- Hermes config registers the direct MLX service with a clear provider/alias
  after the service reports a Hermes-owned model id.
- `distil-large-v3` is copied to:
  `/Users/admin/.hermes/models/mlx_models/distil-large-v3`
- Stock-update transcription is explicitly pointed at the Hermes model root via
  `CIPHER_STOCK_UPDATES_TRANSCRIBE_MODEL_ROOT=/Users/admin/.hermes/models` or
  an equivalent non-fallback Hermes config path.
- Video-summary transcription is verified not to resolve `distil-large-v3`
  through `/Users/admin/claw/models`.
- Studio Ollama and Mac mini Ollama remain registered and usable by Hermes.
- Every remaining Claw/OpenClaw model reference is classified as:
  - migrated to Hermes
  - intentional legacy source/config
  - disabled canary
  - duplicate/archive candidate
  - stale/unused
  - unknown and blocked with exact evidence
- No migrated workflow writes generated outputs, transcripts, logs, recordings,
  reports, model runtime state, or Telegram delivery artifacts under
  `/Users/admin/claw*`.
- No duplicate active output/model runtime trees exist where Hermes and Claw
  both receive the same generated artifact or active model runtime state.
- Verification evidence is written to:
  - `HERMES_LOCAL_MODELS_MIGRATION_CHECKLIST.md`
  - `HERMES_MIGRATION_CHECKLIST.md`
- Findings are written to:
  - `HERMES_LOCAL_MODELS_MIGRATION_PLAN.md`
  - `HERMES_MIGRATION_FINDINGS.md`
- Folder navigation remains documented in:
  - `/Users/admin/.hermes/README.md`

Scope:
- Run all work from `/Users/admin/.hermes/hermes-agent`.
- Treat `/Users/admin/.hermes` as runtime state, not the git project.
- Treat `/Users/admin/.hermes/profiles` as runtime state that must be preserved.
- Do not inspect, migrate, test, or modify Discord paths/configs/integrations.
- Do not delete OpenClaw/Claw source or legacy data unless it is proven
  duplicated, migrated, documented, and safe to archive.
- Do not reset or casually clean the Hermes live checkout.
- Preserve unrelated user or runtime changes in the working tree.

Required Operating Loop:
1. Re-read:
   - `HERMES_LOCAL_MODELS_MIGRATION_PLAN.md`
   - `HERMES_LOCAL_MODELS_MIGRATION_CHECKLIST.md`
   - `HERMES_MIGRATION_FINDINGS.md`
   - `HERMES_MIGRATION_CHECKLIST.md`
   - `/Users/admin/.hermes/README.md`
2. Research live runtime state first:
   - `pwd`
   - `git status --short`
   - `hermes status`
   - `hermes profile list`
   - `launchctl print gui/$(id -u)/ai.hermes.gateway`
   - `find /Users/admin/.hermes -maxdepth 3 -type d -name profiles -print`
   - `launchctl list | rg -i 'ollama|mlx|qwen|bonsai|openwebui|hermes'`
   - `ps aux | rg -i 'ollama|mlx|qwen|bonsai|openwebui|hermes'`
3. Reconfirm model endpoints:
   - `curl -s http://127.0.0.1:11434/v1/models`
   - `curl -s http://127.0.0.1:11435/v1/models`
   - `curl -s http://admins-Mac-mini.local:11434/v1/models`
4. Build or refresh the model inventory:
   - `/Users/admin/.hermes/models`
   - `/Users/admin/claw/models`
   - `/Users/admin/.ollama/models`
   - `/Users/admin/models`
   - `/Users/admin/.cache/qmd/models`
   - `/Users/admin/.lmstudio/models`
   - `/Users/admin/.openclaw.pre-migration`
5. Classify every model path as migrated, intentional legacy, disabled canary,
   duplicate/archive candidate, stale/unused, or unknown.
6. Implement only high-confidence redirects and model moves.
7. After each meaningful change, run the fastest relevant verification.
8. Update the tracking docs after each verified phase.

High-Confidence Migration Steps:
1. Copy, do not delete, Qwen MLX OptiQ:
   `rsync -a --info=progress2 /Users/admin/claw/models/mlx_models/Qwen3.6-27B-OptiQ-4bit/ /Users/admin/.hermes/models/mlx_models/Qwen3.6-27B-OptiQ-4bit/`
2. Verify Qwen source/destination parity by size, file count, and representative
   checksums or manifest comparison.
3. Update `~/Library/LaunchAgents/local.qwen-mlx-11435.plist` so `--model` and
   `--model-id` point to
   `/Users/admin/.hermes/models/mlx_models/Qwen3.6-27B-OptiQ-4bit`.
4. Restart only `local.qwen-mlx-11435`.
5. Verify `127.0.0.1:11435` reports the Hermes path and can answer a minimal
   chat completion.
6. Register a Hermes provider/alias for the direct MLX service, for example:
   - provider: `mlx-studio`
   - alias: `mlx-qwen-optiq`
7. Copy, do not delete, `distil-large-v3`:
   `rsync -a --info=progress2 /Users/admin/claw/models/mlx_models/distil-large-v3/ /Users/admin/.hermes/models/mlx_models/distil-large-v3/`
8. Point stock/video transcription workflows at the Hermes model root with no
   silent fallback to Claw paths.
9. Run the smallest available local transcription smoke and confirm output
   artifacts still land under `/Users/admin/.hermes/outputs`.
10. Decide Bonsai and GGUF handling only after duplicate/provenance checks.
11. Leave Ollama blob migration as optional unless explicitly approved; it is
    not Claw-owned and is a larger service migration.

Required Searches:
- `/Users/admin/claw/models`
- `/Users/admin/claw-cipher`
- `/Users/admin/.openclaw`
- `mlx_models`
- `distil-large-v3`
- `Qwen3.6-27B-OptiQ`
- `Bonsai-8B`
- `OLLAMA_MODELS`
- `CIPHER_STOCK_UPDATES_TRANSCRIBE_MODEL_ROOT`
- `lightning-whisper-mlx`
- `local.qwen-mlx-11435`
- `127.0.0.1:11435`
- `model_aliases`
- `providers:`

Verification Checks:
1. `hermes status`
2. `hermes profile list`
3. `launchctl print gui/$(id -u)/ai.hermes.gateway`
4. `find /Users/admin/.hermes -maxdepth 3 -type d -name profiles -print`
5. `curl -s http://127.0.0.1:11434/v1/models`
6. `curl -s http://127.0.0.1:11435/v1/models`
7. `curl -s http://admins-Mac-mini.local:11434/v1/models`
8. Minimal chat completion against `127.0.0.1:11435`
9. Minimal transcription smoke for the migrated `distil-large-v3` path
10. `ps aux | rg -i 'ollama|mlx|qwen|bonsai|openwebui|hermes'`
11. Path audit showing no migrated model runtime still references
    `/Users/admin/claw/models`
12. Path audit showing no migrated workflow writes generated outputs under
    `/Users/admin/claw*`

Constraints:
- Do not include Discord in the migration scope.
- Do not treat `/Users/admin/.hermes` as the git project.
- Do not create tracking files directly in `/Users/admin/.hermes`; use the
  Hermes checkout for tracking files. The existing `/Users/admin/.hermes/README.md`
  is the only runtime navigation guide.
- Do not create a parallel Hermes model path without updating the service or
  command/runtime that uses it.
- Do not leave fallback behavior that writes to or resolves from Claw if Hermes
  model path creation fails.
- Do not hide errors with broad try/catch or silent fallback paths.
- Do not remove OpenClaw behavior that has not been migrated unless it is
  proven stale.
- Do not claim completion from config inspection alone; verify with runtime
  endpoint, process, and command evidence.
- Keep status timestamps in 12-hour Eastern Time.
- Preserve unrelated user or runtime changes in the working tree.

Stop Condition:
Stop only when:
- every required local model has a verified Hermes-owned path or an explicit
  documented non-Hermes classification,
- the active direct MLX endpoint reports a Hermes-owned model id,
- Hermes can register and utilize the direct MLX model through a provider/alias,
- transcription fallbacks resolve through Hermes-owned model paths,
- `/Users/admin/.hermes/profiles` is preserved,
- every remaining Claw/OpenClaw model path is documented as legacy, disabled,
  stale, duplicate/archive candidate, or intentionally preserved,
- Hermes health checks pass,
- and the relevant checklists are fully updated.

Final Response:
Report:
- Hermes health status
- local models migrated
- local models already registered
- old Claw/OpenClaw model paths removed, bypassed, or intentionally preserved
- new Hermes model roots
- profile handling result
- verification commands and results
- remaining intentional Claw/OpenClaw dependencies
- blockers requiring user approval
```
