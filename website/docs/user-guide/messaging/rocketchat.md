---
sidebar_position: 9
title: "Rocket.Chat"
description: "Set up Hermes Agent as a Rocket.Chat bot"
---

# Rocket.Chat Setup

Hermes Agent integrates with Rocket.Chat as a bot, letting you chat with your AI assistant through direct messages, public channels, or private groups. Rocket.Chat is a self-hosted, open-source team messaging platform — you run it on your own infrastructure and keep full control of your data. The bot connects via Rocket.Chat's REST API (v1) for outbound traffic and the Realtime (DDP) WebSocket for inbound messages, processes messages through the Hermes Agent pipeline (including tool use, memory, and reasoning), and responds in real time. It supports text, file attachments, images, and threaded replies.

No external Rocket.Chat library is required — the adapter uses `aiohttp`, which is already a Hermes dependency.

Before setup, here's the part most people want to know: how Hermes behaves once it's in your Rocket.Chat workspace.

## How Hermes Behaves

| Context | Behavior |
|---------|----------|
| **DMs** | Hermes responds to every message. No `@mention` needed. Each DM has its own session. |
| **Public/private channels** | Hermes responds when you `@mention` it. Without a mention, Hermes ignores the message. |
| **Threads** | If `ROCKETCHAT_REPLY_MODE=thread`, Hermes replies in a Rocket.Chat thread (via `tmid`) under your message. Thread context stays isolated from the parent room. |
| **Shared channels with multiple users** | By default, Hermes isolates session history per user inside the channel. Two people in the same channel do not share one transcript unless you explicitly disable that. |

:::tip
If you want Hermes to reply as threaded conversations (nested under your original message), set `ROCKETCHAT_REPLY_MODE=thread`. The default is `off`, which sends flat messages in the room.
:::

### Session Model in Rocket.Chat

By default:

- each DM gets its own session
- each thread gets its own session namespace
- each user in a shared channel gets their own session inside that channel

This is controlled by `config.yaml`:

```yaml
group_sessions_per_user: true
```

Set it to `false` only if you explicitly want one shared conversation for the entire room. Shared sessions can be useful for a collaborative channel, but they also mean users share context growth and token costs, and one person's long tool-heavy task can bloat everyone else's context.

This guide walks you through the full setup process — from creating your bot user on Rocket.Chat to sending your first message.

## Step 1: Create a Bot User

Rocket.Chat has a dedicated `bot` role for service accounts. Bots bypass the workspace's registration flow and can be added to rooms without counting against some plan limits.

1. Log in to Rocket.Chat as an **Admin**.
2. Go to **Admin** → **Users** → **New**.
3. Fill in the details:
   - **Username**: e.g., `hermes-bot`
   - **Name / Email**: whatever you want to show in the UI
   - **Password**: set a strong one (you can use it once to log in and generate a PAT, then never again)
   - **Roles**: add `bot`
   - Leave **Require password change** unchecked.
4. Click **Save**.

:::info
If you don't have Admin access, ask your Rocket.Chat administrator to create the bot user and assign it the `bot` role.
:::

## Step 2: Generate a Personal Access Token

Hermes authenticates as the bot using a Personal Access Token (PAT). The PAT doubles as a DDP resume token, so the same value authenticates both REST and the Realtime WebSocket.

1. Sign out of your admin account and **sign in as the bot user** you just created.
2. Open **Account** → **Personal Access Tokens**.
3. Enter a name (e.g., `hermes-gateway`) and — critically — check **☑ Ignore Two Factor Authentication**.
4. Click **Add**.
5. Rocket.Chat displays **both** the **Token** and the **User ID**. **Copy them both now.**

:::warning[Shown only once]
The token and user ID are displayed **only once** at creation time. If you lose them, regenerate the PAT (the old one stops working). Never share the token publicly or commit it to Git — anyone with this token has full control of the bot.
:::

:::tip[Why "Ignore Two Factor"]
If 2FA is enabled at the workspace level, a PAT **without** the "Ignore Two Factor" flag makes REST calls fail with `totp-required`. Unattended bots can't solve a 2FA challenge, so the flag is required for gateway use.
:::

## Step 3: Add the Bot to Channels

The bot needs to be a member of any room where you want it to respond:

1. Open the channel where you want the bot.
2. Click the channel name → **Members** → **Add**.
3. Search for your bot username (e.g., `hermes-bot`) and add it.

For DMs, simply open a direct message with the bot — it will be able to respond immediately.

## Step 4: Find Your User ID

Hermes Agent uses your Rocket.Chat User ID to control who can interact with the bot. To find it:

1. Click your **avatar** (top-right corner) → **My Account**.
2. The user ID appears in the profile URL or under **Profile** → **Copy user ID**.

Your User ID is a 17-character alphanumeric MongoDB ObjectId-style string like `kL92HdJ3pXs8Wf7eN`.

:::warning
Your User ID is **not** your username. The username is what appears after `@` (e.g., `@alice`). The User ID is a MongoDB-style identifier that Rocket.Chat uses internally.
:::

**Alternative**: You can also get your User ID via the API using the bot's credentials:

```bash
curl -H "X-Auth-Token: YOUR_TOKEN" -H "X-User-Id: YOUR_BOT_USER_ID" \
  https://your-rocketchat-server/api/v1/users.info?username=YOUR_USERNAME | jq '.user._id'
```

:::tip
To get a **Room ID**: open the room → kebab menu (⋮) → copy the roomId. Or hit `GET /api/v1/channels.info?roomName=<name>` for channels, `groups.info` for private groups, `im.list` for DMs.
:::

## Step 5: Configure Hermes Agent

### Option A: Interactive Setup (Recommended)

Run the guided setup command:

```bash
hermes gateway setup
```

Select **Rocket.Chat** when prompted, then paste your server URL, bot token, and bot user ID when asked.

### Option B: Manual Configuration

Add the following to your `~/.hermes/.env` file:

```bash
# Required
ROCKETCHAT_URL=https://rc.example.com
ROCKETCHAT_TOKEN=***
ROCKETCHAT_USER_ID=***
ROCKETCHAT_ALLOWED_USERS=kL92HdJ3pXs8Wf7eN

# Multiple allowed users (comma-separated)
# ROCKETCHAT_ALLOWED_USERS=kL92HdJ3pXs8Wf7eN,aB3cD4eF5gH6iJ7kL

# Optional: reply mode (thread or off, default: off)
# ROCKETCHAT_REPLY_MODE=thread

# Optional: respond without @mention (default: true = require mention)
# ROCKETCHAT_REQUIRE_MENTION=false

# Optional: rooms where bot responds without @mention (comma-separated room IDs)
# ROCKETCHAT_FREE_RESPONSE_CHANNELS=roomId_1,roomId_2
```

Optional behavior settings in `~/.hermes/config.yaml`:

```yaml
group_sessions_per_user: true
```

### Start the Gateway

Once configured, start the gateway:

```bash
hermes gateway
```

The bot should connect to your Rocket.Chat server within a few seconds. Send it a message — either a DM or in a channel where it's been added — to test.

## Home Channel

You can designate a "home channel" where the bot sends proactive messages (such as cron job output, reminders, and notifications):

### Using the Slash Command

Type `/sethome` in any Rocket.Chat room where the bot is present. That room becomes the home channel.

### Manual Configuration

Add this to your `~/.hermes/.env`:

```bash
ROCKETCHAT_HOME_CHANNEL=kLmNoPqRsTuVwXyZ1
```

Replace the ID with the actual room ID.

## Reply Mode

The `ROCKETCHAT_REPLY_MODE` setting controls how Hermes posts responses:

| Mode | Behavior |
|------|----------|
| `off` (default) | Hermes posts flat messages in the room, like a normal user. |
| `thread` | Hermes replies in a thread (via `tmid`) under your original message. Keeps rooms clean when there's lots of back-and-forth. |

Set it in your `~/.hermes/.env`:

```bash
ROCKETCHAT_REPLY_MODE=thread
```

## Mention Behavior

By default, the bot only responds in channels/groups when `@mentioned`. You can change this:

| Variable | Default | Description |
|----------|---------|-------------|
| `ROCKETCHAT_REQUIRE_MENTION` | `true` | Set to `false` to respond to all messages in rooms (DMs always work). |
| `ROCKETCHAT_FREE_RESPONSE_CHANNELS` | _(none)_ | Comma-separated room IDs where the bot responds without `@mention`, even when require_mention is true. |

The adapter detects `@mention` via both Rocket.Chat's `mentions[]` array (the authoritative source) and a text-scan fallback (which covers manual edits where the server hasn't resolved the mention yet). When the bot is `@mentioned`, the mention is automatically stripped from the message before processing.

## Troubleshooting

### Bot is not responding to messages

**Cause**: The bot is not a member of the room, or `ROCKETCHAT_ALLOWED_USERS` doesn't include your User ID.

**Fix**: Add the bot to the room (channel name → Members → Add → search for the bot). Verify your User ID is in `ROCKETCHAT_ALLOWED_USERS`. Restart the gateway.

### `totp-required` on startup

**Cause**: The PAT was created without the "Ignore Two Factor Authentication" checkbox on a workspace that enforces 2FA.

**Fix**: Regenerate the PAT in Account → Personal Access Tokens, this time with the checkbox ticked. Update `ROCKETCHAT_TOKEN` and restart.

### WebSocket / DDP disconnects

**Cause**: Rocket.Chat's DDP subscriptions do not resume across reconnects — the adapter handles this automatically. If you're seeing constant drops, check the server load or reverse-proxy timeouts.

**Fix**: The adapter reconnects with exponential backoff (2s → 60s) and re-subscribes to `stream-room-messages` after each successful reconnect. For nginx in front of Rocket.Chat, ensure your config allows long-lived WebSockets:

```nginx
location /websocket {
    proxy_pass http://rocketchat-backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 600s;
}
```

### MongoDB warning: Realtime feels laggy

**Cause**: Rocket.Chat's Realtime API requires MongoDB's oplog tailing, which is only available on a replica set.

**Fix**: Even a single-node replica set works — run `rs.initiate()` inside the mongo container once. Standalone Mongo silently falls back to polling and makes stream events drop under load.

### "Failed to authenticate" on startup

**Cause**: One of `ROCKETCHAT_TOKEN`, `ROCKETCHAT_USER_ID`, or `ROCKETCHAT_URL` is wrong.

**Fix**: Verify with curl:

```bash
curl -H "X-Auth-Token: YOUR_TOKEN" -H "X-User-Id: YOUR_BOT_USER_ID" \
  https://your-server/api/v1/me
```

If this returns your bot's user info, the credentials are valid. If it returns `"status":"error"`, regenerate the PAT.

### Bot sees system messages ("X joined", "Y left")

The adapter filters any message with a non-empty `t` field (Rocket.Chat system message types: `uj`, `ul`, `au`, `ru`, `wm`, etc.), so these never reach the agent. If you're seeing the bot respond to join/leave events, please file a bug — include the offending message's `t` value from your server logs.

### Rate-limited (HTTP 429)

**Cause**: Rocket.Chat's default REST rate limit is 10 requests per 60 seconds per endpoint per connection. Bots that chunk long messages can trip it.

**Fix**: In **Admin** → **Rate Limiter**, relax the limits for your deployment or whitelist the bot's IP. DDP method limits are separate and some are hard-coded — the adapter respects `x-ratelimit-remaining` / `x-ratelimit-reset` headers and backs off automatically.

## Per-Channel Prompts

Assign ephemeral system prompts to specific Rocket.Chat rooms. The prompt is injected at runtime on every turn — never persisted to transcript history — so changes take effect immediately.

```yaml
rocketchat:
  channel_prompts:
    "roomId_abc123": |
      You are a research assistant. Focus on academic sources,
      citations, and concise synthesis.
    "roomId_def456": |
      Code review mode. Be precise about edge cases and
      performance implications.
```

Keys are Rocket.Chat room IDs. All messages in the matching room get the prompt injected as an ephemeral system instruction.

## Security

:::warning
Always set `ROCKETCHAT_ALLOWED_USERS` to restrict who can interact with the bot. Without it, the gateway denies all users by default as a safety measure. Only add User IDs of people you trust — authorized users have full access to the agent's capabilities, including tool use and system access.
:::

For more information on securing your Hermes Agent deployment, see the [Security Guide](../security.md).

## Notes

- **Self-hosted friendly**: Works with any self-hosted Rocket.Chat instance (tested against 7.x and 8.x). No Rocket.Chat Cloud account required.
- **No extra dependencies**: The adapter uses `aiohttp` for REST and DDP WebSocket — already included with Hermes Agent.
- **Community and Enterprise**: Works with both Community and Enterprise editions.
- **Mongo replica set**: Production deployments should run MongoDB as a replica set (even single-node) so the Realtime API is reliable.
