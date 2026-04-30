# Provider-migration runbook

Goal: swap any role's provider/model in under two hours with zero methodology changes.

## Single-role swap

```bash
$EDITOR config/models.yml
bash scripts/apply-models-yml.sh
./hermes doctor
```

## Full provider migration

1. Confirm target provider is supported by Hermes.
2. Add target provider key to `${HERMES_HOME:-$HOME/.hermes}/.env`.
3. Update all roles and `/escalate` pool entries in `config/models.yml`.
4. Run `bash scripts/apply-models-yml.sh`.
5. Verify committed methodology files did not change.
6. Smoke-test `./hermes doctor` and `./hermes -c '/skills'`.

## Unsupported providers

Prefer OpenRouter or an OpenAI-compatible endpoint before carrying fork-local provider code. If a provider adapter is needed, upstream it.

## Anti-patterns

- Do not edit committed methodology files to swap models.
- Do not migrate during an overnight `/escalate` run.
- Do not remove fallback providers before testing the new primary alone.
