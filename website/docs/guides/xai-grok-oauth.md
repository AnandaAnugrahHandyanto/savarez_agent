---
sidebar_position: 16
title: "xAI Grok OAuth (SuperGrok Subscription)"
description: "Sign in with your SuperGrok subscription to use Grok models in Hermes Agent — no API key required"
---

# xAI Grok OAuth (SuperGrok Subscription)

Hermes Agent supports xAI Grok through a browser-based OAuth login flow against [accounts.x.ai](https://accounts.x.ai), using your existing **SuperGrok subscription**. No `XAI_API_KEY` is required — log in once and Hermes automatically refreshes your session in the background.

The transport reuses the `codex_responses` adapter (xAI exposes a Responses-style endpoint), so reasoning, tool-calling, streaming, and prompt caching work without any adapter changes.

The same OAuth bearer token is also reused by every direct-to-xAI surface in Hermes — TTS, image generation, video generation, and transcription — so a single login covers all four.

## Overview

| Item | Value |
|------|-------|
| Provider ID | `xai-oauth` |
| Display name | xAI Grok OAuth (SuperGrok Subscription) |
| Auth type | Browser OAuth 2.0 PKCE (loopback callback, with manual-code fallback for remote sessions) |
| Transport | xAI Responses API (`codex_responses`) |
| Default model | `grok-4.3` |
| Endpoint | `https://api.x.ai/v1` |
| Auth server | `https://accounts.x.ai` |
| Requires env var | No (`XAI_API_KEY` is **not** used for this provider) |
| Subscription | [SuperGrok](https://x.ai/grok) (any active tier) |

## Prerequisites

- Python 3.9+
- Hermes Agent installed
- An active SuperGrok subscription on your xAI account
- A browser on either the Hermes machine or another device
- For phone/Discord/SSH/headless setup, use `--manual-code` so Hermes prompts you to paste the xAI redirect URL instead of waiting on a local callback

## Quick Start

```bash
# Launch the provider and model picker
hermes model
# → Select "xAI Grok OAuth (SuperGrok Subscription)" from the provider list
# → Hermes opens your browser to accounts.x.ai
# → Approve access in the browser
# → Pick a model (grok-4.3 is at the top)
# → Start chatting

hermes
```

After the first login, credentials are stored under `~/.hermes/auth.json` and refreshed automatically before they expire.

## Logging In Manually

You can trigger a login without going through the model picker:

```bash
hermes auth add xai-oauth
```

### Remote / phone / headless sessions

If Hermes is running somewhere other than the browser device — SSH, a container, WSL driven from Discord, or a phone-only setup — use the manual-code fallback:

```bash
hermes auth add xai-oauth --manual-code
# or, through the provider picker:
# hermes model --manual-code
```

Hermes prints the xAI authorize URL. Open it in any browser, approve access, then xAI redirects to `http://127.0.0.1:56121/callback`. On a different device that page may fail to load; that is expected. Copy the full failed redirect URL from the browser address bar and paste it back into Hermes. Hermes validates the OAuth `state` when the full URL is pasted, exchanges the one-time code with the same PKCE verifier and redirect URI, and stores the tokens normally.

If your browser only lets you copy the one-time `code`, you can paste just the code, but the full redirect URL is preferred because it includes `state`.

### SSH tunnel alternative

You can still use the traditional loopback callback flow with an SSH local-forward. This is useful if you want a fully automatic callback or if you are authenticating a provider that does not support manual paste mode.

```bash
# In a separate terminal on your local machine:
ssh -N -L 56121:127.0.0.1:56121 user@remote-host

# Then in your SSH session on the remote machine:
hermes auth add xai-oauth --no-browser
# Open the printed authorize URL in your local browser.
```

Through a jump box / bastion: add `-J jump-user@jump-host`.

See [OAuth over SSH / Remote Hosts](./oauth-over-ssh.md) for the full tunnel step-by-step, including ProxyJump chains, mosh/tmux, and ControlMaster gotchas.

## How the Login Works

1. Hermes opens your browser to `accounts.x.ai`.
2. You sign in (or confirm your existing session) and approve access.
3. xAI redirects back to Hermes and the tokens are saved to `~/.hermes/auth.json`.
4. From then on, Hermes refreshes the access token in the background — you stay signed in until you `hermes auth remove xai-oauth` or revoke access from your xAI account settings.

## Checking Login Status

```bash
hermes doctor
```

The `◆ Auth Providers` section will show the current state of every provider, including `xai-oauth`.

## Switching Models

```bash
hermes model
# → Select "xAI Grok OAuth (SuperGrok Subscription)"
# → Pick from the model list (grok-4.3 is pinned to the top)
```

Or set the model directly:

```bash
hermes config set model.default grok-4.3
hermes config set model.provider xai-oauth
```

## Configuration Reference

After login, `~/.hermes/config.yaml` will contain:

```yaml
model:
  default: grok-4.3
  provider: xai-oauth
  base_url: https://api.x.ai/v1
```

### Provider aliases

All of the following resolve to `xai-oauth`:

```bash
hermes --provider xai-oauth        # canonical
hermes --provider grok-oauth       # alias
hermes --provider x-ai-oauth       # alias
hermes --provider xai-grok-oauth   # alias
```

## Direct-to-xAI Tools (TTS / Image / Video / Transcription / X Search)

Once you're logged in via OAuth, every direct-to-xAI tool reuses the same bearer token automatically — there is **no separate setup** unless you'd rather use an API key.

To pick a backend for each tool:

```bash
hermes tools
# → Text-to-Speech       → "xAI TTS"
# → Image Generation     → "xAI Grok Imagine (image)"
# → Video Generation     → "xAI Grok Imagine"
# → X (Twitter) Search   → "xAI Grok OAuth (SuperGrok Subscription)"
```

If OAuth tokens are already stored, the picker confirms it and skips the credential prompt. If neither OAuth nor `XAI_API_KEY` is set, the picker offers a 3-choice menu: OAuth login, paste API key, or skip.

:::note Video generation is off by default
The `video_gen` toolset is disabled by default. Enable it in `hermes tools` → `🎬 Video Generation` (press space) before the agent can call `video_generate`. Otherwise the agent may fall back to the bundled ComfyUI skill, which is also tagged for video generation.
:::

:::note X search is off by default
The `x_search` toolset is disabled by default. Enable it in `hermes tools` → `🐦 X (Twitter) Search` (press space) before the agent can call `x_search`. The tool routes through xAI's built-in `x_search` Responses API — it works with **either** your SuperGrok OAuth login or a paid `XAI_API_KEY`, and prefers OAuth when both are configured (uses your subscription quota instead of API spend). The tool schema is hidden from the model when no xAI credentials are configured, regardless of whether the toolset is enabled.
:::

### Models

| Tool | Model | Notes |
|------|-------|-------|
| Chat | `grok-4.3` | Default; auto-selected when you log in via OAuth |
| Chat | `grok-4.20-0309-reasoning` | Reasoning variant |
| Chat | `grok-4.20-0309-non-reasoning` | Non-reasoning variant |
| Chat | `grok-4.20-multi-agent-0309` | Multi-agent variant |
| Image | `grok-imagine-image` | Default; ~5–10 s |
| Image | `grok-imagine-image-quality` | Higher fidelity; ~10–20 s |
| Video | `grok-imagine-video` | Text-to-video and image-to-video; up to 7 reference images |
| TTS | (default voice) | xAI `/v1/tts` endpoint |

The chat catalog is derived live from the on-disk `models.dev` cache; new xAI releases appear automatically once that cache refreshes. `grok-4.3` is always pinned to the top of the list.

## Environment Variables

| Variable | Effect |
|----------|--------|
| `XAI_BASE_URL` | Override the default `https://api.x.ai/v1` endpoint (rarely needed). |
| `HERMES_INFERENCE_PROVIDER` | Force the active provider at runtime, e.g. `HERMES_INFERENCE_PROVIDER=xai-oauth hermes`. |

## Troubleshooting

### Token expired — not re-logging in automatically

Hermes refreshes the token before each session and again reactively on a 401. If refresh fails with `invalid_grant` (the refresh token was revoked, or the account was rotated), Hermes surfaces a typed re-auth message instead of crashing.

**Fix:** run `hermes auth add xai-oauth` again to start a fresh login.

### Authorization timed out

The loopback listener has a finite expiry window. If you don't approve the login in time, Hermes raises a timeout error.

**Fix:** re-run `hermes auth add xai-oauth` (or `hermes model`). If the browser is on another device, use `hermes auth add xai-oauth --manual-code` so Hermes prompts for the redirect URL/code instead of waiting for the callback listener.

### State mismatch (possible CSRF)

Hermes detected that the `state` value returned by the authorization server doesn't match what it sent.

**Fix:** re-run the login. If it persists, check for a proxy or redirect that is modifying the OAuth response.

### Logging in from a remote server or phone

Use manual-code mode when the browser is not on the Hermes machine:

```bash
hermes auth add xai-oauth --manual-code
```

Open the printed URL, approve access, then paste the full failed `127.0.0.1:56121/callback?...` redirect URL back into Hermes. The failed localhost page is expected when using a phone, Discord-driven setup, or a browser on a different computer.

If you prefer the automatic callback flow, use an SSH local-forward and run `hermes auth add xai-oauth --no-browser`; see [OAuth over SSH / Remote Hosts](./oauth-over-ssh.md).

### "No xAI credentials found" error at runtime

The auth store has no `xai-oauth` entry and no `XAI_API_KEY` is set. You haven't logged in yet, or the credential file was deleted.

**Fix:** run `hermes model` and pick the xAI Grok OAuth provider, or run `hermes auth add xai-oauth`.

## Logging Out

To remove all stored xAI Grok OAuth credentials:

```bash
hermes auth logout xai-oauth
```

This clears both the singleton OAuth entry in `auth.json` and any credential-pool rows for `xai-oauth`. Use `hermes auth remove xai-oauth <index|id|label>` if you only want to drop a single pool entry (run `hermes auth list xai-oauth` to see them).

## See Also

- [OAuth over SSH / Remote Hosts](./oauth-over-ssh.md) — SSH tunnel alternative when Hermes is on a different machine than your browser
- [AI Providers reference](../integrations/providers.md)
- [Environment Variables](../reference/environment-variables.md)
- [Configuration](../user-guide/configuration.md)
- [Voice & TTS](../user-guide/features/tts.md)
