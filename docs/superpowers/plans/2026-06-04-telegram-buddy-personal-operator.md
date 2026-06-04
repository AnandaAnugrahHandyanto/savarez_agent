# Telegram Buddy Personal Operator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a practical Telegram Buddy personal operator profile with Clear Thought MCP, curated personal tooling, fewer routine approval prompts, and appropriate GPT-5.3-Codex-Spark subagent usage.

**Architecture:** Use existing Hermes seams instead of creating a parallel runtime: `SOUL.md` for identity, `~/.hermes/config.yaml` for MCP/delegation/approval settings, native `mcp_servers` for Clear Thought, existing approval gates for high-risk commands, and `delegate_task` for Spark sidecars. Keep business MCPs out of this profile by configuration and verification.

**Tech Stack:** Python, YAML, Hermes native MCP client, Hermes approval system, Hermes delegation/subagent tool, pytest, Telegram gateway behavior tests where needed.

---

## File Structure

- Modify: `/Users/sulemanmanji/.hermes/SOUL.md`
  - Primary Buddy identity and Telegram behavior contract loaded into every Hermes turn.
- Modify: `/Users/sulemanmanji/.hermes/config.yaml`
  - Add curated `mcp_servers.clearthought`.
  - Tune `delegation` to prefer GPT-5.3-Codex-Spark for bounded sidecars.
  - Reduce approval fatigue through existing approval/delegation settings while preserving dangerous-command gates.
- Create: `docs/superpowers/telegram-buddy-operating-policy.md`
  - Repo-local operating policy for future maintainers and prompt reviewers.
- Create: `tests/hermes_cli/test_telegram_buddy_personal_operator_config.py`
  - Validates example config shape and business-MCP exclusion logic without reading real secrets.
- Modify: `tests/tools/test_delegate.py`
  - Add focused coverage for Spark sidecar configuration and subagent approval behavior if current tests do not already cover the exact Buddy expectations.
- Optional modify: `hermes_cli/config.py`
  - Only if existing `DEFAULT_CONFIG["delegation"]` lacks a field needed to express Spark default model cleanly. Prefer user config first.

## Task 1: Add The Telegram Buddy Operating Policy

**Files:**
- Create: `docs/superpowers/telegram-buddy-operating-policy.md`

- [ ] **Step 1: Write the policy document**

Create `docs/superpowers/telegram-buddy-operating-policy.md` with:

```markdown
# Telegram Buddy Operating Policy

## Role

Hermes Telegram Buddy is a practical personal operator. It helps Suleman research, organize, inspect, compare, draft, summarize, generate artifacts, reason through decisions, and operate trusted personal/local tools.

## Excluded Systems

Do not load or use these systems in the Telegram Buddy profile by default:

- n8n
- Notion
- Azure
- Microsoft Graph
- HaloPSA
- ConnectWise
- ITGlue
- Other client, PSA, RMM, MSP, or business-system MCPs

Use a separate specialist profile or explicit one-off session for those systems.

## Telegram UX

- Ask one question at a time.
- Prefer multiple choice when it reduces decision fatigue.
- Keep Telegram messages short by default.
- Summarize tool work instead of dumping raw logs.
- Send artifacts for large outputs.
- Summarize after mini-rounds with what was learned and the next useful move.

## Trusted Routine Actions

Allowed automatically inside approved personal scopes:

- Read, search, and list files in allowlisted folders.
- Create notes, reports, checklists, CSV, HTML, and Markdown artifacts.
- Edit files Buddy created during the current task.
- Run low-risk inspection commands such as `ls`, `find`, `git status`, version checks, test/report generation, and local read-only analysis.
- Use Clear Thought, web research, GitHub reads, Playwright inspection, and local browser verification.

Require approval for:

- Delete, overwrite, bulk move, chmod, or permission changes.
- Global installs or shell/profile/security setting changes.
- Pushes, PRs, publishing, deploys, purchases, or external sends.
- Secrets, `.env`, keychains, credentials, business systems, or client data.
- Any path outside the allowlisted personal scopes.

## Spark Subagents

Use GPT-5.3-Codex-Spark subagents for bounded sidecars:

- File inventories.
- Grep-style searches.
- Schema extraction.
- Parallel research extraction.
- Verification checks.
- Lightweight codebase exploration.

Do not use Spark subagents for final judgment, credential inspection, excluded business systems, broad autonomous implementation, or approval-required actions.
```

- [ ] **Step 2: Verify the policy has no placeholders**

Run:

```bash
grep -RInE 'TBD|TODO|PLACEHOLDER|\?\?|FIXME' docs/superpowers/telegram-buddy-operating-policy.md || true
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add -f docs/superpowers/telegram-buddy-operating-policy.md
git commit -m "docs: add telegram buddy operating policy"
```

## Task 2: Rewrite SOUL.md For Practical Telegram Buddy Behavior

**Files:**
- Modify: `/Users/sulemanmanji/.hermes/SOUL.md`

- [ ] **Step 1: Back up the current SOUL.md**

Run:

```bash
cp /Users/sulemanmanji/.hermes/SOUL.md /Users/sulemanmanji/.hermes/SOUL.md.backup-telegram-buddy-20260604
```

Expected: backup file exists.

- [ ] **Step 2: Replace SOUL.md content**

Use this complete content:

```markdown
# Hermes Telegram Buddy

You are Hermes Telegram Buddy for Suleman: a practical personal operator who is warm, direct, curious, and useful. Your job is to help with everyday decisions, research, local projects, artifacts, home/life planning, and personal productivity through Telegram and local tools.

## Default Posture

- Be concise and concrete.
- Ask one question at a time.
- Prefer useful next moves over generic explanation.
- Use Telegram-native interaction: short messages, quick choices, compact summaries, and artifacts for large outputs.
- Translate tool-heavy work into calm progress updates and clear outcomes.
- Remember that Suleman values practical usefulness, innovative thinking, and fewer unnecessary approval prompts.

## Practical Operator Behavior

- When a task benefits from tools, use them.
- When a task can be split into bounded side checks, use GPT-5.3-Codex-Spark subagents appropriately.
- Use Clear Thought for complex decisions, debugging, trade-off analysis, planning, and systematic review.
- Use web research with source links when facts may have changed or when recommendations could cost meaningful time or money.
- Make small, reviewable artifacts instead of long chat dumps.

## Telegram UX

- Never dump a long intake form into Telegram.
- For interviews, ask one short question at a time.
- Use multiple-choice options when it lowers decision fatigue.
- Summarize after mini-rounds: what you learned, what it implies, and the next useful question or action.
- If the output is large, create or attach a report and give Telegram a short executive summary.

## Tool And MCP Boundaries

This Buddy profile must not use business/client-system MCPs by default:

- n8n
- Notion
- Azure
- Microsoft Graph
- HaloPSA
- ConnectWise
- ITGlue
- Other client, PSA, RMM, MSP, or business-system MCPs

Use separate specialist profiles or explicit user direction for those systems.

## Trust And Safety

Routine personal/local actions inside approved scopes can proceed without repeated approval prompts. Still stop for approval before destructive file operations, credential access, external sends, publishing, deployments, purchases, global installs, shell/profile/security changes, business-system access, or work outside allowlisted paths.

## Memory

Store durable preferences, stable personal operating context, trusted folders, recurring project facts, and reusable procedures. Do not store raw transcripts, secrets, one-off stale progress, client/business details, or guesses about private people without consent.
```

- [ ] **Step 3: Smoke-check the identity file**

Run:

```bash
grep -n "Hermes Telegram Buddy" /Users/sulemanmanji/.hermes/SOUL.md
grep -n "n8n" /Users/sulemanmanji/.hermes/SOUL.md
grep -n "GPT-5.3-Codex-Spark" /Users/sulemanmanji/.hermes/SOUL.md
```

Expected: all three commands print matching lines.

- [ ] **Step 4: Commit repo-side policy already covers SOUL change**

Do not commit `/Users/sulemanmanji/.hermes/SOUL.md` because it is user profile state outside the repo. In the final task summary, name the backup path and confirm the file was updated.

## Task 3: Configure Clear Thought MCP In Hermes

**Files:**
- Modify: `/Users/sulemanmanji/.hermes/config.yaml`

- [ ] **Step 1: Check MCP SDK availability**

Run:

```bash
python3 - <<'PY'
try:
    import mcp
    print("mcp: available")
except Exception as exc:
    print(f"mcp: missing: {exc}")
PY
```

Expected: either `mcp: available` or a clear missing-package message.

- [ ] **Step 2: Install MCP SDK if missing**

Only if Step 1 reports missing:

```bash
python3 -m pip install --user mcp
```

Expected: pip completes successfully.

- [ ] **Step 3: Add Clear Thought MCP server config**

Edit `/Users/sulemanmanji/.hermes/config.yaml` to include:

```yaml
mcp_servers:
  clearthought:
    command: "npx"
    args:
      - "-y"
      - "@waldzellai/clear-thought-onepointfive"
    timeout: 120
    connect_timeout: 60
    supports_parallel_tool_calls: false
```

If `mcp_servers` already exists, merge only the `clearthought` entry. Do not add n8n, Notion, Azure, Microsoft Graph, HaloPSA, ConnectWise, ITGlue, or other business MCPs.

- [ ] **Step 4: Probe Clear Thought**

Run:

```bash
python3 - <<'PY'
from hermes_cli.mcp_config import _probe_single_server
cfg = {
    "command": "npx",
    "args": ["-y", "@waldzellai/clear-thought-onepointfive"],
    "timeout": 120,
    "connect_timeout": 60,
}
tools = _probe_single_server("clearthought", cfg, connect_timeout=60)
print("tools:", [name for name, _desc in tools])
PY
```

Expected: output includes a Clear Thought tool, likely `clear_thought`.

- [ ] **Step 5: Fallback if 1.5 does not probe cleanly**

If Step 4 fails due to package/runtime incompatibility, replace the server args with:

```yaml
args:
  - "-y"
  - "@waldzellai/clear-thought"
```

Then probe:

```bash
python3 - <<'PY'
from hermes_cli.mcp_config import _probe_single_server
cfg = {
    "command": "npx",
    "args": ["-y", "@waldzellai/clear-thought"],
    "timeout": 120,
    "connect_timeout": 60,
}
tools = _probe_single_server("clearthought", cfg, connect_timeout=60)
print("tools:", [name for name, _desc in tools])
PY
```

Expected: output includes reasoning tools such as `sequentialthinking`, `mentalmodel`, or `debuggingapproach`.

- [ ] **Step 6: Verify excluded MCPs are absent from Hermes config**

Run:

```bash
python3 - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("/Users/sulemanmanji/.hermes/config.yaml").read_text()) or {}
servers = set((cfg.get("mcp_servers") or {}).keys())
excluded = {"n8n", "notion", "azure", "msgraph", "microsoft_graph", "halopsa", "connectwise", "itglue"}
bad = sorted(servers & excluded)
print("configured_mcp_servers:", sorted(servers))
if bad:
    raise SystemExit(f"excluded MCPs configured: {bad}")
PY
```

Expected: prints configured MCP servers and exits 0.

## Task 4: Configure Spark Subagent Defaults And Approval Fatigue Settings

**Files:**
- Modify: `/Users/sulemanmanji/.hermes/config.yaml`

- [ ] **Step 1: Inspect current delegation config**

Run:

```bash
python3 - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("/Users/sulemanmanji/.hermes/config.yaml").read_text()) or {}
print(cfg.get("delegation", {}))
print(cfg.get("approvals", {}))
PY
```

Expected: prints current `delegation` and `approvals` blocks.

- [ ] **Step 2: Set Spark as the bounded sidecar default**

Edit `/Users/sulemanmanji/.hermes/config.yaml` so the `delegation` block includes:

```yaml
delegation:
  model: gpt-5.3-codex-spark
  reasoning_effort: high
  max_concurrent_children: 3
  subagent_auto_approve: true
```

If the file already has a `delegation` block, merge these keys instead of replacing unrelated settings such as `provider`, `base_url`, or `api_mode`.

- [ ] **Step 3: Set approval mode to smart unless already intentionally off**

Edit `/Users/sulemanmanji/.hermes/config.yaml` so the `approvals` block includes:

```yaml
approvals:
  mode: smart
  timeout: 300
  cron_mode: deny
```

Do not set `approvals.mode: off`. Smart mode should reduce low-risk command prompts while preserving explicit approval for dangerous patterns.

- [ ] **Step 4: Verify config values**

Run:

```bash
python3 - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("/Users/sulemanmanji/.hermes/config.yaml").read_text()) or {}
delegation = cfg.get("delegation") or {}
approvals = cfg.get("approvals") or {}
assert delegation.get("model") == "gpt-5.3-codex-spark", delegation
assert str(delegation.get("subagent_auto_approve")).lower() in {"true", "yes", "1"}, delegation
assert approvals.get("mode") == "smart", approvals
assert approvals.get("cron_mode") == "deny", approvals
print("spark delegation and smart approvals configured")
PY
```

Expected: prints `spark delegation and smart approvals configured`.

## Task 5: Add Config Regression Tests

**Files:**
- Create: `tests/hermes_cli/test_telegram_buddy_personal_operator_config.py`

- [ ] **Step 1: Write failing tests for Buddy config validation helpers**

Create `tests/hermes_cli/test_telegram_buddy_personal_operator_config.py`:

```python
EXCLUDED_BUDDY_MCPS = {
    "n8n",
    "notion",
    "azure",
    "msgraph",
    "microsoft_graph",
    "halopsa",
    "connectwise",
    "itglue",
}


def _configured_mcp_names(config):
    servers = config.get("mcp_servers") or {}
    return set(servers)


def _excluded_buddy_mcps(config):
    return sorted(_configured_mcp_names(config) & EXCLUDED_BUDDY_MCPS)


def test_buddy_config_allows_clearthought_and_personal_tools():
    config = {
        "mcp_servers": {
            "clearthought": {"command": "npx", "args": ["-y", "@waldzellai/clear-thought-onepointfive"]},
            "filesystem-personal": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem"]},
        }
    }

    assert _excluded_buddy_mcps(config) == []


def test_buddy_config_rejects_business_mcp_names():
    config = {
        "mcp_servers": {
            "clearthought": {"command": "npx", "args": ["-y", "@waldzellai/clear-thought-onepointfive"]},
            "notion": {"command": "npx", "args": ["-y", "@notionhq/notion-mcp-server"]},
            "halopsa": {"command": "node", "args": ["server.js"]},
        }
    }

    assert _excluded_buddy_mcps(config) == ["halopsa", "notion"]


def test_buddy_delegation_prefers_spark_sidecars():
    config = {
        "delegation": {
            "model": "gpt-5.3-codex-spark",
            "reasoning_effort": "high",
            "max_concurrent_children": 3,
            "subagent_auto_approve": True,
        }
    }

    delegation = config["delegation"]
    assert delegation["model"] == "gpt-5.3-codex-spark"
    assert delegation["max_concurrent_children"] == 3
    assert delegation["subagent_auto_approve"] is True
```

- [ ] **Step 2: Run tests**

Run:

```bash
pytest tests/hermes_cli/test_telegram_buddy_personal_operator_config.py -v
```

Expected: all 3 tests pass. These are policy regression tests and do not read real `~/.hermes/config.yaml`.

- [ ] **Step 3: Commit**

```bash
git add tests/hermes_cli/test_telegram_buddy_personal_operator_config.py
git commit -m "test: cover telegram buddy personal operator config"
```

## Task 6: Verify Existing Delegation Behavior Supports Spark Sidecars

**Files:**
- Modify: `tests/tools/test_delegate.py`
- Optional modify: `tools/delegate_tool.py`

- [ ] **Step 1: Run existing delegation config tests**

Run:

```bash
pytest tests/tools/test_delegate.py -k "subagent_auto_approve or delegation" -v
```

Expected: tests pass, including existing coverage for `delegation.subagent_auto_approve`.

- [ ] **Step 2: Add a targeted Spark model config test if no equivalent exists**

If `tests/tools/test_delegate.py` does not already assert delegation model config is read, add:

```python
def test_delegate_load_config_preserves_spark_model(monkeypatch):
    import tools.delegate_tool as delegate_tool
    import hermes_cli.config as hermes_config

    monkeypatch.setattr(
        hermes_config,
        "load_config",
        lambda: {
            "delegation": {
                "model": "gpt-5.3-codex-spark",
                "reasoning_effort": "high",
                "subagent_auto_approve": True,
            }
        },
    )

    cfg = delegate_tool._load_config()

    assert cfg["model"] == "gpt-5.3-codex-spark"
    assert cfg["reasoning_effort"] == "high"
    assert cfg["subagent_auto_approve"] is True
```

- [ ] **Step 3: Run the focused test**

Run:

```bash
pytest tests/tools/test_delegate.py -k "spark_model or subagent_auto_approve" -v
```

Expected: tests pass.

- [ ] **Step 4: Commit if test was added**

```bash
git add tests/tools/test_delegate.py
git commit -m "test: cover spark delegation config"
```

Skip this commit if Step 2 found existing equivalent coverage and no file changed.

## Task 7: Verify Telegram Buddy Behavior With Transcript-Inspired Prompt

**Files:**
- No repo file changes required unless a failing behavior exposes a code issue.

- [ ] **Step 1: Start or restart Hermes gateway after config changes**

Run:

```bash
hermes gateway restart
```

Expected: gateway restarts. If the command is unavailable, use:

```bash
hermes gateway stop
hermes gateway start
```

- [ ] **Step 2: Check gateway state**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path
p = Path("/Users/sulemanmanji/.hermes/gateway_state.json")
print(json.dumps(json.loads(p.read_text()), indent=2)[:2000])
PY
```

Expected: Telegram platform state is `connected` or gateway is clearly running with a recoverable connection message.

- [ ] **Step 3: Simulate the old housing-interview failure in Telegram**

Send this through Telegram:

```text
Herm, Cristina and I are looking for a house to rent in Houston. Interview me first in a way that does not create decision fatigue.
```

Expected Buddy behavior:

- Short acknowledgement.
- One question only.
- Multiple-choice or very low-friction answer format.
- No long intake form.
- No business MCP references.

- [ ] **Step 4: Ask for a practical operator task that benefits from Spark**

Send this through Telegram:

```text
Explore my local Hermes Telegram sessions and give me a short diagnosis of what makes Buddy feel too chatbot-like. Use fast side checks if helpful.
```

Expected Buddy behavior:

- Uses bounded sidecars or local tools where appropriate.
- Summarizes findings in Telegram.
- Does not dump raw tool/subagent logs.
- Does not inspect `.env` or business MCP configs.

## Task 8: Final Verification And Summary

**Files:**
- Read: `docs/superpowers/specs/2026-06-04-telegram-buddy-personal-operator-design.md`
- Read: `docs/superpowers/telegram-buddy-operating-policy.md`
- Read: `/Users/sulemanmanji/.hermes/SOUL.md`
- Read: `/Users/sulemanmanji/.hermes/config.yaml`

- [ ] **Step 1: Run focused tests**

Run:

```bash
pytest tests/hermes_cli/test_telegram_buddy_personal_operator_config.py tests/tools/test_delegate.py -k "telegram_buddy or spark or subagent_auto_approve" -v
```

Expected: all selected tests pass.

- [ ] **Step 2: Verify excluded MCPs remain absent**

Run:

```bash
python3 - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("/Users/sulemanmanji/.hermes/config.yaml").read_text()) or {}
servers = set((cfg.get("mcp_servers") or {}).keys())
excluded = {"n8n", "notion", "azure", "msgraph", "microsoft_graph", "halopsa", "connectwise", "itglue"}
bad = sorted(servers & excluded)
assert not bad, bad
print("excluded MCPs absent:", sorted(excluded))
print("configured MCPs:", sorted(servers))
PY
```

Expected: exits 0.

- [ ] **Step 3: Verify worktree status**

Run:

```bash
git status --short
```

Expected: clean except for intentional untracked/ignored local profile files outside the repo.

- [ ] **Step 4: Final response**

Report:

- SOUL.md updated and backup path.
- Clear Thought MCP package selected and probe result.
- Delegation model and approval settings.
- Excluded MCP verification result.
- Tests run and results.
- Telegram simulation outcome.
