# Reviewer Findings — remove-teams-email-resolution

**Date:** 2026-05-06  
**Reviewer:** Agent Reviewer  
**Change:** `remove-teams-email-resolution`  
**Review Basis:** Updated Commander direction overrides earlier exploration assumptions:

- Support raw AAD object IDs only for `allowed_users`
- Support raw channel/conversation IDs only for `allowed_channels`
- Do not support email matching
- Do not support channel-name matching

## Verdict

**REQUEST_CHANGES**

The implementation is close to the intended direction, but it still preserves email-based authorization hooks and channel-name matching behavior that should not exist under the final scope.

## Findings

### P1 — Authorization logic still preserves email-alias matching hooks

**File:** [`gateway/run.py`](/home/ubuntu/workspaces/oss/hermes-agent/gateway/run.py:3675)

The change objective is raw-ID-only authorization for Teams, but `_is_user_authorized()` still expands matching through `source.user_id_alt` and email-localpart logic:

```python
check_ids = {user_id}
if source.user_id_alt:
    check_ids.add(source.user_id_alt)

for cid in check_ids:
    if "@" in cid:
        expanded_emails.add(cid.split("@")[0])
```

Why this is a problem:

- It preserves the authorization pathway for email aliases instead of removing it.
- It broadens shared gateway auth behavior instead of constraining Teams to raw IDs only.
- It contradicts the change direction and makes future regressions easier.

Related test that currently locks the wrong behavior:

- [`tests/gateway/test_teams_auth.py`](/home/ubuntu/workspaces/oss/hermes-agent/tests/gateway/test_teams_auth.py:26)

### P1 — Channel allowlist still supports channel-name matching

**File:** [`plugins/platforms/teams/adapter.py`](/home/ubuntu/workspaces/oss/hermes-agent/plugins/platforms/teams/adapter.py:322)

Current logic accepts a match if any configured entry appears in either `conv_id` or `conv_name`:

```python
if not any(c in conv_id or c in conv_name for c in self._allowed_channels):
```

Why this is a problem:

- Final direction is raw channel/conversation IDs only.
- `conv_name` matching reintroduces a human-readable contract that was explicitly removed from scope.
- It makes policy behavior less deterministic and harder to document correctly.

Related test that currently locks the wrong behavior:

- [`tests/gateway/test_teams_channel.py`](/home/ubuntu/workspaces/oss/hermes-agent/tests/gateway/test_teams_channel.py:57)

### P2 — Debug/noise logging still conflicts with the cleanup intent

**Files:**

- [`gateway/run.py`](/home/ubuntu/workspaces/oss/hermes-agent/gateway/run.py:3699)
- [`plugins/platforms/teams/adapter.py`](/home/ubuntu/workspaces/oss/hermes-agent/plugins/platforms/teams/adapter.py:324)
- [`plugins/platforms/teams/adapter.py`](/home/ubuntu/workspaces/oss/hermes-agent/plugins/platforms/teams/adapter.py:265)

Issues:

1. Auth miss path logs full `check_ids`, `allowed_ids`, and the effective allowlist:

```python
logger.warning(f"Auth DEBUG: check_ids={check_ids}, allowed_ids={allowed_ids}, platform_allowlist={repr(platform_allowlist)}")
```

2. Teams adapter still emits warning logs for dropped disallowed channels.
3. Normal adapter disconnect was changed from `info` to `warning`.

Why this matters:

- The change includes an operational cleanup goal.
- The auth debug log exposes sensitive identifiers unnecessarily.
- Warning level should be reserved for actionable operator conditions, not routine disconnects or policy drops.

### P3 — Scratch helper file is left in the worktree

**File:** [`test_run.py`](/home/ubuntu/workspaces/oss/hermes-agent/test_run.py:1)

This appears to be a local ad hoc helper for invoking one Teams test manually. It should not ship as part of the change unless there is a documented reason to keep it.

## What Looks Correct

- Teams adapter uses `aad_object_id` as the primary user identity:
  - [`plugins/platforms/teams/adapter.py`](/home/ubuntu/workspaces/oss/hermes-agent/plugins/platforms/teams/adapter.py:337)
- Teams source construction explicitly sets `user_id_alt=None`:
  - [`plugins/platforms/teams/adapter.py`](/home/ubuntu/workspaces/oss/hermes-agent/plugins/platforms/teams/adapter.py:346)
- Teams docs were moved toward raw-ID guidance:
  - [`website/docs/user-guide/messaging/teams.md`](/home/ubuntu/workspaces/oss/hermes-agent/website/docs/user-guide/messaging/teams.md:126)
- `opentelemetry.context` was added to noisy logger suppression:
  - [`hermes_logging.py`](/home/ubuntu/workspaces/oss/hermes-agent/hermes_logging.py:65)

## Verification Notes

Static review completed against:

- current code diff
- change artifacts
- Teams adapter/tests/docs touched by this implementation

Test execution was attempted but not completed successfully:

1. `python3 -m pytest tests/gateway/test_teams.py tests/gateway/test_teams_auth.py tests/gateway/test_teams_channel.py`
   - **Exit code:** `1`
   - **Reason:** `pytest` not installed in the base interpreter

2. `uv run --extra dev pytest -n 0 tests/gateway/test_teams.py tests/gateway/test_teams_auth.py tests/gateway/test_teams_channel.py`
   - **Exit code:** `1`
   - **Reasons:**
     - `tool.uv.exclude-newer = "7 days"` in `pyproject.toml` is rejected by this `uv` parser
     - dependency resolution fails on `yc-bench` for Python 3.11

## Reviewer Recommendation

Before archive or approval:

1. Remove Teams email-alias matching from gateway auth for this change scope.
2. Restrict Teams channel allowlist matching to raw IDs only.
3. Remove or downgrade noisy/debug logs introduced by this change.
4. Remove `test_run.py` if it is only a local scratch helper.
5. Re-run targeted Teams tests in a working test environment and attach real pass/fail evidence.
