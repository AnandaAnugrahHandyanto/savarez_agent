# CLAUDE.md (project template)

<!-- provenance: genericized from Motion-Granted-Production/CLAUDE.md -->
<!--
  USAGE: This is a TEMPLATE for the CLAUDE.md you will place at the root of a project
  that adopts tanner-stack. When you vendor tanner-stack into a project, copy this file
  to the project root as `CLAUDE.md` and fill in the slots (inviolable rules, project
  essentials, commands, dead-code paths, GitNexus index name). The root CLAUDE.md at
  the top of tanner-stack itself is the orientation doc for anyone working inside this
  repo — it is NOT this template.
-->

## Active Branch

Run `git branch --show-current` before any file edits.
Never commit to `main`, `master`, or any branch marked as production/live.
The operator owns production merges.

## Inviolable Rules

_Replace these placeholders with your project's non-negotiable constraints. Each rule should be specific, greppable, and testable._

1. **[Rule 1 — Cardinal Sin]**: [What must never happen from an error/catch path.]
2. **[Rule 2]**: [Missing required field = FAIL LOUD. No silent defaults.]
3. **[Rule 3]**: [What must never appear in customer-facing output.]
4. **[Rule 4]**: [Config values must come from a single source of truth — never hardcoded.]
5. **[Rule 5]**: [Schema before code. Migrations deploy before code changes. Always.]

_See `.claude/rules/` for domain-specific rules._

## Session Defaults

- Default effort: high. Escalate to max for architecture decisions and hard debugging.
- Before every edit: confirm you're on the right branch.
- After every claim: grep the actual code.

## Project

_Fill in your project's essentials. Keep this short — it's the first thing an agent reads._

- **What it is**: [One line describing the product]
- **Stack**: [Key technologies]
- **Deploy**: [How and where]
- **Key config**: [Source-of-truth config files — models, registry, tier config, etc.]

## Commands

_Fill in your project's common commands._

```bash
# Dev server
# Build
# Type check (run after every edit)
# Test suite
```

## DO NOT Edit — Dead Code

_Paths that are dead code, superseded, or read-only. Claude Code must never edit these._

- `{path/to/dead/file}` — DEAD. Live equivalent: `{path/to/live/file}`
- `{path/to/production-live-repo/}` — READ ONLY. Never the edit target.

## Patterns

- Before editing any file, grep-verify it's on the live execution path: `grep -r "import.*from.*{filename}" {source_dir}/`
- Use the project logger — not `console.log`
- All DB writes must be idempotent
- Do not browse large directories whole — use grep/glob
- Do not create framework config files that conflict with existing ones (e.g., Tailwind v4 uses CSS config, not `tailwind.config.js`)

## Line Endings

If your Edit tool appears to silently fail with no error, check line endings: `file <filename>`. CRLF line terminators cause silent no-ops in Claude Code's Edit tool. Fix with `dos2unix <filename>`. Set `git config --global core.autocrlf input` permanently.

## Verification

After every edit: run your type checker or build. After every claim: grep the actual code.

Historical false positive rate in AI audits: **38–54%**. Grep before you trust any finding.

## Compaction

When compacting, ALWAYS preserve:
- Current branch name and git status
- All modified files this session
- The active task or constraint being implemented
- Current error/stack trace being debugged
- Any grep evidence collected

## Out-of-Scope Issues

When you discover a bug, tech debt, cleanup opportunity, or improvement **outside the current task's scope**, add it to @BACKLOG.md instead of fixing it:

```
- [ ] **Title** — One-line description.
  _Found: YYYY-MM-DD | Context: what you were doing_
```

Do NOT expand scope. Do NOT fix it inline. Log it and move on.

## References

See @PROGRESS.md for current implementation status.
See @LEARNINGS.md for known pitfalls and hard-won lessons.
See @BACKLOG.md for out-of-scope issues found during sessions.
See `.claude/rules/` for domain-specific rules.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

_Replace `YOUR_REPO_NAME` everywhere below with your GitNexus index name (the name you passed to `npx gitnexus analyze`)._

This project is indexed by GitNexus as **YOUR_REPO_NAME**. Use the GitNexus MCP tools to understand code, assess impact, and navigate safely before editing.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the operator.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the operator** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/YOUR_REPO_NAME/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "functionName"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/YOUR_REPO_NAME/context` | Codebase overview, check index freshness |
| `gitnexus://repo/YOUR_REPO_NAME/clusters` | All functional areas |
| `gitnexus://repo/YOUR_REPO_NAME/processes` | All execution flows |
| `gitnexus://repo/YOUR_REPO_NAME/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## CLI

- Re-index: `npx gitnexus analyze`
- Check freshness: `npx gitnexus status`
- Generate docs: `npx gitnexus wiki`

<!-- gitnexus:end -->
