## Context

The Microsoft Teams adapter was originally designed to query the Microsoft Graph API to resolve `aad_object_id` into a user's email address. This enabled human-readable authorization matching in `config.yaml` using emails. However, this introduced major complexity: Azure AD Application permissions (`User.Read.All`) were strictly required, throwing 403 Forbidden errors if missing, and adding OAuth token management overhead to the bot's runtime. Furthermore, Microsoft Teams masks channel names, sending only internal `19:xxx@thread.v2` IDs to bots, which caused human-readable channel configuration to silently fail. 

## Goals / Non-Goals

**Goals:**
- Completely remove the Microsoft Graph API dependency from the Teams plugin.
- Simplify authorization by shifting to raw `aad_object_id` strings and raw channel IDs.
- Ensure the gateway cleanly loads configuration from `config.yaml` and matches against the raw `source.user_id` and `source.chat_id`. Channel IDs must be evaluated using substring matching to accommodate dynamic Teams suffixes (e.g., `;messageid=...`).
- Update setup documentation so users understand how to find their raw IDs and map them via YAML comments.

**Non-Goals:**
- We are not changing the core gateway `_is_user_authorized` logic; the gateway's string intersection logic works perfectly when provided the correct IDs.

## Decisions

- **Decision 1: Delete `graph_client.py` and remove its imports**
  - *Rationale*: Without the need to resolve emails, the Graph client is dead code. Removing it trims dependencies and reduces error surface area.
- **Decision 2: Remove `user_id_alt` assignment in `TeamsAdapter._on_message`**
  - *Rationale*: The `TeamsAdapter` will solely assign `user_id = aad_object_id` (or `from_account.id`). We do not need a secondary identifier.
- **Decision 3: Update User Documentation**
  - *Rationale*: Users must know they should copy the raw AAD Object ID from their Entra profile, and that they must find the channel thread ID from the Teams client or gateway logs, then map them using comments in `config.yaml` for readability.

## Risks / Trade-offs

- **Risk: Poor User Experience with Raw IDs** -> Users may find configuring raw AAD Object IDs and Channel IDs less friendly than emails/names.
  - *Mitigation*: Emphasize in the documentation that users can and should use inline YAML comments (e.g., `- "fd3fdd... # phuong@optimalitypro.com"`) to maintain readability.
- **Risk: Breaking Change for Existing Deployments** -> Anyone currently configured with emails will immediately fail authorization upon upgrading.
  - *Mitigation*: Highlight this extensively in the release notes and update the official documentation.
