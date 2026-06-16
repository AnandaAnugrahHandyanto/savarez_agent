# PR Draft: Scope TUI session list and auto-resume to the active profile DB

## Title

Scope TUI session list and auto-resume to the active profile DB

## Summary

This makes the TUI session picker and auto-resume path read from the same profile-owned state that `session.resume` already uses. Today, a profile-resume can hydrate the correct profile workspace and runtime session, but `session.list` and `session.most_recent` still read the launch profile DB through `_get_db()`, so the picker can show the wrong recent sessions after switching profiles.

## Why

Profile resume is supposed to restore the active profile's own workspace and persisted session state. If the resume path comes from `profile_home` but the history/most-recent paths still come from the launch DB, the UI can point the user at a different session list than the one actually owning the resumed workspace.

## Changes

- Scope `session.list` to the active profile when `params.profile` is present.
- Scope `session.most_recent` to the active profile when `params.profile` is present.
- Preserve the current launch-profile behavior when no profile override is provided.
- Add regression coverage for profile-resume + list/most-recent divergence.

## Tests

```text
python -m pytest tests/test_tui_gateway_server.py -k "session_list or session_most_recent or session_resume_profile" -q --timeout-method=thread
```

## Branch

Local branch:

```text
fix/tui-profile-session-list-scope
```

## Duplicate check

Search queries already checked:

```text
repo:NousResearch/hermes-agent is:issue is:pr "session.list" "profile resume"
repo:NousResearch/hermes-agent is:issue is:pr "session.most_recent" "profile resume"
repo:NousResearch/hermes-agent is:issue is:pr "profile_home" "session.list" hermes-agent
repo:NousResearch/hermes-agent is:issue is:pr "most recent" "profile" "state.db" hermes-agent
```

No exact duplicate found in the current search pass.

