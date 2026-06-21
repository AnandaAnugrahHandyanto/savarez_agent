---
name: savarez-security-auditor
description: "Android security validation: SELinux completeness, permission overuse, patch level, signing, key management, network security, secure boot, security scoring."
---

# Savarez Security Auditor

Comprehensive security validation for Android ROM builds.

## Purpose

Validate security posture, detect vulnerabilities, and verify compliance for Android ROM and kernel builds. Focuses exclusively on security — not build readiness or functionality.

## Skill Type

- **Audit-based** (security-focused)
- **No runtime execution**
- **No automatic code modification**
- **Documentation-driven**

## When to Use

| Scenario | Use This Skill |
|----------|----------------|
| Security audit | ✅ |
| Permission review | ✅ |
| Patch level check | ✅ |
| Signing verification | ✅ |
| Key management audit | ✅ |
| Network security review | ✅ |
| Secure boot validation | ✅ |
| Build readiness | Use savarez-android-rom-maintainer |
| Kernel health | Use savarez-kernel-maintainer |
| Boot readiness | Use savarez-device-bringup-maintainer |

## Capabilities

### 8 Capabilities

| # | Capability | Weight | Purpose |
|---|------------|--------|---------|
| 1 | SELinux Policy Completeness | 20% | Policy quality audit |
| 2 | Permission Overuse Detection | 15% | App permission analysis |
| 3 | Security Patch Level Validator | 20% | Patch currency check |
| 4 | Signing & Verification Audit | 15% | Image signing validation |
| 5 | Key Management Audit | 10% | Key security practices |
| 6 | Network Security Audit | 10% | Network security config |
| 7 | Secure Boot Security Audit | 10% | Boot security mechanisms |
| 8 | Security Score Report | — | Aggregated scoring |

---

## Security Severity Model

| Level | Description | Action |
|-------|-------------|--------|
| CRITICAL | Immediate exploitation risk | Fix immediately |
| HIGH | Significant security risk | Fix before release |
| MEDIUM | Moderate security risk | Plan to fix |
| LOW | Minor security risk | Consider fixing |

## Severity Penalty

```
Penalty = (
    CRITICAL_count * 25 +
    HIGH_count * 10 +
    MEDIUM_count * 3 +
    LOW_count * 1
)
```

---

## Scoring Model

### Base Score

```
Base Score = (
    SELinux Score * 0.20 +
    Permission Score * 0.15 +
    Patch Level Score * 0.20 +
    Signing Score * 0.15 +
    Key Management Score * 0.10 +
    Network Score * 0.10 +
    Secure Boot Score * 0.10
)
```

### Final Score

```
Final Score = max(0, Base Score - Penalty)
```

### Categories

| Score | Category |
|-------|----------|
| 90-100 | SECURE |
| 70-89 | GOOD |
| 50-69 | MODERATE |
| 25-49 | WEAK |
| 0-24 | INSECURE |

---

## Output Format

Every capability produces:

```
=== [Capability Name] ===
[✓/!] [Finding]
[✓/!] [Finding]

Score: [X]/100
Severity: [CRITICAL/HIGH/MEDIUM/LOW]
```

Final report:

```
=== Security Score ===
Base Score: [X]
Penalty: [Y]
Final Score: [X-Y]/100
Category: [SECURE/GOOD/MODERATE/WEAK/INSECURE]

=== Risk Summary ===
CRITICAL: [count]
HIGH: [count]
MEDIUM: [count]
LOW: [count]

=== Recommendations ===
1. [recommendation]
2. [recommendation]
```

---

## Reference Files

| File | Purpose |
|------|---------|
| selinux-completeness.md | SELinux policy audit |
| permission-overuse.md | Permission analysis |
| patch-level-validator.md | Patch currency check |
| signing-audit.md | Signing verification |
| key-management.md | Key security |
| network-security.md | Network security |
| secure-boot.md | Boot security |
| security-score.md | Score calculation |

---

## Separation from Other Skills

### vs ROM Maintainer

| ROM Maintainer | Security Auditor |
|----------------|------------------|
| SELinux policy exists | SELinux policy quality |
| Build permissions | App permission overuse |
| Network config | Network security |

### vs Kernel Maintainer

| Kernel Maintainer | Security Auditor |
|-------------------|------------------|
| Kernel SELinux config | SELinux policy completeness |
| Kernel version | Security patch level |
| Module loading | — |

### vs Device Bringup

| Device Bringup | Security Auditor |
|----------------|------------------|
| Boot chain presence | Boot security mechanisms |
| Bootloader config | AVB/dm-verity status |
| — | Key management |

---

## Example Output

```
=== Security Audit Report ===

Device: Poco F7 (onyx)
Build: lineage-onyx-userdebug

=== SELinux Policy Completeness ===
[✓] Policy present
[!] 2 permissive domains
[✓] No unconfined domains
[✓] neverallow enforced
Score: 85/100

=== Permission Overuse ===
[!] 15 dangerous permissions
[✓] No signatureOrSystem abuse
[✓] Protection levels set
Score: 75/100

=== Security Patch Level ===
[✓] Patch level: 2026-06-05
[✓] Current (0-3 months)
Score: 95/100

=== Signing & Verification ===
[✓] AVB enabled
[✓] dm-verity enabled
[✓] Signatures verified
Score: 95/100

=== Key Management ===
[✓] Keys not exposed
[✓] Proper permissions
[!] No key rotation
Score: 80/100

=== Network Security ===
[✓] No cleartext traffic
[✓] SSL/TLS configured
[✓] Certificate pinning
Score: 90/100

=== Secure Boot ===
[✓] AVB enabled
[✓] dm-verity active
[✓] Rollback protection
Score: 95/100

=== Security Score ===
Base Score: 87
Penalty: 3
Final Score: 84/100
Category: GOOD

=== Risk Summary ===
CRITICAL: 0
HIGH: 0
MEDIUM: 2
LOW: 0

=== Recommendations ===
1. Remove permissive domains
2. Implement key rotation
```

---

## Notes

- All checks are static analysis (no runtime dependencies)
- Security patch level is most critical factor
- CRITICAL findings heavily impact score
- False positives are mitigated by context analysis
- Always verify findings before remediation
