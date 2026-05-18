# hypura-harness (bundled extension)

OpenClaw bundled plugin **`hypura-harness`**: HTTP proxy tools (`hypura_harness_*`) to the Hypura Python harness (VRChat OSC, VOICEVOX, code run, skills, Shinka evolve, LoRA).

## Canonical paths

| Item | Path |
|------|------|
| Python project | `extensions/hypura-harness/scripts/pyproject.toml` |
| Daemon entry | `extensions/hypura-harness/scripts/harness_daemon.py` |
| Config | `extensions/hypura-harness/config/harness.config.json` |
| Default HTTP port | **18794** (avoids OpenClaw Bridge default **18790**) |

## Start the daemon

From repository root (after `uv` is installed):

```bash
cd extensions/hypura-harness/scripts && uv run harness_daemon.py
```

Windows (env merge + optional `openclaw.json` → harness model sync):

```powershell
.\scripts\launchers\Start-Hypura-Harness.ps1
```

Full desktop stack (Gateway, TUI, harness, etc.): `scripts/launchers/openclaw-desktop/launch-desktop-stack.ps1` or `Sovereign-Portal.ps1`. See [scripts/launchers/README.md](../../scripts/launchers/README.md).

## OpenClaw config

- Enable the plugin in `openclaw.json` under `plugins.entries["hypura-harness"]`.
- Set `plugins.entries["hypura-harness"].config.baseUrl` to match `harness.config.json` / daemon port (default `http://127.0.0.1:18794`).

## Docker

`docker-compose.override.yml` defines a `hypura-harness` service (image build context: this directory). Adjust compose env if you change ports.

## Operator docs

- Workspace skill: [skills/hypura-harness/SKILL.md](../../skills/hypura-harness/SKILL.md)
- LoRA pipeline: [extensions/hypura-harness/scripts/LORA_PIPELINE.md](./scripts/LORA_PIPELINE.md)
- Layout vs `scripts/hypura/`: [_docs/2026-04-05_OpenClaw-layout-Sovereign-overlay_clawdbot-main.md](../../_docs/2026-04-05_OpenClaw-layout-Sovereign-overlay_clawdbot-main.md)

## Extension boundary

Production code imports `openclaw/plugin-sdk/*` only; see [extensions/AGENTS.md](../AGENTS.md).
