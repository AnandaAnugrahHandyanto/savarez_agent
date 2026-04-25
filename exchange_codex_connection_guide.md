# Company Exchange Connection Guide for Codex.app

## Scope

This document describes the **current** Exchange-related connection method used in this workspace, so it can be packaged for use in Codex.app or a company Codex environment.

## Current connection method

### Email / Flow approvals
The current email integration uses:
- **IMAP** to receive mail
- **SMTP** to send replies
- standard mailbox polling for new messages

This is implemented in the email adapter, not Microsoft Graph.

### Exchange calendar
At the time this guide was generated, there is **no active Microsoft Graph calendar sync implementation** found in the repo. If calendar sync is needed, it would need a separate Graph OAuth integration.

## Environment variables used today

Required for the current email connection:

```bash
EMAIL_ADDRESS=your-agent-address@company.com
EMAIL_PASSWORD=your-app-password-or-mail-password
EMAIL_IMAP_HOST=imap.office365.com
EMAIL_SMTP_HOST=smtp.office365.com
```

Optional / recommended:

```bash
EMAIL_IMAP_PORT=993
EMAIL_SMTP_PORT=587
EMAIL_POLL_INTERVAL=15
EMAIL_ALLOWED_USERS=user1@company.com,user2@company.com
EMAIL_HOME_ADDRESS=your-agent-address@company.com
EMAIL_ALLOW_ALL_USERS=false
```

## How it works

### Receiving flow approval mail
1. The adapter connects to the mailbox with IMAP.
2. It polls for unread messages.
3. It ignores automated/noreply mail.
4. It extracts the plain-text body and any attachments.
5. It passes the message into the Hermes gateway workflow.

### Sending replies
1. The adapter uses SMTP to send replies.
2. It preserves thread context with standard email headers.
3. It can attach files when the response includes media references.

## Where this is defined in code

- `gateway/platforms/email.py`
  - IMAP receive logic
  - SMTP send logic
  - body parsing, attachment extraction, automation filtering
- `gateway/config.py`
  - loads the `EMAIL_*` environment variables
- `website/docs/user-guide/messaging/email.md`
  - user-facing setup documentation

## Current behavior summary

- **Flow sign-off mail**: handled through the email adapter via IMAP/SMTP
- **Exchange calendar sync**: not currently implemented in this repo
- **Graph OAuth**: not the current active path for email handling in this codebase

## Suggested Codex usage pattern

Before running a Codex task that needs mailbox access:

```bash
set -a
source ~/.credentials/company/exchange.env
set +a
codex ...
```

## Security notes

- Keep credentials in a secure file or secret mount
- Do not paste secrets into chat
- Do not commit live credentials into the skill or documentation file
- Prefer least-privilege mailbox access

## If you later add Graph OAuth for calendar
If Exchange calendar sync is added later, the expected Graph endpoints would likely be:
- `GET /v1.0/me`
- `GET /v1.0/me/calendarView`
- `GET /v1.0/me/messages`
- `GET /v1.0/me/mailFolders/Inbox/messages`

But again: **those are not the current active mechanism** in this repo.

## Packaging note

This file is safe to share with Codex.app as documentation, because it contains **no live credentials**.
