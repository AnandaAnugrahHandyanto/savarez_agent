# Low-risk upstream sync for a deployment fork

Use this when a fork has drifted far from upstream and the user asks to merge only low-risk changes.

## When to use

- The fork has deployment-specific files or local operational changes.
- Upstream has many commits since the merge-base.
- The user explicitly wants "low risk" or "only selected fixes," not a wholesale merge.

## Workflow

1. Fetch and quantify divergence:
   ```bash
   git fetch origin main
   git fetch upstream main
   BASE=$(git merge-base origin/main upstream/main)
   git rev-list --left-right --count upstream/main...origin/main
   git log --oneline --no-merges $BASE..upstream/main | sed -n '1,120p'
   git diff --name-status $BASE..upstream/main | sed -n '1,220p'
   ```

2. Identify fork-sensitive files before choosing commits:
   ```bash
   git diff --name-only $BASE..origin/main > /tmp/fork_paths.txt
   git diff --name-only $BASE..upstream/main > /tmp/upstream_paths.txt
   comm -12 <(sort /tmp/fork_paths.txt) <(sort /tmp/upstream_paths.txt)
   ```

3. Use a read-only merge simulation for risk mapping:
   ```bash
   git merge-tree $BASE origin/main upstream/main | sed -n '1,200p'
   ```
   Direct content conflicts are not the only risk: files such as `run_agent.py`, gateway session code, approval/security code, and container entrypoints may auto-merge but still have high semantic risk.

4. Prefer commits that are all true:
   - one or two narrow files,
   - bug/security fix rather than feature/refactor,
   - no fork-sensitive deployment files,
   - tests are included or easy to target,
   - no dependency on a later feature stack.

5. Cherry-pick onto a branch from clean `origin/main`:
   ```bash
   git checkout main
   git reset --hard origin/main
   git checkout -B low-risk-upstream-fixes
   git cherry-pick -x <commit>
   ```

6. Resolve conflicts conservatively:
   - If conflict markers enclose an upstream test block that depends on unrelated later upstream changes, keep only the tests relevant to the intended cherry-pick.
   - Do not accept unrelated upstream-only tests for features/helpers absent in the fork; they create false failures and may tempt over-merging.
   - For code conflicts, preserve fork deployment behavior unless the user explicitly approved changing it.

7. Run targeted tests for touched areas. If the repo has no local pytest install, `uv` can create an isolated test env:
   ```bash
   uv run --with pytest --with pytest-asyncio pytest <targeted tests> -q -o 'addopts='
   ```
   Include `pytest-asyncio` when tests use `@pytest.mark.asyncio`; otherwise pytest reports async tests as unsupported.

8. Watch for `uv.lock` churn caused by `uv run --with ...`; revert it unless the dependency lock update is intentional:
   ```bash
   git checkout -- uv.lock
   ```

9. Fast-forward main and verify origin:
   ```bash
   git checkout main
   git merge --ff-only low-risk-upstream-fixes
   git push origin main
   git ls-remote origin refs/heads/main | cut -f1
   git rev-parse HEAD
   git status --short
   ```

## Pitfalls

- A "low-risk" commit can still conflict in tests because upstream's test file contains later unrelated tests. Trim only incompatible upstream-only test blocks; keep the relevant regression tests.
- Do not bulk-merge deployment files such as `Dockerfile`, `docker/entrypoint.sh`, `gateway/run.py`, or fork-specific skills/scripts in Gordon's Hermes fork.
- If upstream changed test expectations for defaults that intentionally differ in the fork, do not change fork behavior just to satisfy unrelated upstream tests.
- Cherry-pick order matters for follow-up fixes: apply precursor Telegram/media fixes before follow-ups that assume them.
