---
name: legal-tech-context
description: Legal-tech-coding domain context. Auto-invokes when reading/editing files under plugins/legal-tech-*/ paths OR matching canonical-state-mutation signatures (CREATE/INSERT/UPDATE on *_history tables, GRANT/REVOKE statements, enum-type definitions, confidence comparison logic, FK lookup error-path routing). Surfaces relevant patterns from binding/legal-tech-coding-patterns.md. Always-on; no toggle.
---

# Legal-tech-context

When reading or editing legal-tech production code, surface the 12 patterns from [binding/legal-tech-coding-patterns.md](../../../binding/legal-tech-coding-patterns.md). Before any edit that touches canonical state, ask:

1. Is this fail-closed?
2. Does this require multi-factor verification?
3. Is dual-control needed?
4. Is the audit-trail row generated?
5. Is the enum boundary enforced?
6. Is privileged/PII content scrubbed from logs and exceptions?

If any answer is no or uncertain, halt and ask the operator before continuing.
