# Hermes Agent — Handoff

> Personal-fork operational handoff. For the upstream project's user-facing docs see [README.md](./README.md) and [hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/).

## What it is
Hermes is a self-improving AI agent (originally **NousResearch/hermes-agent**, MIT). This is **gordonrouse's personal fork**, deployed as a long-running messaging bot on Railway. It listens on Telegram/Discord/Slack/WhatsApp/Signal/etc. via a single "gateway" process, talks to LLM providers (MiniMax default, with Sonnet/Opus 4.6 available), and has a built-in skills/memory/cron system that lets it create and run its own routines.

## Where the code lives
- **Local source:** `~/hermes-agent` (Python, with some Node for the TUI/web UI)
- **Fork remote (`origin`):** `https://github.com/rousegordon-ops/hermes-agent`
- **Upstream (`upstream`):** `https://github.com/NousResearch/hermes-agent`
- **Branches:**
  - `main` — bleeding edge. Both manual edits *and* an in-container source-watcher daemon push commits here (author "Hermes <hermes@hermes>"). Always `git fetch && git pull --rebase` before pushing.
  - `release-pin` — what Railway watches. To deploy code that needs a rebuild: `git push origin main:release-pin`. Pushes to `main` alone never trigger Railway.

## How it's structured
- `gateway/` — the long-running process. `gateway/run.py` is the entrypoint; `gateway/platforms/` has one file per messaging platform (telegram.py, discord.py, slack.py, whatsapp.py, signal.py, email.py, matrix.py, …).
- `skills/` — agent skills (procedural memory). The agent also writes its own here. `skills/autonomous-ai-agents/hermes-agent/self-*/` are the self-restart and self-rebuild skills.
- `agent/`, `cli.py`, `run_agent.py` — agent loop and CLI.
- `tools/` — tool implementations (40+ tools).
- `scripts/source_watcher.py` — the daemon that auto-commits container-side edits to `main`.
- `Dockerfile` — Debian 13 + Python 3.13 (uv) + Node, with Playwright/Chromium baked in. Runtime `ENTRYPOINT` is `docker/entrypoint.sh` → `gateway run`.
- `pyproject.toml` / `uv.lock` — Python deps. `package.json` for top-level Node.

## How it's built
- **Locally:** `uv venv && uv pip install -e ".[all]"`, then `hermes` (CLI) or `hermes gateway start` (messaging).
- **Container:** `docker build .` — multi-stage, copies `uv` from `ghcr.io/astral-sh/uv` and `gosu` for privilege drops; runs as non-root user `hermes` (UID 10000) with `/opt/data` as `HERMES_HOME` (the persisted volume on Railway).

## How it's deployed (Railway)
- **Project:** `pretty-amazement` (`c49b3e8b-a36d-4d24-a972-eab5e05b881d`)
- **Service:** `hermes-agent` (`c32be0a9-9d43-49a8-bf43-764915360dfb`)
- **Environment:** `production` (`38eea0f3-0bd3-48f4-abaf-ec3de09174de`)
- **Two deploy modes:**
  - **Restart** (~30s, free-ish): `serviceInstanceRedeploy` GraphQL via curl from inside the container. The entrypoint pulls `origin/main` on start, so any restart picks up new gateway/tools/scripts code (Bucket 2).
  - **Rebuild** (~10 min, ~$0.11): `git push origin main:release-pin`. Required for Dockerfile / dependency changes (Bucket 3).
- **Key env vars on the service:** `RAILWAY_API_TOKEN` (powers self-restart, rotated 2026-05-06), `GITHUB_TOKEN` (powers self-rebuild push), `TIRITH_IGNORED_RULES=lookalike_tld` (so Railway's `.app` TLD doesn't trip approval prompts on every self-restart).
- **Crash-suppression marker:** the gateway writes `${HERMES_HOME}/.planned_redeploy` before any self-redeploy; its SIGTERM handler reads + unlinks it to exit 0 instead of 1, suppressing Railway's "Deploy Crashed!" notification.

## Footguns to know about
1. **`~/chatbot` may be Railway-linked to hermes-agent.** Earlier diagnostics relinked it for log access. `railway up` from `~/chatbot` while linked to hermes-agent will deploy chatbot code AS hermes-agent and crash the service. Always `railway status` before `railway up` from `~/chatbot`. Recovery: `git push origin main:release-pin` from `~/hermes-agent`.
2. **Watcher conflicts.** The container's `source_watcher.py` commits 4–10 times/hr to `main`, often touching the same skill files you're editing (especially `skills/autonomous-ai-agents/hermes-agent/self-*/SKILL.md` and `gateway/run.py`). It has reverted user-requested changes more than once. **Always rebase before pushing**; defer to user's in-session intent over what the bot committed; if the bot keeps re-asserting an unwanted string, *delete the string* rather than re-reverting messages.
3. **Confirm before pushes.** Any push that triggers a Railway build/restart should be confirmed with the user first so they can batch.
