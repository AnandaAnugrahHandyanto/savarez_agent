# OpenAI Codex Plan/OAuth capability matrix

Hermes's `openai-codex` provider uses the ChatGPT Codex Plan/OAuth path. It is
not the direct OpenAI API-key path: credentials are resolved from Hermes auth,
including `credential_pool.openai-codex` entries in `~/.hermes/auth.json`.

Use `scripts/smoke_openai_codex_capabilities.py` to refresh this matrix against
your own plan. The Codex endpoint is account/plan gated and can change server
side, so treat this file as a documented baseline plus a repeatable verification
procedure rather than a permanent guarantee.

## Baseline matrix

- `gpt-5.5`
  - Text: supported in prior smoke probes.
  - Function calling/tools: supported in prior smoke probes.
  - Structured outputs (`response_format: json_schema`): supported in prior smoke probes.
  - Vision/image input: supported in prior smoke probes.
  - Recommended default: yes, for Codex Plan/OAuth coding tasks.

- `gpt-5.4-mini`
  - Text: supported in prior smoke probes.
  - Function calling/tools: supported in prior smoke probes.
  - Structured outputs (`response_format: json_schema`): supported in prior smoke probes.
  - Vision/image input: supported in prior smoke probes.
  - Recommended default: economical/fast fallback.

- `gpt-5.3-codex`
  - Text: supported in prior smoke probes.
  - Function calling/tools: supported in prior smoke probes.
  - Structured outputs (`response_format: json_schema`): supported in prior smoke probes.
  - Vision/image input: supported in prior smoke probes.
  - Recommended default: legacy Codex-specialized fallback.

- `gpt-5.5-pro`
  - Status: not available in the probed Codex Plan/OAuth path on 2026-05-04.
  - Probe result: `400` — `The 'gpt-5.5-pro' model is not supported when using Codex with a ChatGPT account.`
  - Notes: availability is plan/server allow-list dependent. Re-run the smoke
    script before relying on this verdict in a different account or later date.

## Repeatable smoke-test procedure

From the repository root:

```bash
source .venv/bin/activate 2>/dev/null || source venv/bin/activate
python scripts/smoke_openai_codex_capabilities.py --model gpt-5.5 --json
```

Probe all documented baseline models and features:

```bash
python scripts/smoke_openai_codex_capabilities.py --json
```

Probe a candidate model such as `gpt-5.5-pro`:

```bash
python scripts/smoke_openai_codex_capabilities.py --model gpt-5.5-pro --json
```

Limit to a single feature when debugging:

```bash
python scripts/smoke_openai_codex_capabilities.py --model gpt-5.5 --feature text
python scripts/smoke_openai_codex_capabilities.py --model gpt-5.5 --feature tools
python scripts/smoke_openai_codex_capabilities.py --model gpt-5.5 --feature structured
python scripts/smoke_openai_codex_capabilities.py --model gpt-5.5 --feature vision
```

## Interpreting results

- Exit code `0`: every requested model/feature probe passed.
- Exit code `1`: one or more probes failed; inspect the printed `detail` field.
- Authentication failures should be fixed with `hermes auth openai-codex` or by
  checking `~/.hermes/auth.json` for a usable `credential_pool.openai-codex`
  entry. Do not add `OPENAI_API_KEY`; that switches to a different auth model.
- 404/unknown-model style failures usually mean the model is not available on
  the current Codex Plan/OAuth allow-list.
- 429/quota failures mean the plan is authenticated but temporarily exhausted;
  rerun after the reported reset.
