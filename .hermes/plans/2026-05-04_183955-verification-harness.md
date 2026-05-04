# Hermes Worker Verification Harness Implementation Plan

> For Hermes: Use subagent-driven-development skill to implement this plan task-by-task after Callum approves scope.

Goal: Build a lightweight verification harness so coding workers cannot honestly report success without machine-readable evidence: tests run, UI/browser/simulator evidence captured where relevant, artifacts stored, and summary visible to Hermes/UI.

Architecture: Start as a local CLI/library inside Hermes Agent, not a giant new service. The harness should accept a repo path plus task type, discover repo verification commands, run checks, capture evidence artifacts, and write a JSON + markdown verification report. Hermes/Codex prompts can then require workers to call it before final response.

Tech Stack: Python for harness CLI/library, pytest for unit tests, existing Hermes web/API later for visibility, Playwright/browser tooling only once the core report format is stable.

---

## Current context / assumptions

- Brain source: `/Users/cal/dev/brain/research/x-bookmarks-agent-orchestration.md`
- Strongest bookmark signal: agents improve when they have durable context, a harness, and real verification loops.
- Repo routing source: `/Users/cal/dev/orca/hermes/repo-families.yaml`
- Main reference architecture: `program-mobile-backend` family.
- Callum wants honest verification, not workers judging taste.
- Callum remains final authority on whether UI/product work is satisfactory.
- Existing Hermes repo: `/Users/cal/.hermes/hermes-agent`
- Existing Orca repo: `/Users/cal/dev/orca`

## Non-goals for v1

- Do not build a full CI replacement.
- Do not make monitor agents decide taste.
- Do not add a huge dashboard first.
- Do not require every repo to adopt new config before basic verification works.
- Do not restart Hermes gateway as part of implementation unless Callum explicitly approves.

## Acceptance criteria for v1

A worker can run one command like:

```bash
hermes verify --repo /path/to/repo --task-type web-ui --output /tmp/verification
```

And get:

- `verification.json` with status, repo path, git SHA/branch, commands run, exit codes, artifact paths, and honest limitations.
- `verification.md` with a short human-readable summary.
- test/lint command evidence when repo conventions are known.
- screenshot/browser evidence for web UI when a URL is provided.
- explicit `not_run` entries when evidence was expected but unavailable.
- non-zero exit if required checks fail.

## Proposed v1 check types

1. repo_state
   - git branch
   - git SHA
   - dirty diff summary
   - changed files

2. command_checks
   - discover from repo config or repo-family map
   - run fast verification commands only by default
   - record command, cwd, exit code, duration, stdout/stderr tail

3. web_ui_evidence
   - optional in v1 behind `--url`
   - load page with Playwright or existing browser tooling if available
   - capture screenshot
   - optionally collect console errors

4. mobile_evidence
   - v1: report `not_run` unless repo provides command
   - v1.5: Expo/iOS simulator/Maestro integration

5. final_report
   - machine-readable JSON
   - markdown summary
   - status: `passed`, `failed`, `partial`, `not_run`

---

# Task 1: Add verification report data model

Objective: Create stable Python objects for verification reports before adding runners.

Files:
- Create: `hermes_cli/verification/__init__.py`
- Create: `hermes_cli/verification/report.py`
- Test: `tests/verification/test_report.py`

Steps:
1. Write failing pytest for constructing a report with one passed command check.
2. Verify failure with:
   `./venv/bin/python -m pytest tests/verification/test_report.py -q -o 'addopts='`
3. Implement dataclasses or pydantic-free plain Python structures:
   - `VerificationReport`
   - `VerificationCheck`
   - `VerificationArtifact`
4. Add JSON serialization.
5. Add markdown serialization.
6. Run the test and verify pass.

Expected behavior:
- JSON includes `status`, `repo`, `branch`, `sha`, `checks`, `artifacts`, `limitations`.
- Markdown is short and readable in terminal.

# Task 2: Add repo state collector

Objective: Capture git state so verification evidence is tied to exact code.

Files:
- Create: `hermes_cli/verification/repo_state.py`
- Test: `tests/verification/test_repo_state.py`

Steps:
1. Write failing tests using a temp git repo.
2. Collect branch, SHA, dirty flag, and changed files.
3. Handle non-git dirs gracefully as `partial` with limitation.
4. Verify with pytest.

Commands:
- `git rev-parse --abbrev-ref HEAD`
- `git rev-parse HEAD`
- `git status --short`

# Task 3: Add command runner with evidence capture

Objective: Run verification commands and preserve outputs without flooding final responses.

Files:
- Create: `hermes_cli/verification/commands.py`
- Test: `tests/verification/test_commands.py`

Steps:
1. Write failing test for a passing command.
2. Write failing test for a failing command.
3. Implement command runner with timeout, cwd, stdout/stderr tail, full log artifact path.
4. Mark report failed if required command fails.
5. Verify with pytest.

Design constraints:
- Default timeout should be explicit and configurable.
- No shell injection from config: command list preferred, shell string only when intentionally accepted.
- Store full command output under output directory.

# Task 4: Discover repo verification commands

Objective: Reuse existing project conventions before inventing new workflow layers.

Files:
- Create: `hermes_cli/verification/discovery.py`
- Test: `tests/verification/test_discovery.py`

Sources in priority order:
1. Explicit CLI `--command` flags.
2. Repo-local config, if present later: `.hermes/verification.yaml`.
3. Known repo family map: `/Users/cal/dev/orca/hermes/repo-families.yaml`.
4. Makefile/package fallback suggestions, marked `not_run` unless explicit.

For v1:
- Implement explicit `--command` first.
- Implement family map lookup for exact repo or similar repo paths.
- Do not add repo-local config until the first two paths work.

# Task 5: Add `hermes verify` CLI

Objective: Give workers one stable command to call.

Files:
- Modify: likely `hermes_cli/main.py` or CLI command registration file after inspection.
- Create: `hermes_cli/verification/cli.py`
- Test: `tests/verification/test_cli.py`

CLI sketch:

```bash
hermes verify \
  --repo /Users/cal/dev/program \
  --task-type mobile-ui \
  --command 'make test-mobile' \
  --command 'make test-backend' \
  --output /tmp/hermes-verification/program-task
```

Output:
- prints path to `verification.md`
- exits 0 only when required checks pass
- exits non-zero when required checks fail
- exits with partial status if evidence couldn't be collected but commands passed

# Task 6: Add web UI evidence behind `--url`

Objective: For web tasks, capture proof the page loads and screenshots exist.

Files:
- Create: `hermes_cli/verification/web_ui.py`
- Test: `tests/verification/test_web_ui.py`

Behavior:
- If `--url` supplied, launch browser check.
- Capture screenshot into output artifacts.
- Capture title, HTTP-ish load result, console errors if feasible.
- If browser dependencies are missing, mark `not_run` with a limitation instead of lying.

Implementation note:
- Prefer Playwright if already present or cheap to add.
- If dependency addition is annoying, v1 can use existing Hermes browser tooling only in agent flow and leave CLI browser evidence as v1.5.

# Task 7: Integrate harness into worker prompts

Objective: Make verification mandatory in delegated coding workflows.

Files likely to modify:
- Hermes skill: `subagent-driven-development`
- Hermes skill: `codex`
- Hermes skill: `claude-code`
- Possibly Orca prompts/docs if worker orchestration lives there.

Prompt rule:
- Worker final response must include verification report path.
- If no report path exists, parent treats completion as unverified.
- Worker must list limitations honestly.

Important:
- The harness reports evidence.
- Callum judges taste.
- Monitor/review agents can check spec compliance and code quality, but not override Callum's taste.

# Task 8: Show verification summaries in Hermes UI

Objective: Make evidence inspectable without reading logs.

Files likely to inspect/change:
- `hermes_cli/web_server.py`
- `web/src/pages/*`
- `web/src/lib/api.ts`

Minimal UI v1:
- Add a Verification page or attach latest verification reports to job/session details.
- Show status, repo, branch/SHA, checks, artifacts, and markdown summary.
- Auto-refresh if a verification run is active.

Do this after CLI/report format is stable. Do not start here.

# Task 9: Add mobile/simulator support

Objective: Bring the harness to Callum's main app shape.

Possible integrations:
- Expo start + iOS simulator screenshot.
- Maestro flow if repo has flows.
- `make test-mobile` plus optional simulator evidence.

Start with `program` family and do not generalize too early.

# Task 10: Dogfood on a real task

Objective: Prove it catches bullshit.

Candidate dogfood task:
- A small Hermes UI tweak or `program` mobile screen tweak.

Required evidence:
- report JSON/markdown
- test command output
- screenshot artifact if UI
- final response includes exact report path

Then ask Callum to accept/reject the quality. If rejected, log the behavioral incident in Orca, not Brain.

---

## Suggested build order

Phase 1: Core CLI evidence
1. report model
2. repo state
3. command runner
4. CLI
5. discovery via explicit commands and repo-family map

Phase 2: Visual evidence
6. web URL screenshot evidence
7. UI page for reports

Phase 3: Mobile evidence
8. Expo/iOS simulator path for `program` family
9. Maestro support if useful

Phase 4: Workflow enforcement
10. Update worker skills/prompts so workers must return a report path.
11. Dogfood and refine.

## Testing / validation

Focused tests:

```bash
./venv/bin/python -m pytest tests/verification -q -o 'addopts='
```

Regression tests:

```bash
./venv/bin/python -m pytest tests/cron/test_jobs.py::TestJobRunState -q -o 'addopts='
```

Web build only after UI integration:

```bash
cd web && npm run build
```

Manual dogfood command:

```bash
hermes verify --repo /Users/cal/.hermes/hermes-agent --command './venv/bin/python -m pytest tests/verification -q -o addopts=' --output /tmp/hermes-verification/dogfood
```

Expected final proof:
- `/tmp/hermes-verification/dogfood/verification.json`
- `/tmp/hermes-verification/dogfood/verification.md`
- command log artifacts
- non-zero exit on failing checks

## Risks / tradeoffs

- Biggest risk: building a fancy framework before one boring CLI works. Avoid that.
- Browser/simulator automation can be flaky. Treat visual evidence as artifact capture, not absolute correctness.
- If report format is unstable, UI integration will churn. Keep UI after core reports.
- Do not let verification become taste judgment. It proves what ran and what was observed.
- Avoid per-repo custom hacks until `program` and Hermes dogfooding prove the base shape.

## Open questions for Callum

1. Should v1 live in Hermes Agent, Orca, or a small separate repo?
   - My vote: Hermes Agent, because this is a control-plane feature.
2. Should first dogfood target be Hermes web UI or `program` mobile?
   - My vote: Hermes web UI first because browser evidence is simpler than iOS simulator.
3. How strict should worker final-response enforcement be?
   - My vote: harsh. No verification report path = unverified, no matter how confident the worker sounds.
