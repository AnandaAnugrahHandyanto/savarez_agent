---
sidebar_position: 3
title: "Run Hermes on boxd"
description: "Deploy Hermes Agent on a boxd cloud VM in under five minutes — persistent, auto-suspending, and reachable from any messaging platform"
---

# Run Hermes on boxd

This guide walks you through running Hermes Agent on a [boxd](https://boxd.sh) cloud VM. By the end you'll have a persistent agent you can SSH into from your laptop, message from Telegram or Discord, or expose over HTTPS for webhooks — without paying for compute when nobody's using it.

## Why boxd

Hermes is built to live somewhere other than your laptop. boxd is built for that "somewhere":

- **Per-VM public IPv4** with a real subdomain on `*.boxd.sh`. Webhook-driven platforms (Discord, Slack, WhatsApp, Mattermost) just work.
- **Auto-suspend.** The VM warm-pauses after N idle seconds and wakes in sub-millisecond on the next request. You pay near-zero when the agent is idle, which is most of the time.
- **SSH-key auth.** No password. Your existing `~/.ssh` key authenticates everything — `boxd connect`, `boxd exec`, file copy.
- **Persistent disk.** Unlike serverless backends, the VM keeps `~/.hermes/` between sessions — sessions, memory, skills, and config survive across restarts.
- **Fixed shape (2 vCPU, 8 GiB RAM, 100 GB disk)** — comfortably above what Hermes needs and the LLM calls happen remotely anyway.

If you want fully serverless instead, look at the Modal and Daytona [terminal backends](../user-guide/configuration.md#terminal-backend-configuration). boxd is the right pick when you want a real, addressable Linux box that survives between conversations.

---

## Prerequisites

Before starting, make sure you have:

- **A boxd account.** Sign up at [boxd.sh](https://boxd.sh) — uses your existing GitHub SSH key.
- **An LLM provider key** — at minimum OpenRouter, OpenAI, Anthropic, or Nous Portal. We use OpenRouter in the examples below.
- **Local SSH key** registered with GitHub (boxd reads your GitHub keys at signup).

---

## Step 1: Install the boxd CLI

On your laptop:

```bash
curl -fsSL https://boxd.sh/downloads/install.sh | sh
boxd login
```

`boxd login` opens your browser, you approve, and the CLI stores credentials in `~/.config/boxd/`. Verify:

```bash
boxd whoami
```

---

## Step 2: Create a VM

```bash
boxd new --name hermes
```

This creates a fresh Linux VM, prints the SSH command, and gives it a public IP plus a default `<vm-name>.<user>.boxd.sh` HTTPS subdomain.

By default the VM auto-suspends after 5 minutes of network idle. If you want the gateway to stay up indefinitely, disable auto-suspend up front:

```bash
boxd auto-suspend hermes 0
```

You can re-enable it later with `boxd auto-suspend hermes 300` (5 minutes), or any value `>= 5` seconds.

:::tip
Keep auto-suspend on for CLI / SSH-only use — every connection wakes the VM in under a millisecond. Only disable it if you're running the [messaging gateway](#step-5-optional-add-a-messaging-gateway) and need to receive incoming pushes 24/7.
:::

---

## Step 3: Install Hermes inside the VM

SSH in and run the official installer:

```bash
boxd connect hermes
```

Inside the VM:

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
source ~/.bashrc
```

The installer handles Python, uv, Node, ripgrep, ffmpeg, and the venv. See the [installation guide](../getting-started/installation.md) for what it does under the hood.

---

## Step 4: Configure your provider key

Still inside the VM:

```bash
hermes config set OPENROUTER_API_KEY sk-or-v1-...
hermes model
```

`hermes model` walks you through provider + model selection. Then verify everything works:

```bash
hermes doctor
hermes -q "Hello from boxd"
```

That's the minimum viable install. You can stop here if you only want to SSH in and chat.

---

## Step 5 (optional): Add a messaging gateway

This is where boxd's HTTPS subdomain pays off. Pick a platform and follow its setup, then start the gateway:

```bash
hermes gateway setup     # interactive — Telegram, Discord, Slack, WhatsApp, ...
hermes gateway start
```

For [Telegram](../user-guide/messaging/telegram.md) you don't need anything else — it long-polls. For platforms that push webhooks, expose a port through boxd's proxy:

```bash
# from your laptop, not inside the VM
boxd proxy new hermes-webhook --vm hermes --port 8080
```

You'll get back something like `https://hermes-webhook.<you>.boxd.sh` — give that URL to Discord / Slack / Mattermost as your webhook target. TLS is terminated for you; no certbot, no reverse proxy.

For the full team-bot walkthrough (per-user authorization, scheduled messages, etc.), see the [Team Telegram Assistant tutorial](./team-telegram-assistant.md).

---

## Step 6 (optional): Run scheduled tasks

Hermes' [cron scheduler](../user-guide/features/cron.md) is the killer combo with boxd's auto-suspend: the VM wakes when cron fires, runs the job, delivers the result to your messaging platform, and goes back to sleep.

Inside the VM:

```bash
hermes cron create "every 1d at 08:00" \
  "Summarize today's calendar and unread emails, send to Telegram" \
  --name "morning-briefing"
```

Make sure auto-suspend is either disabled or large enough that the cron daemon can fire — boxd's auto-suspend is network-idle-based, so an in-VM cron tick keeps it awake long enough to run.

---

## Updating Hermes

```bash
boxd exec hermes -- hermes update
```

`hermes update` pulls the latest release in-place. No need to rebuild the VM.

---

## Stopping and resuming

The VM runs until you destroy it. To free compute without losing state:

```bash
boxd pause hermes        # warm suspend, sub-ms resume
boxd resume hermes       # wake it back up
```

Or just let auto-suspend handle it. To get rid of the VM entirely:

```bash
boxd destroy hermes
```

The name is reserved for re-creation if you want it back later.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `boxd connect` hangs | Check `boxd list` — if the VM is paused, any TCP connect wakes it but takes a moment. Try again. |
| Telegram bot stops responding overnight | Auto-suspend is paused outbound long-poll connections. Run `boxd auto-suspend hermes 0`. |
| Webhook returns 502 | Confirm the gateway is listening on the port you forwarded: `boxd exec hermes -- ss -ltnp \| grep 8080`. |
| `hermes: command not found` after install | Reload the shell — `source ~/.bashrc` — or open a fresh `boxd connect` session. |

For deeper diagnostics, run `hermes doctor` inside the VM. For boxd-side issues, `boxd info hermes` shows VM state, IP, and last activity.

---

## Where to go next

- **[Configuration reference](../user-guide/configuration.md)** — every config knob
- **[Messaging Gateway overview](../user-guide/messaging/index.md)** — set up additional platforms on the same VM
- **[Cron scheduling](../user-guide/features/cron.md)** — daily reports, nightly backups, weekly audits
- **[Skills](../user-guide/features/skills.md)** — extend Hermes with your own procedural memory
