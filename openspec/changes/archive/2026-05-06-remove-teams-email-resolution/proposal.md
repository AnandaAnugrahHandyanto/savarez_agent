## Why

The Microsoft Teams adapter currently uses the Microsoft Graph API to resolve a user's Entra ID (AAD Object ID) into an email address, allowing `config.yaml` to authorize users by email. This creates significant operational overhead: it requires assigning the `User.Read.All` Application permission in Azure AD, maintaining an OAuth Graph Client, handling token caching, and managing 403 Forbidden errors. Furthermore, the channel policy enforcement also suffers from naming quirks because Teams only sends raw `19:xxx` IDs, making human-readable name matching error-prone. Removing the email/name resolution entirely in favor of using raw AAD Object IDs and raw Channel IDs in `config.yaml` greatly simplifies the architecture, eliminates the Graph API dependency, and creates a more robust mapping system.

## What Changes

- **BREAKING**: Remove `GraphClient` entirely from the Teams plugin.
- **BREAKING**: Remove email extraction logic from `adapter.py`. The gateway will now solely rely on `aad_object_id` or the raw bot framework `id` for user authorization.
- Modify documentation to instruct users to configure `config.yaml` using raw AAD Object IDs for users and raw `19:xxx` IDs for channels, utilizing YAML comments to label them with human-readable names.
- Remove Azure AD API permission requirements (`User.Read.All`) from the setup guide since the Graph API is no longer used.

## Capabilities

### New Capabilities
None

### Modified Capabilities
- `teams-connector`: Changing authorization matching requirements from email/human-readable names to raw AAD Object IDs and raw Channel IDs.

## Impact

- **Code**: `plugins/platforms/teams/adapter.py`, `plugins/platforms/teams/graph_client.py` (deleted).
- **Configuration**: Users must update their `config.yaml` to use raw IDs.
- **Documentation**: `setup-hermes-team-gateway.md` and `docs/user-guide/messaging/teams.md` must be updated to remove Graph API steps.
