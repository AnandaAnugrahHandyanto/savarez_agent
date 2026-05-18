# DigitalOcean Gradient (serverless inference)

Hermes profile for [DigitalOcean Inference](https://docs.digitalocean.com/products/inference/) **serverless** endpoints: OpenAI-compatible `POST /v1/chat/completions` and `GET /v1/models` on `https://inference.do-ai.run/v1`.

## Credentials

HTTP requests use **`Authorization: Bearer <token>`**. Per [Serverless Inference API Endpoints](https://docs.digitalocean.com/products/inference/how-to/si-endpoints/), DigitalOcean accepts either:

1. **Model access key** (recommended for inference-only scope) — create under **Inference → Model access keys** in the [DigitalOcean control panel](https://cloud.digitalocean.com/), or follow [Manage model access keys](https://docs.digitalocean.com/products/inference/how-to/manage-model-access-keys/).
2. **Personal access token (PAT)** — also works as the Bearer token; PATs are broader account credentials (rotate carefully, least-privilege scopes).

Set the key in Hermes as:

- `DIGITALOCEAN_GRADIENT_API_KEY` — primary env var (Hermes naming; not the same string as DO’s console label, but the value is the key or PAT).

Optional override:

- `DIGITALOCEAN_GRADIENT_BASE_URL` — defaults to `https://inference.do-ai.run/v1` if unset.

## Provider id and aliases

- Canonical: `digitalocean-gradient`
- Aliases: `do-gradient`, `digitalocean` (CLI / config normalization)

## Compatibility caveats

OpenAI-compatible does not mean full OpenAI feature parity. See [Inference limits](https://docs.digitalocean.com/products/inference/details/limits/) for caveats, tool/plugin support, and rate limits (documented defaults include **5000 requests/hour** and **250 requests/minute** on applicable operations per the [API reference](https://docs.digitalocean.com/reference/api/reference/serverless-inference/)).

## Further reading

- [Use serverless inference](https://docs.digitalocean.com/products/gradient-ai-platform/how-to/use-serverless-inference/)
- [Available models](https://docs.digitalocean.com/products/inference/details/models/)
