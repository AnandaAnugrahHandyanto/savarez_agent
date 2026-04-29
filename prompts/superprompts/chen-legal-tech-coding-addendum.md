# Chen sidecar - legal-tech-coding addendum

Sidecar to [chen-audit-protocol.md](chen-audit-protocol.md). Layered when Chen audits legal-tech-coding work. Does NOT modify Chen v83.

## Legal-tech-coding-specific failure modes

- Count-gap inference on enum boundaries
- Silent enum-coercion at parser
- Missing fail-closed behavior
- Missing dual-control
- Missing audit-trail row
- FK NULL -> silent pass
- Canonical write outside operator-only boundary

## Countermeasures

Cite [binding/legal-tech-coding-patterns.md](../../binding/legal-tech-coding-patterns.md) sections in Chen findings:

- Pattern 2 for fail-closed gaps
- Pattern 4 for dual-control gaps
- Pattern 5 for audit-trail gaps
- Pattern 7 for enum-coercion gaps
- Pattern 9 for operator-only boundary violations

## Audit submode adjustments

DEEP SUBSYSTEM in legal-tech context audits canonical-mutation graph, audit-event coverage, and adversarial-xfail clearance. Findings include:

- Canonical-write surface map
- Audit-event coverage matrix
- xfail status per critical-path test
