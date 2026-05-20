# Repo Policy Closeout Template

Every repo-policy-governed closeout must make policy authority visible before claiming progress. A green test suite is not enough if the repo policy is missing, stale, or mismatched.

## Standard template

```text
Policy check
- <repo-policy checker result, policy path, pass/fail_closed/drift reason>

Green 완료
- <completed local/green work>

Yellow 대기
- <queued release/live/restart/review items, or none>

Red 필요
- <actions still requiring explicit approval, or none crossed>

검증
- <tests/static checks/proofs>

Git 상태
- <branch/worktree/commit/dirty state/push status>

Live 상태
- <deployed/live/runtime/customer-visible state>
```

## Runtime/tooling extra sections

Hermes-agent and other runtime/tooling repos must also report the live-apply queue state explicitly:

```text
Gateway restart 필요
- <yes/no and why; do not restart unless explicitly approved>

Live runtime 반영됨
- <yes/no with runtime proof if applied>

대기열 포함됨
- <yes/no; queue entry id/details if restart/live apply is pending>
```

## Incomplete closeout rule

A closeout missing `Policy check` is incomplete. The agent must not treat it as final progress, because it hides whether authority came from `.hermes/repo-policy.yaml`, from stale memory, or from an unsafe assumption.

For runtime/tooling repos, a closeout missing restart/live/queue fields is also incomplete when code/config changes could affect live runtime behavior. Restart-needed items go to Yellow until Chris explicitly says `대기열 적용해` or `restart 필요한 것 모아서 적용해`.
