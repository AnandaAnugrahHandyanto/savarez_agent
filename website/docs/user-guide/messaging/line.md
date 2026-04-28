---
sidebar_position: 16
title: "LINE"
description: "Set up Hermes Agent as a LINE Messaging API bot"
---

# LINE Setup

Hermes connects to LINE through the official **LINE Messaging API**. Users message your LINE Official Account, LINE sends HTTPS webhooks to your Hermes gateway, and Hermes replies through the Messaging API. The adapter supports text, images, voice messages, group chats, loading indicators, and native LINE audio replies.

:::info Official Account usage tiers
LINE Official Account plans vary by country or region. In Japan, the common public tiers are Free, Light, and Standard. As an example, LINE's public pricing docs list these monthly included-message counts for Japan:

| Tier | Included messages per month |
|------|-----------------------------|
| Free | Up to 200 |
| Light | Up to 5,000 |
| Standard | Up to 30,000 |

LINE counts push, multicast, broadcast, and narrowcast messages toward the plan message count, but **reply messages are not counted**.

Hermes is designed around that billing model: it caches each inbound reply token and uses the **Reply API first** whenever possible. If the reply token is stale or unavailable, Hermes falls back to the Push API so the response still gets delivered. LINE reply tokens are single-use and must be used quickly, so long-running agent turns may still require a push fallback.
:::

:::warning Public HTTPS Required
LINE webhooks require a public HTTPS URL. For local testing, use a tunnel such as Cloudflare Tunnel, ngrok, or another reverse proxy. For production, run Hermes behind a stable HTTPS endpoint.
:::

## Prerequisites

- A LINE Developers account
- A LINE Official Account with a Messaging API channel
- A public HTTPS URL that forwards to the Hermes gateway
- Hermes installed with the messaging extra:

```bash
pip install hermes-agent[messaging]
```

The messaging extra installs `line-bot-sdk` and `aiohttp`, which the LINE adapter needs at runtime.

## Step 1: Create a Messaging API Channel

1. Open the [LINE Developers Console](https://developers.line.biz/console/)
2. Create or select a provider
3. Create a **Messaging API** channel
4. Open the channel's **Messaging API** tab
5. Copy the **Channel access token**
6. Open the **Basic settings** tab and copy the **Channel secret**

Keep both values secret. The access token can send messages as your Official Account, and the channel secret validates webhook signatures.

## Step 2: Configure the Webhook URL

Hermes listens on `/webhooks/line` by default. If your public URL is `https://bot.example.com`, set the LINE webhook URL to:

```text
https://bot.example.com/webhooks/line
```

In the LINE Developers Console:

1. Open your Messaging API channel
2. Go to **Messaging API**
3. Enable **Use webhook**
4. Set the **Webhook URL**
5. Use **Verify** to test reachability after the gateway is running

If you are running locally through a tunnel, forward the tunnel to the LINE webhook port. The default local listener is:

```text
http://127.0.0.1:8645/webhooks/line
```

## Step 3: Configure Hermes

Add the required credentials to `~/.hermes/.env`:

```bash
# Required
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_CHANNEL_SECRET=...

# Access control - pick one:
LINE_ALLOWED_USERS=Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# LINE_ALLOWED_USERS=*          # Allow everyone
# LINE_ALLOW_ALL_USERS=true     # Same effect as *
```

Optional webhook settings:

```bash
LINE_WEBHOOK_HOST=0.0.0.0
LINE_WEBHOOK_PORT=8645
LINE_WEBHOOK_PATH=/webhooks/line
LINE_MEDIA_PATH=/media/line
LINE_PUBLIC_BASE_URL=https://bot.example.com
LINE_MULTIMODAL_GRACE_PERIOD_SECONDS=5
```

| Variable | Purpose |
|----------|---------|
| `LINE_WEBHOOK_HOST` | Local bind address for the webhook server. Defaults to `0.0.0.0`. |
| `LINE_WEBHOOK_PORT` | Local webhook port. Defaults to `8645`. |
| `LINE_WEBHOOK_PATH` | Webhook path. Defaults to `/webhooks/line`. |
| `LINE_MEDIA_PATH` | Public path used to serve outbound voice replies. Defaults to `/media/line`. |
| `LINE_PUBLIC_BASE_URL` | Public HTTPS origin used for outbound audio URLs, for example `https://bot.example.com`. |
| `LINE_MULTIMODAL_GRACE_PERIOD_SECONDS` | Time window for grouping near-simultaneous image/voice/text events into one agent turn. Defaults to `5`. |

Then start the gateway:

```bash
hermes gateway              # Foreground
hermes gateway install      # Install as a user service
sudo hermes gateway install --system   # Linux only: boot-time system service
```

## Access Control

Hermes uses LINE user IDs for allowlists. LINE user IDs usually begin with `U`; group IDs begin with `C`; room IDs begin with `R`.

To find your user ID, send a message to the bot and check the gateway logs:

```bash
hermes logs --follow --level debug
```

For a private bot, configure `LINE_ALLOWED_USERS` with specific user IDs. For a public or team bot, use `LINE_ALLOWED_USERS=*` or `LINE_ALLOW_ALL_USERS=true` only if you understand the risk: allowed users can reach the same agent tools that are available from other gateway platforms.

## Usage Tiers and Quota Behavior

LINE plan limits are based on counted outbound messages. LINE's Messaging API pricing docs distinguish between counted send methods and non-counted reply messages:

- **Not counted toward the plan message total:** Reply API messages
- **Counted toward the plan message total:** Push, multicast, broadcast, and narrowcast messages

Hermes therefore optimizes for low quota usage:

- Uses the Reply API first when responding to a recent inbound message
- Sends up to five LINE message objects in one reply request when long text is chunked
- Falls back to Push API only when the reply token is missing, already used, or expired
- Disables interim assistant commentary on LINE by default
- Sets LINE's tool progress default to `off` and streaming to `false` to avoid extra permanent message bubbles
- Sends voice-mode turns as a single modality where possible: voice input gets one voice reply instead of both voice and text

The adapter logs quota snapshots around sends using LINE's quota endpoints when credentials are available. Check `~/.hermes/logs/gateway.log` to see current usage snapshots and delivery mode metadata.

## Voice and Images

LINE voice messages are downloaded from LINE, cached locally, and passed through Hermes's normal speech-to-text pipeline. Configure an STT provider as described in [Voice Mode](/docs/user-guide/features/voice-mode).

Outgoing voice replies require `LINE_PUBLIC_BASE_URL`. LINE fetches audio by URL, so Hermes converts generated audio to LINE-compatible `.m4a`, serves it from the gateway's media path, and sends it as a native LINE audio message.

Images are downloaded from LINE previews, cached locally, and passed to the agent as image inputs. When an image arrives immediately after a voice or text event, Hermes waits briefly so the media and text can be processed as one multimodal turn.

## Message Formatting and Delivery

LINE does not support message editing in the same way as Telegram, Discord, or Slack. Hermes treats LINE as a quota-sensitive, low-noise platform:

- Tool progress is off by default
- Token streaming is disabled by default
- Loading animation is sent best-effort while the agent works
- Long text is split into LINE-sized chunks
- Reply tokens are preferred over push messages for quota control

You can override display defaults in `~/.hermes/config.yaml`, but increasing progress verbosity on LINE can consume additional quota because every progress update must be sent as a separate message:

```yaml
display:
  platforms:
    line:
      tool_progress: off
      streaming: false
```

## Home Channel and Scheduled Delivery

LINE is optimized for direct replies to the current conversation. The `send_message` tool can send to:

- an explicit target such as `line:Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- the active LINE session when the agent is already running inside LINE

Hermes intentionally avoids a generic LINE home-channel fallback for bare `line` sends. This prevents scheduled or tool-generated messages from accidentally burning push-message quota in the wrong chat.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **Webhook verify fails** | Confirm the public URL is HTTPS, routes to `LINE_WEBHOOK_PORT`, and includes the configured `LINE_WEBHOOK_PATH`. Check firewall and reverse-proxy rules. |
| **Invalid signature** | Verify `LINE_CHANNEL_SECRET` matches the Messaging API channel that is sending webhooks. |
| **Bot receives messages but does not reply** | Check `LINE_ALLOWED_USERS` or pairing state. Unknown users are denied unless allowlisted or paired. |
| **Voice replies fail with public base URL error** | Set `LINE_PUBLIC_BASE_URL` to the public HTTPS origin that can serve `LINE_MEDIA_PATH`. |
| **Reply works sometimes, push fallback appears in logs** | Long tool runs can exceed LINE's reply-token window. Hermes falls back to push delivery when the reply token can no longer be used. |
| **Quota usage is higher than expected** | Keep `display.platforms.line.tool_progress: off`, avoid enabling streaming/progress, and prefer direct conversation replies over scheduled push delivery. |
| **Images or voice arrive as separate turns** | Increase `LINE_MULTIMODAL_GRACE_PERIOD_SECONDS` slightly if your client sends media and captions slowly. |

## Security

:::warning
Configure access control before exposing the webhook publicly. Set `LINE_ALLOWED_USERS` to specific LINE user IDs, use the DM pairing system, or explicitly opt into `LINE_ALLOWED_USERS=*` / `LINE_ALLOW_ALL_USERS=true`.
:::

- Store `LINE_CHANNEL_ACCESS_TOKEN` and `LINE_CHANNEL_SECRET` only in `~/.hermes/.env`
- Do not commit `.env` or logs containing raw credentials
- Use a dedicated LINE Official Account for the bot
- Rotate the channel access token if it leaks
- Run one gateway per LINE channel token; Hermes uses a local scoped lock to prevent multiple profiles from using the same token at once
- Review your logs before sharing debug bundles, because chat IDs and user IDs can identify LINE users or groups
