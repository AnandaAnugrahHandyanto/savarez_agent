# Kernel Health Audit Reference

## Purpose

Overall kernel source health check.

## Checks

| Check | Weight | Description |
|-------|--------|-------------|
| Makefile | 20% | Root Makefile exists |
| Kconfig | 20% | Root Kconfig exists |
| arch/ | 20% | Architecture directory |
| drivers/ | 20% | Drivers directory |
| scripts/ | 20% | Build scripts |

## Scoring

| Check | Pass | Fail |
|-------|------|------|
| Makefile | +3 | 0 |
| Kconfig | +3 | 0 |
| arch/ | +3 | 0 |
| drivers/ | +3 | 0 |
| scripts/ | +3 | 0 |
| **Total** | **15** | |

## Common Issues

| Issue | Impact | Fix |
|-------|--------|-----|
| Missing Makefile | Build failure | Add Makefile |
| Missing Kconfig | Config failure | Add Kconfig |
| Missing arch/ | No arch support | Add arch |

## Example Output

```
=== Kernel Health Audit ===

[✓] Makefile
[✓] Kconfig
[✓] arch/
[✓] drivers/
[✓] scripts/

Kernel Health: 15/15
```
