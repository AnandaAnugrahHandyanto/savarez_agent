# Gemini 2.5 Flash — auxiliary, delegation, and fallback (Hermes)

Hermes routes **side work** (vision, web extract, context compression, session search, approval helpers, trajectory summarization) through the auxiliary client. The built-in defaults prefer **Gemini 2.5 Flash** for cost and latency when using OpenRouter, Nous Portal, or direct Google AI Studio (`provider: gemini`).

Secrets: store API keys in `~/.hermes/.env` (e.g. `GEMINI_API_KEY` from Vaultwarden `gemini_api_key`). Never commit keys.

## Recommended `config.yaml` (Codex / OpenRouter primary + Flash side tasks)

Use your main model on the primary turn; pin auxiliary tasks and subagents to Flash; keep a **fallback chain** so hard failures upgrade to a stronger model.

```yaml
# Primary agent (example — adjust to your stack)
model:
  provider: openrouter
  model: anthropic/claude-sonnet-4

# Cheap/fast auxiliary stack (same pattern for each slot)
auxiliary:
  vision:
    provider: gemini
    model: gemini-2.5-flash
  web_extract:
    provider: gemini
    model: gemini-2.5-flash
  compression:
    provider: gemini
    model: gemini-2.5-flash
  session_search:
    provider: gemini
    model: gemini-2.5-flash
  approval:
    provider: gemini
    model: gemini-2.5-flash

# delegate_task children — isolated context, typically narrower toolsets
delegation:
  provider: gemini
  model: gemini-2.5-flash
  max_iterations: 50

# When the primary model errors or exhausts retries, try Flash first, then escalate
fallback_providers:
  - provider: gemini
    model: gemini-2.5-flash
  - provider: openrouter
    model: anthropic/claude-sonnet-4
```

If you only use **OpenRouter** for everything, set `provider: openrouter` and `model: google/gemini-2.5-flash` in each block instead of `gemini` / bare `gemini-2.5-flash`.

## Task routing (what Flash should handle)

| Area | Hermes surface | Notes |
|------|----------------|--------|
| Subtask decomposition | Main model plans; `delegate_task` runs children | Children default to `delegation.*` or inherit parent — pin Flash on children |
| MCP / tool routing | Main turn | Keep primary model; routing prompts stay on main |
| Web extract | `auxiliary.web_extract` | Flash summarization of fetched pages |
| Summarization | `auxiliary.compression`, session search | Flash |
| Repo indexing / PR diff overview | Main agent or delegated workers | Use Flash on **delegated** workers for mechanical summaries; keep Sonnet/GPT on parent for tricky merges |
| Boilerplate / log tidy | Often `delegate_task` or main | Prefer Flash on delegates |

## Escalation policy (operations)

Hermes does not yet expose a single “auto-switch on low confidence” knob. Treat escalation as **explicit configuration + operator judgment**:

1. **`fallback_providers`** — ordered list after primary failure (HTTP errors, empty responses where applicable). Put Flash early, then Sonnet / GPT‑5 / Codex for hard failures.
2. **Retries** — when the same tool loop repeats without progress (`retry_count` high), switch session model (`/model`) or widen delegation to a stronger `delegation.model`.
3. **Malformed patches / low-quality edits** — rerun with a stronger primary model or delegate with `provider: anthropic` / `openrouter` and an opus/sonnet-class model.
4. **Security-sensitive or architectural work** — do not rely on Flash; use your tier‑1 model on the main agent and restrict delegates to read-only toolsets if needed.

Conditions from AUT‑28 to watch manually or automate later: `tool_loop`, `low_confidence`, `malformed_patch`, `retry_count > 2`.

## Smoke check

From a repo checkout:

```bash
hermes config get auxiliary.compression.model
hermes chat --model openrouter/anthropic/claude-sonnet-4 -p "Summarize README in three bullets" </dev/null
```

Confirm logs or traces show auxiliary calls targeting `gemini-2.5-flash` / `google/gemini-2.5-flash` when using OpenRouter defaults.
