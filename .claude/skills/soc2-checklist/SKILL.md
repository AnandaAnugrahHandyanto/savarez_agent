---
name: soc2-checklist
description: Applies SOC 2 Type II framework as code review checklist. Auto-invokes during PR review or pre-commit when changed files touch authentication, authorization (GRANT/REVOKE), audit logging, encryption configuration, key rotation, or change control.
---

# SOC2-checklist

For each change under SOC 2 scope, verify:

- Segregation of duties: is the operation gated by role, dual-control, or operator-only boundary?
- Audit logging: does every mutation produce an audit-trail row with subject_id, action, timestamp?
- Encryption-at-rest: are sensitive fields encrypted and keys rotated per policy?
- Access control matrix: does the change respect the role matrix?
- Change-control trail: is the change documented, reviewed, and approved per process?

Findings go to `audits/code-review/`.
