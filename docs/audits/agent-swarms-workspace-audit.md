# Agent Swarms Workspace Audit

Date: 2026-05-12
Audited root: `/Users/officemacmini/.hermes/hermes-agent`

I treated the current Hermes Agent checkout as the "agent swarms workspace" because no dedicated `agent-swarms` directory exists under `~/.hermes/projects` or the current repo, and this session is running from the Hermes Agent workspace.

## Coverage

Scanned the repository excluding common dependency/runtime directories: `.git`, `venv`, `.venv`, `node_modules`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `dist`, `build`, `.next`, and `coverage`.

- Files counted: 3,355
- Text files read: 3,168
- Source summary: 3,142 files, 1,240,676 lines
- Tests counted: 1,064
- Skill files: 167
- Hook-related files: 62
- Guardrail/security-related files: 60
- Harness/test/eval-related files: 1,146

Top-level file distribution:

- `tests`: 1,057 files
- `skills`: 532 files
- `website`: 367 files
- `ui-tui`: 318 files
- `optional-skills`: 255 files
- `plugins`: 159 files
- `web`: 112 files
- `tools`: 103 files
- `hermes_cli`: 96 files
- `gateway`: 63 files
- `agent`: 60 files

## Verification run

Targeted guardrail harness passed:

```txt
python -m pytest \
  tests/agent/test_tool_guardrails.py \
  tests/tools/test_tirith_security.py \
  tests/tools/test_approval.py \
  tests/agent/test_shell_hooks_consent.py \
  tests/agent/test_prompt_builder.py \
  -q -o 'addopts='

373 passed, 1 skipped in 2.24s
```

## Key findings

### 1. High: client-specific Charity Charge assets are sitting untracked in the core Hermes repo

Evidence from `git status --short`:

```txt
?? charity-charge-brand.zip
?? charity-charge-brand/
```

Evidence from size/listing:

```txt
136K charity-charge-brand
80K  charity-charge-brand.zip
16 files under charity-charge-brand/
```

Why this matters:

- This is project-specific context living inside the global Hermes Agent source tree.
- It risks accidental commit, accidental context loading during repo work, and confusing future agents about whether Charity Charge is part of core Hermes.
- It duplicates the separate dedicated Charity Charge workspace pattern already present under `~/.hermes/projects/charity-charge`.

Recommended fix:

- Move `charity-charge-brand/` and `charity-charge-brand.zip` out of this repo, ideally into `/Users/officemacmini/.hermes/projects/charity-charge/brand-kit/` if not already there.
- Add a repo-level ignore for `charity-charge-brand/` and `charity-charge-brand.zip` if they may recur.

### 2. Medium-high: `AGENTS.md` is useful but too large to be a default always-loaded context file

Evidence:

- `AGENTS.md`: 989 lines, 45,991 bytes.
- It contains valuable contributor guidance, but it is broad enough that every repo-scoped agent run pays a context tax before knowing which subsystem matters.

What is good:

- It identifies load-bearing files and architecture.
- It explicitly says the filesystem is canonical, avoiding stale tree reliance.
- It includes critical safety notes around config/secrets and tool usage.

Risk:

- Default context injection of a nearly 1,000-line file increases token usage and raises the chance that unrelated subsystem guidance competes with task-specific instructions.

Recommended fix:

- Keep `AGENTS.md`, but slim the default file to a 150-250 line routing map.
- Move long subsystem guidance into `docs/agent-guides/*.md` or `references/*.md`.
- Add a small "load these when needed" table at the top.

### 3. Medium: guardrails exist, but hard loop-stops are disabled in live config

Current config snapshot:

```json
{
  "tool_loop_guardrails": {
    "warnings_enabled": true,
    "hard_stop_enabled": false,
    "warn_after": {
      "exact_failure": 2,
      "same_tool_failure": 3,
      "idempotent_no_progress": 2
    },
    "hard_stop_after": {
      "exact_failure": 5,
      "same_tool_failure": 8,
      "idempotent_no_progress": 5
    }
  }
}
```

Code evidence:

- `agent/tool_guardrails.py` implements warning and hard-stop decisions.
- `hard_stop_enabled` gates the actual blocking behavior.

Risk:

- Warnings reduce wasted tokens only if the model listens. Hard stops are the actual circuit breaker against repeated failed/no-progress tool loops.

Recommended fix:

- For Discord and long-running gateway contexts, enable hard stops after a short soak period:

```bash
hermes config set tool_loop_guardrails.hard_stop_enabled true
```

- Keep thresholds as currently configured unless testing shows false positives.

### 4. Medium: agent-created skill scanning is available but disabled

Current config snapshot:

```json
{
  "skills": {
    "guard_agent_created": false,
    "inline_shell": false,
    "external_dirs": [],
    "disabled": []
  }
}
```

Code evidence:

- `tools/skills_guard.py` contains a strong threat scanner for exfiltration, prompt injection, destructive commands, persistence, network tunnels, obfuscation, etc.
- It notes `agent-created` behavior is only active when `skills.guard_agent_created` is enabled.

Risk:

- Agent-authored skills can become persistent instructions and tool recipes. If a bad or bloated procedure is saved, it can re-enter future sessions.
- External skill install is guarded, but local agent-created skills are the place where accidental bloat and hidden context most often creep in.

Recommended fix:

```bash
hermes config set skills.guard_agent_created true
```

### 5. Medium: Tirith security is enabled but fail-open

Current config snapshot:

```json
{
  "security": {
    "redact_secrets": true,
    "tirith_enabled": true,
    "tirith_fail_open": true
  }
}
```

What is good:

- Secret redaction is on.
- Tirith is enabled.
- Approval mode is manual and cron mode is deny.

Risk:

- `tirith_fail_open: true` means a failure in the security classifier allows execution instead of blocking. That is good for availability, weaker for high-risk automation.

Recommended fix:

- If this workspace is used for autonomous / multi-agent runs, consider fail-closed for safer operations:

```bash
hermes config set security.tirith_fail_open false
```

- If availability matters more than strict blocking, keep fail-open but add a periodic `hermes doctor` or startup check that confirms Tirith is reachable.

### 6. Medium: Discord toolset is broad, which is powerful but token-heavy

Current Discord platform toolsets include:

```txt
browser, clarify, code_execution, computer_use, cronjob, delegation, file,
image_gen, kanban, memory, messaging, session_search, skills, terminal,
todo, tts, vision, web
```

Risk:

- This is maximum-capability mode. It is great for Salty's operator style, but it increases tool schema footprint and the chance of expensive exploratory behavior.

Recommended fix:

- Keep broad tools for `#chat` if desired.
- For project-specific channels or worker profiles, use narrower profiles/toolsets.
- For cron jobs, continue using job-level `enabled_toolsets`; the repo has support for it and documentation in `cron/jobs.py` and `cron/scheduler.py`.

### 7. Low-medium: optional skills contain massive reference files

Largest text/context-relevant files:

- `optional-skills/mlops/training/unsloth/references/llms-full.md`: 16,800 lines, 1.08 MB
- `optional-skills/mlops/training/unsloth/references/llms-txt.md`: 12,045 lines, 813 KB
- `optional-skills/mlops/training/axolotl/references/api.md`: 5,549 lines
- `optional-skills/mlops/pytorch-fsdp/references/other.md`: 4,262 lines

What is good:

- They live in `optional-skills`, not active default skills.
- Supporting files are not injected automatically by slash skill invocation; they are listed and loaded on demand via `skill_view(file_path=...)`.

Risk:

- If a skill tells the agent to read entire reference files, it can waste a lot of context quickly.

Recommended fix:

- Add or enforce a convention in large optional skills: every huge reference should have a short `references/index.md` or `references/summary.md` with routing instructions.
- Prefer chunked `read_file(offset, limit)` reads for these files.

### 8. Low: built dashboard/static assets are correctly ignored, but present in the working tree

Large present files include:

- `hermes_cli/web_dist/assets/index-CKodqInF.js`: 1.56 MB
- `hermes_cli/web_dist/ds-assets/filler-bg0.jpg`: 3.87 MB
- `web/public/ds-assets/filler-bg0.jpg`: 3.87 MB

What is good:

- `.gitignore` excludes `hermes_cli/web_dist/`, `web/public/fonts/`, and `web/public/ds-assets/`.

Risk:

- Low repo risk, but they can pollute naive file scans if tools do not honor ignore rules.

Recommended fix:

- Audit scripts and agents should skip ignored/generated asset dirs by default.

## Guardrail and harness inventory

Present and healthy:

- Context injection scanner in `agent/prompt_builder.py` blocks suspicious `AGENTS.md`, `.cursorrules`, and similar context-file patterns.
- Tool-use enforcement and execution discipline are injected for GPT/Codex/Gemini/Gemma/Grok-like models.
- Tool loop guardrail controller exists in `agent/tool_guardrails.py`.
- Shell hooks are consent-gated via `~/.hermes/shell-hooks-allowlist.json` and run with `shell=False`.
- Skill guard exists in `tools/skills_guard.py`.
- Approval mode is manual, cron approvals deny by default.
- Secret redaction is enabled.
- Context compression is enabled with `threshold=0.5`, `target_ratio=0.2`, `protect_last_n=20`, and `hygiene_hard_message_limit=400`.
- Cron supports per-job `enabled_toolsets`, `workdir`, `no_agent`, and disables recursive cron/messaging/clarify in agent jobs.

Needs tightening:

- Enable `tool_loop_guardrails.hard_stop_enabled`.
- Enable `skills.guard_agent_created`.
- Decide whether Tirith should fail-closed for this workspace.
- Remove client-specific untracked Charity Charge files from the Hermes repo.
- Slim default `AGENTS.md` to a routing map.

## Prioritized fix list

### P0, do now

1. Move or delete untracked `charity-charge-brand/` and `charity-charge-brand.zip` from the Hermes Agent repo.
2. Add ignore rules for those exact paths if they may be regenerated.

### P1, next

3. Enable agent-created skill guard:
   `hermes config set skills.guard_agent_created true`
4. Enable tool loop hard stops:
   `hermes config set tool_loop_guardrails.hard_stop_enabled true`
5. Slim `AGENTS.md` default load path and move detail to referenced docs.

### P2, soon

6. Add summaries/indexes to large optional-skill reference directories.
7. Add a workspace audit script under `scripts/` that produces this inventory automatically and honors skip dirs.
8. Consider `security.tirith_fail_open false` for autonomous worker profiles.

## Bottom line

The workspace has real guardrails and test coverage. The most important issues are not missing safety infrastructure; they are operational hygiene: client context accidentally sitting in the core repo, large always-loaded guidance, and two protective switches that exist but are not fully engaged.
