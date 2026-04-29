---
name: canonical-mutation-gate
description: Auto-invokes on canonical-state-mutation code paths. Reminds of fail-closed validation, audit-trail row generation, dual-control requirement, error-path routing, transition_type explicitness. Auto-invokes when emitting INSERT/UPDATE/DELETE on canonical tables, GRANT/REVOKE statements, or any code that mutates state-of-record data.
---

# Canonical-mutation-gate

Halt before emitting code that mutates canonical state. Required:

- Fail-closed validation (NULL -> exception, never pass)
- Audit-trail row generated in same transaction
- Dual-control evaluated
- Error-path explicitly routed
- Transition_type set explicitly on history row

If any of these are missing, the code is not ship-ready. Surface the gap to the operator.
