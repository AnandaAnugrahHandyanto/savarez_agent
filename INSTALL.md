# INSTALL.md - Hermes coding agent overlay

Personal-install daily-driver coding agent for Porter and Clay. Each operator installs on their own machine. Methodology is shared through the fork; model choices are per-machine.

## Prerequisites

- Windows 11 with WSL2 Ubuntu, macOS, or Linux
- GitHub authentication
- API key for at least one provider
- Optional MCP credentials for GitHub, Sentry, Supabase, and Upstash

## Install on Windows via WSL2

```powershell
wsl --install -d Ubuntu-24.04
wsl --set-default-version 2
```

Inside Ubuntu:

```bash
mkdir -p $HOME/repos
cd $HOME/repos
git clone https://github.com/ptanner66-prog/hermes-agent.git
cd hermes-agent
./setup-hermes.sh
source venv/bin/activate
./hermes setup
```

Do not run Hermes natively from a Windows OneDrive checkout. Keep active work inside the WSL filesystem.

## Configure models

```bash
cp config/models.yml.example config/models.yml
$EDITOR config/models.yml
bash scripts/apply-models-yml.sh
```

Provider swaps are done by editing `config/models.yml` and rerunning `scripts/apply-models-yml.sh`. Committed methodology files should not change when providers change.

## Configure secrets

Store provider keys in `${HERMES_HOME:-$HOME/.hermes}/.env`, not in the repository.

Examples:

```bash
KIMI_API_KEY=...
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GITHUB_TOKEN=...
```

## First-run checks

```bash
./hermes doctor
./hermes -c '/skills'
ruff check .
scripts/run_tests.sh
```

Stage 1 baseline currently has documented upstream failures in `BACKLOG.md`; future work should avoid adding new failures.

## /escalate

Use `/escalate "<problem statement>"` only after normal workflow has tried 2-3 fixes on a critical-path bug and waiting overnight is acceptable. Operator approves before commit.

## Per-machine files never committed

- `${HERMES_HOME:-$HOME/.hermes}/.env`
- `config/models.yml`
- `config/pricing.yml`
- `config/cost-baseline.yml`
- `.claude/settings.local.json`
- `~/.claude/agents/*.md`
