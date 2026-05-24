# Hermes Agent — Claude Code Project Context

Native context file for Claude Code CLI. Full developer guide is in AGENTS.md.
This file covers Claude Code-specific operating rules. Read AGENTS.md first for
architecture, file structure, and conventions.

## Quick Reference

```bash
# Activate environment
source .venv/bin/activate          # or: source venv/bin/activate

# Run tests (ALWAYS use the wrapper — never bare pytest)
scripts/run_tests.sh                           # full suite
scripts/run_tests.sh tests/gateway/ -q         # one directory
scripts/run_tests.sh tests/agent/test_foo.py::test_bar  # one test

# Key entry points
run_agent.py        # AIAgent class and conversation loop
model_tools.py      # tool orchestration, handle_function_call()
cli.py              # HermesCLI — interactive CLI (~11k LOC)
tools/              # all tool implementations (auto-discovered)
gateway/run.py      # messaging gateway main loop
hermes_cli/commands.py  # slash command registry (COMMAND_REGISTRY list)
```

## Mandatory Task Workflow

For any change > ~10 lines or touching > 1 file, follow these steps in order:

1. **INSPECT** — read the files you will touch; run `git status`
2. **PLAN** — state what you will change and why, before writing
3. **IMPLEMENT** — make changes; commit atomically (one logical change per commit)
4. **TEST** — `scripts/run_tests.sh [test/path] -q`; verify no regressions
5. **REVIEW** — `git diff HEAD~N..HEAD`; confirm no unintended changes
6. **SUMMARIZE** — report changed files, test result (N passed / M failed), caveats

## Verification Gates

| Gate | Command | Pass condition |
|------|---------|----------------|
| Pre-flight | `git status` + `scripts/run_tests.sh -q 2>&1 \| tail -3` | Baseline established |
| Post-implement | `scripts/run_tests.sh [changed test paths] -q` | Targeted tests pass |
| Regression | `scripts/run_tests.sh -q` | No new failures vs baseline |
| Pre-commit | `git diff --stat HEAD` | Only expected files changed |

## Claude Code Operating Rules

### Context management
- Run `/context` to check context window usage before starting large tasks
- At 70%: write a handoff checkpoint to `.hermes/handoff/agent-<date>.md`
- At 85%: write checkpoint, commit in-progress work, stop and hand off
- Use `/compact` proactively; CLAUDE.md content survives compaction
- Session resumption: `claude --resume <session_id>` or `claude --continue`

### Permissions and safety
- Use `--allowedTools Read,Edit` for reviews; `Read,Write,Bash` for implementation
- Do NOT run: `rm -rf`, `git reset --hard`, `git clean -fdx`, `git push --force`
- Do NOT pipe `curl`/`wget` directly to bash
- Before any destructive command: name the target path explicitly in output
- Dependency additions require upper-bound pins; run `uv lock` after pyproject.toml edits

### Multi-agent patterns
- For parallel work: use `claude -w <name>` per task (creates `.claude/worktrees/<name>`)
- Serial rule: migration files and shared manifests (`pyproject.toml`, `uv.lock`) — ONE agent only
- After an implementer completes: an independent reviewer reads the diff before merge
- Self-reports are not verified — always cross-check claims against actual tool output (exit codes, diffs)

### Print mode (for Hermes orchestration)
```bash
# Preferred for automation — no dialogs, structured output.
# Run this from the repo root, or set the orchestrator/tool workdir to the repo root.
claude -p "task description" --allowedTools "Read,Edit" --max-turns 10 \
  --output-format json
```
Key flags: `--max-turns` (required in -p mode), `--output-format json` for
structured results, `--resume <id>` to continue a previous session. Claude Code
uses the current working directory; it does not have a `--workdir` flag.

### When to stop and ask
- Ambiguous scope (e.g. "refactor X" without specifying boundaries)
- Any irreversible operation (data deletion, force-push, dropping tables)
- Reviewer returns FAIL and the fix is non-obvious
- Test suite drops from N passing to 0 (catastrophic regression)

## Critical Invariants (must not break)

- `get_hermes_home()` from `hermes_constants` — never hardcode `~/.hermes`
- `display_hermes_home()` for user-facing messages — never bare `~/.hermes`
- Prompt caching: do NOT alter past context, toolsets, or system prompt mid-conversation
- Slash commands: all defined in `COMMAND_REGISTRY` in `hermes_cli/commands.py` — one place
- New tools need registration in both `tools/<name>.py` AND `toolsets.py`
- Plugins MUST NOT modify core files (`run_agent.py`, `cli.py`, `gateway/run.py`)
- Tests must not write to real `~/.hermes/` — the `_isolate_hermes_home` autouse fixture handles this
- Never use `simple_term_menu` for new interactive menus (use `hermes_cli/curses_ui.py`)
- All new deps need upper-bound pins; run `uv lock` after changes

## Key Policies (summary — full text in AGENTS.md)

- Dependency pinning: `>=floor,<next_major` for PyPI; commit SHA for git URLs (post-litellm-compromise policy)
- No new in-tree memory providers under `plugins/memory/` (closed set; new ones go to standalone repos)
- No change-detector tests (no snapshot asserts on catalogs, version literals, or enumeration counts)
- Squash merges from stale branches silently revert recent fixes — rebase on main first

## Full Details

See AGENTS.md for:
- Complete project structure and file dependency chain
- AIAgent class API and agent loop internals
- CLI architecture and slash command registry
- TUI architecture (ui-tui + tui_gateway)
- Adding tools, config, plugins, skills
- Dependency pinning policy
- Profile and HERMES_HOME rules
- Known pitfalls (hardcoded paths, ANSI escape leaks, gateway message guards, etc.)
- Full test suite guidance and anti-patterns
