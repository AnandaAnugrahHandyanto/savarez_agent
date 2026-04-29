# Legal-tech-coding patterns (generalized from CDB v7.2)

Patterns ANY legal-tech AI infrastructure code must follow. Always-on; no toggle.

## 1. Authority hierarchy precedence
Binding doc > ratified artifacts > reports > archive. Resolve conflicts by precedence, never by recency or volume.

## 2. Fail-closed gate on canonical mutations
Validation logic MUST fail-closed: NULL/missing-FK -> exception, never permissive default.

## 3. Multi-factor verification before high-stakes mutations
Production-canonical writes require explicit gate satisfaction. Never inferred satisfaction.

## 4. Dual-control on canonical writes
Operations with severe blast radius require a second approver distinct from initiator. SOC 2 segregation enforced at code level, not just process.

## 5. Append-only history
Every state mutation produces a permanent audit row with explicit transition_type. No UPDATE/DELETE on history tables. Tombstones via new rows.

## 6. Stateless producer / stateful authority separation
AI-driven inference (producer) is stateless. Canonical-state ownership (authority layer) is centralized. Trust boundary enforced.

## 7. Enumeration boundary governance
Schema enums are canonical. Legacy values pass through explicit parser/contract-check at boundary. Never silently coerced.

## 8. Adversarial xfail as ship gate
Known-failure tests stay tracked as `strict xfail`. Clearance is a precondition for tier promotion.

## 9. Operator-only boundaries
Agent never pushes to main, opens PRs, applies migrations, or edits canonical sources without explicit authorization. SOC 2 change control enforced via agent rules.

## 10. Confidence floor with two-place precision
Legal-tech ML confidence thresholds are gates, not advisories. Stored to two-place precision; >= 0.99 for canonical promotion.

## 11. Sub-second taxonomy invariants
Domain enumerations are contracts. Lowercase/legacy values normalize through explicit parser; never persisted directly.

## 12. RBAC at code-review-awareness level
Production legal-tech infra requires fine-grained role-based access control. Code reviews enumerate roles; agent knows the matrix.
