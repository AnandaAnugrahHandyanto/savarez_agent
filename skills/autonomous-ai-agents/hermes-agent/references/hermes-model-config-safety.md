# Model Config Safety Rules

**When Gordon asks about changing LLM configuration — always confirm before acting, never assume.**

## Rule: Ask first on model/provider changes

Before running any `hermes config set model.*` command (or similar):
- State the exact command you would run and the effect it will have
- Wait for Gordon to confirm with "yes" or equivalent
- Do not proceed on inference from context — explicit confirmation only

### Why
Gordon's primary model is GPT-5.5, fallback is MiniMax-M2.7. He has corrected the agent mid-session for jumping the gun on config changes. Getting this wrong is disruptive.

## Why changes may not take effect

- **Railway deployments**: Config changes (`hermes config set`) take effect immediately in the running Railway process — no restart needed
- **File edits to `/opt/hermes/run_agent.py`**: These only take effect if the source is baked into the container image at deploy time. If the file isn't in the git-backed source tree, it won't survive a rebuild. Changes to the running process via file edit require a Railway redeploy.

## If a code change is made to `/opt/hermes/`

Trigger a Railway rebuild to pick it up:
```bash
# Via the Railway CLI (if available) or the Railway dashboard
# Or use the self-rebuild skill: skill_view(name='self-rebuild')
```

## Source tree location

`/opt/hermes/run_agent.py` is NOT a git repo — it's part of the deployed Hermes Agent package. To persist code changes, they must be committed to the source repository (`rousegordon-ops/hermes-agent`) and then a new deployment triggered.