# SecondBrain Memory Provider

Disabled-by-default Hermes memory provider for a controlled SecondBrain trial.

## Switch

The provider reads `$HERMES_HOME/secondbrain.json`:

```json
{
  "enabled": false,
  "mode": "recall_only",
  "base_url": "http://127.0.0.1:3030",
  "project_scope": "secondbrain-phase4-placeholder",
  "timeout_ms": 1500
}
```

- `enabled: false` is the rollback/off switch.
- `mode: recall_only` is the only initially supported live mode.
- `SECONDBRAIN_HERMES_TRIAL_ENABLED=false` is a hard-off environment override.
- Secret values must be supplied via environment variables only, never committed.

Enable as active memory provider only after review:

```bash
hermes config set memory.provider secondbrain
```

Gateway/CLI processes must be restarted or reset before config changes take effect.
