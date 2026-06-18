---
title: "Documentation Maintainer"
sidebar_label: "Documentation Maintainer"
description: "Audit and repair codebase documentation drift: compare docs to source, make small high-confidence docs fixes, and verify docs/tests"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Documentation Maintainer

Audit and repair codebase documentation drift: compare docs to source, make small high-confidence docs fixes, and verify docs/tests.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/software-development/documentation-maintainer` |
| Version | `1.0.0` |
| Author | Hermes Agent |
| License | MIT |
| Platforms | linux, macos, windows |
| Tags | `documentation`, `docs`, `maintenance`, `drift`, `automation`, `codebase` |
| Related skills | [`hermes-agent`](/docs/user-guide/skills/bundled/autonomous-ai-agents/autonomous-ai-agents-hermes-agent), [`systematic-debugging`](/docs/user-guide/skills/bundled/software-development/software-development-systematic-debugging), [`test-driven-development`](/docs/user-guide/skills/bundled/software-development/software-development-test-driven-development), [`requesting-code-review`](/docs/user-guide/skills/bundled/software-development/software-development-requesting-code-review) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Documentation Maintainer

## Overview

Use this skill when acting as a documentation maintenance agent for a codebase. The job is to keep documentation aligned with the source of truth in code, tests, configuration, CLI behavior, and generated catalogs.

The maintainer should make small, safe documentation repairs without creating product-code churn. Treat code and tests as the source of truth; treat documentation as the artifact to reconcile unless the investigation proves the docs are correct and the code is broken.

Documentation should behave like a build artifact: generated or refreshed from repository evidence, versioned with the code it describes, and safe for both humans and agents to use as a navigation map. The goal is not just typo-fixing; it is keeping a living system map current.

## When to Use

Use this skill for:
- Scheduled documentation drift checks.
- Reviewing recent code changes for missing or stale docs.
- Fixing stale commands, option names, config keys, tool names, routes, feature descriptions, or setup instructions.
- Updating generated documentation only through its generator when the repo has one.
- Refreshing structured codebase wiki pages such as overview, architecture, tech stack, project structure, entry points, systems, features, contribution guide, and references.
- Producing a concise report of checked areas when no safe edit is available.

Do not use this skill for:
- Large documentation rewrites without user direction.
- Marketing copy or new conceptual docs that require product decisions.
- Product-code changes, except tiny generator/test fixture updates that are necessary to keep docs generation working.
- Publishing, committing, pushing, or opening PRs unless explicitly asked.

## Operating Loop

### Scheduled-run architecture

- Prefer scheduling through the `documentation-maintainer` automation blueprint rather than creating an ad-hoc cron job by hand.
- Provide the repository path when setting up the blueprint; Hermes stores it as the cron job `workdir`, so the run loads the repo's context files and terminal/file tools execute against the intended checkout.
- The blueprint intentionally narrows the scheduled agent to the `terminal` and `file` toolsets. It should inspect, edit, and verify the repository, not browse the web or call unrelated integrations during routine docs maintenance.
- The bundled skill alone is not auto-scheduled. Installing it only makes the operating procedure available; the user must opt in through the blueprint or an explicit cron job.

1. Prepare the workspace.
   - Run `git status --short --branch` before doing anything else.
   - The run must be on latest `origin/main`. If the tree is clean, run `git fetch origin main` and `git checkout main && git pull --ff-only`. If local changes block this, stop and report the blocker rather than auditing stale code.
   - Run Auggie workspace indexing before codebase retrieval, from the repository root: `auggie --print --wait-for-indexing --workspace-root "$PWD" -i "Index this workspace for documentation maintenance. Do not edit files."`
   - Run CocoIndex before the docs audit. Prefer the repo's documented CocoIndex command if present; otherwise try `cocoindex update` / `cocoindex index` or `coco index`. If CocoIndex is unavailable, stop and report that the preflight cannot complete.

2. Establish scope.
   - Read the user's requested focus if present.
   - If running as a cron job, use the job prompt as the focus and assume the repository root is the working directory.

3. Find the source of truth.
   - Use `search_files` to locate relevant code, tests, config defaults, CLI command registries, schemas, generated-doc scripts, and existing docs.
   - Use `read_file` on the exact files before editing.
   - Do a two-pass scan:
     1. Structural scan: README, package manifests, config defaults, CI workflows, docs index/sidebar, entry points, route registries, command registries, and generated-doc scripts.
     2. Semantic scan: API routes, service classes, data models/schemas, database migrations, feature flags, platform adapters, user-facing command examples, and tests that encode behavior.
   - For Hermes-Agent, common source-of-truth files include:
     - `hermes_cli/commands.py` for slash/CLI command registry.
     - `hermes_cli/config.py` for default config and env metadata.
     - `toolsets.py` and `tools/registry.py` for tool exposure.
     - `cron/blueprint_catalog.py` and `tools/blueprints.py` for automation docs.
     - `website/scripts/` for generated Docusaurus pages.
     - `AGENTS.md` for developer-facing policy.

4. Compare docs against code.
   - Check names, flags, config keys, env var names, paths, schedules, command examples, setup flows, supported platforms, and generated catalogs.
   - Prefer verifying behavior with tests or a harmless command over inferring from names.
   - If documentation and code disagree, identify the exact code line or test that proves the intended behavior.
   - Maintain an evidence ledger while working: every proposed doc edit should be backed by at least one source path and, when possible, a test or harmless command.

5. Refresh the codebase map.
   - Ensure the docs answer the questions a new engineer or agent needs on day one:
     - What are the major components and how are they composed?
     - What are the request/control/data flows through the system?
     - What are the entry points, CLIs, services, adapters, and generated artifacts?
     - Where should a contributor make common changes?
     - What has changed since the previous documented commit or docs run?
   - Prefer targeted updates to existing pages. If a repo has a generated wiki/docs tree, update through the generator. If no page exists and the gap is clearly source-grounded, create the smallest useful page and wire it into the docs index/sidebar.

6. Edit narrowly.
   - Touch only documentation or generator/test files required for documentation correctness.
   - Keep the user's wording style and the surrounding document structure.
   - Do not reformat whole files.
   - Do not introduce new user-facing environment variables for non-secret settings.
   - In Hermes-Agent docs, use `get_hermes_home()` / `display_hermes_home()` language when documenting profile-scoped paths.

7. Verify.
   - Run the narrowest relevant check first.
   - For Hermes-Agent, prefer `scripts/run_tests.sh` over direct `pytest`.
   - If a generated docs script was touched, run that script or its test.
   - If website docs were touched, run the relevant website script/test when practical.

8. Report.
   - Summarize changed files with path references.
   - State what source-of-truth files were checked.
   - Include the evidence ledger: source paths, generated-doc inputs, and tests/commands used to justify edits.
   - Include the exact verification command and result.
   - If no edit was safe, say what was checked and why no change was made.

## Safe Fix Patterns

- Command drift: registry says `/foo --bar`, docs say `/foo --baz`; update docs and command examples.
- Config drift: `DEFAULT_CONFIG` has `section.key`, docs refer to removed `HERMES_OLD_KEY`; update docs to `hermes config set section.key ...`.
- Generated catalog drift: source catalog changed; run or fix the generator instead of hand-editing generated output.
- Codebase map drift: a new service/entry point/route exists but the architecture or project-structure docs do not mention it; add a concise source-grounded section with source-path references.
- Link drift: move or rename links only after locating the target file.
- Feature capability drift: tests or adapter code prove a platform does not support a claimed behavior; update support wording precisely.

## Pitfalls

1. Do not run against a stale branch. Latest `origin/main` plus completed Auggie and CocoIndex indexing are mandatory preflights.
2. Do not guess based on old documentation. Trace the current code.
3. Do not turn a documentation maintenance run into a feature implementation.
4. Do not hide uncertainty. If source-of-truth is ambiguous, report the ambiguity instead of inventing docs.
5. Do not edit secrets, `.env`, credentials, or private local notes as part of docs maintenance.
6. Do not break prompt caching by trying to mutate current-session skills/tools; scheduled jobs should load this skill at job start.

## Verification Checklist

- [ ] Latest `origin/main` checked out or a blocker reported.
- [ ] Auggie indexing completed from the repository root.
- [ ] CocoIndex completed, or missing/unavailable CocoIndex was reported as a blocker.
- [ ] Structural and semantic scans completed for the requested focus.
- [ ] Evidence ledger ties each edit to source paths/tests/commands.
- [ ] Each edited statement was traced to current code, tests, or generated source.
- [ ] Only documentation/generator/test files necessary for docs correctness changed.
- [ ] Relevant docs generation or tests ran successfully, or a blocker is reported clearly.
- [ ] Final response cites changed files and verification output.
