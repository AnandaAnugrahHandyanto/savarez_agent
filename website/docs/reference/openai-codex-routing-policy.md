# OpenAI Codex Plan routing policy

Hermes uses the `openai-codex` provider for ChatGPT/Codex Plan OAuth work. This
is separate from the direct OpenAI API path and should stay that way unless the
user explicitly chooses API billing.

## Defaults

- Provider: `openai-codex`
- Primary model: `gpt-5.5`
- Auxiliary model: `gpt-5.4-mini`
- Coding fallback: `gpt-5.3-codex`
- Not supported on the current plan: `gpt-5.5-pro`

## Routing rules

- Use `gpt-5.5` for implementation, debugging, architecture, security review,
  project planning, and any critical task.
- Use `gpt-5.4-mini` for compression, titles, metadata, classification, smoke
  checks, monitors, PR status polling, and other cheap/background work.
- Low-budget/background tasks use `gpt-5.4-mini` unless marked critical.
- Existing explicit config values win; the policy only fills defaults.

The machine-readable helper lives in `agent/codex_model_policy.py`:

```python
from agent.codex_model_policy import choose_codex_model

route = choose_codex_model("compression")
assert route.provider == "openai-codex"
assert route.model == "gpt-5.4-mini"
```

## Verification

Capability monitoring should use:

```bash
python scripts/smoke_openai_codex_capabilities.py --baseline latest --output ~/.hermes/diagnostics/codex_capability/latest.json
```

The smoke script must continue to call Hermes with `provider="openai-codex"`,
not `OPENAI_API_KEY` or direct OpenAI API credentials.
