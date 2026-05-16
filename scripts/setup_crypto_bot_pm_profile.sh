#!/usr/bin/env bash
set -euo pipefail

PROFILE_NAME="${PROFILE_NAME:-crypto-bot-pm}"
HERMES_ROOT="${HERMES_ROOT:-$HOME/.hermes}"
PROFILE_ROOT="$HERMES_ROOT/profiles/$PROFILE_NAME"
SOURCE_PLUGIN="$HERMES_ROOT/plugins/crypto-bot-pm"
SOURCE_SKILL="$HERMES_ROOT/skills/project-management/crypto-bot-pm"
TARGET_PLUGIN="$PROFILE_ROOT/plugins/crypto-bot-pm"
TARGET_SKILL="$PROFILE_ROOT/skills/project-management/crypto-bot-pm"
export PROFILE_NAME HERMES_ROOT

if [[ ! -d "$PROFILE_ROOT" ]]; then
  echo "Profile '$PROFILE_NAME' does not exist at $PROFILE_ROOT"
  echo "Create it first: hermes profile create $PROFILE_NAME"
  exit 1
fi

if [[ ! -d "$SOURCE_PLUGIN" ]]; then
  echo "Missing source plugin: $SOURCE_PLUGIN"
  exit 1
fi

if [[ ! -d "$SOURCE_SKILL" ]]; then
  echo "Missing source skill: $SOURCE_SKILL"
  exit 1
fi

if ! command -v hermes >/dev/null 2>&1; then
  echo "Could not find hermes on PATH."
  echo "Activate the Hermes venv or run from a shell where hermes is available."
  exit 1
fi

python3 - <<'PY'
from pathlib import Path
import os
import shutil

profile_name = os.environ.get("PROFILE_NAME", "crypto-bot-pm")
hermes_root = Path(os.environ.get("HERMES_ROOT", str(Path.home() / ".hermes"))).expanduser()
profile_root = hermes_root / "profiles" / profile_name

copies = [
    (hermes_root / "plugins" / "crypto-bot-pm", profile_root / "plugins" / "crypto-bot-pm"),
    (
        hermes_root / "skills" / "project-management" / "crypto-bot-pm",
        profile_root / "skills" / "project-management" / "crypto-bot-pm",
    ),
]

for source, target in copies:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )

source_auth = hermes_root / "auth.json"
target_auth = profile_root / "auth.json"
if source_auth.exists():
    if target_auth.exists() or target_auth.is_symlink():
        target_auth.unlink()
    target_auth.symlink_to(source_auth)
else:
    print(
        "Warning: default profile auth.json was not found. "
        "Run `hermes auth openai-codex` in the default profile first."
    )

target_env = profile_root / ".env"
if target_env.exists():
    kept_lines = []
    for raw_line in target_env.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("OPENROUTER_API_KEY="):
            continue
        kept_lines.append(raw_line)
    if kept_lines:
        target_env.write_text("\n".join(kept_lines) + "\n", encoding="utf-8")
        target_env.chmod(0o600)
    else:
        target_env.unlink()

soul = """You are crypto-bot-pm, a Hermes project-management profile for the local crypto_bot managed project.

Primary role:
- Act as PM, architect, supervisor, verifier, and reporter for crypto_bot work.
- Use the profile-local crypto-bot-pm skill and the crypto_bot native Kanban board as the operating contract.
- Treat Codex as a bounded coding or audit sidecar, not as the decision maker.

Source-of-truth paths:
- Hermes control plane: /Users/preston/.hermes/hermes-agent
- Managed repo: /Users/preston/robinhood/crypto_bot
- Managed-project descriptor: /Users/preston/.hermes/hermes-agent/projects/crypto_bot/crypto_bot.project.yaml
- Native Kanban board: crypto_bot

Operating rules:
- Begin with read-only reality checks before reporting readiness or selecting work.
- Do not rely on stale session claims; verify profile, repo branch/HEAD, plugin paths, Kanban state, PR/CI/readiness state, and token hygiene.
- Safe branch-local development may proceed only when the crypto-bot-pm skill policy allows it and durable task-source evidence exists.
- Stop and escalate before secrets, credential stores, broker/trading/financial APIs, runtime services, Gitea writes, workflows, runners, pushes, PR creation, PR updates, or merges unless exact future policy explicitly enables the action.
- Never print token material. If token material appears in output or artifacts, report it as compromised without quoting it.
- Completion claims require evidence: selected task source, branch, HEAD, changed files, validators, sidecar audit result, completion-gate JSON path, blocked-surface proof, and next action.

Communication:
- Be concise, operational, and evidence-first.
- Separate local readiness, PR/CI readiness, merge readiness, and operator approval requirements.
"""
(profile_root / "SOUL.md").write_text(soul, encoding="utf-8")
PY

hermes -p "$PROFILE_NAME" config set model.default gpt-5.5
hermes -p "$PROFILE_NAME" config set model.provider openai-codex
hermes -p "$PROFILE_NAME" config set model.openai_runtime auto
hermes -p "$PROFILE_NAME" config set model.api_mode codex_responses
hermes -p "$PROFILE_NAME" config set terminal.cwd /Users/preston/robinhood/crypto_bot
hermes -p "$PROFILE_NAME" plugins enable crypto-bot-pm

echo
echo "Configured profile:"
hermes profile show "$PROFILE_NAME"

echo
echo "Plugin check:"
hermes -p "$PROFILE_NAME" plugins list | grep -E 'crypto-bot-pm|Name|Status' || true

echo
echo "Skill check:"
hermes -p "$PROFILE_NAME" skills list --enabled-only | grep -E 'crypto-bot-pm|Enabled|Name' || true

echo
echo "Done. Try: $PROFILE_NAME chat"
