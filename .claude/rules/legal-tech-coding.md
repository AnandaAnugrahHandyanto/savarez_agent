# Rule: legal-tech-coding

Paths: repo-wide, always-on.

DO NOT:
- Do not silently pass validation.
- Do require explicit error-path routing on canonical-mutation paths.
- Do log every state mutation.
- Do require dual-control on canonical-state operations.
- Do scrub credentials, PII, and privileged content from logs and exception messages.
- Do treat enum boundaries as contracts.
- Do treat adversarial xfails as ship-gate blockers.
- Do enforce SOC 2 segregation of duties at code level.

Architecture Notes: the agent helps build legal-tech; it is not a legal-tech agent.

Thresholds: canonical mutation paths require legal-tech-reviewer review.

Key Files: `binding/legal-tech-coding-patterns.md`, `.claude/agents/legal-tech-reviewer.md`.
