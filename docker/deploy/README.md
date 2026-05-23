# Mac Mini Deployment Configs

Personal deployment configs for running Hermes on the Mac Mini.
These are overlay files — they don't modify upstream code.

## LiteLLM Proxy Sidecar

Routes model requests through Bedrock (Claude) and Vertex AI (Gemini)
instead of using API keys directly.

```bash
# Start with LiteLLM overlay
docker compose -f docker-compose.yml -f docker/deploy/docker-compose.litellm.yml up -d
```

Required env vars in `~/.hermes/.env`:
- `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` (Bedrock)
- `GOOGLE_CLOUD_API_KEY` (Vertex AI)

Then configure each agent's model to use the proxy:
```yaml
model:
  provider: custom
  base_url: http://litellm-proxy:4000/v1
```

## Signal Voice Memo Path Translation

When Hermes runs in Docker but signal-cli runs on the host (via
`host.docker.internal`), attachment paths like `/opt/data/cache/audio/tts.ogg`
are unreachable from signal-cli.

Apply the patch:
```bash
git apply docker/deploy/signal-host-path.patch
```

Then set in your agent's env:
```
SIGNAL_HOST_DATA_DIR=~/.hermes
```

This translates container paths (`/opt/data/...`) to host paths
(`~/.hermes/...`) before passing them to signal-cli.

## Telegram Proxy

Upstream already supports `TELEGRAM_PROXY` env var via `resolve_proxy_url()`.
No patch needed — just set the env var if your network requires a proxy:
```
TELEGRAM_PROXY=socks5://host:port
```
