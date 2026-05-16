# Selective cherry-pick pass — 2026-05-16

Context: Gordon asked to “pull-in the selective cherry picks” for `rousegordon-ops/hermes-agent`, a deployment fork with fork-sensitive Railway/gateway behavior. Use this as a concrete example of a low-risk upstream sync.

## Setup

Repository: `/opt/data/repo`

```bash
git -C /opt/data/repo remote add upstream https://github.com/NousResearch/hermes-agent.git  # if missing
git -C /opt/data/repo fetch origin main
git -C /opt/data/repo fetch upstream main
BASE=$(git -C /opt/data/repo merge-base origin/main upstream/main)
git -C /opt/data/repo rev-list --left-right --count upstream/main...origin/main
git -C /opt/data/repo log --oneline --no-merges $BASE..upstream/main | sed -n '1,80p'
```

## Commits applied successfully

Cherry-picked onto `low-risk-upstream-fixes-20260516`, then fast-forwarded main:

- `fcd9011f8` — `fix(security): separate OAuth PKCE state from code_verifier`
- `345821b4a` — `style: move secrets import alongside other function-level imports`
- `72f94f4a7` — `test(security): regression guard for OAuth PKCE state/verifier separation`
- `2d7182f72` — `fix(delegate): move heartbeat thread start inside try block to prevent orphan`
- `606836331` — `fix(delegate): guard heartbeat join against unstarted thread`
- `c445f48b7` — `fix(delegation): honor api_mode + auto-detect anthropic_messages URLs`
- `627f8a5f1` — `security: sanitize tool error strings before injecting into model context`

Skipped:

- `d0a183cad` — `fix(doctor): suppress stale direct-key issues when oauth is healthy`; conflicted heavily in forked `hermes_cli/doctor.py` and `tests/hermes_cli/test_doctor.py`. In this fork, skip rather than risk semantic damage unless Gordon explicitly asks for the doctor fix.

## Conflict notes

- `72f94f4a7` conflicted only in `scripts/release.py` `AUTHOR_MAP`; resolve by keeping both sides’ author entries.
- `c445f48b7` conflicted in `tests/tools/test_delegate.py`; keep Gordon fork’s existing `test_direct_endpoint_falls_back_to_openai_api_key_env` and insert upstream’s new Anthropic/api_mode tests before it. Do not accidentally replace the fork test with upstream’s `returns_none_api_key_when_not_configured` block unless the production code is also intended to change that behavior.
- `627f8a5f1` conflicted in `model_tools.py`; keep `logger.exception(error_msg)` plus `return json.dumps({"error": _sanitize_tool_error(error_msg)}, ensure_ascii=False)`.

## Verification used

System Python lacked pytest, so use `uv`:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/agent/test_anthropic_oauth_pkce.py \
  tests/tools/test_delegate.py \
  tests/test_sanitize_tool_error.py \
  -q -o 'addopts='
```

Result: `142 passed, 1 warning`.

Then revert `uv.lock` churn before merging/pushing:

```bash
git checkout -- uv.lock
git checkout main
git merge --ff-only low-risk-upstream-fixes-20260516
GIT_TERMINAL_PROMPT=0 git push origin main
```

Pushed fork main to `6971de750dab77f72b4b37fd94710361dfa7e673`.
