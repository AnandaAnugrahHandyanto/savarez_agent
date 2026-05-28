# Telegram Bot API Tester

A small local React UI for testing a Telegram **Bot API** token.

## What it does

- Stores the bot token in `sessionStorage` only.
- Uses a tiny local Express proxy so the browser never calls Telegram directly.
- Pulls chats/groups/channels from `getUpdates` and caches update data in `localStorage`, keyed by a hash of the token.
- Refreshes only new updates when possible.
- Lets you inspect cached messages per chat.
- Includes testing buttons for:
  - `getMe`
  - `getWebhookInfo`
  - `getChat`
  - `getChatAdministrators`
  - `sendMessage` test message

## Run

```bash
cd /home/clawd/.hermes/hermes-agent/telegram-bot-client
npm install
npm start
```

Open: <http://localhost:5173>

## Bot API limitation

Telegram Bot API cannot list every chat or fetch arbitrary history. It can only show chats/messages that appear in updates the bot receives. To test full user-account Telegram behavior, use MTProto/GramJS/Telethon with API ID/API hash and a login flow instead.
