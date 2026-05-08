---
sidebar_label: macOS airgap mode
sidebar_position: 7
description: >-
  Run Hermes with zero cloud calls on Apple Silicon using the vMLX provider
  plugin. Suitable for privacy-sensitive, regulated, and offline workloads.
---

# macOS airgap mode

This guide walks you from a clean macOS install to a fully airgapped Hermes —
no cloud API calls, no telemetry, all inference on-device — using the
**vMLX** model-provider plugin (Hermes v0.13.0+).

For provider-only reference docs, see
[`plugins/model-providers/vmlx/README.md`](https://github.com/NousResearch/hermes-agent/tree/main/plugins/model-providers/vmlx).
For the underlying plugin contract, see
[Model Provider Plugins](/docs/developer-guide/model-provider-plugin).

:::info Who is this for?
- You handle data that cannot leave your machine (legal, medical, KRITIS,
  regulated, classified-equivalent workloads).
- You want predictable cost: $0 per token, forever.
- You want Hermes to keep working on a plane, in a SCIF, or anywhere the WAN
  is down.
:::

## Prerequisites

- Apple Silicon Mac (M1 / M2 / M3 / M4 / M5 family). Intel is not supported.
- macOS 14 or newer.
- 24 GB unified memory minimum; 36 GB+ for a primary model in the 30 B class.
- Python 3.11 (managed via `uv` recommended).
- Hermes Agent **v0.13.0 or later** — earlier versions don't have the
  `ProviderProfile` plugin contract that `vmlx` registers against.
- `hermes doctor` passing on a non-airgap config.

## 1. Install vMLX

```bash
pip install vmlx
```

The plugin loads automatically — discovery happens at first
`get_provider_profile()` call.

## 2. Download MLX models

You need **two** models: a *primary* for the main agent loop and a smaller
*janitor* for auxiliary tasks (compression, memory writes, summarization,
skill curation).

```bash
mkdir -p ~/models

huggingface-cli download mlx-community/Qwen2.5-32B-Instruct-4bit \
    --local-dir ~/models/primary

huggingface-cli download mlx-community/gemma-3-4b-it-4bit \
    --local-dir ~/models/janitor
```

The names above are suggestions — any MLX-quantized chat model in those
size classes will work.

## 3. Start both vMLX servers

For a manual smoke test:

```bash
vmlx serve --model ~/models/primary --port 8000 --ctx-size 65536 &
vmlx serve --model ~/models/janitor --port 8001 --ctx-size 16384 &
```

For permanent setup, see the [launchd section](#launchd-auto-start) below.

## 4. Configure Hermes

The `vmlx` plugin registers two profiles with sane defaults — primary on
`:8000`, janitor on `:8001`. You only need to wire them into your
`config.yaml`:

```yaml
model:
  provider: vmlx
  name: primary
  context_length: 65536
  temperature: 0.2

auxiliary_routes:
  compression:     { provider: vmlx-janitor, name: janitor }
  memory_write:    { provider: vmlx-janitor, name: janitor }
  skill_curation:  { provider: vmlx-janitor, name: janitor }
  context_summary: { provider: vmlx-janitor, name: janitor }

fallback_providers: []
```

`fallback_providers: []` is the explicit airgap declaration — Hermes will
never reach for a cloud provider on inference failure.

If your Hermes release does not yet support per-task `provider` overrides
in `auxiliary_routes`, drop the block and use `default_aux_model` to point
at a smaller model on the primary endpoint instead.

And the matching `.env` — local-only variables, no cloud keys:

```bash
# Local endpoints only. Do NOT add OPENAI_API_KEY, ANTHROPIC_API_KEY, or any
# other cloud credential here — adding one defeats the airgap guarantee
# because plugins may opportunistically use cloud creds as fallbacks.
HERMES_LOG_LEVEL=info
HERMES_TELEMETRY=off
```

## launchd auto-start

`launchd` runs with an empty `PATH`, so the plists need an **absolute** path
to the `vmlx` binary. The location depends on how you installed it:

```bash
# Find the absolute path to substitute below.
which vmlx
# Common locations on Apple Silicon:
#   /opt/homebrew/bin/vmlx                (Homebrew on Apple Silicon)
#   ~/Library/Python/3.11/bin/vmlx        (pip --user)
#   <venv>/bin/vmlx                       (virtualenv)
```

Capture both substitutions before writing the plists:

```bash
export VMLX_BIN="$(which vmlx)"
export USERNAME="$(whoami)"
```

`~/Library/LaunchAgents/dev.hermes.vmlx-primary.plist` — `VMLX_BIN` and
`USERNAME` are placeholders to substitute:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>dev.hermes.vmlx-primary</string>
  <key>ProgramArguments</key>
  <array>
    <string>VMLX_BIN</string>
    <string>serve</string>
    <string>--model</string><string>/Users/USERNAME/models/primary</string>
    <string>--port</string><string>8000</string>
    <string>--ctx-size</string><string>65536</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key>
  <string>/Users/USERNAME/Library/Logs/vmlx-primary.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/USERNAME/Library/Logs/vmlx-primary.log</string>
</dict>
</plist>
```

`~/Library/LaunchAgents/dev.hermes.vmlx-janitor.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>dev.hermes.vmlx-janitor</string>
  <key>ProgramArguments</key>
  <array>
    <string>VMLX_BIN</string>
    <string>serve</string>
    <string>--model</string><string>/Users/USERNAME/models/janitor</string>
    <string>--port</string><string>8001</string>
    <string>--ctx-size</string><string>16384</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key>
  <string>/Users/USERNAME/Library/Logs/vmlx-janitor.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/USERNAME/Library/Logs/vmlx-janitor.log</string>
</dict>
</plist>
```

Substitute the placeholders in-place and load both:

```bash
sed -i '' "s|VMLX_BIN|$VMLX_BIN|g; s|USERNAME|$USERNAME|g" \
    ~/Library/LaunchAgents/dev.hermes.vmlx-primary.plist \
    ~/Library/LaunchAgents/dev.hermes.vmlx-janitor.plist

launchctl load ~/Library/LaunchAgents/dev.hermes.vmlx-primary.plist
launchctl load ~/Library/LaunchAgents/dev.hermes.vmlx-janitor.plist
launchctl list | grep vmlx
```

## 5. Verify

```bash
hermes doctor
```

Expected (relevant lines — the `/models` probe is automatic per the
v0.13.0 plugin contract):

```
[ok]   provider 'vmlx' registered
[ok]   provider 'vmlx-janitor' registered
[ok]   http://localhost:8000/v1/models reachable
[ok]   http://localhost:8001/v1/models reachable
[ok]   fallback_providers is empty (airgap mode)
```

A quick end-to-end loop:

```bash
hermes run "summarize the contents of ~/Documents/notes.md in three bullets"
```

If the primary model produces a response and `tcpdump` shows no off-host
traffic from the Hermes process, the airgap is working:

```bash
sudo tcpdump -i any -nn 'host not 127.0.0.1 and host not ::1' &
hermes run "..."
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `vmlx` not registered in `hermes doctor` | Plugin import failed (often non-Darwin) | Apple Silicon only; check `python -c "import platform; print(platform.system())"` |
| `/models` probe fails on :8000 or :8001 | `vmlx serve` not listening | `launchctl list \| grep vmlx`; tail `~/Library/Logs/vmlx-{primary,janitor}.log` |
| `context length exceeded` mid-loop | `--ctx-size` lower than `config.yaml` `context_length` | Restart the affected server with matching `--ctx-size` |
| `connection refused` on :8001 only | Janitor crashed (often OOM with both models loaded) | Smaller janitor model or raise quantization to 4-bit |
| All requests slow on first call only | MLX warming the model into unified memory | Expected; subsequent calls hit the warm model |
| `address already in use` on launch | Another process owns 8000/8001 | `lsof -nP -iTCP:8000 -sTCP:LISTEN` then kill or change port |
| `auxiliary_routes` config rejected | Hermes release pre-dates per-task provider override | Drop the block; use `default_aux_model` on the primary profile instead |

:::tip Contributing
Found a gap or a bug in this guide? See
[CONTRIBUTING.md](https://github.com/NousResearch/hermes-agent/blob/main/CONTRIBUTING.md).
The plugin's macOS gate lives in `__init__.py` (`ImportError` on non-Darwin),
so non-Mac contributors can hack on Hermes without it loading.
:::
