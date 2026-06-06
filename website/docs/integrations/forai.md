---
title: "ForAI"
sidebar_label: "ForAI"
---

# ForAI

[ForAI](https://www.forai.ai) is an OpenAI-compatible AI model gateway for developers and AI agent builders.

## Configuration

ForAI can be used in Hermes as a custom OpenAI-compatible provider.

Provider type:

```text
OpenAI-compatible
```

Base URL:

```text
https://www.forai.ai/v1
```

API key:

```text
Your ForAI API key
```

## Example

Add ForAI as a named custom provider in `~/.hermes/config.yaml`:

```yaml
custom_providers:
  - name: forai
    base_url: https://www.forai.ai/v1
    key_env: FORAI_API_KEY

model:
  provider: custom:forai
  default: your-forai-model
```

Then put your API key in `~/.hermes/.env`:

```bash
FORAI_API_KEY=your_forai_api_key
```

You can also configure it interactively:

```bash
hermes model
# Select "Custom endpoint (self-hosted / VLLM / etc.)"
# Enter base URL: https://www.forai.ai/v1
# Enter your ForAI API key and model name
```

For OpenAI-compatible clients that use OpenAI-style environment variables, the equivalent settings are:

```bash
OPENAI_API_KEY=your_forai_api_key
OPENAI_BASE_URL=https://www.forai.ai/v1
```

## Notes

ForAI supports OpenAI-compatible chat completions and can be used with agent workflows that support custom OpenAI-compatible providers.

Get an API key at [forai.ai](https://www.forai.ai).
