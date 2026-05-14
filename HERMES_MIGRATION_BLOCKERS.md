# Hermes Migration Blockers

Last updated: May 14, 2026, 2:50 PM EDT

## Completion Blockers

None for the migrated Hermes command surfaces or active local-model migration.

## Intentional Legacy Dependencies

- `/Users/admin/claw/plugins/*` and `/Users/admin/claw/scripts/cipher/*`
  - Preserved source copies only.
  - Migrated command bridges now load Hermes-owned native copies from
    `/Users/admin/.hermes/plugins/cipher-workflows/native`.

- `/Users/admin/claw/models/mlx_models/Qwen3.6-27B-OptiQ-4bit`
  - Preserved source copy only.
  - Active MLX serving now uses
    `/Users/admin/.hermes/models/mlx_models/Qwen3.6-27B-OptiQ-4bit`.

- `/Users/admin/claw/models/mlx_models/distil-large-v3`
  - Preserved source copy only.
  - Migrated stock/video transcription resolves
    `/Users/admin/.hermes/models/mlx_models/distil-large-v3`.

- `/Users/admin/claw-cipher/.secrets` and `/Users/admin/claw-cipher/.venvs`
  - Preserved SnapTrade config/venv dependencies for stock portfolio comparison.
  - Exposed through Hermes compatibility symlinks; not used as generated output
    roots.

- `/Users/admin/claw/projects/autoresearch-dashboard`
  - Active non-migrated legacy dashboard via `com.local.autoresearch-dashboard`.
  - Not part of the migrated Hermes command surfaces. Migrating or stopping it
    should be a separate approval because it is an active service.

## Explicitly Excluded

- Discord paths/configs/integrations were not inspected, migrated, tested, or
  modified.

## Future Approval Candidates

- Archive or delete preserved Claw model source copies after a separate
  duplicate/provenance decision.
- Migrate or stop the active AutoResearch dashboard if the next goal is to
  remove every active Claw process, not just migrated Hermes ownership.
- Move the active Ollama blob store from `/Users/admin/.ollama/models` to
  `/Users/admin/.hermes/models/ollama` during a planned service window.
