## What does this PR do?

<!-- Describe the change clearly. What problem does it solve? Why is this approach the right one? -->



## Related Issue / Plan / Control Doc

<!-- Link the issue this PR addresses. If no issue exists, consider creating one first. -->

Fixes #

<!-- For long-running, autonomous, or session-continuity work, link the PRD/plan/control doc and any run-ledger/capsule/evidence handles. Use N/A for simple one-off changes. -->

- PRD / implementation plan:
- Long-task control doc / resume capsule:
- Run ledger / state capsule handles:
- Evidence or artifact manifest:

## Type of Change

<!-- Check the one that applies. -->

- [ ] 🐛 Bug fix (non-breaking change that fixes an issue)
- [ ] ✨ New feature (non-breaking change that adds functionality)
- [ ] 🔒 Security fix
- [ ] 📝 Documentation update
- [ ] ✅ Tests (adding or improving test coverage)
- [ ] ♻️ Refactor (no behavior change)
- [ ] 🎯 New skill (bundled or hub)

## Changes Made

<!-- List the specific changes. Include file paths for code changes. -->

- 

## How to Test

<!-- Steps to verify this change works. For bugs: reproduction steps + proof that the fix works. -->

1. 
2. 
3. 

## TDD / Review Evidence

<!-- For code changes, include the tests planned before implementation, RED evidence, GREEN evidence, and any independent/second-review result. Use N/A only for docs-only or non-code changes. -->

- Planned tests vs. acceptance criteria:
- RED evidence (failing tests observed before implementation):
- GREEN evidence (focused tests passing after implementation):
- Broader validation / regression checks:
- Independent review / second opinion:

## Operational / Safety Impact

<!-- Note config changes, migrations, storage/retention impact, privacy/redaction impact, rollback plan, or user-visible behavior. -->

- Config or migration impact:
- Storage / retention / privacy impact:
- Rollback plan:
- Not authorized / out of scope:

## Checklist

<!-- Complete these before requesting review. -->

### Code

- [ ] I've read the [Contributing Guide](https://github.com/NousResearch/hermes-agent/blob/main/CONTRIBUTING.md)
- [ ] My commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (`fix(scope):`, `feat(scope):`, etc.)
- [ ] I searched for [existing PRs](https://github.com/NousResearch/hermes-agent/pulls) to make sure this isn't a duplicate
- [ ] My PR contains **only** changes related to this fix/feature (no unrelated commits)
- [ ] I've run `pytest tests/ -q` and all tests pass
- [ ] I've added tests for my changes (required for bug fixes, strongly encouraged for features)
- [ ] For behavioral code changes, I followed TDD or documented why it was not applicable
- [ ] For long-running/autonomous work, I updated the control doc/resume capsule and evidence manifest, or marked them N/A
- [ ] I resolved or explicitly triaged reviewer/second-review comments
- [ ] I've tested on my platform (e.g. Ubuntu 24.04, macOS 15.2, Windows 11):

### Documentation & Housekeeping

<!-- Check all that apply. It's OK to check "N/A" if a category doesn't apply to your change. -->

- [ ] I've updated relevant documentation (README, `docs/`, docstrings) — or N/A
- [ ] I've updated `cli-config.yaml.example` if I added/changed config keys — or N/A
- [ ] I've updated `CONTRIBUTING.md` or `AGENTS.md` if I changed architecture or workflows — or N/A
- [ ] I've considered cross-platform impact (Windows, macOS) per the [compatibility guide](https://github.com/NousResearch/hermes-agent/blob/main/CONTRIBUTING.md#cross-platform-compatibility) — or N/A
- [ ] I've updated tool descriptions/schemas if I changed tool behavior — or N/A

## For New Skills

<!-- Only fill this out if you're adding a skill. Delete this section otherwise. -->

- [ ] This skill is **broadly useful** to most users (if bundled) — see [Contributing Guide](https://github.com/NousResearch/hermes-agent/blob/main/CONTRIBUTING.md#should-the-skill-be-bundled)
- [ ] SKILL.md follows the [standard format](https://github.com/NousResearch/hermes-agent/blob/main/CONTRIBUTING.md#skillmd-format) (frontmatter, trigger conditions, steps, pitfalls)
- [ ] No external dependencies that aren't already available (prefer stdlib, curl, existing Hermes tools)
- [ ] I've tested the skill end-to-end: `hermes --toolsets skills -q "Use the X skill to do Y"`

## Screenshots / Logs

<!-- If applicable, add screenshots or log output showing the fix/feature in action. -->

