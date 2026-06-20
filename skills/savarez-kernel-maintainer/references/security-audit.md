# Security Audit Reference

## Purpose

Audit kernel security configuration.

## Checks

| Config | Description |
|--------|-------------|
| CONFIG_SECURITY | Security framework |
| CONFIG_SECURITY_SELINUX | SELinux |
| CONFIG_CC_STACKPROTECTOR | Stack protection |
| CONFIG_RANDOMIZE_BASE | KASLR |

## Scoring

| Check | Pass | Fail |
|-------|------|------|
| SECURITY | +2 | 0 |
| SELINUX | +2 | 0 |
| CC_STACKPROTECTOR | +2 | 0 |
| RANDOMIZE_BASE | +2 | 0 |
| **Total** | **8** | |

## Common Issues

| Issue | Impact | Fix |
|-------|--------|-----|
| SECURITY disabled | No security | Enable SECURITY |
| No SELinux | Reduced security | Enable SELinux |
| No stack protection | Vulnerable | Enable CC_STACKPROTECTOR |

## Example Output

```
=== Security Audit ===

[✓] CONFIG_SECURITY
[✓] CONFIG_SECURITY_SELINUX
[✓] CONFIG_CC_STACKPROTECTOR
[✓] CONFIG_RANDOMIZE_BASE

Security: 8/8
```
