# Discord Gateway Readiness Check

Use this reference when auditing whether Hermes Discord integration is actually live. It captures a reusable check sequence, not one session's transient state.

## Read-only checks

```bash
hermes status --all
hermes gateway status
hermes tools list --platform discord
hermes doctor | grep -Ei 'discord|gateway|messaging|intent|token|platform|service|warning|error'
```

Interpretation:
- `Discord ✓ configured` means config/env are present; it does not mean the gateway is running.
- `Gateway Service ✗ stopped` or `hermes gateway status` reporting not running means Discord will not respond live even if the bot token is valid.
- `hermes tools list` without `--platform discord` shows the CLI/default platform, not Discord. Always pass `--platform discord` for platform-specific tool enablement.
- Disabled `messaging`, `discord`, or `discord_admin` toolsets do not necessarily block normal Discord chat through the gateway; they only affect extra in-session messaging/admin tools.

## Non-secret config inspection

Prefer structural checks that print key names and booleans, never token values. Useful fields:
- `discord.require_mention`
- `discord.auto_thread` (should remain false when the user wants no new threads)
- `discord.history_backfill` / `history_backfill_limit`
- `platform_toolsets.discord`
- presence of `DISCORD_BOT_TOKEN` and `DISCORD_HOME_CHANNEL` in `~/.hermes/.env`

## Bot login smoke test

If full gateway logs are absent or the gateway service is not installed, validate Discord credentials directly with the Hermes venv Python, not system Python. The `hermes` wrapper may use `/home/h/.hermes/hermes-agent/venv/bin/hermes`, so system `python3` can falsely report `ModuleNotFoundError: discord` even though Hermes has `discord.py` installed.

```bash
/home/h/.hermes/hermes-agent/venv/bin/python - <<'PY'
import asyncio, os, sys
from pathlib import Path
for line in (Path.home()/'.hermes/.env').read_text(errors='ignore').splitlines():
    line=line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    k, v = line.split('=', 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

token = os.getenv('DISCORD_BOT_TOKEN')
home = os.getenv('DISCORD_HOME_CHANNEL')
print('DISCORD_BOT_TOKEN:', 'set' if token else 'missing')
print('DISCORD_HOME_CHANNEL:', 'set' if home else 'missing')
if not token:
    sys.exit(2)
import discord
print('discord.py:', getattr(discord, '__version__', 'unknown'))
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print('login: ok')
    print('bot_user:', str(client.user))
    print('guild_count:', len(client.guilds))
    if home:
        ch = client.get_channel(int(home))
        print('home_channel_resolved:', bool(ch), type(ch).__name__ if ch else '')
    await client.close()

async def main():
    try:
        await asyncio.wait_for(client.start(token), timeout=20)
    except Exception as e:
        print('login: failed:', type(e).__name__, str(e))
        await client.close()

asyncio.run(main())
PY
```

## Start/enable path

If credentials and home channel resolve but gateway is stopped:

```bash
hermes gateway install
hermes gateway start
```

In non-interactive automation, `hermes gateway install` may ask two prompts:
1. start the gateway now after installing the service
2. start the gateway automatically on login/boot with systemd

Feed both answers, or the install can exit before writing the user service:

```bash
printf 'Y\nY\n' | hermes gateway install
```

Then verify both systemd and Discord websocket connection:

```bash
hermes gateway status
systemctl --user status hermes-gateway --no-pager -l
sleep 8
tail -80 ~/.hermes/logs/gateway.log | grep -Ei 'Connected as|discord connected|Gateway running|error|exception'
```

Good evidence of live Discord gateway:
- `hermes-gateway.service` is `active (running)`
- `hermes gateway status` says the user gateway service is running
- logs contain `Connected as <bot>` and `✓ discord connected`
- linger enabled is a plus because the gateway survives logout

For a temporary foreground run:

```bash
hermes gateway run
```

Do not claim Discord is live until either the gateway service is running or a foreground gateway process is active, and preferably until the logs show the Discord adapter connected.
