---
name: sendit
description: Use SendIt from Hermes Agent for social publishing, scheduling, platform connection, media upload, content validation, previews, and analytics through remote MCP OAuth.
version: 0.2.0
author: SendIt / Infinite Apps AI
license: MIT
platforms: [linux, macos]
category: social-media
tags: [sendit, social-media, mcp, oauth, publishing, scheduling, analytics]
repository: https://github.com/Shree-git/sendit-hermes-skills
sourceUrl: https://github.com/Shree-git/sendit-hermes-skills/tree/main/skills/sendit
summary: SendIt gives Hermes a remote OAuth MCP workflow for connecting social accounts, validating content, uploading media, publishing or scheduling posts, and reviewing analytics.
icon: https://sendit.infiniteappsai.com/favicon.ico
metadata:
  hermes:
    category: social-media
    tags: [sendit, social-media, mcp, oauth, publishing, scheduling, analytics]
    homepage: https://sendit.infiniteappsai.com
    repository: https://github.com/Shree-git/sendit-hermes-skills
    config:
      - key: sendit.mcp_server_name
        description: Hermes MCP server name for SendIt.
        default: sendit
        prompt: SendIt MCP server name
      - key: sendit.mcp_url
        description: SendIt remote MCP endpoint.
        default: https://sendit.infiniteappsai.com/api/mcp
        prompt: SendIt MCP endpoint
---

# SendIt

SendIt is an MCP server for AI-native social media publishing. Use this skill
when the user wants Hermes to connect social accounts, publish or schedule
posts, upload media, validate platform requirements, preview content, or review
analytics through SendIt.

## When To Use

Use SendIt for:

- Publishing or scheduling social posts to connected platforms.
- Listing or connecting LinkedIn, Instagram, TikTok, Threads, X, and other
  SendIt-supported accounts.
- Validating text, media, captions, hashtags, and platform-specific limits.
- Creating upload sessions for images, videos, or chat attachments.
- Checking previews and analytics before or after publishing.
- Working in a team context after discovering teams with SendIt tools.

Do not use SendIt when the user only wants local content drafting with no
publishing, scheduling, account connection, upload, or analytics action.

## MCP Configuration

Configure SendIt as a remote HTTP MCP server with OAuth:

```yaml
mcp_servers:
  sendit:
    url: "https://sendit.infiniteappsai.com/api/mcp"
    auth: oauth
```

Use `https://sendit.infiniteappsai.com/api/mcp`, not
`https://sendit.infiniteappsai.com/mcp`. The `/mcp` endpoint is reserved for the
ChatGPT app submission profile and exposes a reduced catalog. The `/api/mcp`
endpoint exposes the standard SendIt catalog, including team tools.

Hermes registers MCP tools with the `mcp_<server>_<tool>` naming pattern. With
the server name `sendit`, expected tools include:

- `mcp_sendit_list_connected_accounts`
- `mcp_sendit_list_teams`
- `mcp_sendit_connect_platform`
- `mcp_sendit_get_platform_requirements`
- `mcp_sendit_validate_content`
- `mcp_sendit_create_upload_session`
- `mcp_sendit_get_upload_session`
- `mcp_sendit_preview_content`
- `mcp_sendit_publish_content`
- `mcp_sendit_schedule_content`
- `mcp_sendit_get_analytics`

If the configured MCP server name is not `sendit`, replace the `mcp_sendit_`
prefix with the configured name.

## Setup From A Remote VPS Or Telegram

Use this flow when Hermes runs on a VPS and the user opens OAuth links on a
local phone or laptop.

If this folder was uploaded through Telegram or another messaging gateway, read
`TELEGRAM_SETUP.md` in this directory first. It contains the shorter operator
playbook.

1. Install the skill and MCP config:

   ```bash
   node ${HERMES_SKILL_DIR}/scripts/install-sendit-hermes.mjs
   ```

   If Hermes has not substituted `${HERMES_SKILL_DIR}`, run the same command
   from this skill directory as:

   ```bash
   node scripts/install-sendit-hermes.mjs
   ```

2. Start the OAuth login on the VPS:

   ```bash
   node ${HERMES_SKILL_DIR}/scripts/start-oauth-login.mjs
   ```

3. Send the printed SendIt authorization URL to the user.
4. Ask the user to open it, sign in, approve SendIt, and copy the final
   localhost callback URL from their browser address bar.
5. When the user pastes the callback URL, replay it on the VPS:

   ```bash
   node ${HERMES_SKILL_DIR}/scripts/complete-oauth-callback.mjs '<PASTED_CALLBACK_URL>'
   ```

6. Ask the user to send `/reload-mcp`, or restart the Hermes gateway/session if
   tools do not appear.

The callback helper accepts only `http://127.0.0.1:<port>/callback?...` and
`http://localhost:<port>/callback?...` URLs. Treat callback URLs as sensitive
because their `code` and `state` query parameters can complete OAuth.

## Publishing Workflow

1. Call `mcp_sendit_list_connected_accounts` before publishing or scheduling.
2. If the user has teams, call `mcp_sendit_list_teams` and use the intended
   `team_id` where relevant.
3. Call `mcp_sendit_get_platform_requirements` when requirements are uncertain.
4. If the user provides a local image, video, or chat attachment, create a
   SendIt upload session and use the returned HTTPS URL. Do not pass arbitrary
   local file paths to publish tools unless the tool description explicitly says
   the target platform accepts them.
5. Call `mcp_sendit_validate_content` before publish or schedule.
6. Call `mcp_sendit_preview_content` before publishing when available.
7. Use `mcp_sendit_publish_content` only when the user clearly asks for
   immediate publishing.
8. Use `mcp_sendit_schedule_content` for delayed posts. Confirm date, time, and
   timezone before scheduling.
9. Use `mcp_sendit_get_analytics` for performance reporting.

## Platform Connection Workflow

1. Call `mcp_sendit_list_connected_accounts`.
2. For missing accounts, call `mcp_sendit_connect_platform` with the target
   platform.
3. Send the returned platform OAuth URL to the user.
4. Ask the user to complete platform authorization in their browser.
5. Re-run `mcp_sendit_list_connected_accounts` to verify the connection.

## Safety Rules

- Do not publish, schedule, delete, reply, or trigger scheduled posts unless the
  user clearly asks for that action.
- Validate before publish or schedule.
- Preview before publish when the preview tool is available.
- Confirm destructive actions such as deleting published or scheduled posts.
- Do not ask the user for a SendIt API key. This setup uses MCP OAuth.
- Treat pasted OAuth callback URLs as sensitive. Never echo full `code` or
  `state` values in chat, logs, or summaries.
- Only replay callback URLs whose host is `127.0.0.1` or `localhost` and whose
  path is `/callback`.
- If OAuth fails or times out, restart the background `hermes mcp login sendit`
  flow and send the new authorization URL.

## Troubleshooting

- If Hermes mentions ChatGPT or team tools are missing, repair the MCP config by
  running `node ${HERMES_SKILL_DIR}/scripts/install-sendit-hermes.mjs`. Older
  installs may have used the reduced `/mcp` endpoint.
- If the authorization URL is not printed, inspect
  `/tmp/sendit-hermes/oauth.log` and verify `hermes mcp login sendit` is still
  running.
- If callback replay fails, ensure the OAuth login process is still waiting on
  the VPS and rerun `node ${HERMES_SKILL_DIR}/scripts/start-oauth-login.mjs`.
- If tools do not appear after OAuth succeeds, ask the user to send
  `/reload-mcp` or restart the Hermes session.

## Verification

After OAuth completes and MCP reloads, ask Hermes:

```text
Use the SendIt skill and list my connected social accounts.
```

Hermes should call `mcp_sendit_list_connected_accounts` or the equivalent
SendIt MCP tool for the configured server name.
