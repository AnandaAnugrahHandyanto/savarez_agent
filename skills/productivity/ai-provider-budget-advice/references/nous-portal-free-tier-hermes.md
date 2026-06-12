# Nous Portal free tier for Hermes

Session-derived reference for advising Hevar on free/low-cost AI through Nous Portal.

## What was verified

- The Nous Portal subscription page showed a Free plan at `$0/mo` with:
  - free model access
  - pay-as-you-go access to 300+ models
- Paid tiers showed hosted tool usage and monthly credits; do not promise hosted Tool Gateway access on Free unless live docs/status confirm it.
- `hermes portal status` can show Portal auth, Portal API URL, current model/provider, and Tool Gateway routing.
- A Hermes profile may be logged into Nous Portal while the active/default model is still another provider.

## Useful commands

Inspect Portal state:

```bash
hermes portal status
```

List Tool Gateway routing/catalog:

```bash
hermes portal tools
```

Smoke-test a free Nous model without changing global config:

```bash
hermes chat -Q --provider nous -m 'stepfun/step-3.7-flash:free' -q 'Reply with exactly: NOUS_FREE_MODEL_OK'
```

Alternative model seen in the same free recommendations:

```bash
hermes chat -Q --provider nous -m 'nvidia/nemotron-3-ultra:free' -q 'Reply with exactly: NOUS_FREE_MODEL_OK'
```

## Live-free-model caveat

Free model IDs are not permanent. Treat specific IDs as examples, not durable truth. If possible, check live Portal recommendations or run `hermes model`/Portal picker before advising.

## Recommended explanation to user

- For $0 Hermes use, try Nous Portal Free models first.
- For agent/tool-heavy Hermes use, paid Portal or OpenRouter credit may be more practical.
- For one-off free usage, use `--provider nous -m <free-model-id>`.
- For permanent switching, use `hermes model` and pick Nous Portal.
