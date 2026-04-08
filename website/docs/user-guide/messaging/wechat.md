---
sidebar_position: 11
title: "WeChat"
description: "Set up Hermes Agent as a WeChat bot via the iLink Bot API"
---

# WeChat Setup

Hermes Agent can connect to WeChat (personal) through the iLink Bot API. The WeChat adapter runs as part of the normal Hermes gateway process: it long-polls for new direct messages, downloads and decrypts CDN media, and sends replies back through the same API using the required `context_token` from the inbound message.

This integration is best for 1:1 bot conversations on WeChat where you want Hermes available from a phone-friendly messaging client with native support for images, videos, files, and typing indicators.

:::note
This is the **personal WeChat** adapter (via iLink Bot). For **Enterprise WeChat (WeCom/Qiwei)**, see the [WeCom](./wecom.md) adapter.
:::

## Overview

The WeChat integration provides:

- Plain-text chat replies with automatic markdown stripping
- Native image, video, and file delivery via CDN with AES-128-ECB encryption
- Inbound voice handling with SILK transcoding and speech-to-text fallback
- Referenced message (quote) context extraction
- Typing indicators via `getconfig` + `sendtyping`
- Context token persistence across gateway restarts
- Session resume from saved `get_updates_buf`
- iLink 2.1.x protocol compliance (App-Id, ClientVersion headers, IDC redirect)

## Prerequisites

Install the required Python packages:

```bash
pip install httpx cryptography
```

Optional:

```bash
pip install qrcode        # Render QR code in terminal during login
pip install silk-python    # Transcode SILK voice messages to WAV
```

## Setup

### Option A: QR Login Script

Run the login helper:

```bash
python3 scripts/wechat_login.py
```

The script will:

1. Request a QR code from the iLink Bot API
2. Render the QR code in your terminal (if `qrcode` is installed)
3. Handle IDC redirects if your WeChat account is on a different datacenter
4. Auto-refresh expired QR codes (up to 3 times)
5. Save credentials to `~/.hermes/wechat/accounts/`
6. Print the environment variables to add to `~/.hermes/.env`

### Option B: Hermes Gateway Setup Wizard

```bash
hermes gateway setup
```

Choose **WeChat** and paste the token and account ID returned by the QR login step.

### Manual Configuration

Add the required settings to `~/.hermes/.env`:

```bash
WECHAT_BOT_TOKEN=your-bot-token
WECHAT_ACCOUNT_ID=your-ilink-bot-id

# Optional overrides
# WECHAT_API_BASE_URL=https://ilinkai.weixin.qq.com
# WECHAT_CDN_BASE_URL=https://novac2c.cdn.weixin.qq.com/c2c

# iLink protocol headers (defaults are usually fine)
# WECHAT_ILINK_APP_ID=bot
# WECHAT_ILINK_CLIENT_VERSION=512

# Security
# WECHAT_ALLOWED_USERS=user-id-1,user-id-2
# WECHAT_ALLOW_ALL_USERS=true

# Optional home channel for cron / send_message
# WECHAT_HOME_CHANNEL=user-id-1
```

Start the gateway:

```bash
hermes gateway
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WECHAT_BOT_TOKEN` | Yes | — | Bot token from QR login |
| `WECHAT_ACCOUNT_ID` | Yes | — | iLink bot account ID from QR login |
| `WECHAT_API_BASE_URL` | No | `https://ilinkai.weixin.qq.com` | Override the API base URL |
| `WECHAT_CDN_BASE_URL` | No | `https://novac2c.cdn.weixin.qq.com/c2c` | Override the CDN base URL |
| `WECHAT_ILINK_APP_ID` | No | `bot` | iLink application identifier (SDK 2.1.1+) |
| `WECHAT_ILINK_CLIENT_VERSION` | No | Auto-computed | iLink client version as uint32 (SDK 2.1.1+) |
| `WECHAT_ALLOWED_USERS` | No | — | Comma-separated user IDs allowed to message the bot |
| `WECHAT_ALLOW_ALL_USERS` | No | `false` | Allow all users without an allowlist |
| `WECHAT_HOME_CHANNEL` | No | — | Default user/chat ID for cron delivery and `send_message` |
| `WECHAT_HOME_CHANNEL_NAME` | No | `Home` | Display name for the home channel |

## Supported Features

| Feature | Status | Notes |
|---------|--------|-------|
| Text replies | Supported | Markdown auto-stripped for WeChat compatibility |
| Image send/receive | Supported | AES-128-ECB encrypted via CDN |
| File attachments | Supported | PDF, DOC, ZIP, etc. |
| Video send/receive | Supported | MP4 via CDN |
| Voice messages | Supported | SILK transcoding with fallback to file attachment |
| Referenced messages | Supported | Quoted reply context extracted as `[Quote: ...]` |
| Typing indicators | Supported | Via `getconfig` + `sendtyping` |
| Context token persistence | Supported | Survives gateway restarts |
| Session resume | Supported | Picks up from saved `get_updates_buf` |
| IDC redirect | Supported | Login handles `scaned_but_redirect` (SDK 2.1.1+) |

## Architecture

The WeChat adapter uses a 3-file architecture:

| File | Purpose |
|------|---------|
| `wechat.py` | Adapter lifecycle, message routing, platform API |
| `wechat_transport.py` | HTTP layer, CDN upload/download, AES crypto, iLink headers |
| `wechat_state.py` | Context token and sync buffer persistence |

## Known Limitations

- **No streaming**: WeChat does not support message editing. Streaming mode sends raw `MEDIA:` tags as text. Disable streaming for WeChat or accept text-only output.
- **Audio delivery**: Outbound audio is sent as a file attachment, not a native voice bubble. Bot-originated voice playback is not reliably supported by the WeChat client. This matches the official SDK behavior.
- **Context token required**: Outbound replies require a valid `context_token`. A user must message the bot first before Hermes can reply or proactively send.
- **DM only**: The adapter targets direct-message conversations. Group chat is not supported.
- **Session expiry**: If WeChat returns `errcode -14`, the adapter pauses for one hour and clears context tokens. Users need to re-message after the pause.
- **Markdown**: WeChat does not render markdown. The adapter strips all markdown formatting before delivery.

## Troubleshooting

### "No token configured"

The gateway cannot see `WECHAT_BOT_TOKEN`.

- Run `python3 scripts/wechat_login.py` again
- Add the printed token to `~/.hermes/.env`
- Restart the gateway

### Bot connects but cannot reply

Outbound sends require a fresh `context_token`.

- Send the bot a new message from WeChat first
- The token persists across restarts, so this is usually a one-time issue per user

### Media upload fails

Common causes:

- `cryptography` is missing — run `pip install cryptography`
- File exceeds the 100 MB limit
- CDN returned no `x-encrypted-param` header — check gateway logs

The adapter retries CDN uploads up to 3 times with exponential backoff. If uploads consistently fail, check your network connectivity to the WeChat CDN.

### Voice messages not transcribed

- Install `silk-python` or ensure `ffmpeg` is available for SILK→WAV transcoding
- If neither is available, voice is stored as raw SILK and WeChat's built-in STT text is used when present

### IDC redirect during login

If your WeChat account is registered in a different datacenter region, the login script handles this automatically via `scaned_but_redirect`. If login hangs, check the script output for redirect messages and ensure the redirect host is reachable.

### Session pauses for one hour

WeChat returned session-expiry `errcode -14`. Context tokens are cleared.

- Wait for the 1-hour cooldown, or
- Re-run `python3 scripts/wechat_login.py` to get a fresh token
