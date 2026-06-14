# Deploy notes — reproducing this Hermes build

This fork adds custom integrations on top of upstream Hermes. The **code** is
in the repo and works out of the box once dependencies, API keys, and a few
config settings are in place. Secrets are intentionally **not** committed
(`~/.hermes/.env` and `~/.hermes/config.yaml` live outside the repo), so a
fresh clone needs the steps below to run fully.

## 1. Install

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -e .          # installs deps from pyproject.toml (incl. requests)
```

## 2. API keys

Hermes reads keys from `~/.hermes/.env` (preferred) and the project `.env`.
Copy the template and fill in the keys you use:

```bash
mkdir -p ~/.hermes
cp .env.example ~/.hermes/.env
$EDITOR ~/.hermes/.env
```

Keys this build uses (names only — fill your own values):

| Variable | Purpose |
| --- | --- |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USERS`, `TELEGRAM_HOME_CHANNEL` | Telegram gateway |
| `DEEPSEEK_API_KEY` | Primary LLM provider (deepseek-v4-pro) |
| `OPENROUTER_API_KEY` | Fallback LLM provider (any OpenRouter model) |
| `PERPLEXITY_API_KEY` | Web search backend + `perplexity_ask` tool |
| `FIRECRAWL_API_KEY` | Web extract backend |
| `REPLICATE_API_TOKEN` | Image + video generation (custom plugins) |
| `MCP_GITHUB_API_KEY` | GitHub MCP (optional) |

## 3. Config deltas

On first run Hermes writes a default `~/.hermes/config.yaml`. Apply these
non-default settings (everything else stays default):

```yaml
model:
  provider: deepseek
  default: deepseek-v4-pro
  base_url: https://api.deepseek.com

# OpenRouter as fallback (tried when the primary fails)
fallback_providers:
  - provider: openrouter
    model: deepseek/deepseek-v4-pro

web:
  search_backend: perplexity
  extract_backend: firecrawl

# Custom Replicate media backends (this fork)
image_gen:
  provider: replicate
  replicate:
    model: black-forest-labs/flux-1.1-pro-ultra
video_gen:
  provider: replicate
  replicate:
    model: google/veo-3.1
```

## 4. Custom plugins (already in the repo)

- `plugins/image_gen/replicate/` — Replicate image backend (default
  `flux-1.1-pro-ultra`; override via `REPLICATE_IMAGE_MODEL`).
- `plugins/video_gen/replicate/` — Replicate video backend (default
  `google/veo-3.1`, text-to-video + image-to-video; override via
  `REPLICATE_VIDEO_MODEL`).

Both are bundled `kind: backend` plugins — they auto-load, no extra steps.
`toolsets.py` exposes `perplexity_ask` and `video_generate` in the core
toolset so they are reachable from Telegram and other platforms.

## 5. Run

```bash
hermes gateway restart      # or: python -m hermes_cli.main gateway run
hermes gateway status
```

## Notes

- No new Python dependencies — the Replicate plugins use `requests`, already
  declared in `pyproject.toml`.
- Media generation costs real money: flux-1.1-pro-ultra ≈ $0.06/image,
  veo-3.1 ≈ $0.40/s.
- `~/.hermes/config.yaml`'s `fallback_providers` must be a YAML list (as
  above). You can also manage it with `hermes fallback add`.
