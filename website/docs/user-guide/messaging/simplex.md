# SimpleX Chat

[SimpleX Chat](https://simplex.chat/) is a private, decentralised messaging platform where users own their contacts and groups. Unlike other platforms, SimpleX assigns no persistent user IDs — every contact is identified by an opaque internal ID generated at connection time, which makes it one of the most private messengers available.

## Prerequisites

- The **simplex-chat** CLI installed and running as a daemon
- Python package **websockets** (`pip install websockets`)

## Install simplex-chat

Download the latest release from the [simplex-chat GitHub releases](https://github.com/simplex-chat/simplex-chat/releases) page, or via Docker:

```bash
# Linux / macOS binary
curl -L https://github.com/simplex-chat/simplex-chat/releases/latest/download/simplex-chat-ubuntu-22_04-x86-64 -o simplex-chat
chmod +x simplex-chat

# Or Docker
docker run -p 5225:5225 simplexchat/simplex-chat -p 5225
```

## Start the daemon

```bash
simplex-chat -p 5225
```

The daemon listens on WebSocket at `ws://127.0.0.1:5225` by default.

## Configure Hermes

### Via setup wizard

```bash
hermes setup gateway
```

Select **SimpleX Chat** and follow the prompts.

### Via environment variables

Add these to `~/.hermes/.env`:

```
SIMPLEX_WS_URL=ws://127.0.0.1:5225
SIMPLEX_ALLOWED_USERS=<contact-id-1>,<contact-id-2>
SIMPLEX_HOME_CHANNEL=<contact-display-name-or-group-display-name>
```

| Variable | Required | Description |
|---|---|---|
| `SIMPLEX_WS_URL` | Yes | WebSocket URL of the simplex-chat daemon |
| `SIMPLEX_ALLOWED_USERS` | Recommended | Comma-separated contact IDs allowed to use the agent |
| `SIMPLEX_ALLOW_ALL_USERS` | Optional | Set `true` to allow every contact (use carefully) |
| `SIMPLEX_HOME_CHANNEL` | Optional | Default DM display name or `group:<group-display-name>` for cron job delivery |
| `SIMPLEX_HOME_CHANNEL_NAME` | Optional | Human label for the home channel |

## Find your contact ID and delivery target

After starting the daemon, open a conversation with your agent contact and run:

```bash
simplex-chat -e '/info <display-name>' -t 2 --execute-log messages
```

Use the numeric `contact ID` in `SIMPLEX_ALLOWED_USERS` for authorization.
For outbound delivery, SimpleX's text command interface sends DMs to local
display names (for example `@alice hi`), so use the contact's local display
name for `SIMPLEX_HOME_CHANNEL` and `send_message` targets such as
`simplex:alice`. Use `simplex:group:<group-display-name>` for group delivery.

The SimpleX adapter receives live `newChatItem` events over the daemon
WebSocket. If the socket reconnects while Hermes is still running, it does a
one-time `/chats` + targeted `/tail @contact` catch-up over the same persistent
socket to recover items that arrived during the connection gap. On fresh
startup it primes recent history without replaying it, so old messages do not
trigger duplicate bot replies.

## Authorization

By default **all contacts are denied**. You must either:

1. Set `SIMPLEX_ALLOWED_USERS` to a comma-separated list of contact IDs, or
2. Use **DM pairing** — send any message to the bot and it will reply with a pairing code. Enter that code via `hermes pairing approve <code>`.

## Using SimpleX with cron jobs

```python
cronjob(
    action="create",
    schedule="every 1h",
    deliver="simplex",          # uses SIMPLEX_HOME_CHANNEL
    prompt="Check for alerts and summarise."
)
```

Or target a specific contact:

```python
send_message(target="simplex:<contact-display-name>", message="Done!")
```

## Privacy notes

- SimpleX never reveals phone numbers or email addresses — contacts use opaque IDs
- The connection between Hermes and the daemon is local WebSocket (`ws://127.0.0.1:5225`) — no data leaves your machine
- Messages are end-to-end encrypted by the SimpleX protocol before reaching the daemon

## Troubleshooting

**"Cannot reach daemon"** — Ensure `simplex-chat -p 5225` is running and the port matches `SIMPLEX_WS_URL`.

**"websockets not installed"** — Run `pip install websockets`.

**Messages not received** — Check that the contact's numeric ID is in `SIMPLEX_ALLOWED_USERS` or approve them via DM pairing. Also verify `simplex-chat -p 5225` is still running; Hermes receives live events over the daemon WebSocket and does one catch-up pass after an in-process reconnect.
