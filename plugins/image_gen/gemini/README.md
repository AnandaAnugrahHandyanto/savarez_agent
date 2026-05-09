# Gemini / Nano Banana image generation backend

This backend gives Hermes `image_generate` a direct Google Gemini path, separate from Nous/FAL.

## Credentials

The backend looks for the first non-empty key in this order:

1. `GEMINI_API_KEY`
2. `GOOGLE_API_KEY`
3. `NANO_BANANA_API_KEY`

`NANO_BANANA_API_KEY` is supported as a Palmer-local alias so the existing credential can be reused without copying or printing its value.

If you want the conventional Google env name too, run this in a shell that has Palmer's env loaded:

```bash
export GEMINI_API_KEY="$NANO_BANANA_API_KEY"
```

Do not paste the key into chat or logs.

## Config

Palmer profile config:

```yaml
image_gen:
  provider: gemini
  model: gemini-2.5-flash-image
  use_gateway: false
  gemini:
    image_size: 1K
```

Supported model IDs:

- `gemini-2.5-flash-image` — Nano Banana, fastest/safest default
- `gemini-3.1-flash-image-preview` — Nano Banana 2
- `gemini-3-pro-image-preview` — Nano Banana Pro

Optional env overrides:

- `GEMINI_IMAGE_MODEL`
- `GEMINI_IMAGE_SIZE` (`512`, `1K`, `2K`, `4K`)

## Usage

Once the `image_gen` toolset is enabled and the profile/gateway has been restarted, ask Palmer to generate an image. The backend saves inline Gemini image data under:

`$HERMES_HOME/cache/images/`
