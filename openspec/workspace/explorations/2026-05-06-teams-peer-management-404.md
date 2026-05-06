# Exploration: Teams Peer Management Failure

## The Problem
The user reported the following errors in `hermes-gateway.log` when the agent attempts to follow the `teams-peer-management` skill:
```log
ERROR plugins.memory.honcho.session: Failed to create conclusion: Peer Hao-Nguyen not found in workspace hermes_workspace
ERROR plugins.memory.honcho.session: Failed to create conclusion: Peer Aziz not found in workspace hermes_workspace
```

## Post-Revision Analysis (New Findings)
Another agent recently revised the `teams-peer-management` skill to instruct Hermes to use **Emails** as the Peer ID (e.g., `hao.nguyen@optimalitypro.com`). This revision was tested and **will completely break.**

### Finding 1: Honcho Peer ID Validation Rules
I ran a test script directly against the Honcho Python SDK.
Honcho strictly enforces the following Regex pattern for Peer IDs:
```regex
^[a-zA-Z0-9_-]+$
```
**This means Peer IDs CANNOT contain `@` or `.` characters.**
- `hao.nguyen` (from the original skill) -> **Fails validation** (contains `.`)
- `hao.nguyen@optimalitypro.com` (from the revised skill) -> **Fails validation** (contains `@` and `.`)
- `Hao-Nguyen` -> **Passes validation**
- `6bee71a3-b027-4c8f-ae4d-22b1bb8b973a` (UUID) -> **Passes validation**

### Finding 2: `honcho_profile` vs `honcho_conclude`
The agent correctly deduced in the skill that `honcho_profile()` (which calls `set_card` under the hood) has the ability to **implicitly create** a new peer in the Honcho backend if it doesn't exist, while `honcho_conclude()` will throw a `404 Not Found` if the peer doesn't already exist.

So the original error occurred because:
1. The AI tried to use `honcho_conclude(peer="Hao-Nguyen")`.
2. `Hao-Nguyen` was a valid ID, but it didn't exist yet, so it threw a 404.

If the AI uses `honcho_profile(peer="hao.nguyen@optimalitypro.com")` under the NEW skill, it will fail BEFORE even hitting the network, with a Pydantic Validation Error: `String should match pattern '^[a-zA-Z0-9_-]+$'`.

## Visualization

```text
┌────────────────────┐
│ AI uses new skill  │
│ peer="hao@opt.com" │
└────────────────────┘
          │
          ▼
┌────────────────────┐
│ Honcho Python SDK  │
│ Pydantic Validator │
│ Regex: ^[a-zA-Z0-9_-]+$
│ ❌ CRASH: Invalid  │
└────────────────────┘
```

## The Correct Solution

The `teams-peer-management` skill must be revised again to enforce Honcho's regex constraints.

**Recommendation:** Revert to using the **AAD Object ID (UUID)** as the Peer ID.
* It is guaranteed to be unique.
* It perfectly matches the `^[a-zA-Z0-9_-]+$` regex (UUIDs are just alphanumeric and hyphens).
* It eliminates all edge cases with dots, at-signs, spaces, and duplicate names.

The skill should instruct the AI to:
1. Always use the raw AAD Object ID for the peer parameter (e.g., `peer="fd3fdd74-1ba4-4df1-a5ea-55b35de08c5f"`).
2. Store the user's human-readable name and email *inside* the peer card via `honcho_profile()`, rather than trying to force it into the Peer ID string.
