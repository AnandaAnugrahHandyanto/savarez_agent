# Teams Connector

## Purpose
TBD - Manages integration with Microsoft Teams, processing incoming webhooks and dispatching responses.

## Requirements

### Requirement: Raw AAD Object ID Authorization
The system SHALL authorize Microsoft Teams users strictly based on their raw AAD Object ID (`aad_object_id`) or Bot Framework User ID (`id`).

#### Scenario: User provides raw AAD ID in allowed_users
- **WHEN** a user sends a message from Microsoft Teams and their AAD Object ID matches an entry in `config.yaml` `allowed_users` list
- **THEN** the system authorizes the user and processes the message

#### Scenario: User authorization fails for missing ID
- **WHEN** a user's AAD Object ID is not present in the `allowed_users` list
- **THEN** the system rejects the user as Unauthorized

### Requirement: Raw Channel ID Policy Enforcement
The system SHALL authorize Microsoft Teams channels based on substring matching of their raw internal thread ID (e.g., `19:xxxx@thread.v2` or `19:xxxx@thread.tacv2`). Exact matching MUST NOT be used because Microsoft Teams dynamically appends a `;messageid=...` suffix to the thread ID in some webhook payloads.

#### Scenario: User messages bot in an allowed channel
- **WHEN** a user mentions the bot in a channel whose raw ID is present in the `allowed_channels` list
- **THEN** the system processes the message and responds
