---
sidebar_position: 20
title: "Google Chat"
description: "Set up Hermes Agent as a Google Chat bot"
---

# Google Chat Setup

Hermes Agent integrates with Google Chat via Cloud Pub/Sub for inbound events and the Chat REST API for outbound messages. No additional relay server is needed — the adapter subscribes directly to a Pub/Sub subscription where Google Chat publishes native events, and replies via the Chat API with service-account credentials.

This setup requires a **Business or Enterprise** [Google Workspace](https://workspace.google.com/) account with access to [Google Chat](https://workspace.google.com/products/chat/).

**Dependencies** (not bundled with Hermes):

```bash
pip install google-cloud-pubsub google-auth google-api-python-client
```

## How Hermes Behaves

| Context | Behavior |
|---------|----------|
| **DMs** | Hermes responds to every message. No `@mention` needed. |
| **Spaces** | Hermes responds when you `@mention` it. Without a mention, Hermes ignores the message. |
| **Threads** | Thread context is preserved — replies in a thread stay in that thread's session. |

## Prerequisites

Before setting up Hermes, you need:

1. A **Google Cloud project** with billing enabled
2. The **Google Chat API** and **Cloud Pub/Sub API** enabled on that project
3. A **service account** with a downloaded JSON key
4. A **Pub/Sub topic and pull subscription** for inbound events

## Step 1: Create a Google Chat App

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Select or create a project.
3. Navigate to **APIs & Services** → **Enable APIs and Services**.
4. Search for and enable both:
   - **Google Chat API**
   - **Cloud Pub/Sub API**
5. In the Chat API settings, click **Configuration**:
   - Ensure **"Build this Chat app as a Google Workspace add-on"** is **unchecked**
   - **App name**: e.g., `Hermes Agent`
   - **Avatar URL**: optional
   - **Description**: optional
   - **Functionality**: select **Join spaces and group conversations**
   - **Connection settings**: select **Cloud Pub/Sub** and enter the topic name you'll create in Step 3
   - **Visibility**: select **Make this Google Chat app available to specific people and groups in your domain** and enter your email address
   - **Logs**: optionally select **Log errors to Logging**

## Step 2: Create a Service Account

1. In the Cloud Console, go to **IAM & Admin** → **Service Accounts**.
2. Click **Create Service Account**.
3. Give it a name (e.g., `hermes-chat-bot`).
4. Click **Done** — no special Chat-specific IAM role is needed. The adapter authenticates with the Chat API using the [`chat.bot` OAuth scope](https://developers.google.com/workspace/chat/authenticate-authorize-chat-app), which is self-granted at runtime.
5. Open the service account, go to **Keys** → **Add Key** → **Create new key** → **JSON**.
6. Download the JSON key file and store it securely.

:::warning[Service Account Key Security]
The JSON key file grants full access to the Chat bot. Never commit it to Git or share it publicly. Store it in a secure location and reference it via `GOOGLE_CHAT_CREDENTIALS`.
:::

## Step 3: Set Up Pub/Sub

1. Go to **Pub/Sub** in the Cloud Console.
2. Create a **topic** (e.g., `hermes-chat-inbound`).
3. Grant the Chat API's internal service account (`chat-api-push@system.gserviceaccount.com`) the **Pub/Sub Publisher** role on this topic. This allows Google Chat to publish events to your topic.
4. Create a **pull subscription** on the topic (e.g., `hermes-chat-inbound-sub`):
   - Delivery type: **Pull** (not Push)
   - Acknowledgment deadline: 60 seconds recommended
5. Grant your service account (from Step 2) the **Pub/Sub Subscriber** role on the subscription. This allows the Hermes adapter to pull events.

:::info
The Google Chat API publishes events to your Pub/Sub topic automatically once configured. Your Hermes adapter pulls from the subscription — no webhook endpoint or public URL needed.
:::

## Step 4: Configure Hermes Agent

### Option A: Interactive Setup (Recommended)

```bash
hermes gateway setup
```

Select **Google Chat** when prompted, then enter your GCP project ID, subscription name, and credentials path.

### Option B: Manual Configuration

Add the following to your `~/.hermes/.env` file:

```bash
# Required
GOOGLE_CHAT_GCP_PROJECT=your-gcp-project-id
GOOGLE_CHAT_PUBSUB_SUBSCRIPTION=hermes-chat-inbound-sub

# Service account credentials (leave empty for Application Default Credentials)
GOOGLE_CHAT_CREDENTIALS=/path/to/service-account-key.json

# Access control
GOOGLE_CHAT_ALLOWED_USERS=alice@example.com,bob@example.com

# Bypass allowlist entirely (NOT recommended — use with caution)
# GOOGLE_CHAT_ALLOW_ALL_USERS=true

# Optional: home space for cron delivery
# GOOGLE_CHAT_HOME_CHANNEL=spaces/AAAAxxxxxxxx
```

### Start the Gateway

```bash
hermes gateway
```

The adapter connects to Pub/Sub and begins listening for events. Send a message to the bot in Google Chat to test.

## Home Channel

Designate a space for proactive messages (cron jobs, reminders, notifications):

### Using the Slash Command

Type `/sethome` in any Google Chat space where the bot is present.

### Manual Configuration

```bash
GOOGLE_CHAT_HOME_CHANNEL=spaces/AAAAxxxxxxxx
```

To find the space name: open the space in Google Chat, look at the URL — it contains the space ID (e.g., `spaces/AAAABBBBcccc`).

## Authentication

The adapter supports two authentication methods:

| Method | When to use |
|--------|-------------|
| **Service Account JSON** | Local development, self-hosted deployments. Set `GOOGLE_CHAT_CREDENTIALS` to the key file path. |
| **Application Default Credentials (ADC)** | Cloud Run, GCE, or environments with `gcloud auth application-default login`. Leave `GOOGLE_CHAT_CREDENTIALS` empty. |

The adapter uses two OAuth scopes at runtime — no IAM roles are needed for these:

- `https://www.googleapis.com/auth/chat.bot` — lets the app send and receive messages (self-granted, no admin approval required)
- `https://www.googleapis.com/auth/pubsub` — lets the app pull events from the subscription

## Troubleshooting

### Bot is not responding

**Cause**: Pub/Sub subscription is not receiving events, or the Chat app configuration is incorrect.

**Fix**:

1. Verify the Chat API is enabled and the app is configured with the correct Pub/Sub topic.
2. Check that the `chat-api-push@system.gserviceaccount.com` service account has Publisher access to your topic.
3. Verify `GOOGLE_CHAT_GCP_PROJECT` and `GOOGLE_CHAT_PUBSUB_SUBSCRIPTION` match your setup.
4. Check `hermes gateway` output for error messages.

### "Permission denied" errors

**Cause**: Missing IAM roles or OAuth scope issues.

**Fix**: Ensure:

- Your service account has the **Pub/Sub Subscriber** role on the subscription (for pulling events)
- The `chat-api-push@system.gserviceaccount.com` account has the **Pub/Sub Publisher** role on the topic (for Google Chat to publish events)
- The Chat API is enabled and the Chat app is configured in the same GCP project as the service account
- The `chat.bot` OAuth scope handles message sending automatically — no Chat-specific IAM role is needed

### "User not allowed" / Bot ignores you

**Cause**: Your email isn't in `GOOGLE_CHAT_ALLOWED_USERS`.

**Fix**: Add your Google Workspace email to `GOOGLE_CHAT_ALLOWED_USERS` in `~/.hermes/.env` and restart the gateway.

### Messages are delayed

**Cause**: Pub/Sub acknowledgment timeout or flow control limits.

**Fix**: The adapter uses streaming pull with a default of 10 outstanding messages. For high-traffic spaces, this is usually sufficient. If messages are consistently delayed, check your Pub/Sub subscription's acknowledgment deadline (60s recommended).

## Security

:::warning
Always set `GOOGLE_CHAT_ALLOWED_USERS` to restrict who can interact with the bot. Without it, the gateway denies all users by default. Only add email addresses of people you trust — authorized users have full access to the agent's capabilities.
:::

## Notes

- **No public endpoint needed**: Unlike webhook-based integrations, the Pub/Sub pull model doesn't require a public URL or port forwarding.
- **Cloud Run friendly**: When deployed on Cloud Run with ADC, no credentials file is needed.
- **Message limit**: Google Chat messages are limited to 4,096 characters. Longer responses are automatically split into multiple messages.
- **Typing indicators**: Google Chat API does not support typing indicators for Chat apps, so this is a no-op.
